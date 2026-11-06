"""Regression tests for OpenShot clipboard payloads."""

import pickle  # nosec B403 - Generate controlled pickle fixtures for regression tests.
import unittest

from qt_api import QMimeData
from classes.clipboard import ClipboardManager


class ClipboardTests(unittest.TestCase):
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
