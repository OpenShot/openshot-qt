"""Regression coverage for zoom slider grip geometry and mouse gestures."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from qt_api import QApplication, QPointF, Qt
from windows.views.zoom_slider import ZoomSlider


class MouseEvent:
    def __init__(self, x, y):
        self.point = QPointF(x, y)

    def position(self):
        return self.point

    def button(self):
        return Qt.LeftButton

    def accept(self):
        pass


class ZoomSliderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Mock()
        app = SimpleNamespace(_tr=lambda text: text, window=self.window, updates=Mock())
        self.patch = patch('windows.views.zoom_slider.get_app', return_value=app)
        self.patch.start()
        self.slider = ZoomSlider()
        self.slider.resize(240, 20)
        self.slider.scrollbar_position = [0.5, 0.50001, 1000, 100]
        self.slider.delayed_resize_callback = Mock()
        self.slider._emit_pending_zoom = Mock()
        self.slider._update_handle_geometry()

    def tearDown(self):
        self.slider.delayed_resize_timer.stop()
        self.slider._zoom_emit_timer.stop()
        self.slider.close()
        self.patch.stop()

    def drag(self, start, end):
        self.slider.mousePressEvent(MouseEvent(*start))
        self.slider.mouseMoveEvent(MouseEvent(*end))
        self.slider.mouseReleaseEvent(MouseEvent(*end))

    def test_thin_selection_moves_from_top_and_bottom_even_when_pointer_leaves(self):
        for y in (1, 19):
            with self.subTest(y=y):
                self.slider.scrollbar_position = [0.5, 0.50001, 1000, 100]
                self.slider._update_handle_geometry()
                x = self.slider.move_handle_rect.center().x()
                self.drag((x, y), (x + 40, y))
                self.assertAlmostEqual(self.slider.scrollbar_position[1] -
                                       self.slider.scrollbar_position[0], 0.00001)
                self.assertGreater(self.slider.scrollbar_position[0], 0.5)
                self.slider.delayed_resize_callback.assert_not_called()
                self.window.TimelineScroll.emit.assert_called()

    def test_grips_remain_separate_and_inside_widget_at_all_scales(self):
        for left, right in ((0, 0.00001), (0.99999, 1), (0, 1), (0.2, 0.8)):
            with self.subTest(span=(left, right)):
                self.slider.scrollbar_position[:2] = [left, right]
                self.slider._update_handle_geometry()
                for name, rect in (("left", self.slider.left_handle_rect),
                                   ("move", self.slider.move_handle_rect),
                                   ("right", self.slider.right_handle_rect)):
                    self.assertGreaterEqual(rect.left(), 0)
                    self.assertLessEqual(rect.right(), self.slider.width())
                    self.assertEqual(self.slider._hit_target(QPointF(rect.center().x(), 1) if name == "move" else rect.center()), name)

    def test_resize_stays_on_pressed_handle_when_pointer_leaves(self):
        for target, direction in (("left", -1), ("right", 1)):
            with self.subTest(target=target):
                self.slider.scrollbar_position[:2] = [0.5, 0.50001]
                self.slider._update_handle_geometry()
                rect = getattr(self.slider, target + '_handle_rect')
                x = rect.center().x()
                self.drag((x, 10), (x + direction * 30, 10))
                self.assertGreater(self.slider.scrollbar_position[1] -
                                   self.slider.scrollbar_position[0], 0.1)
                fixed = 1 if target == 'left' else 0
                self.assertEqual(self.slider.scrollbar_position[fixed], [0.5, 0.50001][fixed])

    def test_resize_keeps_opposite_grip_visually_fixed_across_minimum_width(self):
        for target, direction in (("left", -1), ("right", 1)):
            with self.subTest(target=target):
                self.slider.scrollbar_position[:2] = [0.5, 0.50001]
                self.slider._update_handle_geometry()
                fixed = "right" if target == "left" else "left"
                fixed_rect = getattr(self.slider, fixed + '_handle_rect')
                x = getattr(self.slider, target + '_handle_rect').center().x()
                self.slider.mousePressEvent(MouseEvent(x, 10))
                for distance in (6, 12, 30, 12, 6):
                    self.slider.mouseMoveEvent(MouseEvent(x + direction * distance, 10))
                    self.slider._update_handle_geometry()
                    self.assertEqual(getattr(self.slider, fixed + '_handle_rect'), fixed_rect)
                    moving_x = getattr(self.slider, target + '_handle_rect').center().x()
                    self.assertAlmostEqual(moving_x, x + direction * distance)
                self.slider.mouseReleaseEvent(MouseEvent(x + direction * 6, 10))
                self.assertEqual(getattr(self.slider, fixed + '_handle_rect'), fixed_rect)

    def test_resize_at_endpoint_never_pushes_opposite_edge(self):
        for target, span, direction in (("right", [0.99999, 1.0], 1),
                                        ("left", [0.0, 0.00001], -1)):
            with self.subTest(target=target):
                self.slider.scrollbar_position[:2] = span
                self.slider._update_handle_geometry()
                x = getattr(self.slider, target + '_handle_rect').center().x()
                self.drag((x, 10), (x + direction * 30, 10))
                self.assertEqual(self.slider.scrollbar_position[:2], span)

    def test_overlapping_resize_targets_have_no_move_gaps(self):
        for height in (20, 36):
            self.slider.resize(240, height)
            self.slider._update_handle_geometry()
            center = self.slider.scroll_bar_rect.center().x()
            for dx, target in ((-9, "left"), (-5, "left"), (-1, "left"),
                               (1, "right"), (5, "right"), (9, "right")):
                for y in (5, height / 2, height - 5):
                    with self.subTest(height=height, dx=dx, y=y):
                        self.slider.mouseMoveEvent(MouseEvent(center + dx, y))
                        self.assertEqual(self.slider.hover_target, target)
                        self.assertEqual(self.slider._hit_target(QPointF(center + dx, y)), target)
            for y in (1, height - 1):
                self.assertEqual(self.slider._hit_target(QPointF(center, y)), "move")

    def test_hover_stays_on_pressed_handle_during_drag(self):
        center = self.slider.scroll_bar_rect.center().x()
        self.slider.mousePressEvent(MouseEvent(center - 8, 10))
        self.slider.mouseMoveEvent(MouseEvent(center + 30, 1))
        self.assertEqual(self.slider.hover_target, "left")
        self.assertTrue(self.slider.left_handle_dragging)
        self.slider.mouseReleaseEvent(MouseEvent(center + 30, 1))
        self.assertEqual(self.slider.hover_target,
                         self.slider._hit_target(QPointF(center + 30, 1)))

    def test_pan_clamps_without_changing_tiny_span(self):
        for destination in (-100, 400):
            self.slider.scrollbar_position[:2] = [0.5, 0.50001]
            self.slider._update_handle_geometry()
            x = self.slider.move_handle_rect.center().x()
            self.drag((x, 1), (destination, 1))
            left, right = self.slider.scrollbar_position[:2]
            self.assertGreaterEqual(left, 0)
            self.assertLessEqual(right, 1)
            self.assertAlmostEqual(right - left, 0.00001)

    def test_handle_click_does_not_recenter(self):
        x = self.slider.left_handle_rect.center().x()
        self.drag((x, 10), (x + 1, 10))
        self.assertEqual(self.slider.scrollbar_position[:2], [0.5, 0.50001])
        self.slider.delayed_resize_callback.assert_not_called()

    def test_double_click_restores_zoom_and_releases_gesture(self):
        original = self.slider.scrollbar_position[:2]
        event = MouseEvent(self.slider.move_handle_rect.center().x(), 1)
        for expected in ([0.0, 1.0], original):
            # Qt sends double-click instead of a second mouse press.
            self.slider.mousePressEvent(event)
            self.slider.mouseReleaseEvent(event)
            self.slider.mouseDoubleClickEvent(event)
            self.slider.mouseReleaseEvent(event)
            self.assertEqual(self.slider.scrollbar_position[:2], expected)
            self.assertFalse(self.slider.mouse_pressed)
            self.assertFalse(self.slider.mouse_dragging)
        positions = [0.1, 0.4, 1000, 100]
        self.slider.clip_rects = [object()]
        self.slider.update_scrollbars(positions)
        self.assertEqual(self.slider.scrollbar_position, positions)

    def test_shift_resize_moves_both_edges(self):
        for target, direction in (("left", -1), ("right", 1)):
            self.slider.scrollbar_position[:2] = [0.3, 0.7]
            self.slider._update_handle_geometry()
            x = getattr(self.slider, target + '_handle_rect').center().x()
            with patch('windows.views.zoom_slider.modifiers_has', return_value=True):
                self.drag((x, 10), (x + direction * 10, 10))
            left, right = self.slider.scrollbar_position[:2]
            self.assertLess(left, 0.3)
            self.assertGreater(right, 0.7)
            self.assertAlmostEqual(left + right, 1.0)

    def test_background_click_recenters_and_preserves_span(self):
        self.slider.scrollbar_position[:2] = [0.4, 0.6]
        x = self.slider._track_rect().left() + self.slider._track_rect().width() * 0.2
        self.drag((x, 10), (x, 10))
        self.assertAlmostEqual(self.slider.scrollbar_position[0], 0.1)
        self.assertAlmostEqual(self.slider.scrollbar_position[1], 0.3)

    def test_background_drag_left_maps_through_gutters(self):
        track = self.slider._track_rect()
        self.drag((track.right(), 10), (track.left() + track.width() * 0.75, 10))
        self.assertEqual(self.slider.scrollbar_position[:2], [0.75, 1.0])

    def test_background_drag_maps_through_gutters(self):
        track = self.slider._track_rect()
        self.drag((track.left(), 10), (track.left() + track.width() / 4, 10))
        self.assertEqual(self.slider.scrollbar_position[:2], [0, 0.25])


if __name__ == '__main__':
    unittest.main()
