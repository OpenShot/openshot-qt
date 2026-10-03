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

from qt_api import QRectF, Qt, QFont, QFontMetrics, QColor, QPainter, QPainterPath, QPen
from classes.qt_types import font_metrics_horizontal_advance


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
        if getattr(getattr(self.w, "theme", None), "compact_track_headers", False):
            max_height = max(8.0, inner.height() - 4.0)
            font_height = QFontMetrics(font).height()
            if font_height > max_height:
                factor = max_height / font_height
                if font.pixelSize() > 0:
                    font.setPixelSize(max(1, int(font.pixelSize() * factor)))
                else:
                    font.setPointSizeF(max(1.0, font.pointSizeF() * factor))
        painter.setFont(font)
        text = self._draw_item_text(
            painter, item, header, header.left(), header.right(),
            visible_width=header.width(), icon_entries=icons,
            transparent_container=isinstance(audio, list) and len(audio) > 1,
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

        metrics = QFontMetrics(painter.font())
        font_h = float(metrics.height())

        pad_x = 6.0
        pad_y = 2.0
        container_h = font_h + pad_y * 2.0
        icon_size = max(8.0, font_h - 2.0)
        icon_gap = 4.0

        # --- Effect badge sizing ---
        effects = item.data.get("effects", []) if self.header_kind == "clip" and isinstance(item.data, dict) else []
        effects = [e for e in effects if isinstance(e, dict)] if isinstance(effects, list) else []

        badge_font = QFont(painter.font())
        if badge_font.pointSizeF() > 0:
            badge_font.setPointSizeF(max(7.0, badge_font.pointSizeF() * 0.8))
        badge_fm = QFontMetrics(badge_font)
        badge_h = max(10.0, min(container_h - pad_y * 2.0, font_h))

        raw_badge_infos = []
        for eff in effects:
            label = (eff.get("type") or eff.get("effect") or eff.get("name") or eff.get("class_name") or "?")
            letter = label.strip()[0].upper() if isinstance(label, str) and label.strip() else "?"
            tw = float(font_metrics_horizontal_advance(badge_fm, letter))
            bw = max(tw + 6.0, badge_h)
            raw_badge_infos.append((eff, letter, bw))

        compact_w = pad_x + icon_size + pad_x
        min_visible = float(getattr(self.w.theme.clip, "thumb_min_visible", 5.0) or 5.0)
        item_min = float(getattr(self.w.theme.clip, "thumb_clip_min_width", 24.0) or 24.0)
        compact_lod_w = max(compact_w, min_visible * 2.0, item_min)
        visible_item_w = float(visible_width if visible_width is not None else inner.width())

        # --- LOD: two phases as clip narrows ---
        #
        # Phase 1 (all badges fit + arrow): keep ALL badges, shrink text
        #   [b1 b2] [full title]  [arrow]
        #   [b1 b2] [elided...]   [arrow]
        #   [b1 b2] [T...]        [arrow]
        #   [b1 b2]               [arrow]   ← text gone, badges still there
        #
        # Phase 2 (all badges no longer fit): drop badges from the right, no text
        #   [b1]                  [arrow]
        #                         [arrow]   ← compact
        #                                   ← None (too narrow)

        if raw_badge_infos:
            all_used_w = (
                sum(bw for _, _, bw in raw_badge_infos)
                + self.menu_margin * (len(raw_badge_infos) - 1)
            )
        else:
            all_used_w = 0.0

        # "All badges fit" means all badges + arrow fit with zero text
        all_badges_fit = (
            not raw_badge_infos
            or pad_x + all_used_w + 2.0 * icon_gap + icon_size + pad_x <= text_width
        )

        badge_infos = []
        badges_prefix_w = 0.0
        title_elided = ""
        text_advance = 0.0
        container_w = compact_w
        mode = "compact"

        if all_badges_fit:
            # Phase 1: keep all badges; text fills whatever space remains
            badge_infos = list(raw_badge_infos)
            badges_prefix_w = (all_used_w + icon_gap) if badge_infos else 0.0
            avail_text_w = int(text_width - pad_x * 2.0 - badges_prefix_w - icon_gap - icon_size)
            if avail_text_w >= 4:
                title_elided = metrics.elidedText(title_raw, Qt.ElideRight, avail_text_w)
                if title_elided:
                    text_advance = float(font_metrics_horizontal_advance(metrics, title_elided))

            if badge_infos or text_advance > 0:
                container_w = min(
                    pad_x + badges_prefix_w + text_advance + icon_gap + icon_size + pad_x,
                    text_width,
                )
                container_w = max(container_h, container_w)
                mode = "full"
            elif compact_w <= text_width and compact_lod_w <= visible_item_w:
                mode = "compact"
            else:
                return None

        else:
            # Phase 2: drop badges from the right until arrow fits, then compact/none
            for n in range(len(raw_badge_infos) - 1, 0, -1):
                used_w = (
                    sum(bw for _, _, bw in raw_badge_infos[:n])
                    + self.menu_margin * (n - 1)
                )
                if pad_x + used_w + 2.0 * icon_gap + icon_size + pad_x <= text_width:
                    badge_infos = list(raw_badge_infos[:n])
                    badges_prefix_w = used_w + icon_gap
                    break

            if badge_infos:
                container_w = min(
                    pad_x + badges_prefix_w + icon_gap + icon_size + pad_x,
                    text_width,
                )
                container_w = max(container_h, container_w)
                mode = "full"
            elif compact_w <= text_width and compact_lod_w <= visible_item_w:
                mode = "compact"
            else:
                return None

        container_x = inner.x()
        container_y = inner.y()
        container_rect = QRectF(container_x, container_y, container_w, container_h)

        radius = min(4.0, container_rect.width() / 2.0, container_rect.height() / 2.0)
        path = QPainterPath()
        path.addRoundedRect(container_rect, radius, radius)
        if not transparent_container:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.fillPath(path, QColor(0, 0, 0, 140))
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
        if mode == "full":
            # Draw effect badges left of the title text
            if badge_infos:
                selected_ids = set()
                if hasattr(self.w, "_selected_effect_ids"):
                    selected_ids = self.w._selected_effect_ids()
                original_font = painter.font()
                badge_x = container_x + pad_x
                badge_y = container_y + (container_h - badge_h) / 2.0
                for eff, letter, bw in badge_infos:
                    badge_rect = QRectF(badge_x, badge_y, bw, badge_h)
                    color = self.w._effect_color(eff)
                    if not isinstance(color, QColor) or not color.isValid():
                        color = QColor("#4d7bff")
                    effect_id = eff.get("id")
                    effect_id_str = str(effect_id) if effect_id is not None else ""
                    selected = bool(eff.get("selected")) or (effect_id_str and effect_id_str in selected_ids)
                    fill = QColor(color)
                    if selected and fill.isValid():
                        fill = fill.lighter(120)
                    opacity = 1.0 if selected else 0.7
                    border = QColor(223, 223, 223) if selected else QColor(0, 0, 0, 200)
                    badge_pen = QPen(border, 1.0)
                    badge_pen.setCosmetic(True)
                    painter.save()
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    painter.setOpacity(opacity)
                    painter.setBrush(fill)
                    painter.setPen(badge_pen)
                    badge_radius = min(badge_h / 2.0, 6.0)
                    painter.drawRoundedRect(badge_rect, badge_radius, badge_radius)
                    painter.setOpacity(1.0)
                    painter.setFont(badge_font)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(badge_rect, Qt.AlignCenter, letter)
                    painter.restore()
                    if icon_entries is not None:
                        icon_entries.append({
                            "rect": QRectF(badge_rect),
                            "effect": eff,
                            "selected": selected,
                            "effect_id": effect_id_str,
                        })
                    badge_x += bw + self.menu_margin
                painter.setFont(original_font)

            # Title text after badges
            flags = Qt.AlignLeft | Qt.AlignVCenter
            text_start_x = container_x + pad_x + badges_prefix_w
            text_draw_rect = QRectF(text_start_x, container_y + pad_y, text_advance, font_h)
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

