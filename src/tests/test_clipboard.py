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

"""Regression tests for OpenShot clipboard payloads."""

import pickle  # nosec B403 - Generate controlled pickle fixtures for regression tests.
import unittest
from unittest.mock import patch

from qt_api import QMimeData
from classes.clipboard import ClipboardManager


class ClipboardTests(unittest.TestCase):
    def test_executable_globals_are_rejected_without_execution(self):
        class Payload:
            def __reduce__(self):
                return eval, ("1 + 1",)
        mime = QMimeData()
        mime.setData("application/x-openshot-generic", pickle.dumps(Payload()))
        with patch("builtins.eval") as execute:
            self.assertIsNone(ClipboardManager.from_mime(mime))
            execute.assert_not_called()

    def test_clip_objects_round_trip_with_unknown_fields(self):
        from classes.query import Clip
        clip = Clip()
        clip.id = "C1"
        clip.data = {"id": "C1", "unknown": {"keep": [1, 2]}}
        restored = ClipboardManager.from_mime(ClipboardManager.to_mime(clip))
        self.assertIsInstance(restored, Clip)
        self.assertEqual(restored.data, clip.data)

    def test_empty_and_truncated_payloads_are_ignored(self):
        payload = pickle.dumps({"id": "clip", "values": list(range(100))})
        for data in (b"", payload[:2], payload[:-1]):
            with self.subTest(data=data):
                mime = QMimeData()
                mime.setData("application/x-openshot-generic", data)
                self.assertIsNone(ClipboardManager.from_mime(mime))

    def test_valid_payload_is_preserved(self):
        value = {"id": "clip", "values": [1, 2, 3]}
        mime = QMimeData()
        mime.setData("application/x-openshot-generic", pickle.dumps(value))
        self.assertEqual(ClipboardManager.from_mime(mime), value)
