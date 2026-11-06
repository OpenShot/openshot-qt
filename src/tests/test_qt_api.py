"""Tests for the centralized Qt binding loader."""

import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

import qt_api


class QtApiTests(unittest.TestCase):
    def test_application_exec_alias_supports_class_and_instance_calls(self):
        # Isolate application lifetime from the rest of the widget test suite.
        script = """
from qt_api import QApplication, QCoreApplication, QEventLoop, QTimer, QtGui
app = QApplication([])
for run in (QCoreApplication.exec_, QtGui.QGuiApplication.exec_,
            QApplication.exec_, app.exec_):
    QTimer.singleShot(0, lambda: app.exit(0))
    assert run() == 0
loop = QEventLoop()
QTimer.singleShot(0, loop.quit)
assert loop.exec_() == 0
"""
        env = os.environ.copy()
        env["OPENSHOT_QT_API"] = qt_api.QT_API
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONPATH"] = PATH + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True,
            text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dialogs_have_no_context_help_button(self):
        # Qt5 on Windows adds a "?" button that does nothing in OpenShot.
        script = """
import sys
sys.modules["OpenGL"] = None  # skip OpenGL setup; only attributes matter here
from classes.qt_bootstrap import configure_qt
configure_qt()
from qt_api import QApplication, Qt
help_button = getattr(Qt, "AA_DisableWindowContextHelpButton", None)
sys.exit(0 if help_button is None or QApplication.testAttribute(help_button) else 1)
"""
        env = os.environ.copy()
        env["OPENSHOT_QT_API"] = qt_api.QT_API
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONPATH"] = PATH + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(  # nosec B603 - Fixed interpreter and script; no shell.
            [sys.executable, "-c", script], env=env, capture_output=True,
            text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_qt6_scoped_tooltip_and_focus_events_get_legacy_aliases(self):
        events = SimpleNamespace(ToolTip=110, FocusOut=9, WindowDeactivate=25)
        event_class = type("ScopedEvent", (), {"Type": events})
        core = SimpleNamespace(QEvent=event_class, Qt=SimpleNamespace())
        with patch.multiple(qt_api, QT_API="pyqt6", QtCore=core,
                            QtGui=SimpleNamespace(), QtWidgets=SimpleNamespace()):
            qt_api._patch_enums_for_qt6()
        for name in ("ToolTip", "FocusOut", "WindowDeactivate"):
            self.assertEqual(getattr(event_class, name), getattr(events, name))

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
