"""
 @file
 @brief This file contains unit tests for optimized-preview proxy rewriting
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

import json
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QObject
from qt_api import QApplication

from classes.project_data import ProjectDataStore
from classes.proxy_service import ProxyService, dialog_preview_reader_data
from classes.updates import UpdateManager
from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app


class DummySettings:
     def __init__(self):
         self.values = {
             "default-profile": "HD 720p 30 fps",
             "default-samplerate": 48000,
             "default-channels": 2,
         }

     def get(self, key):
         return self.values.get(key)


class DummyApp(QApplication):
     def __init__(self):
         super().__init__([])
         self.settings = DummySettings()
         self.project = None
         self.updates = None
         self.window = None

     def get_settings(self):
         return self.settings

     def _tr(self, text):
         return text


def ensure_app_state(app):
     return ensure_qt_app_state(
         app,
         DummySettings,
         project_factory=ProjectDataStore,
         updates_factory=UpdateManager,
         extra_attrs={"window": None},
     )


class DummySignal:
     def __init__(self):
         self.calls = 0

     def emit(self, *args):
         self.calls += 1


class DummyTimeline:
     def __init__(self):
         self.payloads = []
         self.cache_clears = []

     def ApplyJsonDiff(self, payload):
         self.payloads.append(payload)

     def ClearAllCache(self, clear_images):
         self.cache_clears.append(bool(clear_images))


class DummyWindow(QObject):
     def __init__(self):
         super().__init__()
         self.timeline_sync = types.SimpleNamespace(timeline=DummyTimeline())
         self.refreshFrameSignal = DummySignal()
         self.status_messages = []
         self.statusBar = types.SimpleNamespace(showMessage=lambda text, ms: self.status_messages.append((text, ms)))


class ProxyServiceTests(unittest.TestCase):
     @classmethod
     def setUpClass(cls):
         app, cls._owns_app = get_or_create_app(DummyApp)
         cls.app = ensure_app_state(app)

     @classmethod
     def tearDownClass(cls):
         if getattr(cls, "_owns_app", False) and cls.app:
             cls.app.quit()

     def setUp(self):
         ensure_app_state(self.app)
         self.win = DummyWindow()
         self.app.window = self.win
         self.service = ProxyService(self.win)

     def tearDown(self):
         self.service.shutdown()
         ensure_app_state(self.app)

     def test_dialog_preview_reader_data_prefers_valid_proxy_reader(self):
         file_obj = types.SimpleNamespace(
             id="F1",
             data={
                 "id": "F1",
                 "path": "/media/source.mp4",
                 "proxy_reader": {"path": "/optimized/F1.mp4", "width": 640},
             },
         )

         with patch("classes.proxy_service.absolute_media_path", side_effect=lambda path: path), \
              patch("classes.proxy_service.os.path.exists", side_effect=lambda path: path == "/optimized/F1.mp4"):
             reader_data = dialog_preview_reader_data(file_obj)

         self.assertEqual(reader_data["path"], "/optimized/F1.mp4")
         self.assertEqual(reader_data["width"], 640)
         self.assertEqual(reader_data["id"], "F1")

     def test_dialog_preview_reader_data_falls_back_when_proxy_missing(self):
         file_obj = types.SimpleNamespace(
             id="F1",
             data={
                 "id": "F1",
                 "path": "/media/source.mp4",
                 "width": 1920,
                 "proxy_reader": {"path": "/optimized/F1.mp4", "width": 640},
             },
         )

         with patch("classes.proxy_service.absolute_media_path", side_effect=lambda path: path), \
              patch("classes.proxy_service.os.path.exists", return_value=False):
             reader_data = dialog_preview_reader_data(file_obj)

         self.assertEqual(reader_data["path"], "/media/source.mp4")
         self.assertEqual(reader_data["width"], 1920)
         self.assertEqual(reader_data["id"], "F1")

     def test_dialog_preview_reader_data_ignores_missing_proxy_marker_even_if_file_exists(self):
         file_obj = types.SimpleNamespace(
             id="F1",
             data={
                 "id": "F1",
                 "path": "/media/source.mp4",
                 "width": 1920,
                 "proxy_reader": {"path": "/optimized/F1.mp4", "width": 640, "missing": True},
             },
         )

         with patch("classes.proxy_service.absolute_media_path", side_effect=lambda path: path), \
              patch("classes.proxy_service.os.path.exists", return_value=True):
             reader_data = dialog_preview_reader_data(file_obj)

         self.assertEqual(reader_data["path"], "/media/source.mp4")
         self.assertEqual(reader_data["width"], 1920)
         self.assertEqual(reader_data["id"], "F1")

     def test_rewrite_json_for_preview_replaces_clip_and_effect_readers_only(self):
         payload = {
             "files": [
                 {
                     "id": "F1",
                     "path": "/media/source.mp4",
                     "proxy_reader": {
                         "id": "F1",
                         "path": "/cache/F1.mp4",
                         "width": 1280,
                     },
                 }
             ],
             "clips": [
                 {
                     "id": "C1",
                     "file_id": "F1",
                     "reader": {
                         "id": "F1",
                         "path": "/media/source.mp4",
                         "width": 3840,
                     },
                     "effects": [
                         {
                             "id": "CE1",
                             "mask_reader": {
                                 "id": "F1",
                                 "path": "/media/source.mp4",
                                 "width": 3840,
                             }
                         }
                     ],
                 }
             ],
         }

         with patch("classes.proxy_service.os.path.exists", return_value=True):
             rewritten = self.service.rewrite_json_for_preview(payload)

         self.assertEqual(rewritten["files"][0]["path"], "/media/source.mp4")
         self.assertEqual(rewritten["clips"][0]["reader"]["path"], "/cache/F1.mp4")
         self.assertEqual(rewritten["clips"][0]["effects"][0]["mask_reader"]["path"], "/cache/F1.mp4")

     def test_rewrite_json_for_preview_is_noop_without_proxy_readers(self):
         payload = json.dumps(
             {
                 "clips": [
                     {
                         "id": "C1",
                         "reader": {
                             "id": "F1",
                             "path": "/media/source.mp4",
                         },
                     }
                 ]
             }
         )

         rewritten = self.service.rewrite_json_for_preview(payload)

         self.assertEqual(rewritten, payload)

     def test_rewrite_json_for_preview_ignores_missing_proxy_reader(self):
         payload = {
             "files": [
                 {
                     "id": "F1",
                     "path": "/media/source.mp4",
                     "proxy_reader": {
                         "id": "F1",
                         "path": "/missing/F1.mp4",
                     },
                 }
             ],
             "clips": [
                 {
                     "id": "C1",
                     "reader": {
                         "id": "F1",
                         "path": "/media/source.mp4",
                     },
                 }
             ],
         }

         with patch("classes.proxy_service.os.path.exists", return_value=False):
             rewritten = self.service.rewrite_json_for_preview(payload)

         self.assertEqual(rewritten, payload)

     def test_apply_runtime_updates_for_file_targets_related_clips_and_effects(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/source.mp4"})
         clip_obj = types.SimpleNamespace(
             id="C1",
             data={
                 "id": "C1",
                 "file_id": "F1",
                 "reader": {"id": "F1", "path": "/media/source.mp4"},
             },
         )
         transition_obj = types.SimpleNamespace(
             id="T1",
             data={
                 "id": "T1",
                 "reader": {"id": "F1", "path": "/media/source.mp4"},
             },
         )

         with patch("classes.proxy_service.File.get", return_value=file_obj), \
              patch("classes.proxy_service.Clip.filter", return_value=[clip_obj]), \
              patch("classes.proxy_service.Transition.filter", return_value=[transition_obj]), \
              patch.object(self.service, "rewrite_json_for_preview", side_effect=lambda payload: payload):
             changed = self.service.apply_runtime_updates_for_file("F1")

         self.assertTrue(changed)
         self.assertEqual(len(self.win.timeline_sync.timeline.payloads), 1)
         payload = json.loads(self.win.timeline_sync.timeline.payloads[0])
         self.assertEqual(len(payload), 2)
         self.assertEqual(self.win.timeline_sync.timeline.cache_clears, [True])
         self.assertEqual(self.win.refreshFrameSignal.calls, 1)

     def test_apply_runtime_updates_for_files_batches_multiple_file_ids(self):
         clip_one = types.SimpleNamespace(
             id="C1",
             data={"id": "C1", "file_id": "F1", "reader": {"id": "F1", "path": "/media/a.mp4"}},
         )
         clip_two = types.SimpleNamespace(
             id="C2",
             data={"id": "C2", "file_id": "F2", "reader": {"id": "F2", "path": "/media/b.mp4"}},
         )

         with patch("classes.proxy_service.Clip.filter", return_value=[clip_one, clip_two]), \
              patch("classes.proxy_service.Transition.filter", return_value=[]), \
              patch.object(self.service, "_payload_references_file", side_effect=lambda payload, file_id: payload.get("file_id") == file_id), \
              patch.object(self.service, "rewrite_json_for_preview", side_effect=lambda payload: payload):
             changed = self.service.apply_runtime_updates_for_files(["F1", "F2"])

         self.assertTrue(changed)
         self.assertEqual(len(self.win.timeline_sync.timeline.payloads), 1)
         payload = json.loads(self.win.timeline_sync.timeline.payloads[0])
         self.assertEqual(len(payload), 2)
         self.assertEqual(self.win.timeline_sync.timeline.cache_clears, [True])
         self.assertEqual(self.win.refreshFrameSignal.calls, 1)

     def test_build_proxy_reader_opens_and_closes_source_clip(self):
         class DummyCache:
             def __init__(self):
                 self.max_bytes = []
                 self.clears = 0

             def SetMaxBytes(self, value):
                 self.max_bytes.append(int(value))

             def Clear(self):
                 self.clears += 1

         clip_cache = DummyCache()
         reader_cache = DummyCache()
         clip_reader = types.SimpleNamespace(
             Json=lambda: json.dumps(
                 {
                     "width": 1920,
                     "height": 1080,
                     "fps": {"num": 30, "den": 1},
                     "pixel_ratio": {"num": 1, "den": 1},
                     "video_length": 3,
                     "has_audio": True,
                     "channels": 2,
                 }
             ),
             GetFrame="frame-{}".format,
             GetCache=lambda: reader_cache,
         )
         clip_obj = types.SimpleNamespace(
             opened=False,
             closed=False,
             parent_timeline_calls=[],
             Open=lambda: setattr(clip_obj, "opened", True),
             Close=lambda: setattr(clip_obj, "closed", True),
             Reader=lambda: clip_reader,
             GetCache=lambda: clip_cache,
             ParentTimeline=lambda timeline: clip_obj.parent_timeline_calls.append(timeline),
         )
         created_timelines = []
         def fake_timeline(width, height, fps, sample_rate, channels, layout):
             timeline = types.SimpleNamespace(
                 width=width,
                 height=height,
                 fps=fps,
                 sample_rate=sample_rate,
                 channels=channels,
                 layout=layout,
                 preview_width=width,
                 preview_height=height,
             )
             created_timelines.append(timeline)
             return timeline
         writer_obj = types.SimpleNamespace(
             opened=False,
             closed=False,
             frames=[],
             video_options=[],
             audio_options=[],
             stream_options=[],
             SetVideoOptions=lambda *args: writer_obj.video_options.append(args),
             PrepareStreams=lambda: None,
             SetAudioOptions=lambda *args: writer_obj.audio_options.append(args),
             SetOption=lambda *args: writer_obj.stream_options.append(args),
             Open=lambda: setattr(writer_obj, "opened", True),
             Close=lambda: setattr(writer_obj, "closed", True),
             WriteFrame=lambda frame: writer_obj.frames.append(frame),
         )

         thumbnail_calls = []

         def fake_exists(path):
             return path == "/media/source.mp4"

         with patch("classes.proxy_service.absolute_media_path", return_value="/media/source.mp4"), \
              patch("classes.proxy_service.os.path.exists", side_effect=fake_exists), \
              patch("classes.proxy_service.os.listdir", return_value=[]), \
              patch("classes.proxy_service.os.makedirs"), \
              patch("classes.proxy_service.openshot.Clip", return_value=clip_obj), \
              patch("classes.proxy_service.openshot.Timeline", side_effect=fake_timeline), \
              patch("classes.proxy_service.openshot.FFmpegWriter", return_value=writer_obj), \
              patch("classes.proxy_service.openshot.Fraction", side_effect=lambda num, den: (num, den)), \
              patch("classes.proxy_service.GenerateThumbnailFromFrame", side_effect=lambda frame, path, width, height, mask, overlay, rotate=0.0: thumbnail_calls.append((frame, path, width, height, rotate))), \
              patch.object(self.service, "_proxy_root", return_value="/project/optimized"), \
              patch.object(self.service, "_reader_json_for_path", return_value={"id": "F1", "path": "/project/optimized/source_proxy.mov"}):
             result = self.service._build_proxy_reader("F1", {"path": "/media/source.mp4", "media_type": "video"})

         self.assertTrue(clip_obj.opened)
         self.assertTrue(clip_obj.closed)
         self.assertTrue(writer_obj.opened)
         self.assertTrue(writer_obj.closed)
         self.assertEqual(len(created_timelines), 1)
         self.assertEqual(created_timelines[0].preview_width, 1280)
         self.assertEqual(created_timelines[0].preview_height, 720)
         self.assertEqual(clip_obj.parent_timeline_calls[0], created_timelines[0])
         self.assertIsNone(clip_obj.parent_timeline_calls[-1])
         self.assertEqual(writer_obj.video_options[0][1], "mjpeg")
         self.assertEqual(writer_obj.audio_options[0][1], "pcm_s16le")
         self.assertEqual(writer_obj.audio_options[0][2], 48000)
         self.assertTrue(any(option[1:] == ("qscale", "1") for option in writer_obj.stream_options))
         self.assertEqual(writer_obj.frames, ["frame-1", "frame-2", "frame-3"])
         self.assertEqual([os.path.basename(call[1]) for call in thumbnail_calls], ["1.png", "3.png"])
         self.assertEqual([call[4] for call in thumbnail_calls], [0.0, 0.0])
         self.assertEqual(clip_cache.max_bytes, [self.service.OPTIMIZE_CACHE_MAX_BYTES])
         self.assertEqual(reader_cache.max_bytes, [self.service.OPTIMIZE_CACHE_MAX_BYTES])
         self.assertGreaterEqual(clip_cache.clears, 2)
         self.assertGreaterEqual(reader_cache.clears, 2)
         self.assertEqual(result["path"], "/project/optimized/source_proxy.mov")

     def test_thumbnail_prewarm_frames_uses_coarse_4fps_grid(self):
         with patch.object(self.service, "_thumbnail_prewarm_rate", return_value=4):
             frames = self.service._thumbnail_prewarm_frames(
                 "F1",
                 31,
                 {"num": 30, "den": 1},
             )

         self.assertEqual(frames, [1, 9, 17, 25, 31])

     def test_executor_defaults_to_single_worker(self):
         self.assertEqual(self.service._executor._max_workers, 1)

     def test_optimize_settings_override_workers_size_and_thumbnail_rate(self):
         self.app.settings.values["optimize-preview-jobs"] = 3
         self.app.settings.values["optimize-preview-max-size"] = "1920x1080"
         self.app.settings.values["optimize-preview-thumbnails"] = 5
         self.app.settings.values["optimize-preview-encoder"] = "dnxhr_lb"

         self.service._jobs.clear()
         self.service._ensure_executor()

         self.assertEqual(self.service._executor._max_workers, 3)
         self.assertEqual(self.service._max_optimize_bounds(), (1920, 1080))
         self.assertEqual(self.service._thumbnail_prewarm_rate(), 5)
         self.assertEqual(self.service._proxy_encoder_settings()["video_codec"], "dnxhd")

     def test_proxy_encoder_defaults_to_mjpeg(self):
         settings = self.service._proxy_encoder_settings()

         self.assertEqual(settings["video_codec"], "mjpeg")
         self.assertEqual(settings["video_options"]["pix_fmt"], "yuvj420p")

     def test_create_for_files_skips_already_optimized_files(self):
         ready_file = types.SimpleNamespace(
             id="F1",
             data={"id": "F1", "proxy_reader": {"path": "/optimized/F1.mp4"}},
         )
         new_file = types.SimpleNamespace(
             id="F2",
             data={"id": "F2", "path": "/media/source.mp4", "media_type": "video"},
         )
         submitted = []

         with patch.object(self.service, "has_missing_proxy", return_value=False), \
              patch.object(self.service, "_proxy_root", return_value="/project/optimized"), \
              patch("classes.proxy_service.os.makedirs"), \
              patch.object(self.service._executor, "submit", side_effect=lambda *args: submitted.append(args) or Mock(add_done_callback=lambda callback: None)):
             self.service.create_for_files([ready_file, new_file])

         self.assertEqual(len(submitted), 1)
         self.assertEqual(submitted[0][1], "F2")
         self.assertEqual(self.win.status_messages[-1][0], "Optimize Preview: creating 1 item(s), skipped 1")

     def test_create_for_files_links_existing_target_file_instead_of_rerendering(self):
         file_obj = types.SimpleNamespace(
             id="F1",
             data={"id": "F1", "path": "/media/source.mp4", "media_type": "video"},
         )
         submitted = []

         with patch.object(self.service, "has_missing_proxy", return_value=False), \
              patch.object(self.service, "_existing_proxy_output_path", return_value="/project/optimized/source_proxy.mov"), \
              patch.object(self.service, "_reader_json_for_path", return_value={"id": "F1", "path": "/project/optimized/source_proxy.mov"}), \
              patch.object(self.service, "_save_proxy_reader", return_value=None) as save_proxy_reader, \
              patch.object(self.service._executor, "submit", side_effect=lambda *args: submitted.append(args)):
             self.service.create_for_files([file_obj])

         save_proxy_reader.assert_called_once_with("F1", {"id": "F1", "path": "/project/optimized/source_proxy.mov"})
         self.assertEqual(submitted, [])
         self.assertEqual(self.win.status_messages[-1][0], "Optimize Preview: linked 1 item(s)")

     def test_create_for_files_removes_invalid_existing_target_and_rerenders(self):
         file_obj = types.SimpleNamespace(
             id="F1",
             data={"id": "F1", "path": "/media/source.mp4", "media_type": "video"},
         )
         submitted = []

         with patch.object(self.service, "has_missing_proxy", return_value=False), \
              patch.object(self.service, "_existing_proxy_output_path", return_value="/project/optimized/source_proxy.mov"), \
              patch.object(self.service, "_reader_json_for_path", side_effect=RuntimeError("invalid proxy")), \
              patch("classes.proxy_service.os.remove") as remove_file, \
              patch.object(self.service, "_reserve_proxy_output_path", return_value="/project/optimized/source_proxy.mov"), \
              patch.object(self.service._executor, "submit", side_effect=lambda *args: submitted.append(args) or Mock(add_done_callback=lambda callback: None)):
             self.service.create_for_files([file_obj])

         remove_file.assert_called_once_with("/project/optimized/source_proxy.mov")
         self.assertEqual(len(submitted), 1)
         self.assertEqual(submitted[0][1], "F1")

     def test_existing_proxy_output_path_reuses_default_name_when_file_exists(self):
         with patch.object(self.service, "_proxy_root", return_value="/project/optimized"), \
              patch("classes.proxy_service.os.path.exists", side_effect=lambda path: path == "/project/optimized/clip001_proxy.mov"):
             existing_path = self.service._existing_proxy_output_path("F2", {"path": "/media/clip001.mov"})

         self.assertEqual(existing_path, "/project/optimized/clip001_proxy.mov")

     def test_existing_proxy_output_path_reuses_legacy_mp4_proxy_when_present(self):
         with patch.object(self.service, "_proxy_root", return_value="/project/optimized"), \
              patch("classes.proxy_service.os.path.exists", side_effect=lambda path: path == "/project/optimized/clip001_proxy.mp4"):
             existing_path = self.service._existing_proxy_output_path("F2", {"path": "/media/clip001.mov"})

         self.assertEqual(existing_path, "/project/optimized/clip001_proxy.mp4")

     def test_get_proxy_state_returns_ready_and_missing(self):
         file_obj = types.SimpleNamespace(
             id="F1",
             data={"id": "F1", "proxy_reader": {"path": "/project/optimized/F1.mp4"}},
         )

         with patch("classes.proxy_service.os.path.exists", return_value=True):
             self.assertEqual(self.service.get_proxy_state(file_obj), "ready")

         with patch("classes.proxy_service.os.path.exists", return_value=False):
             self.assertEqual(self.service.get_proxy_state(file_obj), "missing")

         missing_marked = types.SimpleNamespace(
             id="F2",
             data={"id": "F2", "proxy_reader": {"path": "/project/optimized/F2.mp4", "missing": True}},
         )

         with patch("classes.proxy_service.os.path.exists", return_value=True):
             self.assertEqual(self.service.get_proxy_state(missing_marked), "missing")

     def test_use_existing_for_files_links_matches_and_marks_missing(self):
         file_one = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/source-a.mp4"})
         file_two = types.SimpleNamespace(id="F2", data={"id": "F2", "path": "/media/source-b.mp4"})
         saved = []

         with patch.object(self.service, "_proxy_root", return_value="/project_assets/optimized"), \
              patch("classes.proxy_service.QFileDialog.getExistingDirectory", return_value="/optimized") as choose_dir, \
              patch.object(self.service, "_index_existing_optimized_files", return_value={
                  "basename": {"source-a.mp4": ["/optimized/F1.mp4"]},
                  "stem": {"f1": ["/optimized/F1.mp4"]},
                  "path": {},
              }), \
              patch("classes.proxy_service.os.path.exists", side_effect=lambda path: path == "/optimized/F1.mp4"), \
              patch.object(self.service, "_reader_json_for_path", return_value={"id": "F1", "path": "/optimized/F1.mp4"}), \
              patch.object(self.service, "_save_proxy_reader", side_effect=lambda file_id, reader, **kwargs: saved.append((file_id, reader))), \
              patch.object(self.service, "apply_runtime_updates_for_files", return_value=True), \
              patch.object(self.service, "_emit_job_change", return_value=None):
             self.service.use_existing_for_files([file_one, file_two])

         self.assertEqual(choose_dir.call_args[0][2], "/project_assets/optimized")
         self.assertEqual(saved[0], ("F1", {"id": "F1", "path": "/optimized/F1.mp4"}))
         self.assertEqual(saved[1][0], "F2")
         self.assertTrue(saved[1][1]["missing"])
         self.assertEqual(saved[1][1]["path"], "/optimized/source-b_proxy.mov")

     def test_use_existing_for_files_skips_invalid_matches_without_crashing(self):
         file_one = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/source-a.mp4"})
         file_two = types.SimpleNamespace(id="F2", data={"id": "F2", "path": "/media/source-b.mp4"})
         saved = []

         def fake_reader(path, file_id):
             if path == "/optimized/F1.mp4":
                 raise RuntimeError("invalid proxy")
             return {"id": file_id, "path": path}

         with patch.object(self.service, "_proxy_root", return_value="/project_assets/optimized"), \
              patch("classes.proxy_service.QFileDialog.getExistingDirectory", return_value="/optimized"), \
              patch.object(self.service, "_index_existing_optimized_files", return_value={
                  "basename": {"source-a.mp4": ["/optimized/F1.mp4"], "source-b.mp4": ["/optimized/F2.mp4"]},
                  "stem": {"source-a": ["/optimized/F1.mp4"], "source-b": ["/optimized/F2.mp4"]},
                  "path": {},
              }), \
              patch("classes.proxy_service.os.path.exists", side_effect=lambda path: path in {"/optimized/F1.mp4", "/optimized/F2.mp4"}), \
              patch.object(self.service, "_reader_json_for_path", side_effect=fake_reader), \
              patch.object(self.service, "_save_proxy_reader", side_effect=lambda file_id, reader, **kwargs: saved.append((file_id, reader))), \
              patch.object(self.service, "apply_runtime_updates_for_files", return_value=True), \
              patch.object(self.service, "_emit_job_change", return_value=None):
             self.service.use_existing_for_files([file_one, file_two])

         self.assertEqual(saved, [("F2", {"id": "F2", "path": "/optimized/F2.mp4"})])
         self.assertEqual(self.win.status_messages[-1][0], "Optimize Preview: linked 1 item(s), missing 0, invalid 1")

     def test_match_existing_optimized_path_prefers_same_name_different_extension(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/clip001.mov"})
         folder_index = {
             "basename": {},
             "stem": {"clip001": ["/optimized/clip001.mkv"]},
             "normalized": {},
             "path": {},
         }

         match_path = self.service._match_existing_optimized_path(file_obj, "/optimized", folder_index)

         self.assertEqual(match_path, "/optimized/clip001.mkv")

     def test_match_existing_optimized_path_supports_proxy_suffix(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/clip001.mov"})
         folder_index = {
             "basename": {},
             "stem": {"clip001_proxy": ["/optimized/clip001_proxy.mp4"]},
             "normalized": {"clip001": ["/optimized/clip001_proxy.mp4"]},
             "path": {},
         }

         match_path = self.service._match_existing_optimized_path(file_obj, "/optimized", folder_index)

         self.assertEqual(match_path, "/optimized/clip001_proxy.mp4")

     def test_match_existing_optimized_path_does_not_match_unknown_suffix(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/clip001.mov"})
         folder_index = {
             "basename": {},
             "stem": {"clip001_reviewcopy": ["/optimized/clip001_reviewcopy.mp4"]},
             "normalized": {},
             "path": {},
         }

         match_path = self.service._match_existing_optimized_path(file_obj, "/optimized", folder_index)

         self.assertEqual(match_path, "/optimized/clip001_proxy.mp4")

     def test_match_existing_optimized_path_supports_source_name_with_file_id_suffix(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/clip001.mov"})
         folder_index = {
             "basename": {},
             "stem": {"clip001_proxy_f1": ["/optimized/clip001_proxy_F1.mp4"]},
             "normalized": {},
             "path": {},
         }

         match_path = self.service._match_existing_optimized_path(file_obj, "/optimized", folder_index)

         self.assertEqual(match_path, "/optimized/clip001_proxy_F1.mp4")

     def test_match_existing_optimized_path_supports_file_id_only_name(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "path": "/media/clip001.mov"})
         folder_index = {
             "basename": {},
             "stem": {"f1": ["/optimized/F1.mp4"]},
             "normalized": {},
             "path": {},
         }

         match_path = self.service._match_existing_optimized_path(file_obj, "/optimized", folder_index)

         self.assertEqual(match_path, "/optimized/F1.mp4")

     def test_preferred_proxy_filename_uses_source_name_without_collision(self):
         filename = self.service._preferred_proxy_filename(
             "F1",
             {"path": "/media/clip001.mov"},
             "/project/optimized",
             existing_names={"other_proxy.mp4"},
         )

         self.assertEqual(filename, "clip001_proxy.mov")

     def test_preferred_proxy_filename_appends_file_id_on_collision(self):
         filename = self.service._preferred_proxy_filename(
             "F1",
             {"path": "/media/clip001.mov"},
             "/project/optimized",
             existing_names={"clip001_proxy.mov"},
         )

         self.assertEqual(filename, "clip001_proxy_F1.mov")

     def test_reserve_proxy_output_path_avoids_collisions_with_already_reserved_jobs(self):
         self.service._jobs["F1"] = {
             "id": "F1",
             "status": "queued",
             "progress": 0,
             "cancel_requested": False,
             "output_path": "/project/optimized/clip001_proxy.mov",
         }

         with patch.object(self.service, "_proxy_root", return_value="/project/optimized"), \
              patch("classes.proxy_service.os.listdir", return_value=[]), \
              patch("classes.proxy_service.os.makedirs"):
             output_path = self.service._reserve_proxy_output_path("F2", {"path": "/media/clip001.mov"})

         self.assertEqual(output_path, "/project/optimized/clip001_proxy_F2.mov")

     def test_index_existing_optimized_files_limits_matches_to_common_video_extensions(self):
         def fake_walk(_):
             yield ("/optimized", [], ["clip001_proxy.mp4", "clip001_proxy.thm", "clip001_proxy.txt", "clip001_proxy.mxf"])

         with patch("classes.proxy_service.os.walk", side_effect=fake_walk):
             index = self.service._index_existing_optimized_files("/optimized")

         self.assertIn("clip001_proxy.mp4", index["basename"])
         self.assertIn("clip001_proxy.mxf", index["basename"])
         self.assertNotIn("clip001_proxy.thm", index["basename"])
         self.assertNotIn("clip001_proxy.txt", index["basename"])

     def test_delete_and_unlink_for_files_deletes_linked_proxy_and_unlinks_all(self):
         file_one = types.SimpleNamespace(id="F1", data={"id": "F1"})
         file_two = types.SimpleNamespace(id="F2", data={"id": "F2"})
         fresh_one = types.SimpleNamespace(
             id="F1",
             key=["files", {"id": "F1"}],
             data={"id": "F1", "proxy_reader": {"path": "/project/optimized/F1.mp4"}},
             save=Mock(),
         )
         refreshed_one = types.SimpleNamespace(
             id="F1",
             key=["files", {"id": "F1"}],
             data={"id": "F1", "proxy_reader": {"path": "/project/optimized/F1.mp4"}},
         )
         fresh_two = types.SimpleNamespace(
             id="F2",
             key=["files", {"id": "F2"}],
             data={"id": "F2", "proxy_reader": {"path": "/external/proxy/F2.mp4"}},
             save=Mock(),
         )
         refreshed_two = types.SimpleNamespace(
             id="F2",
             key=["files", {"id": "F2"}],
             data={"id": "F2", "proxy_reader": {"path": "/external/proxy/F2.mp4"}},
         )
         delete_calls = []
         removed_paths = []
         self.app.updates = types.SimpleNamespace(delete=delete_calls.append, transaction_id=None)

         with patch("classes.proxy_service.File.get", side_effect=[fresh_one, refreshed_one, fresh_two, refreshed_two]), \
              patch("classes.proxy_service.absolute_media_path", side_effect=lambda path: path), \
              patch("classes.proxy_service.os.path.exists", return_value=True), \
              patch("classes.proxy_service.os.remove", side_effect=removed_paths.append), \
              patch.object(self.service, "apply_runtime_updates_for_files", return_value=True), \
              patch.object(self.service, "_emit_job_change", return_value=None):
             deleted = self.service.delete_and_unlink_for_files([file_one, file_two])

         self.assertEqual(deleted, 2)
         self.assertEqual(removed_paths, ["/project/optimized/F1.mp4", "/external/proxy/F2.mp4"])
         fresh_one.save.assert_called_once_with()
         fresh_two.save.assert_called_once_with()
         self.assertEqual(delete_calls, [
             ["files", {"id": "F1"}, "proxy_reader"],
             ["files", {"id": "F2"}, "proxy_reader"],
         ])
         self.assertEqual(self.win.status_messages[-1][0], "Optimize Preview: deleted 2, unlinked 2")

     def test_remove_for_files_clears_proxy_reader_via_file_save_then_nested_delete_if_needed(self):
         file_obj = types.SimpleNamespace(id="F1", data={"id": "F1"})
         fresh_file = types.SimpleNamespace(
             id="F1",
             key=["files", {"id": "F1"}],
             data={"id": "F1", "proxy_reader": {"path": "/optimized/F1.mp4"}},
             save=Mock(),
         )
         refreshed_file = types.SimpleNamespace(
             id="F1",
             key=["files", {"id": "F1"}],
             data={"id": "F1", "proxy_reader": {"path": "/optimized/F1.mp4"}},
         )
         delete_calls = []
         self.app.updates = types.SimpleNamespace(delete=delete_calls.append, transaction_id=None)

         with patch("classes.proxy_service.File.get", side_effect=[fresh_file, refreshed_file]), \
              patch.object(self.service, "apply_runtime_updates_for_files", return_value=True), \
              patch.object(self.service, "_emit_job_change", return_value=None):
             self.service.remove_for_files([file_obj])

         fresh_file.save.assert_called_once_with()
         self.assertNotIn("proxy_reader", fresh_file.data)
         self.assertEqual(delete_calls, [["files", {"id": "F1"}, "proxy_reader"]])

     def test_cancel_job_finalizes_queued_future(self):
         future = Mock()
         future.cancel.return_value = True
         self.service._jobs["F1"] = {
             "id": "F1",
             "status": "queued",
             "progress": 0,
             "future": future,
             "cancel_requested": False,
         }

         canceled = self.service.cancel_job("F1")

         self.assertTrue(canceled)
         self.assertIsNone(self.service.get_active_job_for_file("F1"))
         self.assertEqual(self.service.get_file_badge("F1"), None)

     def test_cancel_job_marks_running_job_canceling(self):
         future = Mock()
         future.cancel.return_value = False
         self.service._jobs["F1"] = {
             "id": "F1",
             "status": "running",
             "progress": 37,
             "future": future,
             "cancel_requested": False,
         }

         canceled = self.service.cancel_job("F1")
         badge = self.service.get_file_badge("F1")

         self.assertTrue(canceled)
         self.assertTrue(self.service._jobs["F1"]["cancel_requested"])
         self.assertEqual(self.service._jobs["F1"]["status"], "canceling")
         self.assertEqual(badge["status"], "canceling")
         self.assertEqual(badge["progress"], 37)

     def test_get_active_job_for_file_ignores_unserializable_future_state(self):
         self.service._jobs["F1"] = {
             "id": "F1",
             "status": "queued",
             "progress": 12,
             "future": Mock(),
             "cancel_requested": False,
         }

         job = self.service.get_active_job_for_file("F1")

         self.assertEqual(job, {
             "id": "F1",
             "status": "queued",
             "progress": 12,
             "cancel_requested": False,
         })

     def test_proxy_root_ignores_backup_project_path(self):
         self.app.project = types.SimpleNamespace(current_filepath="/home/test/.openshot_qt/backup.osp")

         with patch("classes.proxy_service.info.BACKUP_FILE", "/home/test/.openshot_qt/backup.osp"), \
              patch("classes.proxy_service.info.RECOVERY_PATH", "/home/test/.openshot_qt/recovery"), \
              patch("classes.proxy_service.info.PROXY_PATH", "/home/test/.openshot_qt/optimized"):
             proxy_root = self.service._proxy_root()

         self.assertEqual(proxy_root, "/home/test/.openshot_qt/optimized")
