"""Tests for shared QMessageBox presentation."""

import unittest

from qt_api import QApplication, QMessageBox, QObject

from themes.base import BaseTheme, MessageBoxStyleFilter


app = QApplication.instance() or QApplication([])


class MessageBoxStylingTests(unittest.TestCase):
    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox):
                widget.close()

    def test_assigns_semantic_button_roles_and_removes_icons(self):
        box = QMessageBox(
            QMessageBox.Question,
            "Unsaved Changes",
            "Save changes to project before closing?",
            QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes,
        )

        MessageBoxStyleFilter.style_message_box(box)

        self.assertEqual(
            box.button(QMessageBox.Yes).property("dialogRole"), "primary")
        self.assertEqual(
            box.button(QMessageBox.No).property("dialogRole"), "secondary")
        self.assertEqual(
            box.button(QMessageBox.Cancel).property("dialogRole"), "cancel")
        self.assertTrue(box.button(QMessageBox.Yes).icon().isNull())
        self.assertTrue(box.button(QMessageBox.No).icon().isNull())
        self.assertTrue(box.button(QMessageBox.Cancel).icon().isNull())
        self.assertNotIn("&", box.button(QMessageBox.Yes).text())
        self.assertNotIn("&", box.button(QMessageBox.No).text())

        icon_label = box.findChild(QObject, "qt_msgboxex_icon_label")
        self.assertIsNotNone(icon_label)
        self.assertTrue(icon_label.isHidden())
        self.assertEqual(box.minimumWidth(), 400)

    def test_application_filter_styles_future_message_boxes(self):
        theme = BaseTheme(app)
        theme.install_message_box_styling()
        box = QMessageBox(
            QMessageBox.Question,
            "Confirm",
            "Continue?",
            QMessageBox.No | QMessageBox.Yes,
        )

        box.show()
        app.processEvents()

        self.assertEqual(
            box.button(QMessageBox.Yes).property("dialogRole"), "primary")
        self.assertEqual(
            box.button(QMessageBox.No).property("dialogRole"), "secondary")

if __name__ == "__main__":
    unittest.main()
