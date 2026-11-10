"""Missing-file dialog ownership and nested folder-picker regression tests."""

import types
import unittest
from unittest.mock import patch

from qt_api import QApplication, QDialog, QPushButton, QWidget
from tests.qt_test_app import get_or_create_app
from windows.views import find_file


class MissingFileDialogTests(unittest.TestCase):
    def setUp(self):
        self.app, _ = get_or_create_app(lambda: QApplication([]))
        self.window = QWidget()
        self.addCleanup(self.window.deleteLater)
        app = types.SimpleNamespace(window=self.window, _tr=lambda text: text)
        app_patch = patch.object(find_file, "get_app", return_value=app)
        app_patch.start()
        self.addCleanup(app_patch.stop)

    def test_browse_cancel_retry_and_parent_ownership(self):
        def choose_folder(parent, caption, directory):
            self.assertIs(parent.parentWidget(), self.window)
            button = parent.findChild(QPushButton, "acceptButton")
            self.assertFalse(button.isEnabled())
            # Even explicit re-entry must not start a second picker.
            button.clicked.emit()
            return "" if picker.call_count == 1 else "/relocated"

        def interact(dialog):
            button = dialog.findChild(QPushButton, "acceptButton")
            button.click()
            self.assertTrue(button.isEnabled())
            self.assertEqual(dialog.result(), QDialog.Rejected)
            button.click()
            self.assertEqual(dialog.result(), QDialog.Accepted)

        with patch.object(find_file, "get_existing_directory", side_effect=choose_folder) as picker, \
                patch.object(QDialog, "exec_", interact):
            result = find_file._show_missing_file_dialog("image.png", "/old/image.png", "/tmp")
        self.assertEqual(result, ("locate", "/relocated/image.png"))
        self.assertEqual(picker.call_count, 2)

    def test_remove_choices_do_not_open_picker(self):
        for label, action in (("Remove", "file"), ("Remove All Missing", "all")):
            def interact(dialog):
                for button in dialog.findChildren(QPushButton):
                    if button.text() == label:
                        button.click()
                        return
                self.fail("Missing remove button")

            with self.subTest(action=action), \
                    patch.object(find_file, "get_existing_directory") as picker, \
                    patch.object(QDialog, "exec_", interact):
                result = find_file._show_missing_file_dialog("image.png", "/old/image.png", "/tmp")
                self.assertEqual(result, (action, "/old/image.png"))
                picker.assert_not_called()
