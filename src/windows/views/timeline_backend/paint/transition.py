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

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .base import BasePainter


class TransitionPainter(BasePainter):
    def update_theme(self):
        self.col = self.w.theme.transition.background
        self.col2 = self.w.theme.transition.background2
        bw = getattr(self.w.theme.transition, "border_width", 1.5) or 0.0
        bw = float(bw) if isinstance(bw, (int, float)) else 0.0
        if bw <= 0.0:
            bw = 1.5
        self.border_width = bw
        self.border_radius = float(self.w.theme.transition.border_radius or 0.0)
        self.pen = QPen(QBrush(self.w.theme.transition.border_color), bw)
        self.pen.setCosmetic(True)
        self.img = self.w.theme.transition.background_image
        self.sel_pen = QPen(QBrush(self.w.theme.clip_selected), bw)
        self.sel_pen.setCosmetic(True)
        self.menu_pix = None
        if self.w.theme.menu_icon:
            size = self.w.theme.menu_size or self.w.theme.menu_icon.width()
            self.menu_pix = self.scaled_pixmap(self.w.theme.menu_icon, size, size)
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
        for rect, _tran, selected in self.w.geometry.iter_transitions():
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
            result = self._transition_pixmap(rect, segment_rect)
            if not result:
                continue
            pix, includes_start, includes_end = result
            if pix:
                painter.drawPixmap(segment_rect.topLeft(), pix)
            self._stroke_visible_border(
                painter,
                segment_rect,
                pen,
                includes_start=includes_start,
                includes_end=includes_end,
            )
        painter.restore()

    def _transition_pixmap(self, full_rect, segment_rect):
        """Return cached pixmap for the visible portion of a transition."""
        w = int(segment_rect.width())
        h = int(segment_rect.height())
        if w <= 0 or h <= 0:
            return None

        offset_px = max(0.0, float(segment_rect.left() - full_rect.left()))
        includes_start = offset_px <= 0.5
        includes_end = (segment_rect.right() + 0.5) >= full_rect.right()

        bg_cache_key = self.img.cacheKey() if self.img else None
        key = (w, h, bg_cache_key, round(offset_px, 2), includes_start, includes_end)
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

        if self.menu_pix and not small and includes_start:
            p.drawPixmap(
                QPointF(self.menu_margin, self.menu_margin),
                self.menu_pix,
            )

        p.end()

        pix = QPixmap.fromImage(img)
        result = (pix, includes_start, includes_end)
        self.transition_cache[key] = result
        return result

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
