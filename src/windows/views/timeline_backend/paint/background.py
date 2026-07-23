"""
 @file
 @brief Painter for the timeline background gradient.
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

from qt_api import QPointF, QRectF
from qt_api import QBrush, QColor, QLinearGradient, QPainter

from .base import BasePainter


class BackgroundPainter(BasePainter):
    def paint(self, painter: QPainter, rect: QRectF):
        bg = self.w.theme.background
        bg2 = getattr(self.w.theme, "background2", QColor())
        if bg2.isValid() and bg2 != bg:
            grad = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
            grad.setColorAt(0, bg)
            grad.setColorAt(1, bg2)
            painter.fillRect(rect, QBrush(grad))
        else:
            painter.fillRect(rect, bg)
            
        # Draw empty state hint if timeline has no clips
        try:
            if not any(True for _ in self.w.geometry.iter_clips()):
                from qt_api import QPen
                pen = QPen(QColor("#384254"))
                pen.setStyle(Qt.DashLine)
                pen.setWidth(2)
                painter.setPen(pen)
                
                # Center hint in viewport
                vp_width = self.w.viewport().width()
                vp_height = self.w.viewport().height()
                hint_rect = QRectF(vp_width/2 - 150, vp_height/2 - 25, 300, 50)
                
                painter.drawRoundedRect(hint_rect, 8, 8)
                
                painter.setPen(QColor("#8B95A5"))
                font = painter.font()
                font.setPixelSize(13)
                painter.setFont(font)
                text = "Drag clips here to start editing"
                painter.drawText(hint_rect, Qt.AlignCenter, text)
        except Exception:
            pass
