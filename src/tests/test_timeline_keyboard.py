"""Keyboard navigation, editing boundaries, focus, and settings migration."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from classes.keyboard_shortcuts import migrate_timeline_shortcuts, LEGACY_TIMELINE_SHORTCUTS
from classes.query import Clip, Transition
from windows.views.timeline_backend.qwidget.keyboard import KeyboardMixin


def clip(identity, layer, position, duration=1):
    result = Clip()
    result.id = identity
    result.data = dict(id=identity, layer=layer, position=position, start=0, end=duration, duration=duration)
    return result


class Canvas(KeyboardMixin):
    def __init__(self, clips):
        self.clips = clips
        self.geometry = Mock()
        self.fps_float = 30
        self.track_list = [SimpleNamespace(data={'number': n}) for n in (3, 2, 1)]
        self.win = SimpleNamespace(selected_clips=[], selected_transitions=[],
                                   preview_thread=SimpleNamespace(current_frame=1),
                                   PauseSignal=Mock(), SeekSignal=Mock())
        self._keyboard_reveal = Mock()
        self.update = Mock()
        self.locked = set()
        self.writes = []
        self.update_clip_data = self.commit
        self.update_transition_data = self.commit

    def commit(self, data, **kwargs):
        self.writes.append((dict(data), kwargs))
        next(c for c in self.clips if c.id == data['id']).data = dict(data)

    def _is_track_locked(self, layer):
        return layer in self.locked

    def _select_timeline_item(self, identity, kind, clear):
        if clear:
            self.win.selected_clips.clear()
            self.win.selected_transitions.clear()
        selected = self.win.selected_clips if kind == 'clip' else self.win.selected_transitions
        if identity not in selected:
            selected.append(identity)


class TimelineKeyboardTests(unittest.TestCase):
    def setUp(self):
        self.clips = [clip('a', 2, 0), clip('b', 2, 1, 1/30), clip('c', 2, 2), clip('top', 3, 0, 4)]
        self.canvas = Canvas(self.clips)
        self.addCleanup(patch.stopall)
        patch.object(Clip, 'filter', return_value=self.clips).start()
        patch.object(Clip, 'get', side_effect=lambda id: next((c for c in self.clips if c.id == id), None)).start()
        patch.object(Transition, 'get', return_value=None).start()
        patch.object(Transition, 'filter', return_value=[]).start()

    def test_selects_tiny_clip_and_extends_without_seeking(self):
        w = self.canvas
        w.win.selected_clips = ['a']
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['b'])
        w.keyboard_select('right', True)
        self.assertEqual(w.win.selected_clips, ['b', 'c'])
        w.keyboard_select('left')
        self.assertEqual(w.win.selected_clips, ['b'])
        w.win.SeekSignal.emit.assert_not_called()
        self.assertEqual(w._keyboard_reveal.call_count, 3)

    def test_navigation_from_gap_obeys_direction(self):
        w = self.canvas
        w._keyboard_layer = 2
        w.win.preview_thread.current_frame = 46
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['c'])
        w.win.selected_clips = []
        w.keyboard_select('left')
        self.assertEqual(w.win.selected_clips, ['b'])

    def test_group_nudge_at_zero_preserves_spacing_and_undo_transaction(self):
        from tests.test_main_window import DummyApp, ensure_app_state
        from tests.qt_test_app import get_or_create_app
        app, _owned = get_or_create_app(DummyApp)
        ensure_app_state(app)
        from windows.views import timeline
        self.clips[0].data['position'] = 1 / 30
        w = self.canvas
        with patch.object(timeline, 'get_app', return_value=SimpleNamespace(
                project=SimpleNamespace(get=lambda key: {'num': 30, 'den': 1}))):
            timeline.TimelineView.Nudge_Triggered(w, -5, ['a', 'b'], [])
        self.assertAlmostEqual(w.writes[0][0]['position'], 0)
        self.assertAlmostEqual(w.writes[1][0]['position'], 1 - 1/30)
        self.assertEqual(len({opts['transaction_id'] for _, opts in w.writes}), 1)

    def test_horizontal_selection_continues_across_tracks_and_extends(self):
        w = self.canvas
        self.clips[:] = [clip('alien', 3, 24), clip('skull', 2, 34),
                         clip('angry', 2, 78), clip('kiss', 1, 60)]
        w.win.selected_clips = ['alien']
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['skull'])
        w.keyboard_select('left')
        self.assertEqual(w.win.selected_clips, ['alien'])
        w.keyboard_select('right', True)
        self.assertEqual(w.win.selected_clips, ['alien', 'skull'])
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['angry'])
        # The current track still takes priority over a closer clip elsewhere.
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['angry'])
        w.win.selected_clips = ['kiss']
        w.keyboard_select('left')
        self.assertEqual(w.win.selected_clips, ['skull'])
        w.win.SeekSignal.emit.assert_not_called()

    def test_cross_track_fallback_prefers_nearby_track_at_equal_times(self):
        w = self.canvas
        self.clips[:] = [clip('a', 3, 1), clip('near', 2, 2), clip('far', 1, 2)]
        w.win.selected_clips = ['a']
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['near'])

    def test_horizontal_navigation_from_empty_track_uses_direction(self):
        w = self.canvas
        w._keyboard_layer = 1
        w.win.preview_thread.current_frame = 46
        w.keyboard_select('left')
        self.assertEqual(w.win.selected_clips, ['b'])
        w.win.selected_clips = []
        w._keyboard_layer = 1
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, ['c'])

    def test_vertical_selection_and_edges_do_not_wrap(self):
        w = self.canvas
        w.win.selected_clips = ['b']
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['top'])
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['top'])
        w.keyboard_select('left')
        self.assertEqual(w.win.selected_clips, ['top'])

    def test_vertical_selection_skips_multiple_empty_tracks_in_both_directions(self):
        w = self.canvas
        w.track_list = [SimpleNamespace(data={'number': n}) for n in (5, 4, 3, 2, 1)]
        self.clips[-1].data['layer'] = 5
        w.win.selected_clips = ['b']
        w.win.preview_thread.current_frame = 31
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['top'])
        w.keyboard_select('down')
        self.assertEqual(w.win.selected_clips, ['c'])
        w.keyboard_select('down')
        self.assertEqual(w.win.selected_clips, ['c'])
        w.win.SeekSignal.emit.assert_not_called()

    def test_track_movement_still_targets_adjacent_empty_track(self):
        w = self.canvas
        self.clips[-1].data['layer'] = 1
        w.win.selected_clips = ['b']
        w.keyboard_move_track(-1)
        self.assertEqual(w.writes[0][0]['layer'], 3)
        self.assertEqual(w.writes[0][0]['position'], 1)

    def test_playhead_selection_uses_topmost_occupied_track_and_gap_is_noop(self):
        w = self.canvas
        w.keyboard_select('playhead')
        self.assertEqual(w.win.selected_clips, ['top'])
        w.win.preview_thread.current_frame = 301
        w.keyboard_select('playhead')
        self.assertEqual(w.win.selected_clips, ['top'])

    def test_playhead_cycle_wraps_extends_and_resets_when_frame_changes(self):
        w = self.canvas
        self.clips[:] = [clip('bottom', 1, 0, 4), clip('middle', 2, 0, 4),
                         clip('top', 3, 0, 4)]
        for identity in ('top', 'middle', 'bottom', 'top'):
            w.keyboard_select('playhead')
            self.assertEqual(w.win.selected_clips, [identity])
        w.keyboard_select('playhead', True)
        self.assertEqual(w.win.selected_clips, ['top', 'middle'])
        w.keyboard_select('playhead', True)
        self.assertEqual(w.win.selected_clips, ['top', 'middle', 'bottom'])
        w.keyboard_select('playhead', True)
        self.assertEqual(w.win.selected_clips, ['top', 'middle', 'bottom'])
        w.win.preview_thread.current_frame = 31
        w.keyboard_select('playhead')
        self.assertEqual(w.win.selected_clips, ['top'])
        self.clips.pop()
        w.keyboard_select('playhead')
        self.assertEqual(w.win.selected_clips, ['middle'])

    def test_vertical_selection_uses_selected_clip_not_playhead(self):
        w = self.canvas
        self.clips[:] = [clip('selected', 2, 10, 20), clip('edge', 3, 0, 11),
                         clip('above', 3, 15, 10), clip('far', 3, 40, 10)]
        for frame in (1, 601, 3001):
            w.win.selected_clips = ['selected']
            w.win.preview_thread.current_frame = frame
            w.keyboard_select('up')
            self.assertEqual(w.win.selected_clips, ['above'])
        w.keyboard_select('down')
        self.assertEqual(w.win.selected_clips, ['selected'])

    def test_vertical_selection_skips_occupied_but_unaligned_tracks(self):
        w = self.canvas
        w.track_list = [SimpleNamespace(data={'number': n}) for n in (4, 3, 2, 1)]
        self.clips[:] = [clip('goblin', 4, 19, 10), clip('dizzy', 4, 64, 10),
                         clip('love', 3, 29, 10), clip('thought', 3, 74, 10),
                         clip('sparkle', 2, 29, 10), clip('right', 1, 70, 10)]
        w.win.selected_clips = ['right']
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['thought'])
        w.keyboard_select('down')
        self.assertEqual(w.win.selected_clips, ['right'])
        w.keyboard_select('up')
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['dizzy'])
        w.win.SeekSignal.emit.assert_not_called()

    def test_vertical_selection_without_overlap_prefers_nearest_horizontal_gap(self):
        w = self.canvas
        self.clips[:] = [clip('selected', 1, 70, 10), clip('far', 2, 20, 10),
                         clip('near', 3, 85, 10)]
        w.win.selected_clips = ['selected']
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['near'])

    def test_vertical_selection_prefers_nearest_track_when_both_overlap(self):
        w = self.canvas
        self.clips[:] = [clip('selected', 1, 70, 10), clip('near', 2, 75, 10),
                         clip('far', 3, 70, 10)]
        w.win.selected_clips = ['selected']
        w.keyboard_select('up')
        self.assertEqual(w.win.selected_clips, ['near'])

    def test_five_frame_steps_pause_and_clamp_at_start(self):
        w = self.canvas
        w.win.preview_thread.current_frame = 10
        w.keyboard_step_frames(5)
        w.win.SeekSignal.emit.assert_called_with(15, True)
        w.keyboard_step_frames(-5)
        w.win.SeekSignal.emit.assert_called_with(5, True)
        w.win.preview_thread.current_frame = 3
        w.keyboard_step_frames(-5)
        w.win.SeekSignal.emit.assert_called_with(1, True)
        self.assertEqual(w.win.PauseSignal.emit.call_count, 3)

    def test_keyboard_trim_uses_hover_edge_target_and_current_geometry(self):
        from qt_api import QRectF
        from windows.views.timeline_backend.paint.hover import HoverFeedback
        w = self.canvas
        w.hasFocus = Mock(return_value=True)
        w.win.selected_clips = ['a']
        w._keyboard_edge = ('a', 'left')
        rect = QRectF(100, 50, 200, 70)
        w.geometry.iter_items.return_value = [(rect, self.clips[0], True, 'clip')]
        feedback = HoverFeedback(w)
        self.assertEqual(feedback.keyboard_resize_target(), ('edge-left', rect, 'clip'))
        w._keyboard_edge = ('a', 'right')
        rect.setWidth(250)
        self.assertEqual(feedback.keyboard_resize_target(), ('edge-right', rect, 'clip'))
        w.hasFocus.return_value = False
        self.assertIsNone(feedback.keyboard_resize_target())
        w.hasFocus.return_value = True
        w.win.selected_clips = []
        self.assertIsNone(feedback.keyboard_resize_target())

    def test_edit_navigation_uses_active_track_and_skips_current_boundary(self):
        w = self.canvas
        w.win.selected_clips = ['a']
        w.keyboard_edit_point(1)
        w.win.SeekSignal.emit.assert_called_with(31, True)
        w.win.preview_thread.current_frame = 31
        w.keyboard_edit_point(1)
        w.win.SeekSignal.emit.assert_called_with(32, True)
        w.keyboard_edit_point(-1)
        w.win.SeekSignal.emit.assert_called_with(1, True)

    def test_moves_group_together_in_one_transaction(self):
        w = self.canvas
        w.win.selected_clips = ['a', 'b']
        w.keyboard_move_track(-1)
        self.assertEqual([d['layer'] for d, _ in w.writes], [3, 3])
        self.assertEqual([d['position'] for d, _ in w.writes], [0, 1])
        self.assertEqual(len({opts['transaction_id'] for _, opts in w.writes}), 1)

    def test_locked_destination_or_source_or_track_boundary_blocks_whole_move(self):
        w = self.canvas
        w.win.selected_clips = ['a', 'b']
        for layer in (2, 3):
            w.locked = {layer}
            w.keyboard_move_track(-1)
            self.assertEqual(w.writes, [])
        w.locked.clear()
        w.win.selected_clips = ['a', 'top']
        w.keyboard_move_track(-1)
        self.assertEqual(w.writes, [])

    def test_nudge_no_selection_and_locked_selection_are_noops(self):
        w = self.canvas
        w.Nudge_Triggered = Mock()
        w.keyboard_nudge(1)
        w.win.selected_clips = ['a']
        w.locked = {2}
        w.keyboard_nudge(1)
        w.Nudge_Triggered.assert_not_called()
        w.locked.clear()
        w.keyboard_nudge(5)
        w.Nudge_Triggered.assert_called_once_with(5, ['a'], [])

    def test_keyboard_trim_previews_source_edges_and_restores_timeline(self):
        w = self.canvas
        w.win.timeline = Mock()
        w.win.TrimPreviewMode = Mock()
        w.win.TimelinePreviewMode = Mock()
        w.win.preview_thread.frame_step_position = Mock(return_value=91)
        w.win.selected_clips = ['a']
        self.clips[0].data.update(start=2, end=4, position=20)
        w.keyboard_select_edge('left')
        w.win.timeline.PreviewClipFrame.assert_called_with('a', 61)
        w.keyboard_select_edge('right')
        w.win.timeline.PreviewClipFrame.assert_called_with('a', 120)
        w._resize_edge = None
        w.enable_timing = False
        w._build_resize_context = Mock(return_value={})
        w._resize_edge_value = Mock(return_value=4)
        w._compute_clip_resize = Mock(return_value=(None, 2, 4 + 5/30, 20))
        def commit(item, start, end, position, *_args):
            item.data.update(start=start, end=end, position=position)
        w._commit_resized_clip = Mock(side_effect=commit)
        w.keyboard_nudge(5)
        w.win.timeline.PreviewClipFrame.assert_called_with('a', 125)
        w.win.TrimPreviewMode.emit.assert_called_once()
        w.win.SeekSignal.emit.assert_not_called()
        w._keyboard_end_trim_preview()
        w.win.TimelinePreviewMode.emit.assert_called_once()
        w.win.SeekSignal.emit.assert_called_once_with(91, False)
        w._keyboard_end_trim_preview()
        w.win.SeekSignal.emit.assert_called_once()

    def test_edge_nudge_uses_resize_limits_and_restores_timing_mode(self):
        w = self.canvas
        w.win.selected_clips = ['a']
        w._keyboard_edge = ('a', 'right')
        w._resize_edge = None
        w.enable_timing = True
        w._build_resize_context = Mock(return_value={'initial': self.clips[0].data})
        w._resize_edge_value = Mock(return_value=1)
        w._compute_clip_resize = Mock(return_value=(None, 0, 1+1/30, 0))
        w._commit_resized_clip = Mock()
        w.keyboard_nudge(1)
        self.assertAlmostEqual(w._compute_clip_resize.call_args.args[2], 1+1/30)
        self.assertEqual(w._commit_resized_clip.call_args.args[1:4], (0, 1+1/30, 0))
        self.assertTrue(w.enable_timing)
        self.assertIsNone(w._resize_edge)


class TransitionKeyboardTests(unittest.TestCase):
    """Exercise mixed selections and transition-specific trim behavior."""
    def setUp(self):
        TimelineKeyboardTests.setUp(self)
        self.transitions = []
        for index in (1, 2):
            original = self.clips[index]
            item = Transition()
            item.id, item.data = original.id, original.data
            self.clips[index] = item
            self.transitions.append(item)
        patch.object(Clip, 'filter', side_effect=lambda: [c for c in self.clips if isinstance(c, Clip)]).start()
        patch.object(Clip, 'get', side_effect=lambda id: next(
            (c for c in self.clips if c.id == id and isinstance(c, Clip)), None)).start()
        patch.object(Transition, 'filter', return_value=self.transitions).start()
        patch.object(Transition, 'get', side_effect=lambda id: next(
            (c for c in self.transitions if c.id == id), None)).start()

    def test_mixed_navigation_and_extension(self):
        w = self.canvas
        w.win.selected_clips = ['a']
        w.keyboard_select('right')
        self.assertEqual(w.win.selected_clips, [])
        self.assertEqual(w.win.selected_transitions, ['b'])
        w.keyboard_select('right', True)
        self.assertEqual(w.win.selected_transitions, ['b', 'c'])
        w.keyboard_select('up', True)
        self.assertEqual(w.win.selected_clips, ['top'])
        self.assertEqual(w.win.selected_transitions, ['b', 'c'])

    def test_playhead_cycles_both_types_and_extends(self):
        w = self.canvas
        self.transitions[0].data.update(position=0, end=1)
        for expected in ('top', 'a', 'b', 'top'):
            w.keyboard_select('playhead')
            self.assertEqual(w.win.selected_clips + w.win.selected_transitions, [expected])
        w.keyboard_select('playhead', True)
        w.keyboard_select('playhead', True)
        self.assertEqual(w.win.selected_clips, ['top', 'a'])
        self.assertEqual(w.win.selected_transitions, ['b'])

    def test_mixed_group_moves_and_nudges(self):
        w = self.canvas
        w.win.selected_clips = ['a']
        w.win.selected_transitions = ['b']
        w.keyboard_move_track(-1)
        self.assertEqual([d['layer'] for d, _ in w.writes], [3, 3])
        self.assertEqual(len({opts['transaction_id'] for _, opts in w.writes}), 1)
        w.Nudge_Triggered = Mock()
        w.keyboard_nudge(5)
        w.Nudge_Triggered.assert_called_once_with(5, ['a'], ['b'])
        w.locked = {3}
        w.keyboard_nudge(-1)
        self.assertEqual(w.Nudge_Triggered.call_count, 1)

    def test_transition_edge_highlight_and_preview(self):
        from qt_api import QRectF
        from windows.views.timeline_backend.paint.hover import HoverFeedback
        w = self.canvas
        w.win.timeline = Mock()
        w.win.TrimPreviewMode = Mock()
        w.win.selected_transitions = ['b']
        w.hasFocus = Mock(return_value=True)
        rect = QRectF(100, 50, 200, 70)
        w.geometry.iter_items.return_value = [(rect, self.transitions[0], True, 'transition')]
        w.keyboard_select_edge('left')
        self.assertEqual(HoverFeedback(w).keyboard_resize_target(), ('edge-left', rect, 'transition'))
        w.win.timeline.PreviewTransitionFrame.assert_called_with('b', 1)
        w.keyboard_select_edge('right')
        self.assertEqual(HoverFeedback(w).keyboard_resize_target(), ('edge-right', rect, 'transition'))
        w.win.timeline.PreviewClipFrame.assert_not_called()


    def test_transition_keyboard_trim_uses_mouse_limits_and_commit(self):
        from qt_api import QRectF
        from windows.views.timeline_backend.qwidget.clip import ClipInteractionMixin
        w = self.canvas
        item = self.transitions[0]
        w.win.selected_transitions = [item.id]
        w._last_event = None
        w.pixels_per_second = 100
        w.track_name_width = 50
        w._resize_edge = None
        w.enable_timing = True
        w._snap_time = lambda t: round(t * w.fps_float) / w.fps_float
        for name in ('_compute_transition_resize', '_commit_resized_transition',
                     '_normalize_resize_commit_bounds', '_resize_edge_value'):
            setattr(w, name, getattr(ClipInteractionMixin, name).__get__(w))
        w.win.timeline = Mock()
        w.win.TrimPreviewMode = Mock()
        for static in (True, False):
            with self.subTest(static_mask=static):
                item.data.update(start=0, end=1, duration=1, position=2)
                w._build_resize_context = lambda item: dict(
                    initial=dict(item.data), rect=QRectF(250, 50, 100, 70), static_mask=static)
                w.keyboard_select_edge('left')
                w.keyboard_nudge(5)
                self.assertAlmostEqual(item.data['position'], 2 + 5/30)
                self.assertAlmostEqual(item.data['duration'], 25/30)
                self.assertAlmostEqual(item.data['start'], 0 if static else 5/30)
                self.assertEqual(item.data['_auto_direction'], static)
                w.keyboard_select_edge('right')
                w.keyboard_nudge(-100)
                self.assertAlmostEqual(item.data['duration'], 1/30)
                w.win.timeline.PreviewTransitionFrame.assert_called_with(
                    item.id, round(item.data['end'] * 30))
                self.assertTrue(w.enable_timing)
                self.assertIsNone(w._resize_edge)



class KeyboardMigrationTests(unittest.TestCase):
    def setUp(self):
        self.defaults = json.loads((Path(__file__).parents[1] / 'settings/_default.settings').read_text())

    def test_stock_shortcuts_migrate_once(self):
        user = [{'setting': name, 'value': value} for name, value in LEGACY_TIMELINE_SHORTCUTS.items()]
        result = migrate_timeline_shortcuts(self.defaults, user)
        values = {i['setting']: i['value'] for i in result}
        self.assertEqual(values['nudgeLeft'], ',')
        self.assertEqual(values['timelineSelectPrevious'], 'Ctrl+Left')
        self.assertEqual(values['actionCenterOnPlayhead'], 'Shift+C')
        self.assertEqual(values['playToggle'], 'Space')
        self.assertEqual(values['playbackStop'], 'K')
        self.assertEqual(migrate_timeline_shortcuts(self.defaults, result), result)

    def test_custom_binding_survives_and_new_command_gets_nonconflicting_binding(self):
        user = [{'setting': 'actionSave', 'value': 'Ctrl+Left'},
                {'setting': 'nudgeLeft', 'value': 'Ctrl+Left'},
                {'setting': 'playToggle', 'value': ''}]
        result = {i['setting']: i['value'] for i in migrate_timeline_shortcuts(self.defaults, user)}
        self.assertEqual(result['actionSave'], 'Ctrl+Left')
        self.assertEqual(result['playToggle'], '')
        self.assertEqual(result['timelineSelectPrevious'], 'Ctrl+Alt+Shift+Left')
        self.assertEqual(result['nudgeLeft'], ',')

    def test_default_bindings_are_unique(self):
        from qt_api import QKeySequence
        seen = {}
        for item in self.defaults:
            if item.get('category') != 'Keyboard' or item.get('type') != 'text':
                continue
            for key in item['value'].split('|'):
                if not key.strip():
                    continue
                key = QKeySequence(key.strip()).toString()
                self.assertNotIn(key, seen, (key, seen.get(key), item['setting']))
                seen[key] = item['setting']


class KeyboardFocusTests(unittest.TestCase):
    def test_timeline_shortcuts_do_not_capture_text_editing_or_tab(self):
        import importlib
        from qt_api import QApplication, QMainWindow, QWidget, QLineEdit, QVBoxLayout, Qt, QKeySequence, QT_API
        from tests.qt_test_app import get_or_create_app
        from tests.test_main_window import DummyApp, ensure_app_state
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        app, _owned = get_or_create_app(DummyApp)
        ensure_app_state(app)
        from windows.main_window import MainWindow
        window = QMainWindow()
        container = QWidget()
        window.setCentralWidget(container)
        layout = QVBoxLayout(container)
        window.timeline = QWidget()
        window.timeline.setFocusPolicy(Qt.StrongFocus)
        editor = QLineEdit('one two three')
        layout.addWidget(window.timeline)
        layout.addWidget(editor)
        window.nudgeLeft = Mock()
        window.timelineSelectPrevious = Mock()
        window.getAllKeyboardShortcuts = lambda: [{'setting': 'nudgeLeft'}, {'setting': 'timelineSelectPrevious'}]
        window.getShortcutByName = lambda name: [QKeySequence(',' if name == 'nudgeLeft' else 'Ctrl+Left')]
        MainWindow.initShortcuts(window)
        self.addCleanup(window.close)
        window.show()
        window.activateWindow()
        window.timeline.setFocus()
        QTest.qWait(20)
        QTest.keyClick(window.timeline, Qt.Key_Comma)
        QTest.keyClick(window.timeline, Qt.Key_Left, Qt.ControlModifier)
        window.nudgeLeft.assert_called_once()
        window.timelineSelectPrevious.assert_called_once()
        QTest.keyClick(window.timeline, Qt.Key_Tab)
        self.assertTrue(editor.hasFocus())
        editor.setCursorPosition(len(editor.text()))
        QTest.keyClick(editor, Qt.Key_Comma)
        QTest.keyClick(editor, Qt.Key_Left, Qt.ControlModifier)
        self.assertTrue(editor.text().endswith(','))
        self.assertLess(editor.cursorPosition(), len(editor.text()))
        window.nudgeLeft.assert_called_once()
        window.timelineSelectPrevious.assert_called_once()
        QTest.keyClick(editor, Qt.Key_Backtab)
        self.assertTrue(window.timeline.hasFocus())

    def test_ctrl_horizontal_shortcuts_select_real_query_results(self):
        import importlib
        from types import MethodType
        from qt_api import QMainWindow, QWidget, Qt, QKeySequence, QT_API
        from classes import query
        from tests.qt_test_app import get_or_create_app
        from tests.test_main_window import DummyApp, ensure_app_state
        app, _owned = get_or_create_app(DummyApp)
        ensure_app_state(app)
        from windows.main_window import MainWindow
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        window = QMainWindow()
        window.selected_clips = ['a']
        window.selected_transitions = []
        window.preview_thread = SimpleNamespace(current_frame=1)

        class TestCanvas(KeyboardMixin, QWidget):
            def __init__(self):
                super().__init__()
                self.win = window
                self.geometry = Mock()
                self.fps_float = 30
                self.track_list = [SimpleNamespace(data={'number': 2})]
                self._keyboard_reveal = Mock()
                self.setFocusPolicy(Qt.StrongFocus)

            def _select_timeline_item(self, identity, kind, clear):
                if clear:
                    window.selected_clips.clear()
                if identity not in window.selected_clips:
                    window.selected_clips.append(identity)

        window.timeline = TestCanvas()
        window.setCentralWidget(window.timeline)
        names = ['timelineSelectPrevious', 'timelineSelectNext', 'timelineExtendNext',
                 'timelineSelectAtPlayhead', 'timelineExtendAtPlayhead', 'timelinePreviousFiveFrames', 'timelineNextFiveFrames']
        window.PauseSignal = Mock()
        window.SeekSignal = Mock()
        for name in names + ['_timeline_keyboard']:
            setattr(window, name, MethodType(getattr(MainWindow, name), window))
        defaults = json.loads((Path(__file__).parents[1] / 'settings/_default.settings').read_text())
        bindings = {i['setting']: i['value'] for i in defaults if i['setting'] in names}
        window.getAllKeyboardShortcuts = lambda: [{'setting': name} for name in names]
        window.getShortcutByName = lambda name: [QKeySequence(bindings[name])]
        MainWindow.initShortcuts(window)
        self.addCleanup(window.close)
        window.show()
        window.activateWindow()
        window.timeline.setFocus()
        QTest.qWait(20)
        clips = [clip('c', 2, 3).data, clip('a', 2, 0).data, clip('b', 2, 2).data,
                 clip('lower', 1, 3).data]
        project = SimpleNamespace(get=lambda key: clips if key == ['clips'] else [])
        with patch.object(query, 'get_app', return_value=SimpleNamespace(
                project=project, updates=SimpleNamespace(data_version=object()))):
            QTest.keyClick(window.timeline, Qt.Key_Right, Qt.ControlModifier)
            self.assertEqual(window.selected_clips, ['b'])
            QTest.keyClick(window.timeline, Qt.Key_Right, Qt.ControlModifier | Qt.ShiftModifier)
            self.assertEqual(window.selected_clips, ['b', 'c'])
            QTest.keyClick(window.timeline, Qt.Key_Left, Qt.ControlModifier)
            self.assertEqual(window.selected_clips, ['b'])
            QTest.keyClick(window.timeline, Qt.Key_Left, Qt.ControlModifier)
            self.assertEqual(window.selected_clips, ['a'])
            QTest.keyClick(window.timeline, Qt.Key_D, Qt.ControlModifier | Qt.ShiftModifier)
            self.assertEqual(window.selected_clips, ['a'])
            window.preview_thread.current_frame = 91
            QTest.keyClick(window.timeline, Qt.Key_D)
            self.assertEqual(window.selected_clips, ['c'])
            QTest.keyClick(window.timeline, Qt.Key_D, Qt.ControlModifier | Qt.ShiftModifier)
            self.assertEqual(window.selected_clips, ['c', 'lower'])
            QTest.keyClick(window.timeline, Qt.Key_D)
            self.assertEqual(window.selected_clips, ['c'])
            QTest.keyClick(window.timeline, Qt.Key_Right, Qt.ShiftModifier)
            window.SeekSignal.emit.assert_called_with(96, True)
            QTest.keyClick(window.timeline, Qt.Key_Left, Qt.ShiftModifier)
            window.SeekSignal.emit.assert_called_with(86, True)

    def test_tab_order_handles_views_with_window_attribute(self):
        from qt_api import QWidget, Qt
        from classes import tabstops
        from tests.qt_test_app import get_or_create_app
        from tests.test_main_window import DummyApp, ensure_app_state
        app, _owned = get_or_create_app(DummyApp)
        ensure_app_state(app)
        root = QWidget()
        first, second, third = [QWidget(root) for _ in range(3)]
        self.addCleanup(root.close)
        first.window = root
        for widget in (first, second, third):
            widget.setFocusPolicy(Qt.StrongFocus)
        tabstops.safe_set_tab_order(first, third)
        self.assertIs(first.nextInFocusChain(), third)
        tabstops.apply_explicit_tab_order([first, second], include_hidden=True)
        self.assertIs(first.nextInFocusChain(), second)
