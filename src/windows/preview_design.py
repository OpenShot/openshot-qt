"""Shared presentation for source preview, clip preview, and split-file editing."""
from qt_api import (Qt, QFrame, QVBoxLayout, QHBoxLayout, QToolButton,
                    QSize, QSizePolicy, QDialogButtonBox, QIcon,
                    QGridLayout, QWidget, QObject, QEvent, QTimer, QSlider, QApplication, QStyle, QtWidgets)
from classes.app import get_app
from windows.preview_icons import preview_icon, preview_colors, preview_toggle_icon


class PreviewVolumeSlider(QSlider):
    """Jump to a clicked volume while retaining normal handle dragging."""
    def mousePressEvent(self, event):
        option = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(option)
        controls = getattr(QStyle, 'ComplexControl', QStyle)
        subcontrols = getattr(QStyle, 'SubControl', QStyle)
        handle = self.style().subControlRect(
            controls.CC_Slider, option, subcontrols.SC_SliderHandle, self)
        if event.button() == Qt.LeftButton and not handle.contains(event.pos()):
            groove = self.style().subControlRect(
                controls.CC_Slider, option, subcontrols.SC_SliderGroove, self)
            span = max(1, groove.width() - handle.width())
            position = event.pos().x() - groove.x() - handle.width() // 2
            self.setValue(QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), position, span, option.upsideDown))
        super().mousePressEvent(event)


def _saved_preview_volume():
    settings = get_app().project.get('settings') or {}
    try:
        return max(0, min(100, int(settings.get('preview_volume', 100))))
    except (TypeError, ValueError, OverflowError):
        return 100


def _save_preview_volume(dialog, value):
    app = get_app()
    settings = app.project.get('settings') or {}
    if settings.get('preview_volume', 100) != value:
        settings['preview_volume'] = value
        app.updates.update_untracked(['settings'], settings)
    dialog._volume_timer.start()


def source_preview_title(mode, name, _):
    """Keep the mode visible and long source names recognizable."""
    title = {
        'preview': _('Preview File'),
        'create': _('Split File'),
        'file': _('Preview Split File'),
        'clip': _('Preview Clip'),
    }[mode]
    name = ' '.join(str(name or '').split())
    if len(name) > 56:
        name = name[:35] + '…' + name[-20:]
    return '{}: {}'.format(title, name) if name else title


class PreviewWindowState(QObject):
    """Remember source-dialog size and maximization in the current project."""
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.save)
        settings = get_app().project.get('settings') or {}
        state = settings.get('preview_window') or {}
        if isinstance(state, dict):
            try:
                width, height = int(state['width']), int(state['height'])
                if width > 0 and height > 0:
                    handle = dialog.windowHandle()
                    screen = handle.screen() if handle else QApplication.primaryScreen()
                    if screen:
                        available = screen.availableGeometry()
                        width = min(width, available.width())
                        height = min(height, available.height())
                    dialog.resize(width, height)
                    if state.get('maximized') is True:
                        dialog.setWindowState(dialog.windowState() | Qt.WindowMaximized)
            except (KeyError, TypeError, ValueError, OverflowError):
                pass
        dialog.installEventFilter(self)

    def save(self):
        self.timer.stop()
        dialog = self.dialog
        if dialog.isMinimized():
            return
        size = dialog.normalGeometry().size() if dialog.isMaximized() else dialog.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        state = dict(width=size.width(), height=size.height(), maximized=dialog.isMaximized())
        app = get_app()
        settings = dict(app.project.get('settings') or {})
        if settings.get('preview_window') != state:
            settings['preview_window'] = state
            app.updates.update_untracked(['settings'], settings)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.WindowStateChange) and watched.isVisible():
            self.timer.start()
        elif event.type() == QEvent.Hide:
            self.save()
        return False


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
    d.setWindowTitle(source_preview_title(d.range_mode, '', _))
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
        QFrame#timeField { background: transparent; border: none; }
        QFrame#rangeTimeField {
            background: %(field)s; border: 1px solid %(border)s; border-radius: 7px;
        }
        QFrame#rangeTimeField QLineEdit { background: transparent; }
        QFrame#rangeTimeField QLineEdit:!focus { border: 1px solid transparent; }
        QDialog#sourcePreviewDialog QPushButton { padding: 10px 20px; }
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
    d.volume_button.setIcon(preview_toggle_icon('tool-preview-volume', active_when_checked=False,
                                                         checked_name='tool-preview-muted'))
    style_transport_button(d.volume_button)
    d.volume_button.setCheckable(True)
    d.volume_button.setToolTip(_('Mute preview audio'))
    d.loopLayout.setSpacing(10)
    d.loopLayout.addWidget(d.volume_button)
    d.volume_slider = PreviewVolumeSlider(Qt.Horizontal, d)
    d.volume_slider.setObjectName('previewVolume')
    d.volume_slider.setRange(0, 100)
    d.volume_slider.setValue(_saved_preview_volume())
    d.volume_slider.setTracking(False)
    d.volume_slider.setFixedSize(80, 24)
    d.volume_slider.setAccessibleName(_('Preview volume'))
    d.volume_slider.setToolTip(_('Preview volume (applied after releasing the slider)'))
    d.loopLayout.addWidget(d.volume_slider)
    d._volume_timer = QTimer(d)
    d._volume_timer.setSingleShot(True)
    d._volume_timer.setInterval(200)
    d._volume_timer.timeout.connect(lambda: _set_muted(d, d.volume_button.isChecked()))
    d.volume_slider.valueChanged.connect(lambda value: _save_preview_volume(d, value))
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
        field = panel(d.widgetControls, 'rangeTimeField')
        field_row = QHBoxLayout(field)
        field_row.setContentsMargins(6, 3, 5, 3)
        field_row.setSpacing(6)
        if button is None:
            field_row.addWidget(d.range_duration)
            field_row.addStretch()
            d.range_duration.setFixedWidth(d.range_duration.fontMetrics().horizontalAdvance('00:00:00.00') + 24)
        else:
            button.setText('')
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setIcon(preview_icon('tool-timing'))
            button.setIconSize(QSize(22, 22))
            button.setFixedSize(23, 25)
            field_row.addWidget(button)
            edit = d.range_edits[edge]
            edit.setFixedWidth(edit.fontMetrics().horizontalAdvance('00:00:00.00')+24)
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
        field.setFixedHeight(38)
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
        row.setContentsMargins(0, 0, 0, 0)
        d.txtName.setPlaceholderText(_('Optional'))
        d.txtName.setMinimumWidth(70)
        d.txtName.setFixedHeight(38)
        row.addWidget(d.txtName)
        field.setFixedHeight(38)
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
    d.btnAddClip.setProperty('dialogRole', 'primary')
    d.btnAddClip.style().unpolish(d.btnAddClip)
    d.btnAddClip.style().polish(d.btnAddClip)
    d.btnAddClip.setIcon(preview_icon('tool-preview-apply', '#ffffff'))
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
    d.resize(650, 400)
    d._preview_window_state = PreviewWindowState(d)


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
    """Keep generous transport targets while the theme draws their states."""
    button.setAutoRaise(True)
    button.setToolButtonStyle(Qt.ToolButtonIconOnly)
    button.setIconSize(QSize(28, 28) if play else QSize(24, 24))
    size = 46 if play else 38
    button.setFixedSize(size, size)
    button.setStyleSheet('')
    if play:
        window = getattr(get_app(), 'window', None)
        toolbar = getattr(window, 'videoToolbar', None)
        action = getattr(window, 'actionPlay', None)
        main_button = toolbar.widgetForAction(action) if toolbar and action else None
        if main_button is not None:
            button.setIconSize(main_button.iconSize())
            button.setToolButtonStyle(main_button.toolButtonStyle())
            button.setAutoRaise(main_button.autoRaise())
