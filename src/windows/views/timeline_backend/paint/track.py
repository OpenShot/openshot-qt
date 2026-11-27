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
    QPixmap,
)

from .base import BasePainter
from .header import draw_effect_badge, effect_badge_label, header_control_center
from classes.qt_types import font_metrics_horizontal_advance


def paint_track_divider(painter, widget, hovered=False):
    """Paint one opaque, quiet divider entirely inside the fixed header."""
    color = QColor(widget.theme.track.border_color)
    if not color.isValid():
        color = QColor(widget.theme.track.name_background)
    color.setAlpha(255)
    if hovered:
        color = color.lighter(110) if color.lightness() < 128 else color.darker(105)
    top = float(widget.ruler_height)
    width = 4.0
    painter.fillRect(QRectF(
        max(0.0, widget.track_name_width - width), top,
        min(width, widget.track_name_width),
        max(0.0, widget.height() - widget.scroll_bar_thickness - top),
    ), color)


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
        arrow = (getattr(self.w.theme.track, "menu_icon", None)
                 or _theme_icon("themes/cosmic/images/dropdown-arrow.svg"))
        self.dropdown_arrow_pix = arrow if (arrow and not arrow.isNull()) else None
        self.menu_margin = self.w.theme.menu_margin
        self.toggle_off_pix = None
        self.toggle_on_pix = None
        def _scaled_toggle(pixmap, idle=False):
            if not pixmap or pixmap.isNull():
                return None
            # Header controls keep the same visual scale at every track height.
            width = height = self.w.theme.track_control_size
            scaled = self.scaled_pixmap(pixmap, width, height)
            if scaled is None:
                return None
            # Legacy theme SVGs have baked-in colors. Use the same palette as
            # the speaker, eye and FX controls rather than mixing icon sets.
            tinted = QPixmap(scaled.size())
            tinted.setDevicePixelRatio(scaled.devicePixelRatioF())
            tinted.fill(Qt.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(QPointF(0, 0), scaled)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            color = QColor(self.w.theme.track_control_color)
            if idle:
                color.setAlphaF(0.65)
            painter.fillRect(tinted.rect(), color)
            painter.end()
            return tinted

        if self.w.theme.keyframe_toggle_off_icon:
            self.toggle_off_pix = _scaled_toggle(
                self.w.theme.keyframe_toggle_off_icon, idle=True
            )
        if self.w.theme.keyframe_toggle_on_icon:
            self.toggle_on_pix = _scaled_toggle(
                self.w.theme.keyframe_toggle_on_icon
            )
        self.toggle_margin = self.w.theme.menu_margin

        self.toolbar_order = (
            "mute-toggle",
            "visibility-toggle",
            "effects-tray",
            "keyframe-panel",
            "lock-toggle",
            "more-controls",
        )

        toolbar = {
            "mute-toggle": self.output_button_pixmaps("audio"),
            "visibility-toggle": self.output_button_pixmaps("video"),
            "more-controls": self.output_button_pixmaps("more"),
        }

        keyframe_disabled = _scaled_toggle(
            getattr(self.w.theme, "track_keyframe_panel_disabled_icon", None)
            or self.w.theme.keyframe_toggle_off_icon, idle=True
        )
        keyframe_enabled = _scaled_toggle(
            getattr(self.w.theme, "track_keyframe_panel_enabled_icon", None)
            or self.w.theme.keyframe_toggle_on_icon
        )
        keyframe_hide_disabled = _scaled_toggle(
            getattr(self.w.theme, "track_keyframe_panel_hide_disabled_icon", None), idle=True
        ) or keyframe_disabled
        keyframe_hide_enabled = _scaled_toggle(
            getattr(self.w.theme, "track_keyframe_panel_hide_enabled_icon", None)
        ) or keyframe_enabled
        if keyframe_disabled or keyframe_enabled:
            toolbar["keyframe-panel"] = {
                # Default pixmaps also provide the toolbar button dimensions.
                "disabled": keyframe_disabled,
                "enabled": keyframe_enabled or keyframe_disabled,
                "show": {
                    "disabled": keyframe_disabled,
                    "enabled": keyframe_enabled or keyframe_disabled,
                },
                "hide": {
                    "disabled": keyframe_hide_disabled,
                    "enabled": keyframe_hide_enabled or keyframe_hide_disabled,
                },
            }
            if not self.toggle_off_pix:
                self.toggle_off_pix = keyframe_disabled
            if not self.toggle_on_pix:
                self.toggle_on_pix = keyframe_enabled or keyframe_disabled

        lock_locked_disabled = _scaled_toggle(getattr(self.w.theme, "track_locked_disabled_icon", None), idle=True)
        lock_locked_enabled = _scaled_toggle(getattr(self.w.theme, "track_locked_enabled_icon", None))
        lock_unlocked_disabled = _scaled_toggle(getattr(self.w.theme, "track_unlocked_disabled_icon", None), idle=True)
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

        self._effect_button_pixmaps = {}
        toolbar["effects-tray"] = self.effect_button_pixmaps()
        self.toolbar_pixmaps = toolbar
        # Clip controls sit on media under a dark scrim in every theme.
        self.clip_output_pixmaps = {
            key: self.output_button_pixmaps(kind, QColor("white"))["active"]
            for key, kind in (("mute-toggle", "audio"), ("visibility-toggle", "video"))
        }

    def output_button_pixmaps(self, kind, color_override=None):
        """Theme-colored vector controls, with a persistent crossed-out disabled state."""
        size = max(12, round(self.w.theme.track_control_size))
        if kind == "more":
            size = 10
        states = {}
        for state in ("disabled", "enabled", "active", "active-hovered"):
            active = state.startswith("active")
            color = QColor(color_override if color_override is not None else self.w.theme.track_control_color)
            if not color.isValid():
                color = QColor(self.w.theme.track.font_color)
            # The crossed-out glyph conveys mute/hidden without a warning hue.
            if state == "disabled":
                color.setAlphaF(0.65)
            pix = QPixmap(size * 2, size * 2)
            pix.setDevicePixelRatio(2)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.scale(size / 16.0, size / 16.0)
            painter.setPen(QPen(color, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            if kind == "more":
                path.moveTo(4, 2)
                path.lineTo(11, 8)
                path.lineTo(4, 14)
                painter.drawPath(path)
            elif kind == "audio":
                path.moveTo(2, 6)
                path.lineTo(5, 6)
                path.lineTo(8, 3)
                path.lineTo(8, 13)
                path.lineTo(5, 10)
                path.lineTo(2, 10)
                path.closeSubpath()
                painter.drawPath(path)
                if not active:
                    path = QPainterPath()
                    path.moveTo(11, 5)
                    path.quadTo(14, 8, 11, 11)
                    painter.drawPath(path)
            else:
                path.moveTo(1, 8)
                path.cubicTo(5, 2, 11, 2, 15, 8)
                path.cubicTo(11, 14, 5, 14, 1, 8)
                painter.drawPath(path)
                painter.drawEllipse(QRectF(6, 6, 4, 4))
            if active and kind != "more":
                painter.drawLine(QPointF(2, 14), QPointF(14, 2))
            painter.end()
            states[state] = pix
        return states

    def effect_button_pixmaps(self, count=0):
        label = effect_badge_label(count)
        cached = self._effect_button_pixmaps.get(label)
        if cached:
            return cached

        size = max(12, round(self.w.theme.track_control_size))
        accent = QColor(self.w.theme.track_control_color)
        if not accent.isValid():
            accent = QColor(self.w.theme.track.font_color)
        font = QFont(self.w.font())
        font.setBold(True)
        font.setPixelSize(max(8, round(size * 0.57)))
        width = max(size, font_metrics_horizontal_advance(QFontMetrics(font), label) + 6) if count > 1 else size
        states = {}
        for state, opacity in (("disabled", 0.0), ("enabled", 0.14), ("populated", 0.0),
                               ("active", 0.0), ("active-hovered", 0.49)):
            badge = QPixmap(width * 2, size * 2)
            badge.setDevicePixelRatio(2)
            badge.fill(Qt.transparent)
            painter = QPainter(badge)
            text_color = QColor(accent)
            if state in ("disabled", "populated"):
                text_color.setAlphaF(0.55)
            outline = text_color if state == "disabled" else accent
            draw_effect_badge(
                painter, QRectF(0.5, 0.5, width - 1, size - 1), font, label, outline, text_color, opacity
            )
            painter.end()
            states[state] = badge
        self._effect_button_pixmaps[label] = states
        return states

    def header_font(self, track=None):
        font = QFont(self.w.font())
        scale = getattr(self.w.theme, "label_font_scale", 1.0)
        if font.pixelSize() > 0:
            font.setPixelSize(max(1, round((font.pixelSize() + 1) * scale)))
        else:
            font.setPointSizeF(max(1.0, (font.pointSizeF() + 1.0) * scale))
        max_height = max(8.0, min(18.0, self.w.theme.track.height - 6.0))
        height = QFontMetrics(font).height()
        if height > max_height:
            factor = max_height / height
            if font.pixelSize() > 0:
                font.setPixelSize(max(1, int(font.pixelSize() * factor)))
            else:
                font.setPointSizeF(max(1.0, font.pointSizeF() * factor))
        if track is not None and track.data.get("number") == getattr(self.w, "_asset_target_layer", None):
            font.setBold(True)
        return font

    def track_title_width(self, track):
        metrics = QFontMetrics(self.header_font(track))
        text = font_metrics_horizontal_advance(metrics, self.w._track_display_label(track))
        # The same padding, dropdown, and gap used by track_title_geometry.
        return text + 12.0 + 4.0 + max(8.0, metrics.height() - 2.0) + self.name_border_width + 2.0

    def track_title_geometry(self, name_rect, track=None, *, painter=None):
        if name_rect.isNull() or name_rect.width() <= 0.0 or name_rect.height() <= 0.0:
            return QRectF(), None, QRectF(), ""

        name_rect = QRectF(name_rect)
        name_rect.setHeight(min(name_rect.height(), self.w.theme.track.height))
        metrics = QFontMetrics(self.header_font(track))
        font_h = float(metrics.height()) if metrics is not None else max(12.0, name_rect.height() - 4.0)
        pad_x = 6.0
        pad_y = 2.0
        icon_gap = 4.0
        border_left = float(self.name_border_width or 0.0)
        border_top = float(self.name_border_top_width or 0.0)
        border_bottom = float(self.name_border_bottom_width or 0.0)
        available_w = max(0.0, name_rect.width() - border_left)
        if track is not None:
            buttons = self.w._track_toolbar_buttons(track, name_rect)
            if buttons:
                available_w = max(0.0, min(b["rect"].left() for b in buttons)
                                  - name_rect.x() - border_left - 2.0)
        available_h = max(1.0, name_rect.height() - border_top - border_bottom)
        container_h = min(available_h, font_h + pad_y * 2.0)
        icon_size = max(8.0, font_h - 2.0)
        label = self.w._track_display_label(track) if track is not None else ""

        text_advance = 0.0
        title_elided = ""
        if metrics is not None:
            avail_text_w = int(max(0.0, available_w - pad_x * 2.0 - icon_gap - icon_size))
            minimum_label = min(font_metrics_horizontal_advance(metrics, label),
                                font_metrics_horizontal_advance(metrics, label[:3] + "…"))
            if avail_text_w >= minimum_label:
                title_elided = metrics.elidedText(label, Qt.ElideRight, avail_text_w)
                if title_elided:
                    text_advance = float(font_metrics_horizontal_advance(metrics, title_elided))

        if available_w <= 0.0:
            return QRectF(), None, QRectF(), ""
        if text_advance <= 0.0:
            # Keep the menu centered on the same row after the label disappears.
            icon_size = min(icon_size, max(0.0, available_w - 4.0))
            pad_x = 2.0
            icon_gap = 0.0
        container_w = min(pad_x + text_advance + icon_gap + icon_size + pad_x, available_w)
        container_rect = QRectF(
            name_rect.x() + border_left,
            name_rect.y() + header_control_center(name_rect.height()) - container_h / 2.0,
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
                if arrow_x + arrow_w <= container_rect.right() + 0.01:
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

    def paint_divider(self, painter: QPainter):
        paint_track_divider(painter, self.w)

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
        for _track_rect, track, name_rect in self.w.geometry.iter_tracks():
            painter.setFont(self.header_font(track))
            locked = bool((track.data if isinstance(track.data, dict) else {}).get("lock"))
            name_bg = self.focus_background(self.w.theme.track.name_background)
            name_border_top = QColor(self.name_border_top_color)
            name_border_bottom = QColor(self.name_border_bottom_color)
            name_border = QColor(self.name_border_color)
            text_color = QColor(self.w.theme.track.font_color)
            if not self.w.hasFocus():
                # Fade text toward its header background in both light and dark
                # themes. The background's three-level dim is too subtle here.
                text_color.setAlphaF(text_color.alphaF() * 0.75)
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
                pen.setJoinStyle(Qt.RoundJoin)
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
                pen.setJoinStyle(Qt.RoundJoin)
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
                        "title": str(self.w._track_display_label(track) or ""),
                        "open_menu": True,
                    }
                )

            buttons = self.w._track_toolbar_buttons(track, name_rect)
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
