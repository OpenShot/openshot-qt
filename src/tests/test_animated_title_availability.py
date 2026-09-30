"""Unavailable Blender keeps browsing and Cancel active, without editing."""
from contextlib import ExitStack
from types import SimpleNamespace
import importlib
import unittest
from unittest.mock import Mock, patch

from qt_api import QApplication, QDialog, QStandardItem, Qt, QPoint, QPixmap, QPainter, QStyle, QStyleOptionButton, QT_API
from tests.qt_test_app import ensure_app_state, get_or_create_app
from tests.test_project_data import DummySettings

binding = {"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API]
QTest = importlib.import_module(binding + ".QtTest").QTest


class AnimatedTitleAvailabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))
        ensure_app_state(cls.app, DummySettings)
        from windows.animated_title import AnimatedTitle
        cls.dialog_class = AnimatedTitle

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        project = SimpleNamespace(get=lambda key: {'num': 30, 'den': 1})
        self.stack.enter_context(patch.object(self.app, 'project', project, create=True))
        self.stack.enter_context(patch.object(self.app, 'window', SimpleNamespace(WaitCursorSignal=Mock()), create=True))
        self.stack.enter_context(patch('windows.animated_title.ui_util.init_ui'))
        self.stack.enter_context(patch('windows.animated_title.metrics.track_metric_screen'))
        # Keep the real view/model and avoid generating image thumbnails.
        def populate(model):
            for number in range(60):
                model.model.appendRow(QStandardItem('Sample title %s' % number))
        self.stack.enter_context(patch('windows.models.blender_model.BlenderModel.update_model',
                                       autospec=True, side_effect=populate))

    def dialog(self, snap):
        with patch('windows.animated_title.is_snap', return_value=snap):
            dialog = self.dialog_class()
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.reject)
        return dialog

    def assert_disabled_editor(self, dialog):
        self.assertFalse(dialog.blenderNotice.isHidden())
        self.assertTrue(dialog.blenderNotice.isEnabled())
        self.assertTrue(dialog.splitter.isEnabled())
        self.assertTrue(dialog.blenderView.isEnabled())
        self.assertTrue(dialog.scrollArea.isEnabled())
        self.assertFalse(dialog.settingsContainer.isEnabled())
        for row in range(dialog.blenderView.model().rowCount()):
            flags = dialog.blenderView.model().index(row, 0).flags()
            self.assertFalse(flags & Qt.ItemIsEnabled)
            self.assertFalse(flags & Qt.ItemIsSelectable)
        self.assertFalse(dialog.sliderPreview.isEnabled())
        self.assertFalse(dialog.btnRefresh.isEnabled())
        self.assertFalse(dialog.btnRender.isEnabled())
        self.assertTrue(dialog.btnCancel.isEnabled())
        self.assertFalse(dialog.blenderView.preview_timer.isActive())
        self.assertGreater(dialog.blenderView.model().rowCount(), 0)
        self.assertFalse(dialog.blenderNotice.wordWrap())
        self.assertNotIn('\n', dialog.blenderNotice.text())

    def test_snap_keeps_templates_visible_and_never_starts_blender(self):
        with patch('windows.views.blender_listview.Worker') as worker:
            dialog = self.dialog(snap=True)
            dialog.show()
            dialog.resize(900, 700)
            self.app.processEvents()
            self.assert_disabled_editor(dialog)
            self.assertLess(dialog.blenderNotice.height(), dialog.splitter.height() / 2)
            self.assertIn('Snap', dialog.blenderNotice.text())
            dialog.accept()
            dialog.blenderView.Render()
            dialog.blenderView.setCurrentIndex(dialog.blenderView.model().index(0, 0))
            worker.assert_not_called()
            self.assertTrue(dialog.isVisible())
            dialog.btnCancel.click()
            self.assertFalse(dialog.isVisible())
            self.assertEqual(dialog.result(), QDialog.Rejected)

    def test_blender_errors_use_banner_and_cleanup_does_not_reenable_editor(self):
        from classes import info
        for version, detail, expected in (
                ('2.0', None, info.BLENDER_MIN_VERSION),
                (None, None, 'Preferences'),
                (None, 'private path and technical traceback', 'Preferences')):
            with self.subTest(version=version, detail=detail):
                dialog = self.dialog(snap=False)
                dialog.blenderView.preview_timer.start()
                dialog.blenderView.error_with_blender(version, detail)
                dialog.show()
                self.assert_disabled_editor(dialog)
                self.assertIn(expected, dialog.blenderNotice.text())
                self.assertNotIn('technical traceback', dialog.blenderNotice.text())
                # Worker cleanup arrives after its error signal.
                dialog.blenderView.end_processing()
                self.assert_disabled_editor(dialog)
                self.assertTrue(dialog.isVisible())
                dialog.btnCancel.click()
                self.assertFalse(dialog.isVisible())

    def test_normal_dialog_remains_available(self):
        dialog = self.dialog(snap=False)
        self.assertTrue(dialog.blenderNotice.isHidden())
        self.assertTrue(dialog.splitter.isEnabled())
        dialog.blenderView.end_processing()
        self.assertTrue(dialog.btnRender.isEnabled())
        with patch.object(dialog.blenderView, 'Render') as render:
            dialog.accept()
            render.assert_called_once_with()

    def test_unavailable_templates_and_settings_still_scroll_without_selection(self):
        dialog = self.dialog(snap=True)
        dialog.settingsContainer.setMinimumHeight(1600)
        dialog.show()
        self.app.processEvents()
        view = dialog.blenderView
        first_item = view.visualRect(view.model().index(0, 0)).center()
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=first_item)
        self.assertFalse(view.selectionModel().hasSelection())
        view.setFocus()
        QTest.keyClick(view, Qt.Key_Down)
        self.assertFalse(view.selectionModel().hasSelection())
        for area in (view, dialog.scrollArea):
            scrollbar = area.verticalScrollBar()
            self.assertTrue(scrollbar.isEnabled())
            self.assertGreater(scrollbar.maximum(), 0)
            scrollbar.setValue(scrollbar.maximum())
            self.assertEqual(scrollbar.value(), scrollbar.maximum())
        self.assert_disabled_editor(dialog)

    def test_cosmic_render_is_muted_and_focused_cancel_has_visible_hover(self):
        from themes.cosmic.theme import CosmicTheme
        dialog = self.dialog(snap=True)
        dialog.setStyleSheet(CosmicTheme(self.app).style_sheet)
        dialog.show()
        self.app.processEvents()
        QTest.mouseMove(dialog, QPoint(1, 1))
        self.app.processEvents()

        def background(button):
            image = button.grab().toImage()
            position = round(5 * image.devicePixelRatio())
            return image.pixelColor(position, position)

        disabled_color = background(dialog.btnRender)
        self.assertEqual(background(dialog.btnRefresh), disabled_color)
        dialog.btnRender.setEnabled(True)
        active_color = background(dialog.btnRender)
        dialog.btnRender.setEnabled(False)
        self.assertLess(disabled_color.saturation(), active_color.saturation())
        QTest.mouseMove(dialog.btnRender, dialog.btnRender.rect().center())
        self.app.processEvents()
        self.assertEqual(background(dialog.btnRender), disabled_color)

        dialog.btnCancel.setFocus()
        normal_color = background(dialog.btnCancel)
        dialog.btnCancel.clearFocus()
        self.app.processEvents()
        self.assertEqual(background(dialog.btnCancel), normal_color)
        dialog.btnCancel.setFocus()
        QTest.mouseMove(dialog.btnCancel, dialog.btnCancel.rect().center())
        self.app.processEvents()
        # Render the hover state explicitly too, independent of whether the
        # headless backend can move its pointer into this window.
        option = QStyleOptionButton()
        dialog.btnCancel.initStyleOption(option)
        option.state |= QStyle.State_MouseOver
        pixmap = QPixmap(dialog.btnCancel.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        dialog.btnCancel.style().drawControl(QStyle.CE_PushButton, option, painter, dialog.btnCancel)
        painter.end()
        self.assertNotEqual(pixmap.toImage().pixelColor(5, 5), normal_color)

        # These overrides must not reach other dialogs using the same button names.
        dialog.setObjectName('unrelatedDialog')
        dialog.setStyleSheet(CosmicTheme(self.app).style_sheet)
        self.app.processEvents()
        self.assertNotEqual(background(dialog.btnRender), disabled_color)


if __name__ == '__main__':
    unittest.main()
