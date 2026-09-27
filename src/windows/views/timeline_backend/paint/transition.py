"""
 @file
 @brief Painter for transition items.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

from qt_api import QPointF, QRectF, Qt
from qt_api import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .base import BasePainter
from .header import ItemHeaderMixin


class TransitionPainter(ItemHeaderMixin, BasePainter):
    header_kind = "transition"

    DEFAULT_OPACITY = 0.75
    SELECTED_OPACITY = 0.88
    LOCKED_OPACITY_MULTIPLIER = 0.8
    SELECTED_OVERLAY_ALPHA = 32

    def update_theme(self):
        self.col = self.w.theme.transition.background
        self.col2 = self.w.theme.transition.background2
        bw = getattr(self.w.theme.transition, "border_width", 2.0) or 0.0
        bw = float(bw) if isinstance(bw, (int, float)) else 0.0
        if bw <= 0.0:
            bw = 2.0
        self.border_width = bw
        self.border_radius = float(self.w.theme.transition.border_radius or 0.0)
        self.pen = QPen(QBrush(self.w.theme.transition.border_color), bw)
        self.pen.setCosmetic(True)
        self.img = self.w.theme.transition.background_image
        self.sel_pen = QPen(QBrush(self.w.theme.clip_selected), bw)
        self.sel_pen.setCosmetic(True)
        from windows.views.timeline_backend.theme import _icon as _theme_icon
        arrow = _theme_icon("themes/cosmic/images/dropdown-arrow.svg")
        self.dropdown_arrow_pix = arrow if (arrow and not arrow.isNull()) else None
        self.menu_margin = self.w.theme.menu_margin
        # Cache of fully rendered transition pixmaps
        self.transition_cache = {}

    def clear_cache(self):
        """Clear cached rendered transition pixmaps."""
        self.transition_cache.clear()

    def _segment_overdraw(self, view_width):
        blur = max(0.0, float(self.w.theme.clip.shadow_blur or 0.0))
        base = max(48.0, view_width * 0.2)
        return max(base, blur * 3.0)

    def paint(self, painter: QPainter):
        area = QRectF(
            self.w.track_name_width,
            self.w.ruler_height,
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        overdraw = self._segment_overdraw(area.width())
        expanded = QRectF(
            area.left() - overdraw,
            area.top(),
            area.width() + (overdraw * 2.0),
            area.height(),
        )

        painter.save()
        painter.setClipRect(area)
        self.w._transition_text_rects = []
        for rect, tran, selected in self.w.geometry.iter_transitions():
            if not rect.intersects(expanded):
                continue
            segment_left = max(rect.left(), expanded.left())
            segment_right = min(rect.right(), expanded.right())
            if segment_right <= segment_left:
                continue
            segment_rect = QRectF(
                segment_left,
                rect.top(),
                segment_right - segment_left,
                rect.height(),
            )
            pen = self.sel_pen if selected else self.pen
            locked = self.w._is_track_locked((tran.data if isinstance(tran.data, dict) else {}).get("layer"))
            if locked:
                pen = self.dimmed_pen(pen)
            opacity = self.SELECTED_OPACITY if selected else self.DEFAULT_OPACITY
            if locked:
                opacity *= self.LOCKED_OPACITY_MULTIPLIER
            painter.save()
            if opacity < 0.999:
                painter.setOpacity(opacity)
            result = self._transition_pixmap(rect, segment_rect, selected=selected)
            if not result:
                painter.restore()
                continue
            pix, includes_start, includes_end = result
            if pix:
                painter.drawPixmap(segment_rect.topLeft(), pix)
            painter.restore()
            self._stroke_visible_border(
                painter,
                segment_rect,
                pen,
                includes_start=includes_start,
                includes_end=includes_end,
            )
            self._draw_item_header(painter, tran, rect, area)
        painter.restore()

    def _transition_pixmap(self, full_rect, segment_rect, *, selected=False):
        """Return cached pixmap for the visible portion of a transition."""
        w = int(segment_rect.width())
        h = int(segment_rect.height())
        if w <= 0 or h <= 0:
            return None

        offset_px = max(0.0, float(segment_rect.left() - full_rect.left()))
        includes_start = offset_px <= 0.5
        includes_end = (segment_rect.right() + 0.5) >= full_rect.right()

        bg_cache_key = self.img.cacheKey() if self.img else None
        key = (w, h, bg_cache_key, round(offset_px, 2), includes_start, includes_end, bool(selected))
        if key in self.transition_cache:
            return self.transition_cache[key]

        small = w < 20
        tiny = w < 2
        radius = self.w.theme.transition.border_radius if not small else 0
        if radius:
            radius = min(float(radius), min(float(w), float(h)) / 2.0)

        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(0, 0, w, h)
        path = None
        if radius > 0.0 and (includes_start or includes_end):
            left = rect.left()
            right = rect.right()
            top = rect.top()
            bottom = rect.bottom()
            path = QPainterPath()

            if includes_start:
                path.moveTo(left, top + radius)
                path.quadTo(left, top, left + radius, top)
            else:
                path.moveTo(left, top)

            if includes_end:
                path.lineTo(right - radius, top)
                path.quadTo(right, top, right, top + radius)
                path.lineTo(right, bottom - radius)
                path.quadTo(right, bottom, right - radius, bottom)
            else:
                path.lineTo(right, top)
                path.lineTo(right, bottom)

            if includes_start:
                path.lineTo(left + radius, bottom)
                path.quadTo(left, bottom, left, bottom - radius)
                path.lineTo(left, top + radius)
            else:
                path.lineTo(left, bottom)
                path.lineTo(left, top)

            path.closeSubpath()
        elif radius > 0.0:
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)

        if not tiny:
            if self.col2.isValid() and self.col2 != self.col:
                grad = QLinearGradient(QPointF(0, 0), QPointF(0, h))
                grad.setColorAt(0, self.col)
                grad.setColorAt(1, self.col2)
                brush = QBrush(grad)
            else:
                brush = QBrush(self.col)

            if path is not None:
                p.fillPath(path, brush)
            else:
                p.fillRect(rect, brush)

            if self.img and not small:
                scaled = self.img.scaled(
                    w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                )
                if path is not None:
                    p.save()
                    p.setClipPath(path)
                    p.drawPixmap(0, 0, scaled)
                    p.restore()
                else:
                    p.drawPixmap(0, 0, scaled)

            if selected:
                overlay = QColor(255, 255, 255, self.SELECTED_OVERLAY_ALPHA)
                if path is not None:
                    p.fillPath(path, overlay)
                else:
                    p.fillRect(rect, overlay)

        p.end()

        pix = QPixmap.fromImage(img)
        result = (pix, includes_start, includes_end)
        self.transition_cache[key] = result
        return result

    def _header_title(self, tran):
        resolver = getattr(self.w, "_transition_label", None)
        if callable(resolver):
            try:
                return str(resolver(tran) or "")
            except Exception:
                pass
        data = tran.data if isinstance(getattr(tran, "data", None), dict) else {}
        return str(data.get("title", "") or "")

    def transition_menu_geometry(self, rect, tran=None):
        """Measure the shared header for menu hit testing before the first paint."""
        from types import SimpleNamespace

        if rect.isEmpty():
            return QRectF(), QRectF(), None, QRectF(), ""
        image = QImage(1, 1, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        try:
            entry = self._draw_item_text(
                painter, tran if tran is not None else SimpleNamespace(data={}),
                rect, rect.left(), rect.right(), visible_width=rect.width(),
            )
        finally:
            painter.end()
        if not entry:
            return QRectF(), QRectF(), None, QRectF(), ""
        return (entry["rect"], QRectF(entry["rect"]), entry.get("scaled_arrow"),
                entry.get("arrow_rect", QRectF()), entry.get("title_elided", ""))

    def _stroke_visible_border(
        self,
        painter,
        segment_rect,
        pen,
        *,
        includes_start=True,
        includes_end=True,
    ):
        if not isinstance(pen, QPen) or not pen.color().isValid():
            return
        if segment_rect.width() <= 0.0 or segment_rect.height() <= 0.0:
            return

        painter.save()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)

        rect = QRectF(segment_rect)
        width_offset = max(pen.widthF(), 1.0) / 2.0
        max_x = max(rect.width() / 2.0 - 0.1, 0.0)
        max_y = max(rect.height() / 2.0 - 0.1, 0.0)
        offset_x = min(width_offset, max_x)
        offset_y = min(width_offset, max_y)
        rect.adjust(offset_x, offset_y, -offset_x, -offset_y)

        if rect.width() <= 0.0 or rect.height() <= 0.0:
            painter.restore()
            return

        radius = 0.0
        if rect.width() > 0.0 and rect.height() > 0.0:
            radius = min(self.border_radius, min(rect.width(), rect.height()) / 2.0)

        painter.setRenderHint(QPainter.Antialiasing, True)
        if radius > 0.0 and (includes_start or includes_end):
            left = rect.left()
            right = rect.right()
            top = rect.top()
            bottom = rect.bottom()
            path = QPainterPath()

            if includes_start:
                path.moveTo(left, top + radius)
                path.quadTo(left, top, left + radius, top)
            else:
                path.moveTo(left, top)

            if includes_end:
                path.lineTo(right - radius, top)
                path.quadTo(right, top, right, top + radius)
                path.lineTo(right, bottom - radius)
                path.quadTo(right, bottom, right - radius, bottom)
            else:
                path.lineTo(right, top)
                path.lineTo(right, bottom)

            if includes_start:
                path.lineTo(left + radius, bottom)
                path.quadTo(left, bottom, left, bottom - radius)
                path.lineTo(left, top + radius)
            else:
                path.lineTo(left, bottom)
                path.lineTo(left, top)

            path.closeSubpath()
            painter.drawPath(path)
        elif radius > 0.0:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.drawRect(rect)

        painter.restore()
