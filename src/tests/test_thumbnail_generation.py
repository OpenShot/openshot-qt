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
            thumbnail.GenerateThumbnail("missing.webp", "/tmp/thumb.png", 7, 20, 20, None, None)

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


if __name__ == "__main__":
    unittest.main()
