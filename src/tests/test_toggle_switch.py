"""Shared toggle input, painting, theming, and real Designer UI integration.

Runs without libopenshot on PyQt5, PyQt6, and PySide6.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from qt_api import QApplication, QCheckBox, QColor, QDialog, QPalette, QPoint, Qt, QTest, load_ui
from tests.qt_test_app import get_or_create_app
from windows.toggle_switch import ToggleSwitch

class ToggleSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))

    def toggle(self, text=''):
        toggle = ToggleSwitch(text)
        toggle.resize(toggle.sizeHint())
        toggle.show()
        self.addCleanup(toggle.deleteLater)
        self.addCleanup(toggle.hide)
        self.app.processEvents()
        return toggle

    def pixel(self, toggle, x, y):
        image = toggle.grab().toImage()
        scale = image.devicePixelRatio()
        return image.pixelColor(round(x * scale), round(y * scale))

    def test_constructor_overloads(self):
        parent = QDialog()
        self.addCleanup(parent.deleteLater)
        for toggle in (ToggleSwitch(parent), ToggleSwitch('Label', parent), ToggleSwitch(parent=parent)):
            self.assertIs(toggle.parent(), parent)
            self.assertIsInstance(toggle, QCheckBox)

    def test_translated_labels_resize_and_are_clickable_in_both_directions(self):
        toggle = self.toggle()
        compact = toggle.sizeHint()
        toggle.setText('&Preview Mask — Vorschau')
        self.assertGreater(toggle.sizeHint().width(), compact.width())
        font = toggle.font()
        font.setPointSize(24)
        toggle.setFont(font)
        self.assertGreater(toggle.sizeHint().height(), compact.height())
        toggle.resize(toggle.sizeHint().width() + 100, toggle.sizeHint().height())
        changed = Mock()
        toggle.toggled.connect(changed)
        for direction in (Qt.LeftToRight, Qt.RightToLeft):
            toggle.setLayoutDirection(direction)
            toggle.setChecked(False)
            changed.reset_mock()
            label_x = 65 if direction == Qt.LeftToRight else toggle.width() - 65
            QTest.mouseClick(toggle, Qt.LeftButton, pos=QPoint(label_x, toggle.height() // 2))
            self.assertTrue(toggle.isChecked())
            changed.assert_called_once_with(True)
            empty_x = toggle.width() - 10 if direction == Qt.LeftToRight else 10
            QTest.mouseClick(toggle, Qt.LeftButton, pos=QPoint(empty_x, toggle.height() // 2))
            self.assertTrue(toggle.isChecked())
            toggle.setEnabled(False)
            QTest.mouseClick(toggle, Qt.LeftButton, pos=QPoint(label_x, toggle.height() // 2))
            self.assertTrue(toggle.isChecked())
            toggle.setEnabled(True)

    def test_tristate_preserves_native_signal_values_and_centers_thumb(self):
        toggle = self.toggle()
        toggle.setTristate(True)
        native = QCheckBox()
        self.addCleanup(native.deleteLater)
        native.setTristate(True)
        actual, expected = [], []
        toggle.stateChanged.connect(actual.append)
        native.stateChanged.connect(expected.append)
        for _ in range(3):
            toggle.click()
            native.click()
            self.assertEqual(toggle.checkState(), native.checkState())
        self.assertEqual(actual, expected)
        toggle.setCheckState(Qt.PartiallyChecked)
        self.assertEqual(self.pixel(toggle, 19, 14), QColor('#e2e7ed'))

    def test_palette_and_stylesheet_colors_are_rendered(self):
        toggle = self.toggle()
        toggle.clearFocus()
        toggle.setStyleSheet('ToggleSwitch { qproperty-uncheckedColor: #a03050; qproperty-thumbColor: #fff080; }')
        self.app.processEvents()
        toggle.setAttribute(Qt.WA_UnderMouse, False)
        self.assertEqual(self.pixel(toggle, 26, 14), QColor('#a03050'))
        self.assertEqual(self.pixel(toggle, 12, 14), QColor('#fff080'))
        toggle.setChecked(True)
        for color in ('#2080c0', '#a04080'):
            palette = toggle.palette()
            palette.setColor(QPalette.Highlight, QColor(color))
            toggle.setPalette(palette)
            actual = self.pixel(toggle, 12, 14).getRgb()
            expected = QColor(color).darker(115).getRgb()
            # HSV-to-RGB conversion can round channels differently in Qt versions.
            self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(actual, expected)))

    def test_label_is_painted_with_theme_text_color(self):
        toggle = self.toggle('Preview Mask')
        palette = toggle.palette()
        palette.setColor(QPalette.WindowText, QColor('#ff0000'))
        toggle.setPalette(palette)
        for stylesheet in ('', 'QCheckBox#checkboxMetrics { color: #ff0000; }'):
            toggle.setObjectName('checkboxMetrics')
            if stylesheet:
                toggle.setPalette(self.app.palette())
            toggle.setStyleSheet(stylesheet)
            image = toggle.grab().toImage()
            scale = image.devicePixelRatio()
            self.assertTrue(any(
                image.pixelColor(x, y).red() > 200 and image.pixelColor(x, y).green() < 80
                for x in range(round(50 * scale), image.width()) for y in range(image.height())))

    def test_designer_dialogs_use_toggles_and_keep_defaults(self):
        # Match the resource module alias installed by the application at startup.
        from classes import openshot_rc
        ui_dir = Path(__file__).resolve().parents[1] / 'windows' / 'ui'
        for filename, names in (
            ('animation.ui', {'chkLoop': False}),
            ('export.ui', {'checkStartFirstClip': False, 'checkEndLastClip': True}),
        ):
            for use_base in (False, True):
                with self.subTest(filename=filename, use_base=use_base):
                    base = QDialog() if use_base else None
                    with patch.dict(sys.modules, {'openshot_rc': openshot_rc}):
                        dialog = load_ui(str(ui_dir / filename), base)
                    self.addCleanup(dialog.deleteLater)
                    for name, checked in names.items():
                        toggle = dialog.findChild(ToggleSwitch, name)
                        self.assertIsNotNone(toggle, name)
                        if use_base:
                            self.assertIs(getattr(base, name), toggle)
                        self.assertTrue(toggle.text())
                        self.assertEqual(toggle.isChecked(), checked)
                        toggle.click()
                        self.assertEqual(toggle.isChecked(), not checked)


if __name__ == '__main__':
    unittest.main()
