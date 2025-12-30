"""
 @file
 @brief Effect badge and drop handling helpers.
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
from classes.query import Clip


class EffectInteractionMixin:
    def _apply_effect_drop(self, effect_names, pos_seconds, track_num):
        if not effect_names:
            return
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return
        pos_seconds = max(0.0, float(pos_seconds))
        try:
            track_num = int(track_num)
        except (TypeError, ValueError):
            return
        candidates = Clip.filter(layer=track_num)
        for clip in candidates:
            data = clip.data if isinstance(clip.data, dict) else {}
            clip_position = float(data.get("position", 0.0) or 0.0)
            clip_start = float(data.get("start", 0.0) or 0.0)
            clip_end = float(data.get("end", clip_start) or clip_start)
            duration = clip_end - clip_start
            if duration <= 0.0:
                continue
            clip_finish = clip_position + duration
            if pos_seconds == 0.0 or clip_position <= pos_seconds <= clip_finish:
                timeline.addEffect(effect_names, QPointF(pos_seconds, track_num))
                break

    def _effect_icon_at(self, pos):
        for entry in reversed(self._effect_icon_rects):
            rect = entry.get("rect")
            if isinstance(rect, QRectF) and rect.contains(pos):
                return entry
        return None

    def _trigger_effect_context_menu(self, icon_entry, modifiers=None):
        """Handle context menu interaction on an effect badge."""
        if not isinstance(icon_entry, dict):
            return False
        effect = icon_entry.get("effect")
        effect_id = icon_entry.get("effect_id")
        if effect_id is None and isinstance(effect, dict):
            effect_id = effect.get("id")
        if effect_id is None:
            return False
        effect_id_str = str(effect_id)
        ctrl = False
        if modifiers is None and self._last_event and hasattr(self._last_event, "modifiers"):
            modifiers = self._last_event.modifiers()
        if modifiers is not None:
            ctrl = bool(modifiers & Qt.ControlModifier)
        self._select_timeline_item(effect_id_str, "effect", not ctrl)
        timeline = getattr(self.win, "timeline", None)
        if timeline:
            timeline.ShowEffectMenu(effect_id_str)
        return True

    def _selected_effect_ids(self):
        selected = getattr(self.win, "selected_effects", [])
        return {str(eff) for eff in selected if eff is not None}

    def _handle_effect_icon_click(self, entry):
        if not isinstance(entry, dict):
            return
        effect = entry.get("effect")
        if not isinstance(effect, dict):
            return
        effect_id = entry.get("effect_id")
        if effect_id is None:
            effect_id = effect.get("id")
        if effect_id is None:
            return
        effect_id_str = str(effect_id)
        modifiers = Qt.NoModifier
        if self._last_event and hasattr(self._last_event, "modifiers"):
            modifiers = self._last_event.modifiers()
        ctrl = bool(modifiers & Qt.ControlModifier)
        self._select_timeline_item(effect_id_str, "effect", not ctrl)
