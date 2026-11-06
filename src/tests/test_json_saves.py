"""Save failures must preserve the last usable project."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classes.json_data import JsonDataStore


class JsonSaveTests(unittest.TestCase):
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
