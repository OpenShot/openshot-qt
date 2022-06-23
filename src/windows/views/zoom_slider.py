"""
 @file
 @brief This file contains the zoom slider QWidget (for interactive zooming/panning on the timeline)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

from PyQt5.QtCore import (
    Qt, QCoreApplication, QRectF, QTimer
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QCursor, QPainterPath, QIcon
)
from PyQt5.QtWidgets import QSizePolicy, QWidget

import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import updates
from classes.app import get_app
from classes.query import Clip, Track, Transition, Marker


class ZoomSlider(QWidget, updates.UpdateInterface):
    """ A QWidget used to zoom and pan around a Timeline"""

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        # Clear previous rects
        self.clip_rects.clear()
        self.clip_rects_selected.clear()
        self.marker_rects.clear()

        # Get layer lookup
        layers = {}
        for count, layer in enumerate(reversed(sorted(Track.filter()))):
            layers[layer.data.get('number')] = count

        # Wait for timeline object and valid scrollbar positions
        if hasattr(get_app().window, "timeline") and self.scrollbar_position[2] != 0.0:
            # Get max width of timeline
            project_duration = get_app().project.get("duration")
            pixels_per_second = self.width() / project_duration

            # Determine scale factor
            vertical_factor = self.height() / len(layers.keys())

            for clip in Clip.filter():
                # Calculate clip geometry (and cache it)
                clip_x = (clip.data.get('position', 0.0) * pixels_per_second)
                clip_y = layers.get(clip.data.get('layer', 0), 0) * vertical_factor
                clip_width = ((clip.data.get('end', 0.0) - clip.data.get('start', 0.0))
                              * pixels_per_second)
                clip_rect = QRectF(clip_x, clip_y, clip_width, 1.0 * vertical_factor)
                if clip.id in get_app().window.selected_clips:
                    # selected clip
                    self.clip_rects_selected.append(clip_rect)
                else:
                    # un-selected clip
                    self.clip_rects.append(clip_rect)

            for clip in Transition.filter():
                # Calculate clip geometry (and cache it)
                clip_x = (clip.data.get('position', 0.0) * pixels_per_second)
                clip_y = layers.get(clip.data.get('layer', 0), 0) * vertical_factor
                clip_width = ((clip.data.get('end', 0.0) - clip.data.get('start', 0.0))
                              * pixels_per_second)
                clip_rect = QRectF(clip_x, clip_y, clip_width, 1.0 * vertical_factor)
                if clip.id in get_app().window.selected_transitions:
                    # selected clip
                    self.clip_rects_selected.append(clip_rect)
                else:
                    # un-selected clip
                    self.clip_rects.append(clip_rect)

            for marker in Marker.filter():
                # Calculate clip geometry (and cache it)
                marker_x = (marker.data.get('position', 0.0) * pixels_per_second)
                marker_rect = QRectF(marker_x, 0, 0.5, len(layers) * vertical_factor)
                self.marker_rects.append(marker_rect)

        # Force re-paint
        self.update()

    def paintEvent(self, event, *args):
        """ Custom paint event """
        event.accept()

        # Paint timeline preview on QWidget
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing,
            True)

        # Fill the whole widget with the solid color (background solid color)
        painter.fillRect(event.rect(), QColor("#191919"))

        # Create pens / colors
        clip_pen = QPen(QBrush(QColor("#53a0ed")), 1.5)
        clip_pen.setCosmetic(True)
        painter.setPen(clip_pen)

        selected_clip_pen = QPen(QBrush(QColor("Red")), 1.5)
        selected_clip_pen.setCosmetic(True)

        scroll_color = QColor("#4053a0ed")
        scroll_pen = QPen(QBrush(scroll_color), 2.0)
        scroll_pen.setCosmetic(True)

        marker_color = QColor("#4053a0ed")
        marker_pen = QPen(QBrush(marker_color), 1.0)
        marker_pen.setCosmetic(True)

        playhead_color = QColor(Qt.GlobalColor.red)
        playhead_color.setAlphaF(0.5)
        playhead_pen = QPen(QBrush(playhead_color), 1.0)
        playhead_pen.setCosmetic(True)

        handle_color = QColor("#a653a0ed")
        handle_pen = QPen(QBrush(handle_color), 1.5)
        handle_pen.setCosmetic(True)

        # Get layer lookup
        layers = Track.filter()

        # Wait for timeline object and valid scrollbar positions
        if get_app().window.timeline and self.scrollbar_position[2] != 0.0:
            # Get max width of timeline
            project_duration = get_app().project.get("duration")
            pixels_per_second = event.rect().width() / project_duration
            project_pixel_width = max(0, project_duration * pixels_per_second)
            scroll_width = (self.scrollbar_position[1] - self.scrollbar_position[0]) * event.rect().width()

            # Get FPS info
            fps_num = get_app().project.get("fps").get("num", 24)
            fps_den = get_app().project.get("fps").get("den", 1)
            fps_float = float(fps_num / fps_den)

            # Determine scale factor
            vertical_factor = event.rect().height() / len(layers)

            # Loop through each clip
            painter.setPen(clip_pen)
            for clip_rect in self.clip_rects:
                painter.drawRect(clip_rect)

            painter.setPen(selected_clip_pen)
            for clip_rect in self.clip_rects_selected:
                painter.drawRect(clip_rect)

            painter.setPen(marker_pen)
            for marker_rect in self.marker_rects:
                painter.drawRect(marker_rect)

            painter.setPen(playhead_pen)
            playhead_x = ((self.current_frame / fps_float) * pixels_per_second)
            playhead_rect = QRectF(playhead_x, 0, 0.5, len(layers) * vertical_factor)
            painter.drawRect(playhead_rect)

            # Draw scroll bars (if available)
            if self.scrollbar_position:
                painter.setPen(scroll_pen)

                # scroll bar path
                scroll_x = self.scrollbar_position[0] * event.rect().width()
                self.scroll_bar_rect = QRectF(scroll_x, 0.0, scroll_width, event.rect().height())
                scroll_path = QPainterPath()
                scroll_path.addRoundedRect(self.scroll_bar_rect, 6, 6)

                # draw scroll bar rect
                painter.fillPath(scroll_path, scroll_color)
                painter.drawPath(scroll_path)

                # draw handles
                painter.setPen(handle_pen)
                handle_width = 12.0

                # left handle
                left_handle_x = (self.scrollbar_position[0] * event.rect().width()) - (handle_width/2.0)
                self.left_handle_rect = QRectF(left_handle_x, event.rect().height() / 4.0, handle_width, event.rect().height() / 2.0)
                left_handle_path = QPainterPath()
                left_handle_path.addRoundedRect(self.left_handle_rect, handle_width, handle_width)
                painter.fillPath(left_handle_path, handle_color)

                # right handle
                right_handle_x = (self.scrollbar_position[1] * event.rect().width()) - (handle_width/2.0)
                self.right_handle_rect = QRectF(right_handle_x, event.rect().height() / 4.0, handle_width, event.rect().height() / 2.0)
                right_handle_path = QPainterPath()
                right_handle_path.addRoundedRect(self.right_handle_rect, handle_width, handle_width)
                painter.fillPath(right_handle_path, handle_color)

            # Determine if play-head is inside scroll area
            if get_app().window.preview_thread.player.Mode() == openshot.PLAYBACK_PLAY and self.is_auto_center:
                if not self.scroll_bar_rect.contains(playhead_rect):
                    get_app().window.TimelineCenter.emit()

        # End painter
        painter.end()

    def mousePressEvent(self, event):
        """Capture mouse press event"""
        event.accept()
        self.mouse_pressed = True
        self.mouse_dragging = False
        self.mouse_position = event.pos().x()
        self.scrollbar_position_previous = self.scrollbar_position

        # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
        get_app().updates.ignore_history = True

    def mouseReleaseEvent(self, event):
        """Capture mouse release event"""
        event.accept()

        self.mouse_pressed = False
        self.mouse_dragging = False
        self.left_handle_dragging = False
        self.right_handle_dragging = False
        self.scroll_bar_dragging = False

    def set_handle_limits(self, left_handle, right_handle, is_left=False):
        """Set min/max limits on the bounds of the handles (to prevent invalid values)"""
        if left_handle < 0.0:
            left_handle = 0.0
            right_handle = self.scroll_bar_rect.width() / self.width()
        if right_handle > 1.0:
            left_handle = 1.0 - (self.scroll_bar_rect.width() / self.width())
            right_handle = 1.0

        # Don't allow handles to extend past each other
        diff = right_handle - left_handle

        # Adjust currently dragged handle (if exceeding min distance)
        if is_left and diff < self.min_distance:
            left_handle = right_handle - self.min_distance
        elif not is_left and diff < self.min_distance:
            right_handle = left_handle + self.min_distance

        return left_handle, right_handle

    def mouseMoveEvent(self, event):
        """Capture mouse events"""
        event.accept()

        # Get current mouse position
        mouse_pos = event.pos().x()
        if mouse_pos < 0:
            mouse_pos = 0
        elif mouse_pos > self.width():
            mouse_pos = self.width()

        # Set cursor
        if not self.mouse_dragging:
            if self.left_handle_rect.contains(event.pos()):
                self.setCursor(self.cursors.get('resize_x'))
            elif self.right_handle_rect.contains(event.pos()):
                self.setCursor(self.cursors.get('resize_x'))
            elif self.scroll_bar_rect.contains(event.pos()):
                self.setCursor(self.cursors.get('move'))
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        # Detect dragging
        if self.mouse_pressed and not self.mouse_dragging:
            self.mouse_dragging = True

            if self.left_handle_rect.contains(event.pos()):
                self.left_handle_dragging = True
            elif self.right_handle_rect.contains(event.pos()):
                self.right_handle_dragging = True
            elif self.scroll_bar_rect.contains(event.pos()):
                self.scroll_bar_dragging = True
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        # Dragging handle
        if self.mouse_dragging:
            if self.left_handle_dragging:
                # Update scrollbar position
                delta = (self.mouse_position - mouse_pos) / self.width()
                new_left_pos = self.scrollbar_position_previous[0] - delta
                is_left = True
                if int(QCoreApplication.instance().keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier) > 0:
                    # SHIFT key pressed (move )
                        if (self.scrollbar_position_previous[1] + delta) - new_left_pos > self.min_distance:
                            #both handles if we don't exceed min distance
                            new_right_pos = self.scrollbar_position_previous[1] + delta
                        else:
                            midpoint = (self.scrollbar_position_previous[1] + self.scrollbar_position_previous)/2
                            new_right_pos = midpoint + (self.min_distance/2)
                            new_left_pos = midpoint - (self.min_distance/2)
                else:
                    new_right_pos = self.scrollbar_position_previous[1]

                # Enforce limits (don't allow handles to go past each other, or out of bounds)
                new_left_pos, new_right_pos = self.set_handle_limits(new_left_pos, new_right_pos, is_left)

                self.scrollbar_position = [new_left_pos,
                                           new_right_pos,
                                           self.scrollbar_position[2],
                                           self.scrollbar_position[3]]
                self.delayed_resize_timer.start()

            elif self.right_handle_dragging:
                delta = (self.mouse_position - mouse_pos) / self.width()
                is_left = False
                new_right_pos = self.scrollbar_position_previous[1] - delta
                if int(QCoreApplication.instance().keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier) > 0:
                    # SHIFT key pressed (move )
                        if new_right_pos - (self.scrollbar_position_previous[0] + delta) > self.min_distance:
                            #both handles if we don't exceed min distance
                            new_left_pos = self.scrollbar_position_previous[0] + delta
                        else:
                            midpoint = (self.scrollbar_position_previous[1] + self.scrollbar_position_previous)/2
                            new_right_pos = midpoint + (self.min_distance/2)
                            new_left_pos = midpoint - (self.min_distance/2)
                else:
                    new_left_pos = self.scrollbar_position_previous[0]

                # Enforce limits (don't allow handles to go past each other, or out of bounds)
                new_left_pos, new_right_pos = self.set_handle_limits(new_left_pos, new_right_pos, is_left)

                self.scrollbar_position = [new_left_pos,
                                           new_right_pos,
                                           self.scrollbar_position[2],
                                           self.scrollbar_position[3]]
                self.delayed_resize_timer.start()

            elif self.scroll_bar_dragging:
                # Update scrollbar position
                delta = (self.mouse_position - mouse_pos) / self.width()
                new_left_pos = self.scrollbar_position_previous[0] - delta
                new_right_pos = self.scrollbar_position_previous[1] - delta

                # Enforce limits (don't allow handles to go past each other, or out of bounds)
                new_left_pos, new_right_pos = self.set_handle_limits(new_left_pos, new_right_pos)

                self.scrollbar_position = [new_left_pos,
                                           new_right_pos,
                                           self.scrollbar_position[2],
                                           self.scrollbar_position[3]]

                # Emit signal to scroll Timeline
                get_app().window.TimelineScroll.emit(new_left_pos)

            # Force re-paint
            self.update()

        # Update mouse position
        # self.mouse_position = mouse_pos

    def resizeEvent(self, event):
        """Widget resize event"""
        event.accept()
        self.delayed_size = self.size()
        self.delayed_resize_timer.start()

    def delayed_resize_callback(self):
        """Callback for resize event timer (to delay the resize event, and prevent lots of similar resize events)"""
        # Get max width of timeline
        project_duration = get_app().project.get("duration")
        normalized_scroll_width = self.scrollbar_position[1] - self.scrollbar_position[0]
        scroll_width_seconds = normalized_scroll_width * project_duration
        tick_pixels = 100
        if self.scrollbar_position[3] > 0.0:
            # Calculate the new zoom factor, based on pixels per tick
            zoom_factor = scroll_width_seconds / (self.scrollbar_position[3] / tick_pixels)

            # Set scroll width (and send signal)
            if zoom_factor > 0.0:
                self.setZoomFactor(zoom_factor)

                # Emit signal to scroll Timeline
                get_app().window.TimelineScroll.emit(self.scrollbar_position[0])

    # Capture wheel event to alter zoom/scale of widget
    def wheelEvent(self, event):
        event.accept()

        # Repaint widget on zoom
        self.repaint()

    def setZoomFactor(self, zoom_factor):
        """Set the current zoom factor"""
        # Force recalculation of clips
        self.zoom_factor = zoom_factor

        # Emit zoom signal
        get_app().window.TimelineZoom.emit(self.zoom_factor)
        get_app().window.TimelineCenter.emit()

        # Force re-paint
        self.repaint()

    def zoomIn(self):
        """Zoom into timeline"""
        if self.zoom_factor >= 10.0:
            new_factor = self.zoom_factor - 5.0
        elif self.zoom_factor >= 4.0:
            new_factor = self.zoom_factor - 2.0
        else:
            new_factor = self.zoom_factor * 0.8

        # Emit zoom signal
        self.setZoomFactor(new_factor)

    def zoomOut(self):
        """Zoom out of timeline"""
        if self.zoom_factor >= 10.0:
            new_factor = self.zoom_factor + 5.0
        elif self.zoom_factor >= 4.0:
            new_factor = self.zoom_factor + 2.0
        else:
            # Ensure zoom is reversable when using only keyboard zoom
            new_factor = min(self.zoom_factor * 1.25, 4.0)

        # Emit zoom signal
        self.setZoomFactor(new_factor)

    def update_scrollbars(self, new_positions):
        """Consume the current scroll bar positions from the webview timeline"""
        if self.mouse_dragging:
            return

        self.scrollbar_position = new_positions

        # Check for empty clips rects
        if not self.clip_rects:
            self.changed(None)

        # Disable auto center
        self.is_auto_center = False

        # Force re-paint
        self.repaint()

    def handle_selection(self):
        # Force recalculation of clips and repaint
        self.changed(None)
        self.repaint()

    def update_playhead_pos(self, currentFrame):
        """Callback when position is changed"""
        self.current_frame = currentFrame

        # Force re-paint
        self.repaint()

    def handle_play(self):
        """Callback when play button is clicked"""
        self.is_auto_center = True

    def connect_playback(self):
        """Connect playback signals"""
        self.win.preview_thread.position_changed.connect(self.update_playhead_pos)
        self.win.PlaySignal.connect(self.handle_play)

    def __init__(self, *args):
        # Invoke parent init
        QWidget.__init__(self, *args)

        # Translate object
        _ = get_app()._tr

        # Init default values
        self.leftHandle = None
        self.rightHandle = None
        self.centerHandle = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.zoom_factor = 15.0
        self.scrollbar_position = [0.0, 0.0, 0.0, 0.0]
        self.scrollbar_position_previous = [0.0, 0.0, 0.0, 0.0]
        self.left_handle_rect = QRectF()
        self.left_handle_dragging = False
        self.right_handle_rect = QRectF()
        self.right_handle_dragging = False
        self.scroll_bar_rect = QRectF()
        self.scroll_bar_dragging = False
        self.clip_rects = []
        self.clip_rects_selected = []
        self.marker_rects = []
        self.current_frame = 0
        self.is_auto_center = True
        self.min_distance = 0.02

        # Load icon (using display DPI)
        self.cursors = {}
        for cursor_name in ["move", "resize_x", "hand"]:
            icon = QIcon(":/cursors/cursor_%s.png" % cursor_name)
            self.cursors[cursor_name] = QCursor(icon.pixmap(24, 24))

        # Init Qt widget's properties (background repainting, etc...)
        super().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        super().setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)

        # Set mouse tracking
        self.setMouseTracking(True)

        # Get a reference to the window object
        self.win = get_app().window

        # Connect zoom functionality
        self.win.TimelineScrolled.connect(self.update_scrollbars)

        self.win.TimelineResize.connect(self.delayed_resize_callback)

        # Connect Selection signals
        self.win.SelectionChanged.connect(self.handle_selection)

        # Show Property timer
        # Timer to use a delay before sending MaxSizeChanged signals (so we don't spam libopenshot)
        self.delayed_size = None
        self.delayed_resize_timer = QTimer(self)
        self.delayed_resize_timer.setInterval(200)
        self.delayed_resize_timer.setSingleShot(True)
        self.delayed_resize_timer.timeout.connect(self.delayed_resize_callback)
