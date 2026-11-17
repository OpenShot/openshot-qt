# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.

"""Save failures must preserve the last usable project."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classes.json_data import JsonDataStore


class JsonSaveTests(unittest.TestCase):
    def test_path_conversion_context_is_private_to_each_store(self):
        first, second = JsonDataStore(), JsonDataStore()
        original = first.replace_string_to_absolute

        def interleaved(match):
            second.convert_paths_to_absolute("/two/project.osp", '{"path": "media.mp4"}')
            return original(match)

        with patch.object(first, "replace_string_to_absolute", side_effect=interleaved):
            converted = first.convert_paths_to_absolute("/one/project.osp", '{"path": "media.mp4"}')
        self.assertEqual(json.loads(converted)["path"], "/one/media.mp4")

    def test_backup_streams_json_without_building_one_large_string(self):
        data = {"clips": [{"title": "日本語", "samples": list(range(1000))}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.osp"
            with patch.object(json.JSONEncoder, "encode", side_effect=AssertionError("full serialization")):
                JsonDataStore().write_to_file(path, data)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)

    def test_memory_failure_mid_serialization_preserves_backup(self):
        def fail_after_start(*args, **kwargs):
            yield '{"clips": ['
            raise MemoryError()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.osp"
            path.write_text('{"clips": []}', encoding="utf-8")
            with patch.object(json.JSONEncoder, "iterencode", fail_after_start):
                with self.assertRaises(MemoryError):
                    JsonDataStore().write_to_file(path, {})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"clips": []})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_replace_failure_preserves_last_good_project_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.osp"
            path.write_text('{"last_good": true}', encoding="utf-8")
            with patch("qt_api.os.replace", side_effect=PermissionError("replace denied")):
                with self.assertRaises(PermissionError):
                    JsonDataStore().write_to_file(path, {"new": "snapshot"})
            self.assertEqual(json.loads(path.read_text()), {"last_good": True})
            self.assertEqual(list(Path(directory).iterdir()), [path])
