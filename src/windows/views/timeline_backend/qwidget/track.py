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

from qt_api import QRectF, QLocale
from classes.app import get_app

TRACK_TOOLBAR_SPACING_REDUCTION = 2.0


class TrackInteractionMixin:
    def _track_menu_rect(self, name_rect, track=None):
        for entry in reversed(getattr(self, "_track_title_rects", [])):
            entry_track = entry.get("track") if isinstance(entry, dict) else None
            entry_rect = entry.get("rect") if isinstance(entry, dict) else None
            if track is not None and entry_track is not track:
                continue
            if isinstance(entry_rect, QRectF):
                return QRectF(entry_rect)
        if not self.track_painter:
            return QRectF()
        rect, _scaled_arrow, _arrow_rect, _title = self.track_painter.track_title_geometry(name_rect, track)
        return rect

    def _track_toolbar_buttons(self, track, name_rect):
        painter = self.track_painter
        order = getattr(painter, "toolbar_order", ())
        icons = getattr(painter, "toolbar_pixmaps", {})
        if not order or not icons or name_rect.isNull():
            return []

        margin = float(getattr(painter, "toggle_margin", 0.0) or 0.0)
        track_num = self.normalize_track_number(track.data.get("number"))

        buttons = []
        specs = []

        for key in order:
            pix_info = icons.get(key)
            if key == "effects-tray":
                count = len(track.data.get("effects") or ())
                if count > 1:
                    pix_info = painter.effect_button_pixmaps(count)
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
                "icon_width": pix_w,
                "pixmaps": pix_info,
            })

        if not specs:
            return []

        # One fixed-size row at every track height, independent of expanded panels.
        row_height = min(name_rect.height(), self.theme.track.height)
        hit_size = min(22.0, max(0.0, row_height - 2.0))
        hit_width = min(hit_size, float(self.theme.track_control_size) + 4.0)
        widths = [max(hit_width, spec["icon_width"] + 4.0) if spec["key"] == "effects-tray"
                  else hit_width for spec in specs]
        controls = list(zip(specs[:-1], widths[:-1]))
        more, more_width = specs[-1], widths[-1]
        # Use the measured name width, so the divider reveals controls directly
        # after the name instead of reserving an invisible fixed-width column.
        title_width = painter.track_title_width(track) + 4.0
        available = max(0.0, name_rect.width() - 6.0 - title_width)
        if sum(width for _spec, width in controls) <= available:
            visible = controls
        else:
            budget = max(0.0, available - more_width)
            visible = []
            used = 0.0
            for spec, width in controls:
                if used + width > budget:
                    break
                visible.append((spec, width))
                used += width
            more["overflow"] = [dict(spec) for spec, _width in controls[len(visible):]]
            visible.append((more, more_width))
        specs = [spec for spec, _width in visible]
        widths = [width for _spec, width in visible]
        right_aligned = name_rect.right() - 6.0 - sum(widths)
        left = min(right_aligned, name_rect.x() + painter.track_title_width(track) + 4.0)
        for spec, width in zip(specs, widths):
            if spec["key"] == "more-controls":
                left = name_rect.right() - 6.0 - width
            spec["rect"] = QRectF(left, name_rect.y() + (row_height - hit_size) / 2.0, width, hit_size)
            spec["margin_x"] = max(0.0, (width - spec["icon_width"]) / 2.0)
            spec["margin_y"] = max(0.0, (hit_size - spec["icon_height"]) / 2.0)
            buttons.append(spec)
            left += width
        return buttons

    def _show_track_controls(self, button):
        from qt_api import QFrame, QHBoxLayout, QToolButton, QIcon, QPoint, Qt

        previous = getattr(self, "_track_controls_popup", None)
        if previous is not None:
            if previous.isVisible():
                previous.close()
                self.update()
                return
            previous.deleteLater()
        track = button.get("track") or self._find_track_by_id(button.get("track_id"))
        if track is None:
            return
        owner = self
        class TrackControlsPopup(QFrame):
            def keyPressEvent(self, event):
                if event.key() == Qt.Key_Escape:
                    self.close()
                    event.accept()
                else:
                    super().keyPressEvent(event)

            def closeEvent(self, event):
                super().closeEvent(event)
                owner.update()

        popup = TrackControlsPopup(self, Qt.Popup)
        self._track_controls_popup = popup
        popup.setAttribute(Qt.WA_NoMouseReplay)
        popup.setObjectName("trackControlsFlyout")
        bg = self.theme.track.name_background.name()
        fg = self.theme.track.font_color.name()
        accent = self.theme.track_control_color.name()
        hover_bg = self.theme.track.name_background.lighter(135).name()
        popup.setStyleSheet(
            "QFrame#trackControlsFlyout { background: %s; border: 1px solid %s; border-radius: 4px; }"
            "QToolButton { color: %s; background: transparent; border: none; border-radius: 3px; }"
            "QToolButton:hover, QToolButton:focus { background: %s; }" % (bg, accent, fg, hover_bg))
        layout = QHBoxLayout(popup)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        track_num = self.normalize_track_number(track.data.get("number"))
        for hidden in button.get("overflow", []):
            action = dict(hidden, track=track, track_num=track_num)
            control = QToolButton(popup)
            control.setFixedSize(28, 24)
            control.setFocusPolicy(Qt.StrongFocus)
            def refresh(control=control, action=action):
                control.setIcon(QIcon(self._toolbar_button_pixmap(track, action)))
                label = self._track_button_tooltip(action)
                control.setToolTip(label)
                control.setAccessibleName(label)
            refresh()
            def activate(checked=False, action=action, refresh=refresh):
                self._activate_track_toolbar_button(action)
                refresh()
                self.update()
            control.clicked.connect(activate)
            layout.addWidget(control)
        popup.adjustSize()
        anchor = self.mapToGlobal(button["rect"].topRight().toPoint())
        y = self.mapToGlobal(button["rect"].center().toPoint()).y() - popup.height() // 2
        screen = self.screen().availableGeometry()
        x = min(anchor.x() + 3, screen.right() - popup.width() + 1)
        x = max(screen.left(), x)
        y = min(max(screen.top(), y), screen.bottom() - popup.height() + 1)
        popup.move(QPoint(x, y))
        popup.show()
        popup.setFocus()
        self.update()

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
        if hasattr(pos, "toPointF"):
            pos = pos.toPointF()
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

        if key == "more-controls":
            popup = getattr(self, "_track_controls_popup", None)
            active = bool(popup is not None and popup.isVisible())
            if active:
                return pixmaps.get("active-hovered" if hovered else "active")
            return pixmaps.get("enabled" if hovered or pressed else "disabled")

        if key in ("mute-toggle", "visibility-toggle"):
            setting = "muted" if key == "mute-toggle" else "hidden"
            active = bool(track.data.get(setting))
            state = ("active-hovered" if hovered or pressed else "active") if active else (
                "enabled" if hovered or pressed else "disabled")
            return pixmaps.get(state)

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
            pixmaps = pixmaps.get("hide" if enabled else "show") or pixmaps
            state = "enabled" if enabled else "disabled"
            if hovered or pressed:
                state = "enabled"
            pix = pixmaps.get(state) or pixmaps.get("enabled") or pixmaps.get("disabled")
            return pix

        if key == "effects-tray":
            panel = getattr(self, "_effects_tray", None)
            if (panel and panel.track_id == track.id) or pressed:
                return pixmaps.get("active-hovered" if hovered else "active")
            if track.data.get("effects") and not hovered:
                return pixmaps.get("populated")

        state = "enabled" if (hovered or pressed) else "disabled"
        pix = pixmaps.get(state) or pixmaps.get("enabled") or pixmaps.get("disabled")
        return pix

    def _find_track_by_id(self, track_id):
        for track in self.track_list:
            if getattr(track, "id", None) == track_id:
                return track
        return None

    def _toggle_track_panel(self, track_num):
        self._set_track_keyframes(track_num, not self._track_panel_enabled.get(track_num, False))

    def _set_track_keyframes(self, track_num, new_state):
        if new_state == bool(self._track_panel_enabled.get(track_num)):
            return
        self.geometry.preserve_vertical_scroll()
        panel = getattr(self, "_effects_tray", None)
        if new_state and panel and panel.track_number == track_num:
            self._fx_return_rows[panel.track_id] = (panel.clip_id, panel.selected_id)
            panel.close()
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

        if key == "more-controls":
            self._show_track_controls(button)
            return

        if key == "keyframe-panel":
            if track_num is not None:
                self._toggle_track_panel(track_num)
            return

        if not self.win:
            return

        if key in ("mute-toggle", "visibility-toggle") and track_id:
            setting = "muted" if key == "mute-toggle" else "hidden"
            self.win.timeline.set_track_render_setting(track_id, setting, not bool(track.data.get(setting)))
            self.update()
            return

        if key == "effects-tray" and track_id:
            panel = getattr(self, "_effects_tray", None)
            target = () if panel and panel.track_id == track_id else self._fx_return_rows.pop(track_id, ())
            self.win.timeline.show_effects_tray(track_id, *target, reveal=False)
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
        if hasattr(pos, "toPointF"):
            pos = pos.toPointF()
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
        return _("Track %s") % QLocale().toString(display_index)

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
