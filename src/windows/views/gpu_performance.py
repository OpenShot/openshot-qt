"""Small session indicators backed by cached GPU presentation evidence."""
from qt_api import QWidget, QPainter, QRectF, QSvgRenderer
from classes import hardware_rc  # noqa: F401; registers vector badges
from windows.views.hardware_combo import BADGE_WIDTH, BADGE_HEIGHT


class GpuStatusBadge(QWidget):
    """The exact vector badge artwork used in Export and Preferences."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = 'cpu'
        self.renderers = {mode: QSvgRenderer(':/hardware/%s.svg' % mode, self)
                          for mode in ('cpu', 'gpu')}
        self.setFixedSize(BADGE_WIDTH, BADGE_HEIGHT)

    def set_mode(self, mode):
        self.mode = 'gpu' if mode == 'gpu' else 'cpu'
        self.setAccessibleName(self.mode.upper())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.renderers[self.mode].render(painter, QRectF(0, 0, BADGE_WIDTH, BADGE_HEIGHT))
        painter.end()
