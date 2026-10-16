"""
@file
@brief Unit tests for thumbnail generation fallback behavior.
"""

import unittest
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import classes.thumbnail as thumbnail


class _Frame:
    def __init__(self):
        self.calls = []

    def Thumbnail(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class _Reader:
    def __init__(self, *, open_error=None, metadata=None):
        self.open_error = open_error
        self.open_calls = 0
        self.close_calls = 0
        self.decode_sizes = []
        self.max_frames = []
        self.metadata = metadata or {}

        class _Metadata(dict):
            def count(self, key):
                return 1 if key in self else 0

        self.info = SimpleNamespace(metadata=_Metadata(self.metadata))
        self._frame = _Frame()

    def SetMaxDecodeSize(self, width, height):
        self.decode_sizes.append((width, height))

    def Open(self):
        self.open_calls += 1
        if self.open_error:
            raise self.open_error

    def GetFrame(self, _):
        self.max_frames.append(_)
        return self._frame

    def Close(self):
        self.close_calls += 1


class _QueriedFile:
    def __init__(self):
        self.data = {"fps": {"num": 25, "den": 1}}

    def absolute_path(self):
        return "/tmp/dummy.webp"


class ThumbnailGenerationTests(unittest.TestCase):
    def test_migration_unreadable_cache_is_optional(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(thumbnail.os, "listdir", side_effect=PermissionError("denied")):
                self.assertEqual(thumbnail.MigrateThumbnailLayout(root), 0)

    def test_migration_keeps_failed_files_and_continues(self):
        for operation in ("mkdir", "move", "remove"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as root:
                for name in ("denied-1.png", "ok-2.png"):
                    with open(os.path.join(root, name), "wb") as stream:
                        stream.write(b"thumbnail")
                if operation == "remove":
                    os.makedirs(os.path.join(root, "denied"))
                    with open(os.path.join(root, "denied", "1.png"), "wb") as stream:
                        stream.write(b"existing")
                owner, name = ((thumbnail.shutil, "move") if operation == "move" else
                               (thumbnail.os, "makedirs" if operation == "mkdir" else "remove"))
                original = getattr(owner, name)

                def denied(path, *args, **kwargs):
                    if os.path.basename(path).startswith("denied"):
                        raise PermissionError("denied")
                    return original(path, *args, **kwargs)

                with patch.object(owner, name, side_effect=denied):
                    self.assertEqual(thumbnail.MigrateThumbnailLayout(root), 1)
                self.assertTrue(os.path.isfile(os.path.join(root, "denied-1.png")))
                self.assertTrue(os.path.isfile(os.path.join(root, "ok", "2.png")))

    def test_generate_thumbnail_retries_when_first_reader_fails_to_open(self):
        first_reader = _Reader(open_error=RuntimeError("QtImageReader could not open image file."))
        second_reader = _Reader()
        created = []
        reader_iter = iter([first_reader, second_reader])

        def create_reader(path, inspect_reader):
            created.append((path, inspect_reader))
            return next(reader_iter)

        with patch.object(thumbnail.openshot.Clip, "CreateReader", side_effect=create_reader), \
             patch.object(thumbnail.os.path, "exists", side_effect=lambda path: True), \
             patch.object(thumbnail.shutil, "copyfile") as copyfile_patch:
            thumbnail.GenerateThumbnail("image.webp", "/tmp/thumb.png", 1, 20, 20, None, None)

        self.assertEqual(created, [("image.webp", False), ("image.webp", True)])
        self.assertEqual(first_reader.open_calls, 1)
        self.assertEqual(second_reader.open_calls, 1)
        self.assertEqual(second_reader.decode_sizes, [(60, 60)])
        self.assertEqual(second_reader.max_frames, [1])
        self.assertEqual(first_reader.close_calls, 1)
        self.assertEqual(second_reader.close_calls, 1)
        copyfile_patch.assert_not_called()

    def test_generate_thumbnail_renders_svg_placeholder_when_source_cannot_open(self):
        failing_readers = [
            _Reader(open_error=RuntimeError("missing source")),
            _Reader(open_error=RuntimeError("missing source")),
        ]
        placeholder_reader = _Reader()
        reader_iter = iter([*failing_readers, placeholder_reader])
        created = []

        def create_reader(path, inspect_reader):
            created.append((path, inspect_reader))
            return next(reader_iter)

        with patch.object(thumbnail.openshot.Clip, "CreateReader", side_effect=create_reader), \
             patch.object(thumbnail.os.path, "exists", side_effect=lambda path: True), \
             patch.object(thumbnail.shutil, "copyfile") as copyfile_patch:
            result = thumbnail.GenerateThumbnail("missing.webp", "/tmp/thumb.png", 7, 20, 20, None, None)
            self.assertIsNone(result)

        self.assertEqual(created[0:2], [("missing.webp", False), ("missing.webp", True)])
        self.assertEqual(created[2], (thumbnail.os.path.join(thumbnail.info.IMAGES_PATH, "NotFound.svg"), False))
        self.assertEqual(placeholder_reader.max_frames, [1])
        copyfile_patch.assert_not_called()

    def test_http_thumbnail_handler_uses_project_file_icon_size(self):
        file_record = _QueriedFile()
        handler = thumbnail.httpThumbnailHandler.__new__(thumbnail.httpThumbnailHandler)
        handler.path = "/thumbnails/file-id/1/path/"
        handler.wfile = type("_Writer", (), {"write": lambda *_: None})()
        handler.send_response_only = unittest.mock.Mock()
        handler.send_header = unittest.mock.Mock()
        handler.end_headers = unittest.mock.Mock()
        handler.send_error = unittest.mock.Mock()

        with patch.object(thumbnail, "File") as file_cls, \
             patch.object(thumbnail, "GenerateThumbnail") as generate_thumbnail, \
             patch.object(thumbnail, "ThumbnailCacheIsStale", return_value=False), \
             patch.object(thumbnail.os.path, "exists", return_value=False), \
             patch.object(thumbnail.time, "sleep", return_value=None):
            file_cls.get.return_value = file_record
            handler.do_GET()

        self.assertEqual(generate_thumbnail.call_count, 1)
        call_kwargs = generate_thumbnail.call_args[0]
        self.assertEqual(call_kwargs[3], thumbnail.info.LIST_ICON_SIZE.width())
        self.assertEqual(call_kwargs[4], thumbnail.info.LIST_ICON_SIZE.height())

    def test_http_thumbnail_handler_regenerates_stale_project_file_thumbnail(self):
        file_record = _QueriedFile()
        handler = thumbnail.httpThumbnailHandler.__new__(thumbnail.httpThumbnailHandler)
        handler.path = "/thumbnails/file-id/1/path/"
        handler.wfile = type("_Writer", (), {"write": lambda *_: None})()
        handler.send_response_only = unittest.mock.Mock()
        handler.send_header = unittest.mock.Mock()
        handler.end_headers = unittest.mock.Mock()
        handler.send_error = unittest.mock.Mock()

        with patch.object(thumbnail, "File") as file_cls, \
             patch.object(thumbnail, "GenerateThumbnail") as generate_thumbnail, \
             patch.object(thumbnail, "ThumbnailCacheIsStale", return_value=True), \
             patch.object(thumbnail.os.path, "exists", return_value=True), \
             patch.object(thumbnail.time, "sleep", return_value=None):
            file_cls.get.return_value = file_record
            handler.do_GET()

        self.assertEqual(generate_thumbnail.call_count, 1)

    def test_timing_excludes_opening_and_thumbnail_writing(self):
        reader = _Reader()
        clock = [0.0]
        def open_reader():
            clock[0] += 5.0
        def get_frame(number):
            self.assertEqual(number, 1)
            clock[0] += .25
            return reader._frame
        def write_thumbnail(*args):
            clock[0] += 7.0
        reader.Open = open_reader
        reader.GetFrame = get_frame
        reader._frame.Thumbnail = write_thumbnail
        with tempfile.TemporaryDirectory() as root, \
             patch.object(thumbnail.openshot.Clip, "CreateReader", return_value=reader), \
             patch.object(thumbnail, "GetThumbDeviceScale", return_value=1.0), \
             patch.object(thumbnail.time, "perf_counter", side_effect=lambda: clock[0]):
            result = thumbnail.GenerateThumbnail("source.mp4", os.path.join(root, "thumb.png"),
                                                 1, 100, 65, None, None)
        self.assertEqual(result, {"frame_ms": 250.0, "frame": 1, "decode_size": [300, 195]})
        self.assertEqual(reader.close_calls, 1)

    def test_http_records_only_new_first_frame_source_video_measurements(self):
        for cached, frame, media_type, result, expected in (
                (False, 1, "video", {"frame_ms": 300, "frame": 1}, True),
                (True, 1, "video", {"frame_ms": 300, "frame": 1}, False),
                (False, 25, "video", {"frame_ms": 300, "frame": 25}, False),
                (False, 1, "image", {"frame_ms": 300, "frame": 1}, False),
                (False, 1, "video", None, False)):
            with self.subTest(cached=cached, frame=frame, media_type=media_type, result=result):
                file = _QueriedFile()
                file.data.update(media_type=media_type, type="FFmpegReader")
                controller = SimpleNamespace(epoch=7, thumbnail_measured=unittest.mock.Mock())
                app = SimpleNamespace(window=SimpleNamespace(auto_optimize=controller))
                handler = thumbnail.httpThumbnailHandler.__new__(thumbnail.httpThumbnailHandler)
                handler.path = "/thumbnails/file-id/%s/path/" % frame
                handler.wfile = unittest.mock.Mock()
                for method in ("send_response_only", "send_header", "end_headers", "send_error"):
                    setattr(handler, method, unittest.mock.Mock())
                with patch.object(thumbnail, "get_app", return_value=app), \
                     patch.object(thumbnail.File, "get", return_value=file), \
                     patch.object(thumbnail, "GenerateThumbnail", return_value=result) as generate, \
                     patch.object(thumbnail, "source_fingerprint", return_value={"size": 100, "mtime_ns": 1}), \
                     patch.object(thumbnail, "ThumbnailCacheIsStale", return_value=False), \
                     patch.object(thumbnail.os.path, "exists", return_value=cached):
                    handler.do_GET()
                if expected:
                    controller.thumbnail_measured.emit.assert_called_once()
                    epoch, file_id, sample = controller.thumbnail_measured.emit.call_args.args
                    self.assertEqual((epoch, file_id), (7, "file-id"))
                    self.assertEqual(sample["frame_ms"], 300)
                    self.assertEqual(sample["source"], {"size": 100, "mtime_ns": 1})
                else:
                    controller.thumbnail_measured.emit.assert_not_called()
                if cached:
                    generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
