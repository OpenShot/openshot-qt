"""
 @file
 @brief This file contains optimized-preview proxy management logic.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import copy
import json
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from qt_api import QObject, pyqtSignal, pyqtSlot
from qt_api import QFileDialog

import openshot

from classes import info
from classes.app import get_app
from classes.assets import get_assets_path
from classes.logger import log
from classes.path_utils import absolute_media_path, comparable_media_path
from classes.query import Clip, File, Transition
from classes.thumbnail import (
    GenerateThumbnailFromFrame,
    RoundFrameToThumbnailGrid,
    ThumbnailPathForFrame,
)
from classes.updates import UpdateAction


def dialog_preview_reader_data(file_obj, prefer_proxy=True):
     """Return reader payload for dialog previews, optionally preferring a valid proxy reader."""
     data = getattr(file_obj, "data", {}) if file_obj else {}
     if not isinstance(data, dict):
         data = {}

     file_id = str(getattr(file_obj, "id", "") or data.get("id") or "")
     proxy_reader = data.get("proxy_reader")
     if prefer_proxy and isinstance(proxy_reader, dict):
         if proxy_reader.get("missing"):
             proxy_reader = None
         else:
             proxy_path = absolute_media_path(proxy_reader.get("path"))
             if proxy_path and os.path.exists(proxy_path):
                 resolved = copy.deepcopy(proxy_reader)
                 resolved["path"] = proxy_path
                 if file_id:
                     resolved["id"] = file_id
                 return resolved

     resolved = copy.deepcopy(data)
     source_path = absolute_media_path(resolved.get("path"))
     if source_path:
         resolved["path"] = source_path
     if file_id:
         resolved["id"] = file_id
     return resolved


class ProxyService(QObject):
     """Encapsulates optimized-preview proxy generation, linking, and runtime rewrites."""

     proxy_generated = pyqtSignal(str, object, str)
     file_job_changed = pyqtSignal(str)
     queue_changed = pyqtSignal()
     job_updated = pyqtSignal(str, str, int)
     job_finished = pyqtSignal(str, str)
     ACTIVE_STATES = ("queued", "running", "canceling")
     OPTIMIZE_CACHE_MAX_BYTES = 16 * 1024 * 1024
     OPTIMIZE_CACHE_CLEAR_INTERVAL = 120
     MATCHABLE_VIDEO_EXTENSIONS = {
         ".3g2", ".3gp", ".asf", ".avi", ".f4v", ".flv", ".m2t", ".m2ts", ".m4v", ".mkv",
         ".mov", ".mp2", ".mp4", ".mpeg", ".mpg", ".mts", ".mxf", ".ogv", ".rm", ".rmvb",
         ".ts", ".vob", ".webm", ".wmv",
     }
     _PROXY_PREFIX_RE = re.compile(
         r"^(?:proxy|proxies|prox|optimized?|optimised|preview|lowres|low_res|low-res|offline|transcoded?)[\s._-]+",
         re.IGNORECASE,
     )
     _PROXY_SUFFIX_RE = re.compile(
         r"[\s._-]+(?:proxy|proxies|prox|optimized?|optimised|preview|lowres|low_res|low-res|offline|transcoded?)$",
         re.IGNORECASE,
     )
     _RESOLUTION_SUFFIX_RE = re.compile(
         r"[\s._-]+(?:360p|540p|720p|1080p|1440p|2160p|4320p|4k|8k)$",
         re.IGNORECASE,
     )
     _CAMERA_PROXY_SUFFIX_RE = re.compile(r"[\s._-]+p$", re.IGNORECASE)

     def __init__(self, win):
         super().__init__(win)
         self.win = win
         self._executor = None
         self._jobs = {}
         self._lock = threading.RLock()
         self._ensure_executor()
         self.proxy_generated.connect(self._on_proxy_generated)

     def shutdown(self):
         if getattr(self, "_executor", None):
             self._shutdown_executor(self._executor)

     def create_for_files(self, files):
         files = [f for f in (files or []) if getattr(f, "id", None)]
         if not files:
             return

         self._ensure_executor()
         os.makedirs(self._proxy_root(), exist_ok=True)
         submitted = 0
         linked_existing = 0
         skipped = 0
         for file_obj in files:
             file_id = str(file_obj.id or "")
             if not file_id:
                 continue
             if self.get_active_job_for_file(file_id):
                 log.info("Optimize Preview create_for_files file_id=%s skipped: job already active", file_id)
                 skipped += 1
                 continue
             if self.has_proxy_reader(file_obj) and not self.has_missing_proxy(file_obj):
                 log.info("Optimize Preview create_for_files file_id=%s skipped: already optimized", file_id)
                 skipped += 1
                 continue
             snapshot = copy.deepcopy(file_obj.data or {})
             existing_output_path = self._existing_proxy_output_path(file_id, snapshot)
             if existing_output_path:
                 try:
                     proxy_reader = self._reader_json_for_path(existing_output_path, file_id)
                     self._save_proxy_reader(file_id, proxy_reader)
                     log.info("Optimize Preview create_for_files file_id=%s linked existing output=%s", file_id, existing_output_path)
                     linked_existing += 1
                     continue
                 except Exception as exc:
                     log.warning(
                         "Optimize Preview create_for_files file_id=%s ignored invalid existing output=%s (%s)",
                         file_id,
                         existing_output_path,
                         exc,
                     )
                     try:
                         os.remove(existing_output_path)
                     except Exception as cleanup_exc:
                         log.warning(
                             "Optimize Preview create_for_files file_id=%s failed to remove invalid existing output=%s (%s)",
                             file_id,
                             existing_output_path,
                             cleanup_exc,
                         )
             output_path = self._reserve_proxy_output_path(file_id, snapshot)
             with self._lock:
                 self._jobs[file_id] = {
                     "id": file_id,
                     "status": "queued",
                     "progress": 0,
                     "cancel_requested": False,
                     "output_path": output_path,
                 }
             future = self._executor.submit(self._build_proxy_reader, file_id, snapshot)
             with self._lock:
                 if file_id in self._jobs:
                     self._jobs[file_id]["future"] = future
             future.add_done_callback(lambda fut, fid=file_id: self._emit_proxy_result(fid, fut))
             self._emit_job_change(file_id)
             submitted += 1

         if submitted:
             status = "Optimize Preview: creating {} item(s)".format(submitted)
             if linked_existing:
                 status += ", linked {}".format(linked_existing)
             if skipped:
                 status += ", skipped {}".format(skipped)
             self._show_status(status)
         elif linked_existing:
             status = "Optimize Preview: linked {} item(s)".format(linked_existing)
             if skipped:
                 status += ", skipped {}".format(skipped)
             self._show_status(status, 3000)
         elif skipped:
             self._show_status("Optimize Preview: skipped {} item(s)".format(skipped), 3000)

     def use_existing_for_files(self, files):
         files = [f for f in (files or []) if getattr(f, "id", None)]
         if not files:
             return

         start_dir = self._proxy_root()
         if not start_dir:
             start_dir = info.HOME_PATH
         translator = getattr(self.win, "_tr", None) or getattr(get_app(), "_tr", lambda text: text)
         selected_folder = QFileDialog.getExistingDirectory(
             self.win,
             translator("Choose optimized preview folder"),
             start_dir,
         )
         if not selected_folder:
             return

         matched = 0
         missing = 0
         invalid = 0
         changed_file_ids = []
         folder_index = self._index_existing_optimized_files(selected_folder)
         updates = get_app().updates
         previous_tid = getattr(updates, "transaction_id", None)
         updates.transaction_id = str(uuid.uuid4())
         try:
             for file_obj in files:
                 match_path = self._match_existing_optimized_path(file_obj, selected_folder, folder_index)
                 if match_path and os.path.exists(match_path):
                     try:
                         proxy_reader = self._reader_json_for_path(match_path, file_obj.id)
                         matched += 1
                         self._save_proxy_reader(file_obj.id, proxy_reader, apply_runtime=False, emit_job_change=False)
                         changed_file_ids.append(str(file_obj.id or ""))
                     except Exception as exc:
                         log.warning(
                             "Optimize Preview use_existing_for_files file_id=%s skipped invalid existing file=%s (%s)",
                             file_obj.id,
                             match_path,
                             exc,
                         )
                         invalid += 1
                 else:
                     proxy_reader = self._missing_proxy_reader(file_obj, selected_folder)
                     self._save_proxy_reader(file_obj.id, proxy_reader, apply_runtime=False, emit_job_change=False)
                     changed_file_ids.append(str(file_obj.id or ""))
                     missing += 1
         finally:
             updates.transaction_id = previous_tid

         self.apply_runtime_updates_for_files(changed_file_ids)
         for file_id in changed_file_ids:
             self._emit_job_change(file_id)

         status = "Optimize Preview: linked {} item(s), missing {}".format(matched, missing)
         if invalid:
             status += ", invalid {}".format(invalid)
         self._show_status(status, 4000)

     def remove_for_files(self, files):
         files = [f for f in (files or []) if getattr(f, "id", None)]
         if not files:
             return

         removed = 0
         changed_file_ids = []
         updates = get_app().updates
         previous_tid = getattr(updates, "transaction_id", None)
         updates.transaction_id = str(uuid.uuid4())
         try:
             for file_obj in files:
                 file_id = str(file_obj.id or "")
                 self.cancel_job(file_id)
                 fresh_file = File.get(id=file_id)
                 data = getattr(fresh_file, "data", {}) or {}
                 if "proxy_reader" not in data:
                     continue
                 data.pop("proxy_reader", None)
                 fresh_file.data = data
                 fresh_file.save()

                 refreshed = File.get(id=file_id)
                 refreshed_data = getattr(refreshed, "data", {}) or {}
                 if "proxy_reader" in refreshed_data and refreshed and refreshed.key:
                     get_app().updates.delete(refreshed.key + ["proxy_reader"])
                 changed_file_ids.append(file_id)
                 removed += 1
         finally:
             updates.transaction_id = previous_tid

         self.apply_runtime_updates_for_files(changed_file_ids)
         for file_id in changed_file_ids:
             self._emit_job_change(file_id)

         if removed:
             self._show_status("Optimize Preview: removed {} item(s)".format(removed), 3000)

     def delete_and_unlink_for_files(self, files):
         files = [f for f in (files or []) if getattr(f, "id", None)]
         if not files:
             return 0

         deleted = 0
         unlinked = 0
         changed_file_ids = []
         updates = get_app().updates
         previous_tid = getattr(updates, "transaction_id", None)
         updates.transaction_id = str(uuid.uuid4())
         try:
             for file_obj in files:
                 file_id = str(file_obj.id or "")
                 self.cancel_job(file_id)
                 fresh_file = File.get(id=file_id)
                 data = getattr(fresh_file, "data", {}) or {}
                 proxy_reader = data.get("proxy_reader")
                 if not isinstance(proxy_reader, dict):
                     continue

                 proxy_path = absolute_media_path(proxy_reader.get("path"))
                 if proxy_path and os.path.exists(proxy_path):
                     proxy_abs = os.path.abspath(proxy_path)
                     try:
                         os.remove(proxy_abs)
                         deleted += 1
                     except Exception:
                         log.warning("Optimize Preview delete failed for %s", proxy_abs, exc_info=1)

                 data.pop("proxy_reader", None)
                 fresh_file.data = data
                 fresh_file.save()

                 refreshed = File.get(id=file_id)
                 refreshed_data = getattr(refreshed, "data", {}) or {}
                 if "proxy_reader" in refreshed_data and refreshed and refreshed.key:
                     get_app().updates.delete(refreshed.key + ["proxy_reader"])
                 changed_file_ids.append(file_id)
                 unlinked += 1
         finally:
             updates.transaction_id = previous_tid

         self.apply_runtime_updates_for_files(changed_file_ids)
         for file_id in changed_file_ids:
             self._emit_job_change(file_id)

         status = "Optimize Preview: deleted {}, unlinked {}".format(deleted, unlinked)
         if unlinked:
             self._show_status(status, 4000)
         return deleted

     def has_internal_project_proxy_files(self):
         proxy_root = self._proxy_root()
         if not proxy_root or not os.path.isdir(proxy_root):
             return False
         for _, _, files in os.walk(proxy_root):
             if files:
                 return True
         return False

     def delete_internal_project_proxy_files(self):
         proxy_root = os.path.abspath(str(self._proxy_root() or ""))
         proxy_root_prefix = proxy_root + os.sep if proxy_root else ""
         if not proxy_root_prefix or not os.path.isdir(proxy_root):
             return 0

         deleted = 0
         unlinked = 0
         changed_file_ids = []
         updates = get_app().updates
         previous_tid = getattr(updates, "transaction_id", None)
         updates.transaction_id = str(uuid.uuid4())
         try:
             for file_obj in File.filter():
                 file_id = str(getattr(file_obj, "id", "") or "")
                 if not file_id:
                     continue
                 fresh_file = File.get(id=file_id)
                 data = getattr(fresh_file, "data", {}) or {}
                 proxy_reader = data.get("proxy_reader")
                 if not isinstance(proxy_reader, dict):
                     continue

                 proxy_path = absolute_media_path(proxy_reader.get("path"))
                 if not proxy_path:
                     continue
                 proxy_abs = os.path.abspath(proxy_path)
                 if not proxy_abs.startswith(proxy_root_prefix):
                     continue

                 self.cancel_job(file_id)
                 if os.path.exists(proxy_abs):
                     try:
                         os.remove(proxy_abs)
                         deleted += 1
                     except Exception:
                         log.warning("Optimize Preview delete failed for %s", proxy_abs, exc_info=1)

                 data.pop("proxy_reader", None)
                 fresh_file.data = data
                 fresh_file.save()

                 refreshed = File.get(id=file_id)
                 refreshed_data = getattr(refreshed, "data", {}) or {}
                 if "proxy_reader" in refreshed_data and refreshed and refreshed.key:
                     get_app().updates.delete(refreshed.key + ["proxy_reader"])
                 changed_file_ids.append(file_id)
                 unlinked += 1
         finally:
             updates.transaction_id = previous_tid

         try:
             for root, dirs, files in os.walk(proxy_root, topdown=False):
                 for name in files:
                     file_path = os.path.join(root, name)
                     try:
                         os.remove(file_path)
                         deleted += 1
                     except Exception:
                         log.warning("Optimize Preview delete failed for %s", file_path, exc_info=1)
                 for name in dirs:
                     dir_path = os.path.join(root, name)
                     try:
                         os.rmdir(dir_path)
                     except OSError:
                         pass
         except Exception:
             log.warning("Optimize Preview cleanup failed for %s", proxy_root, exc_info=1)

         self.apply_runtime_updates_for_files(changed_file_ids)
         for file_id in changed_file_ids:
             self._emit_job_change(file_id)

         if deleted or unlinked:
             self._show_status("Optimize Preview: deleted {}, unlinked {}".format(deleted, unlinked), 4000)
         return deleted

     def cancel_for_files(self, files):
         files = [f for f in (files or []) if getattr(f, "id", None)]
         if not files:
             return False

         canceled = 0
         for file_obj in files:
             if self.cancel_job(file_obj.id):
                 canceled += 1

         if canceled:
             self._show_status("Optimize Preview: canceled {} item(s)".format(canceled), 3000)
             return True
         return False

     def cancel_job(self, file_id):
         file_id = str(file_id or "")
         if not file_id:
             return False

         with self._lock:
             job = self._jobs.get(file_id)
             if not job:
                 return False
             status = str(job.get("status") or "")
             future = job.get("future")
             if status == "queued" and future and future.cancel():
                 self._finalize_job(file_id, "canceled")
                 return True
             if status == "queued":
                 job["cancel_requested"] = True
                 job["status"] = "canceling"
             elif status == "running":
                 job["cancel_requested"] = True
                 job["status"] = "canceling"
             elif status == "canceling":
                 return True
             else:
                 return False

         self._emit_job_change(file_id)
         return True

     def _rewrite_hidden_tracks_in_payload(self, parsed):
         try:
             from classes.app import get_app
             win = get_app().window
             if not win or not hasattr(win, "timeline"):
                 return False
             hidden_layers = set()
             for track in getattr(win.timeline, "track_list", []):
                 if isinstance(track.data, dict) and track.data.get("hidden"):
                     layer_num = track.data.get("number")
                     if layer_num is not None:
                         hidden_layers.add(layer_num)
                         hidden_layers.add(str(layer_num))
                         try:
                             hidden_layers.add(int(layer_num))
                         except Exception:
                             pass

             if not hidden_layers:
                 return False

             changed = False
             def _apply_clip_hidden(clip_dict):
                 if isinstance(clip_dict, dict):
                     layer = clip_dict.get("layer")
                     if layer in hidden_layers or str(layer) in hidden_layers:
                         clip_dict["display"] = 0
                         clip_dict["alpha"] = {
                             "Points": [
                                 {
                                     "co": {"X": 1.0, "Y": 0.0},
                                     "handle_left": {"X": 0.0, "Y": 0.0},
                                     "handle_right": {"X": 0.0, "Y": 0.0},
                                     "interpolation": 0
                                 }
                             ]
                         }
                         return True
                 return False

             if isinstance(parsed, dict):
                 clips = parsed.get("clips")
                 if isinstance(clips, list):
                     for clip in clips:
                         if _apply_clip_hidden(clip):
                             changed = True
             elif isinstance(parsed, list):
                 for action in parsed:
                     if isinstance(action, dict):
                         key = action.get("key")
                         values = action.get("values")
                         if isinstance(key, list) and len(key) >= 1 and key[0] == "clips":
                             if _apply_clip_hidden(values):
                                 changed = True
             return changed
         except Exception:
             return False

     def rewrite_json_for_preview(self, payload):
         """Return preview-bound JSON/object with proxy readers substituted when available and hidden tracks zeroed."""
         original_is_text = isinstance(payload, str)
         if original_is_text:
             try:
                 parsed = json.loads(payload)
             except Exception:
                 return payload
         else:
             parsed = copy.deepcopy(payload)

         hidden_changed = self._rewrite_hidden_tracks_in_payload(parsed)

         proxy_lookup, path_lookup = self._proxy_lookup_from_payload(parsed)
         if not proxy_lookup:
             proxy_lookup, path_lookup = self._proxy_lookup_from_project()

         changed = False
         if proxy_lookup:
             changed = self._rewrite_payload_in_place(parsed, proxy_lookup, path_lookup)

         if not changed and not hidden_changed:
             return payload
         if original_is_text:
             return json.dumps(parsed)
         return parsed

     def apply_runtime_updates_for_file(self, file_id):
         """Push runtime-only clip/effect updates to libopenshot for one file's proxy state."""
         return self.apply_runtime_updates_for_files([file_id])

     def apply_runtime_updates_for_files(self, file_ids):
         """Push one combined runtime-only clip/effect diff for one or more file proxy changes."""
         normalized_ids = {str(file_id or "") for file_id in (file_ids or []) if str(file_id or "")}
         if not normalized_ids:
             return False

         timeline_sync = getattr(self.win, "timeline_sync", None)
         timeline = getattr(timeline_sync, "timeline", None) if timeline_sync else None
         if timeline is None:
             return False

         actions = []
         for clip in Clip.filter():
             if any(self._payload_references_file(clip.data, file_id) for file_id in normalized_ids):
                 actions.append(
                     UpdateAction(
                         type="update",
                         key=["clips", {"id": clip.id}],
                         values=copy.deepcopy(clip.data),
                     )
                 )
         for effect in Transition.filter():
             if any(self._payload_references_file(effect.data, file_id) for file_id in normalized_ids):
                 actions.append(
                     UpdateAction(
                         type="update",
                         key=["effects", {"id": effect.id}],
                         values=copy.deepcopy(effect.data),
                     )
                 )

         if not actions:
             return False

         payload = [json.loads(action.json()) for action in actions]
         timeline.ApplyJsonDiff(self.rewrite_json_for_preview(json.dumps(payload)))
         try:
             timeline.ClearAllCache(True)
         except Exception:
             log.debug("Optimize Preview cache clear failed", exc_info=1)
         if getattr(self.win, "refreshFrameSignal", None):
             self.win.refreshFrameSignal.emit()
         return True

     def has_proxy_reader(self, file_obj):
         data = getattr(file_obj, "data", {}) if file_obj else {}
         proxy_reader = data.get("proxy_reader") if isinstance(data, dict) else None
         return isinstance(proxy_reader, dict) and bool(proxy_reader.get("path"))

     def has_missing_proxy(self, file_obj):
         data = getattr(file_obj, "data", {}) if file_obj else {}
         proxy_reader = data.get("proxy_reader") if isinstance(data, dict) else None
         if not isinstance(proxy_reader, dict) or not proxy_reader.get("path"):
             return False
         if proxy_reader.get("missing"):
             return True
         return not os.path.exists(str(proxy_reader.get("path")))

     def get_active_job_for_file(self, file_id):
         file_id = str(file_id or "")
         if not file_id:
             return None
         with self._lock:
             job = self._job_snapshot(self._jobs.get(file_id))
         if not job or job.get("status") not in self.ACTIVE_STATES:
             return None
         return job

     def get_file_badge(self, file_id):
         job = self.get_active_job_for_file(file_id)
         if not job:
             return None

         status = str(job.get("status") or "").strip().lower()
         progress = int(job.get("progress", 0))
         if status == "queued":
             label = "Queued"
         elif status == "running":
             label = "Creating {}%".format(progress)
         elif status == "canceling":
             label = "Canceling..."
         else:
             label = status.capitalize()
         return {
             "status": status,
             "progress": progress,
             "label": label,
             "job_id": str(job.get("id") or ""),
         }

     def get_proxy_state(self, file_obj):
         file_id = str(getattr(file_obj, "id", "") or "")
         active_job = self.get_active_job_for_file(file_id)
         if active_job:
             return str(active_job.get("status") or "queued")
         if self.has_proxy_reader(file_obj):
             return "missing" if self.has_missing_proxy(file_obj) else "ready"
         return "none"

     def _proxy_root(self):
         app = get_app()
         project = getattr(app, "project", None) if app else None
         current_filepath = getattr(project, "current_filepath", None) if project else None
         if current_filepath:
             current_abs = os.path.abspath(str(current_filepath))
             backup_abs = os.path.abspath(info.BACKUP_FILE)
             recovery_abs = os.path.abspath(info.RECOVERY_PATH) + os.sep
             if current_abs == backup_abs or current_abs.startswith(recovery_abs):
                 return info.PROXY_PATH
             return os.path.join(get_assets_path(current_filepath), "optimized")
         return info.PROXY_PATH

     def _emit_proxy_result(self, file_id, future):
         error_text = ""
         proxy_reader = {}
         try:
             if future.cancelled():
                 raise _ProxyJobCanceled()
             proxy_reader = future.result()
         except _ProxyJobCanceled:
             error_text = "__canceled__"
         except Exception as ex:
             error_text = str(ex)
             log.warning("Optimized Preview generation failed for %s: %s", file_id, error_text, exc_info=1)
         self.proxy_generated.emit(str(file_id or ""), proxy_reader, error_text)

     @pyqtSlot(str, object, str)
     def _on_proxy_generated(self, file_id, proxy_reader, error_text):
         file_id = str(file_id or "")
         if error_text == "__canceled__":
             self._finalize_job(file_id, "canceled")
             return
         if error_text:
             self._finalize_job(file_id, "failed")
             self._show_status("Optimize Preview: {}".format(error_text), 5000)
             return
         self._save_proxy_reader(file_id, proxy_reader)
         self._finalize_job(file_id, "completed")
         self._show_status("Optimize Preview: ready", 3000)

     def _save_proxy_reader(self, file_id, proxy_reader, apply_runtime=True, emit_job_change=True):
         file_obj = File.get(id=file_id)
         if not file_obj:
             return
         file_obj.data["proxy_reader"] = copy.deepcopy(proxy_reader or {})
         file_obj.save()
         if apply_runtime:
             self.apply_runtime_updates_for_file(file_id)
         if emit_job_change:
             self._emit_job_change(file_id)

     def _reader_json_for_path(self, file_path, file_id):
         clip = openshot.Clip(str(file_path))
         try:
             clip.Open()
             proxy_reader = json.loads(clip.Reader().Json())
             proxy_reader["id"] = str(file_id or "")
             return proxy_reader
         finally:
             try:
                 clip.Close()
             except Exception:
                 pass

     def _build_proxy_reader(self, file_id, file_data):
         source_path = absolute_media_path(file_data.get("path"))
         if not source_path or not os.path.exists(source_path):
             raise RuntimeError("source file not found")
         if str(file_data.get("media_type", "")).lower() != "video":
             raise RuntimeError("only video files are supported in V1")

         self._mark_running(file_id)
         output_path = self._reserved_or_computed_proxy_output_path(file_id, file_data)
         try:
             max_width, max_height = self._max_optimize_bounds()
             optimize_timeline = self._create_optimize_timeline(max_width, max_height)
             clip = openshot.Clip(source_path)
             clip.ParentTimeline(optimize_timeline)
             clip.Open()
             try:
                 reader = clip.Reader()
                 self._configure_optimize_caches(clip, reader)
                 source_reader = json.loads(reader.Json())

                 width = int(source_reader.get("width", 0) or 0)
                 height = int(source_reader.get("height", 0) or 0)
                 if width <= 0 or height <= 0:
                     raise RuntimeError("invalid source dimensions")

                 target_width, target_height = self._scaled_dimensions(width, height, max_width, max_height)
                 fps = source_reader.get("fps", {"num": 30, "den": 1})
                 pixel_ratio = source_reader.get("pixel_ratio", {"num": 1, "den": 1})
                 writer = openshot.FFmpegWriter(output_path)
                 writer.SetVideoOptions(
                     True,
                     "libx264",
                     openshot.Fraction(int(fps.get("num", 30)), int(fps.get("den", 1))),
                     target_width,
                     target_height,
                     openshot.Fraction(int(pixel_ratio.get("num", 1)), int(pixel_ratio.get("den", 1))),
                     False,
                     False,
                     28,
                 )
                 writer.PrepareStreams()

                 if source_reader.get("has_audio"):
                     channel_layout = openshot.LAYOUT_STEREO if int(source_reader.get("channels", 2) or 2) > 1 else openshot.LAYOUT_MONO
                     writer.SetAudioOptions(
                         True,
                         "aac",
                         48000,
                         2 if channel_layout == openshot.LAYOUT_STEREO else 1,
                         channel_layout,
                         128000,
                     )
                     writer.PrepareStreams()

                 writer.Open()
                 try:
                     max_frame = int(source_reader.get("video_length", 0) or 0)
                     if max_frame <= 0:
                         raise RuntimeError("invalid source frame count")
                     prewarm_frames = self._thumbnail_prewarm_frames(
                         file_id,
                         max_frame,
                         fps,
                         thumbs_per_second=self._thumbnail_prewarm_rate(),
                     )
                     prewarm_index = 0
                     for frame_number in range(1, max_frame + 1):
                         self._raise_if_canceled(file_id)
                         frame = reader.GetFrame(frame_number)
                         writer.WriteFrame(frame)
                         while prewarm_index < len(prewarm_frames) and prewarm_frames[prewarm_index] < frame_number:
                             prewarm_index += 1
                         if prewarm_index < len(prewarm_frames) and prewarm_frames[prewarm_index] == frame_number:
                             self._save_prewarmed_thumbnail(frame, file_id, frame_number, 0.0)
                             prewarm_index += 1
                         self._trim_optimize_caches(clip, reader, frame_number)
                         if frame_number == 1 or frame_number == max_frame or frame_number % max(1, min(12, max_frame // 40 or 1)) == 0:
                             self._update_progress(file_id, int((float(frame_number) / float(max_frame)) * 100.0))
                 finally:
                     writer.Close()
                     self._clear_cache_object(getattr(reader, "GetCache", lambda: None)())
                     self._clear_cache_object(getattr(clip, "GetCache", lambda: None)())
             finally:
                 clip.Close()
                 clip.ParentTimeline(None)
         except Exception:
             try:
                 if os.path.exists(output_path):
                     os.remove(output_path)
             except Exception:
                 pass
             raise

         return self._reader_json_for_path(output_path, file_id)

     def _proxy_lookup_from_payload(self, payload):
         if isinstance(payload, dict):
             files = payload.get("files")
             if isinstance(files, list):
                 return self._proxy_lookup_from_files(files)
         return {}, {}

     def _proxy_lookup_from_project(self):
         app = get_app()
         project = getattr(app, "project", None) if app else None
         files = project.get("files") if project else None
         if not isinstance(files, list):
             return {}, {}
         return self._proxy_lookup_from_files(files)

     def _proxy_lookup_from_files(self, files):
         proxy_lookup = {}
         path_lookup = {}
         for file_data in files or []:
             if not isinstance(file_data, dict):
                 continue
             file_id = str(file_data.get("id") or "")
             file_path = file_data.get("path")
             if file_id and file_path:
                 path_lookup[comparable_media_path(file_path)] = file_id
             proxy_reader = file_data.get("proxy_reader")
             if not isinstance(proxy_reader, dict) or not proxy_reader.get("path") or not file_id:
                 continue
             if not os.path.exists(str(proxy_reader.get("path"))):
                 continue
             proxy_data = copy.deepcopy(proxy_reader)
             proxy_data["id"] = file_id
             proxy_lookup[file_id] = proxy_data
         return proxy_lookup, path_lookup

     def _rewrite_payload_in_place(self, payload, proxy_lookup, path_lookup):
         changed = False
         if isinstance(payload, dict):
             for key, value in list(payload.items()):
                 if key in ("reader", "mask_reader") and isinstance(value, dict):
                     replacement = self._proxy_replacement_for_reader(value, proxy_lookup, path_lookup)
                     if replacement is not None and replacement != value:
                         payload[key] = copy.deepcopy(replacement)
                         changed = True
                 else:
                     changed = self._rewrite_payload_in_place(value, proxy_lookup, path_lookup) or changed
         elif isinstance(payload, list):
             for item in payload:
                 changed = self._rewrite_payload_in_place(item, proxy_lookup, path_lookup) or changed
         return changed

     def _proxy_replacement_for_reader(self, reader_data, proxy_lookup, path_lookup):
         reader_id = str(reader_data.get("id") or "")
         if reader_id and reader_id in proxy_lookup:
             return proxy_lookup[reader_id]

         reader_path = reader_data.get("path")
         if reader_path:
             file_id = path_lookup.get(comparable_media_path(reader_path))
             if file_id and file_id in proxy_lookup:
                 return proxy_lookup[file_id]
         return None

     def _payload_references_file(self, payload, file_id):
         file_obj = File.get(id=file_id)
         if not file_obj:
             return False
         target_path = comparable_media_path((file_obj.data or {}).get("path"))
         return self._payload_contains_file_reference(payload, str(file_id), target_path)

     def _payload_contains_file_reference(self, payload, file_id, target_path):
         if isinstance(payload, dict):
             for key, value in payload.items():
                 if key in ("reader", "mask_reader") and isinstance(value, dict):
                     if str(value.get("id") or "") == file_id:
                         return True
                     reader_path = value.get("path")
                     if reader_path and comparable_media_path(reader_path) == target_path:
                         return True
                 if self._payload_contains_file_reference(value, file_id, target_path):
                     return True
         elif isinstance(payload, list):
             for item in payload:
                 if self._payload_contains_file_reference(item, file_id, target_path):
                     return True
         return False

     def _show_status(self, text, timeout=5000):
         status_bar = getattr(self.win, "statusBar", None)
         if status_bar and hasattr(status_bar, "showMessage"):
             status_bar.showMessage(str(text), int(timeout))

     def _index_existing_optimized_files(self, folder_path):
         basename_index = {}
         stem_index = {}
         normalized_index = {}
         path_index = {}
         for root, _, files in os.walk(str(folder_path or "")):
             for name in files:
                 ext = os.path.splitext(name)[1].lower()
                 if ext not in self.MATCHABLE_VIDEO_EXTENSIONS:
                     continue
                 full_path = os.path.join(root, name)
                 basename_index.setdefault(name.lower(), []).append(full_path)
                 stem = os.path.splitext(name)[0].lower()
                 stem_index.setdefault(stem, []).append(full_path)
                 normalized_index.setdefault(self._normalized_proxy_name_key(stem), []).append(full_path)
                 path_index[comparable_media_path(full_path)] = full_path
         return {
             "basename": basename_index,
             "stem": stem_index,
             "normalized": normalized_index,
             "path": path_index,
         }

     def _match_existing_optimized_path(self, file_obj, folder_path, folder_index):
         data = getattr(file_obj, "data", {}) if file_obj else {}
         source_path = absolute_media_path(data.get("path"))
         file_id = str(getattr(file_obj, "id", "") or data.get("id") or "")
         basename = os.path.basename(source_path or "")
         basename_lower = basename.lower()
         source_stem = os.path.splitext(basename_lower)[0]
         source_norm = comparable_media_path(source_path)

         if file_id:
             id_matches = folder_index.get("stem", {}).get(file_id.lower(), [])
             if id_matches:
                 return id_matches[0]

         if basename_lower:
             basename_matches = folder_index.get("basename", {}).get(basename_lower, [])
             if basename_matches:
                 return basename_matches[0]

         if source_stem:
             stem_matches = folder_index.get("stem", {}).get(source_stem, [])
             if stem_matches:
                 return stem_matches[0]

         source_variants = self._source_proxy_name_candidates(source_stem)
         candidate_scores = {}
         for variant in source_variants:
             for match_path in folder_index.get("stem", {}).get(variant, []):
                 candidate_scores[match_path] = max(candidate_scores.get(match_path, 0), 90)

         normalized_key = self._normalized_proxy_name_key(source_stem)
         if normalized_key:
             for match_path in folder_index.get("normalized", {}).get(normalized_key, []):
                 candidate_scores[match_path] = max(candidate_scores.get(match_path, 0), 80)

         source_prefixes = self._source_stem_file_id_prefix_candidates(source_stem, file_id)
         for candidate_stem, candidate_paths in folder_index.get("stem", {}).items():
             if source_prefixes and any(candidate_stem.startswith(prefix) for prefix in source_prefixes):
                 for match_path in candidate_paths:
                     candidate_scores[match_path] = max(candidate_scores.get(match_path, 0), 75)

         for candidate_path in folder_index.get("path", {}).values():
             if source_norm and comparable_media_path(candidate_path).endswith(source_norm):
                 candidate_scores[candidate_path] = max(candidate_scores.get(candidate_path, 0), 70)

         if candidate_scores:
             ranked_paths = sorted(
                 candidate_scores.items(),
                 key=lambda item: (
                     -item[1],
                     abs(len(os.path.splitext(os.path.basename(item[0]))[0]) - len(source_stem)),
                     os.path.basename(item[0]).lower(),
                 ),
             )
             return ranked_paths[0][0]

         expected_name = self._preferred_proxy_filename(file_id, data, folder_path, existing_names=set())
         return os.path.join(str(folder_path or ""), expected_name)

     def _missing_proxy_reader(self, file_obj, folder_path):
         data = getattr(file_obj, "data", {}) if file_obj else {}
         file_id = str(getattr(file_obj, "id", "") or data.get("id") or "")
         source_path = absolute_media_path(data.get("path"))
         basename = os.path.basename(source_path or "")
         expected_path = self._match_existing_optimized_path(file_obj, folder_path, {"basename": {}, "stem": {}, "path": {}})
         return {
             "id": file_id,
             "path": expected_path,
             "missing": True,
             "name": basename,
         }

     def _proxy_output_path(self, file_id, file_data):
         proxy_root = self._proxy_root()
         os.makedirs(proxy_root, exist_ok=True)
         filename = self._preferred_proxy_filename(file_id, file_data, proxy_root)
         return os.path.join(proxy_root, filename)

     def _existing_proxy_output_path(self, file_id, file_data):
         proxy_root = self._proxy_root()
         default_filename = self._preferred_proxy_filename(file_id, file_data, proxy_root, existing_names=set())
         default_path = os.path.join(proxy_root, default_filename)
         source_stem = os.path.splitext(os.path.basename(absolute_media_path((file_data or {}).get("path")) or ""))[0]
         specific_path = os.path.join(proxy_root, "{}_{}.mp4".format(self._proxy_filename_stem(source_stem), str(file_id or "")))

         if os.path.exists(specific_path):
             return specific_path
         if os.path.exists(default_path):
             return default_path
         return None

     def _reserve_proxy_output_path(self, file_id, file_data):
         proxy_root = self._proxy_root()
         os.makedirs(proxy_root, exist_ok=True)
         try:
             existing_names = set(os.listdir(proxy_root))
         except Exception:
             existing_names = set()
         with self._lock:
             for job in self._jobs.values():
                 output_path = job.get("output_path")
                 if output_path:
                     existing_names.add(os.path.basename(str(output_path)))
         filename = self._preferred_proxy_filename(file_id, file_data, proxy_root, existing_names=existing_names)
         return os.path.join(proxy_root, filename)

     def _reserved_or_computed_proxy_output_path(self, file_id, file_data):
         with self._lock:
             job = self._jobs.get(str(file_id or ""))
             reserved_path = job.get("output_path") if isinstance(job, dict) else None
         return reserved_path or self._proxy_output_path(file_id, file_data)

     def _preferred_proxy_filename(self, file_id, file_data, proxy_root, existing_names=None):
         file_id = str(file_id or "")
         data = file_data or {}
         source_path = absolute_media_path(data.get("path"))
         source_stem = os.path.splitext(os.path.basename(source_path or ""))[0]
         base_stem = self._proxy_filename_stem(source_stem)
         default_name = "{}.mp4".format(base_stem)

         if existing_names is None:
             try:
                 existing_names = set(os.listdir(proxy_root))
             except Exception:
                 existing_names = set()
         existing_names_lower = {str(name).lower() for name in existing_names}

         if default_name.lower() not in existing_names_lower:
             return default_name
         return "{}_{}.mp4".format(base_stem, file_id)

     @staticmethod
     def _proxy_filename_stem(source_stem):
         source_stem = str(source_stem or "").strip()
         if not source_stem:
             return "optimized_proxy"
         return "{}_proxy".format(source_stem)


     @staticmethod
     def _source_stem_file_id_prefix_candidates(source_stem, file_id):
         source_stem = str(source_stem or "").strip().lower()
         file_id = str(file_id or "").strip().lower()
         if not source_stem or not file_id:
             return []
         separators = ("_", "-", ".")
         prefixes = []
         for separator in separators:
             prefixes.append("{}{}{}".format(source_stem, separator, file_id))
             prefixes.append("{}{}proxy{}{}".format(source_stem, separator, separator, file_id))
             prefixes.append("{}{}preview{}{}".format(source_stem, separator, separator, file_id))
             prefixes.append("{}{}optimized{}{}".format(source_stem, separator, separator, file_id))
             prefixes.append("{}{}lowres{}{}".format(source_stem, separator, separator, file_id))
         return prefixes

     @classmethod
     def _normalized_proxy_name_key(cls, stem):
         normalized = str(stem or "").strip().lower()
         if not normalized:
             return ""
         normalized = re.sub(r"[\s.-]+", "_", normalized)
         normalized = re.sub(r"_+", "_", normalized).strip("_")
         previous = None
         while normalized and normalized != previous:
             previous = normalized
             normalized = cls._PROXY_PREFIX_RE.sub("", normalized).strip("._- ")
             normalized = cls._PROXY_SUFFIX_RE.sub("", normalized).strip("._- ")
             normalized = cls._RESOLUTION_SUFFIX_RE.sub("", normalized).strip("._- ")
             if cls._CAMERA_PROXY_SUFFIX_RE.search(normalized):
                 trimmed = cls._CAMERA_PROXY_SUFFIX_RE.sub("", normalized).strip("._- ")
                 if trimmed:
                     normalized = trimmed
         return normalized

     @classmethod
     def _source_proxy_name_candidates(cls, source_stem):
         source_stem = str(source_stem or "").strip().lower()
         if not source_stem:
             return []

         candidates = {
             source_stem,
             "{}_proxy".format(source_stem),
             "{}-proxy".format(source_stem),
             "{}_optimized".format(source_stem),
             "{}-optimized".format(source_stem),
             "{}_preview".format(source_stem),
             "{}-preview".format(source_stem),
             "{}_lowres".format(source_stem),
             "{}-lowres".format(source_stem),
             "{}_p".format(source_stem),
             "{}-p".format(source_stem),
             "proxy_{}".format(source_stem),
             "proxy-{}".format(source_stem),
             "optimized_{}".format(source_stem),
             "optimized-{}".format(source_stem),
             "preview_{}".format(source_stem),
             "preview-{}".format(source_stem),
         }
         for size_label in ("360p", "540p", "720p", "1080p", "1440p", "2160p", "4k"):
             candidates.add("{}_{}".format(source_stem, size_label))
             candidates.add("{}_proxy_{}".format(source_stem, size_label))
             candidates.add("{}_{}_proxy".format(source_stem, size_label))
         return sorted(candidates)

     def _thumbnail_prewarm_frames(self, file_id, max_frame, fps, thumbs_per_second=None):
         max_frame = max(1, int(max_frame or 1))
         fps_num = float((fps or {}).get("num", 0.0) or 0.0)
         fps_den = float((fps or {}).get("den", 1.0) or 1.0)
         fps_value = (fps_num / fps_den) if fps_num > 0.0 and fps_den > 0.0 else 0.0
         if fps_value <= 0.0:
             return [1]

         if thumbs_per_second is None:
             thumbs_per_second = self._thumbnail_prewarm_rate()
         thumbs_per_second = max(1, int(thumbs_per_second))
         step = max(1, int(round(fps_value / float(thumbs_per_second))))
         frames = []
         seen = set()
         for frame_number in range(1, max_frame + 1, step):
             rounded = min(max_frame, RoundFrameToThumbnailGrid(frame_number, fps_value))
             if rounded not in seen:
                 seen.add(rounded)
                 frames.append(rounded)
         if max_frame not in seen:
             frames.append(max_frame)
         if 1 not in seen:
             frames.insert(0, 1)
         return sorted(set(frames))

     def _save_prewarmed_thumbnail(self, frame, file_id, frame_number, rotate):
         thumb_path = ThumbnailPathForFrame(file_id, frame_number)
         if os.path.exists(thumb_path):
             return
         try:
             mask_path = os.path.join(info.IMAGES_PATH, "mask.png")
             GenerateThumbnailFromFrame(frame, thumb_path, 98, 64, mask_path, "", rotate=rotate)
         except Exception:
             log.debug("Optimize Preview thumbnail prewarm failed file=%s frame=%s", file_id, frame_number, exc_info=1)

     def _configure_optimize_caches(self, clip, reader):
         self._configure_cache_object(getattr(clip, "GetCache", lambda: None)())
         self._configure_cache_object(getattr(reader, "GetCache", lambda: None)())

     def _trim_optimize_caches(self, clip, reader, frame_number):
         if int(frame_number or 0) % int(self.OPTIMIZE_CACHE_CLEAR_INTERVAL) != 0:
             return
         self._clear_cache_object(getattr(reader, "GetCache", lambda: None)())
         self._clear_cache_object(getattr(clip, "GetCache", lambda: None)())

     def _configure_cache_object(self, cache_object):
         if not cache_object:
             return
         try:
             cache_object.SetMaxBytes(int(self.OPTIMIZE_CACHE_MAX_BYTES))
         except Exception:
             log.debug("Optimize Preview cache max-bytes update failed", exc_info=1)
         self._clear_cache_object(cache_object)

     @staticmethod
     def _clear_cache_object(cache_object):
         if not cache_object:
             return
         try:
             cache_object.Clear()
         except Exception:
             log.debug("Optimize Preview cache clear failed", exc_info=1)

     def _create_optimize_timeline(self, width, height):
         width = max(2, int(width or 2))
         height = max(2, int(height or 2))
         timeline = openshot.Timeline(
             width,
             height,
             openshot.Fraction(30, 1),
             48000,
             2,
             openshot.LAYOUT_STEREO,
         )
         timeline.preview_width = width
         timeline.preview_height = height
         return timeline

     def _ensure_executor(self):
         worker_count = self._optimize_worker_count()
         current_executor = getattr(self, "_executor", None)
         current_count = getattr(current_executor, "_max_workers", None)
         if current_executor and current_count == worker_count:
             return
         with self._lock:
             if self._jobs:
                 return
             old_executor = self._executor
             self._executor = ThreadPoolExecutor(
                 max_workers=worker_count,
                 thread_name_prefix="optimized-preview",
             )
         if old_executor:
             self._shutdown_executor(old_executor)

     @staticmethod
     def _shutdown_executor(executor):
         if not executor:
             return
         try:
             executor.shutdown(wait=False, cancel_futures=True)
         except TypeError:
             executor.shutdown(wait=False)

     def _optimize_worker_count(self):
         value = self._setting_value("optimize-preview-jobs", 1)
         try:
             return max(1, min(8, int(value)))
         except (TypeError, ValueError):
             return 1

     def _thumbnail_prewarm_rate(self):
         value = self._setting_value("optimize-preview-thumbnails", 4)
         try:
             return max(1, min(12, int(value)))
         except (TypeError, ValueError):
             return 4

     def _max_optimize_bounds(self):
         raw_value = str(self._setting_value("optimize-preview-max-size", "1280x720") or "1280x720").lower()
         try:
             width_text, height_text = raw_value.split("x", 1)
             width = max(2, int(width_text))
             height = max(2, int(height_text))
             return width, height
         except (AttributeError, TypeError, ValueError):
             return 1280, 720

     @staticmethod
     def _setting_value(name, default):
         app = get_app()
         settings = app.get_settings() if app else None
         if not settings:
             return default
         try:
             value = settings.get(name)
         except Exception:
             return default
         return default if value is None else value

     def _mark_running(self, file_id):
         with self._lock:
             job = self._jobs.get(str(file_id or ""))
             if not job:
                 return
             if job.get("cancel_requested"):
                 job["status"] = "canceling"
             else:
                 job["status"] = "running"
             job["progress"] = max(1, int(job.get("progress", 0)))
         self._emit_job_change(file_id)

     def _update_progress(self, file_id, progress):
         with self._lock:
             job = self._jobs.get(str(file_id or ""))
             if not job:
                 return
             if job.get("status") not in self.ACTIVE_STATES:
                 return
             job["progress"] = max(0, min(100, int(progress)))
         self._emit_job_change(file_id)

     def _raise_if_canceled(self, file_id):
         with self._lock:
             job = self._jobs.get(str(file_id or ""))
             if job and job.get("cancel_requested"):
                 raise _ProxyJobCanceled()

     def _finalize_job(self, file_id, status):
         file_id = str(file_id or "")
         with self._lock:
             job = self._jobs.pop(file_id, None)
         if status == "completed":
             self.job_finished.emit(file_id, status)
         elif job is not None:
             self.job_finished.emit(file_id, status)
         self._emit_job_change(file_id)

     def _emit_job_change(self, file_id):
         file_id = str(file_id or "")
         if not file_id:
             return
         job = self.get_active_job_for_file(file_id)
         if job:
             self.job_updated.emit(file_id, str(job.get("status") or ""), int(job.get("progress", 0)))
         self.file_job_changed.emit(file_id)
         self.queue_changed.emit()

     @staticmethod
     def _job_snapshot(job):
         if not isinstance(job, dict):
             return None
         return {
             "id": str(job.get("id") or ""),
             "status": str(job.get("status") or ""),
             "progress": int(job.get("progress", 0)),
             "cancel_requested": bool(job.get("cancel_requested")),
         }

     @staticmethod
     def _scaled_dimensions(width, height, max_width=1280, max_height=720):
         if width <= 0 or height <= 0:
             return (1280, 720)
         scale = min(float(max_width) / float(width), float(max_height) / float(height), 1.0)
         scaled_w = max(2, int(round(width * scale)))
         scaled_h = max(2, int(round(height * scale)))
         if scaled_w % 2:
             scaled_w -= 1
         if scaled_h % 2:
             scaled_h -= 1
         return (max(2, scaled_w), max(2, scaled_h))


class _ProxyJobCanceled(RuntimeError):
     """Raised when a queued/running proxy job is canceled."""
