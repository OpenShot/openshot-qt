"""Tests for the centralized Qt binding loader."""

import os
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

import qt_api


class QtApiTests(unittest.TestCase):
    def test_feedback_event_types_are_available_on_all_bindings(self):
        for name in ("KeyPress", "MouseButtonPress", "MouseButtonRelease",
                     "MouseMove", "Wheel", "TouchBegin", "TouchUpdate",
                     "WindowActivate", "Hide", "DeferredDelete"):
            with self.subTest(name=name, binding=qt_api.QT_API):
                event_type = getattr(qt_api.QEvent, name)
                self.assertEqual(qt_api.QEvent(event_type).type(), event_type)

    def test_common_qt_types_are_eagerly_exported(self):
        """Python 3.6 cannot use the module-level __getattr__ fallback."""
        for name in ("QCoreApplication", "QPointF", "QRectF", "Qt"):
            with self.subTest(name=name):
                self.assertIn(name, vars(qt_api))
                self.assertIsNotNone(vars(qt_api)[name])


if __name__ == "__main__":
    unittest.main()
