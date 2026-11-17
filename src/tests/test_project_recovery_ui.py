# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.

"""Recovery stays in one dialog until an attempt opens a project or is cancelled."""
import unittest
from unittest.mock import Mock
from qt_api import QApplication, QTimer, QDialog, Qt, QTextBrowser, QTextCursor, QPushButton
from tests.qt_test_app import get_or_create_app
from windows.project_recovery import ProjectRecoveryDialog, RepairReport


class RecoveryPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))
        if not hasattr(cls.app, '_tr'):
            cls.app._tr = lambda text: text

    def dialog(self, versions=None, **callbacks):
        defaults = dict(repair=Mock(return_value=({}, ['Omit clip C1'])),
                        restore=Mock(return_value=({}, [])),
                        save=Mock(return_value='/tmp/recovered.osp'),
                        open_project=Mock(return_value=True))
        defaults.update(callbacks)
        selected_versions = versions if versions is not None else ['/backup/1794778200-broken.zip']
        return ProjectRecoveryDialog(
            None, '/tmp/broken.osp', 'Invalid JSON', selected_versions, **defaults)

    def test_two_clear_paths_with_primary_styling(self):
        dialog = self.dialog()
        QTimer.singleShot(0, dialog.reject)
        self.assertEqual(dialog.exec_(), QDialog.Rejected)
        self.assertEqual(dialog.repair_button.text(), 'Repair Project')
        self.assertEqual(dialog.restore_button.text(), 'Restore Backup')
        self.assertEqual(dialog.repair_button.property('dialogRole'), 'primary')
        self.assertEqual(dialog.restore_button.property('dialogRole'), 'primary')
        self.assertEqual(dialog.backups.count(), 1)

    def test_no_backups_is_visible_and_restore_is_disabled(self):
        dialog = self.dialog(versions=[])
        self.assertEqual(dialog.backups.currentText(), 'No backups available')
        self.assertFalse(dialog.backups.isEnabled())
        self.assertFalse(dialog.restore_button.isEnabled())
        self.assertTrue(dialog.repair_button.isEnabled())

    def test_failed_repair_stays_open_and_backup_can_be_used(self):
        dialog = self.dialog(repair=Mock(side_effect=ValueError('truncated JSON')))
        observed = {}

        def attempt():
            dialog.repair_button.click()
            observed['same'] = self.app.activeModalWidget() is dialog
            observed['repair'] = dialog.repair_button.isEnabled()
            observed['restore'] = dialog.restore_button.isEnabled()
            observed['error'] = dialog.error_label.text()
            dialog.restore_button.click()
        QTimer.singleShot(0, attempt)
        self.assertEqual(dialog.exec_(), QDialog.Accepted)
        self.assertTrue(observed['same'])
        self.assertFalse(observed['repair'])
        self.assertTrue(observed['restore'])
        self.assertIn('Repair failed', observed['error'])
        dialog.open_project.assert_called_once_with('/tmp/recovered.osp')

    def test_only_failed_backup_is_disabled_and_next_copy_is_available(self):
        versions = ['/backup/1794778200-broken.zip', '/backup/1794774600-broken.zip']
        dialog = self.dialog(versions=versions, restore=Mock(side_effect=[ValueError('bad archive'), ({}, [])]))
        observed = {}

        def attempt():
            dialog.restore_button.click()
            observed['disabled'] = not bool(dialog.backups.model().item(0).flags() & Qt.ItemIsEnabled)
            observed['selected'] = dialog.backups.currentData()
            observed['label'] = dialog.backups.itemText(0)
            observed['color'] = dialog.backups.itemData(0, Qt.ForegroundRole)
            observed['error'] = dialog.backups.itemData(0, Qt.ToolTipRole)
            observed['repair'] = dialog.repair_button.isEnabled()
            dialog.restore_button.click()
        QTimer.singleShot(0, attempt)
        self.assertEqual(dialog.exec_(), QDialog.Accepted)
        self.assertTrue(observed['disabled'])
        self.assertEqual(observed['selected'], versions[1])
        self.assertIn('failed', observed['label'])
        self.assertEqual(observed['color'].alpha(), 100)
        self.assertIn('bad archive', observed['error'])
        self.assertTrue(observed['repair'])

    def test_all_failed_backups_disable_the_closed_dropdown_too(self):
        dialog = self.dialog(versions=['/backup/1794778200-broken.zip', '/backup/1794774600-broken.zip'],
                             restore=Mock(side_effect=ValueError('bad archive')))
        observed = {}

        def attempt():
            dialog.restore_button.click()
            dialog.restore_button.click()
            observed['dropdown'] = dialog.backups.isEnabled()
            observed['restore'] = dialog.restore_button.isEnabled()
            observed['repair'] = dialog.repair_button.isEnabled()
            dialog.reject()
        QTimer.singleShot(0, attempt)
        dialog.exec_()
        self.assertFalse(observed['dropdown'])
        self.assertFalse(observed['restore'])
        self.assertTrue(observed['repair'])

    def test_write_failure_keeps_options_retryable_without_opening(self):
        dialog = self.dialog(save=Mock(side_effect=OSError('disk full')))
        observed = {}

        def attempt():
            dialog.repair_button.click()
            observed['enabled'] = dialog.repair_button.isEnabled()
            observed['error'] = dialog.error_label.text()
            dialog.reject()
        QTimer.singleShot(0, attempt)
        self.assertEqual(dialog.exec_(), QDialog.Rejected)
        self.assertTrue(observed['enabled'])
        self.assertIn('free space', observed['error'])
        dialog.open_project.assert_not_called()

    def test_repair_opens_directly_and_collects_changes(self):
        dialog = self.dialog()
        QTimer.singleShot(0, dialog.repair_button.click)
        self.assertEqual(dialog.exec_(), QDialog.Accepted)
        self.assertEqual(dialog.changes, ['Omit clip C1'])
        self.assertEqual(dialog.recovered_path, '/tmp/recovered.osp')
        dialog.save.assert_called_once_with({})
        dialog.open_project.assert_called_once_with('/tmp/recovered.osp')

    def test_repair_report_is_modeless(self):
        report = RepairReport(None, '/tmp/recovered.osp', ['Omit clip C1'])
        report.show()
        self.assertFalse(report.isModal())
        self.assertIsNone(self.app.activeModalWidget())
        report.close()

    def test_many_repair_changes_scroll_vertically_and_keep_close_visible(self):
        changes = [
            'Omit clip {} (ID CLIP-{}, position {} seconds): missing media reader.'.format(index, index, index)
            for index in range(1, 81)]
        report = RepairReport(None, '/tmp/recovered.osp', changes)
        report.show()
        self.app.processEvents()
        browser = report.findChild(QTextBrowser, 'repairChanges')
        close = next(button for button in report.findChildren(QPushButton) if button.text() == 'Close')
        self.assertGreater(browser.verticalScrollBar().maximum(), 0)
        self.assertTrue(close.isVisible())
        self.assertTrue(report.rect().contains(close.geometry()))
        self.assertLess(report.height(), 600)
        browser.moveCursor(QTextCursor.End)
        browser.ensureCursorVisible()
        self.app.processEvents()
        self.assertGreater(browser.verticalScrollBar().value(), 0)
        self.assertIn('Omitted clip 80', browser.toPlainText())
        report.close()

    def test_long_issue_text_wraps_without_horizontal_scrolling(self):
        identity = '<clip>' + 'x' * 1000
        report = RepairReport(None, '/tmp/recovered.osp', [
            'Omit clip 1 (ID {}, position 2.75 seconds): missing media reader.'.format(identity)])
        report.show()
        self.app.processEvents()
        browser = report.findChild(QTextBrowser, 'repairChanges')
        self.assertIn(identity, browser.toPlainText())
        self.assertEqual(browser.horizontalScrollBar().maximum(), 0)
        self.assertGreater(browser.verticalScrollBar().maximum(), 0)
        report.close()
