"""Format-first hardware choices with vector badges in both combo paint paths."""
import re
from qt_api import (Qt, QComboBox, QStyledItemDelegate, QStyleOptionViewItem,
                    QStyleOptionComboBox, QStylePainter, QStyle, QIcon, QApplication,
                    QSvgRenderer, QPainter, QFont, QFontMetrics, QColor, QPalette,
                    QRectF, QSize, QListView, QWidget, QVBoxLayout, QHBoxLayout,
                    QLineEdit, QToolButton, QLabel, QPoint, QEvent)
from classes import hardware_rc  # noqa: F401; registers vector badges

BADGES_ROLE = Qt.UserRole + 51


def style_enum(name, group):
    value = getattr(QStyle, name, None)
    return value if value is not None else getattr(getattr(QStyle, group), name)


def set_hardware_item(combo, index, mode, label=None, route="", details=""):
    """Keep the preset identifier in UserRole, independent of its presentation."""
    label = label or combo.itemText(index)
    combo.setItemText(index, label)
    combo.setItemData(index, dict(label=label, mode=mode, route=route, details=details), BADGES_ROLE)
    if isinstance(combo, HardwareComboBox):
        combo.sync_details()
    combo.updateGeometry()


def export_choice_label(title, container, codec, backend):
    """Simplify ordinary formats without losing custom preset qualifiers."""
    family = None
    if codec in ('libx264', 'libx264rgb') or codec.startswith('h264_'):
        family = 'H.264'
    elif codec == 'libx265' or codec.startswith('hevc_'):
        family = 'H.265'
    elif codec in ('libaom-av1', 'libsvtav1') or codec.startswith('av1_'):
        family = 'AV1'
    if not family or not container:
        return title
    formats = {'matroska': 'MKV', 'mp4': 'MP4', 'mov': 'MOV', 'webm': 'WebM', 'avi': 'AVI'}
    format_name = formats.get(container, container.upper())
    # Extra words such as Lossless, RGB, or a user preset name must survive.
    ordinary = re.fullmatch(
        re.escape(format_name) + r'\s*\(\s*(h\.?264|h\.?265|hevc|av1)\s*'
        r'(nv|nvenc|qsv|vtb|videotoolbox|va|vaapi|dx|dxva2|vulkan|amf)?\s*\)', title, re.I)
    if ordinary:
        return '%s (%s)' % (format_name, family)
    return title


def backend_badge(backend, translate=lambda value: value):
    return {'nvenc': 'NVIDIA', 'qsv': 'Intel', 'vtb': 'Apple', 'amf': 'AMD',
            'vaapi': 'Linux', 'dx': 'Windows', 'vulkan': translate('Cross-platform')}.get(backend, '')


class HardwareItemDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
        self.renderers = {mode: QSvgRenderer(':/hardware/%s.svg' % mode, self)
                          for mode in ('cpu', 'gpu')}

    @staticmethod
    def route_font(font):
        result = QFont(font)
        result.setPixelSize(11)
        result.setBold(False)
        return result

    def content_width(self, data, font):
        width = QFontMetrics(font).horizontalAdvance(data['label'])
        if data.get('details'):
            width = max(width, QFontMetrics(self.route_font(font)).horizontalAdvance(data['details']))
        return width + 64 + 36

    def draw_content(self, painter, rect, data, font, palette, selected=False, enabled=True, expanded=False):
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        if not enabled:
            painter.setOpacity(0.45)
        dpr = painter.device().devicePixelRatioF()
        badge_y = round((rect.center().y() - 11) * dpr) / dpr
        badge_x = round((rect.left() + 8) * dpr) / dpr
        badge_rect = QRectF(badge_x, badge_y, 64, 22)
        # Render vectors directly in both the selected control and popup.
        self.renderers[data['mode']].render(painter, badge_rect)
        text_rect = QRectF(badge_rect.right() + 12, rect.top(),
                           max(0, rect.right() - badge_rect.right() - 20), rect.height())
        details = data.get('details', '') if expanded else ''
        if details:
            text_rect.setTop(rect.top() + 5)
            text_rect.setHeight(22)
        painter.setFont(font)
        text_color = palette.color(QPalette.HighlightedText if selected else QPalette.Text)
        painter.setPen(text_color)
        label = QFontMetrics(font).elidedText(data['label'], Qt.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, int(Qt.AlignLeft | Qt.AlignVCenter), label)
        if details:
            detail_font = self.route_font(font)
            painter.setFont(detail_font)
            text_color.setAlpha(185)
            painter.setPen(text_color)
            detail_rect = QRectF(text_rect.left(), rect.top() + 27, text_rect.width(), 18)
            detail_text = QFontMetrics(detail_font).elidedText(details, Qt.ElideRight, int(detail_rect.width()))
            painter.drawText(detail_rect, int(Qt.AlignLeft | Qt.AlignVCenter), detail_text)
        painter.restore()

    def paint(self, painter, option, index):
        data = index.data(BADGES_ROLE)
        if not data:
            return super().paint(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ''
        opt.icon = QIcon()
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(style_enum('CE_ItemViewItem', 'ControlElement'), opt, painter, opt.widget)
        self.draw_content(painter, QRectF(option.rect), data, opt.font, opt.palette,
                          bool(opt.state & QStyle.State_Selected), bool(opt.state & QStyle.State_Enabled), expanded=True)

    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)
        data = index.data(BADGES_ROLE)
        if data:
            return QSize(self.content_width(data, option.font), max(52 if data.get("details") else 32, base.height()))
        return base


class HardwareComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use a regular scrolling list rather than Qt's menu-style combo
        # popup, whose edge hover scrollers are surprising with tall rows.
        self.setStyleSheet("HardwareComboBox { combobox-popup: 0; }")
        self.setMaxVisibleItems(8)
        self.setView(QListView(self))
        self.view().setAutoScroll(False)
        self.base_tooltip = None
        self.badge_delegate = HardwareItemDelegate(self)
        self.setItemDelegate(self.badge_delegate)
        self.currentIndexChanged.connect(self.sync_details)

    def sync_details(self, *args):
        if not self.itemData(self.currentIndex(), BADGES_ROLE):
            if self.base_tooltip is not None:
                self.setToolTip(self.base_tooltip)
                self.setAccessibleDescription(self.base_tooltip)
            return
        details = self.itemData(self.currentIndex(), Qt.ToolTipRole)
        if details:
            if self.base_tooltip is None:
                self.base_tooltip = self.toolTip()
            self.setToolTip(details)
            self.setAccessibleDescription(details)
        elif self.base_tooltip is not None:
            self.setToolTip(self.base_tooltip)
            self.setAccessibleDescription(self.base_tooltip)

    def paintEvent(self, event):
        data = self.itemData(self.currentIndex(), BADGES_ROLE)
        if not data:
            return super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = ''
        option.currentIcon = QIcon()
        painter = QStylePainter(self)
        try:
            control = style_enum('CC_ComboBox', 'ComplexControl')
            painter.drawComplexControl(control, option)
            rect = self.style().subControlRect(control, option,
                                               style_enum('SC_ComboBoxEditField', 'SubControl'), self)
            self.badge_delegate.draw_content(painter, QRectF(rect), data, self.font(), option.palette,
                                             enabled=self.isEnabled())
        finally:
            painter.end()

    def sizeHint(self):
        base = super().sizeHint()
        widths = [self.badge_delegate.content_width(data, self.font()) + 24
                  for i in range(self.count())
                  for data in [self.itemData(i, BADGES_ROLE)] if data]
        return QSize(max([base.width()] + widths), max(base.height(), 32))

    def minimumSizeHint(self):
        base = super().minimumSizeHint()
        return QSize(max(base.width(), 170), max(base.height(), 32))

    def _create_filtered_popup(self):
        self.filter_popup = QWidget(self, Qt.Popup)
        self.filter_popup.setObjectName("hardwareChoices")
        layout = QVBoxLayout(self.filter_popup)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(3)
        self.filter_buttons = {}
        for mode, label in (("all", self.tr("All")), ("gpu", "GPU"), ("cpu", "CPU")):
            button = QToolButton(self.filter_popup)
            button.setText(label)
            button.setCheckable(True)
            button.setAccessibleName(self.tr("Show %s formats") % label)
            button.clicked.connect(lambda checked, mode=mode: self._filter_mode(mode))
            header.addWidget(button)
            self.filter_buttons[mode] = button
        self.filter_search = QLineEdit(self.filter_popup)
        self.filter_search.setPlaceholderText(self.tr("Search formats…"))
        self.filter_search.setAccessibleName(self.tr("Search export formats"))
        self.filter_search.setClearButtonEnabled(True)
        self.filter_search.textChanged.connect(self._filter_rows)
        self.filter_search.returnPressed.connect(self._accept_filter_current)
        self.filter_search.installEventFilter(self)
        header.addWidget(self.filter_search, 1)
        layout.addLayout(header)
        self.popup_view = QListView(self.filter_popup)
        self.popup_view.setAutoScroll(False)
        self.popup_view.setMouseTracking(True)
        self.popup_view.setItemDelegate(HardwareItemDelegate(self.popup_view))
        self.popup_view.clicked.connect(self._accept_filter_index)
        self.popup_view.activated.connect(self._accept_filter_index)
        layout.addWidget(self.popup_view)
        self.filter_empty = QLabel(self.tr("No matching formats"), self.filter_popup)
        layout.addWidget(self.filter_empty)

    def _filter_mode(self, mode):
        self.filter_mode = mode
        for key, button in self.filter_buttons.items():
            button.setChecked(key == mode)
        self._filter_rows()

    def _filter_rows(self, *args):
        query = self.filter_search.text().casefold().strip()
        first = None
        for row in range(self.count()):
            data = self.itemData(row, BADGES_ROLE) or {}
            text = " ".join((self.itemText(row), data.get('details', ''),
                             self.itemData(row, Qt.ToolTipRole) or '')).casefold()
            visible = (self.filter_mode == 'all' or data.get('mode') == self.filter_mode)
            visible = visible and all(word in text for word in query.split())
            self.popup_view.setRowHidden(row, not visible)
            if visible and first is None:
                first = row
        self.filter_empty.setVisible(first is None)
        self.popup_view.setVisible(first is not None)
        current = self.popup_view.currentIndex()
        if first is not None and (not current.isValid() or self.popup_view.isRowHidden(current.row())):
            self.popup_view.setCurrentIndex(self.model().index(first, self.modelColumn()))

    def _accept_filter_index(self, index):
        if not index.isValid() or self.popup_view.isRowHidden(index.row()):
            return
        self.setCurrentIndex(index.row())
        self.hidePopup()
        self.activated.emit(index.row())

    def _accept_filter_current(self):
        self._accept_filter_index(self.popup_view.currentIndex())

    def eventFilter(self, watched, event):
        if (watched is getattr(self, 'filter_search', None)
                and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Down):
            self.popup_view.setFocus()
            return True
        return super().eventFilter(watched, event)

    def hidePopup(self):
        if hasattr(self, 'filter_popup'):
            self.filter_popup.hide()
        super().hidePopup()

    def showPopup(self):
        handle = self.window().windowHandle()
        screen = handle.screen() if handle else QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else self.window().geometry()
        limit = max(170, bounds.width() - 24)
        width = min(limit, max(self.width(), self.sizeHint().width()))
        # Preferences use the same badges but don't need export filtering.
        if not any((self.itemData(i, BADGES_ROLE) or {}).get('details') for i in range(self.count())):
            self.view().setMinimumWidth(width)
            return super().showPopup()
        if not hasattr(self, 'filter_popup'):
            self._create_filtered_popup()
        self.popup_view.setModel(self.model())
        self.popup_view.setModelColumn(self.modelColumn())
        self.popup_view.setCurrentIndex(self.model().index(self.currentIndex(), self.modelColumn()))
        self.filter_mode = 'all'
        self.filter_search.clear()
        self._filter_mode('all')
        below = self.mapToGlobal(QPoint(0, self.height()))
        above = self.mapToGlobal(QPoint(0, 0))
        available_below = bounds.bottom() - below.y()
        available_above = above.y() - bounds.top()
        desired = min(8, self.count()) * 52 + 50
        height = min(desired, max(available_below, available_above))
        y = below.y() if available_below >= height else above.y() - height
        x = max(bounds.left(), min(below.x(), bounds.right() - width + 1))
        self.filter_popup.setGeometry(x, y, width, height)
        self.filter_popup.show()
        self.popup_view.scrollTo(self.popup_view.currentIndex())
        self.filter_search.setFocus()
