"""Shared presentation for source preview, clip preview, and split-file editing."""
from qt_api import (Qt, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
                    QSize, QSizePolicy, QDialogButtonBox, QIcon,
                    QGridLayout, QWidget, QObject, QEvent, QTimer, QSlider, QApplication)
from classes.app import get_app
from windows.preview_icons import preview_icon, preview_colors, preview_toggle_icon


def panel(parent, name):
    result = QFrame(parent)
    result.setObjectName(name)
    return result


def separator(parent):
    line = QFrame(parent)
    line.setObjectName('previewSeparator')
    line.setFixedWidth(1)
    return line


def build_preview_design(dialog):
    d = dialog
    _ = get_app()._tr
    d.setObjectName('sourcePreviewDialog')
    d.setWindowTitle(_('Preview'))
    colors = preview_colors()
    d.setStyleSheet("""
        QDialog#sourcePreviewDialog {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 %(window)s,stop:1 %(window_end)s);
            color: %(text)s;
        }
        QDialog#sourcePreviewDialog QLabel { color: %(text)s; background: transparent; }
        QFrame#previewSurface { background: black; border: 1px solid %(border)s; border-radius: 9px; }
        QFrame#stripPanel, QFrame#widgetControls {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 %(panel)s,stop:1 %(panel_end)s);
            border: 1px solid %(border)s; border-radius: 8px;
        }
        QFrame#timeField { background: %(field)s; border: 1px solid %(border)s; border-radius: 7px; }
        QDialog#sourcePreviewDialog QLineEdit { background: transparent; color: %(text)s; border: none; padding: 0; }
        QDialog#sourcePreviewDialog QLineEdit:focus { border-bottom: 1px solid %(accent)s; }
        QDialog#sourcePreviewDialog QPushButton {
            color: %(text)s; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 %(button)s,stop:1 %(button_end)s);
            border: 1px solid %(border)s; border-radius: 7px; padding: 9px 17px;
        }
        QDialog#sourcePreviewDialog QPushButton:hover { background: %(hover)s; }
        QDialog#sourcePreviewDialog QPushButton:focus { border: 1px solid %(accent)s; }
        QDialog#sourcePreviewDialog QPushButton:disabled { color: %(muted)s; background: %(panel)s; }
        QDialog#sourcePreviewDialog QToolButton { background: transparent; border: none; padding: 0; color: %(text)s; }
        QDialog#sourcePreviewDialog QToolButton:hover { background: %(hover)s; border-radius: 5px; }
        QDialog#sourcePreviewDialog QToolButton:focus { border: 1px solid %(accent)s; border-radius: 5px; }
        QSlider#previewVolume::groove:horizontal { height: 6px; border-radius: 3px; background: %(border)s; }
        QSlider#previewVolume::sub-page:horizontal { background: %(accent)s; border-radius: 3px; }
        QSlider#previewVolume::handle:horizontal { width: 16px; margin: -5px 0; border-radius: 8px; background: %(grip)s; border: none; }
    """ % colors)
    d.verticalLayout.setContentsMargins(15, 22, 15, 23 if d.range_mode == 'preview' else 14)
    d.verticalLayout.setSpacing(12)
    # Keep one expanding region: all additional height belongs to the video.
    if hasattr(d, 'videoPreview'):
        d.preview_surface = panel(d, 'previewSurface')
        surface_layout = QVBoxLayout(d.preview_surface)
        surface_layout.setContentsMargins(2, 2, 2, 2)
        d.verticalLayout.replaceWidget(d.videoPreview, d.preview_surface)
        surface_layout.addWidget(d.videoPreview)
        d.verticalLayout.setStretch(d.verticalLayout.indexOf(d.preview_surface), 1)
        d.videoPreview.setStyleSheet('background: black;')
    d.strip_panel = panel(d, 'stripPanel')
    strip_layout = QVBoxLayout(d.strip_panel)
    strip_layout.setContentsMargins(10, 10, 10, 9)
    d.verticalLayout.replaceWidget(d.sliderVideo, d.strip_panel)
    strip_layout.addWidget(d.sliderVideo)
    d.strip_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    d.sliderVideo.range_enabled = d.range_mode != 'preview'
    d.sliderVideo.reference_design = True
    d.sliderVideo._refresh_theme()
    d.timeLayout.setSpacing(7)
    d.lblVideoTime.setStyleSheet('color: %s; font-weight: bold;' % colors['accent'])
    time_font = d.font()
    time_font.setPointSizeF(time_font.pointSizeF() * 1.2)
    d.lblVideoTime.setFont(time_font)
    d.lblSourceDuration.setStyleSheet('color: %s;' % colors['muted'])
    d.horizontalLayout_3.setSpacing(15)
    for button in (d.btnRangeStart, d.btnRangeEnd):
        style_transport_button(button)
    d.volume_button = QToolButton(d)
    d.volume_button.setIcon(preview_toggle_icon('tool-preview-volume', active_when_checked=False))
    style_transport_button(d.volume_button)
    d.volume_button.setCheckable(True)
    d.volume_button.setToolTip(_('Mute preview audio'))
    d.loopLayout.setSpacing(10)
    d.loopLayout.addWidget(d.volume_button)
    d.volume_slider = QSlider(Qt.Horizontal, d)
    d.volume_slider.setObjectName('previewVolume')
    d.volume_slider.setRange(0, 100)
    d.volume_slider.setValue(100)
    d.volume_slider.setTracking(False)
    d.volume_slider.setFixedSize(80, 24)
    d.volume_slider.setAccessibleName(_('Preview volume'))
    d.volume_slider.setToolTip(_('Preview volume (applied after releasing the slider)'))
    d.loopLayout.addWidget(d.volume_slider)
    d._volume_timer = QTimer(d)
    d._volume_timer.setSingleShot(True)
    d._volume_timer.setInterval(200)
    d._volume_timer.timeout.connect(lambda: _set_muted(d, d.volume_button.isChecked()))
    d.volume_slider.valueChanged.connect(lambda _value: d._volume_timer.start())
    d.volume_button.toggled.connect(lambda muted: _set_muted(d, muted))
    d.fit_button = QToolButton(d)
    d.fit_button.setIcon(preview_icon('ai-action-upscale'))
    style_transport_button(d.fit_button)
    d.fit_button.setToolTip(_('Fit window to source aspect ratio'))
    d.fit_button.setAccessibleName(_('Fit window to source aspect ratio'))
    d.fit_button.clicked.connect(lambda: fit_source_window(d))
    d.loopLayout.addWidget(d.fit_button)
    # Replace the prototype's nested layouts with the same three field groups in each editor.
    d._old_range_items = []
    while d.rangeControlsLayout.count():
        d._old_range_items.append(d.rangeControlsLayout.takeAt(0))
    # Keep the field groups intact while allowing the action area to wrap.
    old_layout = d.rangeControlsLayout
    QWidget().setLayout(old_layout)
    d.rangeControlsLayout = QGridLayout(d.widgetControls)
    d.rangeControlsLayout.setContentsMargins(12, 10, 12, 10)
    d.rangeControlsLayout.setHorizontalSpacing(8)
    d.rangeControlsLayout.setVerticalSpacing(8)
    groups = []
    for edge, title, label, button in (
            ('in', _('Start'), d.startLabel, d.btnStart),
            ('out', _('End'), d.endLabel, d.btnEnd),
            ('duration', _('Duration'), d.durationTitle, None)):
        column = QVBoxLayout()
        column.setSpacing(5)
        label.setText(title)
        label.show()
        label.setStyleSheet('')
        column.addWidget(label)
        field = panel(d.widgetControls, 'timeField')
        field_row = QHBoxLayout(field)
        field_row.setContentsMargins(6, 3, 5, 3)
        field_row.setSpacing(6)
        if button is None:
            field_row.addWidget(d.range_duration)
            field_row.addStretch()
            d.range_duration.setStyleSheet('padding: 0;')
        else:
            button.setText('')
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setIcon(preview_icon('tool-timing'))
            button.setIconSize(QSize(22, 22))
            button.setFixedSize(23, 25)
            field_row.addWidget(button)
            edit = d.range_edits[edge]
            edit.setStyleSheet('padding: 0; border: none;')
            edit.setFixedWidth(edit.fontMetrics().horizontalAdvance('00:00:00.00')+8)
            field_row.addWidget(edit)
            field_row.addStretch()
            steps = QVBoxLayout()
            steps.setSpacing(0)
            for direction, icon_name in ((1, 'spin-up-arrow'), (-1, 'spin-down-arrow')):
                step = QToolButton(field)
                step.setAutoRaise(True)
                step.setIcon(preview_icon(icon_name))
                step.setIconSize(QSize(10, 8))
                step.setFixedSize(16, 13)
                step.setAutoRepeat(True)
                step.setAccessibleName(_('Increase %s one frame') % title if direction == 1 else _('Decrease %s one frame') % title)
                step.clicked.connect(lambda _checked=False, edge=edge, direction=direction:
                                     d.sliderVideo.move_edge(edge, (d.start_frame if edge == 'in' else d.end_frame)+direction))
                steps.addWidget(step)
            field_row.addLayout(steps)
        field.setFixedHeight(34)
        column.addWidget(field)
        groups.append(column)
    if d.range_mode in ('create', 'file'):
        column = QVBoxLayout()
        column.setSpacing(5)
        d.label.setText(_('Name'))
        d.label.show()
        d.txtName.show()
        column.addWidget(d.label)
        field = panel(d.widgetControls, 'timeField')
        row = QHBoxLayout(field)
        row.setContentsMargins(9, 3, 9, 3)
        d.txtName.setPlaceholderText(_('Optional'))
        d.txtName.setMinimumWidth(70)
        row.addWidget(d.txtName)
        field.setFixedHeight(34)
        column.addWidget(field)
        groups.append(column)
    else:
        d.txtName.hide()
        d.label.hide()
    d.btnClear.setIcon(preview_icon('tool-reset-range'))
    d.btnClear.setIconSize(QSize(23, 23))
    d.btnClear.setMinimumWidth(85)
    d.btnAddClip.setIcon(preview_icon('tool-preview-apply'))
    d.btnAddClip.setIconSize(QSize(24, 24))
    d.btnAddClip.setMinimumWidth(155)
    d.btnAddClip.setStyleSheet(
        'QPushButton { background: %(accent)s; color: %(on_accent)s;'
        ' border: 1px solid %(accent)s; border-radius: 7px; padding: 10px 20px; }'
        'QPushButton:hover { background: %(accent_hover)s; }'
        'QPushButton:disabled { background: %(panel)s; color: %(muted)s; border-color: %(border)s; }'
        'QPushButton:focus { border: 2px solid %(grip)s; }' % colors)
    d.btnAddClip.setIcon(preview_icon('tool-preview-apply', colors['on_accent']))
    d.btnAddClip.setAutoDefault(False)
    d.btnClear.setAutoDefault(False)
    action_height = max(d.btnClear.sizeHint().height(), d.btnAddClip.sizeHint().height())
    d.btnClear.setFixedHeight(action_height)
    d.btnAddClip.setFixedHeight(action_height)

    d.widgetControls.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    d.widgetControls.setMinimumWidth(1)
    d._range_layout = RangeLayout(d, groups)
    d.installEventFilter(d._range_layout)
    d._range_layout.reflow(d.size().width())
    if d.range_mode == 'clip':
        d.verticalLayout.insertSpacing(d.verticalLayout.indexOf(d.widgetControls), 7)
    d.widgetControls.setVisible(d.range_mode != 'preview')
    close = d.buttonBox.button(QDialogButtonBox.Close)
    close.setIcon(QIcon())
    close.setMinimumWidth(125)
    close.setFixedHeight(46)
    d.buttonBox.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    d.footerLayout.insertStretch(0, 1)
    d.footerLayout.setContentsMargins(0, 21 if d.range_mode == 'preview' else 3, 6, 0)
    # Leave the footer's breathing room fixed, not proportional to dialog height.
    d.footerLayout.setSpacing(12)
    d.buttonBox.hide()
    d.verticalLayout.removeItem(d.footerLayout)
    d.resize(940, 640)


def _set_muted(dialog, muted):
    dialog._volume_timer.stop()
    dialog.volume_button.setToolTip(get_app()._tr('Unmute preview audio') if muted else get_app()._tr('Mute preview audio'))
    if hasattr(dialog, 'VolumeSignal'):
        dialog.VolumeSignal.emit(0.0 if muted else dialog.volume_slider.value()/100.0)


class RangeLayout(QObject):
    """Reflow the editing controls without taking spare height from the video."""
    def __init__(self, dialog, groups):
        super().__init__(dialog)
        self.dialog = dialog
        self.groups = groups
        self.compact = None

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.reflow(event.size().width())
        return False

    def reflow(self, width):
        d = self.dialog
        grid = d.rangeControlsLayout
        margins = grid.contentsMargins()
        required = (sum(group.minimumSize().width() for group in self.groups)
                    + d.btnClear.sizeHint().width() + d.btnAddClip.sizeHint().width()
                    + grid.horizontalSpacing() * (len(self.groups)+1)
                    + margins.left() + margins.right() + 30)
        compact = width < required
        if self.compact == compact:
            return
        self.compact = compact
        d = self.dialog
        grid = d.rangeControlsLayout
        while grid.count():
            grid.takeAt(0)
        for col in range(6):
            grid.setColumnStretch(col, 0)
        for col, group in enumerate(self.groups):
            grid.addLayout(group, 0, col)
        if compact:
            grid.addWidget(d.btnClear, 1, len(self.groups)-2, Qt.AlignRight | Qt.AlignBottom)
            grid.addWidget(d.btnAddClip, 1, len(self.groups)-1, Qt.AlignRight | Qt.AlignBottom)
            grid.setColumnStretch(len(self.groups)-1, 1)
        else:
            count = len(self.groups)
            grid.addWidget(d.btnClear, 0, count, Qt.AlignBottom)
            grid.addWidget(d.btnAddClip, 0, count+1, Qt.AlignBottom)
            grid.setColumnStretch(count-1, 1)
        d.widgetControls.setFixedHeight(grid.sizeHint().height())


def fit_source_window(dialog):
    """Fit the video viewport, accounting for controls and screen limits."""
    video = getattr(dialog, 'videoPreview', None)
    if video is None:
        return
    ratio = video.aspect_ratio.ToFloat() * video.pixel_ratio.ToFloat()
    if ratio <= 0:
        return
    dialog.verticalLayout.activate()
    overhead_w = dialog.size().width() - video.size().width()
    overhead_h = dialog.size().height() - video.size().height()
    handle = dialog.windowHandle()
    screen = (handle.screen() if handle else QApplication.primaryScreen()).availableGeometry()
    width = min(video.size().width(), screen.width()-overhead_w-20)
    height = width/ratio
    if height + overhead_h > screen.height()-40:
        height = max(1, screen.height()-overhead_h-40)
        width = height*ratio
    dialog.resize(round(width+overhead_w), round(height+overhead_h))


def style_transport_button(button, play=False):
    """Flat, consistent transport targets using the active theme's colors."""
    button.setAutoRaise(True)
    button.setToolButtonStyle(Qt.ToolButtonIconOnly)
    button.setIconSize(QSize(28, 28) if play else QSize(24, 24))
    button.setFixedSize(46, 46) if play else button.setFixedSize(38, 38)
    if play:
        colors = preview_colors()
        button.setStyleSheet(
            'QToolButton { background: %(accent)s; border: none; border-radius: 23px; }'
            'QToolButton:hover { background: %(accent_hover)s; }'
            'QToolButton:focus { border: 2px solid %(grip)s; }' % colors)
        return
    button.setStyleSheet(
        'QToolButton { background: transparent; border: 1px solid transparent;'
        ' border-radius: 5px; padding: 0; }'
        'QToolButton:hover { background: palette(alternate-base); }'
        'QToolButton:focus { border: 1px solid palette(highlight); }')
