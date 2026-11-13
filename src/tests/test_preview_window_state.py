"""Project-level source preview window sizing."""
import types
import unittest
from unittest.mock import Mock, patch

from qt_api import QApplication, QDialog, QSize
from tests.qt_test_app import get_or_create_app
from windows.preview_design import PreviewWindowState


class PreviewWindowStateTests(unittest.TestCase):
    def setUp(self):
        self.qt_app, _ = get_or_create_app(lambda: QApplication([]))
        self.project = {'settings': {'preview_volume': 42}}
        self.updates = Mock()
        self.updates.update_untracked.side_effect = lambda key, value: self.project.update({key[0]: value})
        self.patch = patch('windows.preview_design.get_app', return_value=types.SimpleNamespace(
            project=self.project, updates=self.updates))
        self.patch.start()
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.close()
            dialog._state.timer.stop()
        self.patch.stop()

    def dialog(self):
        dialog = QDialog()
        dialog.resize(650, 400)
        dialog._state = PreviewWindowState(dialog)
        self.dialogs.append(dialog)
        return dialog

    def test_close_persists_size_and_preserves_volume(self):
        first = self.dialog()
        first.show()
        first.resize(800, 580)
        self.qt_app.processEvents()
        first.close()
        self.assertEqual(self.project['settings']['preview_volume'], 42)
        second = self.dialog()
        self.assertEqual(second.size(), QSize(800, 580))
        self.assertFalse(second.isMaximized())

    def test_maximized_state_preserves_normal_size(self):
        first = self.dialog()
        first.resize(800, 580)
        first.show()
        self.qt_app.processEvents()
        first.showMaximized()
        self.qt_app.processEvents()
        first._state.save()
        self.assertEqual(self.project['settings']['preview_window'],
                         {'width': 800, 'height': 580, 'maximized': True})
        second = self.dialog()
        self.assertTrue(second.isMaximized())
        second.showNormal()
        self.qt_app.processEvents()
        second._state.save()
        self.assertFalse(self.project['settings']['preview_window']['maximized'])

    def test_missing_or_invalid_state_uses_default(self):
        for state in (None, 'invalid', {}, {'width': -1, 'height': 200},
                      {'width': 'bad', 'height': 200}):
            self.project['settings']['preview_window'] = state
            self.assertEqual(self.dialog().size(), QSize(650, 400))

    def test_oversized_saved_window_is_limited_to_screen(self):
        self.project['settings']['preview_window'] = {'width': 100000, 'height': 100000}
        dialog = self.dialog()
        available = self.qt_app.primaryScreen().availableGeometry()
        self.assertLessEqual(dialog.width(), available.width())
        self.assertLessEqual(dialog.height(), available.height())

    def test_minimized_state_does_not_replace_saved_size(self):
        dialog = self.dialog()
        dialog.show()
        dialog._state.save()
        saved = dict(self.project['settings']['preview_window'])
        dialog.showMinimized()
        self.qt_app.processEvents()
        dialog._state.save()
        self.assertEqual(self.project['settings']['preview_window'], saved)
