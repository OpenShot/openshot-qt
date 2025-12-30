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

from PyQt5.QtCore import QRectF


class TransitionInteractionMixin:
    def _transition_menu_rect(self, rect):
        if not self.transition_painter.menu_pix:
            return QRectF()
        bw = self.transition_painter.pen.widthF()
        width, height = self.transition_painter.logical_size(self.transition_painter.menu_pix)
        return QRectF(
            rect.x() + bw + self.transition_painter.menu_margin,
            rect.y() + bw + self.transition_painter.menu_margin,
            width,
            height,
        )

    def _trigger_transition_menu_icon(self, pos):
        for rect, tran, _selected in self.geometry.iter_transitions(reverse=True):
            if self._transition_menu_rect(rect).contains(pos) and hasattr(self.win, "timeline"):
                self.win.timeline.ShowTransitionMenu(tran.id)
                return True
        return False
