"""
 @file
 @brief Test file model importing and fallback support
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import importlib
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)


class ReaderStub:
    def __init__(self, *, json_text='{"path":"dummy"}', duration=1.5, open_error=None):
        self._json_text = json_text
        self.info = types.SimpleNamespace(duration=duration)
        self._open_error = open_error
        self.open_calls = 0
        self.close_calls = 0
        self.max_decode_sizes = []

    def SetMaxDecodeSize(self, width, height):
        self.max_decode_sizes.append((width, height))

    def Open(self):
        self.open_calls += 1
        if self._open_error:
            raise self._open_error

    def Json(self):
        return self._json_text

    def Close(self):
        self.close_calls += 1


class FilesModelImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files_model_module = importlib.import_module("windows.models.files_model")

    def test_reimport_full_source_with_surviving_split_ranges(self):
        """Ranges must neither block source import nor become its duplicate target."""
        module = self.files_model_module
        entries = [types.SimpleNamespace(id=str(i), data={
            "path": "/tmp/file1.mp4", "start": i * 10., "end": (i + 1) * 10.})
            for i in range(10)]
        original_ranges = [dict(entry.data) for entry in entries]

        class FileStore:
            @staticmethod
            def filter(**kwargs):
                return entries

            def save(self):
                self.id = "original"
                entries.append(self)

        app = types.SimpleNamespace(_tr=lambda s: s, get_settings=Mock(), processEvents=Mock(),
                                    window=types.SimpleNamespace(statusBar=Mock(), filesView=Mock()))
        model = types.SimpleNamespace(selection_model=Mock(), proxy_model=Mock())
        model.proxy_model.get_file_index.return_value.isValid.return_value = False
        metadata = {"path": "/tmp/file1.mp4", "duration": 100., "has_video": True,
                    "has_audio": True, "type": "FFmpegReader"}
        with patch.object(module, "File", FileStore), \
                patch.object(module, "get_app", return_value=app), \
                patch.object(module, "inspect_media", return_value=(metadata, 100.)) as inspect:
            for path in ("/tmp/file1.mp4", "/tmp/./file1.mp4"):
                module.FilesModel.add_files(model, [path], quiet=True,
                                            prevent_image_seq=True, prevent_recent_folder=True)
            inspect.assert_called_once()
        self.assertEqual(len(entries), 11)
        self.assertEqual([entry.data for entry in entries[:10]], original_ranges)
        self.assertNotIn("start", entries[-1].data)
        self.assertNotIn("end", entries[-1].data)
        self.assertEqual(model.proxy_model.get_file_index.call_args_list[-1].args, ("original",))

    def test_inspect_media_retries_with_inspect_reader_true_after_open_failure(self):
        first_reader = ReaderStub(open_error=RuntimeError("QtImageReader could not open image file."))
        second_reader = ReaderStub(json_text='{"media":"ok"}', duration=2.25)
        create_reader_calls = []

        def create_reader(path, inspect_reader):
            create_reader_calls.append((path, inspect_reader))
            return second_reader if inspect_reader else first_reader

        with patch.object(self.files_model_module.openshot.Clip, "CreateReader", side_effect=create_reader):
            file_data, duration = self.files_model_module.inspect_media("example.flac", 128, 72)

        self.assertEqual(create_reader_calls, [("example.flac", False), ("example.flac", True)])
        self.assertEqual(first_reader.max_decode_sizes, [(128, 72)])
        self.assertEqual(second_reader.max_decode_sizes, [(128, 72)])
        self.assertEqual(first_reader.open_calls, 1)
        self.assertEqual(first_reader.close_calls, 0)
        self.assertEqual(second_reader.open_calls, 1)
        self.assertEqual(second_reader.close_calls, 1)
        self.assertEqual(file_data, {"media": "ok"})
        self.assertEqual(duration, 2.25)

    def test_inspect_media_returns_first_attempt_when_open_succeeds(self):
        reader = ReaderStub(json_text='{"media":"ok"}', duration=3.0)

        with patch.object(self.files_model_module.openshot.Clip, "CreateReader", return_value=reader) as create_reader:
            file_data, duration = self.files_model_module.inspect_media("example.wav", 64, 64)

        create_reader.assert_called_once_with("example.wav", False)
        self.assertEqual(reader.max_decode_sizes, [(64, 64)])
        self.assertEqual(reader.open_calls, 1)
        self.assertEqual(reader.close_calls, 1)
        self.assertEqual(file_data, {"media": "ok"})
        self.assertEqual(duration, 3.0)

    def test_process_urls_preserves_original_url_order_for_import(self):
        files_model_cls = self.files_model_module.FilesModel
        fake_self = types.SimpleNamespace()
        captured = {}

        def record_add_files(paths, quiet=False, prevent_image_seq=False):
            captured["paths"] = list(paths)
            captured["quiet"] = quiet
            captured["prevent_image_seq"] = prevent_image_seq

        fake_self.add_files = record_add_files

        fake_app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(OpenProjectSignal=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)),
        )

        urls = [
            types.SimpleNamespace(toLocalFile=lambda: "/tmp/zeta.mp4"),
            types.SimpleNamespace(toLocalFile=lambda: "/tmp/alpha.mp4"),
        ]

        with patch.object(self.files_model_module.os.path, "exists", return_value=True), \
                patch.object(self.files_model_module.os.path, "isdir", return_value=False), \
                patch.object(self.files_model_module.os.path, "isfile", return_value=True), \
                patch.object(self.files_model_module, "get_app", return_value=fake_app):
            files_model_cls.process_urls(fake_self, urls)

        self.assertEqual(captured["paths"], ["/tmp/zeta.mp4", "/tmp/alpha.mp4"])

    def test_process_urls_sorts_directory_contents_in_place(self):
        files_model_cls = self.files_model_module.FilesModel
        fake_self = types.SimpleNamespace()
        captured = {}

        def record_add_files(paths, quiet=False, prevent_image_seq=False):
            captured["paths"] = list(paths)
            captured["quiet"] = quiet
            captured["prevent_image_seq"] = prevent_image_seq

        fake_self.add_files = record_add_files

        fake_app = types.SimpleNamespace(
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(OpenProjectSignal=types.SimpleNamespace(emit=lambda *_args, **_kwargs: None)),
        )

        urls = [
            types.SimpleNamespace(toLocalFile=lambda: "/tmp/zeta.mp4"),
            types.SimpleNamespace(toLocalFile=lambda: "/tmp/imports"),
            types.SimpleNamespace(toLocalFile=lambda: "/tmp/alpha.mp4"),
        ]

        def fake_isdir(path):
            return path == "/tmp/imports"

        def fake_isfile(path):
            return not fake_isdir(path)

        def fake_walk(path):
            dirs = ["scene_b", "scene_a"]
            yield path, dirs, ["clip_b.mp4", "clip_a.mp4"]
            for dirname in dirs:
                filenames = {
                    "scene_a": ["take_4.mp4", "take_3.mp4"],
                    "scene_b": ["take_2.mp4", "take_1.mp4"],
                }[dirname]
                yield os.path.join(path, dirname), [], filenames

        with patch.object(self.files_model_module.os.path, "exists", return_value=True), \
                patch.object(self.files_model_module.os.path, "isdir", side_effect=fake_isdir), \
                patch.object(self.files_model_module.os.path, "isfile", side_effect=fake_isfile), \
                patch.object(self.files_model_module.os, "walk", side_effect=fake_walk), \
                patch.object(self.files_model_module, "get_app", return_value=fake_app):
            files_model_cls.process_urls(fake_self, urls)

        self.assertEqual(captured["paths"], [
            "/tmp/zeta.mp4",
            "/tmp/imports/clip_a.mp4",
            "/tmp/imports/clip_b.mp4",
            "/tmp/imports/scene_a/take_3.mp4",
            "/tmp/imports/scene_a/take_4.mp4",
            "/tmp/imports/scene_b/take_1.mp4",
            "/tmp/imports/scene_b/take_2.mp4",
            "/tmp/alpha.mp4",
        ])
        self.assertTrue(captured["quiet"])


if __name__ == "__main__":
    unittest.main()
