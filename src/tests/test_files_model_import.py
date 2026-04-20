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
from unittest.mock import patch


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
        self.assertEqual(first_reader.max_decode_sizes, [])
        self.assertEqual(second_reader.max_decode_sizes, [])
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
        self.assertEqual(reader.max_decode_sizes, [])
        self.assertEqual(reader.open_calls, 1)
        self.assertEqual(reader.close_calls, 1)
        self.assertEqual(file_data, {"media": "ok"})
        self.assertEqual(duration, 3.0)

    def test_inspect_media_preserves_reader_reported_dimensions_when_max_size_requested(self):
        reader = ReaderStub(
            json_text='{"media":"ok","width":1920,"height":1080}',
            duration=3.0,
        )

        with patch.object(self.files_model_module.openshot.Clip, "CreateReader", return_value=reader):
            file_data, _duration = self.files_model_module.inspect_media("example.mp4", 128, 128)

        self.assertEqual(reader.max_decode_sizes, [])
        self.assertEqual(file_data["width"], 1920)
        self.assertEqual(file_data["height"], 1080)


if __name__ == "__main__":
    unittest.main()
