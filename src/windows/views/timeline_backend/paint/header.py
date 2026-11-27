"""
 @file
 @brief Shared floating headers for timeline clips and transitions.
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

from classes.waveform_cache import sample_count
from qt_api import QRectF, Qt, QFont, QFontMetrics, QColor, QPainter, QPen, QLinearGradient
from classes.qt_types import font_metrics_horizontal_advance


def effect_badge_label(count):
    return f"FX {count}" if count > 1 else "FX"


def draw_effect_badge(painter, rect, font, label, accent, text_color, opacity):
    """Paint the same outlined badge on track headers and clip titles."""
    fill = QColor(accent)
    fill.setAlphaF(opacity)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setFont(font)
    painter.setBrush(fill)
    painter.setPen(QPen(accent, 1))
    radius = min(4.0, rect.height() / 4)
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    painter.setPen(text_color)
    painter.drawText(rect, Qt.AlignCenter, label)
    painter.restore()


def header_control_center(height):
    """One control line for track names, toolbar icons, and clip headers.

    A 22-pixel row starts four pixels below the top on taller tracks;
    short tracks center the same row without pushing controls outside them.
    """
    return min(max(0.0, float(height)) / 2.0, 15.0)


class ItemHeaderMixin:
    """One viewport placement and rendering path for clip and transition controls."""

    def _header_title(self, item):
        data = item.data if isinstance(item.data, dict) else {}
        return str(data.get("title", "") or "")

    def _draw_item_header(self, painter, item, full_rect, area, *, register_hits=True):
        """Keep controls inside the visible item without moving its true edges."""
        bw = float(self.border_width or 0.0)
        inner = full_rect.adjusted(bw, bw, -bw, -bw)
        visible = inner.intersected(area)
        if visible.isEmpty():
            return
        # A little space before a pinned header leaves media visible beneath it
        # and distinguishes the floating controls from the offscreen trim edge.
        if inner.left() < area.left():
            visible.setLeft(visible.left() + 6.0)
        if visible.width() <= 4.0:
            return
        header = QRectF(visible.left(), inner.top(), visible.width(), inner.height())
        data = item.data if isinstance(item.data, dict) else {}
        ui = data.get("ui", {})
        audio = ui.get("audio_data") if self.header_kind == "clip" and isinstance(ui, dict) else None
        icons = []
        painter.save()
        painter.setClipRect(visible, Qt.IntersectClip)
        # Start from the application font, as the former QImage cache did.
        # Theme scaling keeps labels proportional without changing the ruler.
        font = QFont()
        scale = getattr(getattr(self.w, "theme", None), "label_font_scale", 1.0)
        if font.pixelSize() > 0:
            font.setPixelSize(max(1, round(font.pixelSize() * scale)))
        elif font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() * scale)
        painter.setFont(font)
        text = self._draw_item_text(
            painter, item, header, header.left(), header.right(),
            visible_width=header.width(), icon_entries=icons,
            transparent_container=sample_count(audio) > 1,
        )
        painter.restore()
        if not register_hits or getattr(item, "is_recording_preview", False):
            return
        for entry in icons:
            entry = dict(entry)
            entry["rect"] = entry["rect"].intersected(visible)
            entry["clip"] = item
            self.w._effect_icon_rects.append(entry)
        if text:
            text = {key: text[key] for key in ("rect", "title", "open_menu") if key in text}
            text["rect"] = text["rect"].intersected(visible)
            text[self.header_kind] = item
            getattr(self.w, "_%s_text_rects" % self.header_kind).append(text)

    def _draw_item_text(
        self,
        painter,
        item,
        inner,
        x,
        right,
        visible_width=None,
        icon_entries=None,
        transparent_container=False,
    ):
        text_width = right - x
        if text_width <= 0:
            return None
        title_raw = self._header_title(item)
        if text_width <= 4:
            return {"rect": QRectF(x, inner.y(), max(1.0, text_width), max(1.0, inner.height())),
                    "title": title_raw}

        font = QFont(painter.font())
        max_height = max(8.0, min(18.0, inner.height() - 4.0))
        font_height = QFontMetrics(font).height()
        if font_height > max_height:
            factor = max_height / font_height
            if font.pixelSize() > 0:
                font.setPixelSize(max(1, int(font.pixelSize() * factor)))
            else:
                font.setPointSizeF(max(1.0, font.pointSizeF() * factor))
            painter.setFont(font)
        metrics = QFontMetrics(font)
        font_h = float(metrics.height())

        pad_x = 6.0
        pad_y = 2.0
        container_h = font_h + pad_y * 2.0
        icon_size = max(8.0, font_h - 2.0)
        icon_gap = 4.0

        output_size = min(max(icon_size, float(getattr(self.w.theme, "track_control_size", 16))),
                          max(8.0, inner.height() - 4.0))
        output_badges = []
        if self.header_kind == "clip" and isinstance(item.data, dict):
            for property_name, toolbar_key in (("has_audio", "mute-toggle"),
                                               ("has_video", "visibility-toggle")):
                points = item.data.get(property_name, {}).get("Points", [])
                if points and all(point.get("co", {}).get("Y") == 0 for point in points):
                    if pad_x * 2 + (len(output_badges) + 1) * (output_size + icon_gap) + icon_size <= text_width:
                        output_badges.append((property_name, toolbar_key))
        output_prefix = len(output_badges) * (output_size + icon_gap)

        effects = item.data.get("effects", []) if self.header_kind == "clip" and isinstance(item.data, dict) else []
        effects = [effect for effect in effects if isinstance(effect, dict)] if isinstance(effects, list) else []
        badge_font = QFont(painter.font())
        badge_h = float(getattr(self.w.theme, "track_control_size", 16))
        badge_font.setPixelSize(max(8, round(badge_h * 0.57)))
        badge_font.setBold(True)
        badge_fm = QFontMetrics(badge_font)
        badge_label = ""
        badge_width = 0.0
        if effects:
            preferred = effect_badge_label(len(effects))
            labels = (preferred, "FX") if len(effects) > 1 else (preferred,)
            for candidate in labels:
                width = max(badge_h, font_metrics_horizontal_advance(badge_fm, candidate) + 6.0)
                if pad_x * 2 + output_prefix + width + icon_gap * 2 + icon_size <= text_width:
                    badge_label, badge_width = candidate, width
                    break

        compact_w = pad_x * 2 + icon_size
        if output_badges:
            container_h = max(container_h, output_size + pad_y * 2.0)
        if badge_label:
            container_h = max(container_h, badge_h + pad_y * 2.0)
        min_visible = float(getattr(self.w.theme.clip, "thumb_min_visible", 5.0) or 5.0)
        item_min = float(getattr(self.w.theme.clip, "thumb_clip_min_width", 24.0) or 24.0)
        compact_lod_w = max(compact_w, min_visible * 2.0, item_min)
        visible_item_w = float(visible_width if visible_width is not None else inner.width())
        badge_prefix = output_prefix + (badge_width + icon_gap if badge_label else 0.0)
        available = int(text_width - compact_w - badge_prefix - icon_gap)
        title_elided = metrics.elidedText(title_raw, Qt.ElideRight, available) if available >= 4 else ""
        text_advance = float(font_metrics_horizontal_advance(metrics, title_elided))
        full = bool(output_badges or badge_label or title_elided)
        if full:
            container_w = min(text_width, max(container_h, compact_w + badge_prefix + text_advance + icon_gap))
        elif compact_w <= text_width and compact_lod_w <= visible_item_w:
            container_w = compact_w
        else:
            return None

        container_x = inner.x()
        border = float(self.border_width or 0.0)
        center_y = inner.y() - border + header_control_center(inner.height() + border * 2.0)
        container_y = max(inner.top(), min(center_y - container_h / 2.0,
                                          inner.bottom() - container_h))
        container_rect = QRectF(container_x, container_y, container_w, container_h)

        if not transparent_container:
            # A floating dark pill cuts through small thumbnails. Shade the
            # top of the media instead, fading below the shared control line.
            shade = QRectF(inner.left(), inner.top(), inner.width(),
                           min(inner.height(), container_rect.bottom() - inner.top() + 6.0))
            gradient = QLinearGradient(shade.topLeft(), shade.bottomLeft())
            gradient.setColorAt(0.0, QColor(0, 0, 0, 105))
            gradient.setColorAt(0.65, QColor(0, 0, 0, 100))
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.save()
            painter.fillRect(shade, gradient)
            painter.restore()

        # Pre-scale the arrow once for both modes
        arrow_pix = self.dropdown_arrow_pix
        scaled_arrow = None
        arrow_w = arrow_h = 0.0
        if arrow_pix and not arrow_pix.isNull():
            scaled_arrow = self.scaled_pixmap(arrow_pix, icon_size, icon_size)
            if scaled_arrow and not scaled_arrow.isNull():
                arrow_w, arrow_h = self.logical_size(scaled_arrow)

        arrow_rect = QRectF()
        if full:
            for index, (property_name, toolbar_key) in enumerate(output_badges):
                output_rect = QRectF(container_x + pad_x + index * (output_size + icon_gap),
                                     container_y + (container_h - output_size) / 2,
                                     output_size, output_size)
                painter.save()
                painter.setPen(Qt.NoPen)
                background = QColor(0, 0, 0, 90)
                painter.setBrush(background)
                painter.drawRoundedRect(output_rect.adjusted(-1, -1, 1, 1), 3, 3)
                pix = self.w.track_painter.clip_output_pixmaps[toolbar_key]
                pix = self.scaled_pixmap(pix, output_size, output_size)
                painter.drawPixmap(output_rect.topLeft(), pix)
                painter.restore()
                if icon_entries is not None:
                    icon_entries.append({"rect": output_rect, "output_toggle": property_name})
            if badge_label:
                badge_rect = QRectF(container_x + pad_x + output_prefix, container_y + (container_h - badge_h) / 2,
                                    badge_width, badge_h)
                accent = QColor(getattr(self.w.theme, "track_control_color", "#91c3ff"))
                if not accent.isValid():
                    accent = QColor("#91c3ff")
                selected_ids = getattr(self.w, "_selected_effect_ids", set)()
                selected = any(effect.get("selected") or str(effect.get("id")) in selected_ids
                               for effect in effects)
                # Clip titles use a dark scrim in every theme.
                if accent.lightnessF() < 0.36:
                    accent = accent.lighter(180)
                draw_effect_badge(painter, badge_rect, badge_font, badge_label, accent, Qt.white,
                                  0.49 if selected else 0.32)
                if icon_entries is not None:
                    icon_entries.append({"rect": badge_rect, "effects": effects, "label": badge_label})

            flags = Qt.AlignLeft | Qt.AlignVCenter
            text_start_x = container_x + pad_x + badge_prefix
            text_draw_rect = QRectF(text_start_x, container_y + (container_h - font_h) / 2.0, text_advance, font_h)
            painter.setPen(QColor(0, 0, 0, 120))
            painter.drawText(text_draw_rect.translated(1, 1), flags, title_elided)
            painter.setPen(getattr(self.w.theme, self.header_kind).font_color)
            painter.drawText(text_draw_rect, flags, title_elided)

            # Arrow after text — only if it clears the container edge by ≥3px
            if scaled_arrow:
                arrow_x = text_start_x + text_advance + icon_gap
                if arrow_x + arrow_w <= container_x + container_w - 3.0:
                    arrow_y = container_y + (container_h - arrow_h) / 2.0
                    arrow_rect = QRectF(arrow_x, arrow_y, arrow_w, arrow_h)
                    painter.drawPixmap(arrow_rect.topLeft(), scaled_arrow)
        else:
            # Compact: arrow left-aligned, same position as text would be
            if scaled_arrow:
                arrow_x = container_x + pad_x
                arrow_y = container_y + (container_h - arrow_h) / 2.0
                arrow_rect = QRectF(arrow_x, arrow_y, arrow_w, arrow_h)
                painter.drawPixmap(arrow_rect.topLeft(), scaled_arrow)

        return {"rect": container_rect, "title": title_raw, "open_menu": True,
                "arrow_rect": arrow_rect, "scaled_arrow": scaled_arrow, "title_elided": title_elided}

