"""A compact toggle with native checkbox keyboard and accessibility behavior."""
from qt_api import QCheckBox, QColor, QPainter, QPalette, QPen, QPointF, QRectF, QSize, Qt


class PreferenceSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(50, 28)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(50, 28)

    def minimumSizeHint(self):
        return self.sizeHint()

    def _track_rect(self):
        left = self.width() - 35 if self.layoutDirection() == Qt.LayoutDirection.RightToLeft else 3
        return QRectF(left, (self.height() - 18) / 2, 32, 18)

    def hitButton(self, position):
        # Keep the comfortable click target while making the visible switch smaller.
        left = self.width() - 50 if self.layoutDirection() == Qt.LayoutDirection.RightToLeft else 0
        return QRectF(left, (self.height() - 28) / 2, 50, 28).contains(QPointF(position))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = self._track_rect()
        highlight = self.palette().color(QPalette.Active, QPalette.Highlight)
        highlight.setAlpha(255)
        color = highlight.darker(115) if self.isChecked() else QColor('#596575')
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
        thumb_x = track.right() - 16 if right else track.left() + 2
        painter.setBrush(QColor('#e2e7ed'))
        painter.drawEllipse(QRectF(thumb_x, track.top() + 2, 14, 14))
        painter.end()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()
