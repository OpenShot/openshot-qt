"""Transient feedback for the timeline's existing cursor hit targets."""

from qt_api import QBrush, QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPen, QPointF, QRadialGradient, QRectF, QTransform, Qt


def show_menu_with_hover(widget, callback, *args):
    """Keep a menu's originating control lit through its nested event loop."""
    feedback = getattr(widget, "hover_feedback", None)
    if feedback is None:
        return callback(*args)
    feedback.menu_open = True
    try:
        return callback(*args)
    finally:
        feedback.menu_open = False
        pos = widget.mapFromGlobal(QCursor.pos())
        if widget.rect().contains(pos):
            widget._updateCursor(QPointF(pos))
        else:
            feedback.clear()


class HoverFeedback:
    """Paint uncached feedback without invalidating thumbnails or hit geometry."""

    def __init__(self, widget):
        self.w = widget
        self.position = None
        self.target = None
        self.pending = None
        self.menu_open = False

    def holding_menu_press(self):
        """A press may prepare a clip drag without actually starting one."""
        if not self.target or self.target[0] != "menu":
            return False
        for kind in ("clip", "transition"):
            if (getattr(self.w, "_pending_%s_menu_target" % kind, None)
                    and not getattr(self.w, "_pending_%s_menu_dragged" % kind, False)
                    and not getattr(self.w, "_drag_threshold_met", False)):
                return True
        return False

    def leave(self):
        if not self.menu_open:
            self.clear()

    def begin(self, position):
        self.position = QPointF(position)
        self.pending = None

    def set_target(self, kind, rect, style="clip"):
        if isinstance(rect, QRectF) and not rect.isEmpty():
            self.pending = (kind, QRectF(rect), style)

    def commit(self):
        if self.target != self.pending:
            self.target = self.pending
            self.w.update()

    def clear(self):
        self.position = None
        self.pending = None
        self.commit()

    def active_resize_target(self):
        """Follow the actual resized geometry, including snap and duration limits."""
        item = getattr(self.w, "_resizing_item", None)
        edge = getattr(self.w, "_resize_edge", None)
        if (item is None or edge not in ("left", "right")
                or getattr(self.w, "_fixed_cursor", None) is None):
            return None
        for rect, candidate, _selected, kind in self.w.geometry.iter_items(reverse=True):
            if candidate is item:
                return ("edge-" + edge, QRectF(rect), kind)
        return None

    def edge_stroke_color(self, rect, style):
        """Use the same pen as the item painter, including selection styling."""
        theme = getattr(self.w.theme, style)
        for candidate_rect, _item, selected, kind in self.w.geometry.iter_items(reverse=True):
            if kind == style and candidate_rect == rect:
                item_painter = getattr(self.w, style + "_painter", None)
                pen_name = "sel_pen" if selected else ("clip_pen" if style == "clip" else "pen")
                pen = getattr(item_painter, pen_name, None)
                if isinstance(pen, QPen):
                    return QColor(pen.color())
                return QColor(self.w.theme.clip_selected if selected else theme.border_color)
        return QColor(theme.border_color)

    def keyframe_fill(self, color, rect, style):
        """Shade only the glyph's fill, preserving its shape and selection pen."""
        if self.target != ("keyframe", rect, style):
            return color
        color = QColor(color)
        return color.darker(112) if color.lightnessF() > 0.8 else color.lighter(130)

    def paint(self, painter):
        # Re-evaluate against freshly painted title rectangles when scrolling,
        # zooming, changing themes, or removing an item under a stationary mouse.
        if self.position is not None and not self.menu_open:
            self.w._updateCursor(self.position)
        target = self.active_resize_target() or self.target
        if target is None:
            return
        kind, rect, style = target
        if kind == "keyframe":
            # Each marker painter shades its own interpolation glyph.
            return
        theme = getattr(self.w.theme, style)
        color = QColor(theme.font_color)
        if kind != "menu" or not color.isValid():
            color = QColor("white" if theme.background.lightnessF() < 0.5 else "black")
        color.setAlpha(90 if kind == "menu" else 180)
        fill = QColor(color)
        fill.setAlpha(18)
        track_menu = style == "track" and kind == "menu"
        left = 0 if track_menu else self.w.track_name_width
        right = self.w.width() - self.w.scroll_bar_thickness
        if track_menu:
            right = self.w.track_name_width
        area = QRectF(left, self.w.ruler_height, max(0, right - left),
                      max(0, self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness))
        painter.save()
        painter.setClipRect(area, Qt.IntersectClip)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(color, 1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(fill)
        if kind in ("edge-left", "edge-right"):
            self._paint_edge(painter, rect, theme, kind == "edge-left", self.edge_stroke_color(rect, style))
        else:
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
        painter.restore()

    @staticmethod
    def edge_path(rect, radius, left):
        """Follow the inside of the border without extending beyond the clip."""
        inset = min(1.5, rect.width() / 2, rect.height() / 2)
        inner = rect.adjusted(inset, inset, -inset, -inset)
        radius = max(0.0, min(float(radius), inner.width() / 2, inner.height() / 2))
        x = inner.left() if left else inner.right()
        direction = 1 if left else -1
        tip = x + direction * radius / 4
        top, bottom = inner.top(), inner.bottom()
        path = QPainterPath()
        path.moveTo(tip, top + radius / 4)
        path.quadTo(x, top + radius / 2, x, top + radius)
        path.lineTo(x, bottom - radius)
        path.quadTo(x, bottom - radius / 2, tip, bottom - radius / 4)
        return path

    def _paint_edge(self, painter, rect, theme, left, stroke_color=None):
        path = self.edge_path(rect, theme.border_radius, left)
        # The hit area can extend outside, but every painted pixel belongs to
        # this clip, even for very narrow clips and rounded corners.
        outline = QPainterPath()
        radius = max(0.0, min(float(theme.border_radius), rect.width() / 2, rect.height() / 2))
        outline.addRoundedRect(rect, radius, radius)
        painter.setClipPath(outline, Qt.IntersectClip)
        # Use the item's own border hue rather than a separate handle design.
        accent = QColor(stroke_color if stroke_color is not None else theme.border_color)
        if not accent.isValid():
            accent = QColor(self.w.theme.keyframe_fill)
        # An elliptical radial wash fades inward and toward both corners. It
        # changes opacity only, never the hue of the actual item stroke.
        depth = min(18.0, rect.width() / 3)
        if depth > 0 and rect.height() > 0:
            wash = QRadialGradient(QPointF(0, 0), 1.0)
            for stop, alpha in ((0.0, 100), (0.4, 55), (1.0, 0)):
                color = QColor(accent)
                color.setAlpha(alpha)
                wash.setColorAt(stop, color)
            brush = QBrush(wash)
            edge_x = rect.left() if left else rect.right()
            transform = QTransform()
            transform.translate(edge_x, rect.center().y())
            transform.scale(depth, rect.height() / 2)
            brush.setTransform(transform)
            painter.fillRect(rect, brush)
        painter.setBrush(Qt.NoBrush)
        # Fade the corner tips into the clip instead of outlining a bracket.
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        for stop, alpha in ((0.0, 0), (0.18, 160), (0.5, 240), (0.82, 160), (1.0, 0)):
            color = QColor(accent)
            color.setAlpha(alpha)
            gradient.setColorAt(stop, color)
        painter.setPen(QPen(QBrush(gradient), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

