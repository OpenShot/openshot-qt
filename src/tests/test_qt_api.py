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

    def test_shared_toggle_imports_and_enums_are_available(self):
        for name in ("QCheckBox", "QColor", "QPainter", "QPalette", "QPen", "QPointF",
                     "QRectF", "QSize", "Property"):
            with self.subTest(name=name, binding=qt_api.QT_API):
                self.assertIsNotNone(getattr(qt_api, name))
        for name in ("StrongFocus", "PointingHandCursor", "NoBrush", "NoPen", "PartiallyChecked"):
            with self.subTest(name=name, binding=qt_api.QT_API):
                self.assertIsNotNone(getattr(qt_api.Qt, name))
        self.assertIsNotNone(qt_api.QPainter.Antialiasing)
        for name in ("Active", "Highlight", "WindowText"):
            self.assertIsNotNone(getattr(qt_api.QPalette, name))

    def test_toggle_text_flags_are_available_on_all_bindings(self):
        flags = qt_api.Qt.AlignLeft | qt_api.Qt.AlignVCenter | qt_api.Qt.TextShowMnemonic
        self.assertNotEqual(int(getattr(flags, "value", flags)), 0)

    def test_common_qt_types_are_eagerly_exported(self):
        """Python 3.6 cannot use the module-level __getattr__ fallback."""
        for name in ("QCoreApplication", "QPointF", "QRectF", "Qt"):
            with self.subTest(name=name):
                self.assertIn(name, vars(qt_api))
                self.assertIsNotNone(vars(qt_api)[name])

    def test_event_type_aliases_are_available_on_all_bindings(self):
        """Every unscoped QEvent alias used in the codebase must resolve.

        PyQt6 only exposes scoped enums (QEvent.Type.X); a missing alias
        raises AttributeError inside eventFilter, which PyQt6 treats as fatal.
        """
        for name in ("ShortcutOverride", "Resize", "Paint", "KeyPress", "KeyRelease",
                     "MouseButtonPress", "MouseButtonRelease", "MouseMove", "Wheel",
                     "TouchBegin", "TouchUpdate", "WindowActivate", "WindowStateChange",
                     "DeferredDelete", "Close", "Hide", "Show", "Move"):
            with self.subTest(name=name, binding=qt_api.QT_API):
                event_type = getattr(qt_api.QEvent, name)
                self.assertEqual(qt_api.QEvent(event_type).type(), event_type)

if __name__ == "__main__":
    unittest.main()
