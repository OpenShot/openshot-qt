"""A compact toggle with native checkbox keyboard and accessibility behavior."""
from qt_api import QCheckBox, QColor, QPainter, QPalette, QPen, QPointF, QRectF, QSize, Qt, Property


class ToggleSwitch(QCheckBox):
    """Shared checkbox control, with optional text and native input/signals.

    The active track follows palette Highlight and labels follow WindowText.
    Themes can override qproperty-uncheckedColor and qproperty-thumbColor.
    """

    def __init__(self, text="", parent=None):
        # Support both QCheckBox(parent) and QCheckBox(text, parent).
        if not isinstance(text, str):
            parent, text = text, ""
        super().__init__(text, parent)
        self._unchecked_color = QColor('#596575')
        self._thumb_color = QColor('#e2e7ed')
        self.setMinimumSize(50, 28)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

    def _set_unchecked_color(self, color):
        self._unchecked_color = QColor(color)
        self.update()

    def _set_thumb_color(self, color):
        self._thumb_color = QColor(color)
        self.update()

    uncheckedColor = Property(QColor, lambda self: self._unchecked_color, _set_unchecked_color)
    thumbColor = Property(QColor, lambda self: self._thumb_color, _set_thumb_color)

    def sizeHint(self):
        if not self.text():
            return QSize(50, 28)
        label = self.fontMetrics().size(Qt.TextShowMnemonic, self.text())
        return QSize(50 + label.width(), max(28, label.height() + 8))

    def minimumSizeHint(self):
        return self.sizeHint()

    def _track_rect(self):
        left = self.width() - 35 if self.layoutDirection() == Qt.LayoutDirection.RightToLeft else 3
        return QRectF(left, (self.height() - 18) / 2, 32, 18)

    def hitButton(self, position):
        # Keep the comfortable click target while making the visible switch smaller.
        size = self.sizeHint()
        width = min(self.width(), size.width())
        left = self.width() - width if self.layoutDirection() == Qt.LayoutDirection.RightToLeft else 0
        return QRectF(left, (self.height() - size.height()) / 2, width, size.height()).contains(QPointF(position))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = self._track_rect()
        highlight = self.palette().color(QPalette.Active, QPalette.Highlight)
        highlight.setAlpha(255)
        color = highlight.darker(115) if self.isChecked() else self._unchecked_color
        if not self.isEnabled():
            painter.setOpacity(0.45)
        elif self.underMouse():
            color = color.lighter(110)
        if self.hasFocus():
            painter.setPen(QPen(highlight, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 11, 11)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, 9, 9)
        right = self.isChecked() != (self.layoutDirection() == Qt.LayoutDirection.RightToLeft)
        partial = self.checkState() == Qt.PartiallyChecked
        thumb_x = track.right() - 16 if right else track.left() + 2
        if partial:
            thumb_x = track.center().x() - 7
        painter.setBrush(self._thumb_color)
        painter.drawEllipse(QRectF(thumb_x, track.top() + 2, 14, 14))
        painter.setOpacity(1)
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        label_rect = self.rect().adjusted(0 if rtl else 50, 0, -50 if rtl else 0, 0)
        alignment = Qt.AlignRight if rtl else Qt.AlignLeft
        flags = alignment | Qt.AlignVCenter | Qt.TextShowMnemonic
        # This custom control follows the theme palette on every platform,
        # including native styles which override drawItemText colors.
        palette = self.palette()
        group = palette.currentColorGroup() if self.isEnabled() else QPalette.Disabled
        painter.setPen(palette.color(group, QPalette.WindowText))
        painter.drawText(label_rect, int(getattr(flags, "value", flags)), self.text())
        painter.end()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()
