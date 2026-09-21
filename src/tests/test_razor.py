"""Frame-accurate razor feedback and temporary preview lifecycle regressions."""

import threading
import types
import unittest
from unittest.mock import patch

import openshot
from qt_api import QApplication, QColor, QEvent, QEventLoop, QImage, QKeyEvent, QPainter, QPointF, QRectF, Qt, QTimer, QToolTip, QWidget
from classes.app import get_app
from tests.qt_test_app import get_or_create_app, ensure_app_state
from windows.preview_thread import PlayerWorker
from windows.views.timeline_backend.qwidget.razor import RazorMixin
from windows.views.timeline_backend.qwidget.base import TimelineWidgetBase
from windows.views.timeline_backend.snap import SnapHelper


class RazorWidget(RazorMixin, QWidget):
    def __init__(self, fps=30.0):
        super().__init__()
        self.resize(900, 250)
        self.enable_razor = True
        self.enable_snapping = False
        self._snap_keyframe_seconds = []
        self.keyframe_times = []
        self.track_name_width = 100
        self.ruler_height = 30
        self.scroll_bar_thickness = 10
        self.pixels_per_second = 100.0
        self.h_scroll_offset = 0.0
        self.fps_float = fps
        self.current_frame = 61
        self.playing = False
        self.locked = False
        self.clip = types.SimpleNamespace(id="C1", data={
            "position": 0.0, "start": 5.0, "end": 12.0, "layer": 1,
        })
        self.items = [(QRectF(100, 50, 700, 80), self.clip, False, "clip")]
        self.geometry = types.SimpleNamespace(
            ensure=lambda: None, iter_items=lambda **kwargs: self.items,
            iter_clips=lambda **kwargs: [(r.translated(self.h_scroll_offset, 0), obj, sel)
                                        for r, obj, sel, kind in self.items if kind == "clip"],
            iter_transitions=lambda **kwargs: [(r.translated(self.h_scroll_offset, 0), obj, sel)
                                              for r, obj, sel, kind in self.items if kind == "transition"],
            marker_rects=[],
        )
        self.snap = SnapHelper(self, self.geometry)
        self.previews = []
        self.seeks = []
        worker = types.SimpleNamespace(
            queue_razor_preview=lambda *args: self.previews.append(args) or True,
            queue_seek=lambda *args: self.seeks.append(args),
        )
        self.source_previews = []

        def preview_source(item_id, frame, restore_frame, kind):
            self.source_previews.append((item_id, frame, restore_frame, kind))
            self.previews.append((frame, restore_frame))
            return True

        self.win = types.SimpleNamespace(
            preview_thread=worker, timeline=types.SimpleNamespace(PreviewRazorFrame=preview_source)
        )
        self._init_razor()

    def _snap_time(self, seconds):
        return round(seconds * self.fps_float) / self.fps_float

    def _seconds_from_x(self, x):
        return (x - self.track_name_width + self.h_scroll_offset) / self.pixels_per_second

    def _update_snap_keyframe_targets(self, item):
        self._snap_keyframe_seconds = list(self.keyframe_times)

    def _is_track_locked(self, layer):
        return self.locked

    def _is_playing(self):
        return self.playing

    def setRazorMode(self, enabled):
        self.enable_razor = enabled
        if not enabled:
            self._clear_razor_hover()


class RazorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.owns_app = get_or_create_app(lambda: QApplication([]))
        ensure_app_state(cls.app, dict)

    def test_cut_preview_and_callback_agree_at_fractional_fps_and_zoom(self):
        for fps in (24.0, 30000 / 1001, 60.0):
            widget = RazorWidget(fps)
            for zoom in (100.0, 731.5):
                widget.pixels_per_second = zoom
                widget.h_scroll_offset = zoom * 1.25
                for modifier, extra_frame in ((Qt.NoModifier, 0), (Qt.ShiftModifier, 1), (Qt.ControlModifier, 0)):
                    with self.subTest(fps=fps, zoom=zoom, modifier=modifier):
                        pos = QPointF(330.5, 80)
                        calls = []
                        widget.RazorSliceAtCursor = lambda *args: calls.append(args)
                        with patch.object(QApplication, "keyboardModifiers", return_value=modifier):
                            target = widget._razor_target_at(pos, modifier)
                            widget._razor_pos = pos
                            widget._refresh_razor_hover(modifier)
                            TimelineWidgetBase._handle_razor_press(widget, pos)
                        self.assertEqual(calls[0][:2], ("C1", ""))
                        cut_frame = round(calls[0][2] * fps) + extra_frame + 1
                        self.assertEqual(target["frame"], cut_frame)
                        self.assertEqual(widget.previews[-1], (cut_frame + round(5 * fps), 61))
                        self.assertEqual(widget.current_frame, 61)
                        self.assertEqual(widget.seeks[-1], (61, False))
            widget.close()

    def test_invalid_targets_do_not_preview_or_cut(self):
        widget = RazorWidget()
        calls = []
        widget.RazorSliceAtCursor = lambda *args: calls.append(args)
        for pos, locked in ((QPointF(100, 80), False), (QPointF(800, 80), False),
                            (QPointF(400, 20), False), (QPointF(400, 180), False),
                            (QPointF(400, 80), True)):
            widget.locked = locked
            widget._razor_pos = pos
            widget._refresh_razor_hover(Qt.NoModifier)
            self.assertIsNone(widget._razor_target)
            with patch.object(QApplication, "keyboardModifiers", return_value=Qt.NoModifier):
                self.assertEqual(
                    TimelineWidgetBase._handle_razor_press(widget, pos),
                    widget._razor_in_track_area(pos),
                )
        self.assertEqual(widget.previews, [])
        self.assertEqual(calls, [])
        widget.close()

    def test_hover_deduplicates_and_restores_without_moving_playhead(self):
        widget = RazorWidget()
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget.previews, [(241, 61)])
        widget._clear_razor_hover()
        widget._clear_razor_hover()
        self.assertEqual(widget.seeks, [(61, False)])
        self.assertEqual(widget.current_frame, 61)
        widget.close()

    def test_playback_and_explicit_seeks_supersede_hover(self):
        widget = RazorWidget()
        widget.playing = True
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget.previews, [])
        widget.playing = False
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._razor_user_seek(150, True)
        widget._clear_razor_hover()
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget.seeks, [])
        self.assertEqual(len(widget.previews), 1)
        widget.close()

    def test_escape_exits_and_restores(self):
        widget = RazorWidget()
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        accepted = []
        event = types.SimpleNamespace(key=lambda: Qt.Key_Escape, accept=lambda: accepted.append(True))
        widget.keyPressEvent(event)
        self.assertFalse(widget.enable_razor)
        self.assertEqual(accepted, [True])
        self.assertEqual(widget.seeks, [(61, False)])
        widget.close()

    def test_razor_leaves_track_controls_and_scrollbars_available(self):
        widget = RazorWidget()
        for pos in (QPointF(50, 80), QPointF(895, 80), QPointF(400, 245)):
            self.assertFalse(TimelineWidgetBase._handle_razor_press(widget, pos))
        widget.close()

    def test_disabling_razor_stops_hover_and_restores_preview(self):
        widget = RazorWidget()
        widget._fixed_cursor = object()
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._razor_timer.start()
        TimelineWidgetBase.setRazorMode(widget, False)
        self.assertFalse(widget._razor_timer.isActive())
        self.assertIsNone(widget._razor_target)
        self.assertEqual(widget.seeks, [(61, False)])
        widget.close()

    def test_guide_and_discard_shading_are_clipped_to_target(self):
        widget = RazorWidget()
        widget._razor_pos = QPointF(400, 80)
        widget._razor_modifiers = Qt.ControlModifier
        image = QImage(900, 250, QImage.Format_ARGB32)
        image.fill(QColor("blue"))
        canvas = QPainter(image)
        project = types.SimpleNamespace(get=lambda key: {"num": 30, "den": 1})
        with patch.object(get_app(), "project", project, create=True), patch.object(QApplication, "keyboardModifiers", return_value=Qt.ControlModifier):
            widget._paint_razor(canvas)
        canvas.end()
        self.assertNotEqual(image.pixelColor(400, 100), QColor("blue"))
        self.assertNotEqual(image.pixelColor(200, 100), QColor("blue"))
        self.assertEqual(image.pixelColor(600, 100), QColor("blue"))
        self.assertEqual(image.pixelColor(400, 160), QColor("blue"))
        widget.close()

    def test_modifier_release_clears_painted_shading_without_mouse_or_timer(self):
        for key, flag, sample_x in ((Qt.Key_Shift, Qt.ShiftModifier, 600),
                                    (Qt.Key_Control, Qt.ControlModifier, 200)):
            with self.subTest(key=key):
                widget = RazorWidget()
                widget._razor_pos = QPointF(400, 80)
                # Qt may still report the released modifier in the key event;
                # painting must use the normalized event state, not global state.
                with patch.object(QApplication, "keyboardModifiers", return_value=flag), \
                        patch.object(QToolTip, "showText"):
                    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
                    self.assertNotEqual(widget._razor_target["mode"], "both")
                    widget.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, key, flag))
                    self.assertEqual(widget._razor_target["mode"], "both")
                    self.assertEqual(widget._razor_target["frame"], 91)
                    image = QImage(900, 250, QImage.Format_ARGB32)
                    image.fill(QColor("blue"))
                    canvas = QPainter(image)
                    widget._paint_razor(canvas)
                    canvas.end()
                    self.assertEqual(image.pixelColor(sample_x, 100), QColor("blue"))
                widget.close()

    def test_releasing_control_preserves_held_shift_and_updates_hint(self):
        widget = RazorWidget()
        widget._razor_pos = QPointF(400, 80)
        both = Qt.ControlModifier | Qt.ShiftModifier
        widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Control, both))
        self.assertEqual(widget._razor_target["mode"], "right")
        widget.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, Qt.Key_Control, both))
        self.assertEqual(widget._razor_target["mode"], "left")
        self.assertEqual(widget._razor_hint.text(), "Keep left · 00:00:03,01")
        widget._clear_razor_hover()
        self.assertTrue(widget._razor_hint.isHidden())
        widget.close()

    def test_shift_tap_stays_released_through_real_timer_refreshes(self):
        widget = RazorWidget()
        widget.show()
        QApplication.processEvents()
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._razor_timer.start()
        QApplication.sendEvent(widget, QKeyEvent(QEvent.KeyPress, Qt.Key_Shift, Qt.ShiftModifier))
        self.assertEqual(widget._razor_target["mode"], "left")
        QApplication.sendEvent(widget, QKeyEvent(QEvent.KeyRelease, Qt.Key_Shift, Qt.ShiftModifier))
        self.assertEqual(widget._razor_target["mode"], "both")
        observed = []
        widget._razor_timer.timeout.connect(lambda: observed.append(widget._razor_target["mode"]))
        loop = QEventLoop()
        with patch.object(QApplication, "keyboardModifiers", return_value=Qt.ShiftModifier):
            QTimer.singleShot(180, loop.quit)
            loop.exec_()
        self.assertGreaterEqual(len(observed), 2)
        self.assertEqual(set(observed), {"both"})
        self.assertFalse(widget._razor_hint.isHidden())
        widget._razor_timer.stop()
        widget.close()

    def test_hint_follows_cut_top_even_when_text_does_not_change(self):
        widget = RazorWidget()
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        initial_text = widget._razor_hint.text()
        initial_x = widget._razor_hint.x()
        initial_y = widget._razor_hint.y()
        widget._razor_pos = QPointF(400, 120)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget._razor_hint.y(), initial_y)
        # Scrolling and moving the pointer together preserves the cut time.
        widget.h_scroll_offset = 25
        widget._razor_pos = QPointF(375, 120)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget._razor_hint.text(), initial_text)
        self.assertEqual(widget._razor_hint.x(), initial_x - 25)
        self.assertEqual(widget._razor_hint.y(), initial_y)
        self.assertTrue(widget._razor_hint.testAttribute(Qt.WA_TransparentForMouseEvents))
        widget.close()

    def test_source_preview_switches_items_at_same_time_and_respects_trim(self):
        widget = RazorWidget()
        lower = types.SimpleNamespace(id="LOWER", data=dict(widget.clip.data))
        lower.data.update(position=1.0, start=10.0, end=17.0)
        widget.items.append((QRectF(200, 140, 650, 80), lower, False, "clip"))
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._razor_pos = QPointF(400, 170)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget.source_previews, [
            ("C1", 241, 61, "clip"), ("LOWER", 361, 61, "clip"),
        ])
        # Even identical timestamps on different sources must reload the source.
        lower.data.update(position=0.0, start=5.0, end=12.0)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._razor_pos = QPointF(400, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget.source_previews[-2:], [
            ("LOWER", 241, 61, "clip"), ("C1", 241, 61, "clip"),
        ])
        widget.close()

    def test_alt_adds_ripple_to_side_actions_only_and_release_updates_label(self):
        widget = RazorWidget()
        widget._razor_pos = QPointF(400, 80)
        for side in (Qt.ShiftModifier, Qt.ControlModifier):
            widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Alt, side | Qt.AltModifier))
            self.assertTrue(widget._razor_target["ripple"])
            self.assertIn("Close gap", widget._razor_hint.text())
            widget.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, Qt.Key_Alt, side | Qt.AltModifier))
            self.assertFalse(widget._razor_target["ripple"])
            self.assertNotIn("Close gap", widget._razor_hint.text())
        widget._refresh_razor_hover(Qt.AltModifier)
        self.assertFalse(widget._razor_target["ripple"])
        self.assertEqual(widget._razor_target["mode"], "both")
        widget.close()

    def test_ripple_shortcuts_use_hover_and_consume_invalid_target(self):
        widget = RazorWidget()
        calls = []
        widget.RazorSliceAtCursor = lambda *args: calls.append(args)
        for keep_left, flag in ((True, Qt.ShiftModifier), (False, Qt.ControlModifier)):
            widget._razor_pos = QPointF(400, 80)
            self.assertTrue(widget.razor_ripple_at_cursor(keep_left))
            self.assertEqual(calls[-1], ("C1", "", 3.0, flag | Qt.AltModifier))
        widget._razor_pos = QPointF(400, 80)
        widget.locked = True
        self.assertTrue(widget.razor_ripple_at_cursor(True))
        self.assertEqual(len(calls), 2)
        widget.enable_razor = False
        self.assertFalse(widget.razor_ripple_at_cursor(True))
        widget.enable_razor = True
        widget._razor_pos = QPointF(50, 80)
        self.assertFalse(widget.razor_ripple_at_cursor(True))
        widget.close()

    def test_existing_ripple_actions_route_hover_or_preserve_playhead_behavior(self):
        from windows.main_window import MainWindow
        from windows.views.timeline import MenuSlice

        for method, keep_left, mode in (
            (MainWindow.actionRippleSliceKeepLeft, True, MenuSlice.KEEP_LEFT),
            (MainWindow.actionRippleSliceKeepRight, False, MenuSlice.KEEP_RIGHT),
        ):
            for handled in (False, True):
                hover_calls, playhead_calls = [], []
                window = types.SimpleNamespace(
                    timeline=types.SimpleNamespace(
                        razor_ripple_at_cursor=lambda side: hover_calls.append(side) or handled),
                    slice_clips=lambda *args, **kwargs: playhead_calls.append((args, kwargs)),
                )
                method(window)
                self.assertEqual(hover_calls, [keep_left])
                self.assertEqual(playhead_calls, [] if handled else [
                    ((mode,), {"selected_only": True, "ripple": True})
                ])

    def test_razor_uses_shared_snap_targets_and_pixel_tolerance(self):
        for target_kind in ("clip", "transition", "marker", "playhead", "keyframe"):
            for zoom in (100.0, 731.5):
                with self.subTest(target=target_kind, zoom=zoom):
                    widget = RazorWidget(30000 / 1001)
                    widget.enable_snapping = True
                    widget.pixels_per_second = zoom
                    widget.h_scroll_offset = 2 * zoom
                    widget.current_frame = 1
                    target_time = 90 / widget.fps_float
                    world_x = widget.track_name_width + target_time * zoom
                    viewport_x = world_x - widget.h_scroll_offset
                    widget.items[0] = (QRectF(100 - widget.h_scroll_offset, 50, 7 * zoom, 80), widget.clip, False, "clip")
                    if target_kind in ("clip", "transition"):
                        other = types.SimpleNamespace(id="OTHER", data={})
                        widget.items.append((QRectF(viewport_x, 140, zoom, 80), other, False, target_kind))
                    elif target_kind == "marker":
                        widget.geometry.marker_rects = [{"line_rect": QRectF(world_x, 0, 1, 30)}]
                    elif target_kind == "playhead":
                        widget.current_frame = 91
                    else:
                        widget.keyframe_times = [target_time]
                    original_keyframes = [1000.0]
                    widget._snap_keyframe_seconds = original_keyframes
                    widget._razor_pos = QPointF(viewport_x + 9, 80)
                    widget._refresh_razor_hover(Qt.NoModifier)
                    self.assertAlmostEqual(widget._razor_target["cut_seconds"], target_time)
                    self.assertEqual(widget._razor_target["frame"], 91)
                    self.assertIs(widget._snap_keyframe_seconds, original_keyframes)
                    self.assertIn("razor", widget._snap_active_targets)
                    # Use the helper's normal 12 px radius, regardless of zoom.
                    widget._razor_pos = QPointF(viewport_x + 15, 80)
                    widget._refresh_razor_hover(Qt.NoModifier)
                    self.assertNotIn("razor", widget._snap_active_targets)
                    widget.close()

    def test_all_razor_cut_modes_commit_the_snapped_boundary(self):
        widget = RazorWidget()
        widget.enable_snapping = True
        widget.current_frame = 91
        calls = []
        widget.RazorSliceAtCursor = lambda *args: calls.append(args)
        for modifiers in (Qt.NoModifier, Qt.ShiftModifier, Qt.ControlModifier,
                          Qt.AltModifier | Qt.ShiftModifier, Qt.AltModifier | Qt.ControlModifier):
            widget._razor_pos = QPointF(407, 80)
            widget._refresh_razor_hover(modifiers)
            self.assertEqual(widget._razor_target["cut_seconds"], 3.0)
            self.assertEqual(widget.source_previews[-1][1], 241)
            TimelineWidgetBase._handle_razor_press(widget, widget._razor_pos)
            seconds = calls[-1][2]
            if modifiers & Qt.ShiftModifier:
                seconds += 1 / widget.fps_float
            self.assertAlmostEqual(seconds, 3.0)
        for keep_left in (False, True):
            widget._razor_pos = QPointF(407, 80)
            widget._refresh_razor_hover(Qt.NoModifier)
            self.assertTrue(widget.razor_ripple_at_cursor(keep_left))
            seconds = calls[-1][2] + (1 / widget.fps_float if keep_left else 0)
            self.assertAlmostEqual(seconds, 3.0)
        widget.close()

    def test_snap_toggle_own_edges_and_other_tools_state(self):
        widget = RazorWidget()
        widget.enable_snapping = True
        widget.current_frame = 91
        widget._snap_active_targets = {"drag-left": {"px": 123, "tol": 12}}
        widget._razor_pos = QPointF(407, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget._razor_target["cut_seconds"], 3.0)
        widget.enable_snapping = False
        widget._refresh_razor_hover()
        self.assertAlmostEqual(widget._razor_target["cut_seconds"], 92 / 30)
        self.assertNotIn("razor", widget._snap_active_targets)
        self.assertIn("drag-left", widget._snap_active_targets)
        widget.enable_snapping = True
        widget._razor_pos = QPointF(104, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertAlmostEqual(widget._razor_target["cut_seconds"], 1 / 30)
        self.assertNotIn("razor", widget._snap_active_targets)
        widget._clear_razor_hover()
        self.assertIn("drag-left", widget._snap_active_targets)
        widget.close()

    def test_snap_sticks_until_released_but_drops_deleted_targets(self):
        widget = RazorWidget()
        widget.enable_snapping = True
        widget.current_frame = 1
        widget.geometry.marker_rects = [QRectF(400, 0, 1, 30), QRectF(410, 0, 1, 30)]
        widget._razor_pos = QPointF(402, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget._razor_pos = QPointF(409, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        self.assertEqual(widget._razor_target["cut_seconds"], 3.0)
        # A click must retain the previewed target, rather than choose the nearer marker.
        calls = []
        widget.RazorSliceAtCursor = lambda *args: calls.append(args)
        TimelineWidgetBase._handle_razor_press(widget, widget._razor_pos)
        self.assertEqual(calls[-1][2], 3.0)
        widget._razor_pos = QPointF(402, 80)
        widget._refresh_razor_hover(Qt.NoModifier)
        widget.geometry.marker_rects.pop(0)
        widget._refresh_razor_hover()
        self.assertEqual(widget._razor_target["cut_seconds"], 3.1)
        widget.close()

    def make_worker(self):
        worker = PlayerWorker()
        worker.parent = types.SimpleNamespace(initialized=True)
        worker.mode = openshot.PLAYBACK_PAUSED
        worker.position = 61
        worker.calls = []
        worker.player = types.SimpleNamespace(
            Mode=lambda: worker.mode, Speed=lambda: 1 if worker.mode == openshot.PLAYBACK_PLAY else 0,
            Position=lambda: worker.position,
            Seek=lambda frame, preroll: (worker.calls.append((frame, preroll)), setattr(worker, "position", frame)),
            Play=lambda: setattr(worker, "mode", openshot.PLAYBACK_PLAY),
        )
        worker._seek_lock = threading.Lock()
        worker._pending_seek = None
        worker._last_queued_seek_request = None
        worker._last_applied_seek_request = None
        worker._last_applied_seek_time = 0.0
        worker._razor_restore_frame = None
        worker.clip_path = None
        worker.current_frame = 61
        return worker

    def test_worker_hover_is_silent_and_restore_publishes_original_position(self):
        worker = self.make_worker()
        published = []
        worker.position_changed.connect(published.append)
        self.assertTrue(worker.queue_razor_preview(91, 61))
        worker._apply_seek(*worker._take_pending_seek())
        worker._publish_position()
        self.assertEqual(published, [])
        worker.queue_seek(61, False)
        worker._apply_seek(*worker._take_pending_seek())
        worker._publish_position()
        self.assertEqual(published, [61])

    def test_source_hover_restores_timeline_reader_before_seek_or_play(self):
        for play in (False, True):
            worker = self.make_worker()
            worker.timeline = object()
            worker.reader_mode = "timeline"
            reader_changes = []
            worker.player.Reader = reader_changes.append

            def load(path, stretch, seek=True):
                self.assertFalse(seek, "Source loading must not enqueue an extra frame-1 seek")
                worker.reader_mode = "clip"
                worker.clip_path = path
                worker.preview_stretch = stretch

            worker.LoadFilePreview = load
            worker.queue_razor_preview(241, 61, "/media/lower.mp4", False)
            worker._apply_seek(*worker._take_pending_seek())
            self.assertEqual(worker.position, 241)
            self.assertEqual(worker.clip_path, "/media/lower.mp4")
            self.assertIsNone(worker._take_pending_seek())
            if play:
                worker.Play()
            else:
                worker.queue_seek(61, False)
                worker._apply_seek(*worker._take_pending_seek())
            self.assertEqual(reader_changes, [worker.timeline])
            self.assertEqual(worker.position, 61)
            self.assertEqual(worker.reader_mode, "timeline")
            self.assertIsNone(worker.clip_path)
            self.assertIsNone(worker._razor_restore_frame)

    def test_play_discards_pending_source_hover(self):
        worker = self.make_worker()
        worker.queue_razor_preview(241, 61, "/media/lower.mp4", False)
        worker.Play()
        self.assertEqual(worker.position, 61)
        self.assertIsNone(worker._razor_restore_frame)

    def test_worker_play_restores_pending_and_applied_hover(self):
        for applied in (False, True):
            worker = self.make_worker()
            worker.queue_razor_preview(91, 61)
            if applied:
                worker._apply_seek(*worker._take_pending_seek())
            worker.Play()
            self.assertEqual(worker.position, 61)
            self.assertIsNone(worker._razor_restore_frame)
            self.assertFalse(worker.queue_razor_preview(100, 61))

    def test_worker_manual_seek_wins_and_same_frame_restore_is_not_deduplicated(self):
        worker = self.make_worker()
        worker.queue_seek(150, True)
        self.assertFalse(worker.queue_razor_preview(91, 61))
        self.assertEqual(worker._take_pending_seek(), (150, True))
        worker.queue_razor_preview(61, 61)
        worker._apply_seek(*worker._take_pending_seek())
        worker.queue_seek(61, False)
        self.assertEqual(worker._take_pending_seek(), (61, False))

    def test_rapid_hover_exit_replaces_pending_preview_after_recent_restore(self):
        worker = self.make_worker()
        worker._apply_seek(61, False)
        worker.queue_razor_preview(91, 61)
        worker.queue_seek(61, False)
        self.assertEqual(worker._take_pending_seek(), (61, False))

    def test_worker_latest_hover_wins_and_playback_rejects_inflight_preview(self):
        worker = self.make_worker()
        worker.queue_razor_preview(91, 61)
        worker.queue_razor_preview(101, 61)
        request = worker._take_pending_seek()
        self.assertEqual(request, (101, False, 61))
        worker.mode = openshot.PLAYBACK_PLAY
        worker._apply_seek(*request)
        self.assertEqual(worker.calls, [])
        self.assertIsNone(worker._razor_restore_frame)

    def test_transition_is_targeted_without_cutting_underlying_clip(self):
        widget = RazorWidget()
        transition = types.SimpleNamespace(id="T1", data=dict(widget.clip.data))
        widget.items.insert(0, (QRectF(300, 50, 150, 80), transition, False, "transition"))
        calls = []
        widget.RazorSliceAtCursor = lambda *args: calls.append(args)
        with patch.object(QApplication, "keyboardModifiers", return_value=Qt.NoModifier):
            TimelineWidgetBase._handle_razor_press(widget, QPointF(400, 80))
        self.assertEqual(calls, [("", "T1", 3.0, Qt.NoModifier)])
        widget.close()
