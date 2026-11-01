"""Regression tests for preserving files when a save fails."""

import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qt_api


class FileWriteTests(unittest.TestCase):
    def test_failed_flush_or_replace_preserves_previous_project(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "project.osp"
                path.write_text('{"clips": []}', encoding="utf-8")
                with patch.object(qt_api.os, operation, side_effect=OSError(errno.ENOSPC, "disk full")):
                    with self.assertRaises(OSError):
                        qt_api.write_file_text(path, '{"clips": [{"id": "new"}]}')
                self.assertEqual(path.read_text(encoding="utf-8"), '{"clips": []}')
                self.assertEqual(os.listdir(directory), ["project.osp"])

    def test_successful_save_replaces_unicode_file_and_preserves_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vidéo.osp"
            path.write_text("old", encoding="utf-8")
            path.chmod(0o640)
            qt_api.write_file_text(path, '{"title": "日本語"}')
            self.assertEqual(path.read_text(encoding="utf-8"), '{"title": "日本語"}')
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            self.assertEqual(os.listdir(directory), ["vidéo.osp"])

    def test_windows_lock_retries_atomic_replace_without_rewriting_data(self):
        for code in (5, 32, 33):
            with self.subTest(winerror=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "openshot.settings"
                path.write_text("old")
                locked = PermissionError("locked")
                locked.winerror = code
                replace = os.replace
                calls = []

                def transient_lock(source, destination):
                    calls.append(source)
                    self.assertEqual(path.read_text(), "old")
                    if len(calls) < 3:
                        raise locked
                    replace(source, destination)

                with patch.object(qt_api.os, "replace", side_effect=transient_lock), \
                        patch.object(qt_api.time, "sleep"):
                    qt_api.write_file_text(path, "new")
                self.assertEqual(path.read_text(), "new")
                self.assertEqual(len(set(calls)), 1)
                self.assertEqual(os.listdir(directory), ["openshot.settings"])

    def test_permanent_access_denial_preserves_file_and_removes_temporary(self):
        for code, attempts in ((5, 4), (None, 1)):
            with self.subTest(winerror=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "project.osp"
                path.write_text("original")
                denied = PermissionError("denied")
                if code is not None:
                    denied.winerror = code
                with patch.object(qt_api.os, "replace", side_effect=denied) as replace, \
                        patch.object(qt_api.time, "sleep") as sleep:
                    with self.assertRaises(PermissionError):
                        qt_api.write_file_text(path, "new")
                self.assertEqual(replace.call_count, attempts)
                self.assertEqual(sleep.call_count, attempts - 1)
                self.assertEqual(path.read_text(), "original")
                self.assertEqual(os.listdir(directory), ["project.osp"])

    def test_content_uri_keeps_existing_writer(self):
        with patch.object(qt_api, "write_to_content_uri") as write:
            qt_api.write_file_text("content://documents/project", "new data")
            write.assert_called_once_with("content://documents/project", "new data")
