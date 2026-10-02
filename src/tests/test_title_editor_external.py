"""Cross-platform SVG saves and nonblocking external-editor handoffs."""
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from defusedxml import minidom

from qt_api import QApplication, QDialog, QEventLoop, QTimer, QLineEdit
from tests.qt_test_app import get_or_create_app, ensure_app_state
from classes.svg_watcher import SvgWatcher
from tests.test_project_data import DummySettings


class ExternalTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))
        ensure_app_state(cls.app, DummySettings)
        from windows.title_editor import TitleEditor
        cls.editor_class = TitleEditor

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='title editor ü ')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'title with spaces.svg'
        self.path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><text>old</text></svg>')
        self.watcher = SvgWatcher()
        self.watcher.watch(str(self.path))
        self.addCleanup(self.watcher.stop)
        self.changed = Mock()
        self.watcher.changed.connect(self.changed)

    def settle(self):
        self.watcher.check()
        self.watcher.check()

    def wait_for(self, condition):
        deadline = time.monotonic() + 4
        while not condition() and time.monotonic() < deadline:
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec_()
        self.assertTrue(condition())

    def dialog(self):
        dialog = self.editor_class.__new__(self.editor_class)
        QDialog.__init__(dialog)
        self.addCleanup(dialog.deleteLater)
        dialog.app = self.app
        dialog.env = dict(os.environ)
        dialog.filename = str(self.path)
        dialog.xmldoc = minidom.parse(str(self.path))
        dialog.is_thread_busy = False
        dialog.update_timer = QTimer(dialog)
        dialog.preview_timer = QTimer(dialog)
        dialog.svg_watcher = self.watcher
        dialog.finished.connect(self.watcher.stop)
        dialog.editor_process = None
        dialog.txtFileName = QLineEdit('My chosen name', dialog)
        dialog.load_svg_template = Mock()
        dialog.display_svg = Mock()
        self.watcher.changed.connect(dialog._external_svg_changed)
        dialog.show()
        self.addCleanup(dialog.hide)
        return dialog

    def test_closing_dialog_cancels_deferred_editor_launch(self):
        dialog = self.dialog()
        dialog.is_thread_busy = True
        with patch('windows.title_editor.QProcess') as process_class, \
                patch('windows.title_editor.open_file_with_application') as chooser:
            dialog.btnAdvanced_clicked()
            dialog.reject()
            dialog.is_thread_busy = False
            loop = QEventLoop()
            QTimer.singleShot(100, loop.quit)
            loop.exec_()
            process_class.assert_not_called()
            chooser.assert_not_called()
            self.assertFalse(self.watcher.timer.isActive())

    def test_real_title_controls_reload_without_rewriting_external_svg(self):
        from qt_api import QWidget
        from classes import info
        template = '<svg xmlns="http://www.w3.org/2000/svg"><text><tspan>original</tspan></text></svg>'
        self.path.write_text(template)
        with patch.object(self.app, 'project', Mock(), create=True), \
                patch.object(info, 'TITLE_PATH', self.tmp.name), \
                patch('windows.title_editor.TitlesListView', side_effect=lambda **kwargs: QWidget(kwargs['parent'])), \
                patch('windows.title_editor.ui_util.init_ui'), \
                patch('windows.title_editor.track_metric_screen'), \
                patch.object(self.editor_class, 'display_svg'):
            dialog = self.editor_class(edit_file_path=str(self.path))
            self.addCleanup(dialog.deleteLater)
            dialog.svg_watcher.watch(dialog.filename)
            external = '<svg xmlns="http://www.w3.org/2000/svg"><text style="font-family:serif"><tspan>edited externally</tspan></text></svg>'
            Path(dialog.filename).write_text(external)
            dialog.svg_watcher.check(force=True)
            self.assertEqual(Path(dialog.filename).read_text(), external)
            self.assertEqual(dialog.tspan_nodes[0].firstChild.data, 'edited externally')
            self.assertEqual(dialog.txtFileName.text(), self.path.name)
            self.assertFalse(dialog.txtFileName.isEnabled())
            fields = dialog.settingsContainer.findChildren(QLineEdit)
            self.assertIn('edited externally', [field.text() for field in fields])
            scratch = Path(dialog.filename)
            dialog.reject()
            self.assertFalse(scratch.exists())
            self.assertEqual(self.path.read_text(), template)

    def test_own_writes_do_not_rebuild_controls(self):
        dialog = self.dialog()
        self.assertTrue(dialog.writeToFile(minidom.parseString('<svg><text>internal</text></svg>')))
        self.settle()
        self.changed.assert_not_called()

    def test_external_save_reloads_controls_and_preview_without_writing(self):
        dialog = self.dialog()
        dialog.writeToFile = Mock()
        dialog.update_timer.start(1000)
        self.path.write_text('<svg><text>external</text></svg>')
        self.settle()
        dialog.load_svg_template.assert_called_once()
        self.assertEqual(dialog.load_svg_template.call_args.kwargs['filename_field'], 'My chosen name')
        dialog.display_svg.assert_called_once()
        dialog.writeToFile.assert_not_called()
        self.assertFalse(dialog.update_timer.isActive())

    def test_accept_includes_external_save_before_next_watcher_tick(self):
        dialog = self.dialog()
        dialog.edit_file_path = str(self.path.with_name('accepted.svg'))
        dialog.duplicate = False
        dialog.load_svg_template.side_effect = lambda **kwargs: setattr(dialog, 'xmldoc', kwargs['document'])
        self.path.write_text('<svg><text>just saved</text></svg>')
        dialog.accept()
        self.assertIn('just saved', Path(dialog.edit_file_path).read_text())
        self.assertFalse(self.watcher.timer.isActive())

    def test_resizing_preview_does_not_schedule_a_file_write(self):
        from qt_api import QLabel, QEvent
        dialog = self.dialog()
        dialog.lblPreviewLabel = QLabel(dialog)
        dialog.eventFilter(dialog.lblPreviewLabel, QEvent(QEvent.Resize))
        self.assertTrue(dialog.preview_timer.isActive())
        self.assertFalse(dialog.update_timer.isActive())

    def test_launch_commands_on_all_platforms_and_snap(self):
        dialog = self.dialog()
        settings = SimpleNamespace(get=lambda key: '/path with spaces/Inkscape')
        for platform in ('linux', 'win32', 'darwin'):
            for snap in (False, True):
                with self.subTest(platform=platform, snap=snap), \
                        patch('windows.title_editor.sys.platform', platform), \
                        patch('windows.title_editor.is_snap', return_value=snap), \
                        patch.object(self.app, 'get_settings', return_value=settings), \
                        patch('windows.title_editor.QProcess') as process_class, \
                        patch('windows.title_editor.open_file_with_application', return_value=True) as chooser:
                    dialog.editor_process = None
                    dialog.btnAdvanced_clicked()
                    if snap:
                        chooser.assert_called_once_with(dialog, str(self.path))
                        process_class.assert_not_called()
                    else:
                        process_class.return_value.start.assert_called_once_with(
                            '/path with spaces/Inkscape', [str(self.path)])
                        chooser.assert_not_called()
                    process_class.return_value.waitForFinished.assert_not_called()
                    self.assertTrue(self.watcher.timer.isActive())
        dialog.editor_process = None

    def test_snap_cancel_is_quiet_and_portal_failure_is_reported(self):
        dialog = self.dialog()
        for result in (True, False, None):
            with self.subTest(result=result), \
                    patch('windows.title_editor.is_snap', return_value=True), \
                    patch('windows.title_editor.open_file_with_application', return_value=result), \
                    patch('windows.title_editor.QProcess') as process_class, \
                    patch.object(dialog, '_editor_error') as error:
                dialog.btnAdvanced_clicked()
                self.assertEqual(error.call_count, 1 if result is None else 0)
                process_class.assert_not_called()

    def test_real_process_quick_success_then_later_save(self):
        dialog = self.dialog()
        # A Python script in place of the SVG is sufficient for a real process
        # handoff; the launcher does not inspect the file type.
        dialog.writeToFile = Mock(return_value=True)
        self.path.write_text('pass\n')
        with patch.object(self.app, 'get_settings', return_value=SimpleNamespace(get=lambda key: sys.executable)), \
                patch('windows.title_editor.is_snap', return_value=False), \
                patch.object(dialog, '_editor_error') as error:
            dialog.btnAdvanced_clicked()
            self.wait_for(lambda: dialog.editor_process is None)
            error.assert_not_called()
            self.path.write_text('<svg><text>saved after handoff</text></svg>')
            self.wait_for(lambda: dialog.display_svg.called)
        self.assertEqual(self.path.read_text(), '<svg><text>saved after handoff</text></svg>')

    def test_real_process_failure_is_reported(self):
        dialog = self.dialog()
        dialog.writeToFile = Mock(return_value=True)
        self.path.write_text('raise SystemExit(3)\n')
        with patch.object(self.app, 'get_settings', return_value=SimpleNamespace(get=lambda key: sys.executable)), \
                patch('windows.title_editor.is_snap', return_value=False), \
                patch.object(dialog, '_editor_error') as error:
            dialog.btnAdvanced_clicked()
            self.wait_for(lambda: dialog.editor_process is None)
            error.assert_called_once()

    def test_missing_editor_can_be_retried(self):
        dialog = self.dialog()
        with patch.object(self.app, 'get_settings', return_value=SimpleNamespace(get=lambda key: str(self.path / 'missing'))), \
                patch('windows.title_editor.is_snap', return_value=False), \
                patch.object(dialog, '_editor_error') as error:
            for count in (1, 2):
                dialog.btnAdvanced_clicked()
                self.wait_for(lambda: dialog.editor_process is None)
                self.assertEqual(error.call_count, count)

    def test_close_stops_watching_but_does_not_own_external_process(self):
        dialog = self.dialog()
        with patch.object(self.app, 'get_settings', return_value=SimpleNamespace(get=lambda key: sys.executable)), \
                patch('windows.title_editor.is_snap', return_value=False), \
                patch('windows.title_editor.QProcess') as process_class:
            dialog.btnAdvanced_clicked()
            process_class.assert_called_once_with(self.app)
            dialog.reject()
            self.assertFalse(self.watcher.timer.isActive())
            process_class.return_value.kill.assert_not_called()
            process_class.return_value.terminate.assert_not_called()
        dialog.editor_process = None


class SnapCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))
        ensure_app_state(cls.app, DummySettings)

    def test_snap_detection_does_not_include_other_packages(self):
        from classes.distribution import is_snap
        for env, expected in (({}, False), ({'SNAP': ''}, False),
                              ({'APPIMAGE': '/app'}, False), ({'FLATPAK_ID': 'org.openshot'}, False),
                              ({'SNAP': '/snap/openshot/current'}, True)):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                self.assertEqual(is_snap(), expected)

    def test_snap_animated_title_opens_the_dialog_without_a_message_box(self):
        from windows.main_window import MainWindow
        with patch.dict(os.environ, {'SNAP': '/snap/openshot/current'}), \
                patch('windows.main_window.QMessageBox.information') as message, \
                patch('windows.animated_title.AnimatedTitle') as animated:
            MainWindow.actionAnimatedTitle_trigger(Mock())
            animated.return_value.exec_.assert_called_once()
            message.assert_not_called()

    def test_non_snap_animated_titles_are_unchanged(self):
        from windows.main_window import MainWindow
        with patch.dict(os.environ, {}, clear=True), \
                patch('windows.main_window.QMessageBox.information') as message, \
                patch('windows.animated_title.AnimatedTitle') as animated:
            MainWindow.actionAnimatedTitle_trigger(Mock())
            animated.return_value.exec_.assert_called_once()
            message.assert_not_called()

    def test_preferences_show_explanations_only_in_snap_without_changing_paths(self):
        from qt_api import QTabWidget, QLabel, QPushButton, QVBoxLayout
        from windows.preferences import Preferences
        from windows.preference_switch import PreferenceSwitch
        from themes.cosmic.theme import CosmicTheme
        for snap in (False, True):
            with self.subTest(snap=snap), patch('windows.preferences.is_snap', return_value=snap):
                dialog = Preferences.__new__(Preferences)
                QDialog.__init__(dialog)
                self.addCleanup(dialog.deleteLater)
                dialog.s = Mock()
                dialog.settings_data = [
                    dict(category='General', type='browse', setting=key, title=title, value='/custom/tool')
                    for key, title in (('blender_command', 'Blender Command (path)'),
                                       ('title_editor', 'Advanced Title Editor (path)'))
                ]
                dialog.settings_data.insert(0, dict(
                    category='General', type='dropdown', setting='example-choice',
                    title='Example choice', value='default',
                    values=[dict(name='Default', value='default')]))
                dialog.settings_data.append(dict(category='General', type='bool',
                    setting='example-toggle', title='Example toggle', value=True))
                dialog.tabCategories = QTabWidget(dialog)
                QVBoxLayout(dialog).addWidget(dialog.tabCategories)
                dialog.setStyleSheet(CosmicTheme(self.app).style_sheet)
                dialog.custom_order = ['General']
                dialog.category_tabs = {}
                dialog.category_names = {}
                dialog.category_sort = {}
                dialog.visible_category_names = {}
                dialog._apply_tab_order = Mock()
                dialog.Populate()
                dialog.resize(800, 300)
                dialog.show()
                self.app.processEvents()
                for key in ('blender_command', 'title_editor'):
                    widget = dialog.setting_widgets[key]
                    self.assertIsInstance(widget, QLabel if snap else QLineEdit)
                    if snap:
                        self.assertFalse(widget.wordWrap())
                        self.assertFalse(widget.isEnabled())
                        self.assertEqual(widget.height(), dialog.setting_widgets['example-choice'].height())
                    else:
                        self.assertEqual(widget.text(), '/custom/tool')
                labels = dialog.tabCategories.findChildren(QLabel)
                for label in labels:
                    is_value = label in dialog.setting_widgets.values()
                    self.assertEqual(label.isEnabled(), not (snap and is_value))
                buttons = dialog.tabCategories.findChildren(QPushButton)
                self.assertEqual(len(buttons), 0 if snap else 2)
                dialog.s.set.assert_not_called()
                toggle = dialog.setting_widgets['example-toggle']
                self.assertIsInstance(toggle, PreferenceSwitch)
                self.assertEqual(toggle.accessibleName(), 'Example toggle')
                self.assertTrue(toggle.isChecked())
                toggle.setChecked(False)
                dialog.s.set.assert_called_once_with('example-toggle', False)
                dialog.hide()


if __name__ == '__main__':
    unittest.main()
