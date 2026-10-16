"""
 @file
 @brief Targeted unit tests for the headless single-clip render helpers used by
        the two-clip AI bridge timeline action.
"""

import importlib
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)


class ClipRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("classes.clip_render")

    def _clip(self, **data_overrides):
        data = {
            "file_id": "F1",
            "start": 1.0,
            "end": 3.0,
            "reader": {
                "path": "/media/source.mp4",
                "fps": {"num": 24, "den": 1},
                "width": 1920,
                "height": 1080,
                "has_audio": True,
                "sample_rate": 48000,
                "channels": 2,
                "channel_layout": 3,
                "audio_bit_rate": 192000,
                "pixel_ratio": {"num": 1, "den": 1},
            },
        }
        data.update(data_overrides)
        return types.SimpleNamespace(id="C1", data=data)

    # ---- clip_source_path ----

    def test_clip_source_path_prefers_live_file_lookup(self):
        clip = self._clip()
        file_obj = types.SimpleNamespace(absolute_path=lambda: "/resolved/source.mp4")
        with patch.object(self.module.File, "get", return_value=file_obj) as file_get:
            result = self.module.clip_source_path(clip)
        file_get.assert_called_once_with(id="F1")
        self.assertEqual(result, "/resolved/source.mp4")

    def test_clip_source_path_falls_back_to_nested_reader_path(self):
        clip = self._clip(file_id=None)
        result = self.module.clip_source_path(clip)
        self.assertEqual(result, "/media/source.mp4")

    def test_clip_source_path_falls_back_when_file_lookup_misses(self):
        clip = self._clip()
        with patch.object(self.module.File, "get", return_value=None):
            result = self.module.clip_source_path(clip)
        self.assertEqual(result, "/media/source.mp4")

    # ---- clip_frame_range ----

    def test_clip_frame_range_computes_inclusive_frame_bounds(self):
        clip = self._clip(start=1.0, end=3.0)
        # start=1.0s @ 24fps -> frame 25; end=3.0s -> frame 72
        self.assertEqual(self.module.clip_frame_range(clip), (25, 72))

    def test_clip_frame_range_defaults_fps_when_missing(self):
        clip = self._clip(start=0.0, end=1.0, reader={"path": "/media/source.mp4"})
        # No fps in reader -> defaults to 30fps: end=1.0s -> frame 30
        self.assertEqual(self.module.clip_frame_range(clip), (1, 30))

    # ---- setup_clip_writer ----

    def test_setup_clip_writer_configures_video_and_audio_options(self):
        clip = self._clip()
        writer = MagicMock()
        fake_fraction = MagicMock(side_effect=lambda num, den: (num, den))
        with patch.object(self.module.openshot, "Fraction", fake_fraction):
            self.module.setup_clip_writer(clip, writer)

        writer.SetVideoOptions.assert_called_once()
        video_args = writer.SetVideoOptions.call_args[0]
        self.assertEqual(video_args[0], True)
        self.assertEqual(video_args[1], "libx264")
        self.assertEqual(video_args[3], 1920)
        self.assertEqual(video_args[4], 1080)

        writer.SetAudioOptions.assert_called_once_with(True, "aac", 48000, 2, 3, 192000)
        writer.Open.assert_called_once()

    def test_setup_clip_writer_uses_defaults_for_missing_reader_fields(self):
        clip = self._clip(reader={"path": "/media/source.mp4"})
        writer = MagicMock()
        fake_fraction = MagicMock(side_effect=lambda num, den: (num, den))
        with patch.object(self.module.openshot, "Fraction", fake_fraction):
            self.module.setup_clip_writer(clip, writer)

        video_args = writer.SetVideoOptions.call_args[0]
        self.assertEqual(video_args[3], 1280)
        self.assertEqual(video_args[4], 720)
        writer.SetAudioOptions.assert_called_once_with(False, "aac", 48000, 2, 3, 192000)

    # ---- render_clip_to_file ----

    def test_render_clip_to_file_writes_every_frame_in_range(self):
        clip = self._clip(start=0.0, end=0.125)  # 24fps -> frames 1..3
        written_frames = []
        fake_writer = types.SimpleNamespace(
            Close=lambda: None,
        )
        fake_reader = types.SimpleNamespace(
            Open=lambda: None,
            Close=lambda: None,
            GetFrame=lambda frame: ("frame", frame),
        )

        with patch.object(self.module.File, "get", return_value=None), \
             patch.object(self.module.openshot, "FFmpegWriter", return_value=fake_writer), \
             patch.object(self.module.openshot, "Clip", return_value=fake_reader), \
             patch.object(self.module, "setup_clip_writer", lambda c, w: None):
            fake_writer.WriteFrame = lambda frame_obj: written_frames.append(frame_obj)
            result = self.module.render_clip_to_file(clip, "/tmp/out.mp4")

        self.assertTrue(result)
        self.assertEqual(written_frames, [("frame", 1), ("frame", 2), ("frame", 3)])

    def test_render_clip_to_file_false_when_no_source_path(self):
        clip = self._clip(file_id=None, reader={})
        result = self.module.render_clip_to_file(clip, "/tmp/out.mp4")
        self.assertFalse(result)

    def test_render_clip_to_file_cleans_up_partial_file_on_reader_error(self):
        clip = self._clip(start=0.0, end=0.125)
        fake_writer = types.SimpleNamespace(Close=lambda: None)

        def boom(path):
            raise RuntimeError("reader failed to open")

        with patch.object(self.module.File, "get", return_value=None), \
             patch.object(self.module.openshot, "FFmpegWriter", return_value=fake_writer), \
             patch.object(self.module.openshot, "Clip", side_effect=boom), \
             patch.object(self.module, "setup_clip_writer", lambda c, w: None), \
             patch.object(self.module.os.path, "exists", return_value=True) as exists_mock, \
             patch.object(self.module.os, "remove") as remove_mock:
            result = self.module.render_clip_to_file(clip, "/tmp/out.mp4")

        self.assertFalse(result)
        exists_mock.assert_called_with("/tmp/out.mp4")
        remove_mock.assert_called_once_with("/tmp/out.mp4")

    def test_render_clip_to_file_false_and_no_writer_setup_for_empty_range(self):
        clip = self._clip(start=2.0, end=1.0)  # end before start -> empty range
        with patch.object(self.module.File, "get", return_value=None), \
             patch.object(self.module.openshot, "FFmpegWriter") as writer_cls:
            result = self.module.render_clip_to_file(clip, "/tmp/out.mp4")
        self.assertFalse(result)
        writer_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
