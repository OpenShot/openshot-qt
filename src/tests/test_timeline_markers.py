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


class MarkerNavigationTests(unittest.TestCase):
    # A 29.97 fps clip (806 frames) on a 30 fps timeline ends between frames
    CLIP_END = 26.893533
    LAST_FRAME = 807

    def setUp(self):
        app, _ = get_or_create_app(DummyApp)
        ensure_app_state(app)
        from windows.main_window import MainWindow
        self.positions = [0, self.CLIP_END - 1 / 30]
        self.window = SimpleNamespace(
            preview_thread=SimpleNamespace(current_frame=1),
            findAllMarkerPositions=lambda: list(self.positions),
            SeekSignal=Mock(), timeline=Mock())
        self.window.SeekSignal.emit.side_effect = self.seek
        self.window.seekToAdjacentMarker = (
            lambda forward: MainWindow.seekToAdjacentMarker(self.window, forward))
        self.previous = lambda: MainWindow.actionPreviousMarker_trigger(self.window)
        self.next = lambda: MainWindow.actionNextMarker_trigger(self.window)
        project = Mock()
        project.get.return_value = {'num': 30, 'den': 1}
        app_window = SimpleNamespace(
            timeline_sync=SimpleNamespace(GetLastFrame=lambda: self.LAST_FRAME),
            propertyTableView=Mock())
        item = patch('windows.main_window.get_app',
                     return_value=SimpleNamespace(project=project, window=app_window))
        item.start()
        self.addCleanup(item.stop)

    def seek(self, frame, _start_preroll):
        self.window.preview_thread.current_frame = frame

    def test_previous_marker_leaves_clip_end_between_frames(self):
        self.next()
        self.assertEqual(self.window.preview_thread.current_frame, self.LAST_FRAME)
        self.previous()
        self.assertEqual(self.window.preview_thread.current_frame, 1)

    def test_next_and_previous_step_through_distinct_frames(self):
        # Keyframe and marker positions which round to the same frame are one stop
        self.positions.extend([10 / 30, 10.2 / 30, 400 / 30])
        visited = []
        for _ in range(4):
            self.next()
            visited.append(self.window.preview_thread.current_frame)
        self.assertEqual(visited, [11, 401, self.LAST_FRAME, self.LAST_FRAME])
        for _ in range(4):
            self.previous()
            visited.append(self.window.preview_thread.current_frame)
        self.assertEqual(visited[4:], [401, 11, 1, 1])

    def test_markers_past_the_last_frame_do_not_trap_next(self):
        self.positions.append(60.0)
        self.window.preview_thread.current_frame = self.LAST_FRAME
        self.next()
        self.window.SeekSignal.emit.assert_not_called()
        self.window.timeline.setFocus.assert_called()
