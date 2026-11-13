"""Source-range slider using the timeline's ruler painter and theme."""

from qt_api import (Qt, QSlider, QPainter, QColor, QPen, QPointF,
                    QRectF, QEvent, pyqtSignal, QFont, QFontMetrics)
from classes.app import get_app
from windows.views.range_interaction import range_hit_target
from windows.preview_icons import START_COLOR, END_COLOR, preview_colors
from windows.views.timeline_backend.theme import DEFAULT_THEME
from windows.views.timeline_backend.paint.cache import PlaybackCachePainter
from windows.views.timeline_backend.paint.ruler import RulerPainter
from windows.views.timeline_backend.paint.playhead import PlayheadPainter


class SourceRuler(QSlider):
    """QSlider-compatible playhead plus an inclusive, frame-aligned source range."""
    rangeEdited = pyqtSignal(int, int)
    rangeEditStarted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setObjectName('sourceRuler')
        self.setAccessibleName(get_app()._tr('Source ruler'))
        self.setFocusPolicy(Qt.StrongFocus)
        self.ruler_fps = {'num': 30, 'den': 1}
        self.range_enabled = True
        self.active_edge = None
        self.reference_design = False
        self.ruler_bound_labels = True
        self.ruler_compact_labels = True
        self.in_frame = self.out_frame = 1
        self.track_name_width = 10
        self.h_scroll_offset = 0
        self.scroll_bar_thickness = 10
        self.filmstrip_frames = []
        self.filmstrip_images = {}
        self.playback_cache_ranges = []
        self._scrubbing = False
        self.setMouseTracking(True)
        self._refresh_theme()
        self.valueChanged.connect(lambda _value: self.update())

    @property
    def current_frame(self):
        return self.value()

    @property
    def ruler_duration(self):
        return self.maximum() / (self.ruler_fps['num'] / self.ruler_fps['den'])

    @property
    def ruler_min_tick_spacing(self):
        # The shared painter labels every second tick. Budget for the actual
        # compact label, not the timeline's longer timecode or a fixed gap.
        duration = self.ruler_duration
        label = '%02d:%02d' % (int(duration)//60, int(duration)%60)
        if duration < 10:
            label += '.00'
        return max(70, self.fontMetrics().horizontalAdvance(label)+24) / 2

    @property
    def pixels_per_second(self):
        return max(1, self.width() - 21) / max(self.ruler_duration, 0.001)

    def _refresh_theme(self):
        timeline = getattr(getattr(get_app(), 'window', None), 'timeline', None)
        self.theme = getattr(timeline, 'theme', DEFAULT_THEME)
        self.playhead_painter = PlayheadPainter(self)
        # The themed playhead image includes a long shaft, so its full image
        # height must never determine the ruler's layout height.
        self.ruler_height = max(40, self.fontMetrics().height() + 12)
        self.filmstrip_height = 46
        self.cache_painter = PlaybackCachePainter(self)
        self.filmstrip_top = self.ruler_height + self.cache_painter.cache_height
        self.setFixedHeight(int(self.filmstrip_top + self.filmstrip_height + 4))
        self.preview_colors = preview_colors()
        self.painter = RulerPainter(self)
        if self.reference_design:
            self.painter.bg = QColor(self.preview_colors['field'])
            self.painter.bg2 = self.painter.bg
            self.painter.name_bg = self.painter.bg
            self.painter.name_bg2 = self.painter.bg
            self.painter.tick_font = QFont(self.font())
            self.painter.tick_font.setPointSizeF(self.font().pointSizeF())
            self.painter.text_pen = QPen(QColor(self.preview_colors['text']))
            self.painter.tick_pen = QPen(QColor(self.preview_colors['border']))
            self.painter.label_top = 2
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange) and hasattr(self, 'painter'):
            self._refresh_theme()

    def set_region(self, first, last):
        self.in_frame = max(1, min(self.maximum(), int(first)))
        self.out_frame = max(self.in_frame, min(self.maximum(), int(last)))
        self.update()

    def move_edge(self, edge, frame):
        first, last = self.in_frame, self.out_frame
        if edge == 'in':
            first = max(1, min(last, int(frame)))
        else:
            last = max(first, min(self.maximum(), int(frame)))
        if (first, last) != (self.in_frame, self.out_frame):
            self.set_region(first, last)
            self.rangeEdited.emit(first, last)
        self.setValue(first if edge == 'in' else last)

    def frame_at(self, x):
        return max(1, min(self.maximum(), round((x-10) / max(1, self.width()-21) * self.maximum()) + 1))

    def _x(self, boundary):
        return 10 + boundary / max(1, self.maximum()) * max(1, self.width()-21)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.save()
        painter.setClipRect(QRectF(10, 0, max(1, self.width()-20), self.ruler_height))
        self.painter.paint(painter)
        painter.restore()
        if self.reference_design:
            end = '%02d:%02d' % (int(self.ruler_duration)//60, int(self.ruler_duration)%60)
            metrics = QFontMetrics(self.painter.tick_font)
            width = metrics.horizontalAdvance(end)+8
            rect = QRectF(self.width()-10-width, 0, width, self.ruler_height-4)
            painter.fillRect(rect, QColor(self.preview_colors['field']))
            painter.setFont(self.painter.tick_font)
            painter.setPen(QColor(self.preview_colors['text']))
            painter.drawText(rect.adjusted(0, 0, -2, 0), Qt.AlignRight | Qt.AlignTop, end)
        # Use the timeline's painter, including theme colors and cache lane height.
        fps = self.ruler_fps['num'] / self.ruler_fps['den']
        self._playback_cache_ranges = [
            ((first - 1) / fps, last / fps)
            for first, last in self.playback_cache_ranges if last >= first]
        strip = QRectF(10, self.filmstrip_top, max(1, self.width()-20), self.filmstrip_height)
        painter.fillRect(strip, self.palette().base())
        frames = self._visible_filmstrip_frames(strip.width())
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if frames:
            cell_width = strip.width() / len(frames)
            for index, frame in enumerate(frames):
                pixmap = self.filmstrip_images.get(frame)
                if pixmap is None:
                    continue
                target = QRectF(strip.left() + index * cell_width + 1, strip.top() + 2,
                                cell_width - 2, strip.height() - 4)
                source = QRectF(pixmap.rect())
                # Fill each cell without distorting its source thumbnail.
                ratio = target.width() / target.height()
                if source.width() / source.height() > ratio:
                    width = source.height() * ratio
                    source.setLeft((source.width() - width) / 2)
                    source.setWidth(width)
                else:
                    height = source.width() / ratio
                    source.setTop((source.height() - height) / 2)
                    source.setHeight(height)
                painter.drawPixmap(target, pixmap, source)
        accent = QColor(self.preview_colors['accent'])
        first, last = self._x(self.in_frame-1), self._x(self.out_frame)
        if self.range_enabled:
            shade = QColor(accent)
            shade.setAlpha(115)
            painter.fillRect(QRectF(first, strip.top(), max(1, last-first), strip.height()), shade)
            painter.setPen(QPen(accent, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(first, strip.top()-3, max(1, last-first), strip.height()+5), 5, 5)
            if not self.reference_design:
                for (rect, text), edge_color in zip(self._edge_labels(), (START_COLOR, END_COLOR)):
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(edge_color))
                    painter.drawRoundedRect(rect, 3, 3)
                    painter.setPen(QColor(self.preview_colors['text']))
                    painter.drawText(rect, Qt.AlignCenter, text)
            painter.setRenderHint(QPainter.Antialiasing)
            for edge, grip in zip(('in', 'out'), self._grip_rects()):
                colors = self.preview_colors
                active = edge == self.active_edge
                fill = colors.get('range_grip_active', colors['accent']) if active else colors.get('range_grip', colors['grip'])
                detail = (colors.get('range_grip_active_detail', self.palette().highlightedText().color().name())
                          if active else colors.get('range_grip_detail', colors['accent']))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(fill))
                painter.drawRoundedRect(grip, 6, 6)
                painter.setPen(QPen(QColor(detail), 2))
                for offset in (-2, 2):
                    gx = grip.center().x()+offset
                    painter.drawLine(QPointF(gx, grip.top()+9), QPointF(gx, grip.bottom()-9))
        x = self._x(self.value()-1)
        self.cache_painter.paint(painter)
        self.playhead_painter.paint_at(
            painter, x, 0, self.width(), self.height(), self.ruler_height)

    def _visible_filmstrip_frames(self, width):
        # Reuse the bounded source samples, displaying fewer at narrow widths
        # so the filmstrip stays landscape-shaped rather than square tiles.
        frames = self.filmstrip_frames
        count = min(len(frames), max(1, int(width / (self.filmstrip_height * 16/9))))
        return [frames[round(i*(len(frames)-1)/max(1, count-1))] for i in range(count)]

    def _edge_labels(self):
        first, last = self._x(self.in_frame-1), self._x(self.out_frame)
        label_height = self.fontMetrics().height() + 4
        labels = []
        for x, text in ((first, get_app()._tr('Start')), (last, get_app()._tr('End'))):
            width = self.fontMetrics().horizontalAdvance(text) + 12
            left = max(0, min(self.width()-width, x-width/2))
            labels.append([QRectF(left, self.filmstrip_top+2, width, label_height), text])
        if labels[0][0].right() > labels[1][0].left():
            labels[0][0].moveLeft(max(0, min(first-labels[0][0].width(),
                                          self.width()-sum(item[0].width() for item in labels))))
            labels[1][0].moveLeft(labels[0][0].right())
        return labels

    def _grip_rects(self):
        first, last = self._x(self.in_frame-1), self._x(self.out_frame)
        positions = (first-8, last-8)
        return tuple(QRectF(x, self.filmstrip_top+5, 16, self.filmstrip_height-10)
                     for x in positions)

    def _hit_target(self, pos):
        if not self.range_enabled or pos.y() < self.filmstrip_top:
            return 'seek'
        first, last = self._x(self.in_frame-1), self._x(self.out_frame)
        selection = QRectF(first, self.filmstrip_top, last-first, self.filmstrip_height)
        left, right = self._grip_rects()
        return range_hit_target(pos, selection, left, right,
                                selection.adjusted(-8, 0, 8, 0),
                                self.filmstrip_top+4, self.filmstrip_height-8,
                                midpoint=(left.center().x()+right.center().x())/2)

    def edge_at(self, x, y=None):
        if y is None:
            y = self.filmstrip_top + self.filmstrip_height / 2
        if self.range_enabled and not self.reference_design:
            for edge, (rect, _text) in zip(('in', 'out'), self._edge_labels()):
                if rect.contains(QPointF(x, y)):
                    return edge
        return {'left': 'in', 'right': 'out'}.get(self._hit_target(QPointF(x, y)))

    def _drag_to(self, x):
        target = self._press_target
        if target == 'seek':
            self.setValue(self.frame_at(x))
            return
        # Match the zoom slider's five-pixel threshold before editing a range.
        if not self._dragging and abs(x-self._press_x) < 5:
            return
        if not self._dragging:
            self.rangeEditStarted.emit()
        self._dragging = True
        first, last = self._press_region
        delta = round((x-self._press_x) / max(1, self.width()-21) * self.maximum())
        if target in ('left', 'right'):
            self.move_edge('in' if target == 'left' else 'out',
                           (first if target == 'left' else last) + delta)
            return
        if target == 'move':
            span = last-first
            first = max(1, min(self.maximum()-span, first+delta))
            last = first+span
            frame = max(first, min(last, self._press_value+first-self._press_region[0]))
        else:
            frame = self.frame_at(x)
            first, last = sorted((self.frame_at(self._press_x), frame))
        if (first, last) != (self.in_frame, self.out_frame):
            self.set_region(first, last)
            self.rangeEdited.emit(first, last)
        self.setValue(frame)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.active_edge = None
            self.setFocus(Qt.MouseFocusReason)
            self._scrubbing = True
            self._dragging = False
            self._press_target = self._hit_target(event.pos())
            self._press_x = event.pos().x()
            self._press_region = self.in_frame, self.out_frame
            self._press_value = self.value()
            self.setSliderDown(True)
            if self._press_target == 'seek':
                self._drag_to(self._press_x)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._scrubbing:
            self._drag_to(event.pos().x())
        else:
            target = self._hit_target(event.pos())
            self.setCursor(Qt.SizeHorCursor if target in ('left', 'right') else
                           Qt.OpenHandCursor if target == 'move' else
                           Qt.CrossCursor if target == 'create' else Qt.ArrowCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._scrubbing and event.button() == Qt.LeftButton:
            self._drag_to(event.pos().x())
            if not self._dragging:
                self.setValue(self.frame_at(event.pos().x()))
            self._scrubbing = False
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
