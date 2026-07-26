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
import math
import os
import sys
import types
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import openshot


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QCoreApplication, QPointF, QRectF, Qt
from qt_api import QColor, QCursor, QImage, QPainter
from qt_api import QApplication
from classes import info
from classes.updates import UpdateAction
from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
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
        sys.modules.pop("windows.views.timeline", None)
        cls.timeline_module = importlib.import_module("windows.views.timeline")
        cls.qwidget_base_module = importlib.import_module("windows.views.timeline_backend.qwidget.base")
        cls.geometry_base_module = importlib.import_module("windows.views.timeline_backend.geometry.base")
        cls.geometry_clip_module = importlib.import_module("windows.views.timeline_backend.geometry.clip")
        cls.geometry_transition_module = importlib.import_module("windows.views.timeline_backend.geometry.transition")
        cls.clip_paint_module = importlib.import_module("windows.views.timeline_backend.paint.clip")
        cls.cache_paint_module = importlib.import_module("windows.views.timeline_backend.paint.cache")
        cls.ruler_paint_module = importlib.import_module("windows.views.timeline_backend.paint.ruler")
        cls.transition_paint_module = importlib.import_module("windows.views.timeline_backend.paint.transition")
        cls.qwidget_clip_module = importlib.import_module("windows.views.timeline_backend.qwidget.clip")
        cls.qwidget_transition_module = importlib.import_module("windows.views.timeline_backend.qwidget.transition")
        cls.qwidget_keyframe_module = importlib.import_module("windows.views.timeline_backend.qwidget.keyframe")
        cls.qwidget_keyframe_panel_module = importlib.import_module("windows.views.timeline_backend.qwidget.keyframe_panel")
        cls.qwidget_timecode_module = importlib.import_module("windows.views.timeline_backend.qwidget.timecode")
        cls.thumbnails_module = importlib.import_module("windows.views.timeline_backend.qwidget.thumbnails")
        cls.waveform_module = importlib.import_module("classes.waveform")
        cls.humanity_theme_module = importlib.import_module("themes.humanity.styles")
        cls.cosmic_theme_module = importlib.import_module("themes.cosmic.styles")

    def make_helper(self):
        timeline_module = self.timeline_module

        class Helper:
            def __init__(self):
                self.updated = []

            def update_clip_data(self, clip_data, **kwargs):
                self.updated.append((copy.deepcopy(clip_data), dict(kwargs)))

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

    def make_layout_clip(self, clip_id, position=0.0):
        def kf(value):
            return {"Points": [{"co": {"X": 1, "Y": value}, "interpolation": openshot.BEZIER}]}

        return types.SimpleNamespace(
            id=clip_id,
            data={
                "id": clip_id,
                "position": position,
                "scale": openshot.SCALE_FIT,
                "gravity": openshot.GRAVITY_CENTER,
                "scale_x": kf(1.0),
                "scale_y": kf(1.0),
                "location_x": kf(0.0),
                "location_y": kf(0.0),
            },
        )

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def test_timecode_editor_parses_blank_and_zero_as_timeline_start(self):
        edit = self.qwidget_timecode_module.TimecodeLineEdit()
        edit.set_context(30, 1, 31)

        self.assertEqual(edit.parse_text(""), 1)
        self.assertEqual(edit.parse_text("0"), 1)
        self.assertEqual(edit.parse_text("00:00:00,00"), 1)
        self.assertIsNone(edit.parse_text("bad"))

    def test_show_all_clips_maintain_ratio_uses_uniform_scale(self):
        helper = self.make_helper()
        clips = [self.make_layout_clip("C1"), self.make_layout_clip("C2")]

        with patch.object(self.timeline_module, "Clip", types.SimpleNamespace(filter=lambda: clips)):
            self.timeline_module.TimelineView.show_all_clips(helper, clips[0], stretch=False)

        for clip in clips:
            self.assertEqual(clip.data["scale"], openshot.SCALE_FIT)
            self.assertEqual(clip.data["gravity"], openshot.GRAVITY_TOP_LEFT)
            self.assertAlmostEqual(clip.data["scale_x"]["Points"][0]["co"]["Y"], 0.5)
            self.assertAlmostEqual(clip.data["scale_y"]["Points"][0]["co"]["Y"], 0.5)
        self.assertAlmostEqual(clips[0].data["location_x"]["Points"][0]["co"]["Y"], 0.0)
        self.assertAlmostEqual(clips[1].data["location_x"]["Points"][0]["co"]["Y"], 0.5)
        self.assertEqual(len(helper.updated), 2)

    def test_show_all_clips_distort_uses_cell_width_and_height(self):
        helper = self.make_helper()
        clips = [self.make_layout_clip("C1"), self.make_layout_clip("C2")]

        with patch.object(self.timeline_module, "Clip", types.SimpleNamespace(filter=lambda: clips)):
            self.timeline_module.TimelineView.show_all_clips(helper, clips[0], stretch=True)

        for clip in clips:
            self.assertEqual(clip.data["scale"], openshot.SCALE_STRETCH)
            self.assertAlmostEqual(clip.data["scale_x"]["Points"][0]["co"]["Y"], 0.5)
            self.assertAlmostEqual(clip.data["scale_y"]["Points"][0]["co"]["Y"], 1.0)

    def test_show_all_clips_uses_selected_clip_ids_when_available(self):
        helper = self.make_helper()
        clips = [
            self.make_layout_clip("C1"),
            self.make_layout_clip("C2"),
            self.make_layout_clip("C3"),
        ]

        with patch.object(self.timeline_module, "Clip", types.SimpleNamespace(filter=lambda: clips)):
            self.timeline_module.TimelineView.show_all_clips(
                helper,
                clips[0],
                stretch=False,
                clip_ids=["C1", "C2"],
            )

        self.assertAlmostEqual(clips[0].data["location_x"]["Points"][0]["co"]["Y"], 0.0)
        self.assertAlmostEqual(clips[1].data["location_x"]["Points"][0]["co"]["Y"], 0.5)
        self.assertAlmostEqual(clips[2].data["location_x"]["Points"][0]["co"]["Y"], 0.0)
        self.assertAlmostEqual(clips[2].data["scale_x"]["Points"][0]["co"]["Y"], 1.0)
        self.assertEqual(len(helper.updated), 2)

    def test_playhead_time_edit_commit_centers_on_new_playhead_frame(self):
        helper = types.SimpleNamespace()
        helper.current_frame = 1
        helper.playhead_time_editor = None
        helper.updated = 0
        helper.seeks = []
        helper.center_calls = 0
        helper.update = lambda: setattr(helper, "updated", helper.updated + 1)
        helper._emit_playhead_seek = lambda frame, start_preroll=True, force=False: helper.seeks.append(
            (frame, start_preroll, force)
        )
        helper.centerOnPlayhead = lambda: setattr(helper, "center_calls", helper.center_calls + 1)

        self.qwidget_base_module.TimelineWidgetBase._commit_playhead_time_edit(
            helper,
            301,
            start_preroll=False,
            force=False,
        )

        self.assertEqual(helper.current_frame, 301)
        self.assertEqual(helper.updated, 1)
        self.assertEqual(helper.seeks, [(301, False, False)])
        self.assertEqual(helper.center_calls, 1)

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

    def make_motion_helper(self):
        timeline_module = self.timeline_module

        class Helper:
            def __init__(self):
                self.updated = []
                self.show_wait_spinner = False
                self.window = types.SimpleNamespace(
                    timeline_sync=types.SimpleNamespace(
                        timeline=types.SimpleNamespace(GetClip=lambda _clip_id: None)
                    ),
                    preview_thread=types.SimpleNamespace(current_frame=None),
                )

            def get_uuid(self):
                return "tx-motion-1"

            def AddPoint(self, keyframe, new_point):
                return timeline_module.TimelineView.AddPoint(self, keyframe, new_point)

            def _remove_keypoints_in_range(self, points_data, frame_start, frame_end):
                return timeline_module.TimelineView._remove_keypoints_in_range(
                    self, points_data, frame_start, frame_end)

            def update_clip_data(self, clip_data, **kwargs):
                self.updated.append((copy.deepcopy(clip_data), dict(kwargs)))

            def _get_transition_reader_json(self, path):
                return {"path": path, "has_single_image": True}

        return Helper()

    def make_motion_clip(self):
        def kf(value):
            return {"Points": [{"co": {"X": 1, "Y": value}, "interpolation": openshot.BEZIER}]}

        data = {
            "id": "C1",
            "position": 0.0,
            "start": 0.0,
            "end": 3.0,
            "scale": openshot.SCALE_FIT,
            "scale_x": kf(1.0),
            "scale_y": kf(1.0),
            "location_x": kf(0.0),
            "location_y": kf(0.0),
            "rotation": kf(0.0),
            "shear_x": kf(0.0),
            "shear_y": kf(0.0),
            "alpha": kf(1.0),
            "origin_x": kf(0.5),
            "origin_y": kf(0.5),
            "effects": [],
        }
        return types.SimpleNamespace(id="C1", data=data)

    def make_motion_app(self):
        return types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            project=types.SimpleNamespace(
                get=lambda key: {"num": 30, "den": 1} if key == "fps" else None,
                generate_id=lambda: "FX1",
            ),
        )

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

            def _snap_trim_delta(self, delta_seconds, edge=None, initial=None):
                return float(delta_seconds)

        return Helper()

    def test_waveform_window_uses_legacy_density_when_metadata_is_missing(self):
        helper = self.make_qwidget_clip_helper()
        clip = types.SimpleNamespace(data={
            "start": 0.5,
            "end": 1.5,
            "ui": {"audio_data": [0.25] * 40},
        })

        window = helper.clip_waveform_window(clip)

        self.assertAlmostEqual(window["start_ratio"], 0.25)
        self.assertAlmostEqual(window["end_ratio"], 0.75)

    def test_waveform_window_uses_stored_v2_density(self):
        helper = self.make_qwidget_clip_helper()
        clip = types.SimpleNamespace(data={
            "start": 0.5,
            "end": 1.5,
            "ui": {
                "audio_data": [0.25] * 400,
                "audio_data_format": "absolute_peak_v2",
                "audio_data_rate": 200,
            },
        })

        window = helper.clip_waveform_window(clip)

        self.assertAlmostEqual(window["start_ratio"], 0.25)
        self.assertAlmostEqual(window["end_ratio"], 0.75)

    def test_clip_recording_seeks_to_clip_start_and_selects_lower_track(self):
        helper = types.SimpleNamespace(
            PlayheadMoved=MagicMock(),
            _recording_track_for_clip=MagicMock(return_value=2),
            _show_recording_dock_deferred=MagicMock(),
        )
        clip = types.SimpleNamespace(data={"position": 3.25, "layer": 3})
        app = types.SimpleNamespace(project=types.SimpleNamespace(
            get=lambda key: {"num": 24, "den": 1} if key == "fps" else None
        ))

        with patch.object(self.timeline_module, "get_app", return_value=app):
            self.timeline_module.TimelineView._record_from_clip(helper, clip)

        helper.PlayheadMoved.assert_called_once_with(79, True)
        helper._recording_track_for_clip.assert_called_once_with(clip)
        helper._show_recording_dock_deferred.assert_called_once_with(
            start_time=3.25,
            track_number=2,
        )

    def test_clip_recording_chooses_first_unoccupied_unlocked_track_below(self):
        source = types.SimpleNamespace(data={
            "position": 5.0,
            "start": 0.0,
            "end": 3.0,
            "layer": 5,
        })
        tracks = [
            types.SimpleNamespace(data={"number": 5, "lock": False}),
            types.SimpleNamespace(data={"number": 4, "lock": False}),
            types.SimpleNamespace(data={"number": 3, "lock": True}),
            types.SimpleNamespace(data={"number": 2, "lock": False}),
        ]
        occupied = [types.SimpleNamespace(data={
            "position": 6.0,
            "start": 0.0,
            "end": 1.0,
            "layer": 4,
        })]

        with patch.object(self.timeline_module.Track, "filter", return_value=tracks), \
                patch.object(self.timeline_module.Clip, "filter", return_value=occupied):
            track_number = self.timeline_module.TimelineView._recording_track_for_clip(
                types.SimpleNamespace(), source
            )

        self.assertEqual(track_number, 2)

    def make_qwidget_finish_drag_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class GeometryStub:
            def __init__(self, helper):
                self.helper = helper

            def mark_dirty(self):
                self.helper.geometry_marked_dirty += 1

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self):
                self.dragging_items = []
                self._drag_moved = True
                self._collapse_selection_on_release = False
                self._collapse_selection_target = None
                self._drag_transaction_id = "drag-tx-1"
                self._drag_commit_in_progress = False
                self._preserve_overrides_once = False
                self._pending_transition_overrides = {}
                self._pending_clip_overrides = {}
                self._last_event = None
                self.transition_updates = []
                self.clip_updates = []
                self.changed_calls = 0
                self.update_calls = 0
                self.release_calls = 0
                self.project_duration_updates = 0
                self.geometry_marked_dirty = 0
                self.cursor_updates = []
                self.snap_reset_calls = 0
                self.snap = types.SimpleNamespace(reset=self._reset_snap)
                self.geometry = GeometryStub(self)
                self.win = types.SimpleNamespace(addSelection=lambda *_args, **_kwargs: None)

            def _reset_snap(self):
                self.snap_reset_calls += 1

            def update_transition_data(self, transition_data, **kwargs):
                self.transition_updates.append((copy.deepcopy(transition_data), dict(kwargs)))

            def update_clip_data(self, clip_data, **kwargs):
                self.clip_updates.append((copy.deepcopy(clip_data), dict(kwargs)))

            def _update_project_duration(self):
                self.project_duration_updates += 1

            def changed(self, _value):
                self.changed_calls += 1

            def update(self):
                self.update_calls += 1

            def _release_cursor(self):
                self.release_calls += 1

            def _updateCursor(self, pos):
                self.cursor_updates.append(pos)

        return Helper()

    def make_qwidget_drag_move_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class GeometryStub:
            def __init__(self, helper):
                self.helper = helper
                self.updated_rects = {}

            def calc_item_rect(self, item):
                data = item.data if isinstance(item.data, dict) else {}
                position = float(data.get("position", 0.0) or 0.0)
                start = float(data.get("start", 0.0) or 0.0)
                end = float(data.get("end", start) or start)
                return QRectF(position * 24.0, 0.0, max(0.0, end - start) * 24.0, 10.0)

            def update_item_rect(self, item, rect):
                self.updated_rects[item.id] = QRectF(rect)

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self):
                self._drag_commit_in_progress = False
                self.dragging_items = []
                self._drag_threshold_met = True
                self._drag_press_pos = QPointF()
                self._drag_layer_idx_start = 0
                self.drag_bbox = QRectF()
                self.drag_clip_offset = 0.0
                self.pixels_per_second = 24.0
                self.fps_float = 24.0
                self.enable_snapping = False
                self._pending_clip_overrides = {}
                self._pending_transition_overrides = {}
                self._drag_initial = {}
                self._drag_moved = False
                self.track_list = [types.SimpleNamespace(data={"number": 1})]
                self._track_num_from_index = {0: 1}
                self._last_event = types.SimpleNamespace(
                    pos=lambda: QPointF(0.0, 0.0),
                    modifiers=lambda: Qt.NoModifier,
                )
                self.geometry = GeometryStub(self)
                self.panel_shifts = []
                self.update_calls = 0

            def _track_index_at_viewport_y(self, *_args, **_kwargs):
                return 0

            def _nearest_unlocked_track_index(self, index):
                return index

            def _panel_shift_item(self, item, delta_sec, frame_delta):
                self.panel_shifts.append((item.id, float(delta_sec), int(frame_delta)))

            def update(self):
                self.update_calls += 1

        return Helper()

    def make_qwidget_finish_resize_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self):
                self._resizing_item = None
                self._resize_items = []
                self._resize_initial_map = {}
                self._resize_results = {}
                self._resize_edge = "right"
                self._snap_keyframe_seconds = []
                self._suspend_changed_update = 0
                self._suspend_keyframe_rebuild = False
                self._pending_clip_overrides = {}
                self._pending_transition_overrides = {}
                self._preserve_overrides_once = False
                self._preserve_overrides_during_batch = False
                self._keyframes_dirty = False
                self._dragging_panel_keyframes = False
                self._dragging_keyframe = False
                self.enable_timing = False
                self.clip_updates = []
                self.transition_updates = []
                self.trim_preview_disabled = []
                self.refresh_calls = []
                self.waveform_refresh_calls = []
                self.refresh_keyframe_calls = 0
                self.snap_reset_calls = 0
                self.project_duration_updates = 0
                self.changed_calls = 0
                self.release_calls = 0
                self.cursor_updates = []
                self.geometry_mark_dirty_calls = 0
                self.update_calls = 0
                self.retime_calls = []
                self.win = types.SimpleNamespace(_trim_refresh_pending=False)
                self.snap = types.SimpleNamespace(reset=self._reset_snap)
                self._last_event = types.SimpleNamespace(pos=lambda: QPointF(10.0, 10.0))
                self.geometry = types.SimpleNamespace(mark_dirty=self._mark_geometry_dirty)

            def _reset_snap(self):
                self.snap_reset_calls += 1

            def _snap_time(self, value):
                return float(value)

            def update_clip_data(self, clip_data, **kwargs):
                self.clip_updates.append(
                    {
                        "id": clip_data.get("id"),
                        "override_keys": sorted(self._pending_clip_overrides.keys()),
                        "kwargs": dict(kwargs),
                    }
                )

            def update_transition_data(self, transition_data, **kwargs):
                self.transition_updates.append((copy.deepcopy(transition_data), dict(kwargs)))

            def _set_trim_thumbnail_suspension(self, enabled, clip_id=None):
                if not enabled:
                    self.trim_preview_disabled.append(str(clip_id))

            def RefreshTrimmedTimelineItem(self, payload, edge):
                self.refresh_calls.append((payload, edge))

            def Show_Waveform_Triggered(self, clip_ids, transaction_id=None):
                self.waveform_refresh_calls.append((list(clip_ids), transaction_id))

            def _restore_resize_snap_ignore_ids(self, resized_items):
                return None

            def _update_project_duration(self):
                self.project_duration_updates += 1

            def changed(self, _value):
                self.changed_calls += 1
                preserve_overrides = self._preserve_overrides_once or self._preserve_overrides_during_batch
                if self._preserve_overrides_once:
                    self._preserve_overrides_once = False
                if not preserve_overrides:
                    self._pending_clip_overrides.clear()
                    self._pending_transition_overrides.clear()

            def _release_cursor(self):
                self.release_calls += 1

            def _updateCursor(self, pos):
                self.cursor_updates.append(pos)

            def _mark_geometry_dirty(self):
                self.geometry_mark_dirty_calls += 1

            def update(self):
                self.update_calls += 1

            def _refresh_keyframe_markers(self):
                self.refresh_keyframe_calls += 1

            def _commit_resized_clip(self, clip, start, end, position, context, transaction_id, ignore_refresh):
                self.retime_calls.append(
                    {
                        "id": clip.id,
                        "start": start,
                        "end": end,
                        "position": position,
                        "transaction_id": transaction_id,
                        "ignore_refresh": ignore_refresh,
                        "timing": self.enable_timing,
                    }
                )
                return qwidget_clip_module.ClipInteractionMixin._commit_resized_clip(
                    self,
                    clip,
                    start,
                    end,
                    position,
                    context,
                    transaction_id,
                    ignore_refresh,
                )

        return Helper()

    def make_qwidget_ctrl_zoom_helper(self):
        qwidget_base_module = self.qwidget_base_module

        class TimerStub:
            def __init__(self):
                self.started = 0
                self.active = False

            def start(self, *_args):
                self.started += 1
                self.active = True

            def isActive(self):
                return self.active

        class DeltaStub:
            def __init__(self, x=0.0, y=0.0, is_null=False):
                self._x = float(x)
                self._y = float(y)
                self._is_null = bool(is_null)

            def x(self):
                return self._x

            def y(self):
                return self._y

            def isNull(self):
                return self._is_null

        class EventStub:
            def __init__(self, y, modifiers=Qt.ControlModifier, buttons=Qt.MiddleButton):
                self._pos = QPointF(20.0, float(y))
                self._modifiers = modifiers
                self._buttons = buttons
                self.accepted = False

            def modifiers(self):
                return self._modifiers

            def buttons(self):
                return self._buttons

            def pos(self):
                return self._pos

            def accept(self):
                self.accepted = True

        class WheelEventStub:
            def __init__(self, delta, modifiers=Qt.ControlModifier, pixel_delta=None, x_delta=0.0):
                self._modifiers = modifiers
                self._angle_delta = DeltaStub(x=x_delta, y=delta, is_null=False)
                if pixel_delta is None:
                    self._pixel_delta = DeltaStub(is_null=True)
                else:
                    self._pixel_delta = DeltaStub(y=pixel_delta, is_null=False)
                self.accepted = False
                self.ignored = False

            def modifiers(self):
                return self._modifiers

            def pixelDelta(self):
                return self._pixel_delta

            def angleDelta(self):
                return self._angle_delta

            def accept(self):
                self.accepted = True

            def ignore(self):
                self.ignored = True

        class Helper:
            def __init__(self):
                self._ctrl_zoom_anchor_y = None
                self._ctrl_zoom_step_pixels = 40.0
                self._ctrl_zooming = False
                self._zoom_playhead_anchor = None
                self._zoom_anchor_locked = False
                self._pending_hscroll_delta = 0.0
                self._pending_vscroll_delta = 0.0
                self._pending_zoom_emit = None
                self._hscroll_timer = TimerStub()
                self._vscroll_timer = TimerStub()
                self._zoom_emit_timer = TimerStub()
                self.zoom_factor = 15.0
                self.is_auto_center = False
                self.zoom_steps = []
                self.capture_calls = 0
                self.tooltip_values = []
                self.mouse_dragging = False
                self._middle_panning = False
                self.viewport_reset_calls = 0
                self.update_calls = 0
                self.scrollbar_position = [0.20, 0.60, 400.0, 100.0]
                self.v_scrollbar_position = [0.0, 0.0, 0.0, 0.0]
                self.h_scroll_offset = 80.0
                self.scrollbar_updates = 0
                self.timeline_scrolled = []
                self.geometry = types.SimpleNamespace(mark_dirty=self._mark_dirty)

            def _reset_ctrl_mouse_zoom(self):
                return qwidget_base_module.TimelineWidgetBase._reset_ctrl_mouse_zoom(self)

            def _start_ctrl_mouse_zoom(self, pos):
                return qwidget_base_module.TimelineWidgetBase._start_ctrl_mouse_zoom(self, pos)

            def _finish_ctrl_mouse_zoom(self):
                return qwidget_base_module.TimelineWidgetBase._finish_ctrl_mouse_zoom(self)

            def _capture_playhead_zoom_anchor(self):
                self.capture_calls += 1
                self._zoom_playhead_anchor = ("captured", 75.0)

            def _apply_zoom_steps(self, steps, emit):
                self.zoom_steps.append((steps, emit))
                self.zoom_factor = 12.0
                return True

            def _set_hover_tooltip(self, value):
                self.tooltip_values.append(value)

            def _schedule_viewport_thumbnail_reset(self):
                self.viewport_reset_calls += 1

            def _update_scrollbar_handles(self):
                self.scrollbar_updates += 1

            def _mark_dirty(self):
                self.geometry_marked_dirty = getattr(self, "geometry_marked_dirty", 0) + 1

            def update(self):
                self.update_calls += 1

        return Helper(), EventStub, WheelEventStub

    def make_qwidget_group_resize_preview_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class GeometryStub:
            def __init__(self, helper):
                self.helper = helper

            def update_item_rect(self, item, rect):
                self.helper.updated_rects.append((item.id, rect))

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self):
                self._resize_items = []
                self._resize_initial_map = {}
                self._resize_results = {}
                self._resizing_item = None
                self._resize_edge = "right"
                self._press_hit = "clip-edge"
                self._keyframes_dirty = False
                self.enable_timing = False
                self.fps_float = 24.0
                self.updated_rects = []
                self.update_calls = 0
                self.preview_calls = []
                self.transition_preview_calls = []
                self.geometry = GeometryStub(self)
                self.win = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        PreviewClipFrame=lambda clip_id, frame: self.preview_calls.append((clip_id, frame)),
                        PreviewTransitionFrame=lambda transition_id, frame: self.transition_preview_calls.append((transition_id, frame)),
                    )
                )

            def _compute_clip_resize(self, item, context=None, target_edge_seconds=None):
                return QRectF(), context["initial"]["start"], context["initial"]["end"] + 1.0, context["initial"]["position"]

            def _compute_transition_resize(self, item, context=None, target_edge_seconds=None):
                return QRectF(), context["initial"]["start"], context["initial"]["end"] + 1.0, context["initial"]["position"]

            def _apply_resize_preview_override(self, item, context, start, end, position):
                return None

            def _snap_time(self, seconds):
                return float(seconds)

            def update(self):
                self.update_calls += 1

            def _active_resize_items(self):
                return qwidget_clip_module.ClipInteractionMixin._active_resize_items(self)

            def _is_active_resize_item(self, item):
                return qwidget_clip_module.ClipInteractionMixin._is_active_resize_item(self, item)

        return Helper()

    def make_qwidget_shared_resize_math_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class GeometryStub:
            def __init__(self, helper):
                self.helper = helper

            def update_item_rect(self, item, rect):
                self.helper.updated_rects.append((item.id, rect))

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self):
                self._resize_items = []
                self._resize_initial_map = {}
                self._resize_results = {}
                self._resizing_item = None
                self._resize_edge = "left"
                self._press_hit = "clip-edge"
                self._keyframes_dirty = False
                self.enable_timing = False
                self.enable_snapping = False
                self.fps_float = 30.0
                self.pixels_per_second = 30.0
                self.track_name_width = 0.0
                self.updated_rects = []
                self.update_calls = 0
                self.preview_calls = []
                self.transition_preview_calls = []
                self._last_event = None
                self.geometry = GeometryStub(self)
                self.win = types.SimpleNamespace(timeline=None)

            def _seconds_from_x(self, value):
                return float(value) / float(self.pixels_per_second or 1.0)

            def _snap_trim_delta(self, delta_seconds, edge=None, initial=None):
                return float(delta_seconds)

            def _resize_preview_focus_item(self):
                return None

            def _apply_resize_preview_override(self, item, context, start, end, position):
                return None

            def update(self):
                self.update_calls += 1

        return Helper()

    def make_qwidget_resize_target_helper(self):
        qwidget_clip_module = self.qwidget_clip_module

        class GeometryStub:
            def __init__(self, items):
                self.items = list(items)

            def iter_items(self, reverse=False, viewport=True):
                items = list(self.items)
                if reverse:
                    items.reverse()
                return items

        class Helper(qwidget_clip_module.ClipInteractionMixin):
            def __init__(self, items):
                self.geometry = GeometryStub(items)
                self.fps_float = 24.0

            def _positive_float(self, value):
                try:
                    parsed = float(value)
                except (TypeError, ValueError):
                    return None
                return parsed if parsed > 0.0 else None

        return Helper

    def make_qwidget_assign_press_helper(self, resize_items=None):
        qwidget_base_module = self.qwidget_base_module

        class GeometryStub:
            def __init__(self):
                self.items = []

            def iter_items(self, reverse=False):
                items = list(self.items)
                if reverse:
                    items.reverse()
                return items

        class EventStub:
            def __init__(self, x, y):
                self._pos = QPointF(float(x), float(y))

            def pos(self):
                return self._pos

            def modifiers(self):
                return Qt.NoModifier

        class Helper:
            def __init__(self):
                self.geometry = GeometryStub()
                self.ruler_height = 0.0
                self._press_marker = None
                self._press_keyframe = None
                self._active_keyframe_marker = None
                self._press_keyframe_clear = True
                self._panel_press_info = None
                self._press_effect_icon = None
                self._resizing_item = object()
                self._resize_items = ["stale"]
                self._resize_edge = "left"
                self._press_hit = None
                self.win = types.SimpleNamespace(selected_clips=[], selected_transitions=[])
                self.resize_items = list(resize_items or [])

            def _marker_at(self, pos):
                return None

            def _is_timeline_content_pos(self, pos):
                return qwidget_base_module.TimelineWidgetBase._is_timeline_content_pos(
                    self, pos
                )

            def _get_keyframe_at(self, pos):
                return None

            def _panel_add_button_at(self, pos):
                return None

            def _panel_marker_at(self, pos):
                return None

            def _panel_lane_at(self, pos):
                return None

            def _panel_track_at_pos(self, pos):
                return None

            def _effect_icon_at(self, pos):
                return None

            def _resize_targets_for_item(self, item, edge):
                return list(self.resize_items)

            def _hitTest(self, pos):
                return "ruler" if pos.y() <= self.ruler_height else "clip"

            def _item_resize_edge_at(self, rect, pos, edge=5):
                return qwidget_base_module.TimelineWidgetBase._item_resize_edge_at(
                    self, rect, pos, edge=edge
                )

        return Helper(), EventStub

    def make_qwidget_pending_clip_menu_helper(self):
        qwidget_base_module = self.qwidget_base_module

        class GeometryStub:
            def iter_clips(self, reverse=False):
                return []

        class Helper:
            def __init__(self):
                self._clip_text_rects = []
                self._pending_clip_menu_target = None
                self._pending_clip_menu_press_pos = None
                self._pending_clip_menu_dragged = False
                self.geometry = GeometryStub()
                self.clip_painter = types.SimpleNamespace(
                    menu_pix=None,
                    clip_pen=types.SimpleNamespace(widthF=lambda: 2.0),
                    menu_margin=0,
                    logical_size=lambda pix: (0.0, 0.0),
                )
                self.selected = []
                self.menu_calls = []
                self.win = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        ShowClipMenu=lambda clip_id: self.menu_calls.append(clip_id)
                    )
                )

            def _clip_menu_rect(self, rect):
                return qwidget_base_module.TimelineWidgetBase._clip_menu_rect(self, rect)

            def _effect_icon_at(self, pos):
                return None

            def _select_timeline_item(self, item_id, item_type, clear_existing):
                self.selected.append((item_id, item_type, clear_existing))

            def _clear_pending_clip_menu_click(self):
                return qwidget_base_module.TimelineWidgetBase._clear_pending_clip_menu_click(self)

            def _clip_menu_target_at(self, pos):
                return qwidget_base_module.TimelineWidgetBase._clip_menu_target_at(self, pos)

            def _begin_pending_clip_menu_click(self, pos):
                return qwidget_base_module.TimelineWidgetBase._begin_pending_clip_menu_click(self, pos)

            def _update_pending_clip_menu_drag(self, pos):
                return qwidget_base_module.TimelineWidgetBase._update_pending_clip_menu_drag(self, pos)

            def _handle_pending_clip_menu_release(self, pos):
                return qwidget_base_module.TimelineWidgetBase._handle_pending_clip_menu_release(self, pos)

        return Helper()

    def make_qwidget_pending_transition_menu_helper(self):
        qwidget_base_module = self.qwidget_base_module
        qwidget_transition_module = self.qwidget_transition_module

        class GeometryStub:
            def __init__(self):
                self.transitions = []

            def iter_transitions(self, reverse=False):
                items = list(self.transitions)
                if reverse:
                    items.reverse()
                return items

        class Helper:
            def __init__(self):
                self._pending_transition_menu_target = None
                self._pending_transition_menu_press_pos = None
                self._pending_transition_menu_dragged = False
                self._transition_text_rects = []
                self.geometry = GeometryStub()
                self.selected = []
                self.menu_calls = []
                self.win = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        ShowTransitionMenu=lambda tran_id: self.menu_calls.append(tran_id)
                    )
                )
                self.transition_painter = types.SimpleNamespace(
                    transition_menu_geometry=lambda rect, tran=None: (
                        QRectF(rect.x(), rect.y(), 18.0, min(rect.height(), 20.0)),
                        QRectF(rect.x(), rect.y(), 18.0, min(rect.height(), 20.0)),
                        None,
                        QRectF(rect.x() + 6.0, rect.y() + 4.0, 8.0, 8.0),
                        "",
                    )
                )

            def _transition_menu_rect(self, rect, tran=None):
                return qwidget_transition_module.TransitionInteractionMixin._transition_menu_rect(self, rect, tran)

            def _select_timeline_item(self, item_id, item_type, clear_existing):
                self.selected.append((item_id, item_type, clear_existing))

            def _transition_menu_target_at(self, pos):
                return qwidget_base_module.TimelineWidgetBase._transition_menu_target_at(self, pos)

            def _clear_pending_transition_menu_click(self):
                return qwidget_base_module.TimelineWidgetBase._clear_pending_transition_menu_click(self)

            def _begin_pending_transition_menu_click(self, pos):
                return qwidget_base_module.TimelineWidgetBase._begin_pending_transition_menu_click(self, pos)

            def _update_pending_transition_menu_drag(self, pos):
                return qwidget_base_module.TimelineWidgetBase._update_pending_transition_menu_drag(self, pos)

            def _handle_pending_transition_menu_release(self, pos):
                return qwidget_base_module.TimelineWidgetBase._handle_pending_transition_menu_release(self, pos)

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
                self.ruler_height = 0.0
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

            def _playhead_handle_rect(self):
                return QRectF()

            def _is_timeline_content_pos(self, pos):
                return qwidget_base_module.TimelineWidgetBase._is_timeline_content_pos(
                    self, pos
                )

            def _effect_icon_at(self, pos):
                return None

            def _track_toolbar_button_at(self, pos):
                return None

            def _transition_menu_rect(self, rect, tran=None):
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

            def _item_resize_edge_at(self, rect, pos, edge=5):
                return qwidget_base_module.TimelineWidgetBase._item_resize_edge_at(
                    self, rect, pos, edge=edge
                )

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

    def make_qwidget_keyframe_position_helper(self):
        qwidget_keyframe_module = self.qwidget_keyframe_module

        class Helper(qwidget_keyframe_module.KeyframeMixin):
            def __init__(self):
                self._pending_clip_overrides = {}
                self._pending_transition_overrides = {}

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
            font_color = QColor("black")
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

        from qt_api import QWidget

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

        def fake_get_thumbnail_pixmap(_self, _clip, clip_key, file_id, frame, rect, generation, allow_request=True):
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

        def fake_get_thumbnail_pixmap(_self, _clip, clip_key, file_id, frame, rect, generation, allow_request=True):
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

    def test_anchor_transition_endpoint_keyframes_keeps_first_and_last_frames_aligned(self):
        helper = self.make_helper()
        transition_data = {
            "brightness": {
                "Points": [
                    {"co": {"X": 2, "Y": 1.0}},
                    {"co": {"X": 5, "Y": -1.0}},
                ]
            },
            "contrast": {
                "Points": [
                    {"co": {"X": 3, "Y": 3.0}},
                    {"co": {"X": 6, "Y": 3.0}},
                ]
            },
        }

        self.timeline_module.TimelineView._anchor_transition_endpoint_keyframes(
            helper,
            transition_data,
            4,
        )

        self.assertEqual(transition_data["brightness"]["Points"][0]["co"]["X"], 1)
        self.assertEqual(transition_data["brightness"]["Points"][-1]["co"]["X"], 5)
        self.assertEqual(transition_data["contrast"]["Points"][0]["co"]["X"], 1)
        self.assertEqual(transition_data["contrast"]["Points"][-1]["co"]["X"], 5)

    def test_update_transition_data_reanchors_static_transition_endpoints_without_frame_count_change(self):
        helper = types.SimpleNamespace(
            _transition_uses_static_mask=lambda transition_data, fallback_data=None: self.timeline_module.TimelineView._transition_uses_static_mask(
                helper, transition_data, fallback_data
            ),
            _transition_mask_reader=lambda transition_data, fallback_data=None: self.timeline_module.TimelineView._transition_mask_reader(
                helper, transition_data, fallback_data
            ),
            _transition_reader_changed=lambda transition_data, fallback_data=None: self.timeline_module.TimelineView._transition_reader_changed(
                helper, transition_data, fallback_data
            ),
            _scale_keyframes=lambda keyframe, factor: self.timeline_module.TimelineView._scale_keyframes(
                helper, keyframe, factor
            ),
            _anchor_transition_endpoint_keyframes=lambda transition_data, total_frames: self.timeline_module.TimelineView._anchor_transition_endpoint_keyframes(
                helper, transition_data, total_frames
            ),
            _auto_orient_transition_keyframes=lambda transition_data: None,
            delete_invalid_timeline_item=lambda _item: False,
            window=types.SimpleNamespace(
                IgnoreUpdates=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)
            ),
            show_wait_spinner=False,
        )
        old_data = {
            "id": "T1",
            "layer": 1,
            "position": 10.0,
            "start": 0.0,
            "end": 2.0,
            "reader": {"has_single_image": True},
            "brightness": {
                "Points": [
                    {"co": {"X": 1, "Y": 1.0}},
                    {"co": {"X": 62, "Y": -1.0}},
                ]
            },
            "contrast": {"Points": [{"co": {"X": 1, "Y": 3.0}}, {"co": {"X": 62, "Y": 3.0}}]},
        }
        saved = []
        existing_transition = types.SimpleNamespace(
            id="T1",
            data=copy.deepcopy(old_data),
            save=lambda: saved.append(copy.deepcopy(existing_transition.data)),
        )
        transition_json = {
            "id": "T1",
            "layer": 1,
            "position": 10.0,
            "start": 0.0,
            "end": (61.0 / 30.0),
            "reader": {"has_single_image": True},
        }

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module.Transition, "get", return_value=existing_transition))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=types.SimpleNamespace(
                project=types.SimpleNamespace(get=lambda key: {"fps": {"num": 30, "den": 1}}[key]),
                updates=types.SimpleNamespace(transaction_id=None),
            )))
            self.timeline_module.TimelineView.update_transition_data(helper, transition_json, only_basic_props=True)

        self.assertTrue(saved)
        saved_data = saved[-1]
        self.assertEqual(saved_data["brightness"]["Points"][0]["co"]["X"], 1)
        self.assertEqual(saved_data["brightness"]["Points"][-1]["co"]["X"], 62)

    def test_motion_wipe_mask_uses_high_static_contrast(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()

        with patch.object(self.timeline_module, "get_app", return_value=self.make_motion_app()), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.WIPE_IN_LEFT,
                ["C1"],
                transaction_id="tx-motion-test",
            )

        self.assertEqual(len(clip.data["effects"]), 1)
        effect = clip.data["effects"][0]
        self.assertEqual(effect["class_name"], "Mask")
        self.assertEqual(effect["contrast"]["Points"][0]["co"]["Y"], 20.0)

    def test_motion_blur_wipe_in_produces_blur_then_mask_effects(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()

        with patch.object(self.timeline_module, "get_app", return_value=self.make_motion_app()), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_IN_LEFT,
                ["C1"],
                transaction_id="tx-blur-wipe-test",
            )

        self.assertEqual(len(clip.data["effects"]), 2)
        blur_fx, mask_fx = clip.data["effects"]
        self.assertEqual(blur_fx["class_name"], "Blur")
        self.assertEqual(blur_fx["horizontal_radius"]["Points"][0]["co"]["Y"], 50.0)
        self.assertEqual(blur_fx["horizontal_radius"]["Points"][-1]["co"]["Y"], 0.0)
        self.assertEqual(mask_fx["class_name"], "Mask")
        self.assertEqual(mask_fx["brightness"]["Points"][0]["co"]["Y"], 1.0)
        self.assertEqual(mask_fx["brightness"]["Points"][-1]["co"]["Y"], -1.0)
        self.assertEqual(mask_fx["contrast"]["Points"][0]["co"]["Y"], 10.0)

    def test_motion_blur_wipe_out_produces_blur_then_mask_effects(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()

        with patch.object(self.timeline_module, "get_app", return_value=self.make_motion_app()), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_OUT_LEFT,
                ["C1"],
                transaction_id="tx-blur-wipe-test",
            )

        self.assertEqual(len(clip.data["effects"]), 2)
        blur_fx, mask_fx = clip.data["effects"]
        self.assertEqual(blur_fx["class_name"], "Blur")
        self.assertEqual(blur_fx["horizontal_radius"]["Points"][0]["co"]["Y"], 0.0)
        self.assertEqual(blur_fx["horizontal_radius"]["Points"][-1]["co"]["Y"], 50.0)
        self.assertEqual(mask_fx["class_name"], "Mask")
        self.assertEqual(mask_fx["brightness"]["Points"][0]["co"]["Y"], -1.0)
        self.assertEqual(mask_fx["brightness"]["Points"][-1]["co"]["Y"], 1.0)
        self.assertEqual(mask_fx["contrast"]["Points"][0]["co"]["Y"], 10.0)

    def test_motion_focus_wipe_reuses_existing_blur_and_mask_effects(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()
        app = self.make_motion_app()

        with patch.object(self.timeline_module, "get_app", return_value=app), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_IN_LEFT,
                ["C1"],
                transaction_id="tx-focus-wipe-test",
            )
            first_effect_ids = [effect["id"] for effect in clip.data["effects"]]

            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_IN_TOP,
                ["C1"],
                transaction_id="tx-focus-wipe-test",
            )

        self.assertEqual(len(clip.data["effects"]), 2)
        self.assertEqual([effect["id"] for effect in clip.data["effects"]], first_effect_ids)
        blur_fx, mask_fx = clip.data["effects"]
        self.assertEqual(blur_fx["class_name"], "Blur")
        self.assertEqual(mask_fx["class_name"], "Mask")
        self.assertEqual(mask_fx["ui-menu"], self.timeline_module.MOTION_EFFECT_UI_MENU)
        self.assertEqual(
            os.path.basename(mask_fx["mask_reader"]["path"]),
            "wipe_top_to_bottom.svg",
        )

    def test_motion_focus_wipe_in_then_out_keeps_one_blur_and_one_mask(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()

        with patch.object(self.timeline_module, "get_app", return_value=self.make_motion_app()), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_IN_LEFT,
                ["C1"],
                transaction_id="tx-focus-wipe-test",
            )
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_OUT_LEFT,
                ["C1"],
                transaction_id="tx-focus-wipe-test",
            )

        self.assertEqual(len(clip.data["effects"]), 2)
        blur_fx, mask_fx = clip.data["effects"]
        self.assertEqual(blur_fx["class_name"], "Blur")
        self.assertEqual(mask_fx["class_name"], "Mask")
        self.assertEqual(
            [point["co"]["Y"] for point in blur_fx["horizontal_radius"]["Points"]],
            [50.0, 0.0, 0.0, 50.0],
        )
        self.assertEqual(
            [point["co"]["Y"] for point in mask_fx["brightness"]["Points"]],
            [1.0, -1.0, -1.0, 1.0],
        )

    def test_motion_focus_wipe_does_not_repurpose_manual_blur_or_mask_effects(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()
        clip.data["effects"] = [
            {
                "id": "USER_BLUR",
                "class_name": "Blur",
                "horizontal_radius": {"Points": [{"co": {"X": 1, "Y": 12.0}}]},
                "vertical_radius": {"Points": [{"co": {"X": 1, "Y": 12.0}}]},
            },
            {
                "id": "USER_MASK",
                "class_name": "Mask",
                "brightness": {"Points": [{"co": {"X": 1, "Y": 0.25}}]},
                "contrast": {"Points": [{"co": {"X": 1, "Y": 4.0}}]},
            },
        ]

        with patch.object(self.timeline_module, "get_app", return_value=self.make_motion_app()), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.FOCUS_WIPE_IN_LEFT,
                ["C1"],
                transaction_id="tx-focus-wipe-test",
            )

        self.assertEqual(len(clip.data["effects"]), 4)
        self.assertEqual(clip.data["effects"][0]["id"], "USER_BLUR")
        self.assertEqual(clip.data["effects"][1]["id"], "USER_MASK")
        self.assertNotIn("ui-menu", clip.data["effects"][0])
        self.assertNotIn("ui-menu", clip.data["effects"][1])
        self.assertEqual(clip.data["effects"][0]["horizontal_radius"]["Points"][0]["co"]["Y"], 12.0)
        self.assertEqual(clip.data["effects"][1]["brightness"]["Points"][0]["co"]["Y"], 0.25)

    def test_motion_wipe_out_circle_presets_use_visible_motion_direction(self):
        cases = (
            (self.timeline_module.MenuAnimate.WIPE_OUT_CIRCLE_EXPAND, "circle_out_to_in.svg"),
            (self.timeline_module.MenuAnimate.WIPE_OUT_CIRCLE_SHRINK, "circle_in_to_out.svg"),
            (self.timeline_module.MenuAnimate.FOCUS_WIPE_OUT_CIRCLE_EXPAND, "circle_out_to_in.svg"),
            (self.timeline_module.MenuAnimate.FOCUS_WIPE_OUT_CIRCLE_SHRINK, "circle_in_to_out.svg"),
        )

        for action, svg_filename in cases:
            with self.subTest(action=action):
                helper = self.make_motion_helper()
                clip = self.make_motion_clip()

                with patch.object(self.timeline_module, "get_app", return_value=self.make_motion_app()), \
                        patch.object(self.timeline_module.Clip, "get", return_value=clip):
                    self.timeline_module.TimelineView.Animate_Triggered(
                        helper,
                        action,
                        ["C1"],
                        transaction_id="tx-circle-wipe-test",
                    )

                mask_fx = [
                    effect for effect in clip.data["effects"]
                    if effect.get("class_name") == "Mask"
                ][0]
                self.assertEqual(
                    os.path.basename(mask_fx["mask_reader"]["path"]),
                    svg_filename,
                )
                self.assertEqual(mask_fx["brightness"]["Points"][0]["co"]["Y"], -1.0)
                self.assertEqual(mask_fx["brightness"]["Points"][-1]["co"]["Y"], 1.0)

    def test_motion_bounce_emphasis_uses_frame_relative_offsets(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            project=types.SimpleNamespace(
                get=lambda key: {"num": 30, "den": 1} if key == "fps" else None,
                generate_id=lambda: "FX1",
            ),
        )

        with patch.object(self.timeline_module, "get_app", return_value=app), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.BOUNCE,
                ["C1"],
                transaction_id="tx-motion-test",
            )

        points = {
            point["co"]["X"]: point["co"]["Y"]
            for point in clip.data["location_y"]["Points"]
        }
        self.assertAlmostEqual(points[13], -0.25)
        self.assertAlmostEqual(points[14], -0.25)
        self.assertAlmostEqual(points[22], -0.125)
        self.assertAlmostEqual(points[28], -0.033333, places=6)
        self.assertAlmostEqual(points[31], 0.0)

    def test_motion_emphasis_uses_playhead_in_clip_local_frame_space(self):
        helper = self.make_motion_helper()
        helper.window.preview_thread.current_frame = 331
        clip = self.make_motion_clip()
        clip.data["position"] = 10.0
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            project=types.SimpleNamespace(
                get=lambda key: {"num": 30, "den": 1} if key == "fps" else None,
                generate_id=lambda: "FX1",
            ),
        )

        with patch.object(self.timeline_module, "get_app", return_value=app), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.BOUNCE,
                ["C1"],
                transaction_id="tx-motion-test",
            )

        points = {
            point["co"]["X"]: point["co"]["Y"]
            for point in clip.data["location_y"]["Points"]
        }
        self.assertIn(31, points)
        self.assertIn(43, points)
        self.assertIn(61, points)
        self.assertNotIn(13, points)
        self.assertAlmostEqual(points[43], -0.25)
        self.assertAlmostEqual(points[61], 0.0)

    def test_motion_bounce_in_down_uses_frame_relative_rebound_offsets(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            project=types.SimpleNamespace(
                get=lambda key: {"num": 30, "den": 1} if key == "fps" else None,
                generate_id=lambda: "FX1",
            ),
        )

        with patch.object(self.timeline_module, "get_app", return_value=app), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.BOUNCE_IN_DOWN,
                ["C1"],
                transaction_id="tx-motion-test",
            )

        points = {
            point["co"]["X"]: point["co"]["Y"]
            for point in clip.data["location_y"]["Points"]
        }
        self.assertAlmostEqual(points[1], -3.0)
        self.assertAlmostEqual(points[19], 0.25)
        self.assertAlmostEqual(points[24], -0.1)
        self.assertAlmostEqual(points[28], 0.05)
        self.assertAlmostEqual(points[31], 0.0)

    def test_motion_bounce_out_up_uses_frame_relative_rebound_offsets(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            project=types.SimpleNamespace(
                get=lambda key: {"num": 30, "den": 1} if key == "fps" else None,
                generate_id=lambda: "FX1",
            ),
        )

        with patch.object(self.timeline_module, "get_app", return_value=app), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.BOUNCE_OUT_UP,
                ["C1"],
                transaction_id="tx-motion-test",
            )

        points = {
            point["co"]["X"]: point["co"]["Y"]
            for point in clip.data["location_y"]["Points"]
        }
        self.assertAlmostEqual(points[67], -0.125)
        self.assertAlmostEqual(points[73], 0.25)
        self.assertAlmostEqual(points[74], 0.25)
        self.assertAlmostEqual(points[91], -3.0)

    def test_motion_ken_burns_direction_sets_distinct_scale_and_location(self):
        helper = self.make_motion_helper()
        clip = self.make_motion_clip()
        clip.data["reader"] = {"width": 3840, "height": 1080}
        app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            project=types.SimpleNamespace(
                get=lambda key: {
                    "fps": {"num": 30, "den": 1},
                    "width": 1920,
                    "height": 1080,
                }.get(key),
                generate_id=lambda: "FX1",
            ),
        )

        with patch.object(self.timeline_module, "get_app", return_value=app), \
                patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.timeline_module.TimelineView.Animate_Triggered(
                helper,
                self.timeline_module.MenuAnimate.KEN_BURNS_IN,
                ["C1"],
                transaction_id="tx-motion-test",
            )

        self.assertEqual(clip.data["scale"], openshot.SCALE_CROP)
        self.assertAlmostEqual(clip.data["scale_x"]["Points"][-1]["co"]["Y"], 1.22)
        self.assertAlmostEqual(clip.data["scale_y"]["Points"][-1]["co"]["Y"], 1.22)
        self.assertGreater(clip.data["location_x"]["Points"][0]["co"]["Y"], 0.0)
        self.assertLess(clip.data["location_x"]["Points"][-1]["co"]["Y"], 0.0)
        self.assertAlmostEqual(clip.data["location_y"]["Points"][-1]["co"]["Y"], 0.0)

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
            data={"ui": {
                "audio_data": [0.1, 0.2, 0.3],
                "audio_data_format": "absolute_peak_v2",
                "waveform_token": "wf-2",
            }}
        )

        token = helper.clip_waveform_cache_token(clip)

        self.assertEqual(token, (3, 0, "wf-2", "absolute_peak_v2", None))

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

    def test_freeze_uses_absolute_trim_end_for_right_side_split_clip(self):
        helper = self.make_time_helper()
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "id": "C1",
                "position": 10.0,
                "start": 10.0,
                "end": 52.0,
                "duration": 42.0,
                "time": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR}]},
                "volume": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": openshot.LINEAR}]},
                "ui": {},
            },
        )
        app = types.SimpleNamespace(
            project=types.SimpleNamespace(get=lambda key: {"num": 30, "den": 1} if key == "fps" else None),
            updates=types.SimpleNamespace(apply_last_action_to_history=lambda _data: None),
        )

        with patch.object(self.timeline_module.Clip, "get", return_value=clip), \
                patch.object(self.timeline_module, "get_app", return_value=app):
            self.timeline_module.TimelineView.Time_Triggered(
                helper,
                self.timeline_module.MenuTime.FREEZE,
                ["C1"],
                8,
                10.0,
            )

        self.assertEqual(clip.data["end"], 60.0)
        self.assertEqual(clip.data["duration"], 50.0)
        self.assertIn(
            {"co": {"X": 1801.0, "Y": 1561.0}, "interpolation": openshot.LINEAR},
            clip.data["time"]["Points"],
        )

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

    def test_qwidget_transition_keyframe_base_position_uses_pending_override(self):
        helper = self.make_qwidget_keyframe_position_helper()
        transition = types.SimpleNamespace(
            id="T1",
            data={"id": "T1", "position": 4.0, "start": 0.0, "end": 1.0},
        )
        helper._pending_transition_overrides["T1"] = {"position": 6.5}

        with patch.object(self.qwidget_keyframe_module, "Transition", type(transition)):
            position = self.qwidget_keyframe_module.KeyframeMixin._keyframe_base_position(
                helper,
                {"transition": transition},
            )

        self.assertEqual(position, 6.5)

    def test_qwidget_finish_clip_drag_single_transition_keeps_auto_direction(self):
        helper = self.make_qwidget_finish_drag_helper()

        class DummyTransition:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        transition = DummyTransition(
            "T1",
            {
                "id": "T1",
                "position": 4.0,
                "layer": 1,
                "start": 0.0,
                "end": 1.0,
                "reader": {"has_single_image": True},
            },
        )
        helper.dragging_items = [transition]

        with patch.object(self.qwidget_clip_module, "Transition", DummyTransition):
            self.qwidget_clip_module.ClipInteractionMixin._finishClipDrag(helper)

        self.assertEqual(helper.clip_updates, [])
        self.assertEqual(len(helper.transition_updates), 1)
        transition_payload, transition_kwargs = helper.transition_updates[0]
        self.assertTrue(transition_payload["_auto_direction"])
        self.assertEqual(transition_kwargs["transaction_id"], "drag-tx-1")

    def test_qwidget_finish_clip_drag_multi_selection_preserves_transition_direction(self):
        helper = self.make_qwidget_finish_drag_helper()

        class DummyClip:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        class DummyTransition:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        clip = DummyClip(
            "C1",
            {"id": "C1", "position": 4.0, "layer": 1, "start": 0.0, "end": 5.0},
        )
        transition = DummyTransition(
            "T1",
            {
                "id": "T1",
                "position": 8.0,
                "layer": 1,
                "start": 0.0,
                "end": 1.0,
                "reader": {"has_single_image": True},
            },
        )
        helper.dragging_items = [transition, clip]

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.qwidget_clip_module, "Clip", DummyClip))
            stack.enter_context(patch.object(self.qwidget_clip_module, "Transition", DummyTransition))
            self.qwidget_clip_module.ClipInteractionMixin._finishClipDrag(helper)

        self.assertEqual(len(helper.clip_updates), 1)
        self.assertEqual(len(helper.transition_updates), 1)
        clip_payload, _clip_kwargs = helper.clip_updates[0]
        transition_payload, _transition_kwargs = helper.transition_updates[0]
        self.assertEqual(clip_payload["id"], "C1")
        self.assertEqual(transition_payload["id"], "T1")
        self.assertNotIn("_auto_transition", clip_payload)
        self.assertNotIn("_auto_direction", transition_payload)

    def test_qwidget_drag_move_preserves_shared_edge_alignment_for_off_frame_selection(self):
        helper = self.make_qwidget_drag_move_helper()

        clip_a = types.SimpleNamespace(
            id="A",
            data={"id": "A", "position": 0.01, "layer": 1, "start": 0.0, "end": 0.59},
        )
        clip_b = types.SimpleNamespace(
            id="B",
            data={"id": "B", "position": 0.49, "layer": 1, "start": 0.0, "end": 0.11},
        )
        helper.dragging_items = [clip_a, clip_b]
        helper._drag_initial = {
            "A": {"position": 0.01, "index": 0, "position_frames": 0},
            "B": {"position": 0.49, "index": 0, "position_frames": 12},
        }
        helper.drag_bbox = QRectF(clip_a.data["position"] * 24.0, 0.0, 0.59 * 24.0, 10.0)
        helper._last_event = types.SimpleNamespace(
            pos=lambda: QPointF(helper.drag_bbox.x() + 1.0, 0.0),
            modifiers=lambda: Qt.NoModifier,
        )

        initial_right_a = clip_a.data["position"] + (clip_a.data["end"] - clip_a.data["start"])
        initial_right_b = clip_b.data["position"] + (clip_b.data["end"] - clip_b.data["start"])
        self.assertAlmostEqual(initial_right_a, initial_right_b)

        self.qwidget_clip_module.ClipInteractionMixin._dragMove(helper)

        moved_right_a = clip_a.data["position"] + (clip_a.data["end"] - clip_a.data["start"])
        moved_right_b = clip_b.data["position"] + (clip_b.data["end"] - clip_b.data["start"])
        self.assertAlmostEqual(moved_right_a, moved_right_b)
        self.assertAlmostEqual(moved_right_a - initial_right_a, 1.0 / 24.0)

    def test_qwidget_cursor_uses_razor_cursor_for_items_when_enabled(self):
        helper = self.make_qwidget_cursor_helper()
        helper.enable_razor = True
        helper.geometry.items = [(QRectF(0.0, 0.0, 100.0, 20.0), object(), False, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._updateCursor(helper, QPointF(10.0, 10.0))

        self.assertIs(helper.cursor_value, helper.cursors["razor"])
        self.assertFalse(helper.unset_cursor_called)

    def test_qwidget_razor_cursor_hotspot_matches_web_alignment(self):
        helper = types.SimpleNamespace()

        cursor = self.qwidget_base_module.TimelineWidgetBase._load_razor_cursor(helper)

        self.assertIsInstance(cursor, QCursor)
        self.assertEqual(cursor.hotSpot().x(), 0)
        self.assertEqual(cursor.hotSpot().y(), 2)

    def test_qwidget_cursor_keeps_hand_cursor_for_items_when_razor_disabled(self):
        helper = self.make_qwidget_cursor_helper()
        helper.geometry.items = [(QRectF(0.0, 0.0, 100.0, 20.0), object(), False, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._updateCursor(helper, QPointF(10.0, 10.0))

        self.assertIs(helper.cursor_value, helper.cursors["hand"])
        self.assertFalse(helper.unset_cursor_called)

    def test_qwidget_cursor_uses_resize_cursor_on_exact_item_boundary(self):
        helper = self.make_qwidget_cursor_helper()
        helper.geometry.items = [(QRectF(10.0, 10.0, 40.0, 20.0), object(), True, "transition")]
        helper._resize_targets_for_item = lambda _item, _edge: ["selected"]

        self.qwidget_base_module.TimelineWidgetBase._updateCursor(helper, QPointF(50.0, 20.0))

        self.assertIs(helper.cursor_value, helper.cursors["resize_x"])
        self.assertFalse(helper.unset_cursor_called)

    def test_qwidget_cursor_ignores_item_occluded_by_ruler(self):
        helper = self.make_qwidget_cursor_helper()
        helper.ruler_height = 30.0
        helper.geometry.items = [
            (QRectF(10.0, 10.0, 40.0, 40.0), object(), True, "clip")
        ]

        self.qwidget_base_module.TimelineWidgetBase._updateCursor(
            helper, QPointF(10.0, 20.0)
        )

        self.assertIsNone(helper.cursor_value)
        self.assertTrue(helper.unset_cursor_called)

    def test_qwidget_resize_move_ignores_non_handle_press_hits(self):
        helper = types.SimpleNamespace(
            _press_hit="clip",
            _resizing_item=None,
            _last_event=types.SimpleNamespace(pos=lambda: QPointF(320.0, 20.0)),
            track_name_width=140.0,
            changed_calls=[],
            _itemResizeMove=lambda: (_ for _ in ()).throw(AssertionError("clip resize should not run")),
            _projectResizeMove=lambda: (_ for _ in ()).throw(AssertionError("project resize should not run")),
            changed=lambda value: helper.changed_calls.append(value),
        )

        self.qwidget_clip_module.ClipInteractionMixin._resizeMove(helper)

        self.assertEqual(helper.track_name_width, 140.0)
        self.assertEqual(helper.changed_calls, [])

    def test_clip_geometry_marks_string_selected_ids_for_numeric_clip_ids(self):
        module = self.geometry_clip_module

        class Helper(module.ClipGeometryMixin):
            def __init__(self):
                self.widget = types.SimpleNamespace(
                    track_name_width=140.0,
                    pixels_per_second=10.0,
                    ruler_height=40.0,
                    vertical_factor=48.0,
                    normalize_track_number=lambda value: value,
                )
                self.clip_entries = []
                self._clip_starts = []
                self._clip_max_rights = []

        clip = types.SimpleNamespace(id=42, data={"position": 1.0, "start": 0.0, "end": 3.0, "layer": 0})
        helper = Helper()
        ctx = {"track_offsets": {0: 0.0}, "spacing": 56.0, "top_margin": 0.0}
        win = types.SimpleNamespace(selected_clips=["42"])

        with patch.object(module.Clip, "filter", return_value=[clip]):
            helper._populate_clip_rects({0: 0}, ctx, win)

        self.assertEqual(len(helper.clip_entries), 1)
        self.assertTrue(helper.clip_entries[0].selected)

    def test_transition_geometry_marks_string_selected_ids_for_numeric_transition_ids(self):
        module = self.geometry_transition_module

        class Helper(module.TransitionGeometryMixin):
            def __init__(self):
                self.widget = types.SimpleNamespace(
                    track_name_width=140.0,
                    pixels_per_second=10.0,
                    ruler_height=40.0,
                    vertical_factor=48.0,
                    normalize_track_number=lambda value: value,
                )
                self.transition_entries = []
                self._transition_starts = []
                self._transition_max_rights = []

        transition = types.SimpleNamespace(id=7, data={"position": 2.0, "start": 0.0, "end": 2.0, "layer": 0})
        helper = Helper()
        ctx = {"track_offsets": {0: 0.0}, "spacing": 56.0, "top_margin": 0.0}
        win = types.SimpleNamespace(selected_transitions=["7"])

        with patch.object(module.Transition, "filter", return_value=[transition]):
            helper._populate_transition_rects({0: 0}, ctx, win)

        self.assertEqual(len(helper.transition_entries), 1)
        self.assertTrue(helper.transition_entries[0].selected)

    def test_transition_themes_use_two_pixel_border_width(self):
        humanity = self.humanity_theme_module.HumanityDarkTimelineTheme()
        retro = self.humanity_theme_module.RetroTimelineTheme()
        cosmic = self.cosmic_theme_module.CosmicDuskTimelineTheme()

        self.assertEqual(humanity.transition.border_width, 2.0)
        self.assertEqual(retro.transition.border_width, 2.0)
        self.assertEqual(cosmic.transition.border_width, 2.0)

    def test_transition_selected_state_stays_translucent_but_brighter(self):
        painter_cls = self.transition_paint_module.TransitionPainter

        self.assertLess(painter_cls.DEFAULT_OPACITY, painter_cls.SELECTED_OPACITY)
        self.assertLess(painter_cls.SELECTED_OPACITY, 1.0)
        self.assertGreater(painter_cls.SELECTED_OVERLAY_ALPHA, 0)

    def test_transition_label_uses_friendly_resource_name(self):
        helper = types.SimpleNamespace()
        tran = types.SimpleNamespace(
            data={"reader": {"path": "/tmp/transitions/common/wipe_left_to_right.svg"}}
        )

        with patch.object(self.qwidget_base_module, "get_app", return_value=types.SimpleNamespace(_tr=lambda text: text)):
            label = self.qwidget_base_module.TimelineWidgetBase._transition_label(helper, tran)

        self.assertEqual(label, "Wipe left to right")

    def test_preview_transition_model_includes_reader_path_for_friendly_label(self):
        helper = types.SimpleNamespace()
        entry = {
            "type": "transition",
            "source_id": "/tmp/transitions/common/fade.svg",
            "position": 2.0,
            "duration": 1.5,
            "layer": 4,
        }

        model = self.qwidget_base_module.TimelineWidgetBase._preview_entry_model(helper, entry)

        self.assertEqual(model.data["reader"]["path"], "/tmp/transitions/common/fade.svg")
        self.assertEqual(model.data["position"], 2.0)
        self.assertEqual(model.data["end"], 1.5)

    def test_transition_menu_rect_uses_large_hit_target_for_dropdown_arrow(self):
        rect = QRectF(100.0, 40.0, 60.0, 24.0)
        widget = types.SimpleNamespace(
            theme=self.humanity_theme_module.HumanityDarkTimelineTheme(),
            clip_selected=QColor("red"),
        )
        painter = self.transition_paint_module.TransitionPainter(widget)

        class Helper(self.qwidget_transition_module.TransitionInteractionMixin):
            def __init__(self, transition_painter):
                self.transition_painter = transition_painter

        helper = Helper(painter)
        tran = types.SimpleNamespace(data={"title": "Fade"})
        hit_rect = helper._transition_menu_rect(rect, tran)
        container_rect, _hit_rect, _scaled_arrow, arrow_rect, _title = painter.transition_menu_geometry(rect, tran)

        self.assertFalse(hit_rect.isNull())
        self.assertFalse(container_rect.isNull())
        self.assertFalse(arrow_rect.isNull())
        self.assertAlmostEqual(hit_rect.x(), rect.x())
        self.assertAlmostEqual(hit_rect.y(), rect.y())
        self.assertAlmostEqual(hit_rect.width(), container_rect.width())
        self.assertAlmostEqual(hit_rect.height(), container_rect.height())
        self.assertGreater(hit_rect.width(), arrow_rect.width())
        self.assertGreaterEqual(hit_rect.height(), arrow_rect.height())

    def test_qwidget_pending_transition_menu_release_opens_without_drag_threshold(self):
        helper = self.make_qwidget_pending_transition_menu_helper()
        tran = types.SimpleNamespace(id="T1")
        helper._transition_text_rects = [
            {"rect": QRectF(10.0, 10.0, 36.0, 18.0), "transition": tran, "open_menu": True}
        ]

        self.assertTrue(helper._begin_pending_transition_menu_click(QPointF(20.0, 20.0)))
        helper._update_pending_transition_menu_drag(QPointF(21.0, 20.0))

        opened = helper._handle_pending_transition_menu_release(QPointF(20.0, 20.0))

        self.assertTrue(opened)
        self.assertEqual(helper.selected, [("T1", "transition", True)])
        self.assertEqual(helper.menu_calls, ["T1"])

    def test_qwidget_pending_transition_menu_release_ignores_drag_motion(self):
        helper = self.make_qwidget_pending_transition_menu_helper()
        tran = types.SimpleNamespace(id="T1")
        helper._transition_text_rects = [
            {"rect": QRectF(10.0, 10.0, 36.0, 18.0), "transition": tran, "open_menu": True}
        ]

        self.assertTrue(helper._begin_pending_transition_menu_click(QPointF(20.0, 20.0)))
        helper._update_pending_transition_menu_drag(
            QPointF(20.0 + QApplication.startDragDistance(), 20.0)
        )

        opened = helper._handle_pending_transition_menu_release(
            QPointF(20.0 + QApplication.startDragDistance(), 20.0)
        )

        self.assertFalse(opened)
        self.assertEqual(helper.selected, [])
        self.assertEqual(helper.menu_calls, [])

    def test_transition_painter_border_width_does_not_change_geometry_or_snap_edges(self):
        module = self.geometry_transition_module
        snap_module = importlib.import_module("windows.views.timeline_backend.snap")

        class GeometryHelper(module.TransitionGeometryMixin):
            def __init__(self, widget):
                self.widget = widget
                self.transition_entries = []
                self._transition_starts = []
                self._transition_max_rights = []

        widget = types.SimpleNamespace(
            theme=self.humanity_theme_module.HumanityDarkTimelineTheme(),
            track_name_width=140.0,
            pixels_per_second=10.0,
            ruler_height=40.0,
            vertical_factor=48.0,
            normalize_track_number=lambda value: value,
            scrollbar_position=(0.0, 1.0, 200.0, 200.0),
            _snap_ignore_ids=set(),
            _snap_active_targets={},
            snap_tolerance_px=12.0,
            current_frame=1.0,
            fps_float=24.0,
        )
        geometry = GeometryHelper(widget)
        transition = types.SimpleNamespace(
            id="T1",
            data={"position": 2.0, "start": 0.0, "end": 5.0, "layer": 0},
        )
        ctx = {"track_offsets": {0: 0.0}, "spacing": 56.0, "top_margin": 0.0}
        win = types.SimpleNamespace(selected_transitions=[])

        with patch.object(module.Transition, "filter", return_value=[transition]):
            geometry._populate_transition_rects({0: 0}, ctx, win)

        rect = geometry.transition_entries[0].rect

        class GeometryStub:
            marker_rects = []

            def ensure(self):
                return None

            def iter_clips(self, viewport=False):
                return []

            def iter_transitions(self, viewport=False):
                return [(rect, transition, False)]

        painter = self.transition_paint_module.TransitionPainter(widget)
        self.assertEqual(painter.border_width, 2.0)
        self.assertAlmostEqual(rect.left(), 160.0)
        self.assertAlmostEqual(rect.right(), 210.0)

        snap = snap_module.SnapHelper(widget, GeometryStub())
        targets = snap._target_edges_px(viewport=False)
        self.assertIn(rect.left(), targets)
        self.assertIn(rect.right(), targets)

    def test_marker_icon_viewport_ignores_vertical_track_scroll(self):
        widget = types.SimpleNamespace(
            track_name_width=140.0,
            ruler_height=40.0,
            scroll_bar_thickness=15.0,
            scrollbar_position=[0.2, 0.7, 500.0, 250.0],
            v_scrollbar_position=[0.25, 0.5, 400.0, 100.0],
            width=lambda: 405.0,
            height=lambda: 155.0,
            h_scroll_offset=0.0,
        )
        geometry = self.geometry_base_module.GeometryBase(widget)
        geometry.marker_rects = [{
            "line_rect": QRectF(190.0, 40.0, 0.5, 400.0),
            "icon_rect": QRectF(184.0, 26.0, 12.0, 14.0),
            "hit_rect": QRectF(180.0, 22.0, 20.0, 22.0),
        }]

        marker = next(geometry.iter_markers())

        self.assertAlmostEqual(marker["icon_rect"].x(), 84.0)
        self.assertAlmostEqual(marker["icon_rect"].y(), 26.0)
        self.assertAlmostEqual(marker["hit_rect"].x(), 80.0)
        self.assertAlmostEqual(marker["hit_rect"].y(), 22.0)
        self.assertAlmostEqual(widget.h_scroll_offset, 100.0)

    def test_playback_cache_paints_fixed_lane_background(self):
        image = QImage(140, 80, QImage.Format_ARGB32)
        image.fill(QColor("#00ff00"))
        widget = types.SimpleNamespace(
            theme=types.SimpleNamespace(
                playback_cache_color=QColor("#0000ff"),
                playback_cache_height=5.0,
                track=types.SimpleNamespace(
                    background=QColor("#ff0000"),
                    background2=QColor(),
                ),
            ),
            _playback_cache_ranges=[(0.0, 50.0)],
            pixels_per_second=1.0,
            track_name_width=20.0,
            ruler_height=10.0,
            scroll_bar_thickness=0.0,
            track_margin_top=8.0,
            h_scroll_offset=0.0,
            width=lambda: 140,
            height=lambda: 80,
        )
        painter_obj = self.cache_paint_module.PlaybackCachePainter(widget)

        painter = QPainter(image)
        try:
            painter_obj.paint(painter)
        finally:
            painter.end()

        self.assertEqual(image.pixelColor(30, 12).name(), "#0000ff")
        self.assertEqual(image.pixelColor(90, 12).name(), "#ff0000")
        self.assertEqual(image.pixelColor(30, 16).name(), "#ff0000")
        self.assertEqual(image.pixelColor(30, 19).name(), "#00ff00")

    def test_qwidget_ctrl_mouse_zoom_starts_on_ctrl_middle_press(self):
        helper, _event_cls, _wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        pos = QPointF(20.0, 120.0)

        started = self.qwidget_base_module.TimelineWidgetBase._start_ctrl_mouse_zoom(helper, pos)

        self.assertTrue(started)
        self.assertTrue(helper._ctrl_zooming)
        self.assertTrue(helper.mouse_dragging)
        self.assertEqual(helper._ctrl_zoom_anchor_y, 120.0)
        self.assertEqual(helper._zoom_playhead_anchor, ("captured", 75.0))
        self.assertTrue(helper._zoom_anchor_locked)
        self.assertEqual(helper.zoom_steps, [])

    def test_qwidget_ctrl_mouse_zoom_moves_up_to_zoom_in(self):
        helper, event_cls, _wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        helper._ctrl_zooming = True
        helper._ctrl_zoom_anchor_y = 120.0
        event = event_cls(100.0)

        handled = self.qwidget_base_module.TimelineWidgetBase._handle_ctrl_mouse_zoom(helper, event)

        self.assertTrue(handled)
        self.assertTrue(event.accepted)
        self.assertEqual(helper._ctrl_zoom_anchor_y, 100.0)
        self.assertEqual(helper.capture_calls, 0)
        self.assertEqual(len(helper.zoom_steps), 1)
        self.assertAlmostEqual(helper.zoom_steps[0][0], 0.5)
        self.assertFalse(helper.zoom_steps[0][1])
        self.assertFalse(helper.is_auto_center)
        self.assertEqual(helper._pending_zoom_emit, 12.0)
        self.assertEqual(helper._zoom_emit_timer.started, 1)

    def test_qwidget_ctrl_mouse_zoom_requires_middle_button_and_ctrl(self):
        helper, event_cls, _wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        helper._ctrl_zooming = True
        helper._ctrl_zoom_anchor_y = 120.0
        event = event_cls(90.0, buttons=Qt.LeftButton)

        handled = self.qwidget_base_module.TimelineWidgetBase._handle_ctrl_mouse_zoom(helper, event)

        self.assertFalse(handled)
        self.assertFalse(event.accepted)
        self.assertIsNone(helper._ctrl_zoom_anchor_y)
        self.assertFalse(helper._ctrl_zooming)
        self.assertEqual(helper.zoom_steps, [])

    def test_qwidget_ctrl_mouse_zoom_finish_releases_cursor(self):
        helper, _event_cls, _wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        helper._ctrl_zooming = True
        helper._ctrl_zoom_anchor_y = 120.0
        helper.mouse_dragging = True

        self.qwidget_base_module.TimelineWidgetBase._finish_ctrl_mouse_zoom(helper)

        self.assertFalse(helper._ctrl_zooming)
        self.assertIsNone(helper._ctrl_zoom_anchor_y)
        self.assertIsNone(helper._zoom_playhead_anchor)
        self.assertFalse(helper._zoom_anchor_locked)
        self.assertFalse(helper.mouse_dragging)
        self.assertEqual(helper.viewport_reset_calls, 1)
        self.assertEqual(helper.update_calls, 1)

    def test_qwidget_ctrl_mouse_zoom_release_finishes_gesture(self):
        helper, _event_cls, _wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        helper._ctrl_zooming = True
        helper._ctrl_zoom_anchor_y = 120.0
        helper._zoom_playhead_anchor = ("captured", 75.0)
        helper._zoom_anchor_locked = True
        helper.mouse_dragging = True
        release = types.SimpleNamespace(
            button=lambda: Qt.MiddleButton,
            pos=lambda: QPointF(20.0, 100.0),
            accept=lambda: setattr(release, "accepted", True),
        )
        release.accepted = False

        self.qwidget_base_module.TimelineWidgetBase.mouseReleaseEvent(helper, release)

        self.assertTrue(release.accepted)
        self.assertFalse(helper._ctrl_zooming)
        self.assertIsNone(helper._ctrl_zoom_anchor_y)
        self.assertIsNone(helper._zoom_playhead_anchor)
        self.assertFalse(helper._zoom_anchor_locked)
        self.assertFalse(helper.mouse_dragging)
        self.assertEqual(helper.viewport_reset_calls, 1)

    def test_qwidget_ctrl_wheel_zoom_preserves_viewport_anchor(self):
        helper, _event_cls, wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        event = wheel_event_cls(120.0)

        self.qwidget_base_module.TimelineWidgetBase.wheelEvent(helper, event)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)
        self.assertEqual(helper.capture_calls, 1)
        self.assertEqual(helper._zoom_playhead_anchor, ("captured", 75.0))
        self.assertTrue(helper._zoom_anchor_locked)
        self.assertEqual(helper.zoom_steps, [(1.0, False)])
        self.assertFalse(helper.is_auto_center)
        self.assertEqual(helper._pending_zoom_emit, 12.0)
        self.assertEqual(helper._zoom_emit_timer.started, 1)

    def test_qwidget_shift_wheel_scrolls_horizontally(self):
        helper, _event_cls, wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        event = wheel_event_cls(-120.0, modifiers=Qt.ShiftModifier)
        app = types.SimpleNamespace(
            window=types.SimpleNamespace(
                TimelineScrolled=types.SimpleNamespace(
                    emit=lambda positions: helper.timeline_scrolled.append(list(positions))
                )
            )
        )

        with patch.object(self.qwidget_base_module, "get_app", return_value=app):
            self.qwidget_base_module.TimelineWidgetBase.wheelEvent(helper, event)
            helper._hscroll_timer.active = False
            self.qwidget_base_module.TimelineWidgetBase._flush_pending_horizontal_scroll(helper)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)
        self.assertEqual(helper._hscroll_timer.started, 1)
        self.assertAlmostEqual(helper.scrollbar_position[0], 0.24)
        self.assertAlmostEqual(helper.scrollbar_position[1], 0.64)
        self.assertAlmostEqual(helper.h_scroll_offset, 96.0)
        self.assertFalse(helper.is_auto_center)
        self.assertEqual(helper.geometry_marked_dirty, 1)
        self.assertEqual(helper.scrollbar_updates, 1)
        self.assertEqual(helper.viewport_reset_calls, 1)
        self.assertEqual(helper.update_calls, 1)
        self.assertEqual(len(helper.timeline_scrolled), 1)
        self.assertAlmostEqual(helper.timeline_scrolled[0][0], 0.24)
        self.assertAlmostEqual(helper.timeline_scrolled[0][1], 0.64)
        self.assertEqual(helper.timeline_scrolled[0][2:], [400.0, 100.0])

    def test_qwidget_tilt_wheel_scrolls_horizontally_without_shift(self):
        helper, _event_cls, wheel_event_cls = self.make_qwidget_ctrl_zoom_helper()
        event = wheel_event_cls(0.0, modifiers=Qt.NoModifier, x_delta=-120.0)
        app = types.SimpleNamespace(
            window=types.SimpleNamespace(
                TimelineScrolled=types.SimpleNamespace(
                    emit=lambda positions: helper.timeline_scrolled.append(list(positions))
                )
            )
        )

        with patch.object(self.qwidget_base_module, "get_app", return_value=app):
            self.qwidget_base_module.TimelineWidgetBase.wheelEvent(helper, event)
            helper._hscroll_timer.active = False
            self.qwidget_base_module.TimelineWidgetBase._flush_pending_horizontal_scroll(helper)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)
        self.assertEqual(helper._hscroll_timer.started, 1)
        self.assertAlmostEqual(helper.scrollbar_position[0], 0.24)
        self.assertAlmostEqual(helper.scrollbar_position[1], 0.64)

    def test_qwidget_set_zoom_factor_keeps_playhead_at_existing_viewport_ratio(self):
        helper = types.SimpleNamespace()
        helper.zoom_factor = 10.0
        helper._zoom_playhead_anchor = (4.0, 75.0)
        helper._zoom_anchor_locked = False
        helper._external_zoom_span = None
        helper._suspend_changed_update = 0
        helper.scrollbar_position = [0.20, 0.60, 400.0, 100.0]
        helper.pixels_per_second = 20.0
        helper.is_auto_center = True
        helper.fps_float = 24.0
        helper.current_frame = 97
        helper.win = types.SimpleNamespace(sliderZoomWidget=None)
        helper.changed = lambda _value: None
        helper.update = lambda: None
        helper._emit_zoom_signals = lambda _positions: None
        helper._schedule_viewport_thumbnail_reset = lambda: None
        helper._clamp_zoom_factor = lambda value: self.qwidget_base_module.TimelineWidgetBase._clamp_zoom_factor(helper, value)
        helper._current_project_duration = lambda: 10.0
        helper._center_on_seconds = lambda *args, **kwargs: None

        app = types.SimpleNamespace(project=types.SimpleNamespace(get=lambda key: 100.0 if key == "tick_pixels" else None))
        with patch.object(self.qwidget_base_module, "get_app", return_value=app):
            self.qwidget_base_module.TimelineWidgetBase.setZoomFactor(helper, 5.0, emit=False)

        self.assertAlmostEqual(helper.scrollbar_position[0], 0.025)
        self.assertAlmostEqual(helper.scrollbar_position[1], 0.525)
        self.assertAlmostEqual(helper.h_scroll_offset, 5.0)
        self.assertIsNone(helper._zoom_playhead_anchor)

    def test_qwidget_set_zoom_factor_keeps_locked_playhead_anchor_for_gesture(self):
        helper = types.SimpleNamespace()
        helper.zoom_factor = 10.0
        helper._zoom_playhead_anchor = (4.0, 75.0)
        helper._zoom_anchor_locked = True
        helper._ctrl_zooming = False
        helper._external_zoom_span = None
        helper._suspend_changed_update = 0
        helper.scrollbar_position = [0.20, 0.60, 400.0, 100.0]
        helper.pixels_per_second = 20.0
        helper.is_auto_center = True
        helper.fps_float = 24.0
        helper.current_frame = 97
        helper.win = types.SimpleNamespace(sliderZoomWidget=None)
        helper.changed = lambda _value: None
        helper.update = lambda: None
        helper._emit_zoom_signals = lambda _positions: None
        helper._schedule_viewport_thumbnail_reset = lambda: None
        helper._clamp_zoom_factor = lambda value: self.qwidget_base_module.TimelineWidgetBase._clamp_zoom_factor(helper, value)
        helper._current_project_duration = lambda: 10.0
        helper._center_on_seconds = lambda *args, **kwargs: None

        app = types.SimpleNamespace(project=types.SimpleNamespace(get=lambda key: 100.0 if key == "tick_pixels" else None))
        with patch.object(self.qwidget_base_module, "get_app", return_value=app):
            self.qwidget_base_module.TimelineWidgetBase.setZoomFactor(helper, 5.0, emit=False)

        self.assertAlmostEqual(helper.scrollbar_position[0], 0.025)
        self.assertAlmostEqual(helper.scrollbar_position[1], 0.525)
        self.assertAlmostEqual(helper.h_scroll_offset, 5.0)
        self.assertEqual(helper._zoom_playhead_anchor, (4.0, 75.0))
        self.assertFalse(helper.is_auto_center)

    def test_ruler_tick_intervals_include_intermediate_common_steps(self):
        painter = object.__new__(self.ruler_paint_module.RulerPainter)

        self.assertEqual(
            painter._nice_frame_intervals(30.0)[:8],
            [1, 2, 3, 5, 6, 10, 15, 30],
        )
        self.assertIn(30, painter._nice_frame_intervals(30.0))
        self.assertIn(12, painter._nice_frame_intervals(24.0))

    def test_ruler_tick_picker_avoids_large_density_drop_near_threshold(self):
        painter = object.__new__(self.ruler_paint_module.RulerPainter)

        self.assertEqual(painter._frames_per_tick(210.0, 30.0), 10)
        self.assertEqual(painter._frames_per_tick(190.0, 30.0), 10)
        self.assertEqual(painter._frames_per_tick(110.0, 30.0), 15)
        self.assertEqual(painter._frames_per_tick(70.0, 30.0), 30)

    def test_qwidget_new_item_snap_uses_timeline_space_when_scrolled(self):
        recorded = {}
        helper = types.SimpleNamespace()
        helper.enable_snapping = True
        helper.track_name_width = 140.0
        helper.pixels_per_second = 10.0
        helper.drag_bbox = QRectF(0.0, 20.0, 10.0, 30.0)
        helper._snap_ignore_ids = set()
        helper.geometry = types.SimpleNamespace(ensure=lambda: None)
        helper._snap_time = lambda value: value
        helper._viewport_offsets = lambda: (80.0, 0.0)
        def snap_dx(delta):
            recorded["bbox_x"] = helper.drag_bbox.x()
            return delta
        helper.snap = types.SimpleNamespace(snap_dx=snap_dx)

        result = self.qwidget_base_module.TimelineWidgetBase._snap_new_item_start(helper, 5.0, 2.0)

        self.assertAlmostEqual(result, 5.0)
        self.assertAlmostEqual(recorded["bbox_x"], 190.0)

    def test_qwidget_group_resize_preview_updates_all_resize_items(self):
        helper = self.make_qwidget_group_resize_preview_helper()
        class DummyClip:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        clip_a = DummyClip("A", {"position": 1.0, "start": 0.0, "end": 2.0, "layer": 2})
        clip_b = DummyClip("B", {"position": 4.0, "start": 0.0, "end": 3.0, "layer": 5})
        helper._resize_items = [clip_a, clip_b]
        helper._resizing_item = clip_a
        helper._resize_initial_map = {
            "A": {"initial": {"position": 1.0, "start": 0.0, "end": 2.0}},
            "B": {"initial": {"position": 4.0, "start": 0.0, "end": 3.0}},
        }

        with patch.object(self.qwidget_clip_module, "Clip", DummyClip):
            self.qwidget_clip_module.ClipInteractionMixin._itemResizeMove(helper)

        self.assertEqual(sorted(helper._resize_results.keys()), ["A", "B"])
        self.assertEqual(helper.preview_calls, [("A", 73)])
        self.assertEqual(helper.transition_preview_calls, [])
        self.assertEqual(helper.update_calls, 1)

    def test_qwidget_resize_preview_focus_item_prefers_primary_resizing_item(self):
        helper = self.make_qwidget_group_resize_preview_helper()
        clip = types.SimpleNamespace(id="C1", data={"layer": 2})
        transition = types.SimpleNamespace(id="T1", data={"layer": 5})
        helper._resize_items = [transition, clip]
        helper._resizing_item = clip

        focus = self.qwidget_clip_module.ClipInteractionMixin._resize_preview_focus_item(helper)

        self.assertIs(focus, clip)

    def test_qwidget_group_resize_preview_uses_shared_left_edge_for_mixed_items(self):
        helper = self.make_qwidget_shared_resize_math_helper()
        class DummyTransition:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        clip = types.SimpleNamespace(id="C1", data={"position": 55.0, "start": 0.0, "end": 2.0})
        transition = DummyTransition("T1", {"position": 55.0, "start": 0.5, "end": 2.5})
        helper._resize_items = [transition, clip]
        helper._resizing_item = transition
        helper._resize_initial_map = {
            "T1": {
                "initial": {"position": 55.0, "start": 0.5, "end": 2.5, "duration": 2.0},
                "world_rect": QRectF(55.0 * 30.0, 0.0, 60.0, 40.0),
                "rect": QRectF(55.0 * 30.0, 0.0, 60.0, 40.0),
                "static_mask": False,
            },
            "C1": {
                "initial": {"position": 55.0, "start": 0.0, "end": 2.0, "duration": 2.0},
                "world_rect": QRectF(55.0 * 30.0, 50.0, 60.0, 40.0),
                "rect": QRectF(55.0 * 30.0, 50.0, 60.0, 40.0),
                "max_duration": 10.0,
                "allow_left_overflow": True,
                "clip_is_single_image": True,
            },
        }
        helper._last_event = types.SimpleNamespace(pos=lambda: QPointF((54.766666666666666 * 30.0), 10.0))

        with patch.object(self.qwidget_clip_module, "Transition", DummyTransition):
            self.qwidget_clip_module.ClipInteractionMixin._itemResizeMove(helper)

        self.assertAlmostEqual(helper._resize_results["T1"]["position"], 54.766666666666666)
        self.assertAlmostEqual(helper._resize_results["C1"]["position"], 54.766666666666666)

    def test_qwidget_finish_item_resize_preserves_group_overrides_until_final_refresh(self):
        helper = self.make_qwidget_finish_resize_helper()

        class DummyClip:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        clip_a = DummyClip("A", {"id": "A", "position": 1.0, "start": 0.0, "end": 2.0})
        clip_b = DummyClip("B", {"id": "B", "position": 4.0, "start": 0.0, "end": 3.0})
        helper._resizing_item = clip_a
        helper._resize_items = [clip_a, clip_b]
        helper._resize_initial_map = {
            "A": {"initial": {"start": 0.0}},
            "B": {"initial": {"start": 0.0}},
        }
        helper._resize_results = {
            "A": {"start": 0.0, "end": 2.5, "position": 1.0},
            "B": {"start": 0.0, "end": 3.5, "position": 4.0},
        }
        helper._resize_new_start = 0.0
        helper._resize_new_end = 2.5
        helper._resize_new_position = 1.0
        helper._pending_clip_overrides = {"A": {"position": 1.0}, "B": {"position": 4.0}}

        with patch.object(self.qwidget_clip_module, "Clip", DummyClip):
            self.qwidget_clip_module.ClipInteractionMixin._finishItemResize(helper)

        self.assertEqual([entry["id"] for entry in helper.clip_updates], ["A", "B"])
        self.assertEqual(helper.clip_updates[0]["override_keys"], ["A", "B"])
        self.assertEqual(helper.clip_updates[1]["override_keys"], ["A", "B"])
        self.assertFalse(helper._preserve_overrides_once)
        self.assertEqual(helper._pending_clip_overrides, {})
        self.assertEqual(helper.changed_calls, 1)
        self.assertEqual(helper.refresh_keyframe_calls, 1)

    def test_qwidget_finish_item_resize_batches_multi_retime_commits(self):
        helper = self.make_qwidget_finish_resize_helper()
        helper.enable_timing = True

        class DummyClip:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        clip_a = DummyClip("A", {"id": "A", "position": 1.0, "start": 0.0, "end": 2.0, "ui": {"audio_data": [0.1]}})
        clip_b = DummyClip("B", {"id": "B", "position": 4.0, "start": 0.0, "end": 3.0, "ui": {"audio_data": [0.2]}})
        helper._resizing_item = clip_a
        helper._resize_items = [clip_a, clip_b]
        helper._resize_initial_map = {
            "A": {"initial": {"start": 0.0}},
            "B": {"initial": {"start": 0.0}},
        }
        helper._resize_results = {
            "A": {"start": -1.0, "end": 2.5, "position": 0.0},
            "B": {"start": -1.0, "end": 3.5, "position": 3.0},
        }
        helper._resize_new_start = -1.0
        helper._resize_new_end = 2.5
        helper._resize_new_position = 0.0
        helper._pending_clip_overrides = {"A": {"position": 0.0}, "B": {"position": 3.0}}

        retime_invocations = []

        def fake_retime_clip(clip, new_end, new_position, direction=1):
            retime_invocations.append((clip.id, new_end, new_position, direction))
            clip.data["end"] = new_end
            clip.data["position"] = new_position
            clip.data["duration"] = new_end - float(clip.data.get("start", 0.0) or 0.0)
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.qwidget_clip_module, "Clip", DummyClip))
            stack.enter_context(patch.object(self.qwidget_clip_module, "retime_clip", side_effect=fake_retime_clip))
            self.qwidget_clip_module.ClipInteractionMixin._finishItemResize(helper)

        self.assertEqual(retime_invocations, [("A", 3.5, 0.0, 1), ("B", 4.5, 3.0, 1)])
        self.assertEqual([call["id"] for call in helper.retime_calls], ["A", "B"])
        self.assertEqual(len(helper.clip_updates), 2)
        self.assertEqual(helper.clip_updates[0]["kwargs"]["ignore_refresh"], True)
        self.assertEqual(helper.clip_updates[1]["kwargs"]["ignore_refresh"], False)
        self.assertEqual(
            helper.clip_updates[0]["kwargs"]["transaction_id"],
            helper.clip_updates[1]["kwargs"]["transaction_id"],
        )
        self.assertEqual(
            helper.waveform_refresh_calls,
            [(["A", "B"], helper.clip_updates[0]["kwargs"]["transaction_id"])],
        )
        self.assertEqual(helper.changed_calls, 1)
        self.assertEqual(helper.refresh_keyframe_calls, 1)

    def test_qwidget_finish_item_resize_preserves_shared_right_edge_after_snapping(self):
        helper = self.make_qwidget_finish_resize_helper()
        frame = 1.0 / 24.0

        class DummyClip:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        class DummyTransition:
            def __init__(self, item_id, data):
                self.id = item_id
                self.data = data

        clip = DummyClip("C1", {"id": "C1", "position": 0.0, "start": 0.0, "end": frame, "ui": {}})
        transition = DummyTransition(
            "T1",
            {"id": "T1", "position": 0.0, "start": frame / 2.0, "end": frame * 1.5, "duration": frame},
        )
        helper._resizing_item = clip
        helper._resize_edge = "left"
        helper._resize_items = [clip, transition]
        helper._resize_initial_map = {
            "C1": {"initial": {"start": 0.0, "end": frame, "position": 0.0}},
            "T1": {"initial": {"start": frame / 2.0, "end": frame * 1.5, "position": 0.0}, "static_mask": False},
        }
        helper._resize_results = {
            "C1": {"start": 0.0, "end": frame, "position": 0.0},
            "T1": {"start": frame / 2.0, "end": frame * 1.5, "position": 0.0},
        }
        helper._snap_time = lambda value: round(value * 24.0) / 24.0

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.qwidget_clip_module, "Clip", DummyClip))
            stack.enter_context(patch.object(self.qwidget_clip_module, "Transition", DummyTransition))
            self.qwidget_clip_module.ClipInteractionMixin._finishItemResize(helper)

        clip_right = clip.data["position"] + (clip.data["end"] - clip.data["start"])
        transition_right = transition.data["position"] + (transition.data["end"] - transition.data["start"])
        self.assertAlmostEqual(clip_right, transition_right)
        self.assertEqual(clip_right, frame)

    def test_qwidget_active_resize_item_helper_matches_group_members(self):
        helper = self.make_qwidget_group_resize_preview_helper()
        clip_a = types.SimpleNamespace(id="A", data={})
        clip_b = types.SimpleNamespace(id="B", data={})
        helper._resize_items = [clip_a]
        helper._resizing_item = clip_a

        self.assertTrue(self.qwidget_clip_module.ClipInteractionMixin._is_active_resize_item(helper, clip_a))
        self.assertFalse(self.qwidget_clip_module.ClipInteractionMixin._is_active_resize_item(helper, clip_b))

    def test_clip_painter_trim_preview_helper_accepts_group_resize_items(self):
        painter = self.make_clip_painter()
        clip = types.SimpleNamespace(id="C1", data={})
        painter.w._pending_clip_overrides = {
            "C1": {"start": 0.0, "end": 2.0, "position": 1.0, "scale": False}
        }
        painter.w._press_hit = "clip-edge"
        painter.w.clip_has_pending_override = lambda candidate: getattr(candidate, "id", None) == "C1"
        painter.w._is_active_resize_item = lambda candidate: getattr(candidate, "id", None) == "C1"

        self.assertTrue(painter._is_trim_preview_active(clip))

    def test_qwidget_resize_targets_only_include_shared_outer_edge_items(self):
        Helper = self.make_qwidget_resize_target_helper()
        item_a = types.SimpleNamespace(id="A", data={"position": 2.0, "start": 0.0, "end": 3.0})
        item_b = types.SimpleNamespace(id="B", data={"position": 2.0, "start": 0.0, "end": 5.0})
        item_c = types.SimpleNamespace(id="C", data={"position": 5.0, "start": 0.0, "end": 2.0})
        helper = Helper([
            (QRectF(), item_a, True, "clip"),
            (QRectF(), item_b, True, "clip"),
            (QRectF(), item_c, True, "clip"),
        ])

        left_targets = self.qwidget_clip_module.ClipInteractionMixin._resize_targets_for_item(
            helper, item_a, "left"
        )
        right_targets = self.qwidget_clip_module.ClipInteractionMixin._resize_targets_for_item(
            helper, item_b, "right"
        )

        self.assertEqual([item.id for item in left_targets], ["A", "B"])
        self.assertEqual([item.id for item in right_targets], ["B", "C"])

    def test_qwidget_resize_targets_include_mixed_clip_and_transition_on_shared_edge(self):
        Helper = self.make_qwidget_resize_target_helper()
        transition_a = types.SimpleNamespace(id="T1", data={"position": 2.0, "start": 0.0, "end": 3.0})
        clip = types.SimpleNamespace(id="C1", data={"position": 2.0, "start": 1.0, "end": 4.0})
        transition_b = types.SimpleNamespace(id="T2", data={"position": 2.0, "start": 0.0, "end": 5.0})
        helper = Helper([
            (QRectF(), transition_a, True, "transition"),
            (QRectF(), clip, True, "clip"),
            (QRectF(), transition_b, True, "transition"),
        ])

        targets = self.qwidget_clip_module.ClipInteractionMixin._resize_targets_for_item(
            helper, transition_a, "left"
        )

        self.assertEqual([item.id for item in targets], ["T1", "C1", "T2"])

    def test_qwidget_resize_targets_tolerate_one_frame_mixed_edge_drift(self):
        Helper = self.make_qwidget_resize_target_helper()
        helper = Helper([
            (
                QRectF(),
                types.SimpleNamespace(id="T1", data={"position": 0.0, "start": 0.0, "end": 5.0}),
                True,
                "transition",
            ),
            (
                QRectF(),
                types.SimpleNamespace(id="C1", data={"position": 0.0, "start": 0.0, "end": 5.0 + (1.0 / 30.0)}),
                True,
                "clip",
            ),
        ])
        helper.fps_float = 30.0

        targets = self.qwidget_clip_module.ClipInteractionMixin._resize_targets_for_item(
            helper, helper.geometry.items[0][1], "right"
        )

        self.assertEqual([item.id for item in targets], ["T1", "C1"])

    def test_qwidget_resize_targets_reject_interior_edge_in_multi_selection(self):
        Helper = self.make_qwidget_resize_target_helper()
        left = types.SimpleNamespace(id="L", data={"position": 1.0, "start": 0.0, "end": 3.0})
        middle = types.SimpleNamespace(id="M", data={"position": 3.0, "start": 0.0, "end": 2.0})
        right = types.SimpleNamespace(id="R", data={"position": 6.0, "start": 0.0, "end": 2.0})
        helper = Helper([
            (QRectF(), left, True, "clip"),
            (QRectF(), middle, True, "clip"),
            (QRectF(), right, True, "clip"),
        ])

        targets = self.qwidget_clip_module.ClipInteractionMixin._resize_targets_for_item(
            helper, middle, "left"
        )

        self.assertEqual(targets, [])

    def test_qwidget_assign_press_target_falls_back_to_drag_for_invalid_multi_edge(self):
        helper, event_cls = self.make_qwidget_assign_press_helper(resize_items=[])
        item = types.SimpleNamespace(id="A", data={"position": 1.0, "start": 0.0, "end": 3.0})
        helper.geometry.items = [(QRectF(10.0, 10.0, 40.0, 20.0), item, True, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._assign_press_target(helper, event_cls(10.0, 20.0))

        self.assertEqual(helper._press_hit, "clip")
        self.assertIsNone(helper._resize_edge)
        self.assertEqual(helper._resize_items, [])

    def test_qwidget_assign_press_target_keeps_group_resize_for_valid_outer_edge(self):
        target_a = types.SimpleNamespace(id="A")
        target_b = types.SimpleNamespace(id="B")
        helper, event_cls = self.make_qwidget_assign_press_helper(resize_items=[target_a, target_b])
        item = types.SimpleNamespace(id="A", data={"position": 1.0, "start": 0.0, "end": 3.0})
        helper.geometry.items = [(QRectF(10.0, 10.0, 40.0, 20.0), item, True, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._assign_press_target(helper, event_cls(10.0, 20.0))

        self.assertEqual(helper._press_hit, "clip-edge")
        self.assertEqual(helper._resize_edge, "left")
        self.assertEqual([item.id for item in helper._resize_items], ["A", "B"])

    def test_qwidget_assign_press_target_accepts_exact_right_boundary_edge_hit(self):
        target = types.SimpleNamespace(id="A")
        helper, event_cls = self.make_qwidget_assign_press_helper(resize_items=[target])
        item = types.SimpleNamespace(id="A", data={"position": 1.0, "start": 0.0, "end": 3.0})
        helper.geometry.items = [(QRectF(10.0, 10.0, 40.0, 20.0), item, True, "clip")]

        self.qwidget_base_module.TimelineWidgetBase._assign_press_target(helper, event_cls(50.0, 20.0))

        self.assertEqual(helper._press_hit, "clip-edge")
        self.assertEqual(helper._resize_edge, "right")
        self.assertEqual([item.id for item in helper._resize_items], ["A"])

    def test_qwidget_assign_press_target_ignores_item_occluded_by_ruler(self):
        helper, event_cls = self.make_qwidget_assign_press_helper(resize_items=[object()])
        helper.ruler_height = 30.0
        item = types.SimpleNamespace(
            id="A", data={"position": 1.0, "start": 0.0, "end": 3.0}
        )
        helper.geometry.items = [
            (QRectF(10.0, 10.0, 40.0, 40.0), item, True, "clip")
        ]

        self.qwidget_base_module.TimelineWidgetBase._assign_press_target(
            helper, event_cls(10.0, 20.0)
        )

        self.assertEqual(helper._press_hit, "ruler")
        self.assertIsNone(helper._resizing_item)
        self.assertEqual(helper._resize_items, [])

    def test_qwidget_pending_clip_menu_release_opens_without_drag_threshold(self):
        helper = self.make_qwidget_pending_clip_menu_helper()
        clip = types.SimpleNamespace(id="C1")
        helper._clip_text_rects = [
            {"rect": QRectF(10.0, 10.0, 48.0, 18.0), "clip": clip, "open_menu": True}
        ]

        self.assertTrue(helper._begin_pending_clip_menu_click(QPointF(20.0, 20.0)))
        helper._update_pending_clip_menu_drag(QPointF(21.0, 20.0))

        opened = helper._handle_pending_clip_menu_release(QPointF(20.0, 20.0))

        self.assertTrue(opened)
        self.assertEqual(helper.selected, [("C1", "clip", True)])
        self.assertEqual(helper.menu_calls, ["C1"])

    def test_qwidget_pending_clip_menu_release_ignores_drag_motion(self):
        helper = self.make_qwidget_pending_clip_menu_helper()
        clip = types.SimpleNamespace(id="C1")
        helper._clip_text_rects = [
            {"rect": QRectF(10.0, 10.0, 48.0, 18.0), "clip": clip, "open_menu": True}
        ]

        self.assertTrue(helper._begin_pending_clip_menu_click(QPointF(20.0, 20.0)))
        helper._update_pending_clip_menu_drag(
            QPointF(20.0 + QApplication.startDragDistance(), 20.0)
        )

        opened = helper._handle_pending_clip_menu_release(
            QPointF(20.0 + QApplication.startDragDistance(), 20.0)
        )

        self.assertFalse(opened)
        self.assertEqual(helper.selected, [])
        self.assertEqual(helper.menu_calls, [])

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

        self.assertEqual(wide_increment, 15)
        self.assertEqual(medium_increment, 12)
        self.assertEqual(zoomed_increment, 1)

    def test_frame_rounding_increment_doubles_local_rounding_before_cap(self):
        painter = self.make_clip_painter(project_fps=24.0)
        increment = painter._frame_rounding_increment(24.0, 0.2)

        self.assertEqual(increment, 10)

    def test_frame_rounding_increment_keeps_tighter_rounding_for_time_mapped_clips(self):
        painter = self.make_clip_painter(project_fps=30.0)
        clip = types.SimpleNamespace(
            data={
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 52.2, "video_length": 1252},
                "time": {
                    "Points": [
                        {"co": {"X": 1, "Y": 1566}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 1567, "Y": 1}, "interpolation": openshot.LINEAR},
                    ]
                },
            }
        )

        increment = painter._frame_rounding_increment(24.0, 2.0, clip=clip, project_fps=30.0)

        self.assertEqual(increment, 6)

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
                "path": "/project/example.wav",
                "has_audio": True,
                "ui": {
                    "audio_data": [1.0, 1.0, 1.0, 1.0, 1.0],
                    "audio_data_rms": [0.4, 0.4, 0.4, 0.4, 0.4],
                    "audio_data_format": "absolute_peak_v2",
                    "audio_data_rate": 20,
                },
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
        self.assertEqual(captured[-1][1]["ui"]["audio_data_rms"], [0.2, 0.2, 0.2, 0.2])
        self.assertEqual(captured[-1][1]["ui"]["audio_data_rate"], 20)
        self.assertEqual(
            captured[-1][1]["ui"]["audio_data_format"],
            self.waveform_module.ABSOLUTE_WAVEFORM_FORMAT,
        )

    def test_legacy_waveform_format_is_default_and_keeps_linear_amplitude(self):
        waveform = self.waveform_module

        self.assertEqual(
            waveform.waveform_data_format({"audio_data": [0.1, 1.0]}),
            waveform.LEGACY_WAVEFORM_FORMAT,
        )
        self.assertEqual(
            waveform.waveform_display_amplitude(0.1, waveform.LEGACY_WAVEFORM_FORMAT),
            0.1,
        )

    def _render_test_waveform(self, audio_data, rms_data=None, width=24, height=24):
        theme = types.SimpleNamespace(
            waveform_color=QColor("#2A82DA"),
            waveform_peak_color=QColor(42, 130, 218, 128),
        )
        widget = types.SimpleNamespace(
            theme=theme,
            clip_waveform_window=lambda _clip: {
                "start_ratio": 0.0,
                "end_ratio": 1.0,
                "scale": False,
            },
        )
        ui_data = {
            "audio_data": list(audio_data),
            "audio_data_format": "absolute_peak_v2",
        }
        if rms_data is not None:
            ui_data["audio_data_rms"] = list(rms_data)
        clip = types.SimpleNamespace(data={"ui": ui_data})
        clip_painter = self.clip_paint_module.ClipPainter.__new__(
            self.clip_paint_module.ClipPainter
        )
        clip_painter.w = widget
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            self.assertTrue(
                clip_painter._draw_waveform(
                    painter, clip, QRectF(0.0, 0.0, float(width), float(height))
                )
            )
        finally:
            painter.end()
        return image

    def test_waveform_silence_draws_a_visible_center_line(self):
        image = self._render_test_waveform([0.0] * 24)
        center_y = image.height() // 2

        self.assertGreater(image.pixelColor(image.width() // 2, center_y).alpha(), 0)
        self.assertEqual(image.pixelColor(image.width() // 2, center_y - 3).alpha(), 0)

    def test_waveform_uses_solid_fill_without_artificial_peak_border(self):
        image = self._render_test_waveform([0.5] * 24)
        visible_colors = {
            image.pixelColor(x, y).rgb()
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).alpha() == 255
        }

        self.assertEqual(visible_colors, {QColor("#2A82DA").rgb()})

    def test_waveform_renders_peak_and_rms_as_distinct_envelopes(self):
        image = self._render_test_waveform([0.8] * 24, [0.2] * 24)
        alphas = {
            image.pixelColor(x, y).alpha()
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).alpha() > 0
        }

        self.assertIn(255, alphas)
        self.assertTrue(any(120 < alpha < 255 for alpha in alphas))

    def test_waveform_clip_keeps_full_height_and_uses_transparent_title(self):
        clip_painter = self.clip_paint_module.ClipPainter.__new__(
            self.clip_paint_module.ClipPainter
        )
        clip_painter.border_width = 0.0
        clip_painter.menu_margin = 4.0
        captured = {}

        def draw_waveform(_self, _painter, _clip, inner, _segment):
            captured["waveform_rect"] = QRectF(inner)
            return True

        def draw_text(_self, _painter, _clip, inner, _x, _right, **kwargs):
            captured["title_transparent"] = kwargs.get("transparent_container")
            return {"rect": QRectF(inner)}

        clip_painter._draw_waveform = types.MethodType(draw_waveform, clip_painter)
        clip_painter._draw_clip_text = types.MethodType(draw_text, clip_painter)
        clip_painter._draw_thumbnails = lambda *_args, **_kwargs: False

        image = QImage(120, 60, QImage.Format_ARGB32)
        painter = QPainter(image)
        inner = QRectF(2.0, 3.0, 116.0, 54.0)
        try:
            clip_painter._draw_clip_contents(
                painter,
                types.SimpleNamespace(data={"title": "Audio"}),
                inner,
                {"includes_start": True, "segment_width": inner.width()},
            )
        finally:
            painter.end()

        self.assertEqual(captured["waveform_rect"], inner)
        self.assertTrue(captured["title_transparent"])

    def test_waveform_density_defaults_to_legacy_rate_when_missing(self):
        waveform = self.waveform_module

        self.assertEqual(waveform.waveform_sample_rate({}), 20)
        self.assertEqual(waveform.waveform_sample_rate({"audio_data_rate": 200}), 200)

    def test_new_waveform_density_uses_timeline_preference(self):
        waveform = self.waveform_module
        app = types.SimpleNamespace(
            get_settings=lambda: types.SimpleNamespace(
                get=lambda key: 400 if key == "timeline-waveform-samples-per-second" else None
            )
        )

        with patch.object(waveform, "get_app", return_value=app):
            self.assertEqual(waveform.configured_waveform_sample_rate(), 400)

    def test_absolute_waveform_uses_fixed_root_scale_without_clip_normalization(self):
        waveform = self.waveform_module
        def display(value):
            return waveform.waveform_display_amplitude(
                value, waveform.ABSOLUTE_WAVEFORM_FORMAT
            )

        self.assertEqual(display(0.0), 0.0)
        self.assertAlmostEqual(display(1.0), 1.0)
        self.assertAlmostEqual(display(0.1), math.sqrt(0.1), places=2)
        self.assertLess(display(0.01), display(0.1))
        self.assertEqual(display(2.0), 1.0)

    def test_new_waveform_extraction_is_absolute_and_tagged(self):
        emitted = []
        extracted = types.SimpleNamespace(
            vectors=lambda: ([0.05, 0.1], [0.02, 0.04]),
            clear=lambda: None,
        )
        waveformer = types.SimpleNamespace(ExtractSamples=MagicMock(return_value=extracted))
        reader = types.SimpleNamespace(info=types.SimpleNamespace(has_audio=True))
        source_clip = types.SimpleNamespace(Reader=lambda: reader)
        file_obj = types.SimpleNamespace(
            id="F1",
            data={
                "id": "F1",
                "path": "/project/new.wav",
                "has_audio": True,
                "ui": {},
            },
        )
        app = types.SimpleNamespace(
            window=types.SimpleNamespace(
                WaitCursorSignal=types.SimpleNamespace(emit=lambda *_args: None),
                timeline=types.SimpleNamespace(
                    fileAudioDataReady=types.SimpleNamespace(
                        emit=lambda file_id, ui_data, tid: emitted.append(
                            (file_id, ui_data, tid)
                        )
                    )
                ),
            )
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.waveform_module.File, "get", return_value=file_obj))
            stack.enter_context(patch.object(self.waveform_module, "get_app", return_value=app))
            stack.enter_context(patch.object(self.waveform_module.openshot, "Clip", return_value=source_clip))
            stack.enter_context(patch.object(self.waveform_module.openshot, "AudioWaveformer", return_value=waveformer))
            self.waveform_module.get_waveform_thread("F1", [], "wf-new-1")

        waveformer.ExtractSamples.assert_called_once_with(
            -1, self.waveform_module.SAMPLES_PER_SECOND, False
        )
        completed = [payload for _, payload, _ in emitted if payload["ui"].get("audio_data")]
        self.assertEqual(completed[0]["ui"]["audio_data"], [0.05, 0.1])
        self.assertEqual(completed[0]["ui"]["audio_data_rms"], [0.02, 0.04])
        self.assertEqual(completed[0]["ui"]["audio_data_rate"], 200)
        self.assertEqual(
            completed[0]["ui"]["audio_data_format"],
            self.waveform_module.ABSOLUTE_WAVEFORM_FORMAT,
        )

    def test_clip_audio_data_ready_preserves_existing_waveform_when_pending_samples_are_none(self):
        helper = types.SimpleNamespace(
            clip_painter=types.SimpleNamespace(clear_cache=lambda: None),
            update=lambda: None,
            get_uuid=lambda: "wf-new",
        )
        clip = types.SimpleNamespace(
            id="C1",
            data={"ui": {
                "audio_data": [0.2, 0.4],
                "audio_data_format": "normalized_peak_v1",
                "waveform_token": "wf-old",
            }},
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
        self.assertEqual(clip.data["ui"]["audio_data_format"], "normalized_peak_v1")
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

        self.assertEqual(frames, [25, 61])

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

        self.assertEqual(frames, [25, 37])

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

        self.assertEqual(frames, [48, 13])

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

        self.assertEqual(frames, [84, 49])

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

        self.assertEqual(frames[:2], [1169, 989])
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

        self.assertEqual(frames, [1175, 1025, 875, 719, 570, 420, 264, 114, 18])

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

    def test_build_thumbnail_slots_entire_style_uses_pixel_stable_geometry(self):
        pixels_per_second = 23.8
        painter = self.make_clip_painter(
            thumbnail_style="entire",
            pixels_per_second=pixels_per_second,
            project_fps=24.0,
        )
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 12.0,
                "duration": 12.0,
                "position": 0.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 12.0},
            },
        )
        inner = self.clip_paint_module.QRectF(
            0.0,
            0.0,
            12.0 * pixels_per_second,
            40.0,
        )
        segment = {
            "offset_seconds": 0.0,
            "duration_seconds": 12.0,
            "clip_duration": 12.0,
            "segment_width": 12.0 * pixels_per_second,
            "clip_width": 12.0 * pixels_per_second,
            "includes_start": True,
            "includes_end": True,
        }
        timing = painter._segment_timing(segment, 12.0)

        slots, _interval = painter._build_thumbnail_slots(clip, inner, segment, "entire", timing)
        rects = [
            rect
            for _slot_start, rect in slots
            if rect.x() >= 0.0 and rect.right() <= inner.right()
        ]
        spacings = [
            round(rects[index + 1].x() - rects[index].x(), 6)
            for index in range(len(rects) - 1)
        ]

        self.assertGreaterEqual(len(spacings), 2)
        self.assertTrue(
            all(
                math.isclose(spacing, rects[0].width(), abs_tol=1e-6)
                for spacing in spacings
            )
        )

    def test_expire_thumbnail_requests_clears_edge_slot_fallback_cache(self):
        painter = self.make_clip_painter(thumbnail_style="entire", pixels_per_second=24.0, project_fps=24.0)
        painter._thumb_pending = {
            ("C1", 1): 3,
            ("C1", 30): 4,
        }
        painter._thumb_regions = {
            ("C1", 1): self.clip_paint_module.QRectF(0.0, 0.0, 48.0, 36.0),
            ("C1", 30): self.clip_paint_module.QRectF(48.0, 0.0, 48.0, 36.0),
        }
        painter._thumb_missing_logged = {("C1", 1), ("C1", 30)}
        painter._slot_fallback_cache = {
            ("C1", "edge-start"): object(),
            ("C1", "edge-end"): object(),
        }

        painter.expire_thumbnail_requests(4)

        self.assertNotIn(("C1", 1), painter._thumb_pending)
        self.assertIn(("C1", 30), painter._thumb_pending)
        self.assertEqual(painter._slot_fallback_cache, {})

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

    def test_draw_thumbnails_entire_style_partial_leading_slot_uses_visible_center_sampling(self):
        painter = self.make_clip_painter(thumbnail_style="entire", pixels_per_second=24.0, project_fps=24.0)
        clip = types.SimpleNamespace(
            id="C1",
            data={
                "file_id": "F1",
                "start": 0.0,
                "end": 4.0,
                "duration": 4.0,
                "position": 0.0,
                "reader": {"fps": {"num": 24, "den": 1}, "duration": 4.0},
            },
        )
        frames = []

        def fake_get_thumbnail_pixmap(_self, _clip, clip_key, file_id, frame, rect, generation, allow_request=True):
            frames.append(frame)
            return None

        painter._get_thumbnail_pixmap = types.MethodType(fake_get_thumbnail_pixmap, painter)
        painter._frame_rounding_increment = lambda *args, **kwargs: 1
        inner = self.clip_paint_module.QRectF(0, 0, 72.0, 40)
        segment = {
            "segment_width": 72.0,
            "clip_width": 96.0,
            "offset_seconds": 0.25,
            "duration_seconds": 3.0,
            "clip_duration": 4.0,
            "includes_start": False,
            "includes_end": False,
        }

        painter._draw_thumbnails(None, clip, inner, segment)

        self.assertGreaterEqual(len(frames), 1)
        self.assertEqual(frames[0], 28)

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

    def test_clear_render_cache_preserves_loaded_thumbnail_pixmaps(self):
        painter = self.make_clip_painter()
        thumb = self.clip_paint_module.QPixmap(48, 36)
        thumb.fill(QColor("blue"))
        painter.thumb_cache[("C1", 25)] = thumb
        painter.clip_cache[("C1", 72, 40, None, 1.0, 0.0, 3.0, True, True)] = ("cached", 0.0, [], False, None)
        painter._retime_preview_cache["C1"] = {"pix": thumb, "blur": 0.0}

        painter.clear_render_cache()

        self.assertEqual(painter.clip_cache, {})
        self.assertIn(("C1", 25), painter.thumb_cache)
        self.assertEqual(painter._retime_preview_cache, {})

    def test_existing_thumb_path_reuses_rounded_cached_thumbnail(self):
        painter = self.make_clip_painter()
        thumbnail_root = "/project_assets/thumbs"
        rounded_path = os.path.join(thumbnail_root, "F1", "19.png")

        with ExitStack() as stack:
            stack.enter_context(patch.object(info, "THUMBNAIL_PATH", thumbnail_root))
            stack.enter_context(
                patch.object(
                    self.clip_paint_module.os.path,
                    "exists",
                    side_effect=lambda path: path == rounded_path,
                )
            )
            path = painter._existing_thumb_path("F1", 20, fps=24.0)

        self.assertEqual(path, rounded_path)

    def test_qwidget_changed_preserves_loaded_thumbnail_pixmaps(self):
        helper = types.SimpleNamespace()
        helper.fps_float = 24.0
        helper.win = types.SimpleNamespace(_trim_refresh_pending=False)
        thumb = self.clip_paint_module.QPixmap(48, 36)
        thumb.fill(QColor("green"))
        helper.clip_painter = self.make_clip_painter()
        helper.clip_painter.thumb_cache[("C1", 1)] = thumb
        helper.transition_painter = types.SimpleNamespace(clear_cache=lambda: None)
        helper.geometry = types.SimpleNamespace(mark_dirty=lambda: None, ensure=lambda: None, track_list=[])
        helper._dragging_panel_keyframes = False
        helper._dragging_keyframe = False
        helper._update_track_panel_properties = lambda: None
        helper._keyframes_dirty = False
        helper._snap_keyframe_seconds = []
        helper._pending_clip_overrides = {}
        helper._pending_transition_overrides = {}
        helper._preserve_overrides_once = False
        helper._preserve_overrides_during_batch = False
        helper._suspend_changed_update = 1
        helper.update = lambda: None

        app = types.SimpleNamespace(project=types.SimpleNamespace(get=lambda key: {"num": 24, "den": 1} if key == "fps" else None))
        with patch.object(self.qwidget_base_module, "get_app", return_value=app):
            self.qwidget_base_module.TimelineWidgetBase.changed(helper, None)

        self.assertIn(("C1", 1), helper.clip_painter.thumb_cache)

    def test_reset_drag_preview_invalidates_preview_clip_cache(self):
        invalidated = []

        def invalidate_clip_thumbnails(clip_id):
            invalidated.append(clip_id)

        helper = types.SimpleNamespace(
            clip_painter=types.SimpleNamespace(
                invalidate_clip_thumbnails=invalidate_clip_thumbnails
            ),
            _drag_preview_items=[
                {"type": "clip", "source_id": "F1"},
                {"type": "clip", "model": types.SimpleNamespace(id="preview-clip-F2")},
                {"type": "transition", "source_id": "T1"},
            ],
            _drag_payload={"type": "clip", "ids": ["F1"]},
            item_ids=["preview-1"],
            new_item=True,
            item_type="clip",
            drag_bbox=self.clip_paint_module.QRectF(1.0, 2.0, 3.0, 4.0),
            _set_drag_preview_thumbnail_suspension=lambda enabled: None,
            update=lambda: None,
        )
        helper._invalidate_drag_preview_cache = lambda: self.qwidget_base_module.TimelineWidgetBase._invalidate_drag_preview_cache(helper)

        self.qwidget_base_module.TimelineWidgetBase._reset_drag_preview(helper)

        self.assertEqual(invalidated, ["preview-clip-F1", "preview-clip-F2"])
        self.assertEqual(helper._drag_preview_items, [])
        self.assertEqual(helper._drag_payload, None)
        self.assertEqual(helper.item_ids, [])
        self.assertFalse(helper.new_item)
        self.assertIsNone(helper.item_type)
        self.assertTrue(helper.drag_bbox.isNull())

    def test_thumbnail_updated_invalidates_only_qwidget_clip_cache(self):
        invalidated = []
        thumb_requests = []
        updates = []
        run_js_calls = []

        def invalidate_clip_thumbnails(clip_id):
            invalidated.append(clip_id)

        def run_js(code):
            run_js_calls.append(code)

        clip = types.SimpleNamespace(id="C1", data={"file_id": "F1"})
        helper = types.SimpleNamespace(
            clip_painter=types.SimpleNamespace(
                invalidate_clip_thumbnails=invalidate_clip_thumbnails
            ),
            update=lambda: updates.append(True),
            run_js=run_js,
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module, "ViewClass", self.timeline_module.TimelineWidget))
            stack.enter_context(patch.object(self.timeline_module.Clip, "filter", return_value=[clip]))
            stack.enter_context(
                patch.object(
                    self.timeline_module,
                    "GetThumbPath",
                    side_effect=lambda file_id, frame, clear_cache=False: thumb_requests.append(
                        (file_id, frame, clear_cache)
                    ),
                )
            )
            self.timeline_module.TimelineView.Thumbnail_Updated(helper, "C1", 1)

        self.assertEqual(thumb_requests, [("F1", 1, True)])
        self.assertEqual(invalidated, ["C1"])
        self.assertEqual(updates, [True])
        self.assertEqual(run_js_calls, [])

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

    def test_qwidget_snap_trim_delta_accepts_explicit_initial_context(self):
        helper = self.make_qwidget_clip_helper()
        snap_calls = []
        helper.snap = types.SimpleNamespace(
            snap_edge=lambda edge_sec, delta: snap_calls.append((edge_sec, delta)) or (delta + 0.25)
        )

        result = self.qwidget_clip_module.ClipInteractionMixin._snap_trim_delta(
            helper,
            1.5,
            edge="right",
            initial={"position": 2.0, "start": 1.0, "end": 4.0},
        )

        self.assertEqual(snap_calls, [(5.0, 1.5)])
        self.assertEqual(result, 1.75)

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

    def test_qwidget_drag_enter_prefers_internal_clip_mime_over_urls(self):
        helper = types.SimpleNamespace(
            _drag_payload=None,
            item_type=None,
            new_item=None,
        )
        preimport_calls = []

        def _preimport(urls):
            preimport_calls.append(list(urls))
            return {"type": "clip", "ids": ["wrong"]}

        helper._preimport_os_drop_urls = _preimport

        mime = types.SimpleNamespace(
            html=lambda: "clip",
            text=lambda: '["F1","F2","F3","F4"]',
            hasUrls=lambda: True,
            urls=lambda: ["file:///mock-media/a.mp4", "file:///mock-media/b.mp4"],
        )
        accepted = []
        event = types.SimpleNamespace(
            mimeData=lambda: mime,
            accept=lambda: accepted.append(True),
            ignore=lambda: accepted.append(False),
        )

        self.qwidget_base_module.TimelineWidgetBase.dragEnterEvent(helper, event)

        self.assertEqual(preimport_calls, [])
        self.assertEqual(helper.item_type, "clip")
        self.assertTrue(helper.new_item)
        self.assertEqual(helper._drag_payload, {"type": "clip", "ids": ["F1", "F2", "F3", "F4"]})
        self.assertEqual(accepted, [True])

    def test_qwidget_ensure_drag_payload_prefers_internal_clip_mime_over_urls(self):
        helper = types.SimpleNamespace(
            _drag_payload=None,
            item_type=None,
            new_item=None,
        )
        preimport_calls = []

        def _preimport(urls):
            preimport_calls.append(list(urls))
            return {"type": "clip", "ids": ["wrong"]}

        helper._preimport_os_drop_urls = _preimport

        mime = types.SimpleNamespace(
            html=lambda: "clip",
            text=lambda: '["F1","F2"]',
            hasUrls=lambda: True,
            urls=lambda: ["file:///mock-media/a.mp4"],
        )
        event = types.SimpleNamespace(mimeData=lambda: mime)

        payload = self.qwidget_base_module.TimelineWidgetBase._ensure_drag_payload_from_event(helper, event)

        self.assertEqual(preimport_calls, [])
        self.assertEqual(payload, {"type": "clip", "ids": ["F1", "F2"]})
        self.assertEqual(helper._drag_payload, {"type": "clip", "ids": ["F1", "F2"]})

    def test_qwidget_paste_uses_saved_timeline_context_menu_target(self):
        pasted = []
        helper = types.SimpleNamespace(
            _context_menu_paste_data={"position": 12.5, "track": 4},
            _handle_paste_callback=lambda clip_ids, tran_ids, data: pasted.append(
                (list(clip_ids), list(tran_ids), dict(data))
            ),
            context_menu_cursor_position=None,
        )

        self.timeline_module.TimelineView.Paste_Triggered(helper, "paste", [], [])

        self.assertEqual(pasted, [([], [], {"position": 12.5, "track": 4})])
        self.assertIsNone(helper._context_menu_paste_data)

    def test_handle_paste_callback_extends_project_duration_for_inserted_items(self):
        saved = []
        inserted_clip = None

        class FakeClip:
            def __init__(self, clip_id, data):
                self.id = clip_id
                self.type = "copy"
                self.data = data

        def save_inserted_clip():
            inserted_clip.id = "C1-copy"
            inserted_clip.data["id"] = "C1-copy"
            saved.append(copy.deepcopy(inserted_clip.data))

        def clipboard_stub():
            return types.SimpleNamespace(mimeData=object)

        inserted_clip = FakeClip(
            "C1",
            {"id": "C1", "position": 5.0, "layer": 2, "start": 0.0, "end": 4.0},
        )
        inserted_clip.save = save_inserted_clip
        copied_objects = [inserted_clip]
        ensured_layers = []
        app = types.SimpleNamespace(
            clipboard=clipboard_stub,
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(ensure_tracks_for_layers=lambda layers: ensured_layers.extend(layers)),
        )
        helper = types.SimpleNamespace(
            get_uuid=lambda: "tx-paste-1",
            _assign_new_effect_ids=lambda data: self.timeline_module.TimelineView._assign_new_effect_ids(helper, data),
            _extend_timeline_to_fit_items_calls=[],
            _select_inserted_paste_items_calls=[],
        )
        helper._extend_timeline_to_fit_items = lambda: helper._extend_timeline_to_fit_items_calls.append(True)
        helper._select_inserted_paste_items = lambda items: helper._select_inserted_paste_items_calls.append(list(items))

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    self.timeline_module.ClipboardManager,
                    "from_mime",
                    return_value=copied_objects,
                )
            )
            stack.enter_context(patch.object(self.timeline_module, "Clip", FakeClip))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            self.timeline_module.TimelineView._handle_paste_callback(
                helper,
                [],
                [],
                {"position": 20.0, "track": 4},
            )

        self.assertEqual(saved, [{"id": "C1-copy", "position": 20.0, "layer": 4, "start": 0.0, "end": 4.0}])
        self.assertEqual(ensured_layers, [4])
        self.assertEqual(helper._extend_timeline_to_fit_items_calls, [True])
        self.assertEqual(helper._select_inserted_paste_items_calls, [[("C1-copy", "clip")]])
        self.assertIsNone(app.updates.transaction_id)

    def test_handle_paste_callback_maps_multitrack_selection_downward(self):
        saved = []

        class FakeClip:
            def __init__(self, clip_id, data):
                self.id = clip_id
                self.type = "copy"
                self.data = data

            def save(self):
                self.id = "%s-copy" % self.data["title"]
                self.data["id"] = self.id
                saved.append(copy.deepcopy(self.data))

        def clipboard_stub():
            return types.SimpleNamespace(mimeData=object)

        copied_objects = [
            FakeClip("top", {"id": "top", "title": "top", "position": 5.0, "layer": 3000000, "start": 0.0, "end": 4.0}),
            FakeClip("mid", {"id": "mid", "title": "mid", "position": 5.0, "layer": 2000000, "start": 0.0, "end": 4.0}),
            FakeClip("bot", {"id": "bot", "title": "bot", "position": 5.0, "layer": 1000000, "start": 0.0, "end": 4.0}),
        ]
        ensured_layers = []
        app = types.SimpleNamespace(
            clipboard=clipboard_stub,
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(
                track_stack_from=lambda layer, count: [1000000, 500000, 250000][:count],
                ensure_tracks_for_layers=lambda layers: ensured_layers.extend(layers),
            ),
        )
        helper = types.SimpleNamespace(
            get_uuid=lambda: "tx-paste-2",
            _assign_new_effect_ids=lambda data: self.timeline_module.TimelineView._assign_new_effect_ids(helper, data),
            _extend_timeline_to_fit_items_calls=[],
            _select_inserted_paste_items_calls=[],
        )
        helper._extend_timeline_to_fit_items = lambda: helper._extend_timeline_to_fit_items_calls.append(True)
        helper._select_inserted_paste_items = lambda items: helper._select_inserted_paste_items_calls.append(list(items))

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.timeline_module.ClipboardManager, "from_mime", return_value=copied_objects))
            stack.enter_context(patch.object(self.timeline_module, "Clip", FakeClip))
            stack.enter_context(patch.object(self.timeline_module, "get_app", return_value=app))
            self.timeline_module.TimelineView._handle_paste_callback(
                helper,
                [],
                [],
                {"position": 20.0, "track": 1000000},
            )

        self.assertEqual([item["layer"] for item in saved], [1000000, 500000, 250000])
        self.assertEqual(ensured_layers, [1000000, 500000, 250000])
        self.assertEqual(helper._extend_timeline_to_fit_items_calls, [True])
        self.assertIsNone(app.updates.transaction_id)

    def test_qwidget_paste_coordinates_uses_viewport_adjusted_tracks(self):
        helper = types.SimpleNamespace(
            _seconds_from_x=lambda x: float(x) / 10.0,
            geometry=types.SimpleNamespace(
                ensure=lambda: None,
                iter_tracks=lambda: iter(
                    [
                        (
                            QRectF(0.0, 0.0, 500.0, 40.0),
                            types.SimpleNamespace(data={"number": 7}),
                            QRectF(),
                        ),
                        (
                            QRectF(0.0, 40.0, 500.0, 40.0),
                            types.SimpleNamespace(data={"number": 6}),
                            QRectF(),
                        ),
                    ]
                ),
                track_rects=[
                    (
                        QRectF(0.0, 120.0, 500.0, 40.0),
                        types.SimpleNamespace(data={"number": 7}),
                        QRectF(),
                    ),
                    (
                        QRectF(0.0, 160.0, 500.0, 40.0),
                        types.SimpleNamespace(data={"number": 6}),
                        QRectF(),
                    ),
                ],
            ),
            window=types.SimpleNamespace(selected_tracks=[]),
        )

        seconds, track_number = self.timeline_module.TimelineView._qwidget_paste_coordinates(
            helper,
            QPointF(150.0, 20.0),
            [],
            [],
        )

        self.assertEqual(seconds, 15.0)
        self.assertEqual(track_number, 7)

    # ---------------------------------------------------------------------------
    # Keyframe context menu helpers (_set_keyframe_interpolation_at_path,
    # _apply_keyframe_interpolation, _apply_keyframe_remove)
    # ---------------------------------------------------------------------------

    def make_keyframe_interp_helper(self):
        """Minimal KeyframeMixin subclass for interpolation/remove tests."""
        qwidget_keyframe_module = self.qwidget_keyframe_module

        class Helper(qwidget_keyframe_module.KeyframeMixin):
            def __init__(self):
                self._pending_clip_overrides = {}
                self._pending_transition_overrides = {}
                self._panel_selected_keyframes = {}
                self._active_keyframe_marker = None
                self._press_keyframe = None
                self._dragging_keyframe = None
                self._dragging_panel_keyframes = None
                self._snap_keyframe_seconds = []
                self._keyframes_dirty = False
                self.update_calls = 0
                self.cleanup_calls = 0
                self.geometry = types.SimpleNamespace(
                    mark_dirty=lambda: None,
                )
                self.win = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        update_clip_data=lambda data, **_kw: self.clip_updates.append(
                            copy.deepcopy(data)
                        ),
                        update_transition_data=lambda data, **_kw: self.transition_updates.append(
                            copy.deepcopy(data)
                        ),
                    )
                )
                self.clip_updates = []
                self.transition_updates = []

            def _clear_panel_selection(self, arg):
                self.cleanup_calls += 1

            def _update_track_panel_properties(self):
                pass

            def update(self):
                self.update_calls += 1

        return Helper()

    def _make_clip_data_with_keyframe(self, frame=25, interpolation=0):
        return {
            "id": "C1",
            "volume": {
                "Points": [
                    {
                        "co": {"X": frame, "Y": 1.0},
                        "interpolation": interpolation,
                        "handle_left": {"X": 0.25, "Y": 0.1},
                        "handle_right": {"X": 0.25, "Y": 1.0},
                    }
                ]
            },
        }

    def test_set_keyframe_interpolation_at_path_bezier_sets_handles(self):
        helper = self.make_keyframe_interp_helper()
        data = self._make_clip_data_with_keyframe(frame=25, interpolation=1)
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))
        preset = (0.42, 0.0, 0.58, 1.0, "Ease In/Out")

        result = helper._set_keyframe_interpolation_at_path(data, path, 0, preset)

        self.assertTrue(result)
        pt = data["volume"]["Points"][0]
        self.assertEqual(pt["interpolation"], 0)
        self.assertAlmostEqual(pt["handle_right"]["X"], 0.42)
        self.assertAlmostEqual(pt["handle_right"]["Y"], 0.0)
        self.assertAlmostEqual(pt["handle_left"]["X"], 0.58)
        self.assertAlmostEqual(pt["handle_left"]["Y"], 1.0)

    def test_set_keyframe_interpolation_at_path_linear_removes_handles(self):
        helper = self.make_keyframe_interp_helper()
        data = self._make_clip_data_with_keyframe(frame=25, interpolation=0)
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))

        result = helper._set_keyframe_interpolation_at_path(data, path, 1, None)

        self.assertTrue(result)
        pt = data["volume"]["Points"][0]
        self.assertEqual(pt["interpolation"], 1)
        self.assertNotIn("handle_left", pt)
        self.assertNotIn("handle_right", pt)

    def test_set_keyframe_interpolation_at_path_constant_removes_handles(self):
        helper = self.make_keyframe_interp_helper()
        data = self._make_clip_data_with_keyframe(frame=25, interpolation=0)
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))

        result = helper._set_keyframe_interpolation_at_path(data, path, 2, None)

        self.assertTrue(result)
        pt = data["volume"]["Points"][0]
        self.assertEqual(pt["interpolation"], 2)
        self.assertNotIn("handle_left", pt)
        self.assertNotIn("handle_right", pt)

    def test_set_keyframe_interpolation_at_path_returns_false_for_invalid_path(self):
        helper = self.make_keyframe_interp_helper()
        data = {"volume": {"Points": []}}
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))

        result = helper._set_keyframe_interpolation_at_path(data, path, 1, None)

        self.assertFalse(result)

    def test_apply_keyframe_interpolation_updates_clip_from_marker(self):
        helper = self.make_keyframe_interp_helper()
        clip_data = self._make_clip_data_with_keyframe(frame=25, interpolation=0)
        clip = types.SimpleNamespace(id="C1", data=clip_data)
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))
        marker = {
            "type": "clip",
            "object_type": "clip",
            "object_id": "C1",
            "clip": clip,
            "data_paths": (path,),
        }

        helper._apply_keyframe_interpolation(1, None, marker, [])

        self.assertEqual(len(helper.clip_updates), 1)
        pt = helper.clip_updates[0]["volume"]["Points"][0]
        self.assertEqual(pt["interpolation"], 1)
        self.assertNotIn("handle_left", pt)

    def test_apply_keyframe_interpolation_updates_clip_from_panel_targets(self):
        helper = self.make_keyframe_interp_helper()
        clip_data = self._make_clip_data_with_keyframe(frame=25, interpolation=0)
        clip = types.SimpleNamespace(id="C1", data=clip_data)
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))
        panel_targets = [{
            "owner_type": "clip",
            "object_id": "C1",
            "clip": clip,
            "transition": None,
            "paths": {path},
        }]

        helper._apply_keyframe_interpolation(2, None, None, panel_targets)

        self.assertEqual(len(helper.clip_updates), 1)
        pt = helper.clip_updates[0]["volume"]["Points"][0]
        self.assertEqual(pt["interpolation"], 2)

    def test_apply_keyframe_interpolation_updates_transition_from_panel_targets(self):
        helper = self.make_keyframe_interp_helper()
        trans_data = {
            "id": "T1",
            "brightness": {
                "Points": [
                    {
                        "co": {"X": 10, "Y": 0.5},
                        "interpolation": 1,
                    }
                ]
            },
        }
        trans = types.SimpleNamespace(id="T1", data=trans_data)
        path = (("dict", "brightness"), ("dict", "Points"), ("list", 0))
        panel_targets = [{
            "owner_type": "transition",
            "object_id": "T1",
            "clip": None,
            "transition": trans,
            "paths": {path},
        }]
        preset = (0.42, 0.0, 0.58, 1.0, "Ease In/Out")

        helper._apply_keyframe_interpolation(0, preset, None, panel_targets)

        self.assertEqual(len(helper.transition_updates), 1)
        pt = helper.transition_updates[0]["brightness"]["Points"][0]
        self.assertEqual(pt["interpolation"], 0)
        self.assertAlmostEqual(pt["handle_right"]["X"], 0.42)

    def test_apply_keyframe_remove_panel_targets_updates_clip_and_cleans_up(self):
        helper = self.make_keyframe_interp_helper()
        clip_data = self._make_clip_data_with_keyframe(frame=25, interpolation=1)
        clip = types.SimpleNamespace(id="C1", data=clip_data)
        path = (("dict", "volume"), ("dict", "Points"), ("list", 0))
        panel_targets = [{
            "owner_type": "clip",
            "object_id": "C1",
            "clip": clip,
            "transition": None,
            "paths": {path},
        }]

        helper._apply_keyframe_remove(None, panel_targets)

        self.assertEqual(len(helper.clip_updates), 1)
        self.assertEqual(helper.clip_updates[0]["volume"]["Points"], [])
        self.assertIsNone(helper._active_keyframe_marker)
        self.assertEqual(helper.cleanup_calls, 1)
        self.assertTrue(helper._keyframes_dirty)

    def test_keyframe_bezier_presets_returns_28_entries(self):
        helper = self.make_keyframe_interp_helper()
        presets = helper._keyframe_bezier_presets()
        self.assertEqual(len(presets), 28)
        for preset in presets:
            self.assertEqual(len(preset), 5)
            self.assertIsInstance(preset[4], str)

    def test_video_clip_with_audio_can_toggle_waveform(self):
        helper = types.SimpleNamespace()
        clip = types.SimpleNamespace(data={"reader": {"has_video": True, "has_audio": True}})

        self.assertTrue(self.timeline_module.TimelineView._clip_has_audio(helper, clip))

    def test_video_clip_without_audio_cannot_toggle_waveform(self):
        helper = types.SimpleNamespace()
        clip = types.SimpleNamespace(data={"reader": {"has_video": True, "has_audio": False}})

        self.assertFalse(self.timeline_module.TimelineView._clip_has_audio(helper, clip))

    def test_film_grain_trigger_adds_preset_effect(self):
        timeline_module = self.timeline_module
        clip = types.SimpleNamespace(id="C1", data={
            "id": "C1",
            "reader": {"has_video": True},
            "effects": [],
        })

        class Helper:
            def __init__(self):
                self.updates = []

            def _clip_has_video(self, candidate):
                return timeline_module.TimelineView._clip_has_video(self, candidate)

            def _clip_has_visual(self, candidate):
                return timeline_module.TimelineView._clip_has_visual(self, candidate)

            def _create_film_grain_effect_json(self):
                return {"class_name": "FilmGrain", "id": "FG-1", "seed": 77}

            def update_clip_data(self, clip_data, **kwargs):
                self.updates.append((copy.deepcopy(clip_data), dict(kwargs)))

        history = []
        fake_app = types.SimpleNamespace(
            updates=types.SimpleNamespace(
                apply_last_action_to_history=lambda original: history.append(copy.deepcopy(original))
            )
        )
        helper = Helper()

        with patch.object(timeline_module.Clip, "get", return_value=clip), \
             patch.object(timeline_module, "get_app", return_value=fake_app):
            timeline_module.TimelineView.Film_Grain_Triggered(
                helper,
                timeline_module.FILM_GRAIN_PRESET_SUPER_8,
                ["C1"],
            )

        self.assertEqual(len(clip.data["effects"]), 1)
        effect = clip.data["effects"][0]
        self.assertEqual(effect["class_name"], "FilmGrain")
        self.assertEqual(effect["id"], "FG-1")
        self.assertEqual(effect["seed"], 77)
        self.assertEqual(effect["amount"]["Points"][0]["co"]["Y"], 0.62)
        self.assertEqual(effect["size"]["Points"][0]["co"]["Y"], 0.72)
        self.assertEqual(len(helper.updates), 1)
        self.assertEqual(helper.updates[0][1], {"only_basic_props": False, "ignore_reader": True})
        self.assertEqual(len(history), 1)

    def test_film_grain_trigger_replaces_duplicate_existing_effects(self):
        timeline_module = self.timeline_module
        clip = types.SimpleNamespace(id="C1", data={
            "id": "C1",
            "reader": {"has_video": True},
            "effects": [
                {"class_name": "FilmGrain", "id": "KEEP", "order": 3, "seed": 222},
                {"class_name": "FilmGrain", "id": "DROP", "seed": 333},
            ],
        })

        class Helper:
            def __init__(self):
                self.updates = []

            def _clip_has_video(self, candidate):
                return timeline_module.TimelineView._clip_has_video(self, candidate)

            def _clip_has_visual(self, candidate):
                return timeline_module.TimelineView._clip_has_visual(self, candidate)

            def update_clip_data(self, clip_data, **kwargs):
                self.updates.append(copy.deepcopy(clip_data))

        fake_app = types.SimpleNamespace(
            updates=types.SimpleNamespace(apply_last_action_to_history=lambda _original: None)
        )
        helper = Helper()

        with patch.object(timeline_module.Clip, "get", return_value=clip), \
             patch.object(timeline_module, "get_app", return_value=fake_app):
            timeline_module.TimelineView.Film_Grain_Triggered(
                helper,
                timeline_module.FILM_GRAIN_PRESET_35MM_FINE,
                ["C1"],
            )

        self.assertEqual(len(clip.data["effects"]), 1)
        effect = clip.data["effects"][0]
        self.assertEqual(effect["id"], "KEEP")
        self.assertEqual(effect["order"], 3)
        self.assertEqual(effect["seed"], 222)
        self.assertEqual(effect["amount"]["Points"][0]["co"]["Y"], 0.14)

    def test_film_grain_trigger_none_removes_existing_effects(self):
        timeline_module = self.timeline_module
        clip = types.SimpleNamespace(id="C1", data={
            "id": "C1",
            "reader": {"has_video": True},
            "effects": [
                {"class_name": "FilmGrain", "id": "FG-1"},
                {"class_name": "Brightness", "id": "B-1"},
                {"class_name": "FilmGrain", "id": "FG-2"},
            ],
        })

        class Helper:
            def __init__(self):
                self.updates = []

            def _clip_has_video(self, candidate):
                return timeline_module.TimelineView._clip_has_video(self, candidate)

            def _clip_has_visual(self, candidate):
                return timeline_module.TimelineView._clip_has_visual(self, candidate)

            def update_clip_data(self, clip_data, **kwargs):
                self.updates.append((copy.deepcopy(clip_data), dict(kwargs)))

        history = []
        fake_app = types.SimpleNamespace(
            updates=types.SimpleNamespace(
                apply_last_action_to_history=lambda original: history.append(copy.deepcopy(original))
            )
        )
        helper = Helper()

        with patch.object(timeline_module.Clip, "get", return_value=clip), \
             patch.object(timeline_module, "get_app", return_value=fake_app):
            timeline_module.TimelineView.Film_Grain_Triggered(
                helper,
                timeline_module.FILM_GRAIN_PRESET_NONE,
                ["C1"],
            )

        self.assertEqual(clip.data["effects"], [{"class_name": "Brightness", "id": "B-1"}])
        self.assertEqual(len(helper.updates), 1)
        self.assertEqual(len(history), 1)
