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

"""Repair or restore in one dialog; report changes without blocking editing."""
import os
import html
import re
from datetime import datetime

from qt_api import (
    Qt, QDialog, QPushButton, QLabel, QComboBox, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QApplication, QEventLoop, QCursor, QFrame, QPalette, QColor, QTextBrowser, QTextEdit, QTextOption,
)
from classes.app import get_app


def recovery_style(widget):
    """Use the active theme's text, link, and disabled colors."""
    palette = widget.palette()
    text = palette.color(QPalette.Active, QPalette.WindowText)
    light = text.lightness() < 128
    muted = QColor(text)
    muted.setAlpha(175)
    card = QColor(text)
    card.setAlpha(8 if light else 9)
    disabled = QColor(text)
    disabled.setAlpha(100)
    border = QColor(text)
    border.setAlpha(30)
    warning = QColor('#95610c' if light else '#ebba70')
    warning_fill = QColor(warning)
    warning_fill.setAlpha(18)

    def rgba(color):
        return 'rgba({}, {}, {}, {})'.format(color.red(), color.green(), color.blue(), color.alpha())
    style = """
QDialog#projectRecoveryDialog QLabel#recoveryHeading {
    font-size: 18px; font-weight: 600; background: transparent;
}
QDialog#projectRecoveryDialog QLabel#recoveryFilename {
    color: MUTED; font-size: 13px; background: transparent;
}
QDialog#projectRecoveryDialog QFrame#recoveryOption {
    background: CARD; border: 1px solid BORDER; border-radius: 8px;
}
QDialog#projectRecoveryDialog QFrame#recoveryOption QLabel {
    background: transparent; border: none;
}
QDialog#projectRecoveryDialog QLabel#recoveryOptionTitle {
    font-size: 13px; font-weight: 600;
}
QDialog#projectRecoveryDialog QLabel#recoveryOptionDescription {
    color: MUTED; font-size: 12px;
}
QDialog#projectRecoveryDialog QLabel#recoveryError {
    color: WARNING; background: WARNING_FILL; border: 1px solid WARNING_BORDER;
    border-radius: 6px; padding: 10px 12px; font-size: 13px;
}
QDialog#projectRecoveryDialog QPushButton {
    font-size: 13px;
}
QDialog#projectRecoveryDialog QPushButton[dialogRole="primary"] {
    padding: 8px 14px;
}
QDialog#projectRecoveryDialog QPushButton#repairAction,
QDialog#projectRecoveryDialog QPushButton#restoreAction {
    min-width: 116px; max-width: 116px;
}
QDialog#projectRecoveryDialog QPushButton[dialogRole="link"] {
    color: palette(link); background: transparent; border: none;
    text-decoration: underline; padding: 8px 0; min-width: 0;
}
QDialog#projectRecoveryDialog QPushButton[dialogRole="primary"]:disabled {
    color: palette(disabled, button-text); background: palette(button);
    border: 1px solid BORDER;
}
QDialog#projectRecoveryDialog QPushButton[dialogRole="cancel"] {
    color: MUTED; background: transparent; border: none;
    padding: 8px 2px; min-width: 0;
}
QDialog#projectRecoveryDialog QPushButton[dialogRole="cancel"]:hover {
    color: palette(text);
}
QDialog#projectRecoveryDialog QComboBox {
    font-size: 12px; padding: 8px 10px; min-height: 18px;
}
QDialog#projectRecoveryDialog QComboBox:disabled {
    color: DISABLED; background: CARD; border: 1px solid BORDER;
}
QDialog#projectRecoveryDialog QComboBox::item:disabled,
QDialog#projectRecoveryDialog QComboBox::item:disabled:selected,
QDialog#projectRecoveryDialog QComboBox QAbstractItemView::item:disabled {
    color: DISABLED; background: transparent;
}
QDialog#projectRecoveryDialog QPlainTextEdit#recoveryDetails,
QDialog#projectRecoveryDialog QTextBrowser#repairChanges {
    background: CARD; border: 1px solid BORDER; border-radius: 6px;
    padding: 10px; font-size: 12px;
}
"""
    colors = {
        'WARNING_BORDER': rgba(QColor(warning.red(), warning.green(), warning.blue(), 60)),
        'WARNING_FILL': rgba(warning_fill),
        'WARNING': warning.name(),
        'MUTED': rgba(muted),
        'CARD': rgba(card),
        'BORDER': rgba(border),
        'DISABLED': rgba(disabled),
    }
    for token, color in colors.items():
        style = style.replace(token, color)
    return style


def version_label(path):
    """Use the same relative date and timestamp as File > Recovery."""
    try:
        timestamp = int(os.path.basename(path).split("-", 1)[0])
        window = getattr(get_app(), 'window', None)
        relative = getattr(window, 'time_ago_string', None)
        date = datetime.fromtimestamp(timestamp).strftime('%b %d, %H:%M')
        return '{} ({})'.format(relative(timestamp), date) if callable(relative) else date
    except (ValueError, OverflowError, OSError):
        return os.path.basename(path)


class ProjectRecoveryDialog(QDialog):
    """Keep failed attempts and remaining choices in the same visible dialog."""
    def __init__(self, parent, file_path, error, versions, repair, restore, save, open_project):
        super().__init__(parent)
        _ = get_app()._tr
        self.setObjectName('projectRecoveryDialog')
        self.setWindowTitle(_('Recover Project'))
        self.setMinimumWidth(620)
        self.setStyleSheet(recovery_style(self))
        self.repair = repair
        self.restore = restore
        self.save = save
        self.open_project = open_project
        self.repair_failed = False
        self.failed_backups = set()
        self.changes = []
        self.recovered_path = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(18)
        header = QVBoxLayout()
        header.setSpacing(7)
        heading = QLabel(_('Project could not be opened'), self)
        heading.setObjectName('recoveryHeading')
        header.addWidget(heading)
        filename = QLabel(os.path.basename(file_path), self)
        filename.setObjectName('recoveryFilename')
        filename.setTextFormat(Qt.PlainText)
        filename.setTextInteractionFlags(Qt.TextSelectableByMouse)
        filename.setWordWrap(True)
        header.addWidget(filename)
        layout.addLayout(header)
        self.error_label = QLabel(self)
        self.error_label.setObjectName('recoveryError')
        self.error_label.setTextFormat(Qt.PlainText)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        choices = QVBoxLayout()
        choices.setSpacing(12)
        layout.addLayout(choices)

        repair_card = QFrame(self)
        repair_card.setObjectName('recoveryOption')
        repair_row = QHBoxLayout(repair_card)
        repair_row.setContentsMargins(16, 16, 16, 16)
        repair_row.setSpacing(20)
        repair_description = QVBoxLayout()
        repair_description.setSpacing(7)
        title = QLabel(_('Repair the project file'), repair_card)
        title.setObjectName('recoveryOptionTitle')
        repair_description.addWidget(title)
        description = QLabel(_('Check the file for repairable damage.'), repair_card)
        description.setObjectName('recoveryOptionDescription')
        description.setWordWrap(True)
        repair_description.addWidget(description)
        repair_row.addLayout(repair_description, 1)
        self.repair_button = QPushButton(_('Repair Project'), repair_card)
        self.repair_button.setObjectName('repairAction')
        self.repair_button.setProperty('dialogRole', 'primary')
        self.repair_button.setDefault(True)
        self.repair_button.setFixedWidth(148)
        self.repair_button.clicked.connect(lambda: self.attempt('repair'))
        repair_row.addWidget(self.repair_button)
        choices.addWidget(repair_card)

        backup_card = QFrame(self)
        backup_card.setObjectName('recoveryOption')
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(16, 16, 16, 16)
        backup_layout.setSpacing(10)
        title = QLabel(_('Restore an earlier save'), backup_card)
        title.setObjectName('recoveryOptionTitle')
        backup_layout.addWidget(title)
        backup_row = QHBoxLayout()
        backup_row.setSpacing(20)
        self.backups = QComboBox(backup_card)
        self.backups.setAccessibleName(_('Recovery version'))
        for path in versions:
            self.backups.addItem(version_label(path), path)
        if not versions:
            self.backups.addItem(_('No backups available'), None)
            self.backups.setEnabled(False)
        backup_row.addWidget(self.backups, 1)
        self.restore_button = QPushButton(_('Restore Backup'), backup_card)
        self.restore_button.setObjectName('restoreAction')
        self.restore_button.setProperty('dialogRole', 'primary')
        self.restore_button.setAutoDefault(False)
        self.restore_button.setFixedWidth(148)
        self.restore_button.setEnabled(bool(versions))
        self.restore_button.clicked.connect(lambda: self.attempt('backup'))
        backup_row.addWidget(self.restore_button)
        backup_layout.addLayout(backup_row)
        choices.addWidget(backup_card)
        self.details = QPlainTextEdit(str(error), self)
        self.details.setObjectName('recoveryDetails')
        self.details.setReadOnly(True)
        self.details.setFixedHeight(150)
        self.details.hide()
        layout.addWidget(self.details)
        actions = QHBoxLayout()
        self.expand = QPushButton(_('Technical details'), self)
        self.expand.setProperty('dialogRole', 'link')
        self.expand.setAutoDefault(False)
        self.expand.setCursor(Qt.PointingHandCursor)
        self.expand.clicked.connect(self.toggle_details)
        actions.addWidget(self.expand)
        actions.addStretch()
        self.cancel_button = QPushButton(_('Cancel'), self)
        self.cancel_button.setProperty('dialogRole', 'cancel')
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.backups.currentIndexChanged.connect(self.refresh_actions)

    def toggle_details(self):
        _ = get_app()._tr
        visible = not self.details.isVisible()
        self.details.setVisible(visible)
        self.expand.setText(_('Hide details') if visible else _('Technical details'))
        self.adjustSize()

    def refresh_actions(self):
        self.repair_button.setEnabled(not self.repair_failed)
        path = self.backups.currentData()
        self.backups.setEnabled(any(
            self.backups.itemData(index) is not None and self.backups.itemData(index) not in self.failed_backups
            for index in range(self.backups.count())))
        self.restore_button.setEnabled(path is not None and path not in self.failed_backups)
        self.repair_button.setDefault(not self.repair_failed)
        self.restore_button.setDefault(self.repair_failed and self.restore_button.isEnabled())

    def record_failure(self, action, path, error):
        _ = get_app()._tr
        if action == 'repair':
            self.repair_failed = True
        else:
            self.failed_backups.add(path)
            item = self.backups.model().item(self.backups.currentIndex())
            item.setEnabled(False)
            item.setText(_('%s — failed') % version_label(path))
            item.setToolTip(str(error))
            # Explicit model color also covers popup styles that ignore :disabled.
            disabled = self.palette().color(QPalette.Active, QPalette.WindowText)
            disabled.setAlpha(100)
            item.setData(disabled, Qt.ForegroundRole)
            for index in range(self.backups.count()):
                if self.backups.itemData(index) not in self.failed_backups:
                    self.backups.setCurrentIndex(index)
                    break
        self.refresh_actions()
        if self.restore_button.isEnabled():
            message = (_('Repair failed. Try a backup.') if action == 'repair'
                       else _('That backup failed. Try another backup.'))
        elif not self.repair_failed:
            message = _('That backup failed. You can try repairing the project.')
        else:
            message = _('No recovery options remain. See Details for the errors.')
        self.show_error(message, error)

    def show_error(self, message, error):
        self.error_label.setText(message)
        self.error_label.show()
        previous = self.details.toPlainText()
        self.details.setPlainText(previous + '\n\n' + str(error))
        self.adjustSize()

    def attempt(self, action):
        _ = get_app()._tr
        path = self.backups.currentData() if action == 'backup' else None
        self.repair_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.backups.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        try:
            try:
                data, changes = self.repair() if action == 'repair' else self.restore(path)
            except Exception as error:
                self.record_failure(action, path, error)
                return
            try:
                destination = self.save(data)
            except Exception as error:
                message = _('Could not save the recovery copy. Check free space and folder permissions, then retry.')
                self.show_error(message, error)
                return
            try:
                opened = self.open_project(destination)
            except Exception as error:
                self.record_failure(action, path, error)
                return
            if not opened:
                self.show_error(_('Opening was cancelled. You can retry or cancel recovery.'), destination)
                return
            self.changes = changes
            self.recovered_path = destination
            self.accept()
        finally:
            QApplication.restoreOverrideCursor()
            self.refresh_actions()


class RepairReport(QDialog):
    """A modeless list of actual changes; closing it leaves the project open."""
    def __init__(self, parent, file_path, changes):
        super().__init__(parent)
        _ = get_app()._tr
        self.setObjectName('projectRecoveryDialog')
        self.setWindowTitle(_('Repair Report'))
        self.setMinimumWidth(560)
        self.setStyleSheet(recovery_style(self))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        heading = QLabel(_('Repair changes'), self)
        heading.setObjectName('recoveryHeading')
        title_row = QHBoxLayout()
        title_row.addWidget(heading, 1)
        count = QLabel(_('1 change') if len(changes) == 1 else _('%s changes') % len(changes), self)
        count.setObjectName('recoveryFilename')
        title_row.addWidget(count)
        layout.addLayout(title_row)
        filename = QLabel(os.path.basename(file_path), self)
        filename.setObjectName('recoveryFilename')
        filename.setTextFormat(Qt.PlainText)
        filename.setWordWrap(True)
        layout.addWidget(filename)
        report = QTextBrowser(self)
        report.setObjectName('repairChanges')
        report.setOpenLinks(False)
        report.setReadOnly(True)
        report.setMinimumHeight(172)
        report.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        report.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        report.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        report.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        rows = []
        for change in changes:
            match = re.fullmatch(r'Omit(?:ted)? clip (\d+) \(ID (.*), position (.*?) seconds\): (.*)\.', change)
            if match:
                number, identity, position, reason = match.groups()
                title = _('Omitted clip %s') % number
                reason = {
                    'missing or invalid start': _('Missing or invalid start time'),
                    'missing or invalid end': _('Missing or invalid end time'),
                    'missing or invalid position': _('Missing or invalid timeline position'),
                    'missing media reader': _('Incomplete media information'),
                    'invalid source range': _('Invalid trim range'),
                    'invalid effects collection': _('Invalid effect data'),
                }.get(reason, reason)
                detail = '{} s · {}\n{}'.format(position, identity, reason)
            else:
                title, detail = change, ''
            rows.append('<p style="margin:0 0 14px"><b>{}</b><br>{}</p>'.format(
                html.escape(title), html.escape(detail).replace('\n', '<br>')))
        report.setHtml(''.join(rows))
        layout.addWidget(report, 1)
        close = QPushButton(_('Close'), self)
        close.setProperty('dialogRole', 'primary')
        close.clicked.connect(self.accept)
        layout.addWidget(close, 0, Qt.AlignRight)
        self.resize(600, 380)
