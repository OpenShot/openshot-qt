"""Tests for the centralized Qt binding loader."""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

import qt_api


class QtApiTests(unittest.TestCase):
    def test_common_qt_types_are_eagerly_exported(self):
        """Python 3.6 cannot use the module-level __getattr__ fallback."""
        for name in ("QCoreApplication", "QPointF", "QRectF", "Qt"):
            with self.subTest(name=name):
                self.assertIn(name, vars(qt_api))
                self.assertIsNotNone(vars(qt_api)[name])


if __name__ == "__main__":
    unittest.main()
