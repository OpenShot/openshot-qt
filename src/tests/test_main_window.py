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
import json
import os
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import openshot

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QByteArray, QCoreApplication, QEvent, QKeySequence, Qt
from qt_api import QApplication, QDockWidget, QMainWindow, QMenu, QStandardItem, QStandardItemModel

from classes.project_data import ProjectDataStore
from classes.settings import SettingStore
from classes.updates import UpdateManager
from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app

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


class FakeDock:
    def __init__(self, name="", height=100, width=200, area=Qt.TopDockWidgetArea):
        self._name = name
        self._height = height
        self._width = width
        self._area = area
        self._minimum_height = 0
        self._maximum_height = 16777215
        self._minimum_width = 0
        self._maximum_width = 16777215
        self.fixed_heights = []
        self.fixed_widths = []

    def objectName(self):
        return self._name

    def height(self):
        return self._height

    def width(self):
        return self._width

    def minimumHeight(self):
        return self._minimum_height

    def maximumHeight(self):
        return self._maximum_height

    def minimumWidth(self):
        return self._minimum_width

    def maximumWidth(self):
        return self._maximum_width

    def setFixedHeight(self, height):
        self.fixed_heights.append(height)
        self._height = height
        self._minimum_height = height
        self._maximum_height = height

    def setFixedWidth(self, width):
        self.fixed_widths.append(width)
        self._width = width
        self._minimum_width = width
        self._maximum_width = width

    def setMinimumHeight(self, height):
        self._minimum_height = height

    def setMaximumHeight(self, height):
        self._maximum_height = height

    def setMinimumWidth(self, width):
        self._minimum_width = width

    def setMaximumWidth(self, width):
        self._maximum_width = width


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)
        metrics = types.ModuleType("classes.metrics")
        metrics.track_metric_session = lambda *args, **kwargs: None
        metrics.track_metric_screen = lambda *args, **kwargs: None
        sys.modules["classes.metrics"] = metrics
        sys.modules.pop("windows.views.timeline", None)
        sys.modules.pop("windows.main_window", None)
        sys.modules.pop("windows.views.properties_tableview", None)
        sys.modules.pop("windows.models.properties_model", None)
        cls.main_window_module = importlib.import_module("windows.main_window")
        cls.properties_tableview_module = importlib.import_module("windows.views.properties_tableview")
        cls.properties_model_module = importlib.import_module("windows.models.properties_model")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def test_cosmic_play_toggle_uses_hidpi_svg_renderer_for_both_states(self):
        from themes.cosmic.theme import CosmicTheme

        button = types.SimpleNamespace(setIcon=MagicMock())
        icon_size = object()
        action_play = object()
        toolbar = types.SimpleNamespace(
            widgetForAction=lambda action: button if action is action_play else None,
            iconSize=lambda: icon_size,
        )
        theme = CosmicTheme.__new__(CosmicTheme)
        theme.app = types.SimpleNamespace(
            window=types.SimpleNamespace(videoToolbar=toolbar, actionPlay=action_play)
        )
        theme.create_svg_icon = MagicMock(side_effect=["pause-icon", "play-icon"])

        theme.togglePlayIcon(True)
        pause_path, pause_size = theme.create_svg_icon.call_args.args
        self.assertEqual(os.path.basename(pause_path), "tool-media-pause.svg")
        self.assertIs(pause_size, icon_size)
        button.setIcon.assert_called_with("pause-icon")

        theme.togglePlayIcon(False)
        play_path, play_size = theme.create_svg_icon.call_args.args
        self.assertEqual(os.path.basename(play_path), "tool-media-play.svg")
        self.assertIs(play_size, icon_size)
        button.setIcon.assert_called_with("play-icon")

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

    def test_dock_style_scheduler_ignores_signal_payloads(self):
        starts = []
        callbacks = []

        class FakeSignal:
            def connect(self, callback):
                callbacks.append(callback)

        class FakeTimer:
            def __init__(self, parent=None):
                self.timeout = FakeSignal()

            def setSingleShot(self, enabled):
                pass

            def start(self, delay):
                starts.append(delay)

        fake_window = types.SimpleNamespace(
            _apply_scheduled_dock_style_update=lambda: None,
        )

        with patch.object(self.main_window_module, "QTimer", FakeTimer):
            self.main_window_module.MainWindow._schedule_dock_style_update(
                fake_window,
                True,
            )
            self.assertFalse(fake_window._dock_style_theme_changed)
            self.assertEqual(starts[-1], 150)

            self.main_window_module.MainWindow._schedule_dock_style_update(
                fake_window,
                theme_changed=True,
                delay=0,
            )
            self.assertTrue(fake_window._dock_style_theme_changed)
            self.assertEqual(starts[-1], 0)

    def test_dock_top_level_change_marks_interaction_and_restyles_immediately(self):
        calls = []
        fake_window = types.SimpleNamespace(
            _mark_dock_interaction_active=lambda: calls.append("interaction"),
            _schedule_dock_style_update=lambda **kwargs: calls.append(("style", kwargs)),
        )

        self.main_window_module.MainWindow._on_dock_top_level_changed(fake_window, True)

        self.assertEqual(calls, ["interaction", ("style", {"delay": 0})])

    def test_save_settings_persists_video_width_and_timeline_height(self):
        timeline_dock = FakeDock("dockTimeline", height=240, area=Qt.BottomDockWidgetArea)
        video_dock = FakeDock("dockVideo", height=360, width=520, area=Qt.TopDockWidgetArea)
        fake_window = types.SimpleNamespace(
            dockTimeline=timeline_dock,
            dockVideo=video_dock,
            saveState=lambda: QByteArray(b"state"),
            saveGeometry=lambda: QByteArray(b"geometry"),
            getDocks=lambda: [timeline_dock, video_dock],
            dockWidgetArea=lambda dock: dock._area,
        )

        self.main_window_module.MainWindow.save_settings(fake_window)

        self.assertEqual(self.app.settings.values["timeline_height"], 240)
        self.assertEqual(self.app.settings.values["video_dock_width"], 520)

    def test_default_settings_include_video_dock_width(self):
        with open(os.path.join(PATH, "settings", "_default.settings"), encoding="utf-8") as fh:
            settings = json.load(fh)

        values = {item.get("setting"): item.get("value") for item in settings}

        self.assertIn("video_dock_width", values)
        self.assertEqual(values["active_builtin_view"], "simple")

    def test_setting_store_invalid_key_warns_without_crashing(self):
        store = SettingStore()
        store._data = [{"setting": "known", "value": 1}]

        store.set("unknown", 2)

        self.assertEqual(store.get("known"), 1)

    def test_project_files_focus_blocks_properties_shortcut_for_keyboard_search(self):
        event = types.SimpleNamespace(
            type=lambda: QEvent.ShortcutOverride,
            modifiers=lambda: Qt.NoModifier,
            key=lambda: Qt.Key_U,
            accept=MagicMock(),
        )
        inactive_view = types.SimpleNamespace(hasFocus=lambda: False)
        window = types.SimpleNamespace(
            focusWidget=lambda: object(),
            _blocks_timeline_shortcuts=lambda _widget: False,
            emojiListView=inactive_view,
            filesView=types.SimpleNamespace(hasFocus=lambda: True),
            transitionsView=inactive_view,
            effectsView=inactive_view,
            getShortcutByName=lambda name: (
                [QKeySequence("U")] if name == "actionProperties" else []
            ),
        )
        self.app.window = window

        handled = self.main_window_module.MainWindow.eventFilter(window, None, event)

        self.assertTrue(handled)
        event.accept.assert_called_once_with()

    def test_apply_saved_dock_sizes_restores_video_width_and_timeline_height(self):
        timeline_dock = FakeDock("dockTimeline", height=140, area=Qt.BottomDockWidgetArea)
        video_dock = FakeDock("dockVideo", height=180, width=260, area=Qt.TopDockWidgetArea)
        fake_window = types.SimpleNamespace(
            dockTimeline=timeline_dock,
            dockVideo=video_dock,
            saved_timeline_height=260,
            saved_video_dock_width=640,
            width=lambda: 1200,
            height=lambda: 900,
        )
        fake_window._force_dock_extent_once = types.MethodType(
            self.main_window_module.MainWindow._force_dock_extent_once,
            fake_window)
        fake_window._positive_int = self.main_window_module.MainWindow._positive_int

        with patch.object(self.main_window_module.QTimer, "singleShot", lambda _delay, callback: callback()):
            self.main_window_module.MainWindow._apply_saved_dock_sizes(fake_window)

        self.assertEqual(timeline_dock.fixed_heights, [260])
        self.assertEqual(video_dock.fixed_widths, [640])
        self.assertEqual(timeline_dock.minimumHeight(), 0)
        self.assertEqual(video_dock.maximumWidth(), 16777215)

    def test_missing_video_dock_width_uses_initial_shown_layout_as_fallback(self):
        video_dock = FakeDock("dockVideo", height=300, width=540, area=Qt.TopDockWidgetArea)
        fake_window = types.SimpleNamespace(
            dockVideo=video_dock,
            saved_video_dock_width=None,
        )

        self.main_window_module.MainWindow._capture_missing_dock_size_fallbacks(fake_window)

        self.assertEqual(fake_window.saved_video_dock_width, 540)

    def test_active_custom_view_setter_does_not_shadow_reader(self):
        fake_window = types.SimpleNamespace()
        fake_window._active_custom_view_id = types.MethodType(
            self.main_window_module.MainWindow._active_custom_view_id,
            fake_window)
        fake_window._set_active_custom_view_id = types.MethodType(
            self.main_window_module.MainWindow._set_active_custom_view_id,
            fake_window)

        fake_window._set_active_custom_view_id("view-1")

        self.assertTrue(callable(fake_window._active_custom_view_id))
        self.assertEqual(fake_window._active_custom_view_id(), "view-1")
        self.assertEqual(self.app.settings.values["active_custom_view"], "view-1")
        self.assertEqual(self.app.settings.values["active_builtin_view"], "")

    def test_builtin_and_custom_view_identity_are_mutually_exclusive(self):
        fake_window = types.SimpleNamespace(_active_custom_view_id_value="view-1")

        self.main_window_module.MainWindow._set_active_builtin_view(fake_window, "recording")

        self.assertEqual(self.app.settings.values["active_builtin_view"], "recording")
        self.assertEqual(self.app.settings.values["active_custom_view"], "")
        self.assertEqual(fake_window._active_custom_view_id_value, "")

        self.main_window_module.MainWindow._set_active_custom_view_id(fake_window, "custom-1")

        self.assertEqual(self.app.settings.values["active_builtin_view"], "")
        self.assertEqual(self.app.settings.values["active_custom_view"], "custom-1")

    def test_restore_schedules_split_repair_only_for_recording_view(self):
        scheduled = []

        def make_window(view_name):
            return types.SimpleNamespace(
                saved_state=None,
                _active_builtin_view=lambda: view_name,
                _restore_hidden_docks=lambda _names: None,
                _apply_saved_dock_sizes=lambda: None,
                _repair_recording_view_split=lambda: None,
            )

        with patch.object(self.main_window_module.QTimer, "singleShot", lambda delay, callback: scheduled.append((delay, callback))):
            self.main_window_module.MainWindow._restore_state_and_dock_sizes(make_window("simple"))
            self.main_window_module.MainWindow._restore_state_and_dock_sizes(make_window("color"))
            self.main_window_module.MainWindow._restore_state_and_dock_sizes(make_window("recording"))

        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 250)

    def test_recording_view_repair_restores_adjustable_video_timeline_split(self):
        calls = []

        class RepairDock:
            def __init__(self, name, floating=False):
                self.name = name
                self.floating = floating
                self.shown = False

            def isFloating(self):
                return self.floating

            def setFloating(self, floating):
                self.floating = floating
                calls.append(("floating", self.name, floating))

            def show(self):
                self.shown = True

        video = RepairDock("video", floating=True)
        timeline = RepairDock("timeline")
        areas = {video: Qt.NoDockWidgetArea, timeline: Qt.NoDockWidgetArea}
        fake_window = types.SimpleNamespace(
            dockVideo=video,
            dockTimeline=timeline,
            _active_builtin_view=lambda: "recording",
            dockWidgetArea=lambda dock: areas[dock],
            addDockWidget=lambda area, dock: (areas.__setitem__(dock, area), calls.append(("add", dock.name, area))),
            splitDockWidget=lambda first, second, orientation: calls.append(("split", first.name, second.name, orientation)),
            _apply_saved_timeline_height=lambda: calls.append("height"),
            style_dock_widgets=lambda: calls.append("style"),
        )

        self.main_window_module.MainWindow._repair_recording_view_split(fake_window)

        self.assertIn(("split", "video", "timeline", Qt.Vertical), calls)
        self.assertTrue(video.shown)
        self.assertTrue(timeline.shown)
        self.assertIn("height", calls)
        self.assertIn("style", calls)

    def test_scheduled_dock_style_update_waits_for_mouse_release(self):
        starts = []
        styles = []
        fake_window = types.SimpleNamespace(
            _dock_style_theme_changed=False,
            _dock_style_timer=types.SimpleNamespace(start=starts.append),
            style_dock_widgets=lambda theme_changed=False: styles.append(theme_changed),
        )

        with patch.object(
            self.main_window_module.QApplication,
            "mouseButtons",
            return_value=Qt.LeftButton,
        ):
            self.main_window_module.MainWindow._apply_scheduled_dock_style_update(fake_window)

        self.assertEqual(starts, [50])
        self.assertEqual(styles, [])

        fake_window._dock_style_theme_changed = True
        with patch.object(
            self.main_window_module.QApplication,
            "mouseButtons",
            return_value=Qt.NoButton,
        ):
            self.main_window_module.MainWindow._apply_scheduled_dock_style_update(fake_window)

        self.assertEqual(styles, [True])
        self.assertFalse(fake_window._dock_style_theme_changed)

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
        settings = openshot.Settings.Instance()
        previous_caching = settings.ENABLE_PLAYBACK_CACHING
        settings.ENABLE_PLAYBACK_CACHING = True

        try:
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
                self.assertTrue(settings.ENABLE_PLAYBACK_CACHING)
        finally:
            settings.ENABLE_PLAYBACK_CACHING = previous_caching

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
        scheduled = []
        settings = openshot.Settings.Instance()
        previous_caching = settings.ENABLE_PLAYBACK_CACHING
        settings.ENABLE_PLAYBACK_CACHING = True

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                project_path = os.path.join(tmpdir, "existing.osp")
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(self.main_window_module.os.path, "exists", return_value=True)
                    )
                    stack.enter_context(
                        patch.object(self.main_window_module.QCoreApplication, "processEvents", lambda: None)
                    )
                    stack.enter_context(
                        patch.object(
                            self.main_window_module.QTimer,
                            "singleShot",
                            side_effect=lambda delay, callback: scheduled.append((delay, callback)),
                        )
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
                self.assertEqual(refresh_frame.calls, [])
                self.assertEqual(max_size.calls, [("preview-size",)])
                self.assertIn(("seek", 1), move_calls)
                self.assertFalse(settings.ENABLE_PLAYBACK_CACHING)
                self.assertEqual([delay for delay, _callback in scheduled], [0])
                scheduled[0][1]()
                self.assertEqual(refresh_frame.calls, [()])
        finally:
            settings.ENABLE_PLAYBACK_CACHING = previous_caching
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

    def test_delete_item_removes_selected_effects(self):
        calls = []
        refreshed = SignalRecorder()

        self.app.updates = types.SimpleNamespace(transaction_id=None)

        fake_window = types.SimpleNamespace(
            filesView=types.SimpleNamespace(hasFocus=lambda: False),
            timeline=None,
            refreshFrameSignal=refreshed,
            actionRemoveEffect_trigger=lambda: calls.append("effect"),
            actionRemoveClip_trigger=lambda refresh=False: calls.append(("clip", refresh)),
            actionRemoveTransition_trigger=lambda refresh=False: calls.append(("transition", refresh)),
        )

        self.main_window_module.MainWindow.deleteItem(fake_window)

        self.assertEqual(calls, ["effect", ("clip", False), ("transition", False)])
        self.assertEqual(refreshed.calls, [()])
        self.assertIsNone(self.app.updates.transaction_id)

    def test_add_and_show_docks_keep_default_dock_features(self):
        fake_window = QMainWindow()
        normal_dock = QDockWidget("Normal", fake_window)
        normal_dock.setObjectName("dockNormal")

        self.main_window_module.MainWindow.addDocks(fake_window, [normal_dock], Qt.RightDockWidgetArea)
        self.assertTrue(normal_dock.features() & QDockWidget.DockWidgetClosable)
        self.assertTrue(normal_dock.features() & QDockWidget.DockWidgetMovable)
        self.assertTrue(normal_dock.features() & QDockWidget.DockWidgetFloatable)

        normal_dock.hide()
        fake_window.showDocks = lambda docks: self.main_window_module.MainWindow.showDocks(fake_window, docks)
        self.main_window_module.MainWindow.showDocks(fake_window, [normal_dock])
        self.assertTrue(normal_dock.features() & QDockWidget.DockWidgetClosable)
        self.assertTrue(normal_dock.features() & QDockWidget.DockWidgetMovable)
        self.assertTrue(normal_dock.features() & QDockWidget.DockWidgetFloatable)

    def test_properties_dock_reanchors_to_files_when_shown_after_view_removed_it(self):
        fake_window = QMainWindow()
        fake_window.dockFiles = QDockWidget("Project Files", fake_window)
        fake_window.dockFiles.setObjectName("dockFiles")
        fake_window.dockProperties = QDockWidget("Properties", fake_window)
        fake_window.dockProperties.setObjectName("dockProperties")
        fake_window.style_dock_widgets = lambda: None

        fake_window.addDockWidget(Qt.LeftDockWidgetArea, fake_window.dockFiles)
        fake_window.removeDockWidget(fake_window.dockProperties)

        self.main_window_module.MainWindow._anchor_and_show_properties_dock(fake_window)

        self.assertEqual(fake_window.dockWidgetArea(fake_window.dockProperties), Qt.LeftDockWidgetArea)
        self.assertIn(fake_window.dockProperties, fake_window.tabifiedDockWidgets(fake_window.dockFiles))
        self.assertFalse(fake_window.dockProperties.isFloating())
        self.assertFalse(fake_window.dockProperties.isHidden())

    def test_properties_dock_preserves_existing_simple_view_position(self):
        fake_window = QMainWindow()
        fake_window.dockFiles = QDockWidget("Project Files", fake_window)
        fake_window.dockFiles.setObjectName("dockFiles")
        fake_window.dockProperties = QDockWidget("Properties", fake_window)
        fake_window.dockProperties.setObjectName("dockProperties")
        fake_window.style_dock_widgets = lambda: None

        fake_window.addDockWidget(Qt.TopDockWidgetArea, fake_window.dockFiles)
        fake_window.addDockWidget(Qt.LeftDockWidgetArea, fake_window.dockProperties)
        fake_window.dockProperties.hide()

        self.main_window_module.MainWindow._anchor_and_show_properties_dock(fake_window)

        self.assertEqual(fake_window.dockWidgetArea(fake_window.dockProperties), Qt.LeftDockWidgetArea)
        self.assertNotIn(fake_window.dockProperties, fake_window.tabifiedDockWidgets(fake_window.dockFiles))
        self.assertFalse(fake_window.dockProperties.isHidden())

    def test_recording_view_keeps_properties_hidden_but_tabified_with_files(self):
        fake_window = QMainWindow()
        fake_window.dockFiles = QDockWidget("Project Files", fake_window)
        fake_window.dockFiles.setObjectName("dockFiles")
        fake_window.dockProperties = QDockWidget("Properties", fake_window)
        fake_window.dockProperties.setObjectName("dockProperties")
        fake_window.dockVideo = QDockWidget("Video Preview", fake_window)
        fake_window.dockVideo.setObjectName("dockVideo")
        fake_window.dockTimeline = QDockWidget("Timeline", fake_window)
        fake_window.dockTimeline.setObjectName("dockTimeline")
        fake_window.dockAudioRecording = QDockWidget("Recording", fake_window)
        fake_window.dockAudioRecording.setObjectName("dockAudioRecording")
        fake_window._set_active_custom_view_id = lambda _view_id: None
        fake_window._set_active_builtin_view = lambda _view_id: None
        fake_window._ensure_audio_recording_dock_content = lambda: None
        fake_window.getDocks = lambda: fake_window.findChildren(QDockWidget)
        fake_window.removeDocks = lambda: self.main_window_module.MainWindow.removeDocks(fake_window)
        fake_window.addDocks = lambda docks, area: self.main_window_module.MainWindow.addDocks(fake_window, docks, area)
        fake_window.floatDocks = lambda is_floating: self.main_window_module.MainWindow.floatDocks(fake_window, is_floating)
        fake_window.showDocks = lambda docks: self.main_window_module.MainWindow.showDocks(fake_window, docks)
        fake_window.style_dock_widgets = lambda: None

        self.main_window_module.MainWindow.actionAudio_Recording_View_trigger(fake_window)

        self.assertEqual(fake_window.dockWidgetArea(fake_window.dockProperties), Qt.LeftDockWidgetArea)
        self.assertIn(fake_window.dockProperties, fake_window.tabifiedDockWidgets(fake_window.dockFiles))
        self.assertTrue(fake_window.dockProperties.isHidden())
        self.assertFalse(fake_window.dockFiles.isHidden())

    def test_scope_menu_keeps_conditional_show_and_close_all_actions(self):
        fake_window = QMainWindow()
        fake_window.scopes_menu = QMenu(fake_window)
        fake_window.dockAudio = QDockWidget("Audio Levels", fake_window)
        fake_window.dockAudio.setObjectName("dockAudio")
        fake_window.dockHistogram = QDockWidget("Histogram", fake_window)
        fake_window.dockHistogram.setObjectName("dockHistogram")
        fake_window.dockLumaWaveform = QDockWidget("Luma Waveform", fake_window)
        fake_window.dockLumaWaveform.setObjectName("dockLumaWaveform")
        fake_window.dockVectorscope = QDockWidget("Vectorscope", fake_window)
        fake_window.dockVectorscope.setObjectName("dockVectorscope")
        for dock in [
                fake_window.dockAudio,
                fake_window.dockHistogram,
                fake_window.dockLumaWaveform,
                fake_window.dockVectorscope]:
            fake_window.addDockWidget(Qt.RightDockWidgetArea, dock)
            dock.hide()

        open_docks = set()
        fake_window._scope_docks = lambda: self.main_window_module.MainWindow._scope_docks(fake_window)
        fake_window._dock_is_open = lambda dock: dock in open_docks
        fake_window.closeDocks = lambda docks: self.main_window_module.MainWindow.closeDocks(fake_window, docks)
        fake_window.show_all_scope_docks = lambda: None
        fake_window._add_dock_visibility_actions = (
            lambda menu, docks, show_text, close_text, show_callback=None:
            self.main_window_module.MainWindow._add_dock_visibility_actions(
                fake_window, menu, docks, show_text, close_text, show_callback))

        self.main_window_module.MainWindow._rebuild_scopes_menu(fake_window)
        action_texts = [action.text() for action in fake_window.scopes_menu.actions() if not action.isSeparator()]
        self.assertIn("Show All Scopes", action_texts)
        self.assertNotIn("Close All Scopes", action_texts)
        self.assertNotIn("Lock Scopes", action_texts)

        open_docks.add(fake_window.dockAudio)
        self.main_window_module.MainWindow._rebuild_scopes_menu(fake_window)
        action_texts = [action.text() for action in fake_window.scopes_menu.actions() if not action.isSeparator()]
        self.assertIn("Show All Scopes", action_texts)
        self.assertIn("Close All Scopes", action_texts)
        self.assertNotIn("Unlock Scopes", action_texts)

    def test_live_property_resume_keeps_cache_disabled_until_seek_or_play(self):
        settings = openshot.Settings.Instance()
        previous = settings.ENABLE_PLAYBACK_CACHING
        try:
            settings.ENABLE_PLAYBACK_CACHING = False
            fake_view = types.SimpleNamespace(live_property_cache_paused=True)

            self.properties_tableview_module.PropertiesTableView.resume_live_property_caching(fake_view)

            self.assertFalse(fake_view.live_property_cache_paused)
            self.assertFalse(settings.ENABLE_PLAYBACK_CACHING)
        finally:
            settings.ENABLE_PLAYBACK_CACHING = previous

    def test_insert_keyframe_adds_current_color_property_frame(self):
        saved = []
        refreshed = SignalRecorder()
        self.app.window = types.SimpleNamespace(refreshFrameSignal=refreshed)

        effect = types.SimpleNamespace(
            data={
                "wave_color": {
                    "red": {"Points": [{"co": {"X": 1.0, "Y": 0.0}, "interpolation": openshot.LINEAR}]},
                    "green": {"Points": [{"co": {"X": 1.0, "Y": 123.0}, "interpolation": openshot.LINEAR}]},
                    "blue": {"Points": [{"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR}]},
                    "alpha": {"Points": [{"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR}]},
                }
            },
        )
        effect.save = lambda: saved.append(effect.data)

        model = QStandardItemModel()
        label = QStandardItem("Wave Color")
        label.setData((
            "wave_color",
            {
                "type": "color",
                "red": {"value": 0},
                "green": {"value": 123},
                "blue": {"value": 255},
                "alpha": {"value": 255},
                "closest_point_x": 1,
                "previous_point_x": 1,
                "object_id": None,
                "max": 255.0,
            },
        ))
        value = QStandardItem("")
        value.setData([("effect-1", "effect")])
        model.appendRow([label, value])

        parent = types.SimpleNamespace(
            currentIndex=lambda: model.index(0, 0),
            clearSelection=lambda: None,
            setCurrentIndex=lambda index: None,
        )
        helper = self.properties_model_module.PropertiesModel.__new__(
            self.properties_model_module.PropertiesModel)
        helper.model = model
        helper.parent = parent
        helper.frame_number = 30
        helper._trim_preview_mode = False

        with patch.object(self.properties_model_module.Effect, "get", return_value=effect):
            helper.insert_keyframe(value)

        self.assertEqual(len(saved), 1)
        color = effect.data["wave_color"]
        self.assertIn(30, [point["co"]["X"] for point in color["red"]["Points"]])
        self.assertIn(30, [point["co"]["X"] for point in color["green"]["Points"]])
        self.assertIn(30, [point["co"]["X"] for point in color["blue"]["Points"]])
        self.assertIn(30, [point["co"]["X"] for point in color["alpha"]["Points"]])
        self.assertEqual(refreshed.calls, [()])

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
