"""Regressions for #6177: short clips survive FPS changes and preview endpoints."""
import copy
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import openshot
from qt_api import QApplication, QImage, QColor

from classes.convert_framerate import change_profile
from classes.timeline import TimelineSync
from windows.preview_thread import PreviewParent


def profile(fps):
    return SimpleNamespace(info=SimpleNamespace(fps=SimpleNamespace(num=fps, den=1)))


def clips(fps, layer=1000000):
    return [dict(id=str(i), position=i / fps, start=0.0, end=1 / fps,
                 duration=1 / fps, layer=layer) for i in range(5)]


class OneFrameClipTests(unittest.TestCase):
    def test_profile_changes_preserve_five_adjacent_nonempty_clips(self):
        for source, target in ((30, 25), (25, 30), (60, 24)):
            with self.subTest(source=source, target=target):
                items = clips(source)
                change_profile(items, profile(target))
                for i, item in enumerate(items):
                    self.assertGreaterEqual(round((item['end'] - item['start']) * target), 1)
                    self.assertAlmostEqual(item['duration'], item['end'] - item['start'])
                    if i:
                        previous = items[i - 1]
                        self.assertAlmostEqual(item['position'], previous['position'] + previous['duration'])

    def test_profile_change_does_not_close_intentional_overlaps_or_gaps(self):
        items = clips(25)
        items[1]['position'] = 0.0
        items[2]['position'] = 0.12
        expected = copy.deepcopy(items)
        change_profile(items, profile(25))
        self.assertEqual(items, expected)

    def test_profile_change_does_not_join_different_layers_or_effects(self):
        items = [clips(25)[0], dict(clips(25, 2000000)[0], position=0.08),
                 dict(id='effect', position=0.02, start=0.0, end=0.04, layer=1000000, type='Mask')]
        change_profile(items, profile(25))
        self.assertAlmostEqual(items[0]['end'], 0.04)
        self.assertAlmostEqual(items[1]['position'], 0.08)

    def test_trimmed_short_clip_stays_nonempty(self):
        item = dict(id='trim', position=0.0, start=0.08, end=0.09, duration=0.01, layer=1)
        change_profile([item], profile(25))
        self.assertAlmostEqual(item['end'] - item['start'], 0.04)
        self.assertAlmostEqual(item['duration'], 0.04)

    def test_preview_stops_on_fifth_frame_and_loops_to_first(self):
        parent = SimpleNamespace(movePlayhead=Mock(), PauseSignal=Mock(), loop_playback=False)
        worker = SimpleNamespace(player=Mock(), Seek=Mock())
        worker.player.Mode.return_value = openshot.PLAYBACK_PLAY
        worker.player.Speed.return_value = 1.0
        preview = SimpleNamespace(parent=parent, worker=worker, timeline_max_length=5)
        PreviewParent.onPositionChanged(preview, 4)
        parent.PauseSignal.emit.assert_not_called()
        worker.Seek.assert_not_called()
        PreviewParent.onPositionChanged(preview, 5)
        parent.PauseSignal.emit.assert_called_once_with()
        worker.Seek.assert_called_once_with(5)
        worker.Seek.reset_mock()
        parent.loop_playback = True
        PreviewParent.onPositionChanged(preview, 5)
        worker.Seek.assert_called_once_with(1)

    def test_native_timeline_last_frame_includes_final_one_frame_clip(self):
        app = QApplication.instance() or QApplication([])
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        image = QImage(16, 16, QImage.Format_RGBA8888)
        for fps in (25, 30):
            timeline = openshot.Timeline(16, 16, openshot.Fraction(fps, 1), 44100, 2, openshot.LAYOUT_STEREO)
            native_clips = []
            timeline.Open()
            for item in clips(fps):
                image.fill(QColor("blue" if item["id"] == "4" else "red"))
                path = os.path.join(temp.name, "frame%s.png" % item["id"])
                self.assertTrue(image.save(path))
                clip = openshot.Clip(path)
                clip.Position(item['position'])
                clip.Start(item['start'])
                clip.End(item['end'])
                timeline.AddClip(clip)
                native_clips.append(clip)
            sync = SimpleNamespace(timeline=timeline)
            self.assertEqual(timeline.GetMaxFrame(), 5)
            self.assertEqual(TimelineSync.GetLastFrame(sync), 5)
            self.assertEqual(bytes(timeline.GetFrame(4).GetPixelsBytes())[:4], bytes((255, 0, 0, 255)))
            self.assertEqual(bytes(timeline.GetFrame(TimelineSync.GetLastFrame(sync)).GetPixelsBytes())[:4],
                             bytes((0, 0, 255, 255)))
            timeline.Close()


if __name__ == '__main__':
    unittest.main()
