"""Timeline marker creation respects project-frame uniqueness."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from classes.query import Marker
from tests.qt_test_app import get_or_create_app
from tests.test_main_window import DummyApp, ensure_app_state


class TimelineMarkerTests(unittest.TestCase):
    def setUp(self):
        app, _ = get_or_create_app(DummyApp)
        ensure_app_state(app)
        from windows.main_window import MainWindow
        self.add_marker = MainWindow.actionAddMarker_trigger
        self.markers = []
        self.project = Mock()
        self.project.get.return_value = {'num': 30000, 'den': 1001}
        self.player = Mock()
        self.window = SimpleNamespace(
            preview_thread=SimpleNamespace(player=self.player), timeline=Mock())
        self.patches = [
            patch('windows.main_window.get_app', return_value=SimpleNamespace(project=self.project)),
            patch.object(Marker, 'filter', return_value=self.markers),
            patch.object(Marker, 'save', autospec=True, side_effect=self.markers.append),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def add_at(self, frame):
        self.player.Position.return_value = frame
        self.add_marker(self.window)

    def test_repeated_add_on_same_frame_saves_only_once(self):
        for _ in range(10):
            self.add_at(101)
        self.assertEqual(len(self.markers), 1)
        Marker.save.assert_called_once()
        self.assertAlmostEqual(self.markers[0].data['position'], 100 * 1001 / 30000)
        self.window.timeline.setFocus.assert_called()

    def test_same_frame_with_rounded_seconds_preserves_existing_marker(self):
        marker = Marker()
        marker.data = {'position': round(100 * 1001 / 30000, 6),
                       'icon': 'red.png', 'vector': 'red', 'label': 'Keep this'}
        original = dict(marker.data)
        self.markers.append(marker)
        self.add_at(101)
        self.assertEqual(marker.data, original)
        self.assertEqual(len(self.markers), 1)
        Marker.save.assert_not_called()

    def test_first_and_adjacent_frames_can_each_have_a_marker(self):
        for frame in (1, 1, 2, 101, 102, 101):
            self.add_at(frame)
        self.assertEqual(len(self.markers), 4)
        self.assertEqual([round(m.data['position'] * 30000 / 1001) for m in self.markers],
                         [0, 1, 100, 101])
