"""Preferences toggles retain native checkbox input and signals."""
import importlib
import unittest
from unittest.mock import Mock

from qt_api import QApplication, QCheckBox, QColor, QPoint, Qt, QT_API
from tests.qt_test_app import get_or_create_app
from windows.preference_switch import PreferenceSwitch

binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
QTest = importlib.import_module(binding + '.QtTest').QTest


class PreferenceSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))

    def setUp(self):
        self.toggle = PreferenceSwitch()
        self.toggle.resize(200, 28)
        self.toggle.show()
        self.addCleanup(self.toggle.deleteLater)
        self.addCleanup(self.toggle.hide)
        self.app.processEvents()

    def test_mouse_and_space_emit_native_checkbox_state(self):
        self.assertIsInstance(self.toggle, QCheckBox)
        changes = Mock()
        self.toggle.stateChanged.connect(changes)
        QTest.mouseClick(self.toggle, Qt.LeftButton, pos=QPoint(25, 14))
        self.assertTrue(self.toggle.isChecked())
        self.assertEqual(changes.call_count, 1)
        self.toggle.setFocus()
        QTest.keyClick(self.toggle, Qt.Key_Space)
        self.assertFalse(self.toggle.isChecked())
        self.assertEqual(changes.call_count, 2)

    def test_empty_row_space_and_disabled_switch_do_not_toggle(self):
        QTest.mouseClick(self.toggle, Qt.LeftButton, pos=QPoint(150, 14))
        self.assertFalse(self.toggle.isChecked())
        self.toggle.setEnabled(False)
        QTest.mouseClick(self.toggle, Qt.LeftButton, pos=QPoint(25, 14))
        QTest.keyClick(self.toggle, Qt.Key_Space)
        self.assertFalse(self.toggle.isChecked())

    def test_thumb_position_distinguishes_on_and_off_in_both_directions(self):
        for direction in (Qt.LayoutDirection.LeftToRight, Qt.LayoutDirection.RightToLeft):
            self.toggle.setLayoutDirection(direction)
            left = 3 if direction == Qt.LayoutDirection.LeftToRight else self.toggle.width() - 35
            for checked in (False, True):
                with self.subTest(direction=direction, checked=checked):
                    self.toggle.setChecked(checked)
                    image = self.toggle.grab().toImage()
                    scale = image.devicePixelRatio()
                    right = checked != (direction == Qt.LayoutDirection.RightToLeft)
                    thumb_x = left + (23 if right else 9)
                    empty_x = left + (9 if right else 23)
                    self.assertEqual(image.pixelColor(round(thumb_x * scale), round(14 * scale)), QColor('#e2e7ed'))
                    self.assertNotEqual(image.pixelColor(round(empty_x * scale), round(14 * scale)), QColor('#e2e7ed'))


if __name__ == '__main__':
    unittest.main()
