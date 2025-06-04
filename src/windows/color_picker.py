"""
 @file
 @brief A modal Qt color picker dialog launcher, which works in Wayland
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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

from PyQt5 import QtCore
from PyQt5.QtWidgets import QColorDialog, QPushButton, QDialog, QFrame
from PyQt5.QtGui import QColor, QPainter, QPen, QCursor
from PyQt5.QtCore import Qt, QRect, QPoint
from classes.logger import log
from classes.app import get_app


def draw_checkerboard(painter, rect):
    """Draw a checkerboard pattern for transparent backgrounds."""
    # Use logical pixels for the checker size that scales with different DPIs
    effective_checker_size = 8
    light_color = QColor(220, 220, 220)
    dark_color = QColor(170, 170, 170)

    # Save current brush
    old_brush = painter.brush()

    # Draw checkerboard pattern in logical coordinates
    checker_size = int(effective_checker_size)
    for x in range(0, rect.width(), checker_size):
        for y in range(0, rect.height(), checker_size):
            if ((x // checker_size) + (y // checker_size)) % 2 == 0:
                color = light_color
            else:
                color = dark_color
            painter.fillRect(
                rect.x() + x,
                rect.y() + y,
                min(checker_size, rect.width() - x),
                min(checker_size, rect.height() - y),
                color
            )

    # Restore brush
    painter.setBrush(old_brush)

class BlockPaintFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Paint:
            # Block the paint event so the widget doesn’t draw its own contents.
            return True
        return super().eventFilter(obj, event)


class PreviewFrameFilter(QtCore.QObject):
    """
    Intercepts paint events on the QColorDialog’s preview frame,
    draws a checkerboard background + current hover/selected color.
    """
    def __init__(self, parent_dialog, get_color_callback):
        super().__init__(parent_dialog)
        self.get_color = get_color_callback

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Paint:
            painter = QPainter(obj)
            # Draw checkerboard inside the entire frame
            draw_checkerboard(painter, obj.rect())
            # Draw the overlay color
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.fillRect(obj.rect(), self.get_color())
            painter.end()
            return True
        return super().eventFilter(obj, event)


class ColorPicker(QColorDialog):
    def __init__(self, initial_color, parent=None, title=None, callback=None, *args, **kwargs):
        # Initialize with parent only first
        super().__init__(parent=parent, *args, **kwargs)
        self.parent_window = parent
        self.callback = callback
        self.picked_pixmap = None
        self.hover_color = initial_color  # Track the color being hovered

        if title:
            self.setWindowTitle(title)

        # Enable alpha channel and disable native dialog
        self.setOption(QColorDialog.DontUseNativeDialog)
        self.setOption(QColorDialog.ShowAlphaChannel)

        # Set the current color after options are set
        self.setCurrentColor(initial_color)
        self.colorSelected.connect(self.on_color_selected)
        self.currentColorChanged.connect(self.on_current_color_changed)

        # Override the "Pick Screen Color" button signal
        self._override_pick_screen_color()

        # Automatically open the dialog
        self.open()

        # Install our preview-frame filter
        self.update_preview_rectangles()

    def update_preview_rectangles(self):
        """Find the built-in preview frame and install a filter on it."""
        all_frames = self.findChildren(QFrame)
        # Filter to exact QFrame instances (not subclasses)
        exact_frames = [w for w in all_frames if type(w) is QFrame]
        if not exact_frames:
            return
        preview_frame = exact_frames[-1]
        # Install a filter on the preview frame itself
        filter = PreviewFrameFilter(self, lambda: self.currentColor())
        preview_frame.installEventFilter(filter)
        # Keep a reference so it is not garbage-collected
        self._preview_frame_filter = filter

    def resizeEvent(self, event):
        """Handle window resize events to update preview frame filter."""
        super().resizeEvent(event)
        self.update_preview_rectangles()
        self.update()  # Force repaint

    def on_current_color_changed(self, color):
        """Track when the current color changes (hover or selection)."""
        self.hover_color = color
        self.update()  # Trigger a repaint of the preview frame

    def _override_pick_screen_color(self):
        # Get first pushbutton (color picker)
        color_picker_button = self.findChildren(QPushButton)[0]
        # Connect to button signals
        color_picker_button.clicked.disconnect()
        color_picker_button.clicked.connect(self.start_color_picking)

    def start_color_picking(self):
        if self.parent_window:
            self.picked_pixmap = get_app().window.grab()
            self._show_picking_dialog()
        else:
            log.error("No parent window available for color picking")

    def _show_picking_dialog(self):
        dialog = PickingDialog(self.picked_pixmap, self)
        dialog.exec_()  # Show modal dialog
        self.raise_()

    def on_color_selected(self, color):
        if self.callback:
            self.callback(color)

class PickingDialog(QDialog):
    def __init__(self, pixmap, color_picker, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap = pixmap
        self.device_pixel_ratio = pixmap.devicePixelRatio()
        self.color_picker = color_picker
        self.setWindowModality(Qt.WindowModal)
        self.setGeometry(get_app().window.geometry())
        self.setFixedSize(self.size())
        self.setCursor(Qt.CrossCursor)
        self.color_preview = QColor("#FFFFFF")
        self.setMouseTracking(True)

        # Get first pushbutton (color picker)
        color_picker_button = self.color_picker.findChildren(QPushButton)[0]
        self.setWindowTitle(f"OpenShot: {color_picker_button.text().replace('&', '')}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)

        # Draw color preview rectangle near the cursor
        if self.color_preview:
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            preview_x = cursor_pos.x() + 15
            preview_y = cursor_pos.y() + 15
            preview_size = 50

            # Create preview rectangle
            preview_rect = QRect(preview_x, preview_y, preview_size, preview_size)

            # Draw checkerboard pattern for transparency
            draw_checkerboard(painter, preview_rect)

            # Draw the color with proper alpha over the checkerboard
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.fillRect(preview_rect, self.color_preview)

            # Draw border around preview
            pen = QPen(Qt.black, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(preview_x, preview_y, preview_size, preview_size)

        painter.end()

    def mouseMoveEvent(self, event):
        if self.pixmap:
            image = self.pixmap.toImage()
            # Scale the coordinates for High DPI displays
            scaled_x = int(event.x() * self.device_pixel_ratio)
            scaled_y = int(event.y() * self.device_pixel_ratio)
            if 0 <= scaled_x < image.width() and 0 <= scaled_y < image.height():
                pixel = image.pixel(scaled_x, scaled_y)
                color = QColor(pixel)
                # Ensure alpha channel is preserved in preview
                # Get alpha value from pixel (first 8 bits are alpha in ARGB format)
                alpha = (pixel >> 24) & 0xff
                color.setAlpha(alpha)
                self.color_preview = color

                # Force update display
                self.update()

    def mousePressEvent(self, event):
        if self.pixmap:
            image = self.pixmap.toImage()
            # Scale the coordinates for High DPI displays
            scaled_x = int(event.x() * self.device_pixel_ratio)
            scaled_y = int(event.y() * self.device_pixel_ratio)
            if 0 <= scaled_x < image.width() and 0 <= scaled_y < image.height():
                pixel = image.pixel(scaled_x, scaled_y)
                color = QColor(pixel)
                # Ensure alpha channel is preserved
                # Get alpha value from pixel (first 8 bits are alpha in ARGB format)
                alpha = (pixel >> 24) & 0xff
                color.setAlpha(alpha)

                # Set the selected color in the dialog
                self.color_picker.setCurrentColor(color)
        self.accept()  # Close the dialog
