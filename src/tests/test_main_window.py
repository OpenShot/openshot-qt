"""
 @file
 @brief This file contains unit tests for selected main window flows
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

import importlib
import os
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QCoreApplication, Qt
from qt_api import QApplication

from classes import info
from classes.project_data import ProjectDataStore
from classes.updates import UpdateManager
from qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    actionType = types.SimpleNamespace(LOAD="load")

    def __init__(self):
        self.values = {
            "recent_projects": [],
            "history-limit": 20,
            "recovery-limit": 10,
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
        }
        self.default_paths = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def setDefaultPath(self, action, path):
        self.default_paths[action] = path


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()
        self.project = None
        self.updates = None
        self.window = None
        self.logger_libopenshot = None

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
        extra_attrs={"window": None, "logger_libopenshot": None},
    )


class SignalRecorder:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)
        cls._web_backend_patcher = patch.object(info, "WEB_BACKEND", "qwidget")
        cls._web_backend_patcher.start()
        metrics = types.ModuleType("classes.metrics")
        metrics.track_metric_session = lambda *args, **kwargs: None
        metrics.track_metric_screen = lambda *args, **kwargs: None
        sys.modules["classes.metrics"] = metrics
        sys.modules.pop("windows.views.timeline", None)
        sys.modules.pop("windows.main_window", None)
        cls.main_window_module = importlib.import_module("windows.main_window")

    @classmethod
    def tearDownClass(cls):
        cls._web_backend_patcher.stop()
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def setUp(self):
        ensure_app_state(self.app)
        self.app.settings = DummySettings()
        self.app.window = None

    def tearDown(self):
        ensure_app_state(self.app)

    def test_manage_recovery_files_keeps_daily_and_historical_limits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery_dir = os.path.join(tmpdir, "recovery")
            os.mkdir(recovery_dir)

            with patch.object(self.main_window_module.info, "RECOVERY_PATH", recovery_dir):
                # Freeze the module clock so the retention logic and fixture
                # timestamps use the same notion of "today".
                now = datetime(2026, 3, 21, 12, 0, 0)

                class FixedDateTime(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        if tz is not None:
                            return tz.fromutc(now.replace(tzinfo=tz))
                        return now

                files = [
                    ("100-newest-project.zip", now),
                    ("090-older-today-project.zip", now - timedelta(hours=1)),
                    ("080-yesterday-project.zip", now - timedelta(days=1)),
                    ("070-two-days-project.zip", now - timedelta(days=2)),
                ]
                for name, dt in files:
                    path = os.path.join(recovery_dir, name)
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write("x")
                    ts = dt.timestamp()
                    os.utime(path, (ts, ts))

                fake_window = types.SimpleNamespace()
                with patch.object(self.main_window_module, "datetime", FixedDateTime):
                    self.main_window_module.MainWindow.manage_recovery_files(fake_window, 1, 1, "project")

                remaining = sorted(os.listdir(recovery_dir))
                self.assertEqual(remaining, ["080-yesterday-project.zip", "100-newest-project.zip"])

    def test_save_project_emits_saved_signal_on_success(self):
        saved = SignalRecorder()
        failed = SignalRecorder()
        history_calls = []
        save_calls = []

        self.app.project = types.SimpleNamespace(save=save_calls.append)
        self.app.updates = types.SimpleNamespace(
            save_history=lambda project, limit: history_calls.append((project, limit))
        )
        self.app.settings.values["history-limit"] = 42

        fake_window = types.SimpleNamespace(
            lock=threading.Lock(),
            save_recovery=lambda path: save_calls.append(f"recovery:{path}"),
            ProjectSaved=saved,
            ProjectSaveFailed=failed,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "project.osp")
            self.main_window_module.MainWindow.save_project(fake_window, project_path)

            self.assertEqual(history_calls, [(self.app.project, 42)])
            self.assertEqual(save_calls, [f"recovery:{project_path}", project_path])
            self.assertEqual(saved.calls, [(project_path,)])
            self.assertEqual(failed.calls, [])

    def test_optimized_preview_actions_use_cached_menu_targets_when_selection_is_empty(self):
        proxy_calls = []
        file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"})
        fake_window = types.SimpleNamespace(
            selected_files=lambda: [],
            _optimized_preview_target_file_ids=["F1"],
            proxy_service=types.SimpleNamespace(
                remove_for_files=lambda files: proxy_calls.append(("remove", [getattr(f, "id", None) for f in files])),
                create_for_files=lambda files: proxy_calls.append(("create", [getattr(f, "id", None) for f in files])),
                use_existing_for_files=lambda files: proxy_calls.append(("locate", [getattr(f, "id", None) for f in files])),
                cancel_for_files=lambda files: proxy_calls.append(("cancel", [getattr(f, "id", None) for f in files])),
                delete_and_unlink_for_files=lambda files: proxy_calls.append(("delete", [getattr(f, "id", None) for f in files])),
            ),
        )
        fake_window._optimized_preview_files_for_action = lambda: self.main_window_module.MainWindow._optimized_preview_files_for_action(fake_window)

        with patch.object(self.main_window_module.File, "get", return_value=file_obj):
            files = self.main_window_module.MainWindow._optimized_preview_files_for_action(fake_window)
            self.assertEqual([f.id for f in files], ["F1"])

            self.main_window_module.MainWindow.actionOptimizedPreviewRemove_trigger(fake_window)
            self.main_window_module.MainWindow.actionOptimizedPreviewCreate_trigger(fake_window)
            self.main_window_module.MainWindow.actionOptimizedPreviewDeleteAndUnlink_trigger(fake_window)

        self.assertEqual(proxy_calls, [("remove", ["F1"]), ("create", ["F1"]), ("delete", ["F1"])])

    def test_optimized_preview_cancel_targets_current_file_only(self):
        proxy_calls = []
        file_obj = types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"})
        fake_window = types.SimpleNamespace(
            current_file_id=lambda: "F1",
            selected_files=lambda: [
                types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"}),
                types.SimpleNamespace(id="F2", data={"id": "F2", "media_type": "video"}),
                types.SimpleNamespace(id="F3", data={"id": "F3", "media_type": "video"}),
            ],
            _optimized_preview_target_file_ids=["F1", "F2", "F3"],
            proxy_service=types.SimpleNamespace(
                cancel_for_files=lambda files: proxy_calls.append(("cancel", [getattr(f, "id", None) for f in files])),
            ),
        )
        fake_window._optimized_preview_files_for_action = lambda: self.main_window_module.MainWindow._optimized_preview_files_for_action(fake_window)
        fake_window._optimized_preview_file_for_cancel_action = lambda: self.main_window_module.MainWindow._optimized_preview_file_for_cancel_action(fake_window)

        with patch.object(self.main_window_module.File, "get", return_value=file_obj):
            self.main_window_module.MainWindow.actionOptimizedPreviewCancel_trigger(fake_window)

        self.assertEqual(proxy_calls, [("cancel", ["F1"])])

    def test_open_project_missing_file_removes_recent_project_and_seeks_start(self):
        status_messages = []
        removed = []
        loaded_recent = []
        move_calls = []
        restore_cursor = []
        speed_calls = SignalRecorder()
        pause_calls = SignalRecorder()

        player = types.SimpleNamespace(Seek=lambda frame: move_calls.append(("seek", frame)))
        preview_thread = types.SimpleNamespace(player=player)
        video_preview = types.SimpleNamespace(
            clearTransformState=lambda: move_calls.append(("clear_transform",)),
            size=lambda: "preview-size",
        )

        fake_window = types.SimpleNamespace(
            SpeedSignal=speed_calls,
            PauseSignal=pause_calls,
            videoPreview=video_preview,
            clearSelections=lambda: move_calls.append(("clear_selections",)),
            statusBar=types.SimpleNamespace(showMessage=lambda text, ms: status_messages.append((text, ms))),
            remove_recent_project=removed.append,
            load_recent_menu=lambda: loaded_recent.append(True),
            movePlayhead=lambda frame: move_calls.append(("playhead", frame)),
            preview_thread=preview_thread,
            SetWindowTitle=lambda: None,
            refreshFilesSignal=SignalRecorder(),
            refreshFrameSignal=SignalRecorder(),
            MaxSizeChanged=SignalRecorder(),
            actionSave_trigger=lambda: None,
        )

        self.app.project = types.SimpleNamespace(needs_save=lambda: False)
        self.app.updates = types.SimpleNamespace(load_history=lambda project: None)
        self.app.window = fake_window
        self.app.setOverrideCursor = lambda cursor: None
        self.app.restoreOverrideCursor = lambda: restore_cursor.append(True)

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, "missing.osp")
            with patch.object(self.main_window_module.QCoreApplication, "processEvents", lambda: None):
                self.main_window_module.MainWindow.open_project(
                    fake_window,
                    missing_path,
                    clear_thumbnails=True,
                )

            self.assertEqual(removed, [missing_path])
            self.assertEqual(loaded_recent, [True])
            self.assertTrue(status_messages)
            self.assertIn("missing", status_messages[0][0].lower())
            self.assertIn(("seek", 1), move_calls)
            self.assertIn(("playhead", 1), move_calls)
            self.assertEqual(speed_calls.calls, [(0,)])
            self.assertEqual(pause_calls.calls, [()])
            self.assertEqual(restore_cursor, [True])

    def test_save_recovery_creates_zip_and_calls_retention(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "demo.osp")
            with open(project_path, "w", encoding="utf-8") as handle:
                handle.write("project-data")

            recovery_dir = os.path.join(tmpdir, "recovery")
            os.mkdir(recovery_dir)
            self.app.settings.values["recovery-limit"] = 10

            managed = []
            fake_window = types.SimpleNamespace(
                manage_recovery_files=lambda daily, historical, name: managed.append((daily, historical, name))
            )

            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(self.main_window_module.info, "RECOVERY_PATH", recovery_dir)
                )
                stack.enter_context(
                    patch.object(self.main_window_module, "time", lambda: 1234567890)
                )
                self.main_window_module.MainWindow.save_recovery(fake_window, project_path)

            zip_path = os.path.join(recovery_dir, "1234567890-demo.zip")
            self.assertTrue(os.path.exists(zip_path))
            with zipfile.ZipFile(zip_path, "r") as archive:
                self.assertEqual(archive.namelist(), ["demo.osp"])
                self.assertEqual(archive.read("demo.osp").decode("utf-8"), "project-data")
            self.assertEqual(managed, [(7, 3, "demo")])

    def test_close_event_cancel_keeps_window_open(self):
        tutorial_calls = []
        save_calls = []
        event_calls = []

        fake_window = types.SimpleNamespace(
            tutorial_manager=types.SimpleNamespace(
                re_show_dialog=lambda: tutorial_calls.append("reshow"),
            ),
            actionSave_trigger=lambda: save_calls.append("save"),
            shutting_down=False,
        )
        self.app.project = types.SimpleNamespace(needs_save=lambda: True)

        event = types.SimpleNamespace(
            accept=lambda: event_calls.append("accept"),
            ignore=lambda: event_calls.append("ignore"),
        )

        with patch.object(
            self.main_window_module.QMessageBox,
            "question",
            return_value=self.main_window_module.QMessageBox.Cancel,
        ):
            self.main_window_module.MainWindow.closeEvent(fake_window, event)

        self.assertEqual(save_calls, [])
        self.assertEqual(tutorial_calls, ["reshow"])
        self.assertEqual(event_calls, ["ignore"])
        self.assertFalse(fake_window.shutting_down)

    def test_close_event_yes_saves_and_continues_shutdown(self):
        calls = []
        tracker = []
        event_calls = []

        fake_window = types.SimpleNamespace(
            tutorial_manager=None,
            actionSave_trigger=lambda: calls.append("save"),
            shutting_down=False,
            save_settings=lambda: calls.append("settings"),
            StopSignal=SignalRecorder(),
            http_server_thread=None,
            generation_queue=None,
            generation_service=None,
            preview_thread=None,
            preview_parent=None,
            videoPreview=None,
            timeline_sync=None,
            destroy_lock_file=lambda: calls.append("destroy_lock"),
        )
        self.app.project = types.SimpleNamespace(needs_save=lambda: True)
        self.app.logger_libopenshot = None
        event = types.SimpleNamespace(
            accept=lambda: event_calls.append("accept"),
            ignore=lambda: event_calls.append("ignore"),
        )

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    self.main_window_module.QMessageBox,
                    "question",
                    return_value=self.main_window_module.QMessageBox.Yes,
                )
            )
            stack.enter_context(
                patch.object(
                    self.main_window_module,
                    "track_metric_session",
                    tracker.append,
                )
            )
            stack.enter_context(
                patch.object(self.main_window_module.QCoreApplication, "processEvents", lambda: None)
            )
            self.main_window_module.MainWindow.closeEvent(fake_window, event)

        self.assertEqual(event_calls, ["accept"])
        self.assertIn("save", calls)
        self.assertIn("settings", calls)
        self.assertIn("destroy_lock", calls)
        self.assertEqual(tracker, [False])
        self.assertTrue(fake_window.shutting_down)

    def test_shutdown_cleans_global_hidden_optimized_files(self):
        calls = []
        tracker = []
        fake_window = types.SimpleNamespace(
            tutorial_manager=None,
            shutting_down=False,
            save_settings=lambda: calls.append("settings"),
            StopSignal=SignalRecorder(),
            http_server_thread=None,
            generation_queue=None,
            generation_service=None,
            proxy_service=types.SimpleNamespace(
                uses_global_hidden_proxy_root=lambda: True,
                delete_internal_project_proxy_files=lambda: calls.append("delete_proxy"),
                shutdown=lambda: calls.append("proxy_shutdown"),
            ),
            preview_thread=None,
            preview_parent=None,
            videoPreview=None,
            timeline_sync=None,
            destroy_lock_file=lambda: calls.append("destroy_lock"),
        )
        self.app.logger_libopenshot = None

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.main_window_module, "track_metric_session", tracker.append))
            stack.enter_context(patch.object(self.main_window_module.QCoreApplication, "processEvents", lambda: None))
            self.main_window_module.MainWindow._shutdown(fake_window)

        self.assertIn("delete_proxy", calls)
        self.assertIn("proxy_shutdown", calls)
        self.assertEqual(tracker, [False])

    def test_clear_optimized_files_cancel_does_nothing(self):
        proxy_calls = []
        fake_window = types.SimpleNamespace(
            proxy_service=types.SimpleNamespace(
                delete_internal_project_proxy_files=lambda: proxy_calls.append("delete"),
            ),
        )

        with patch.object(
            self.main_window_module.QMessageBox,
            "question",
            return_value=self.main_window_module.QMessageBox.No,
        ):
            self.main_window_module.MainWindow.actionClearOptimizedFiles_trigger(fake_window)

        self.assertEqual(proxy_calls, [])

    def test_clear_optimized_files_yes_deletes_project_optimized_files(self):
        proxy_calls = []
        fake_window = types.SimpleNamespace(
            proxy_service=types.SimpleNamespace(
                delete_internal_project_proxy_files=lambda: proxy_calls.append("delete"),
            ),
        )

        with patch.object(
            self.main_window_module.QMessageBox,
            "question",
            return_value=self.main_window_module.QMessageBox.Yes,
        ):
            self.main_window_module.MainWindow.actionClearOptimizedFiles_trigger(fake_window)

        self.assertEqual(proxy_calls, ["delete"])

    def test_refresh_clear_menu_action_states_enables_action_only_when_internal_optimized_files_exist(self):
        enabled_calls = []
        fake_window = types.SimpleNamespace(
            proxy_service=types.SimpleNamespace(
                has_internal_project_proxy_files=lambda: True,
            ),
            actionClearOptimizedFiles=types.SimpleNamespace(
                setEnabled=enabled_calls.append,
            ),
        )

        self.main_window_module.MainWindow._refresh_clear_menu_action_states(fake_window)

        self.assertEqual(enabled_calls, [True])

        enabled_calls = []
        fake_window = types.SimpleNamespace(
            proxy_service=types.SimpleNamespace(
                has_internal_project_proxy_files=lambda: False,
            ),
            actionClearOptimizedFiles=types.SimpleNamespace(
                setEnabled=enabled_calls.append,
            ),
        )

        self.main_window_module.MainWindow._refresh_clear_menu_action_states(fake_window)

        self.assertEqual(enabled_calls, [False])

    def test_close_event_no_skips_save_but_shuts_down(self):
        calls = []

        fake_window = types.SimpleNamespace(
            tutorial_manager=None,
            actionSave_trigger=lambda: calls.append("save"),
            shutting_down=False,
            save_settings=lambda: calls.append("settings"),
            StopSignal=SignalRecorder(),
            http_server_thread=None,
            generation_queue=None,
            generation_service=None,
            preview_thread=None,
            preview_parent=None,
            videoPreview=None,
            timeline_sync=None,
            destroy_lock_file=lambda: calls.append("destroy_lock"),
        )
        self.app.project = types.SimpleNamespace(needs_save=lambda: True)
        self.app.logger_libopenshot = None
        event = types.SimpleNamespace(accept=lambda: None, ignore=lambda: None)

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    self.main_window_module.QMessageBox,
                    "question",
                    return_value=self.main_window_module.QMessageBox.No,
                )
            )
            stack.enter_context(
                patch.object(self.main_window_module, "track_metric_session", lambda value: None)
            )
            stack.enter_context(
                patch.object(self.main_window_module.QCoreApplication, "processEvents", lambda: None)
            )
            self.main_window_module.MainWindow.closeEvent(fake_window, event)

        self.assertNotIn("save", calls)
        self.assertIn("settings", calls)
        self.assertIn("destroy_lock", calls)
        self.assertTrue(fake_window.shutting_down)

    def test_open_project_success_loads_project_and_refreshes_ui(self):
        refresh_files = SignalRecorder()
        refresh_frame = SignalRecorder()
        max_size = SignalRecorder()
        recent_calls = []
        clear_temp = []
        move_calls = []

        player = types.SimpleNamespace(Seek=lambda frame: move_calls.append(("seek", frame)))
        preview_thread = types.SimpleNamespace(player=player)
        video_preview = types.SimpleNamespace(
            clearTransformState=lambda: move_calls.append(("clear_transform",)),
            size=lambda: "preview-size",
        )

        fake_window = types.SimpleNamespace(
            SpeedSignal=SignalRecorder(),
            PauseSignal=SignalRecorder(),
            videoPreview=video_preview,
            clearSelections=lambda: move_calls.append(("clear_selections",)),
            preview_thread=preview_thread,
            SetWindowTitle=lambda: recent_calls.append("title"),
            refreshFilesSignal=refresh_files,
            refreshFrameSignal=refresh_frame,
            MaxSizeChanged=max_size,
            load_recent_menu=lambda: recent_calls.append("recent"),
            clear_temporary_files=lambda: clear_temp.append(True),
            movePlayhead=lambda frame: move_calls.append(("playhead", frame)),
            actionSave_trigger=lambda: None,
            statusBar=types.SimpleNamespace(showMessage=lambda *args: None),
            remove_recent_project=lambda path: None,
        )
        load_calls = []
        history_calls = []
        self.app.project = types.SimpleNamespace(
            needs_save=lambda: False,
            load=lambda path, clear_thumbnails: load_calls.append((path, clear_thumbnails)),
        )
        self.app.updates = types.SimpleNamespace(load_history=history_calls.append)
        self.app.window = fake_window
        self.app.setOverrideCursor = lambda cursor: None
        self.app.restoreOverrideCursor = lambda: recent_calls.append("restore")

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "existing.osp")
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(self.main_window_module.os.path, "exists", return_value=True)
                )
                stack.enter_context(
                    patch.object(self.main_window_module.QCoreApplication, "processEvents", lambda: None)
                )
                self.main_window_module.MainWindow.open_project(
                    fake_window,
                    project_path,
                    clear_thumbnails=True,
                )

            self.assertEqual(load_calls, [(project_path, True)])
            self.assertEqual(history_calls, [self.app.project])
            self.assertEqual(clear_temp, [True])
            self.assertEqual(refresh_files.calls, [()])
            self.assertEqual(refresh_frame.calls, [()])
            self.assertEqual(max_size.calls, [("preview-size",)])
            self.assertIn(("seek", 1), move_calls)
            self.assertIn(("playhead", 1), move_calls)
            self.assertIn("recent", recent_calls)
            self.assertIn("restore", recent_calls)

    def test_action_remove_clip_skips_locked_tracks(self):
        deleted = []
        removed = []
        refreshed = SignalRecorder()

        locked_clip = types.SimpleNamespace(data={"layer": 2}, delete=lambda: deleted.append("locked"))
        unlocked_clip = types.SimpleNamespace(data={"layer": 1}, delete=lambda: deleted.append("unlocked"))

        self.app.project = types.SimpleNamespace(get=lambda key: [{"number": 2, "lock": True}])
        self.app.updates = types.SimpleNamespace(transaction_id=None)
        self.app.window = types.SimpleNamespace(refreshFrameSignal=refreshed)

        fake_window = types.SimpleNamespace(
            selected_clips=["C1"],
            removeSelection=lambda item_id, item_type: removed.append((item_id, item_type)),
            emit_selection_signal=lambda: None,
            show_property_timeout=lambda: None,
        )

        with patch.object(self.main_window_module.Clip, "filter", return_value=[locked_clip, unlocked_clip]):
            self.main_window_module.MainWindow.actionRemoveClip_trigger(fake_window, refresh=True)

        self.assertEqual(deleted, ["unlocked"])
        self.assertEqual(removed, [("C1", "clip")])
        self.assertEqual(refreshed.calls, [()])
        self.assertIsNone(self.app.updates.transaction_id)

    def test_action_remove_transition_skips_locked_tracks(self):
        deleted = []
        removed = []
        refreshed = SignalRecorder()

        locked_tran = types.SimpleNamespace(data={"layer": 3}, delete=lambda: deleted.append("locked"))
        unlocked_tran = types.SimpleNamespace(data={"layer": 1}, delete=lambda: deleted.append("unlocked"))

        self.app.project = types.SimpleNamespace(get=lambda key: [{"number": 3, "lock": True}])
        self.app.updates = types.SimpleNamespace(transaction_id=None)
        self.app.window = types.SimpleNamespace(refreshFrameSignal=refreshed)

        fake_window = types.SimpleNamespace(
            selected_transitions=["T1"],
            removeSelection=lambda item_id, item_type: removed.append((item_id, item_type)),
            emit_selection_signal=lambda: None,
            show_property_timeout=lambda: None,
            refreshFrameSignal=refreshed,
        )

        with patch.object(self.main_window_module.Transition, "filter", return_value=[locked_tran, unlocked_tran]):
            self.main_window_module.MainWindow.actionRemoveTransition_trigger(fake_window, refresh=True)

        self.assertEqual(deleted, ["unlocked"])
        self.assertEqual(removed, [("T1", "transition")])
        self.assertEqual(refreshed.calls, [()])
        self.assertIsNone(self.app.updates.transaction_id)

    def test_ripple_delete_gap_shifts_only_later_items_on_same_layer(self):
        saved = []
        clips = [
            types.SimpleNamespace(data={"position": 4.0}, save=lambda: saved.append("clip-before")),
            types.SimpleNamespace(data={"position": 9.0}, save=lambda: saved.append("clip-after")),
        ]
        transitions = [
            types.SimpleNamespace(data={"position": 8.0}, save=lambda: saved.append("tran-before")),
            types.SimpleNamespace(data={"position": 12.0}, save=lambda: saved.append("tran-after")),
        ]

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.main_window_module.Clip, "filter", return_value=clips))
            stack.enter_context(
                patch.object(self.main_window_module.Transition, "filter", return_value=transitions)
            )
            self.main_window_module.MainWindow.ripple_delete_gap(
                types.SimpleNamespace(),
                ripple_start=8.0,
                layer=1,
                total_gap=2.5,
            )

        self.assertEqual(clips[0].data["position"], 4.0)
        self.assertEqual(clips[1].data["position"], 6.5)
        self.assertEqual(transitions[0].data["position"], 8.0)
        self.assertEqual(transitions[1].data["position"], 9.5)
        self.assertEqual(saved, ["clip-after", "tran-after"])
