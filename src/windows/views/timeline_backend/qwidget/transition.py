"""
 @file
 @brief Transition-specific geometry helpers.
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

from qt_api import QRectF


from ..paint.hover import show_menu_with_hover


class TransitionInteractionMixin:
    def _transition_menu_rect(self, rect, tran=None):
        for entry in reversed(getattr(self, "_transition_text_rects", [])):
            entry_tran = entry.get("transition") if isinstance(entry, dict) else None
            entry_rect = entry.get("rect") if isinstance(entry, dict) else None
            if tran is not None and entry_tran is not tran:
                continue
            if isinstance(entry_rect, QRectF):
                return QRectF(entry_rect)
        if not self.transition_painter:
            return QRectF()
        _container_rect, hit_rect, _scaled_arrow, _arrow_rect, _title = self.transition_painter.transition_menu_geometry(rect, tran)
        return hit_rect

    def _trigger_transition_menu_icon(self, pos):
        for rect, tran, _selected in self.geometry.iter_transitions(reverse=True):
            if self._transition_menu_rect(rect, tran).contains(pos) and hasattr(self.win, "timeline"):
                self._select_timeline_item(tran.id, "transition", True)
                show_menu_with_hover(self, self.win.timeline.ShowTransitionMenu, tran.id)
                return True
        return False
