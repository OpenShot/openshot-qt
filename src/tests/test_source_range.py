"""Source ruler interaction, explicit range commits, and preview loop bounds."""
import copy
import os
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from qt_api import QDialog, Qt, QEvent, QApplication, QPoint
from classes import info, ui_util
from classes.query import File, Clip
from classes.updates import UpdateManager
from windows.source_range import SourceRangeMixin
from windows.preview_thread import PreviewParent
from tests.qt_test_app import get_or_create_app
from tests.test_main_window import DummyApp, ensure_app_state


class RangeDialog(SourceRangeMixin, QDialog):
    def __init__(self, file, clip_id=None, preview=True):
        super().__init__()
        ui_util.load_ui(self, os.path.join(info.PATH, 'windows', 'ui', 'cutting.ui'))
        self.file = file
        self.file_path = file.data['path']
        self.range_clip_id = clip_id
        self.is_preview_mode = preview
        self._preview_autoplay_active = preview
        self.fps_num, self.fps_den, self.fps = 30, 1, 30
        self.video_length = 300
        self.btnPlay_clicked = Mock()
        self._setup_source_range()
        self._range_timer.stop()


class SourceRangeTests(unittest.TestCase):
    def setUp(self):
        self.qt_app, _ = get_or_create_app(DummyApp)
        ensure_app_state(self.qt_app)
        self.updates = UpdateManager()
        self.data = {
            'files': [dict(id='source', path='/media/test.mp4', start=2.0, end=5.0, duration=10.0, is_split_file=True)],
            'clips': [dict(id='clip', file_id='source', title='Interview', position=11.0,
                           start=2.0, end=5.0, duration=3.0, layer=1, time={'Points': [{'co': {'X': 1, 'Y': 1}}]})],
        }
        self.saved = copy.deepcopy(self.data)
        self.window = types.SimpleNamespace(timeline=types.SimpleNamespace(_is_track_locked=Mock(return_value=False)),
                                            IgnoreUpdates=Mock(), verifySelections=Mock(), removeSelection=Mock(), show_property_timer=Mock(), selection_timer=Mock())
        self.app = types.SimpleNamespace(_tr=lambda text: text, updates=self.updates, window=self.window, processEvents=Mock())
        def lookup(model, item_id):
            row = next((row for row in self.data[model.object_name] if row['id'] == item_id), None)
            if row is None:
                return None
            obj = model()
            obj.id, obj.key, obj.type = item_id, [model.object_name, {'id': item_id}], 'update'
            obj.data = copy.deepcopy(row)
            return obj
        self.lookup = lookup
        for model in (File, Clip):
            patcher = patch.object(model, 'get', side_effect=lambda id, model=model: lookup(model, id))
            patcher.start()
            self.addCleanup(patcher.stop)
        for module in ('windows.source_range', 'windows.views.source_ruler', 'classes.updates', 'classes.query'):
            patcher = patch(module + '.get_app', return_value=self.app)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(File, 'filter', side_effect=lambda: [lookup(File, row['id']) for row in self.data['files']])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app.project = types.SimpleNamespace(generate_id=lambda: 'new-file')
        def apply(action):
            table = self.data[action.key[0]]
            if action.type == 'insert':
                table.append(copy.deepcopy(action.values))
            elif action.type == 'delete':
                action.set_old_values(copy.deepcopy(next(row for row in table if row['id'] == action.key[1]['id'])))
                table[:] = [r for r in table if r['id'] != action.key[1]['id']]
            else:
                row = next(r for r in table if r['id'] == action.key[1]['id'])
                action.set_old_values(copy.deepcopy(row))
                row.update(copy.deepcopy(action.values))
        self.updates.add_listener(types.SimpleNamespace(changed=apply))
        def update_clip(data, transaction_id=None, **kwargs):
            self.updates.transaction_id = transaction_id
            self.updates.update(['clips', {'id': data['id']}], data)
        self.window.timeline.update_clip_data = Mock(side_effect=update_clip)

    def dialog(self, clip_id=None, preview=False):
        dialog = RangeDialog(self.lookup(File, 'source'), clip_id, preview)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        return dialog

    def test_preview_autoplay_survives_source_range_setup(self):
        for trimmed in (False, True):
            self.data['files'][0].update(
                start=2.0 if trimmed else 0.0,
                end=5.0 if trimmed else 10.0, is_split_file=trimmed)
            for clip_id in (None, 'clip'):
                for preview in (False, True):
                    with self.subTest(trimmed=trimmed, clip_id=clip_id, preview=preview):
                        dialog = self.dialog(clip_id=clip_id, preview=preview)
                        self.assertEqual(dialog._preview_autoplay_active, preview)

    def mock_reject(self, dialog):
        # Qt's native closeEvent calls this void method during dialog cleanup.
        patcher = patch.object(dialog, 'reject', return_value=None)
        reject = patcher.start()
        self.addCleanup(patcher.stop)  # Restore reject before dialog.close().
        return reject

    def test_reject_mock_returns_none_and_is_restored_before_dialog_cleanup(self):
        d = self.dialog()
        original_reject = d.reject
        reject = self.mock_reject(d)
        self.assertIsNone(d.reject())
        reject.assert_called_once_with()
        d.show()
        self.qt_app.processEvents()
        self.assertTrue(d.isVisible())
        self.doCleanups()
        self.assertEqual(d.reject, original_reject)
        self.assertFalse(d.isVisible())

    def test_timeline_markers_preview_then_apply_only_target_with_undo_redo(self):
        d = self.dialog('clip')
        self.assertEqual((d.start_frame, d.end_frame), (61, 150))
        self.assertEqual(d.sliderVideo.maximum(), 300)
        d.sliderVideo.move_edge('in', 31)
        d.sliderVideo.move_edge('out', 210)
        self.assertEqual(self.data, self.saved)
        self.assertEqual(len(self.updates.actionHistory), 0)
        d._save_source_range()
        clip = self.data['clips'][0]
        self.assertEqual((clip['start'], clip['end'], clip['duration'], clip['position']), (1, 7, 6, 11))
        self.assertEqual(self.data['files'], self.saved['files'])
        self.assertEqual(len(self.updates.actionHistory), 1)
        self.updates.undo()
        self.assertEqual(self.data, self.saved)
        d._check_range_target()
        self.assertEqual((d.start_frame, d.end_frame), (61, 150))
        self.updates.redo()
        d._check_range_target()
        self.assertEqual((d.start_frame, d.end_frame), (31, 210))

    def test_split_entry_can_expand_to_full_source_without_changing_existing_clips(self):
        d = self.dialog()
        self.assertEqual(d.range_mode, 'file')
        d.sliderVideo.move_edge('in', 1)
        d.sliderVideo.move_edge('out', 300)
        self.assertEqual(self.data, self.saved)
        d._save_source_range()
        self.assertEqual((self.data['files'][0]['start'], self.data['files'][0]['end']), (0, 10))
        self.assertEqual(self.data['clips'], self.saved['clips'])
        self.updates.undo()
        self.assertEqual(self.data, self.saved)

    def test_generated_range_title_follows_updates_and_custom_title_is_preserved(self):
        d = self.dialog()
        self.data['files'][0]['name'] = d._default_range_name(61, 150)
        d._reset_source_range()
        self.assertEqual(d.txtName.text(), '')
        d.sliderVideo.move_edge('out', 180)
        d._save_source_range()
        self.assertEqual(self.data['files'][0]['name'], d._default_range_name(61, 180))
        d._reset_source_range()
        d.sliderVideo.move_edge('out', 210)
        d._save_source_range()
        self.assertEqual(self.data['files'][0]['name'], d._default_range_name(61, 210))
        d.txtName.setText('Interview excerpt')
        d._save_source_range()
        d._reset_source_range()
        d.sliderVideo.move_edge('out', 240)
        d._save_source_range()
        self.assertEqual(self.data['files'][0]['name'], 'Interview excerpt')

    def test_create_preserves_original_file_and_creates_marked_range(self):
        self.data['files'][0].update(start=0, end=10, is_split_file=False)
        self.saved = copy.deepcopy(self.data)
        d = self.dialog(preview=False)
        d.sliderVideo.move_edge('in', 91)
        d.sliderVideo.move_edge('out', 91)
        d.txtName.setText('One frame')
        d._save_source_range()
        self.assertEqual(self.data['files'][0], self.saved['files'][0])
        new = self.data['files'][1]
        self.assertEqual(new['name'], 'One frame')
        self.assertEqual(new['start'], 3)
        self.assertAlmostEqual(new['end']-new['start'], 1/30)
        self.assertEqual(self.data['clips'], self.saved['clips'])

    def test_locked_retimed_deleted_and_externally_changed_targets_do_not_apply(self):
        d = self.dialog('clip')
        d.sliderVideo.move_edge('in', 31)
        self.window.timeline._is_track_locked.return_value = True
        d._save_source_range()
        self.assertEqual(self.updates.actionHistory, [])
        self.window.timeline._is_track_locked.return_value = False
        row = self.data['clips'][0]
        row['time']['Points'].append({'co': {'X': 30, 'Y': 15}})
        d._save_source_range()
        self.assertEqual(self.updates.actionHistory, [])
        row['time'] = self.saved['clips'][0]['time']
        row['end'] = 4
        d._save_source_range()
        self.assertIn('changed elsewhere', d.range_status.text())
        self.assertEqual(self.updates.actionHistory, [])
        d._reset_source_range()
        self.assertEqual(d.end_frame, 120)
        d.sliderVideo.move_edge('in', 1)
        self.data['clips'].clear()
        d._save_source_range()
        self.assertIn('no longer exists', d.range_status.text())
        self.assertEqual(self.updates.actionHistory, [])

    def test_ruler_clamps_crossing_markers_and_timecode_sets_frame(self):
        d = self.dialog()
        r = d.sliderVideo
        r.move_edge('in', 299)
        self.assertEqual((r.in_frame, r.out_frame), (150, 150))
        r.move_edge('out', -10)
        self.assertEqual((r.in_frame, r.out_frame), (150, 150))
        self.assertEqual(self.data, self.saved)
        d.range_edits['in'].setText('00:00:01,00')
        d.range_edits['in'].commit()
        self.assertEqual(r.in_frame, 31)

    def test_scrubbing_preserves_range_and_reset_clears_pending_changes(self):
        import importlib
        from qt_api import QT_API
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        d = self.dialog()
        d.resize(800, 450)
        d.show()
        d.activateWindow()
        self.qt_app.processEvents()
        r = d.sliderVideo
        self.assertEqual(self.data, self.saved)
        bounds = (r.in_frame, r.out_frame)
        QTest.mouseClick(r, Qt.LeftButton, pos=QPoint(r.width()-2, 12))
        self.assertGreater(r.value(), r.out_frame)
        self.assertEqual((r.in_frame, r.out_frame), bounds)
        d._reset_source_range()
        self.assertFalse(d.range_dirty)
        r.move_edge('in', 31)
        r.move_edge('in', 61)
        self.assertFalse(d.range_dirty)
        self.assertFalse(d.btnAddClip.isEnabled())

    def test_visible_edges_drag_with_playhead_and_clamp_without_saving(self):
        import importlib
        from qt_api import QT_API, QMouseEvent, QPointF
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        d = self.dialog()
        d.resize(800, 450)
        d.show()
        self.qt_app.processEvents()
        r = d.sliderVideo
        for edge, first, last, delta in (('in', 61, 150, 40), ('out', 61, 150, 60),
                                        ('in', 61, 150, 700), ('out', 61, 150, -700)):
            r.set_region(first, last)
            x = round(r._x(first - 1 if edge == 'in' else last))
            self.assertEqual(r.edge_at(x), edge)
            start = QPoint(x, r.ruler_height + r.filmstrip_height // 2)
            end = QPoint(x + delta, start.y())
            QTest.mousePress(r, Qt.LeftButton, pos=start)
            self.assertTrue(r.isSliderDown())
            QApplication.sendEvent(r, QMouseEvent(QEvent.MouseMove, QPointF(end),
                                                  Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            QTest.mouseRelease(r, Qt.LeftButton, pos=end)
            self.assertFalse(r.isSliderDown())
            self.assertEqual(r.value(), r.in_frame if edge == 'in' else r.out_frame)
            self.assertLessEqual(r.in_frame, r.out_frame)
            self.assertNotEqual((r.in_frame, r.out_frame), (first, last))
        self.assertEqual(self.data, self.saved)
        self.assertEqual(self.updates.actionHistory, [])

    def test_range_move_draw_and_endpoint_grips(self):
        import importlib
        from qt_api import QT_API, QMouseEvent, QPointF
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        d = self.dialog()
        d.show()
        self.qt_app.processEvents()
        r = d.sliderVideo
        y = r.ruler_height + r.filmstrip_height // 2

        def drag(first, last):
            QTest.mousePress(r, Qt.LeftButton, pos=first)
            QApplication.sendEvent(r, QMouseEvent(QEvent.MouseMove, QPointF(last),
                                                  Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            QTest.mouseRelease(r, Qt.LeftButton, pos=last)

        r.set_region(61, 150)
        drag(QPoint(round(r._x(100)), y), QPoint(r.width()+200, y))
        self.assertEqual((r.in_frame, r.out_frame), (211, 300))
        drag(QPoint(round(r._x(100)), y), QPoint(round(r._x(40)), y))
        self.assertLess(abs(r.in_frame-41), 2)
        self.assertLess(abs(r.out_frame-101), 2)
        bounds = r.in_frame, r.out_frame
        drag(QPoint(0, 10), QPoint(r.width()-1, 10))
        self.assertEqual((r.in_frame, r.out_frame), bounds)
        self.assertEqual(r.value(), r.maximum())
        r.set_region(1, 300)
        left, right = r._grip_rects()
        # Include the outer halves of the actual painted grips at source limits.
        self.assertEqual(r._hit_target(left.center()), 'left')
        self.assertEqual(r._hit_target(right.center()), 'right')
        for frame in (1, 150, 300):
            r.set_region(frame, frame)
            left, right = r._grip_rects()
            self.assertEqual(r._hit_target(left.center()), 'left')
            self.assertEqual(r._hit_target(right.center()), 'right')
        r.set_region(150, 150)
        center = (r._x(149)+r._x(150))/2
        self.assertEqual(r._hit_target(QPointF(center-2, y)), 'left')
        self.assertEqual(r._hit_target(QPointF(center+2, y)), 'right')
        self.assertEqual(self.data, self.saved)

    def test_create_stays_open_and_apply_closes_only_after_success(self):
        from windows.cutting import Cutting
        self.data['files'][0].update(start=0, end=10, is_split_file=False)
        d = self.dialog()
        self.mock_reject(d)
        d.txtName.setText('Opening')
        self.assertEqual(d.btnAddClip.text(), 'Create')
        Cutting.btnAddClip_clicked(d)
        d.reject.assert_not_called()
        self.assertEqual(self.data['files'][-1]['name'], 'Opening')
        self.assertEqual(d.txtName.text(), '')
        self.assertFalse(hasattr(d, 'range_table'))
        self.assertTrue(d.buttonBox.isHidden())
        clip = self.dialog('clip')
        self.mock_reject(clip)
        self.assertEqual(clip.btnAddClip.text(), 'Update Clip')
        clip.sliderVideo.move_edge('out', 180)
        self.window.timeline._is_track_locked.return_value = True
        Cutting.btnAddClip_clicked(clip)
        clip.reject.assert_not_called()
        self.window.timeline._is_track_locked.return_value = False
        Cutting.btnAddClip_clicked(clip)
        clip.reject.assert_called_once_with()

    def test_handles_stay_centered_on_source_boundaries(self):
        r = self.dialog().sliderVideo
        for first, last in ((1, 300), (1, 1), (300, 300), (100, 200)):
            r.set_region(first, last)
            left, right = r._grip_rects()
            self.assertEqual(left.center().x(), r._x(first-1))
            self.assertEqual(right.center().x(), r._x(last))
            self.assertGreaterEqual(left.left(), 0)
            self.assertLessEqual(right.right(), r.width())

    def test_range_controls_reflow_and_keep_video_space_when_resized(self):
        d = self.dialog()
        d.show()
        for width in (700, 1130, 700):
            d.resize(width, 540)
            self.qt_app.processEvents()
            self.assertEqual(d.size().width(), width)
            self.assertEqual(d.rangeControlsLayout.getItemPosition(3)[0], 0)
            self.assertLess(d.widgetControls.height(), 150)
            self.assertFalse(d.txtName.isHidden())
            self.assertFalse(d.btnAddClip.isHidden())

    def test_preview_keyboard_moves_trims_scrubs_and_leaves_name_typing_alone(self):
        import importlib
        from qt_api import QT_API
        from windows.preview_keyboard import PreviewKeyboard
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        d = self.dialog()
        d.preview_thread = types.SimpleNamespace(player=types.SimpleNamespace(Speed=lambda: 1))
        d.SpeedSignal = Mock()
        with patch('windows.preview_keyboard.get_app', return_value=self.app):
            d.preview_keyboard = PreviewKeyboard(d)
        d.show()
        d.activateWindow()
        d.sliderVideo.setFocus()
        self.qt_app.processEvents()
        r = d.sliderVideo
        QTest.keyClick(r, Qt.Key_Period)
        self.assertEqual((r.in_frame, r.out_frame), (62, 151))
        QTest.keyClick(r, Qt.Key_BracketLeft)
        QTest.keyClick(r, Qt.Key_Comma, Qt.ShiftModifier)
        self.assertEqual((r.in_frame, r.out_frame), (57, 151))
        self.assertEqual(r.active_edge, 'in')
        QTest.keyClick(r, Qt.Key_BracketRight)
        QTest.keyClick(r, Qt.Key_Period)
        self.assertEqual((r.in_frame, r.out_frame), (57, 152))
        QTest.keyClick(r, Qt.Key_Escape)
        self.assertIsNone(r.active_edge)
        self.assertTrue(d.isVisible())
        QTest.keyClick(r, Qt.Key_Left)
        self.assertEqual((r.in_frame, r.out_frame), (57, 152))
        QTest.keyClick(r, Qt.Key_Space)
        self.assertTrue(d.btnPlay.isChecked())
        QTest.keyClick(r, Qt.Key_L)
        d.SpeedSignal.emit.assert_called_with(2)
        QTest.keyClick(r, Qt.Key_K)
        d.btnPlay_clicked.assert_called_with(force='pause')
        d.txtName.setFocus()
        QTest.keyClicks(d.txtName, 'jkl,.[]')
        self.assertIn('jkl,.[]', d.txtName.text())
        self.assertEqual((r.in_frame, r.out_frame), (57, 152))
        self.assertEqual(self.data, self.saved)

    def test_fit_window_accounts_for_controls_and_source_pixel_ratio(self):
        from windows.preview_design import fit_source_window
        from qt_api import QSize, QRect
        video = types.SimpleNamespace(size=lambda: QSize(600, 200),
                                      aspect_ratio=types.SimpleNamespace(ToFloat=lambda: 4/3),
                                      pixel_ratio=types.SimpleNamespace(ToFloat=lambda: 1.5))
        screen = types.SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 1920, 1080))
        d = types.SimpleNamespace(videoPreview=video, verticalLayout=Mock(),
                                  size=lambda: QSize(640, 400),
                                  windowHandle=lambda: types.SimpleNamespace(screen=lambda: screen),
                                  resize=Mock())
        fit_source_window(d)
        d.resize.assert_called_once_with(640, 500)

    def test_scrubbing_does_not_pause_active_playback(self):
        from windows.cutting import Cutting
        d = self.dialog()
        d.preview_thread = Mock()
        d.sliderIgnoreSignal = False
        d.previewFrameSignal = Mock()
        d.slider_timer = Mock()
        d.btnPlay.setChecked(True)
        Cutting.sliderVideo_valueChanged(d, 80)
        Cutting.sliderVideo_released(d)
        Cutting.sliderVideo_timeout(d)
        d.btnPlay_clicked.assert_not_called()
        self.assertTrue(d.btnPlay.isChecked())
        d.previewFrameSignal.emit.assert_any_call(80)

    def test_range_drag_pauses_before_seeking_but_click_does_not(self):
        import importlib
        from qt_api import QT_API, QMouseEvent, QPointF
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        d = self.dialog()
        d.show()
        self.qt_app.processEvents()
        r = d.sliderVideo
        events = []
        d.btnPlay_clicked.side_effect = lambda **kwargs: events.append('pause')
        r.valueChanged.connect(lambda value: events.append('seek'))
        for target in ('left', 'move', 'create'):
            r.set_region(61, 150)
            d.btnPlay.setChecked(True)
            x = round(r._x({'left': 60, 'move': 100, 'create': 220}[target]))
            start = QPoint(x, r.ruler_height + r.filmstrip_height//2)
            events.clear()
            QTest.mousePress(r, Qt.LeftButton, pos=start)
            self.assertEqual(events, [])
            end = QPoint(x+30, start.y())
            QApplication.sendEvent(r, QMouseEvent(QEvent.MouseMove, QPointF(end),
                                                  Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            QTest.mouseRelease(r, Qt.LeftButton, pos=end)
            self.assertEqual(events[0], 'pause')
            self.assertIn('seek', events)
        events.clear()
        QTest.mouseClick(r, Qt.LeftButton, pos=QPoint(30, 10))
        self.assertNotIn('pause', events)

    def test_filmstrip_uses_landscape_cells_at_different_widths(self):
        r = self.dialog(preview=True).sliderVideo
        r.filmstrip_frames = list(range(1, 13))
        self.assertEqual(r.filmstrip_height, 46)
        for width in (400, 650, 1100):
            frames = r._visible_filmstrip_frames(width)
            self.assertGreaterEqual(width/len(frames)/r.filmstrip_height, 16/9)
            self.assertEqual(frames[0], 1)
            self.assertEqual(frames[-1], 12)
            self.assertLessEqual(len(frames), 12)

    def test_source_ruler_labels_are_dense_without_colliding(self):
        r = self.dialog(preview=True).sliderVideo
        r.setRange(1, 52*30)
        for width in (600, 940, 1200):
            r.resize(width, r.height())
            frames = r.painter._frames_per_tick(r.pixels_per_second, 30)
            spacing = 2*frames/30*r.pixels_per_second
            self.assertGreaterEqual(spacing, r.fontMetrics().horizontalAdvance('00:00')+20)
            self.assertGreaterEqual(int(52*30/(frames*2))+1, 6)

    def test_split_update_closes_and_thumbnail_refresh_follows_undo_redo(self):
        from windows.cutting import Cutting
        from windows.models.files_model import FilesModel
        from windows.views.timeline import TimelineView
        files = types.SimpleNamespace(update_model=Mock(), update_file_thumbnail=Mock())
        timeline = types.SimpleNamespace(invalidate_file_thumbnails=Mock())
        self.updates.add_listener(types.SimpleNamespace(changed=lambda action: FilesModel.changed(files, action)))
        self.updates.add_listener(types.SimpleNamespace(changed=lambda action: TimelineView.changed(timeline, action)))
        d = self.dialog()
        self.assertEqual(d.btnAddClip.text(), 'Update')
        self.mock_reject(d)
        d.sliderVideo.move_edge('in', 31)
        Cutting.btnAddClip_clicked(d)
        d.reject.assert_called_once_with()
        files.update_file_thumbnail.assert_called_once_with('source')
        timeline.invalidate_file_thumbnails.assert_called_once_with('source')
        self.updates.undo()
        self.updates.redo()
        self.assertEqual(files.update_file_thumbnail.call_count, 3)
        self.assertEqual(timeline.invalidate_file_thumbnails.call_count, 3)
        self.assertEqual(self.data['clips'], self.saved['clips'])

    def test_file_thumbnail_invalidation_targets_dependent_clips(self):
        from windows.views.timeline import TimelineView, TimelineWidget
        import windows.views.timeline as module
        timeline = types.SimpleNamespace(clip_painter=Mock(), update=Mock())
        clips = [types.SimpleNamespace(id='a'), types.SimpleNamespace(id='b')]
        with patch.object(module, 'ViewClass', TimelineWidget), patch.object(Clip, 'filter', return_value=clips) as query:
            TimelineView.invalidate_file_thumbnails(timeline, 'source')
        query.assert_called_once_with(file_id='source')
        self.assertEqual([call.args[0] for call in timeline.clip_painter.invalidate_clip_thumbnails.call_args_list], ['a', 'b'])
        timeline.update.assert_called_once_with()

    def test_duration_edit_moves_end_and_clamps_to_valid_source_range(self):
        d = self.dialog()
        start = d.start_frame
        for text, expected_end, expected_text in (
                ('00:00:04.00', 180, '00:00:04.00'),
                ('00:00:01.00', 90, '00:00:01.00'),
                ('00:10:00.00', 300, '00:00:08.00'),
                ('00:10:00.00', 300, '00:00:08.00'),
                ('00:00:00.00', 61, '00:00:00.01')):
            d.range_duration.setText(text)
            self.assertTrue(d.range_duration.commit())
            self.assertEqual(d.start_frame, start)
            self.assertEqual(d.end_frame, expected_end)
            self.assertEqual(d.range_duration.text(), expected_text)
        d.range_duration.setText('invalid')
        self.assertFalse(d.range_duration.commit())
        self.assertEqual(d.range_duration.text(), '00:00:00.01')
        self.assertEqual(self.data, self.saved)
        d._save_source_range()
        self.assertAlmostEqual(self.data['files'][0]['end'], 61/30)
        self.updates.undo()
        self.assertEqual(self.data, self.saved)

    def test_enter_commits_duration_then_accepts_outside_time_fields(self):
        import importlib
        from qt_api import QT_API
        from windows.cutting import Cutting
        from windows.preview_keyboard import PreviewKeyboard
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        for mode in ('file', 'clip', 'create'):
            if mode == 'create':
                self.data['files'][0].update(start=0, end=10, is_split_file=False)
            d = self.dialog('clip' if mode == 'clip' else None)
            d.accept_source_changes = types.MethodType(Cutting.accept_source_changes, d)
            self.mock_reject(d)
            with patch('windows.preview_keyboard.get_app', return_value=self.app):
                d.preview_keyboard = PreviewKeyboard(d)
            d.show()
            d.activateWindow()
            d.range_duration.setFocus()
            self.qt_app.processEvents()
            d.range_duration.setText('00:00:02.00')
            QTest.keyClick(d.range_duration, Qt.Key_Return)
            d.reject.assert_not_called()
            self.assertTrue(d.range_duration.hasFocus())
            self.assertFalse(d.range_duration.isHidden())
            self.assertEqual(d.end_frame-d.start_frame+1, 60)
            target = d.btnAddClip if mode == 'clip' else d.txtName
            target.setFocus()
            if mode == 'create':
                d.txtName.setText('First split')
            QTest.keyClick(target, Qt.Key_Return)
            if mode == 'create':
                d.reject.assert_not_called()
                self.assertTrue(d.isVisible())
                self.assertTrue(d.txtName.hasFocus())
                self.assertEqual(d.txtName.text(), '')
                self.assertEqual(self.data['files'][-1]['name'], 'First split')
            else:
                d.reject.assert_called_once_with()
            saved = self.data['clips'][0] if mode == 'clip' else self.data['files'][-1 if mode == 'create' else 0]
            self.assertAlmostEqual(saved['end']-saved['start'], 2)
            d.hide()

    def test_keyboard_accept_keeps_invalid_or_blocked_changes_open(self):
        from windows.cutting import Cutting
        d = self.dialog('clip')
        self.mock_reject(d)
        d.show()
        d.range_duration.setFocus()
        self.qt_app.processEvents()
        d.range_duration.setText('invalid')
        Cutting.accept_source_changes(d)
        d.reject.assert_not_called()
        self.assertEqual(self.data, self.saved)
        d.range_duration.setText('00:00:02.00')
        self.window.timeline._is_track_locked.return_value = True
        Cutting.accept_source_changes(d)
        d.reject.assert_not_called()
        self.assertEqual(self.data, self.saved)

    def test_time_segment_stepping_keeps_selection_and_tab_order(self):
        import importlib
        from qt_api import QT_API
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        d = self.dialog()
        d.show()
        d.activateWindow()
        self.qt_app.processEvents()
        edits = [d.range_edits['in'], d.range_edits['out'], d.range_duration]
        for edit in edits:
            edit.setFocus()
            edit.setCursorPosition(6)
            QTest.keyClick(edit, Qt.Key_Up)
            self.assertEqual(edit.selectionStart(), 6)
            QTest.keyClick(edit, Qt.Key_Down)
            self.assertEqual(edit.selectionStart(), 6)
            self.assertEqual(len(edit.selectedText()), 2)
            edit.setCursorPosition(3)
            QTest.keyClick(edit, Qt.Key_Up)
            self.assertEqual(edit.selectionStart(), 3)
            QTest.keyClick(edit, Qt.Key_Down)
            self.assertEqual(edit.selectionStart(), 3)
            edit.setCursorPosition(9)
            QTest.keyClick(edit, Qt.Key_Up)
            self.assertEqual(edit.selectionStart(), 9)
        chain = edits + [d.txtName]
        chain[0].setFocus()
        for widget in chain[1:]:
            QTest.keyClick(d.focusWidget(), Qt.Key_Tab)
            self.assertIs(d.focusWidget(), widget)
        for widget in reversed(chain[:-1]):
            QTest.keyClick(d.focusWidget(), Qt.Key_Tab, Qt.ShiftModifier)
            self.assertIs(d.focusWidget(), widget)
        self.assertEqual(self.data, self.saved)

    def test_filmstrip_requests_are_bounded_and_not_repeated_for_range_changes(self):
        d = self.dialog()
        self.window.http_server_thread = types.SimpleNamespace(server_address=('127.0.0.1', 1234))
        network = Mock()
        def new_reply(request):
            reply = Mock()
            reply.readAll.return_value = b''
            return reply
        network.get.side_effect = new_reply
        d._range_thumb_network = network
        d._range_thumb_module = types.SimpleNamespace(QNetworkRequest=lambda url: url)
        d._refresh_range_thumbnails()
        self.assertEqual(len(d._range_thumb_replies), 2)
        while d._range_thumb_replies:
            frame, reply = next(iter(d._range_thumb_replies.items()))
            d._range_thumbnail_ready(frame, reply)
            d._refresh_range_thumbnails()
            self.assertLessEqual(len(d._range_thumb_replies), 2)
        self.assertEqual(network.get.call_count, 12)
        d.sliderVideo.move_edge('in', 75)
        d._refresh_range_thumbnails()
        self.assertEqual(network.get.call_count, 12)
        d._stop_range_thumbnails()
        self.assertFalse(d._range_thumb_timer.isActive())

    def test_reopened_filmstrips_load_shared_disk_cache_without_network(self):
        from qt_api import QPixmap
        from classes import thumbnail
        frames = [1 + round(i * 299 / 11) for i in range(12)]
        self.data['files'][0]['fps'] = {'num': 30, 'den': 1}
        with tempfile.TemporaryDirectory() as root, patch.object(thumbnail.info, 'THUMBNAIL_PATH', root):
            os.makedirs(os.path.join(root, 'source'))
            image = QPixmap(96, 54)
            image.fill(Qt.red)
            for frame in frames:
                # Timeline prewarming uses coarse source-frame samples.
                cached_frame = thumbnail.RoundFrameToThumbnailGrid(frame, 30)
                self.assertTrue(image.save(thumbnail.ThumbnailPathForFrame('source', cached_frame)))
            for _ in range(3):
                d = self.dialog()
                d._refresh_range_thumbnails()
                self.assertEqual(set(d.sliderVideo.filmstrip_images), set(frames))
                self.assertIsNone(d._range_thumb_network)
                self.assertFalse(d._range_thumb_replies)
                d._stop_range_thumbnails()

    def test_filmstrip_loads_later_cached_samples_while_first_requests_are_pending(self):
        from qt_api import QPixmap
        from classes import thumbnail
        with tempfile.TemporaryDirectory() as root, patch.object(thumbnail.info, 'THUMBNAIL_PATH', root):
            os.makedirs(os.path.join(root, 'source'))
            image = QPixmap(96, 54)
            image.fill(Qt.red)
            path = thumbnail.ThumbnailPathForFrame('source', 300)
            self.assertTrue(image.save(path))
            d = self.dialog()
            self.window.http_server_thread = types.SimpleNamespace(server_address=('127.0.0.1', 1234))
            d._range_thumb_network = Mock()
            d._range_thumb_module = types.SimpleNamespace(QNetworkRequest=lambda url: url)
            d._refresh_range_thumbnails()
            self.assertIn(300, d.sliderVideo.filmstrip_images)
            self.assertEqual(d._range_thumb_network.get.call_count, 2)
            d._stop_range_thumbnails()
            os.utime(path, (1, 1))
            self.assertEqual(thumbnail.FindCachedThumbnail('source', 300), '')

    def test_start_end_badges_remain_separate_targets_for_one_frame_range(self):
        d = self.dialog()
        r = d.sliderVideo
        r.resize(700, r.height())
        r.set_region(1, 1)
        r.reference_design = False
        labels = r._edge_labels()
        self.assertLessEqual(labels[0][0].right(), labels[1][0].left())
        for edge, (rect, _text) in zip(('in', 'out'), labels):
            self.assertEqual(r.edge_at(rect.center().x(), rect.center().y()), edge)

    def test_plain_preview_has_no_range_editor_or_footer_and_cannot_save(self):
        d = self.dialog(preview=True)
        self.assertEqual(d.range_mode, 'preview')
        self.assertTrue(d.widgetControls.isHidden())
        self.assertTrue(d.buttonBox.isHidden())
        self.assertFalse(hasattr(d, 'range_table'))
        self.assertIsNone(d.sliderVideo.edge_at(0, 0))
        d._save_source_range()
        self.assertEqual(self.data, self.saved)
        clip = self.dialog('clip')
        self.assertTrue(clip.buttonBox.isHidden())
        self.assertFalse(clip.widgetControls.isHidden())

    def test_preview_volume_uses_player_without_editing_source(self):
        from windows.preview_thread import PlayerWorker
        from windows.preview_design import _set_muted
        d = self.dialog(preview=True)
        d.VolumeSignal = Mock()
        d.volume_button.setChecked(True)
        d.VolumeSignal.emit.assert_called_with(0.0)
        d.volume_button.setChecked(False)
        d.VolumeSignal.emit.assert_called_with(1.0)
        self.assertFalse(d.volume_slider.hasTracking())
        d.VolumeSignal.emit.reset_mock()
        d.volume_slider.setSliderDown(True)
        d.volume_slider.setSliderPosition(35)
        d.VolumeSignal.emit.assert_not_called()
        d.volume_slider.setSliderDown(False)
        self.assertTrue(d._volume_timer.isActive())
        d.VolumeSignal.emit.assert_not_called()
        d._volume_timer.stop()
        _set_muted(d, False)
        d.VolumeSignal.emit.assert_called_once_with(0.35)
        import openshot
        d.clip = openshot.Clip()
        worker = types.SimpleNamespace(parent=d, timeline=Mock())
        PlayerWorker.SetVolume(worker, 0.6)
        self.assertAlmostEqual(d.clip.volume.GetValue(1), 0.6)
        worker.timeline.ClearAllCache.assert_not_called()
        worker.timeline.GetCache().Clear.assert_called_once_with()
        PlayerWorker.SetVolume(worker, 0)
        self.assertEqual(d.clip.volume.GetValue(1), 0)
        self.assertEqual(self.data, self.saved)

    def test_split_identity_survives_expanding_to_full_source_and_reopening(self):
        d = self.dialog()
        d.sliderVideo.move_edge('in', 1)
        d.sliderVideo.move_edge('out', 300)
        d._save_source_range()
        reopened = self.dialog()
        self.assertEqual(reopened.range_mode, 'file')
        self.assertEqual((reopened.start_frame, reopened.end_frame), (1, 300))

    def test_loop_uses_in_out_but_scrubbing_and_non_loop_playback_use_full_source(self):
        import openshot
        parent = types.SimpleNamespace(loop_playback=True, playback_range=lambda: (61, 150),
                                       movePlayhead=Mock(), PauseSignal=Mock())
        worker = types.SimpleNamespace(player=types.SimpleNamespace(Mode=lambda: openshot.PLAYBACK_PLAY,
                                                                   Speed=lambda: 1), Seek=Mock())
        preview = types.SimpleNamespace(parent=parent, worker=worker, timeline_max_length=300)
        PreviewParent.onPositionChanged(preview, 150)
        worker.Seek.assert_called_once_with(61)
        worker.Seek.reset_mock()
        parent.loop_playback = False
        PreviewParent.onPositionChanged(preview, 150)
        worker.Seek.assert_not_called()
        PreviewParent.onPositionChanged(preview, 300)
        worker.Seek.assert_called_once_with(300)
        worker.Seek.reset_mock()
        parent.loop_playback = True
        worker.player.Speed = lambda: -1
        PreviewParent.onPositionChanged(preview, 61)
        worker.Seek.assert_called_once_with(150)
        worker.Seek.reset_mock()
        worker.player.Mode = lambda: openshot.PLAYBACK_PAUSED
        PreviewParent.onPositionChanged(preview, 10)
        worker.Seek.assert_not_called()
        parent.movePlayhead.assert_called_with(10)
