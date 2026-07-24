"""
 @file
 @brief Painter for track backgrounds and labels.
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
import math

from qt_api import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

from .base import BasePainter
from classes.qt_types import font_metrics_horizontal_advance


class TrackPainter(BasePainter):
    def update_theme(self):
        self.border_pen = QPen(self.w.theme.track.border_color)
        self.border_pen.setCosmetic(True)
        self.name_border_color = self.w.theme.track.name_border_color
        self.name_border_width = self.w.theme.track.name_border_width
        self.name_border_top_color = self.w.theme.track.name_border_top_color
        self.name_border_top_width = self.w.theme.track.name_border_top_width
        self.name_border_bottom_color = self.w.theme.track.name_border_bottom_color
        self.name_border_bottom_width = self.w.theme.track.name_border_bottom_width
        self.name_radius_tl = self.w.theme.track.name_radius_tl
        self.name_radius_bl = self.w.theme.track.name_radius_bl
        self.name_top_overlay = QColor(self.w.theme.track.name_top_overlay)
        self.name_top_overlay2 = QColor(self.w.theme.track.name_top_overlay2)
        self.menu_pix = None
        from windows.views.timeline_backend.theme import _icon as _theme_icon
        arrow = _theme_icon("themes/cosmic/images/dropdown-arrow.svg")
        self.dropdown_arrow_pix = arrow if (arrow and not arrow.isNull()) else None
        self.menu_margin = self.w.theme.menu_margin
        self.toggle_off_pix = None
        self.toggle_on_pix = None
        toggle_size = float(self.w.theme.menu_size or 0.0)

        def _scaled_toggle(pixmap):
            if not pixmap or pixmap.isNull():
                return None
            width = float(pixmap.width())
            height = float(pixmap.height())
            if toggle_size > 0.0:
                target = max(toggle_size, width, height)
                width = height = target
            return self.scaled_pixmap(pixmap, width, height)

        if self.w.theme.keyframe_toggle_off_icon:
            self.toggle_off_pix = _scaled_toggle(
                self.w.theme.keyframe_toggle_off_icon
            )
        if self.w.theme.keyframe_toggle_on_icon:
            self.toggle_on_pix = _scaled_toggle(
                self.w.theme.keyframe_toggle_on_icon
            )
        self.toggle_margin = self.w.theme.menu_margin

        self.toolbar_order = (
            "visibility-toggle",
            "lock-toggle",
            "keyframe-panel",
        )

        toolbar = {}

        # Visibility toggle (Eye icon)
        vis_enabled = _scaled_toggle(getattr(self.w.theme, "track_visible_enabled_icon", None)) or lock_unlocked_enabled
        vis_disabled = _scaled_toggle(getattr(self.w.theme, "track_visible_disabled_icon", None)) or lock_locked_enabled
        if vis_enabled or vis_disabled:
            toolbar["visibility-toggle"] = {
                "visible": {
                    "disabled": vis_enabled,
                    "enabled": vis_enabled,
                },
                "hidden": {
                    "disabled": vis_disabled,
                    "enabled": vis_disabled,
                },
            }

        keyframe_disabled = _scaled_toggle(
            getattr(self.w.theme, "track_keyframe_panel_disabled_icon", None)
            or self.w.theme.keyframe_toggle_off_icon
        )
        keyframe_enabled = _scaled_toggle(
            getattr(self.w.theme, "track_keyframe_panel_enabled_icon", None)
            or self.w.theme.keyframe_toggle_on_icon
        )
        if keyframe_disabled or keyframe_enabled:
            toolbar["keyframe-panel"] = {
                "disabled": keyframe_disabled,
                "enabled": keyframe_enabled or keyframe_disabled,
            }
            if not self.toggle_off_pix:
                self.toggle_off_pix = keyframe_disabled
            if not self.toggle_on_pix:
                self.toggle_on_pix = keyframe_enabled or keyframe_disabled

        lock_locked_disabled = _scaled_toggle(getattr(self.w.theme, "track_locked_disabled_icon", None))
        lock_locked_enabled = _scaled_toggle(getattr(self.w.theme, "track_locked_enabled_icon", None))
        lock_unlocked_disabled = _scaled_toggle(getattr(self.w.theme, "track_unlocked_disabled_icon", None))
        lock_unlocked_enabled = _scaled_toggle(getattr(self.w.theme, "track_unlocked_enabled_icon", None))
        if (
            lock_locked_disabled
            or lock_locked_enabled
            or lock_unlocked_disabled
            or lock_unlocked_enabled
        ):
            toolbar["lock-toggle"] = {
                "locked": {
                    "disabled": lock_locked_disabled,
                    "enabled": lock_locked_enabled or lock_locked_disabled,
                },
                "unlocked": {
                    "disabled": lock_unlocked_disabled,
                    "enabled": lock_unlocked_enabled or lock_unlocked_disabled,
                },
            }

        self.toolbar_pixmaps = toolbar

    def track_title_geometry(self, name_rect, track=None, *, painter=None):
        if name_rect.isNull() or name_rect.width() <= 0.0 or name_rect.height() <= 0.0:
            return QRectF(), None, QRectF(), ""

        metrics = QFontMetrics(painter.font()) if painter is not None else None
        font_h = float(metrics.height()) if metrics is not None else max(12.0, name_rect.height() - 4.0)
        pad_x = 6.0
        pad_y = 2.0
        icon_gap = 4.0
        border_left = float(self.name_border_width or 0.0)
        border_top = float(self.name_border_top_width or 0.0)
        border_bottom = float(self.name_border_bottom_width or 0.0)
        available_w = max(0.0, name_rect.width() - border_left)
        available_h = max(1.0, name_rect.height() - border_top - border_bottom)
        container_h = min(available_h, font_h + pad_y * 2.0)
        icon_size = max(8.0, font_h - 2.0)
        label = self.w._track_display_label(track) if track is not None else ""

        text_advance = 0.0
        title_elided = ""
        if metrics is not None:
            avail_text_w = int(max(0.0, available_w - pad_x * 2.0 - icon_gap - icon_size))
            if avail_text_w >= 4:
                title_elided = metrics.elidedText(label, Qt.ElideRight, avail_text_w)
                if title_elided:
                    text_advance = float(font_metrics_horizontal_advance(metrics, title_elided))

        if text_advance <= 0.0:
            return QRectF(), None, QRectF(), ""

        container_w = min(pad_x + text_advance + icon_gap + icon_size + pad_x, available_w)
        container_w = max(container_h, container_w)
        container_rect = QRectF(
            name_rect.x() + border_left,
            name_rect.y() + border_top,
            container_w,
            max(1.0, container_h),
        )

        scaled_arrow = None
        arrow_rect = QRectF()
        arrow_pix = self.dropdown_arrow_pix
        if arrow_pix and not arrow_pix.isNull():
            scaled_arrow = self.scaled_pixmap(arrow_pix, icon_size, icon_size)
            if scaled_arrow and not scaled_arrow.isNull():
                arrow_w, arrow_h = self.logical_size(scaled_arrow)
                arrow_x = container_rect.x() + pad_x + text_advance + icon_gap
                if arrow_x + arrow_w <= container_rect.x() + container_rect.width() - 3.0:
                    arrow_y = container_rect.y() + max(0.0, (container_rect.height() - arrow_h) / 2.0)
                    arrow_rect = QRectF(arrow_x, arrow_y, arrow_w, arrow_h)

        return container_rect, scaled_arrow, arrow_rect, title_elided

    def _track_name_path(self, rect: QRectF) -> QPainterPath:
        r = QRectF(rect)
        radius_tl = max(0.0, float(self.name_radius_tl or 0.0))
        radius_bl = max(0.0, float(self.name_radius_bl or 0.0))
        radius_tl = min(radius_tl, r.height() / 2.0)
        radius_bl = min(radius_bl, r.height() / 2.0)
        path = QPainterPath()
        if radius_tl <= 0.0 and radius_bl <= 0.0:
            path.addRect(r)
            return path
        path.moveTo(r.x() + radius_tl, r.y())
        path.lineTo(r.right(), r.y())
        path.lineTo(r.right(), r.bottom())
        path.lineTo(r.x() + radius_bl, r.bottom())
        if radius_bl > 0.0:
            path.quadTo(r.x(), r.bottom(), r.x(), r.bottom() - radius_bl)
        else:
            path.lineTo(r.x(), r.bottom())
        if radius_tl > 0.0:
            path.lineTo(r.x(), r.y() + radius_tl)
            path.quadTo(r.x(), r.y(), r.x() + radius_tl, r.y())
        else:
            path.lineTo(r.x(), r.y())
        path.closeSubpath()
        return path

    def paint_background(self, painter: QPainter):
        area = QRectF(
            self.w.track_name_width,
            self.w.ruler_height,
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        painter.save()
        painter.setClipRect(area)
        banding_cfg = self._frame_banding_config()
        for track_rect, track, _name_rect in self.w.geometry.iter_tracks():
            vis = track_rect.intersected(area)
            if vis.isNull():
                continue
            locked = bool((track.data if isinstance(track.data, dict) else {}).get("lock"))
            bg = QColor(self.w.theme.track.background)
            bg2 = QColor(self.w.theme.track.background2)
            border_color = QColor(self.w.theme.track.border_color)
            if locked:
                bg = self.dimmed_color(bg)
                if bg2.isValid():
                    bg2 = self.dimmed_color(bg2)
                border_color = self.dimmed_color(border_color)
            if bg2.isValid() and bg2 != bg:
                grad = QLinearGradient(QPointF(vis.topLeft()), QPointF(vis.bottomLeft()))
                grad.setColorAt(0, bg)
                grad.setColorAt(1, bg2)
                painter.fillRect(vis, QBrush(grad))
            else:
                painter.fillRect(vis, bg)
            if banding_cfg:
                per_track_cfg = banding_cfg
                if locked:
                    per_track_cfg = dict(banding_cfg)
                    per_track_cfg["color"] = self.dimmed_color(QColor(banding_cfg.get("color")))
                self._paint_frame_banding(painter, vis, per_track_cfg)
            border_pen = QPen(border_color)
            border_pen.setCosmetic(True)
            painter.setPen(border_pen)
            painter.drawLine(vis.topLeft(), vis.topRight())
            painter.drawLine(vis.bottomLeft(), vis.bottomRight())
            painter.drawLine(vis.topRight(), vis.bottomRight())

        painter.fillRect(
            self.w.resize_handle_rect.intersected(area),
            self.w.theme.track.border_color,
        )
        timeline_handle = self.w.geometry.timeline_handle_rect()
        if timeline_handle and not timeline_handle.isNull():
            handle_rect = timeline_handle.intersected(area)
            if not handle_rect.isNull():
                painter.fillRect(handle_rect, self.w.theme.track.border_color)
                inner = QRectF(handle_rect)
                inner.adjust(1.0, 1.0, -1.0, -1.0)
                if inner.width() > 0 and inner.height() > 0:
                    accent = QColor(self.w.theme.track.name_background)
                    accent.setAlpha(180)
                    painter.fillRect(inner, accent)
        painter.restore()

    def _frame_banding_config(self):
        pps = float(getattr(self.w, "pixels_per_second", 0.0) or 0.0)
        fps = float(getattr(self.w, "fps_float", 0.0) or 0.0)
        if pps <= 0.0 or fps <= 0.0:
            return None
        ruler = getattr(self.w, "ruler_painter", None)
        if not ruler:
            return None
        try:
            fpt = ruler._frames_per_tick(pps, fps)
        except Exception:
            return None
        if fpt > 2.0:
            return None
        pixels_per_frame = pps / fps if fps else 0.0
        if pixels_per_frame <= 0.0:
            return None
        base_color = QColor(self.w.theme.track.background)
        if not base_color.isValid():
            return None
        if base_color.lightness() < 128:
            band_color = base_color.lighter(125)
        else:
            band_color = base_color.darker(110)
        band_color.setAlpha(min(220, max(120, band_color.alpha())))
        return {
            "pps": pps,
            "fps": fps,
            "fpt": fpt,
            "pixels_per_frame": pixels_per_frame,
            "offset_px": float(getattr(self.w, "h_scroll_offset", 0.0) or 0.0),
            "color": band_color,
        }

    def _paint_frame_banding(self, painter: QPainter, rect: QRectF, cfg):
        pixels_per_frame = cfg.get("pixels_per_frame", 0.0)
        if pixels_per_frame <= 0.0:
            return
        pps = cfg.get("pps", 0.0)
        fps = cfg.get("fps", 0.0)
        if pps <= 0.0 or fps <= 0.0:
            return
        offset_px = cfg.get("offset_px", 0.0)
        # Convert visible rect to absolute timeline pixel positions
        left_px = offset_px + max(0.0, rect.left() - self.w.track_name_width)
        right_px = offset_px + max(0.0, rect.right() - self.w.track_name_width)
        if right_px <= left_px:
            return
        start_seconds = left_px / pps
        end_seconds = right_px / pps
        if end_seconds <= start_seconds:
            return

        # Use a small epsilon when converting to frame numbers so that
        # fractional floating point rounding errors don't cause the
        # computed frame parity to jitter as we scroll horizontally.
        eps = 1e-9
        start_frame = int(math.floor(start_seconds * fps + eps))
        end_frame = int(math.ceil(end_seconds * fps - eps))
        if end_frame <= start_frame:
            end_frame = start_frame + 1
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(cfg.get("color"))
        # Ensure we do not draw excessive rectangles
        max_frames = end_frame - start_frame
        if max_frames > 2000:
            max_frames = 2000
            end_frame = start_frame + max_frames
        for frame in range(start_frame, end_frame):
            if frame % 2 != 0:
                continue
            t = frame / fps
            x = self.w.track_name_width + t * pps - offset_px
            band_rect = QRectF(x, rect.top(), pixels_per_frame, rect.height())
            band_rect = band_rect.intersected(rect)
            if band_rect.width() <= 0.0:
                continue
            painter.drawRect(band_rect)
        painter.restore()

    def paint_names(self, painter: QPainter):
        area = QRectF(
            0,
            self.w.ruler_height,
            self.w.track_name_width,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        painter.save()
        painter.setClipRect(area)
        self.w._track_title_rects = []
        original_font = painter.font()
        track_font = QFont(original_font)
        if track_font.pixelSize() > 0:
            track_font.setPixelSize(track_font.pixelSize() + 1)
        elif track_font.pointSizeF() > 0:
            track_font.setPointSizeF(track_font.pointSizeF() + 1.0)
        painter.setFont(track_font)
        for _track_rect, track, name_rect in self.w.geometry.iter_tracks():
            locked = bool((track.data if isinstance(track.data, dict) else {}).get("lock"))
            name_bg = QColor(self.w.theme.track.name_background)
            name_border_top = QColor(self.name_border_top_color)
            name_border_bottom = QColor(self.name_border_bottom_color)
            name_border = QColor(self.name_border_color)
            text_color = QColor(self.w.theme.track.font_color)
            if locked:
                name_bg = self.dimmed_color(name_bg)
                name_border_top = self.dimmed_color(name_border_top)
                name_border_bottom = self.dimmed_color(name_border_bottom)
                name_border = self.dimmed_color(name_border)
                text_color = self.dimmed_color(text_color)
            painter.setPen(Qt.NoPen)
            painter.setBrush(name_bg)
            path = self._track_name_path(name_rect)
            painter.drawPath(path)

            # Match JS .track_top overlay (light-to-transparent).
            overlay_top = QColor(self.name_top_overlay)
            overlay_bottom = QColor(self.name_top_overlay2)
            if overlay_top.isValid() or overlay_bottom.isValid():
                if not overlay_top.isValid() and overlay_bottom.isValid():
                    overlay_top = QColor(overlay_bottom)
                if not overlay_bottom.isValid() and overlay_top.isValid():
                    overlay_bottom = QColor(overlay_top)
                    overlay_bottom.setAlpha(0)
                if locked:
                    overlay_top = self.dimmed_color(overlay_top)
                    overlay_bottom = self.dimmed_color(overlay_bottom)
                grad = QLinearGradient(QPointF(name_rect.topLeft()), QPointF(name_rect.bottomLeft()))
                grad.setColorAt(0.0, overlay_top)
                grad.setColorAt(1.0, overlay_bottom)
                painter.save()
                painter.setClipPath(path)
                painter.fillRect(name_rect, QBrush(grad))
                painter.restore()
            painter.setBrush(Qt.NoBrush)

            painter.save()
            painter.setClipPath(path)
            radius_tl = max(0.0, float(self.name_radius_tl or 0.0))
            radius_bl = max(0.0, float(self.name_radius_bl or 0.0))
            if self.name_border_top_width:
                top_rect = QRectF(
                    name_rect.x() + radius_tl,
                    name_rect.y(),
                    max(0.0, name_rect.width() - radius_tl),
                    self.name_border_top_width,
                )
                painter.fillRect(top_rect, name_border_top)
            if self.name_border_bottom_width:
                bottom_rect = QRectF(
                    name_rect.x() + radius_bl,
                    name_rect.bottom() - self.name_border_bottom_width,
                    max(0.0, name_rect.width() - radius_bl),
                    self.name_border_bottom_width,
                )
                painter.fillRect(bottom_rect, name_border_bottom)
            if self.name_border_width:
                left_rect = QRectF(
                    name_rect.x(),
                    name_rect.y() + radius_tl,
                    self.name_border_width,
                    max(
                        0.0,
                        name_rect.height()
                        - radius_tl
                        - radius_bl,
                    ),
                )
                painter.fillRect(left_rect, name_border)

            # Preserve curved left-corner border strokes on rounded track names.
            if radius_tl > 0.0 and self.name_border_top_width and name_border_top.isValid():
                pen = QPen(name_border_top, float(self.name_border_top_width))
                pen.setCapStyle(Qt.FlatCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                arc = QRectF(
                    name_rect.x(),
                    name_rect.y(),
                    radius_tl * 2.0,
                    radius_tl * 2.0,
                )
                painter.drawArc(arc, 90 * 16, 90 * 16)
            if radius_bl > 0.0 and self.name_border_bottom_width and name_border_bottom.isValid():
                pen = QPen(name_border_bottom, float(self.name_border_bottom_width))
                pen.setCapStyle(Qt.FlatCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                arc = QRectF(
                    name_rect.x(),
                    name_rect.bottom() - (radius_bl * 2.0),
                    radius_bl * 2.0,
                    radius_bl * 2.0,
                )
                painter.drawArc(arc, 180 * 16, 90 * 16)
            painter.restore()

            metrics = painter.fontMetrics()
            text_height = float(metrics.height()) if metrics else 0.0
            text_top = name_rect.y() + self.menu_margin
            text_bottom_limit = name_rect.bottom() - self.menu_margin
            if text_height > 0.0 and text_top + text_height > text_bottom_limit:
                text_height = max(0.0, text_bottom_limit - text_top)

            title_rect, scaled_arrow, arrow_rect, title_elided = self.track_title_geometry(
                name_rect,
                track,
                painter=painter,
            )
            title_w = title_rect.width() if not title_rect.isNull() else 0.0
            if not title_rect.isNull():
                if title_elided:
                    flags = Qt.AlignLeft | Qt.AlignTop
                    pad_x = 6.0
                    pad_y = 2.0
                    text_draw_rect = QRectF(
                        title_rect.x() + pad_x,
                        title_rect.y() + pad_y,
                        max(0.0, arrow_rect.x() - (title_rect.x() + pad_x + 4.0)) if not arrow_rect.isNull() else max(0.0, title_rect.width() - pad_x * 2.0),
                        max(1.0, title_rect.height() - pad_y * 2.0),
                    )
                    painter.setPen(text_color)
                    painter.drawText(text_draw_rect, flags, title_elided)
                if scaled_arrow and not arrow_rect.isNull():
                    painter.drawPixmap(arrow_rect.topLeft(), scaled_arrow)
                self.w._track_title_rects.append(
                    {
                        "rect": QRectF(title_rect),
                        "track": track,
                        "title": str(title_elided or self.w._track_display_label(track) or ""),
                        "open_menu": True,
                    }
                )

            buttons = self.w._track_toolbar_buttons(track, name_rect)
            text_offset = self.name_border_width + self.menu_margin
            right_padding = self.name_border_width + self.menu_margin
            if title_w > 0.0:
                text_offset = max(text_offset, (title_rect.x() - name_rect.x()) + title_rect.width() + self.menu_margin)
            text_width = max(0.0, name_rect.width() - text_offset - right_padding)
            text_rect_height = text_height if text_height > 0.0 else max(0.0, name_rect.height() - self.menu_margin * 2)
            text_bottom = min(text_top + text_rect_height, text_bottom_limit)
            text_rect = QRectF(
                name_rect.x() + text_offset,
                text_top,
                text_width,
                max(0.0, text_bottom - text_top),
            )
            painter.setPen(text_color)
            if title_rect.isNull() and text_rect.width() > 0.0 and text_rect.height() > 0.0:
                painter.drawText(
                    text_rect,
                    Qt.AlignLeft | Qt.AlignTop,
                    self.w._track_display_label(track)
                )

            hover_key = getattr(self.w, "_toolbar_hover_key", None)
            pressed_key = getattr(self.w, "_toolbar_pressed_key", None)
            pressed_inside = getattr(self.w, "_toolbar_pressed_inside", False)
            for button in buttons:
                button_key = (button.get("track_id"), button.get("key"))
                pix = self.w._toolbar_button_pixmap(
                    track,
                    button,
                    hovered=hover_key == button_key,
                    pressed=pressed_key == button_key and pressed_inside,
                )
                if not pix:
                    continue
                painter.save()
                if locked:
                    painter.setOpacity(0.8)
                default_margin = float(getattr(self, "toggle_margin", 0.0) or 0.0)
                margin_x = button.get("margin_x", button.get("margin", default_margin))
                margin_y = button.get("margin_y", button.get("margin", default_margin))
                draw_x = button["rect"].x() + margin_x
                draw_y = button["rect"].y() + margin_y
                painter.drawPixmap(QPointF(draw_x, draw_y), pix)
                painter.restore()
        painter.setFont(original_font)
        painter.restore()
