"""Mesh preview geometry and CPU effect integration."""
import json
import types
import unittest
from unittest.mock import Mock, patch

import openshot
from qt_api import QApplication, QColor, QImage, QPainter, QPointF, QTransform, Qt
from windows.video_widget import VideoWidget


class DistortGeometryTests(unittest.TestCase):
    def test_drag_inverts_clip_rotation_shear_and_zoom(self):
        transform = QTransform().translate(100, 50).rotate(35).shear(0.2, -0.1).scale(2, 3)
        inverse, _ = transform.inverted()
        anchor = QPointF(30, 40)
        drag = (5, anchor, [0.1, -0.1], 0.5, inverse, (300, 200), 12)
        result = VideoWidget._distort_drag_offsets(drag, transform.map(anchor + QPointF(15, 20)))
        self.assertAlmostEqual(result['point_5_x'], 0.2)
        self.assertAlmostEqual(result['point_5_y'], 0.1)

    def test_negative_strength_and_offset_limits(self):
        drag = (15, QPointF(), [0, 0], -1, QTransform(), (100, 100), 1)
        result = VideoWidget._distort_drag_offsets(drag, QPointF(200, -200))
        self.assertEqual(result, {'point_15_x': -1, 'point_15_y': 1})

    def test_release_commits_selection_and_coordinates_together(self):
        original = {'selected_point': 5, 'point_6_x': {'Points': []}, 'point_6_y': {'Points': []}}
        changed = {'selected_point': 6, 'point_6_x': {'Points': [1]}, 'point_6_y': {'Points': [2]}}
        effect = types.SimpleNamespace(data=dict(changed), save=Mock())
        native = types.SimpleNamespace(info=types.SimpleNamespace(class_name='Distort'))
        widget = types.SimpleNamespace(mouse_pressed=True, mouse_dragging=True, region_enabled=False,
            transforming_clips=[], transforming_effect=types.SimpleNamespace(id='effect'),
            transforming_effect_object=native, original_effect_data=original,
            original_clip_data_map={}, transaction_id='drag', setCursor=Mock(), _restore_transform_playback_cache=Mock())
        updates = types.SimpleNamespace(ignore_history=True, transaction_id='drag', apply_last_action_to_history=Mock())
        app = types.SimpleNamespace(updates=updates, window=None)
        with patch('windows.video_widget.Effect.get', return_value=effect), \
             patch('windows.video_widget.get_app', return_value=app):
            VideoWidget.mouseReleaseEvent(widget, types.SimpleNamespace(accept=lambda: None))
        effect.save.assert_called_once()
        self.assertEqual(effect.data, changed)
        updates.apply_last_action_to_history.assert_called_once_with(original)
        self.assertFalse(updates.ignore_history)
        self.assertIsNone(updates.transaction_id)

    def test_handle_hit_radius_stays_in_screen_space(self):
        widget = types.SimpleNamespace(_distort_handles=[QPointF(100, 100), QPointF(140, 100)], setCursor=Mock())
        VideoWidget._distort_hover(widget, QPointF(105, 100))
        self.assertEqual(widget.hover_transform_mode, 'distort_0')
        VideoWidget._distort_hover(widget, QPointF(120, 130))
        self.assertIsNone(widget.hover_transform_mode)


@unittest.skipUnless(hasattr(openshot, 'Distort'), 'Requires libopenshot Distort')
class DistortPreviewTests(unittest.TestCase):
    def test_overlay_handles_match_evaluated_mesh(self):
        image = QImage(640, 480, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        effect = openshot.Distort()
        effect.SetJson(json.dumps({'preset': 3}))
        effect.Id("distort")
        reader = openshot.DummyReader(openshot.Fraction(30, 1), 640, 480, 44100, 2, 10.0)
        clip = openshot.Clip(reader)
        clip.AddEffect(effect)
        timeline = openshot.Timeline(640, 480, openshot.Fraction(30, 1),
                                     44100, 2, openshot.LAYOUT_STEREO)
        timeline.AddClip(clip)
        native = timeline.GetClipEffect("distort")
        self.assertIsInstance(native, openshot.EffectBase)
        self.assertFalse(hasattr(native, "MeshJSON"))
        widget = types.SimpleNamespace(transforming_effect_object=native,
                                      transform=QTransform().translate(30, 40).rotate(10), handle_opacity=1)
        painter = QPainter(image)
        try:
            VideoWidget._draw_distort_mesh(widget, painter, 500, 300, 1)
        finally:
            painter.end()
        mesh = json.loads(effect.MeshJSON(1, 36))
        self.assertEqual(len(widget._distort_handles), 16)
        for row in range(4):
            for col in range(4):
                x, y = mesh[row * 12 * 37 + col * 12]
                self.assertEqual(widget._distort_handles[row * 4 + col],
                                 widget.transform.map(QPointF(x * 500, y * 300)))

    def test_overlay_tracks_edits_on_timeline_base_proxy(self):
        effect = openshot.Distort()
        effect.Id("distort")
        reader = openshot.DummyReader(openshot.Fraction(30, 1), 640, 480, 44100, 2, 10.0)
        clip = openshot.Clip(reader)
        clip.AddEffect(effect)
        timeline = openshot.Timeline(640, 480, openshot.Fraction(30, 1),
                                     44100, 2, openshot.LAYOUT_STEREO)
        timeline.AddClip(clip)
        native = timeline.GetClipEffect("distort")
        widget = types.SimpleNamespace(transforming_effect_object=native,
                                      transform=QTransform(), handle_opacity=1)
        image = QImage(640, 480, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            VideoWidget._draw_distort_mesh(widget, painter, 600, 300, 1)
            before = QPointF(widget._distort_handles[5])
            native.SetJson(json.dumps({"point_5_x": {"Points": [
                {"co": {"X": 1, "Y": 0}, "interpolation": openshot.LINEAR},
                {"co": {"X": 11, "Y": 0.2}, "interpolation": openshot.LINEAR}]}}))
            VideoWidget._draw_distort_mesh(widget, painter, 600, 300, 11)
            self.assertAlmostEqual(widget._distort_handles[5].x() - before.x(), 120)
            native.SetJson(json.dumps({"preset": 1, "selected_point": 6}))
            VideoWidget._draw_distort_mesh(widget, painter, 600, 300, 11)
            self.assertLess(widget._distort_handles[5].y(), before.y())
        finally:
            painter.end()

    def test_selecting_zero_strength_point_does_not_start_drag(self):
        effect = openshot.Distort()
        effect.SetJson(json.dumps({'strength': {'Points': [{'co': {'X': 1, 'Y': 0}, 'interpolation': 1}]}}))
        widget = types.SimpleNamespace(transform_mode='distort_5', _distort_frame=1,
                                      transforming_effect_object=effect, _distort_transform=QTransform(),
                                      transforming_effect=types.SimpleNamespace(id='effect'), update=Mock())
        with patch('windows.video_widget.Effect.get', return_value=None):
            VideoWidget._begin_distort_drag(widget, QPointF(30, 40))
        self.assertIsNone(widget._distort_drag)

    def test_drag_saves_both_coordinates_as_one_effect_update(self):
        drag = (5, QPointF(0, 0), [0, 0], 1, QTransform(), (100, 100), 12)
        widget = types.SimpleNamespace(mouse_dragging=True, transform_mode='distort_5',
            _distort_drag=drag, transforming_effect=types.SimpleNamespace(id='effect'),
            setCursor=Mock(), update=Mock(), updateEffectProperties=Mock(),
            _distort_drag_offsets=VideoWidget._distort_drag_offsets)
        VideoWidget._move_distort(widget, QPointF(20, 30))
        widget.updateEffectProperties.assert_called_once_with('effect', 12, None,
            {'point_5_x': 0.2, 'point_5_y': 0.3})


class DistortSelectionTests(unittest.TestCase):
    def test_marquee_selects_screen_points_in_either_drag_direction(self):
        widget = types.SimpleNamespace(_distort_marquee_anchor=QPointF(200, 100),
            _distort_handles=[QPointF(80, 40), QPointF(160, 80), QPointF(220, 100)],
            mouse_pressed=True, mouse_dragging=True, setCursor=Mock(), update=Mock())
        VideoWidget._move_distort(widget, QPointF(50, 10))
        self.assertEqual(widget._distort_selected, {0, 1})
        widget._distort_marquee_anchor = QPointF(50, 10)
        VideoWidget._move_distort(widget, QPointF(200, 100))
        self.assertEqual(widget._distort_selected, {0, 1})

    def test_empty_click_clears_selection_without_changing_effect_data(self):
        widget = types.SimpleNamespace(transform_mode=None, _distort_selected={1, 5}, update=Mock())
        VideoWidget._begin_distort_drag(widget, QPointF(20, 30))
        self.assertEqual(widget._distort_selected, set())
        self.assertEqual(widget._distort_marquee_anchor, QPointF(20, 30))
        self.assertIsNone(widget._distort_drag)

    def test_group_drag_preserves_spacing_under_rotation_and_at_limits(self):
        transform = QTransform().translate(100, 50).rotate(35).shear(0.2, 0.1).scale(2, 3)
        inverse, _ = transform.inverted()
        anchor = QPointF(20, 30)
        drags = {1: (1, anchor, [0.1, -0.1], 0.5, inverse, (300, 200), 12),
                 5: (5, anchor, [0.9, 0.4], 0.5, inverse, (300, 200), 12)}
        values = VideoWidget._distort_group_offsets(drags, transform.map(anchor+QPointF(30, 20)))
        self.assertAlmostEqual(values['point_1_x'], 0.2)
        self.assertAlmostEqual(values['point_5_x'], 1.0)
        self.assertAlmostEqual(values['point_1_y'], 0.1)
        self.assertAlmostEqual(values['point_5_y'], 0.6)

    def test_context_menu_offers_selected_reset_or_all_reset(self):
        for selected, label in (({1, 5}, 'Reset Selected Points'), (set(), 'Reset All Points')):
            menu = Mock()
            action = object()
            menu.addAction.return_value = action
            menu.exec_.return_value = action
            native = types.SimpleNamespace(info=types.SimpleNamespace(class_name='Distort'))
            widget = types.SimpleNamespace(transforming_effect=object(), transforming_effect_object=native,
                region_enabled=False, _distort_selected=selected, _reset_distort_points=Mock())
            event = types.SimpleNamespace(globalPos=lambda: QPointF(0, 0), accept=Mock())
            app = types.SimpleNamespace(_tr=lambda text: text)
            with patch('windows.video_widget.QMenu', return_value=menu), \
                 patch('windows.video_widget.get_app', return_value=app):
                VideoWidget.contextMenuEvent(widget, event)
            menu.addAction.assert_called_once_with(label)
            widget._reset_distort_points.assert_called_once_with(selected or set(range(16)))

    @unittest.skipUnless(hasattr(openshot, 'Distort'), 'Requires libopenshot Distort')
    def test_dragging_selected_point_keeps_group_and_captures_both_points(self):
        effect = openshot.Distort()
        widget = types.SimpleNamespace(transform_mode='distort_6', _distort_selected={5, 6},
            _distort_frame=1, _distort_size=(300, 200), _distort_transform=QTransform(),
            transforming_effect_object=effect, transforming_effect=types.SimpleNamespace(id='effect'), update=Mock())
        with patch('windows.video_widget.Effect.get', return_value=None):
            VideoWidget._begin_distort_drag(widget, QPointF(80, 40))
        self.assertEqual(widget._distort_selected, {5, 6})
        self.assertEqual(set(widget._distort_group_drag), {5, 6})
        self.assertEqual(widget._distort_focus_point, 6)
        self.assertEqual(widget._distort_drag[0], 6)

    @unittest.skipUnless(hasattr(openshot, 'Distort'), 'Requires libopenshot Distort')
    def test_reset_selected_handles_cancels_preset_and_keeps_other_points(self):
        effect = openshot.Distort()
        effect.SetJson(json.dumps({'preset': 1, 'point_5_x': json.loads(openshot.Keyframe(0.2).Json())}))
        widget = types.SimpleNamespace(transforming_effect_object=effect,
            transforming_effect=types.SimpleNamespace(id='effect'), transforming_clip=object(),
            _get_clip_frame_number=lambda clip, fps: 10, updateEffectProperties=Mock())
        app = types.SimpleNamespace(project={'fps': {'num': 30, 'den': 1}})
        for selected in ({5, 6}, set(range(16))):
            with patch('windows.video_widget.get_app', return_value=app):
                VideoWidget._reset_distort_points(widget, selected)
            _, frame, object_id, values = widget.updateEffectProperties.call_args.args
            self.assertEqual(frame, 10)
            self.assertEqual(len(values), len(selected)*2)
            reset = openshot.Distort()
            reset.SetJson(effect.Json())
            reset.SetJson(json.dumps({key: json.loads(openshot.Keyframe(value).Json()) for key, value in values.items()}))
            mesh = json.loads(reset.MeshJSON(10, 3))
            for index in selected:
                self.assertAlmostEqual(mesh[index][0], (index % 4)/3)
                self.assertAlmostEqual(mesh[index][1], (index // 4)/3)
            self.assertEqual(reset.preset, 1)

    def test_marquee_release_does_not_create_undo_action(self):
        native = types.SimpleNamespace(info=types.SimpleNamespace(class_name='Distort'))
        original = {'point_5_x': {'Points': []}}
        effect = types.SimpleNamespace(data=original, save=Mock())
        widget = types.SimpleNamespace(mouse_pressed=True, mouse_dragging=True, region_enabled=False,
            transforming_clips=[], transforming_effect=types.SimpleNamespace(id='effect'),
            transforming_effect_object=native, original_effect_data=original,
            original_clip_data_map={}, transaction_id='select', setCursor=Mock(),
            _restore_transform_playback_cache=Mock(), _distort_selected={5,6},
            _distort_marquee_anchor=QPointF(0,0))
        updates = types.SimpleNamespace(ignore_history=True, transaction_id='select',
                                        apply_last_action_to_history=Mock())
        app = types.SimpleNamespace(updates=updates, window=None)
        with patch('windows.video_widget.Effect.get', return_value=effect), \
             patch('windows.video_widget.get_app', return_value=app):
            VideoWidget.mouseReleaseEvent(widget, types.SimpleNamespace(accept=lambda: None))
        self.assertEqual(widget._distort_selected, {5,6})
        self.assertIsNone(widget._distort_marquee_rect)
        effect.save.assert_not_called()
        updates.apply_last_action_to_history.assert_not_called()

    @unittest.skipUnless(hasattr(openshot, 'Distort'), 'Requires libopenshot Distort')
    def test_repaint_during_focus_update_keeps_group_selection(self):
        effect = openshot.Distort()
        effect.Id('mesh')
        widget = types.SimpleNamespace(transforming_effect_object=effect,
                                      transform=QTransform(), handle_opacity=1)
        image = QImage(640,480,QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            VideoWidget._draw_distort_mesh(widget,painter,600,400,1)
            self.assertEqual(widget._distort_selected, set())
            widget._distort_selected = {5,6}
            widget._distort_focus_point = 6
            widget._distort_pending_focus_point = 6
            VideoWidget._draw_distort_mesh(widget,painter,600,400,1)
            self.assertEqual(widget._distort_selected, {5,6})
            effect.SetJson(json.dumps({'selected_point':6}))
            VideoWidget._draw_distort_mesh(widget,painter,600,400,1)
            self.assertEqual(widget._distort_selected, {5,6})
            self.assertIsNone(widget._distort_pending_focus_point)
            # A later explicit dock selection still selects the requested point.
            effect.SetJson(json.dumps({'selected_point':10}))
            VideoWidget._draw_distort_mesh(widget,painter,600,400,1)
            self.assertEqual(widget._distort_selected, {10})
        finally:
            painter.end()
