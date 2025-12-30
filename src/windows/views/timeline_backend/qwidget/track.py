"""
 @file
 @brief Track toolbar and menu helpers.
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

from PyQt5.QtCore import QRectF
from classes.app import get_app

TRACK_TOOLBAR_SPACING_REDUCTION = 2.0
TRACK_TOOLBAR_LEFT_SHIFT = 10.0


class TrackInteractionMixin:
    def _track_menu_rect(self, name_rect):
        if not self.track_painter.menu_pix:
            return QRectF()
        width, height = self.track_painter.logical_size(self.track_painter.menu_pix)
        return QRectF(
            name_rect.x() + self.track_painter.name_border_width + self.track_painter.menu_margin,
            name_rect.y() + self.track_painter.menu_margin,
            width,
            height,
        )

    def _track_toolbar_buttons(self, track, name_rect):
        painter = self.track_painter
        order = getattr(painter, "toolbar_order", ())
        icons = getattr(painter, "toolbar_pixmaps", {})
        if not order or not icons or name_rect.isNull():
            return []

        margin = float(getattr(painter, "toggle_margin", 0.0) or 0.0)
        border = float(getattr(painter, "name_border_width", 0.0) or 0.0)
        menu_margin = float(getattr(painter, "menu_margin", 0.0) or 0.0)
        menu_w = 0.0
        if painter.menu_pix:
            menu_w, _ = painter.logical_size(painter.menu_pix)

        track_num = self.normalize_track_number(track.data.get("number"))

        buttons = []
        specs = []

        for key in order:
            pix_info = icons.get(key)
            if not pix_info:
                continue
            if key == "lock-toggle":
                variant = pix_info.get("locked") or pix_info.get("unlocked") or {}
                base_pix = variant.get("enabled") or variant.get("disabled")
            else:
                base_pix = pix_info.get("enabled") or pix_info.get("disabled")
            if not base_pix:
                continue
            pix_w, pix_h = painter.logical_size(base_pix)
            margin_x = max(0.0, margin - TRACK_TOOLBAR_SPACING_REDUCTION)
            width = max(0.0, pix_w + margin_x * 2.0)
            icon_height = max(0.0, pix_h)
            height = max(0.0, icon_height + margin * 2.0)
            if width <= 0.0 or height <= 0.0:
                continue

            specs.append({
                "key": key,
                "track_id": track.id,
                "track_num": track_num,
                "width": width,
                "height": height,
                "margin": margin,
                "margin_x": margin_x,
                "margin_y": margin,
                "icon_height": icon_height,
                "pixmaps": pix_info,
            })

        if not specs:
            return []

        left_limit = name_rect.x() + border + menu_margin * 2.0 + menu_w
        min_left = name_rect.x() + border + menu_margin + menu_w
        left_limit = max(min_left, left_limit - TRACK_TOOLBAR_LEFT_SHIFT)
        right_limit = name_rect.right() - border - menu_margin
        if right_limit <= left_limit:
            return []

        bottom_border = float(getattr(painter, "name_border_bottom_width", 0.0) or 0.0)
        font_metrics = self.fontMetrics()
        text_height = float(font_metrics.height()) if font_metrics else 0.0
        icons_base = name_rect.y() + menu_margin + text_height + menu_margin
        min_row_top = name_rect.y() + menu_margin
        max_icon_area_bottom = name_rect.bottom() - bottom_border - menu_margin

        current_left = left_limit

        for spec in specs:
            width = spec["width"]
            if width <= 0.0:
                continue

            next_right = current_left + width
            if next_right > right_limit + 1e-6:
                if current_left > right_limit:
                    break
                available = right_limit - current_left
                if available <= 0.0:
                    break
                width = available
                margin_x = min(spec.get("margin_x", margin), width / 2.0)
                spec["margin_x"] = margin_x
                next_right = current_left + width
                spec["width"] = width

            icon_height = spec.get("icon_height", spec["height"]) or 0.0
            margin_y = spec.get("margin_y", margin)
            # Keep icons strictly below the text row (+ menu margin)
            desired_draw_y = max(icons_base, min_row_top)

            if icon_height:
                max_draw_y = max_icon_area_bottom - icon_height
                desired_draw_y = min(desired_draw_y, max_draw_y)

            top = desired_draw_y  # <-- do NOT subtract margin_y here
            bottom_limit = max_icon_area_bottom  # no extra +margin_y; keep within icon area

            height = spec["height"]
            rect_bottom = top + height
            if rect_bottom > bottom_limit:
                rect_bottom = bottom_limit
                top = rect_bottom - height

            text_bottom = name_rect.y() + menu_margin + text_height
            if top < text_bottom + menu_margin:
                top = text_bottom + menu_margin

            rect = QRectF(
                current_left,
                top,
                width,
                height,
            )
            spec["rect"] = rect
            buttons.append(spec)
            current_left = rect.right()

        return buttons

    def _track_toggle_rect(self, track, name_rect):
        buttons = self._track_toolbar_buttons(track, name_rect)
        return buttons[0]["rect"] if buttons else QRectF()

    def _get_toolbar_button(self, track_id, key):
        self.geometry.ensure()
        for _track_rect, track, name_rect in self.geometry.iter_tracks():
            if track.id != track_id:
                continue
            for button in self._track_toolbar_buttons(track, name_rect):
                if button["key"] == key:
                    info = dict(button)
                    info["track"] = track
                    info["name_rect"] = name_rect
                    return info
        return None

    def _track_toolbar_button_at(self, pos):
        self.geometry.ensure()
        for _track_rect, track, name_rect in self.geometry.iter_tracks():
            for button in self._track_toolbar_buttons(track, name_rect):
                if button["rect"].contains(pos):
                    info = dict(button)
                    info["track"] = track
                    info["name_rect"] = name_rect
                    return info
        return None

    def _toolbar_button_pixmap(self, track, button, hovered=False, pressed=False):
        pixmaps = button.get("pixmaps") or {}
        key = button.get("key")

        if key == "lock-toggle":
            locked = bool(getattr(track, "data", {}).get("lock"))
            variant = pixmaps.get("locked" if locked else "unlocked") or {}
            state = "enabled" if locked else "disabled"
            if hovered or pressed:
                state = "enabled"
            pix = variant.get(state) or variant.get("enabled") or variant.get("disabled")
            return pix

        if key == "keyframe-panel":
            track_num = button.get("track_num")
            enabled = bool(self._track_panel_enabled.get(track_num, False))
            state = "enabled" if enabled else "disabled"
            if hovered or pressed:
                state = "enabled"
            pix = pixmaps.get(state) or pixmaps.get("enabled") or pixmaps.get("disabled")
            return pix

        state = "enabled" if (hovered or pressed) else "disabled"
        pix = pixmaps.get(state) or pixmaps.get("enabled") or pixmaps.get("disabled")
        return pix

    def _find_track_by_id(self, track_id):
        for track in self.track_list:
            if getattr(track, "id", None) == track_id:
                return track
        return None

    def _toggle_track_panel(self, track_num):
        current = self._track_panel_enabled.get(track_num, False)
        new_state = not current
        self._track_panel_enabled[track_num] = new_state
        if not new_state:
            self._clear_panel_selection(track_num)
            if hasattr(self, "_panel_manual_properties"):
                self._panel_manual_properties.pop(track_num, None)
        self._update_track_panel_properties()
        self.geometry.mark_dirty()
        self.update()

    def _select_track_for_action(self, track_id):
        if not track_id or not hasattr(self.win, "selected_tracks"):
            return
        if getattr(self.win, "selected_tracks", None) != [track_id]:
            self.win.selected_tracks = [track_id]

    def _activate_track_toolbar_button(self, button):
        key = button.get("key")
        track_id = button.get("track_id")
        track_num = button.get("track_num")
        track = button.get("track") or self._find_track_by_id(track_id)

        if key == "keyframe-panel":
            if track_num is not None:
                self._toggle_track_panel(track_num)
            return

        if not self.win:
            return

        if key == "insert-above":
            action = getattr(self.win, "actionAddTrackAbove_trigger", None)
            if action and track_id:
                self._select_track_for_action(track_id)
                action()
            return

        if key == "insert-below":
            action = getattr(self.win, "actionAddTrackBelow_trigger", None)
            if action and track_id:
                self._select_track_for_action(track_id)
                action()
            return

        if key == "delete-track":
            action = getattr(self.win, "actionRemoveTrack_trigger", None)
            if action and track_id:
                self._select_track_for_action(track_id)
                action()
            return

        if key == "lock-toggle" and track_id:
            self._select_track_for_action(track_id)
            locked = bool(getattr(track, "data", {}).get("lock")) if track else False
            if locked:
                action = getattr(self.win, "actionUnlockTrack_trigger", None)
                if action:
                    action()
                if track:
                    track.data["lock"] = False
            else:
                action = getattr(self.win, "actionLockTrack_trigger", None)
                if action:
                    action()
                if track:
                    track.data["lock"] = True
            self.geometry.mark_dirty()
            self.update()

    def _update_toolbar_hover(self, pos):
        button = self._track_toolbar_button_at(pos)
        key = None
        if button:
            key = (button.get("track_id"), button.get("key"))
        if key != self._toolbar_hover_key:
            self._toolbar_hover_key = key
            self.update()

    def _update_toolbar_pressed_state(self, pos):
        if not self._toolbar_pressed_key:
            return
        button = self._get_toolbar_button(*self._toolbar_pressed_key)
        inside = bool(button and button.get("rect") and button["rect"].contains(pos))
        if inside != self._toolbar_pressed_inside:
            self._toolbar_pressed_inside = inside
            self.update()

    def _track_display_label(self, track):
        if not track or not isinstance(track.data, dict):
            return ""
        label = track.data.get("label")
        if label:
            return label
        layers = list(get_app().project.get("layers") or [])
        track_id = track.data.get("id")
        try:
            layers_sorted = sorted(layers, key=lambda item: item.get("number", 0))
        except Exception:
            layers_sorted = layers
        display_index = len(layers_sorted)
        for layer in reversed(layers_sorted):
            if layer.get("id") == track_id:
                break
            display_index -= 1
        if display_index <= 0:
            fallback_number = track.data.get("number")
            display_index = fallback_number if fallback_number not in (None, "") else 0
        if not display_index:
            display_index = 1
        _ = get_app()._tr
        return _("Track %s") % display_index

    def normalize_track_number(self, track_num):
        try:
            return int(track_num)
        except (TypeError, ValueError):
            return track_num

    def get_clip_rect_by_id(self, clip_id):
        clip_id_str = str(clip_id)
        if not clip_id_str:
            return QRectF()
        for rect, clip, _selected in self.geometry.iter_clips():
            if str(getattr(clip, "id", "")) == clip_id_str:
                return rect
        return QRectF()

    def get_transition_rect_by_id(self, transition_id):
        transition_id_str = str(transition_id)
        if not transition_id_str:
            return QRectF()
        for rect, tran, _selected in self.geometry.iter_transitions():
            if str(getattr(tran, "id", "")) == transition_id_str:
                return rect
        return QRectF()
