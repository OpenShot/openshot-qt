"""
 @file
 @brief This file contains unit tests for timeline helper logic
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
import importlib
import os
import sys
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import openshot


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from PyQt5.QtCore import QCoreApplication, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from classes import info
from classes.updates import UpdateAction
from qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
            "legacy-based-timeline": False,
        }

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


def ensure_app_state(app):
    return ensure_qt_app_state(app, DummySettings)


class TimelineHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)
        cls._web_backend_patcher = patch.object(info, "WEB_BACKEND", "qwidget")
        cls._web_backend_patcher.start()
        sys.modules.pop("windows.views.timeline", None)
        cls.timeline_module = importlib.import_module("windows.views.timeline")
        cls.qwidget_base_module = importlib.import_module("windows.views.timeline_backend.qwidget.base")
        cls.clip_paint_module = importlib.import_module("windows.views.timeline_backend.paint.clip")
        cls.qwidget_clip_module = importlib.import_module("windows.views.timeline_backend.qwidget.clip")
        cls.qwidget_keyframe_module = importlib.import_module("windows.views.timeline_backend.qwidget.keyframe")
        cls.qwidget_keyframe_panel_module = importlib.import_module("windows.views.timeline_backend.qwidget.keyframe_panel")
        cls.thumbnails_module = importlib.import_module("windows.views.timeline_backend.qwidget.thumbnails")
        cls.waveform_module = importlib.import_module("classes.waveform")

    def make_helper(self):
        timeline_module = self.timeline_module

        class Helper:
            def _transition_mask_reader(self, transition_data, fallback_data=None):
                return timeline_module.TimelineView._transition_mask_reader(
                    self,
                    transition_data,
                    fallback_data,
                )

            def _payload_contains_waveform(self, value):
                return timeline_module.TimelineView._payload_contains_waveform(self, value)

            def _collect_clip_ids_from_value(self, value, clip_ids):
                return timeline_module.TimelineView._collect_clip_ids_from_value(self, value, clip_ids)

        return Helper()

    @classmethod
    def tearDownClass(cls):
        cls._web_backend_patcher.stop()
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def make_time_helper(self):
        timeline_module = self.timeline_module

        class Helper:
            def __init__(self):
                self.window = types.SimpleNamespace(
                    timeline_sync=types.SimpleNamespace(
                        timeline=types.SimpleNamespace(GetClip=lambda _clip_id: None)
                    )
                )
                self.updated = []

            def get_uuid(self):
                return "tx-1"

            def AddPoint(self, keyframe, new_point):
                return timeline_module.TimelineView.AddPoint(self, keyframe, new_point)

            def update_clip_data(self, clip_data, **_kwargs):
                self.updated.append(copy.deepcopy(clip_data))

            def Show_Waveform_Triggered(self, clip_ids, transaction_id=None):
                self.updated.append(
                    {"waveform_refresh": list(clip_ids), "transaction_id": transaction_id}
                )

        return Helper()

    def make_finalize_keyframe_helper(self):
        timeline_module = self.timeline_module

        class Helper:
            def __init__(self):
                self.keyframe_transaction_id = "tx-kf-1"
                self.keyframe_drag_original = {}
                self.show_wait_spinner = False
                self.window = types.SimpleNamespace(
                    IgnoreUpdates=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)
                )
                self.updated = []

            def _clip_has_visible_waveform(self, clip):
                return timeline_module.TimelineView._clip_has_visible_waveform(self, clip)

            def _clip_volume_curve_changed(self, original_data, current_data):
                return timeline_module.TimelineView._clip_volume_curve_changed(
                    self,
                    original_data,
                    current_data,
                )

            def Show_Waveform_Triggered(self, clip_ids, transaction_id=None):
                self.updated.append(
                    {"waveform_refresh": list(clip_ids), "transaction_id": transaction_id}
                )

        return Helper()

    def make_qwidget_clip_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self):
                self._pending_clip_overrides = {}
                self._waveform_samples_per_second = None
                self.enable_timing = False
                self.enable_snapping = False
                self.pixels_per_second = 24.0
                self.fps_float = 24.0
                self.track_name_width = 0.0
                self._resize_edge = "right"
                self._resize_clip_max_duration = None
                self._resize_allow_left_overflow = False
                self._resize_clip_is_single_image = False

            def _seconds_from_x(self, value):
                return float(value) / float(self.pixels_per_second or 1.0)

            def _snap_trim_delta(self, delta_seconds, edge=None):
                return float(delta_seconds)

        return Helper()

    def make_qwidget_cursor_helper(self):
        qwidget_base_module = self.qwidget_base_module

        class GeometryStub:
            def __init__(self):
                self.items = []

            def ensure(self):
                return None

            def iter_transitions(self, reverse=False):
                return []

            def iter_clips(self, reverse=False):
                return []

            def iter_items(self, reverse=False):
                items = list(self.items)
                if reverse:
                    items.reverse()
                return items

            def iter_tracks(self):
                return []

            def timeline_handle_rect(self):
                return QRectF()

        class Helper:
            def __init__(self):
                self._fixed_cursor = None
                self.enable_razor = False
                self.geometry = GeometryStub()
                self.playhead_painter = types.SimpleNamespace(icon_pix=None)
                self.cursors = {
                    "hand": object(),
                    "resize_x": object(),
                    "razor": object(),
                }
                self.cursor_value = None
                self.unset_cursor_called = False

            def setCursor(self, cursor):
                self.cursor_value = cursor
                self.unset_cursor_called = False

            def unsetCursor(self):
                self.cursor_value = None
                self.unset_cursor_called = True

            def _updateCursor(self, pos):
                return qwidget_base_module.TimelineWidgetBase._updateCursor(self, pos)

            def _playhead_handle_rect(self):
                return QRectF()

            def _effect_icon_at(self, pos):
                return None

            def _track_toolbar_button_at(self, pos):
                return None

            def _transition_menu_rect(self, rect):
                return QRectF()

            def _marker_at(self, pos):
                return None

            def _get_keyframe_at(self, pos):
                return None

            def _panel_marker_at(self, pos):
                return None

            def _clip_menu_rect(self, rect):
                return QRectF()

            def _track_menu_rect(self, rect):
                return QRectF()

        return Helper()

    def make_slice_helper(self):
        class Helper:
            def __init__(self):
                self.updated_transitions = []
                self.ripple_calls = []
                self.window = types.SimpleNamespace(
                    SeekSignal=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)
                )
                self.redraw_audio_timer = types.SimpleNamespace(start=lambda: None)

            def get_uuid(self):
                return "slice-tx-1"

            def update_transition_data(self, transition_json, **_kwargs):
                self.updated_transitions.append(copy.deepcopy(transition_json))

            def ripple_delete_gap(self, ripple_start, layer, ripple_gap):
                self.ripple_calls.append((ripple_start, layer, ripple_gap))

        return Helper()

    def make_qwidget_keyframe_drag_helper(self):
        class Helper:
            def __init__(self):
                self._dragging_panel_keyframes = None
                self.pixels_per_second = 24.0
                self.fps_float = 24.0
                self._keyframes_dirty = False
                self.update_calls = 0
                self.begin_calls = 0
                self.apply_calls = []
                self.seek_calls = []
                self.panel_preview_calls = []
                self.release_calls = 0
                self.click_calls = []
                self.finalize_calls = []
                self.show_property_calls = 0
                self.mouse_dragging = True
                self._dragging_keyframe = {
                    "marker": {
                        "clip_rect": QRectF(0.0, 0.0, 240.0, 12.0),
                        "clip_start": 0.0,
                        "clip_end": 10.0,
                        "object_type": "clip",
                        "object_id": "C1",
                    },
                    "current_frame": 25,
                    "pending_frame": 25,
                    "pending_seconds": 1.0,
                    "clip_start": 0.0,
                    "clip_end": 10.0,
                    "transaction_started": False,
                    "moved": False,
                    "object_type": "clip",
                    "object_id": "C1",
                }
                self.win = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        FinalizeKeyframeDrag=lambda object_type, object_id: self.finalize_calls.append(
                            (object_type, object_id)
                        )
                    ),
                    show_property_timeout=lambda: setattr(
                        self,
                        "show_property_calls",
                        self.show_property_calls + 1,
                    ),
                )

            def _clamp_keyframe_seconds(self, seconds, clip_start, clip_end):
                return max(float(clip_start), min(float(seconds), float(clip_end)))

            def _apply_keyframe_snapping(self, drag, relative_seconds):
                return float(relative_seconds)

            def _snap_time(self, seconds):
                return float(seconds)

            def _keyframe_base_position(self, marker):
                return 0.0

            def _panel_preview_marker(self, *args, **kwargs):
                self.panel_preview_calls.append((args, kwargs))

            def _seek_to_marker_frame(self, marker, frame, start_preroll=True):
                self.seek_calls.append((frame, bool(start_preroll)))

            def _begin_keyframe_transaction(self):
                self.begin_calls += 1
                self._dragging_keyframe["transaction_started"] = True

            def _apply_keyframe_delta(self, drag, ignore_refresh=False, force=False):
                self.apply_calls.append((bool(ignore_refresh), bool(force)))

            def _handle_keyframe_click(self, marker, clear_existing=True):
                self.click_calls.append((marker, bool(clear_existing)))

            def _release_cursor(self):
                self.release_calls += 1

            def update(self):
                self.update_calls += 1

        return Helper()

    def make_qwidget_panel_keyframe_drag_helper(self):
        class Helper:
            def __init__(self):
                entry = {
                    "original_seconds": 1.0,
                    "pending_seconds": 1.0,
                    "original_frame": 25,
                    "pending_frame": 25,
                }
                self._dragging_panel_keyframes = {
                    "lane_rect": QRectF(0.0, 0.0, 240.0, 20.0),
                    "entries": [entry],
                    "anchor": entry,
                    "fps": 24.0,
                    "context": {"position": 0.0, "clip_start": 0.0},
                    "base_position": 0.0,
                    "moved": False,
                    "transaction_started": False,
                    "owner_type": "clip",
                    "object_id": "C1",
                }
                self._panel_press_info = {}
                self.fps_float = 24.0
                self._keyframes_dirty = False
                self.mouse_dragging = True
                self.update_calls = 0
                self.update_property_calls = 0
                self.begin_calls = 0
                self.apply_calls = []
                self.seek_calls = []
                self.finalize_calls = []
                self.release_calls = 0
                self.track_panel_refresh_calls = 0
                self.geometry = types.SimpleNamespace(
                    mark_dirty=lambda: setattr(
                        self,
                        "track_panel_refresh_calls",
                        self.track_panel_refresh_calls + 1,
                    )
                )
                self.win = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        FinalizeKeyframeDrag=lambda object_type, object_id: self.finalize_calls.append(
                            (object_type, object_id)
                        )
                    ),
                    SeekSignal=types.SimpleNamespace(
                        emit=lambda frame, preroll=True: self.seek_calls.append(
                            (int(frame), bool(preroll))
                        )
                    ),
                    show_property_timeout=lambda: None,
                )

            def _panel_x_to_seconds(self, x_pos):
                return float(x_pos) / 24.0

            def _panel_snap_seconds(self, drag, seconds):
                return float(seconds)

            def _panel_update_property_points(self, drag):
                self.update_property_calls += 1

            def _panel_begin_transaction(self, drag):
                self.begin_calls += 1
                drag["transaction_started"] = True

            def _apply_panel_keyframe_delta(self, drag, *, ignore_refresh=False, force=False):
                self.apply_calls.append((bool(ignore_refresh), bool(force)))

            def _release_cursor(self):
                self.release_calls += 1

            def _update_track_panel_properties(self):
                self.track_panel_refresh_calls += 1

            def update(self):
                self.update_calls += 1

        return Helper()

    def make_clip_painter(self, thumbnail_style="entire", pixels_per_second=24.0, project_fps=24.0):
        clip_paint_module = self.clip_paint_module

        class ThemeClip:
            border_width = 1
            border_radius = 0
            border_color = QColor("black")
            thumb_width = 48
            thumb_height = 36
            thumb_min_visible = 5
            thumb_clip_min_width = 24
            shadow_blur = 0
            shadow_color = QColor()
            background = QColor("white")
            background2 = QColor("white")
            top_overlay = QColor()
            top_overlay2 = QColor()

        class Theme:
            clip = ThemeClip()
            clip_selected = QColor("red")
            menu_icon = None
            menu_size = 0
            menu_margin = 0

        from PyQt5.QtWidgets import QWidget

        class Widget(QWidget):
            def __init__(self):
                super().__init__()
                self.theme = Theme()
                self.pixels_per_second = pixels_per_second
                self.thumbnail_style = thumbnail_style
                self.thumbnail_generation = 0
                self._resizing_item = None
                self._press_hit = ""
                self.thumbnail_manager = None
                self.fps_float = project_fps
                self._suspend_thumbnail_requests = False

            def clip_has_pending_override(self, clip):
                return False

            def clip_waveform_cache_token(self, clip):
                return None

        widget = Widget()
        painter = clip_paint_module.ClipPainter(widget)
        return painter

    def make_timing_preview_painter(self, thumbnail_style="entire", current_width=144.0):
        painter = self.make_clip_painter(
            thumbnail_style=thumbnail_style,
            pixels_per_second=24.0,
            project_fps=24.0,
        )
        clip = types.SimpleNamespace(id="C1", data={"file_id": "F1"})
        painter.w._pending_clip_overrides = {
            "C1": {
                "start": 0.0,
                "end": 6.0,
                "initial_start": 0.0,
                "initial_end": 3.0,
                "scale": True,
            }
        }
        painter.w._resizing_item = clip
        painter.w._press_hit = "clip-edge"
        painter.w.clip_has_pending_override = lambda candidate: getattr(candidate, "id", None) == "C1"

        base_pix = self.clip_paint_module.QPixmap(72, 40)
        base_pix.fill(QColor("blue"))
        painter._retime_preview_cache["C1"] = {"pix": base_pix, "blur": 0.0}

        full_rect = self.clip_paint_module.QRectF(0, 0, current_width, 40)
        segment_rect = self.clip_paint_module.QRectF(0, 0, current_width, 40)
        return painter, clip, full_rect, segment_rect

    def collect_thumbnail_frames(
        self,
        clip,
        *,
        thumbnail_style="entire",
        inner_width=72.0,
        duration=3.0,
        pixels_per_second=24.0,
        project_fps=24.0,
    ):
        painter = self.make_clip_painter(
            thumbnail_style=thumbnail_style,
            pixels_per_second=pixels_per_second,
            project_fps=project_fps,
        )
        frames = []

        def fake_get_thumbnail_pixmap(_self, clip_key, file_id, frame, rect, generation, allow_request=True):
            frames.append(frame)
            return None

        painter._get_thumbnail_pixmap = types.MethodType(fake_get_thumbnail_pixmap, painter)
        inner = self.clip_paint_module.QRectF(0, 0, inner_width, 40)
        segment = {
            "segment_width": inner_width,
            "clip_width": inner_width,
            "offset_seconds": 0.0,
            "duration_seconds": duration,
            "clip_duration": duration,
            "includes_start": True,
            "includes_end": True,
        }
        painter._draw_thumbnails(None, clip, inner, segment)
        return frames

    def collect_thumbnail_frames_with_trim_preview(
        self,
        clip,
        *,
        thumbnail_style="entire",
        inner_width=60.0,
        duration=2.5,
        project_fps=24.0,
        initial_start=0.0,
        initial_end=3.0,
    ):
        painter = self.make_clip_painter(
            thumbnail_style=thumbnail_style,
            pixels_per_second=(inner_width / duration),
            project_fps=project_fps,
        )
        frames = []

        painter.w._pending_clip_overrides = {
            clip.id: {
                "start": clip.data.get("start"),
                "end": clip.data.get("end"),
                "initial_start": initial_start,
                "initial_end": initial_end,
                "scale": False,
            }
        }
        painter.w._resizing_item = clip
        painter.w._press_hit = "clip-edge"
        painter.w.clip_has_pending_override = lambda candidate: getattr(candidate, "id", None) == clip.id

        def fake_get_thumbnail_pixmap(_self, clip_key, file_id, frame, rect, generation, allow_request=True):
            frames.append(frame)
            return None

        painter._get_thumbnail_pixmap = types.MethodType(fake_get_thumbnail_pixmap, painter)
        inner = self.clip_paint_module.QRectF(0, 0, inner_width, 40)
        segment = {
            "segment_width": inner_width,
            "clip_width": inner_width,
            "offset_seconds": 0.0,
            "duration_seconds": duration,
            "clip_duration": duration,
            "includes_start": True,
            "includes_end": True,
        }
        painter._draw_thumbnails(None, clip, inner, segment)
        return frames

    def test_transition_reader_changed_detects_path_change(self):
        helper = self.make_helper()
        changed = self.timeline_module.TimelineView._transition_reader_changed(
            helper,
            {"reader": {"path": "/new.svg", "id": "R1", "has_single_image": True}},
            {"reader": {"path": "/old.svg", "id": "R1", "has_single_image": True}},
        )
        unchanged = self.timeline_module.TimelineView._transition_reader_changed(
            helper,
            {"reader": {"path": "/same.svg", "id": "R1", "has_single_image": True}},
            {"reader": {"path": "/same.svg", "id": "R1", "has_single_image": True}},
        )

        self.assertTrue(changed)
        self.assertFalse(unchanged)

    def test_transition_uses_static_mask_prefers_has_single_image_flag(self):
        helper = self.make_helper()

        self.assertTrue(
            self.timeline_module.TimelineView._transition_uses_static_mask(
                helper,
                {"reader": {"has_single_image": True}},
            )
        )
        self.assertFalse(
            self.timeline_module.TimelineView._transition_uses_static_mask(
                helper,
                {"reader": {"has_single_image": False}},
            )
        )

    def test_find_missing_transition_details_returns_overlap(self):
        clip_data = {"id": "B", "layer": 1, "position": 4.0, "start": 0.0, "end": 6.0}
        existing_clip = types.SimpleNamespace(data={"id": "A", "position": 0.0, "start": 0.0, "end": 5.0})

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.timeline_module.Clip, "filter", return_value=[existing_clip])
            )
            stack.enter_context(
                patch.object(self.timeline_module.Transition, "filter", return_value=[])
            )
            details = self.timeline_module.TimelineView._find_missing_transition_details(
                types.SimpleNamespace(),
                clip_data,
            )

        self.assertEqual(
            details,
            {"position": 4.0, "layer": 1, "start": 0.0, "end": 1.0},
        )

    def test_find_missing_transition_details_ignores_existing_transition(self):
        clip_data = {"id": "B", "layer": 1, "position": 4.0, "start": 0.0, "end": 6.0}
        existing_clip = types.SimpleNamespace(data={"id": "A", "position": 0.0, "start": 0.0, "end": 5.0})
        existing_transition = types.SimpleNamespace(data={"position": 4.0, "start": 0.0, "end": 1.0})

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.timeline_module.Clip, "filter", return_value=[existing_clip])
            )
            stack.enter_context(
                patch.object(
                    self.timeline_module.Transition,
                    "filter",
                    return_value=[existing_transition],
                )
            )
            details = self.timeline_module.TimelineView._find_missing_transition_details(
                types.SimpleNamespace(),
                clip_data,
            )

        self.assertIsNone(details)

    def test_should_refresh_waveforms_true_for_clip_payload_with_audio_data(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["clips", {"id": "C1"}],
            values={"ui": {"audio_data": [0.1, 0.2]}},
        )

        self.assertTrue(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_should_refresh_waveforms_checks_existing_clip_audio_when_payload_has_no_samples(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["clips", {"id": "C1"}],
            values={"position": 5.0},
        )
        clip = types.SimpleNamespace(data={"ui": {"audio_data": [0.5]}})

        with patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.assertTrue(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_should_refresh_waveforms_false_for_non_clip_action(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["files", {"id": "F1"}],
            values={"path": "example.mp4"},
        )

        self.assertFalse(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_should_refresh_waveforms_false_when_clip_has_no_audio_data(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["clips", {"id": "C1"}],
            values={"position": 5.0},
        )
        clip = types.SimpleNamespace(data={"ui": {"audio_data": []}})

        with patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.assertFalse(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_clip_waveform_cache_token_includes_waveform_generation_token(self):
        helper = self.make_qwidget_clip_helper()
        clip = types.SimpleNamespace(
            data={"ui": {"audio_data": [0.1, 0.2, 0.3], "waveform_token": "wf-2"}}
        )

        token = helper.clip_waveform_cache_token(clip)

        self.assertEqual(token, (3, "wf-2"))

    def test_find_missing_transition_details_ignores_tiny_overlap(self):
        clip_data = {"id": "B", "layer": 1, "position": 4.7, "start": 0.0, "end": 6.0}
        existing_clip = types.SimpleNamespace(data={"id": "A", "position": 0.0, "start": 0.0, "end": 5.0})

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.timeline_module.Clip, "filter", return_value=[existing_clip])
            )
            stack.enter_context(
                patch.object(self.timeline_module.Transition, "filter", return_value=[])
            )
            details = self.timeline_module.TimelineView._find_missing_transition_details(
                types.SimpleNamespace(),
                clip_data,
            )

        self.assertIsNone(details)

    def test_resolve_source_frame_uses_linear_trim_without_time_curve(self):
        clip = types.SimpleNamespace(
            data={
                "start": 2.0,
                "time": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR}]},
            }
        )

        frame = self.clip_paint_module.resolve_source_frame(
            clip,
            clip_time_seconds=3.0,
            clip_fps=24.0,
        )

        self.assertEqual(frame, 73)

    def test_resolve_source_frame_honors_time_keyframes_for_freeze(self):
        clip = types.SimpleNamespace(
            data={
                "start": 0.0,
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 25, "Y": 25}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 49, "Y": 25}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 73, "Y": 49}, "interpolation": openshot.LINEAR},
                    ]
                },
            }
        )

        frozen_frame = self.clip_paint_module.resolve_source_frame(
            clip,
            clip_time_seconds=1.5,
            clip_fps=24.0,
        )
        resumed_frame = self.clip_paint_module.resolve_source_frame(
            clip,
            clip_time_seconds=2.5,
            clip_fps=24.0,
        )

        self.assertEqual(frozen_frame, 25)
        self.assertEqual(resumed_frame, 37)

    def test_resolve_source_frame_converts_project_time_curve_to_reader_frames(self):
        clip = types.SimpleNamespace(
            data={
                "start": 0.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 52.2, "video_length": 1252},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1566}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 1567, "Y": 1}, "interpolation": openshot.LINEAR},
                    ]
                },
            }
        )

        start_frame = self.clip_paint_module.resolve_source_frame(
            clip,
            clip_time_seconds=0.0,
            clip_fps=24.0,
            project_fps=30.0,
        )
        middle_frame = self.clip_paint_module.resolve_source_frame(
            clip,
            clip_time_seconds=19.833333,
            clip_fps=24.0,
            project_fps=30.0,
        )
        end_frame = self.clip_paint_module.resolve_source_frame(
            clip,
            clip_time_seconds=49.583333,
            clip_fps=24.0,
            project_fps=30.0,
        )

        self.assertEqual(start_frame, 1252)
        self.assertEqual(middle_frame, 777)
        self.assertEqual(end_frame, 64)

    def test_volume_triggered_refreshes_waveforms_for_visible_waveform_clips(self):
        helper = self.make_time_helper()
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "id": "C1",
                "start": 0.0,
                "end": 4.0,
                "duration": 4.0,
                "volume": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": openshot.LINEAR}]},
                "ui": {"audio_data": [0.1, 0.2, 0.3]},
            },
        )
        app = types.SimpleNamespace(
            project={"fps": {"num": 24, "den": 1}},
            updates=types.SimpleNamespace(transaction_id=None),
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module.Clip, "get", return_value=clip))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            self.timeline_module.TimelineView.Volume_Triggered(
                helper,
                self.timeline_module.MenuVolume.LEVEL,
                [clip.id],
                "Entire Clip",
                75,
                transaction_id="tx-vol-1",
            )

        self.assertIn(
            {"waveform_refresh": [clip.id], "transaction_id": "tx-vol-1"},
            helper.updated,
        )

    def test_finalize_keyframe_drag_refreshes_waveform_for_volume_curve_changes(self):
        helper = self.make_finalize_keyframe_helper()
        original = {
            "id": "C1",
            "volume": {"Points": [{"co": {"X": 1, "Y": 1.0}}]},
            "ui": {"audio_data": [0.1, 0.2]},
        }
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "id": "C1",
                "volume": {"Points": [{"co": {"X": 10, "Y": 1.0}}]},
                "ui": {"audio_data": [0.1, 0.2]},
            },
            save=lambda: None,
        )
        helper.keyframe_drag_original["C1"] = copy.deepcopy(original)
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(
                transaction_id=None,
                ignore_history=False,
                apply_last_action_to_history=lambda *_args, **_kwargs: None,
            )
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module.Clip, "get", return_value=clip))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            self.timeline_module.TimelineView.FinalizeKeyframeDrag(helper, "clip", "C1")

        self.assertIn(
            {"waveform_refresh": ["C1"], "transaction_id": "tx-kf-1"},
            helper.updated,
        )

    def test_finalize_keyframe_drag_does_not_refresh_waveform_for_non_volume_changes(self):
        helper = self.make_finalize_keyframe_helper()
        original = {
            "id": "C1",
            "volume": {"Points": [{"co": {"X": 1, "Y": 1.0}}]},
            "alpha": {"Points": [{"co": {"X": 1, "Y": 1.0}}]},
            "ui": {"audio_data": [0.1, 0.2]},
        }
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "id": "C1",
                "volume": {"Points": [{"co": {"X": 1, "Y": 1.0}}]},
                "alpha": {"Points": [{"co": {"X": 10, "Y": 1.0}}]},
                "ui": {"audio_data": [0.1, 0.2]},
            },
            save=lambda: None,
        )
        helper.keyframe_drag_original["C1"] = copy.deepcopy(original)
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(
                transaction_id=None,
                ignore_history=False,
                apply_last_action_to_history=lambda *_args, **_kwargs: None,
            )
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module.Clip, "get", return_value=clip))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            self.timeline_module.TimelineView.FinalizeKeyframeDrag(helper, "clip", "C1")

        self.assertEqual(helper.updated, [])

    def test_qwidget_keyframe_move_keeps_drag_preview_local_until_release(self):
        helper = self.make_qwidget_keyframe_drag_helper()
        event = types.SimpleNamespace(pos=lambda: QPointF(120.0, 0.0))

        self.qwidget_keyframe_module.KeyframeMixin._keyframeMove(helper, event)

        self.assertEqual(helper.begin_calls, 0)
        self.assertEqual(helper.apply_calls, [])
        self.assertTrue(helper.panel_preview_calls)
        self.assertEqual(helper.seek_calls, [(121, False)])
        self.assertTrue(helper._dragging_keyframe["moved"])
        self.assertTrue(helper._keyframes_dirty)
        self.assertEqual(helper.update_calls, 1)

    def test_qwidget_keyframe_finish_commits_once_after_preview_drag(self):
        helper = self.make_qwidget_keyframe_drag_helper()
        helper._dragging_keyframe["pending_frame"] = 121
        helper._dragging_keyframe["pending_seconds"] = 5.0
        helper._dragging_keyframe["moved"] = True

        self.qwidget_keyframe_module.KeyframeMixin._finishKeyframeDrag(helper)

        self.assertEqual(helper.begin_calls, 1)
        self.assertEqual(helper.apply_calls, [(False, True)])
        self.assertEqual(helper.finalize_calls, [("clip", "C1")])
        self.assertEqual(helper.seek_calls, [(121, True)])
        self.assertIsNone(helper._dragging_keyframe)
        self.assertFalse(helper.mouse_dragging)
        self.assertEqual(helper.release_calls, 1)

    def test_qwidget_cursor_uses_razor_cursor_for_items_when_enabled(self):
        helper = self.make_qwidget_cursor_helper()
        helper.enable_razor = True
        helper.geometry.items = [(QRectF(0.0, 0.0, 100.0, 20.0), object(), False, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._updateCursor(helper, QPointF(10.0, 10.0))

        self.assertIs(helper.cursor_value, helper.cursors["razor"])
        self.assertFalse(helper.unset_cursor_called)

    def test_qwidget_cursor_keeps_hand_cursor_for_items_when_razor_disabled(self):
        helper = self.make_qwidget_cursor_helper()
        helper.geometry.items = [(QRectF(0.0, 0.0, 100.0, 20.0), object(), False, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._updateCursor(helper, QPointF(10.0, 10.0))

        self.assertIs(helper.cursor_value, helper.cursors["hand"])
        self.assertFalse(helper.unset_cursor_called)

    def test_reset_drag_preview_refreshes_cursor_for_stationary_pointer(self):
        helper = self.make_qwidget_cursor_helper()
        helper._drag_preview_items = [object()]
        helper._drag_payload = {"type": "clip"}
        helper.item_ids = ["C1"]
        helper.new_item = True
        helper.item_type = "clip"
        helper.drag_bbox = QRectF(0.0, 0.0, 50.0, 20.0)
        helper.update_called = 0

        def update():
            helper.update_called += 1

        helper.update = update
        helper.mapFromGlobal = lambda pos: QPointF(float(pos.x()), float(pos.y()))
        helper.rect = lambda: QRectF(0.0, 0.0, 200.0, 100.0)
        helper._set_drag_preview_thumbnail_suspension = lambda _enabled: None
        helper.geometry.items = [(QRectF(0.0, 0.0, 100.0, 20.0), object(), False, "clip")]

        with patch.object(self.qwidget_base_module.QCursor, "pos", return_value=QPointF(10.0, 10.0)):
            self.qwidget_base_module.TimelineWidgetBase._reset_drag_preview(helper)

        self.assertEqual(helper._drag_preview_items, [])
        self.assertIsNone(helper._drag_payload)
        self.assertEqual(helper.item_ids, [])
        self.assertFalse(helper.new_item)
        self.assertIsNone(helper.item_type)
        self.assertEqual(helper.drag_bbox, QRectF())
        self.assertEqual(helper.update_called, 1)
        self.assertIs(helper.cursor_value, helper.cursors["hand"])
        self.assertFalse(helper.unset_cursor_called)

    def test_slice_triggered_keep_both_splits_transition_and_updates_duration(self):
        helper = self.make_slice_helper()
        left_transition = types.SimpleNamespace(
            id="T1",
            type="update",
            key=["effects", {"id": "T1"}],
            data={"id": "T1", "position": 10.0, "layer": 2, "start": 0.0, "end": 4.0, "duration": 4.0},
        )
        right_transition = types.SimpleNamespace(
            id="T1",
            type="update",
            key=["effects", {"id": "T1"}],
            data={"id": "T1", "position": 10.0, "layer": 2, "start": 0.0, "end": 4.0, "duration": 4.0},
        )
        saved_right = []
        right_transition.save = lambda: saved_right.append(copy.deepcopy(right_transition.data))
        left_transition.save = lambda: None
        app = types.SimpleNamespace(
            project=types.SimpleNamespace(
                get=lambda key: {"fps": {"num": 24, "den": 1}, "layers": []}[key]
            ),
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(
                IgnoreUpdates=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)
            ),
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            stack.enter_context(patch.object(self.timeline_module.Clip, "get", return_value=None))
            stack.enter_context(
                patch.object(
                    self.timeline_module.Transition,
                    "get",
                    side_effect=[left_transition, right_transition],
                )
            )
            self.timeline_module.TimelineView.Slice_Triggered(
                helper,
                self.timeline_module.MenuSlice.KEEP_BOTH,
                [],
                ["T1"],
                12.0,
            )

        self.assertEqual(helper.updated_transitions, [{"id": "T1", "position": 10.0, "layer": 2, "start": 0.0, "end": 2.0, "duration": 2.0}])
        self.assertEqual(saved_right, [{"position": 12.0, "layer": 2, "start": 2.0, "end": 4.0, "duration": 2.0}])

    def test_slice_triggered_keep_right_updates_transition_duration(self):
        helper = self.make_slice_helper()
        transition = types.SimpleNamespace(
            id="T1",
            type="update",
            key=["effects", {"id": "T1"}],
            data={"id": "T1", "position": 10.0, "layer": 2, "start": 0.0, "end": 4.0, "duration": 4.0},
            save=lambda: None,
        )
        app = types.SimpleNamespace(
            project=types.SimpleNamespace(
                get=lambda key: {"fps": {"num": 24, "den": 1}, "layers": []}[key]
            ),
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(
                IgnoreUpdates=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)
            ),
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            stack.enter_context(patch.object(self.timeline_module.Clip, "get", return_value=None))
            stack.enter_context(
                patch.object(self.timeline_module.Transition, "get", return_value=transition)
            )
            self.timeline_module.TimelineView.Slice_Triggered(
                helper,
                self.timeline_module.MenuSlice.KEEP_RIGHT,
                [],
                ["T1"],
                12.0,
            )

        self.assertEqual(
            helper.updated_transitions,
            [{"id": "T1", "position": 12.0, "layer": 2, "start": 2.0, "end": 4.0, "duration": 2.0}],
        )

    def test_qwidget_panel_keyframe_move_keeps_updates_off_timeline(self):
        helper = self.make_qwidget_panel_keyframe_drag_helper()
        event = types.SimpleNamespace(pos=lambda: QPointF(120.0, 0.0))

        self.qwidget_keyframe_panel_module.KeyframePanelMixin._panel_keyframe_move(helper, event)

        self.assertEqual(helper.update_property_calls, 1)
        self.assertEqual(helper.begin_calls, 0)
        self.assertEqual(helper.apply_calls, [])
        self.assertEqual(helper.seek_calls, [(121, False)])
        self.assertTrue(helper._dragging_panel_keyframes["moved"])
        self.assertTrue(helper._keyframes_dirty)
        self.assertEqual(helper.update_calls, 1)

    def test_qwidget_panel_keyframe_finish_commits_once_after_preview_drag(self):
        helper = self.make_qwidget_panel_keyframe_drag_helper()
        helper._dragging_panel_keyframes["moved"] = True
        helper._dragging_panel_keyframes["entries"][0]["pending_frame"] = 121
        helper._dragging_panel_keyframes["entries"][0]["pending_seconds"] = 5.0

        self.qwidget_keyframe_panel_module.KeyframePanelMixin._finish_panel_keyframe_drag(helper)

        self.assertEqual(helper.begin_calls, 1)
        self.assertEqual(helper.apply_calls, [(False, True)])
        self.assertEqual(helper.finalize_calls, [("clip", "C1")])
        self.assertEqual(helper.seek_calls, [(121, True)])
        self.assertIsNone(helper._dragging_panel_keyframes)
        self.assertFalse(helper.mouse_dragging)
        self.assertEqual(helper.release_calls, 1)

    def test_frame_rounding_increment_caps_to_nearby_frames(self):
        painter = self.make_clip_painter(project_fps=30.0)

        wide_increment = painter._frame_rounding_increment(30.0, 9.917)
        medium_increment = painter._frame_rounding_increment(24.0, 2.0)
        zoomed_increment = painter._frame_rounding_increment(24.0, 0.02)

        self.assertEqual(wide_increment, 8)
        self.assertEqual(medium_increment, 6)
        self.assertEqual(zoomed_increment, 1)

    def test_timing_resize_preview_stretches_cached_clip_render(self):
        painter, clip, full_rect, segment_rect = self.make_timing_preview_painter()

        result = painter._clip_pixmap(full_rect, segment_rect, clip)

        self.assertIsNotNone(result)
        pix, blur, icons, pending, text_entry = result
        self.assertEqual(blur, 0.0)
        self.assertEqual(pix.width(), 144)
        self.assertEqual(pix.height(), 40)
        self.assertEqual(icons, [])
        self.assertFalse(pending)
        self.assertIsNone(text_entry)

    def test_timing_resize_preview_preserves_logical_height_on_hidpi_pixmaps(self):
        painter, clip, full_rect, segment_rect = self.make_timing_preview_painter(current_width=144.0)
        hidpi_pix = self.clip_paint_module.QPixmap(144, 80)
        hidpi_pix.fill(QColor("green"))
        hidpi_pix.setDevicePixelRatio(2.0)
        painter._retime_preview_cache["C1"] = {"pix": hidpi_pix, "blur": 0.0}

        result = painter._clip_pixmap(full_rect, segment_rect, clip)

        self.assertIsNotNone(result)
        pix = result[0]
        logical_w, logical_h = painter.logical_size(pix)
        self.assertEqual((logical_w, logical_h), (144.0, 40.0))

    def test_timing_resize_preview_freezes_thumbnail_generation_for_all_styles(self):
        for style in ("entire", "start", "start-end"):
            with self.subTest(style=style):
                painter, clip, full_rect, segment_rect = self.make_timing_preview_painter(
                    thumbnail_style=style,
                    current_width=168.0,
                )

                def fail_draw_contents(*_args, **_kwargs):
                    raise AssertionError("thumbnail contents should not be regenerated during timing resize")

                painter._draw_clip_contents = types.MethodType(fail_draw_contents, painter)
                result = painter._clip_pixmap(full_rect, segment_rect, clip)

                self.assertIsNotNone(result)

    def test_waveform_time_curve_generation_still_applies_volume_curve(self):
        captured = []
        file_obj = types.SimpleNamespace(
            id="F1",
            data={
                "id": "F1",
                "path": "/tmp/example.wav",
                "has_audio": True,
                "ui": {"audio_data": [1.0, 1.0, 1.0, 1.0, 1.0]},
            },
        )
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "id": "C1",
                "file_id": "F1",
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 5, "Y": 5}, "interpolation": openshot.LINEAR},
                    ]
                },
                "channel_filter": {"Points": [{"co": {"X": 1, "Y": -1}}]},
            },
        )
        clip_instance = types.SimpleNamespace(
            info=types.SimpleNamespace(duration=0.2, video_length=4, fps=types.SimpleNamespace(num=24, den=1)),
            time=types.SimpleNamespace(GetCount=lambda: 2, GetValue=lambda frame: frame),
            volume=types.SimpleNamespace(GetValue=lambda frame: 0.5),
        )
        app = types.SimpleNamespace(
            window=types.SimpleNamespace(
                timeline_sync=types.SimpleNamespace(
                    timeline=types.SimpleNamespace(GetClip=lambda clip_id: clip_instance)
                ),
                timeline=types.SimpleNamespace(
                    fileAudioDataReady=types.SimpleNamespace(emit=lambda *args, **kwargs: None),
                    clipAudioDataReady=types.SimpleNamespace(
                        emit=lambda clip_id, ui_data, tid: captured.append((clip_id, ui_data, tid))
                    ),
                ),
            ),
            setOverrideCursor=lambda *_args, **_kwargs: None,
            restoreOverrideCursor=lambda *_args, **_kwargs: None,
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.waveform_module.File, "get", return_value=file_obj))
            stack.enter_context(patch.object(self.waveform_module.Clip, "get", return_value=clip))
            stack.enter_context(patch.object(self.waveform_module, "get_app", return_value=app))
            stack.enter_context(patch.object(self.waveform_module, "project_fps_fraction", return_value=(24, 1)))
            stack.enter_context(patch.object(self.waveform_module, "video_length_to_project_frames", return_value=4))
            self.waveform_module.get_waveform_thread("F1", ["C1"], "wf-time-1")

        self.assertTrue(captured)
        self.assertEqual(captured[-1][0], "C1")
        self.assertEqual(captured[-1][2], "wf-time-1")
        self.assertEqual(captured[-1][1]["ui"]["audio_data"], [0.5, 0.5, 0.5, 0.5])

    def test_clip_audio_data_ready_preserves_existing_waveform_when_pending_samples_are_none(self):
        helper = types.SimpleNamespace(
            clip_painter=types.SimpleNamespace(clear_cache=lambda: None),
            update=lambda: None,
            get_uuid=lambda: "wf-new",
        )
        clip = types.SimpleNamespace(
            id="C1",
            data={"ui": {"audio_data": [0.2, 0.4], "waveform_token": "wf-old"}},
            save=lambda: None,
        )
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(
                actionClearWaveformData=types.SimpleNamespace(setEnabled=lambda _value: None)
            ),
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module.Clip, "get", return_value=clip))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            stack.enter_context(patch.object(self.timeline_module.QTimer, "singleShot", side_effect=lambda *_args, **_kwargs: None))
            self.timeline_module.TimelineView.clipAudioDataReady_Triggered(
                helper,
                "C1",
                {"ui": {"audio_data": None}},
                "wf-pending-1",
            )

        self.assertEqual(clip.data["ui"]["audio_data"], [0.2, 0.4])
        self.assertEqual(clip.data["ui"]["waveform_token"], "wf-old")

    def test_draw_thumbnails_entire_style_uses_expected_linear_frames(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
            },
        )

        frames = self.collect_thumbnail_frames(clip)

        self.assertEqual(frames, [1, 25, 72])

    def test_draw_thumbnails_entire_style_freeze_curve_maps_to_reader_frames(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 25, "Y": 25}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 49, "Y": 25}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 73, "Y": 49}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(clip)

        self.assertEqual(frames, [1, 25, 48])

    def test_draw_thumbnails_entire_style_reverse_curve_uses_reversed_reader_frames(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 72}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 73, "Y": 1}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(clip)

        self.assertEqual(frames, [72, 48, 2])

    def test_draw_thumbnails_entire_style_reverse_curve_with_trimmed_start_uses_trimmed_reader_frames(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 1.0,
                "end": 4.0,
                "duration": 3.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 10.0},
                "time": {
                    "Points": [
                        {"co": {"X": 25, "Y": 96}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 97, "Y": 25}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(clip)

        self.assertEqual(frames, [96, 49, 26])

    def test_draw_thumbnails_entire_style_reverse_curve_uses_reader_frame_range_in_mixed_fps_project(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 52.2,
                "duration": 52.2,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 52.2, "video_length": 1252},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1566}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 1567, "Y": 1}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(
            clip,
            duration=52.2,
            inner_width=345.6,
            pixels_per_second=(345.6 / 52.2),
            project_fps=30.0,
        )

        self.assertEqual(frames[:2], [1252, 1169])
        self.assertEqual(frames, sorted(frames, reverse=True))
        self.assertTrue(all(1 <= frame <= 1252 for frame in frames))

    def test_draw_thumbnails_entire_style_mixed_fps_reverse_curve_returns_reader_frames(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 52.2,
                "duration": 52.2,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 52.2, "video_length": 1252},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1566}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 1567, "Y": 1}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(
            clip,
            duration=52.2,
            inner_width=396.6,
            pixels_per_second=(396.6 / 52.2),
            project_fps=30.0,
        )

        self.assertEqual(frames, [1252, 1025, 875, 719, 570, 420, 264, 114, 2])

    def test_draw_thumbnails_entire_style_long_retimed_clip_generates_tail_slots(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 400.0,
                "duration": 400.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0, "video_length": 72},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 9601, "Y": 72}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(
            clip,
            duration=400.0,
            inner_width=9600.0,
            pixels_per_second=24.0,
            project_fps=24.0,
        )

        self.assertGreater(len(frames), 150)
        self.assertEqual(frames[-1], 72)

    def test_build_thumbnail_slots_entire_style_keeps_world_anchored_partial_tail(self):
        painter = self.make_clip_painter(thumbnail_style="entire", pixels_per_second=24.0, project_fps=24.0)
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 1.7,
                "end": 8.2,
                "duration": 6.5,
                "position": 0.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 20.0},
            },
        )
        clip_duration = 6.5
        inner = self.clip_paint_module.QRectF(0.0, 0.0, clip_duration * 24.0, 40.0)
        segment = {
            "offset_seconds": 0.0,
            "duration_seconds": clip_duration,
            "clip_duration": clip_duration,
            "segment_width": clip_duration * 24.0,
            "clip_width": clip_duration * 24.0,
            "includes_start": True,
            "includes_end": True,
        }
        timing = painter._segment_timing(segment, clip_duration)

        slots, interval = painter._build_thumbnail_slots(clip, inner, segment, "entire", timing)
        starts = [round(float(slot_start), 3) for slot_start, _ in slots]

        self.assertEqual(interval, 2.0)
        self.assertIn(6.3, starts)
        self.assertNotIn(4.5, starts)

    def test_build_thumbnail_slots_entire_style_time_stretch_keeps_tail_slots_past_raw_media_end(self):
        painter = self.make_clip_painter(thumbnail_style="entire", pixels_per_second=24.0, project_fps=24.0)
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 8.0,
                "end": 18.0,
                "duration": 10.0,
                "position": 0.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 12.0, "video_length": 288},
                "time": {
                    "Points": [
                        {"co": {"X": 193, "Y": 193}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 433, "Y": 288}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )
        clip_duration = 10.0
        inner = self.clip_paint_module.QRectF(0.0, 0.0, clip_duration * 24.0, 40.0)
        segment = {
            "offset_seconds": 0.0,
            "duration_seconds": clip_duration,
            "clip_duration": clip_duration,
            "segment_width": clip_duration * 24.0,
            "clip_width": clip_duration * 24.0,
            "includes_start": True,
            "includes_end": True,
        }
        timing = painter._segment_timing(segment, clip_duration)

        slots, interval = painter._build_thumbnail_slots(clip, inner, segment, "entire", timing)
        starts = [round(float(slot_start), 3) for slot_start, _ in slots]

        self.assertEqual(interval, 2.0)
        self.assertIn(8.0, starts)

    def test_draw_thumbnails_start_style_reverse_curve_uses_last_reader_frame(self):
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 72}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 73, "Y": 1}, "interpolation": openshot.LINEAR},
                    ]
                },
            },
        )

        frames = self.collect_thumbnail_frames(clip, thumbnail_style="start")

        self.assertEqual(frames, [72])

    def test_draw_thumbnails_entire_style_trim_preview_keeps_static_center_samples(self):
        painter = self.make_clip_painter(thumbnail_style="entire", pixels_per_second=24.0, project_fps=24.0)
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.5,
                "end": 2.5,
                "duration": 2.0,
                "position": 0.5,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
            },
        )
        painter.w._pending_clip_overrides = {
            "C1": {
                "start": 0.5,
                "end": 2.5,
                "position": 0.5,
                "initial_start": 0.0,
                "initial_end": 3.0,
                "initial_position": 0.0,
                "scale": False,
            }
        }
        painter.w._resizing_item = clip
        painter.w._press_hit = "clip-edge"
        painter.w.clip_has_pending_override = lambda candidate: getattr(candidate, "id", None) == "C1"
        cached = self.clip_paint_module.QPixmap(72, 40)
        cached.fill(QColor("yellow"))
        painter._retime_preview_cache["C1"] = {"pix": cached, "blur": 0.0}

        drawn = []

        class FakePainter:
            def save(self):
                pass

            def restore(self):
                pass

            def setClipRect(self, rect, mode):
                drawn.append(("clip", rect, mode))

            def drawPixmap(self, offset, pix):
                drawn.append(("pix", offset, pix))

            def setBrush(self, *_args, **_kwargs):
                pass

            def setPen(self, *_args, **_kwargs):
                pass

            def setRenderHint(self, *_args, **_kwargs):
                pass

            def drawPath(self, *_args, **_kwargs):
                pass

            def drawRoundedRect(self, *_args, **_kwargs):
                pass

            def drawRect(self, *_args, **_kwargs):
                pass

        painter._draw_clip(FakePainter(), self.clip_paint_module.QRectF(12, 0, 48, 40), self.clip_paint_module.QRectF(12, 0, 48, 40), clip, None, False)

        pix_call = next(item for item in drawn if item[0] == "pix")
        offset = pix_call[1]
        self.assertEqual(offset.x(), 0.0)

    def test_trim_preview_freezes_edge_thumbnail_styles(self):
        for style in ("start", "start-end"):
            with self.subTest(style=style):
                painter = self.make_clip_painter(
                    thumbnail_style=style,
                    pixels_per_second=24.0,
                    project_fps=24.0,
                )
                clip = types.SimpleNamespace(
                    id="C1",
                    data={
                        "file_id": "F1",
                        "start": 0.5,
                        "end": 2.5,
                        "duration": 2.0,
                        "position": 0.5,
                        "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
                    },
                )
                painter.w._pending_clip_overrides = {
                    "C1": {
                        "start": 0.5,
                        "end": 2.5,
                        "position": 0.5,
                        "initial_start": 0.0,
                        "initial_end": 3.0,
                        "initial_position": 0.0,
                        "scale": False,
                    }
                }
                painter.w._resizing_item = clip
                painter.w._press_hit = "clip-edge"
                painter.w.clip_has_pending_override = (
                    lambda candidate: getattr(candidate, "id", None) == "C1"
                )
                cached = self.clip_paint_module.QPixmap(72, 40)
                cached.fill(QColor("yellow"))
                painter._retime_preview_cache["C1"] = {"pix": cached, "blur": 0.0}

                def fail_clip_pixmap(*_args, **_kwargs):
                    raise AssertionError(
                        "edge thumbnail styles should not regenerate during trim"
                    )

                painter._clip_pixmap = types.MethodType(fail_clip_pixmap, painter)

                class FakePainter:
                    def save(self):
                        pass

                    def restore(self):
                        pass

                    def setClipRect(self, *_args, **_kwargs):
                        pass

                    def drawPixmap(self, *_args, **_kwargs):
                        pass

                    def setBrush(self, *_args, **_kwargs):
                        pass

                    def setPen(self, *_args, **_kwargs):
                        pass

                    def setRenderHint(self, *_args, **_kwargs):
                        pass

                    def drawPath(self, *_args, **_kwargs):
                        pass

                    def drawRoundedRect(self, *_args, **_kwargs):
                        pass

                    def drawRect(self, *_args, **_kwargs):
                        pass

                painter._draw_clip(
                    FakePainter(),
                    self.clip_paint_module.QRectF(12, 0, 48, 40),
                    self.clip_paint_module.QRectF(12, 0, 48, 40),
                    clip,
                    None,
                    False,
                )

    def test_clip_pixmap_preserves_partial_thumbnail_render_for_trim_freeze(self):
        painter = self.make_clip_painter(
            thumbnail_style="entire",
            pixels_per_second=24.0,
            project_fps=24.0,
        )
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "position": 0.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 3.0},
            },
        )

        def fake_draw_contents(_self, _painter, _clip, _inner, _segment):
            return [], True, None

        painter._draw_clip_contents = types.MethodType(fake_draw_contents, painter)
        full_rect = self.clip_paint_module.QRectF(0.0, 0.0, 72.0, 40.0)
        segment_rect = self.clip_paint_module.QRectF(0.0, 0.0, 72.0, 40.0)

        result = painter._clip_pixmap(full_rect, segment_rect, clip)

        self.assertIsNotNone(result)
        self.assertTrue(result[3])
        self.assertIn("C1", painter._retime_preview_cache)
        cached = painter._retime_preview_cache["C1"]
        self.assertIsInstance(cached.get("pix"), self.clip_paint_module.QPixmap)
        self.assertFalse(cached.get("pix").isNull())

    def test_invalidate_clip_thumbnails_can_preserve_trim_preview_cache(self):
        painter = self.make_clip_painter()
        cached = self.clip_paint_module.QPixmap(72, 40)
        cached.fill(QColor("yellow"))
        painter._retime_preview_cache["C1"] = {"pix": cached, "blur": 0.0}

        painter.invalidate_clip_thumbnails(
            "C1",
            drop_cache=False,
            drop_pending=True,
            drop_fallback=False,
            drop_preview=False,
            invalidate_render_cache=False,
        )

        self.assertIn("C1", painter._retime_preview_cache)

    def test_compute_clip_resize_timing_left_edge_allows_growth_past_timeline_zero(self):
        helper = self.make_qwidget_clip_helper()
        helper.enable_timing = True
        helper._resize_edge = "left"
        helper._last_event = types.SimpleNamespace(pos=lambda: types.SimpleNamespace(x=lambda: -48.0))
        helper._resize_initial_rect = self.clip_paint_module.QRectF(24.0, 0.0, 72.0, 40.0)
        helper._resize_initial_world_rect = self.clip_paint_module.QRectF(24.0, 0.0, 72.0, 40.0)
        helper._resize_initial = {
            "start": 0.0,
            "end": 3.0,
            "position": 1.0,
            "duration": 3.0,
        }

        rect, start, end, position = helper._compute_clip_resize(types.SimpleNamespace())

        self.assertEqual(position, -2.0)
        self.assertEqual(start, -3.0)
        self.assertEqual(end, 3.0)
        self.assertEqual(rect.x(), -48.0)
        self.assertEqual(rect.width(), 144.0)

    def test_clip_reader_duration_uses_time_curve_domain_when_longer_than_reader(self):
        helper = self.make_qwidget_clip_helper()
        helper.fps_float = 30.0
        clip = types.SimpleNamespace(
            data={
                "start": 2.0,
                "end": 7.0,
                "duration": 5.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 8.0, "video_length": 192},
                "time": {
                    "Points": [
                        {"co": {"X": 61, "Y": 61}},
                        {"co": {"X": 361, "Y": 210}},
                    ]
                },
            }
        )

        self.assertEqual(helper._clip_reader_duration_seconds(clip), 12.0)

    def test_compute_clip_resize_non_timing_right_edge_can_expand_to_time_curve_duration(self):
        helper = self.make_qwidget_clip_helper()
        helper.enable_timing = False
        helper._resize_edge = "right"
        helper._last_event = types.SimpleNamespace(pos=lambda: types.SimpleNamespace(x=lambda: 288.0))
        helper._resize_initial_rect = self.clip_paint_module.QRectF(0.0, 0.0, 120.0, 40.0)
        helper._resize_initial_world_rect = self.clip_paint_module.QRectF(0.0, 0.0, 120.0, 40.0)
        helper._resize_initial = {
            "start": 2.0,
            "end": 7.0,
            "position": 0.0,
            "duration": 5.0,
        }
        helper._resize_clip_max_duration = 12.0

        rect, start, end, position = helper._compute_clip_resize(types.SimpleNamespace())

        self.assertEqual(start, 2.0)
        self.assertEqual(end, 12.0)
        self.assertEqual(position, 0.0)
        self.assertEqual(rect.width(), 240.0)

    def test_thumbnail_worker_sorts_requests_and_reuses_clip_instance(self):
        worker = self.thumbnails_module._ThumbnailWorker()
        ready = []
        worker.thumbnail_ready.connect(lambda clip_id, frame, path, generation: ready.append((clip_id, frame, path, generation)))
        scheduled = []
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.thumbnails_module, "GetThumbPath", side_effect=lambda file_id, frame: f"{file_id}:{frame}")
            )
            stack.enter_context(
                patch.object(self.thumbnails_module.QTimer, "singleShot", side_effect=lambda _delay, callback: scheduled.append(callback))
            )
            worker.request_thumbnail("C1", "F1", 400, 1)
            worker.request_thumbnail("C1", "F1", 100, 1)
            worker.request_thumbnail("C1", "F1", 300, 1)
            self.assertEqual(len(scheduled), 1)
            scheduled[0]()

        self.assertEqual([item[1] for item in ready], [100, 300, 400])
        self.assertEqual([item[2] for item in ready], ["F1:100", "F1:300", "F1:400"])
