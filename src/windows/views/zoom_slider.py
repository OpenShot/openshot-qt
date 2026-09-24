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
import copy
import math

from qt_api import (
    Qt, QCoreApplication, QRectF, QTimer, QSize, QPointF
)
from qt_api import modifiers_has
from qt_api import (
    QPainter, QColor, QPen, QBrush, QCursor, QPainterPath, QIcon, QPalette
)
from qt_api import QSizePolicy, QWidget

import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import updates


def _event_posf(event):
    if hasattr(event, "position"):
        return event.position()
    return QPointF(event.pos())
from classes.app import get_app
from classes.query import Clip, Track, Transition, Marker
from classes.logger import log


class ZoomSlider(QWidget, updates.UpdateInterface):
    """ A QWidget used to zoom and pan around a Timeline"""

    def sizeHint(self):
        """Preferred size for layouts that host the slider."""
        return QSize(200, 20)

    def minimumSizeHint(self):
        """Allow the slider to shrink horizontally when space is limited."""
        return QSize(24, 20)

    def _track_rect(self):
        """Reserve space for the grips even at the ends of the timeline."""
        gutter = min(10.0, max(0.0, (self.width() - 1.0) / 2.0))
        return QRectF(gutter, 0.0, max(1.0, self.width() - 2 * gutter), self.height())

    def _position_ratio(self, x):
        track = self._track_rect()
        return max(0.0, min(1.0, (x - track.left()) / track.width()))

    def _update_handle_geometry(self):
        """Keep the true range separate from the minimum-sized interaction grips."""
        track = self._track_rect()
        left = track.left() + self.scrollbar_position[0] * track.width()
        right = track.left() + self.scrollbar_position[1] * track.width()
        self.scroll_bar_rect = QRectF(left, 0.0, max(0.0, right - left), self.height())
        # The visible handles sit on the exact time boundaries. Above and
        # below them, retain a generous move target even for sub-pixel spans.
        self.move_handle_rect = self.scroll_bar_rect.adjusted(-8.0, 0.0, 8.0, 0.0)
        handle_height = self.height() * 0.5
        self.left_handle_rect = QRectF(left - 6.0, self.height() * 0.25,
                                      12.0, handle_height)
        self.right_handle_rect = QRectF(right - 6.0, self.height() * 0.25,
                                       12.0, handle_height)

    def _hit_target(self, pos):
        self._update_handle_geometry()
        # Resize targets extend beyond the painted grips, with continuous left
        # and right halves when they overlap. Reserve top/bottom strips for pan.
        margin = min(4.0, self.height() / 5.0)
        hit_top = margin
        hit_height = max(0.0, self.height() - 2 * margin)
        left_hit = QRectF(self.left_handle_rect.left() - 4, hit_top,
                          20.0, hit_height).contains(pos)
        right_hit = QRectF(self.right_handle_rect.left() - 4, hit_top,
                           20.0, hit_height).contains(pos)
        if left_hit and right_hit:
            # Split overlapping grips by proximity; neither edge masks the other.
            return "left" if pos.x() <= self.scroll_bar_rect.center().x() else "right"
        if left_hit:
            return "left"
        if right_hit:
            return "right"
        if self.move_handle_rect.contains(pos):
            return "move"
        return "create"

    def _playhead_seconds(self):
        fps = get_app().project.get("fps")
        rate = float(fps.get("num", 24)) / float(fps.get("den", 1) or 1)
        return max(0.0, (self.current_frame - 1) / rate) if rate > 0 else 0.0

    def _snap_resize(self, left, right, is_left):
        """Snap only the dragged resize edge to matching clip edges or the playhead."""
        action = getattr(self.win, "actionSnappingTool", None)
        modifiers = QCoreApplication.instance().keyboardModifiers()
        if not action or not action.isChecked() or modifiers_has(modifiers, Qt.AltModifier):
            self._snap_target = None
            return left, right
        duration = float(get_app().project.get("duration") or 0.0)
        if duration <= 0:
            self._snap_target = None
            return left, right
        symmetric = modifiers_has(modifiers, Qt.ShiftModifier)
        midpoint_sum = sum(self.scrollbar_position_previous[:2])
        width = self._track_rect().width()

        def candidate(target, snap_left):
            new_left = target if snap_left else left
            new_right = right if snap_left else target
            if symmetric:
                if snap_left:
                    new_right = midpoint_sum - target
                else:
                    new_left = midpoint_sum - target
            if not (0.0 <= new_left < new_right <= 1.0):
                return None
            if new_right - new_left < self.min_distance - 1e-12:
                return None
            # Do not snap a resize beyond the backend's zoom limits.
            clamp = getattr(getattr(self.win, "timeline", None), "_clamp_zoom_factor", None)
            view_width = self.scrollbar_position[3]
            if callable(clamp) and view_width > 0:
                ticks = float(get_app().project.get("tick_pixels") or 100.0)
                factor = (new_right - new_left) * duration * ticks / view_width
                if not math.isclose(clamp(factor), factor, rel_tol=1e-9, abs_tol=1e-9):
                    return None
            return new_left, new_right

        acquire_radius, release_radius = 3.0, 4.0
        if self._snap_target is not None and self._snap_is_left == is_left:
            edge = left if self._snap_is_left else right
            if abs(self._snap_target - edge) * width <= release_radius:
                result = candidate(self._snap_target, self._snap_is_left)
                if result is not None:
                    return result
        self._snap_target = None
        playhead = self._playhead_seconds() / duration
        targets = []
        edge = left if is_left else right
        positions = self.snap_clip_starts if is_left else self.snap_clip_ends
        for target, priority in [(playhead, 0)] + [(seconds / duration, 1) for seconds in positions]:
            distance = abs(target - edge) * width
            if distance <= acquire_radius:
                targets.append((priority, distance, target, is_left))
        targets.sort()
        for _priority, _distance, target, snap_left in targets:
            result = candidate(target, snap_left)
            if result is not None:
                self._snap_target = target
                self._snap_is_left = snap_left
                return result
        return left, right

    def _set_target_cursor(self, target):
        if self.hover_target != target:
            self.hover_target = target
            self.update()
        if target in ("left", "right"):
            self.setCursor(self.cursors['resize_x'])
        elif target == "move":
            self.setCursor(self.cursors['move'])
        else:
            self.setCursor(Qt.ArrowCursor)

    def leaveEvent(self, event):
        if not self.mouse_pressed:
            self._set_target_cursor(None)
        super().leaveEvent(event)

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        from qt_api import isdeleted
        if isdeleted(self):
            return
        # Ignore changes that don't affect this
        if (action and len(action.key) >= 1 and action.key[0].lower() in ["files", "history", "profile"]) or self.ignore_updates:
            return
        # Effect edits cannot change the clip/transition rectangles or markers.
        if action and action.type == "update" and action.key and (
            action.key[0] == "effects"
            or (len(action.key) >= 3 and action.key[0] == "clips" and action.key[2] == "effects")
        ):
            return

        # Clear previous rects
        self.clip_rects.clear()
        self.clip_rects_selected.clear()
        self.marker_rects.clear()
        self.snap_clip_starts.clear()
        self.snap_clip_ends.clear()

        # Get layer lookup
        layers = {}
        for count, layer in enumerate(reversed(sorted(Track.filter()))):
            layers[layer.data.get('number')] = count

        # Wait for timeline object and valid scrollbar positions
        # TODO: Fix commented out logic
        if hasattr(get_app().window, "timeline"):  # and self.scrollbar_position[2] != 0.0:
            # Get max width of timeline
            project_duration = get_app().project.get("duration")
            track = self._track_rect()
            pixels_per_second = track.width() / project_duration

            # Determine scale factor
            # Inset preview strokes inside the range outline (pens straddle
            # their geometry, so a rectangle at y=0 would protrude above it).
            preview_top = 2.0
            vertical_factor = max(0.0, self.height() - 4.0) / max(1, len(layers))

            for clip in Clip.filter():
                position = float(clip.data.get('position', 0.0))
                duration = max(0.0, float(clip.data.get('end', 0.0)) - float(clip.data.get('start', 0.0)))
                self.snap_clip_starts.append(position)
                self.snap_clip_ends.append(position + duration)
                # Calculate clip geometry (and cache it)
                clip_x = track.left() + (clip.data.get('position', 0.0) * pixels_per_second)
                clip_y = preview_top + layers.get(clip.data.get('layer', 0), 0) * vertical_factor
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
                clip_x = track.left() + (clip.data.get('position', 0.0) * pixels_per_second)
                clip_y = preview_top + layers.get(clip.data.get('layer', 0), 0) * vertical_factor
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
                marker_x = track.left() + (marker.data.get('position', 0.0) * pixels_per_second)
                marker_rect = QRectF(marker_x, preview_top, 0.5, len(layers) * vertical_factor)
                self.marker_rects.append(marker_rect)

        # Force re-paint
        self.update()

    def paintEvent(self, event, *args):
        """ Custom paint event """
        event.accept()

        # Get theme colors
        if get_app().theme_manager:
            theme = get_app().theme_manager.get_current_theme()
            if not theme:
                log.warning("No theme loaded yet. Skip rendering zoom slider widget.")
                return
            playhead_color = theme.get_color(".zoom_slider_playhead", "background-color")
        else:
            log.warning("No ThemeManager loaded yet. Skip rendering zoom slider widget.")
            return

        # Paint timeline preview on QWidget
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing, True)

        # Fill the whole widget with the solid color (background solid color)
        base_role = getattr(QPalette, "Base", None)
        if base_role is None:
            base_role = QPalette.ColorRole.Base
        background_color = self.palette().color(base_role)
        window_role = getattr(QPalette, "Window", None)
        if window_role is None:
            window_role = QPalette.ColorRole.Window
        panel_color = self.palette().color(window_role)
        # Stylesheet toolbar colors are not necessarily reflected in the slider's
        # Window palette (Cosmic Dusk otherwise inherits a gray gutter).
        toolbar_color = theme.get_color("QToolBar#timelineToolbar", "background-color")
        if toolbar_color is not None and toolbar_color.isValid():
            panel_color = toolbar_color
        # Gutters are control space, not part of the time overview.
        painter.fillRect(event.rect(), panel_color)
        track = self._track_rect()
        overview_path = QPainterPath()
        overview_path.addRoundedRect(track.adjusted(0, 1, 0, -1), 5, 5)
        painter.fillPath(overview_path, background_color)

        # Create pens / colors
        clip_pen = QPen(QBrush(QColor("#53a0ed")), 1.0)
        clip_pen.setCosmetic(True)
        painter.setPen(clip_pen)

        selected_clip_pen = QPen(QBrush(QColor("Red")), 1.0)
        selected_clip_pen.setCosmetic(True)

        scroll_color = QColor("#300078ff")
        scroll_pen = QPen(QBrush(QColor("#0078ff")), 1.0)
        scroll_pen.setCosmetic(True)

        marker_color = QColor("#4053a0ed")
        marker_pen = QPen(QBrush(marker_color), 1.0)
        marker_pen.setCosmetic(True)

        playhead_color = playhead_color
        playhead_pen = QPen(QBrush(playhead_color), 1.0)
        playhead_pen.setCosmetic(True)

        handle_color = QColor("#0078ff")
        handle_hover_color = QColor("#66b2ff")

        # Get layer lookup
        layers = Track.filter()

        # Wait for timeline object and valid scrollbar positions
        if get_app().window.timeline:
            # Get max width of timeline
            project_duration = get_app().project.get("duration")
            track = self._track_rect()
            pixels_per_second = track.width() / project_duration
            self._update_handle_geometry()

            # Determine scale factor
            vertical_factor = self.height() / max(1, len(layers))

            # Keep project content out of the control gutters.
            painter.save()
            painter.setClipPath(overview_path)
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

            painter.restore()
            playhead_x = track.left() + (self._playhead_seconds() * pixels_per_second)
            playhead_rect = QRectF(playhead_x, 0, 0.5, len(layers) * vertical_factor)

            # Draw scroll bars (if available)
            if self.scrollbar_position:
                painter.setPen(scroll_pen)

                # Outline the actual time range; never inflate it for hit testing.
                path = QPainterPath()
                path.addRoundedRect(self.scroll_bar_rect.adjusted(0, 1, 0, -1), 5, 5)
                painter.fillPath(path, scroll_color)
                painter.drawPath(path)
                midpoint = self.scroll_bar_rect.center().x()
                for is_left, rect in ((True, self.left_handle_rect),
                                      (False, self.right_handle_rect)):
                    painter.save()
                    # At extreme zoom the two handles meet, with a left and right
                    # half matching the hit test instead of obscuring one another.
                    if self.scroll_bar_rect.width() < rect.width():
                        clip_left = 0.0 if is_left else midpoint
                        clip_right = midpoint if is_left else float(self.width())
                        painter.setClipRect(QRectF(clip_left, 0, clip_right - clip_left, self.height()))
                    path = QPainterPath()
                    path.addRoundedRect(rect, 3, 3)
                    target = "left" if is_left else "right"
                    highlighted = self.hover_target == target
                    painter.fillPath(path, handle_hover_color if highlighted else handle_color)
                    painter.setPen(QPen(QColor("#e0f0ff" if highlighted else "#80c0ff"), 1.0))
                    for dx in (-2, 2):
                        for dy in (-3, 0, 3):
                            painter.drawPoint(QPointF(rect.center().x() + dx, rect.center().y() + dy))
                    painter.restore()

            # Draw the playhead last so the selection cannot obscure time zero.
            painter.setPen(playhead_pen)
            if track.left() <= playhead_x <= track.right():
                painter.save()
                painter.setClipPath(overview_path)
                painter.drawRect(playhead_rect)
                painter.restore()

            # Determine if play-head is inside scroll area
            if get_app().window.preview_thread.player.Mode() == openshot.PLAYBACK_PLAY and self.is_auto_center:
                if not self.scroll_bar_rect.contains(playhead_rect):
                    get_app().window.TimelineCenter.emit()

        # End painter
        painter.end()

    def zoomToTimeline(self):
        """Toggle between zooming to the entire timeline and the previous zoom"""
        # Are we already zoomed complete out?
        if math.isclose(self.scrollbar_position[0], 0.0, abs_tol=1e-9) and math.isclose(self.scrollbar_position[1], 1.0, abs_tol=1e-9):
            # Restore previous zoom
            self.scrollbar_position[0] = self.scrollbar_zoom_previous[0]
            self.scrollbar_position[1] = self.scrollbar_zoom_previous[1]
        else:
            # Zoom out to reveal the entire timeline
            self.scrollbar_zoom_previous = copy.deepcopy(self.scrollbar_position)
            self.scrollbar_position[0] = 0.0
            self.scrollbar_position[1] = 1.0
        self.delayed_resize_callback()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        self.zoomToTimeline()
        # Qt replaces the second press with this event. Keep the release active
        # so it clears the gesture and resumes incoming scrollbar updates.
        self.mouse_pressed = True
        self.mouse_dragging = True  # Prevent mouseReleaseEvent from moving selection
        event.accept()

    def mousePressEvent(self, event):
        """Capture mouse press event"""
        event.accept()
        if event.button() != Qt.LeftButton:
            return
        self._snap_target = None
        self.press_target = self._hit_target(_event_posf(event))
        self._set_target_cursor(self.press_target)
        self.mouse_pressed = True
        self.mouse_dragging = False
        self.mouse_position = _event_posf(event).x()
        self.scrollbar_position_previous = list(self.scrollbar_position)  # copy, don't alias

    def mouseReleaseEvent(self, event):
        """Capture mouse release event"""
        event.accept()
        posf = _event_posf(event)

        if event.button() != Qt.LeftButton or not self.mouse_pressed:
            return

        # Only a click on the background recenters the selection.
        if not self.mouse_dragging and self.press_target == "create":
            # Center the scroll region at the click position (if outside the selection)
            click_pos = self._position_ratio(posf.x())
            selection_width = self.scrollbar_position[1] - self.scrollbar_position[0]
            half_width = selection_width / 2

            # Calculate new left / right handles
            new_left_pos = click_pos - half_width
            new_right_pos = click_pos + half_width

            # If the new left position is less than 0, adjust both sides to fit within bounds
            if new_left_pos < 0.0:
                diff = -new_left_pos
                new_left_pos = 0.0
                new_right_pos = min(1.0, new_right_pos + diff)

            # If the new right position is greater than 1, adjust both sides to fit within bounds
            if new_right_pos > 1.0:
                diff = new_right_pos - 1.0
                new_right_pos = 1.0
                new_left_pos = max(0.0, new_left_pos - diff)

            # Update the scrollbar position to the newly calculated values
            self.scrollbar_position = [new_left_pos, new_right_pos, self.scrollbar_position[2], self.scrollbar_position[3]]

            # Trigger the resize and update
            self.delayed_resize_callback()
            self.update()

        # Finalize drag selection
        self._snap_target = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.left_handle_dragging = False
        self.right_handle_dragging = False
        self.scroll_bar_dragging = False
        self.create_bar_dragging = False
        self._emit_pending_zoom()
        self._set_target_cursor(self._hit_target(posf))
        self.update()

    def set_handle_limits(self, left_handle, right_handle, is_left=False):
        """Set min/max limits on the bounds of the handles (to prevent invalid values)"""
        # Resizing clamps the active edge without moving the opposite edge.
        if is_left:
            right_handle = max(0.0, min(right_handle, 1.0))
            minimum = min(self.min_distance, right_handle)
            left_handle = max(0.0, min(left_handle, right_handle - minimum))
        else:
            left_handle = max(0.0, min(left_handle, 1.0))
            minimum = min(self.min_distance, 1.0 - left_handle)
            right_handle = min(1.0, max(right_handle, left_handle + minimum))

        return left_handle, right_handle

    def mouseMoveEvent(self, event):
        """Capture mouse events"""
        event.accept()
        posf = _event_posf(event)

        mouse_pos = posf.x()
        track_width = self._track_rect().width()
        if not self.mouse_pressed:
            self._set_target_cursor(self._hit_target(posf))

        # Choose the gesture at press time, before the pointer can leave a tiny grip.
        if self.mouse_pressed and not self.mouse_dragging:
            if abs(self.mouse_position - mouse_pos) < 5:
                return
            self.mouse_dragging = True
            self.left_handle_dragging = self.press_target == "left"
            self.right_handle_dragging = self.press_target == "right"
            self.scroll_bar_dragging = self.press_target == "move"
            self.create_bar_dragging = self.press_target == "create"

        # Handle dragging the selection (scroll bar dragging)
        if self.mouse_dragging:
            if self.left_handle_dragging:
                # Dragging the left handle to resize the selection
                delta = (self.mouse_position - mouse_pos) / track_width
                new_left_pos = self.scrollbar_position_previous[0] - delta
                is_left = True

                if modifiers_has(QCoreApplication.instance().keyboardModifiers(), Qt.ShiftModifier):
                    # SHIFT key pressed, move both handles
                    if (self.scrollbar_position_previous[1] + delta) - new_left_pos > self.min_distance:
                        new_right_pos = self.scrollbar_position_previous[1] + delta
                    else:
                        midpoint = (self.scrollbar_position_previous[1] + self.scrollbar_position_previous[0]) / 2
                        new_right_pos = midpoint + (self.min_distance / 2)
                        new_left_pos = midpoint - (self.min_distance / 2)
                else:
                    new_right_pos = self.scrollbar_position_previous[1]

                # Enforce limits (don't allow handles to go past each other, or out of bounds)
                new_left_pos, new_right_pos = self.set_handle_limits(new_left_pos, new_right_pos, is_left)
                new_left_pos, new_right_pos = self._snap_resize(new_left_pos, new_right_pos, is_left)

                self.scrollbar_position = [new_left_pos, new_right_pos, self.scrollbar_position[2], self.scrollbar_position[3]]
                self.delayed_resize_callback()

            elif self.right_handle_dragging:
                # Dragging the right handle to resize the selection
                delta = (self.mouse_position - mouse_pos) / track_width
                new_right_pos = self.scrollbar_position_previous[1] - delta
                is_left = False

                if modifiers_has(QCoreApplication.instance().keyboardModifiers(), Qt.ShiftModifier):
                    # SHIFT key pressed, move both handles
                    if new_right_pos - (self.scrollbar_position_previous[0] + delta) > self.min_distance:
                        new_left_pos = self.scrollbar_position_previous[0] + delta
                    else:
                        midpoint = (self.scrollbar_position_previous[1] + self.scrollbar_position_previous[0]) / 2
                        new_right_pos = midpoint + (self.min_distance / 2)
                        new_left_pos = midpoint - (self.min_distance / 2)
                else:
                    new_left_pos = self.scrollbar_position_previous[0]

                # Enforce limits
                new_left_pos, new_right_pos = self.set_handle_limits(new_left_pos, new_right_pos, is_left)
                new_left_pos, new_right_pos = self._snap_resize(new_left_pos, new_right_pos, is_left)

                self.scrollbar_position = [new_left_pos, new_right_pos, self.scrollbar_position[2], self.scrollbar_position[3]]
                self.delayed_resize_callback()

            elif self.scroll_bar_dragging:
                # Dragging the entire selection (scrolling the timeline)
                delta = (self.mouse_position - mouse_pos) / track_width
                new_left_pos = self.scrollbar_position_previous[0] - delta
                new_right_pos = self.scrollbar_position_previous[1] - delta

                # Panning preserves the exact span, including sub-pixel selections.
                span = self.scrollbar_position_previous[1] - self.scrollbar_position_previous[0]
                new_left_pos = max(0.0, min(new_left_pos, 1.0 - span))
                new_right_pos = new_left_pos + span

                self.scrollbar_position = [new_left_pos, new_right_pos, self.scrollbar_position[2], self.scrollbar_position[3]]
                get_app().window.TimelineScroll.emit(new_left_pos)

            elif self.create_bar_dragging:
                # Handle creating a new selection region
                new_pos = self._position_ratio(mouse_pos)

                if self.mouse_position < mouse_pos:
                    # Dragging to the right: set both handles to the starting position,
                    # then move the right handle (left handle stays where the drag started)
                    new_left_pos = self._position_ratio(self.mouse_position)
                    new_right_pos = new_pos
                else:
                    # Dragging to the left: set both handles to the starting position,
                    # then move the left handle (right handle stays where the drag started)
                    new_right_pos = self._position_ratio(self.mouse_position)
                    new_left_pos = new_pos

                # A new selection needs room for its minimum span at the end.
                new_left_pos = min(new_left_pos, 1.0 - self.min_distance)
                # Enforce limits for the new selection
                new_left_pos, new_right_pos = self.set_handle_limits(new_left_pos, new_right_pos)
                self.scrollbar_position = [new_left_pos, new_right_pos, self.scrollbar_position[2], self.scrollbar_position[3]]
                self.delayed_resize_callback()

            # Force re-paint after any dragging
            self.update()

    def resizeEvent(self, event):
        """Widget resize event"""
        event.accept()
        self.changed(None)
        self.delayed_size = self.size()
        self.delayed_resize_timer.start()

    def get_scroll_width(self):
        """Calculate the width of the scrollbar handle (i.e. selection width)"""
        # Get max width of timeline
        project_duration = get_app().project.get("duration")

        # Calculate scroll bar / selection width
        timeline_pixels_per_second = 100.0 / get_app().project.get("scale")
        timeline_project_width = project_duration * timeline_pixels_per_second
        scroll_ratio = self.scrollbar_position[3] / timeline_project_width
        scroll_width = scroll_ratio * self._track_rect().width()
        scroll_width = min(scroll_width, self._track_rect().width())
        return scroll_width, scroll_ratio

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

    # Capture wheel event to alter zoom/scale of widget
    def wheelEvent(self, event):
        event.accept()

        # Use async repaint to avoid recursive paint on some Qt/Windows paths.
        self.update()

    def setZoomFactor(self, zoom_factor, center=False, emit=True):
        """Set the current zoom factor (do not clamp width here — backend owns authoritative geometry)."""
        self.zoom_factor = zoom_factor
        if emit:
            if not self._apply_zoom_to_backend(self.zoom_factor):
                get_app().window.TimelineZoom.emit(self.zoom_factor)
            else:
                self._pending_zoom_emit = self.zoom_factor
                self._pending_scroll_emit = list(self.scrollbar_position)
                if self.mouse_dragging:
                    self._zoom_emit_timer.stop()
                else:
                    self._zoom_emit_timer.start()
        if center:
            get_app().window.TimelineCenter.emit()

        # Force re-paint asynchronously
        self.update()

    def _apply_zoom_to_backend(self, zoom_factor):
        """Apply zoom directly to the QWidget timeline during slider drags."""
        timeline = getattr(self.win, "timeline", None)
        if not timeline or not hasattr(timeline, "_apply_external_zoom"):
            return False

        self._syncing_backend = True
        try:
            timeline._apply_external_zoom(zoom_factor)
        finally:
            self._syncing_backend = False
        return True

    def _emit_pending_zoom(self):
        """Persist slider-driven zoom once the gesture settles."""
        if self._pending_zoom_emit is None and self._pending_scroll_emit is None:
            return

        zoom_factor = (
            float(self._pending_zoom_emit)
            if self._pending_zoom_emit is not None
            else None
        )
        self._pending_zoom_emit = None
        self._pending_scroll_emit = None

        if zoom_factor is not None:
            current_scale = float(get_app().project.get("scale") or 15.0)
            if abs(zoom_factor - current_scale) > 1e-6:
                get_app().updates.ignore_history = True
                get_app().updates.update(["scale"], zoom_factor)
                get_app().updates.ignore_history = False

        timeline = getattr(self.win, "timeline", None)
        if timeline and hasattr(timeline, "scrollbar_position"):
            self.scrollbar_position = list(timeline.scrollbar_position)
            self.update()

    def zoomIn(self):
        """Zoom into timeline"""
        if self.zoom_factor >= 10.0:
            new_factor = self.zoom_factor - 5.0
        elif self.zoom_factor >= 4.0:
            new_factor = self.zoom_factor - 2.0
        else:
            new_factor = self.zoom_factor * 0.8

        # Emit zoom signal
        self.setZoomFactor(new_factor, center=True)

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
        self.setZoomFactor(new_factor, center=True)

    def update_scrollbars(self, new_positions):
        """Consume the current scroll bar positions from the timeline view."""
        if self.mouse_dragging:
            return

        self.scrollbar_position = new_positions

        # Check for empty clips rects
        if not self.clip_rects:
            self.changed(None)

        # Disable auto center
        self.is_auto_center = False

        # Force re-paint asynchronously
        self.update()

    def handle_selection(self):
        # Force recalculation of clips and repaint
        self.changed(None)
        self.update()

    def timeline_resized(self):
        # Force recalculation of clips and repaint
        self.update()
        self.delayed_resize_timer.start()

    def update_playhead_pos(self, currentFrame):
        """Callback when position is changed"""
        self.current_frame = currentFrame

        # Schedule repaint (non-blocking)
        self.update()

    def handle_play(self):
        """Callback when play button is clicked"""
        self.is_auto_center = True

    def connect_playback(self):
        """Connect playback signals"""
        self.win.preview_thread.position_changed.connect(self.update_playhead_pos)
        self.win.PlaySignal.connect(self.handle_play)

    def ignore_updates_callback(self, ignore, show_wait=True):
        """Ignore updates callback - used to stop updating this widget during batch updates"""
        if not ignore and self.ignore_updates:
            # Force recalculation and repaint
            self.ignore_updates = ignore
            self.changed(None)
            self.update()
        self.ignore_updates = ignore

    def __init__(self, *args):
        # Invoke parent init
        super().__init__(*args)

        # Translate object
        _ = get_app()._tr

        # Init default values
        self.leftHandle = None
        self.rightHandle = None
        self.centerHandle = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.press_target = None
        self.hover_target = None
        self.create_bar_dragging = False
        self.move_handle_rect = QRectF()
        self.zoom_factor = 15.0
        self.scrollbar_position = [0.0, 0.0, 0.0, 0.0]
        self.scrollbar_position_previous = [0.0, 0.0, 0.0, 0.0]
        self.scrollbar_zoom_previous = [0.0, 0.2, 0.0, 0.0]
        self.left_handle_rect = QRectF()
        self.left_handle_dragging = False
        self.right_handle_rect = QRectF()
        self.right_handle_dragging = False
        self.scroll_bar_rect = QRectF()
        self.scroll_bar_dragging = False
        self.clip_rects = []
        self.clip_rects_selected = []
        self.marker_rects = []
        self.snap_clip_starts = []
        self.snap_clip_ends = []
        self._snap_is_left = None
        self._snap_target = None
        self.current_frame = 0
        self.is_auto_center = True
        self.min_distance = 0.002
        self.ignore_updates = False
        self._syncing_backend = False
        self._pending_zoom_emit = None
        self._pending_scroll_emit = None

        # Load icon (using display DPI)
        self.cursors = {}
        for cursor_name in ["move", "resize_x", "hand"]:
            icon = QIcon(":/cursors/cursor_%s.png" % cursor_name)
            self.cursors[cursor_name] = QCursor(icon.pixmap(24, 24))

        # Init Qt widget's properties (background repainting, etc...)
        super().setAttribute(Qt.WA_OpaquePaintEvent)
        super().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)

        self.setToolTip(_("Drag inside the range or above/below the grips to move the timeline view. Drag either grip to zoom. "
                          "Hold Shift while resizing to adjust both sides. Hold Alt to bypass snapping."))

        # Set mouse tracking
        self.setMouseTracking(True)

        # Get a reference to the window object
        self.win = get_app().window

        # Connect zoom functionality
        self.win.TimelineScrolled.connect(self.update_scrollbars)
        self.win.TimelineResize.connect(self.timeline_resized)
        self.win.IgnoreUpdates.connect(self.ignore_updates_callback)
        self.win.TimelineZoom.connect(lambda z: self.setZoomFactor(z, emit=False))

        # Connect Selection signals
        self.win.SelectionChanged.connect(self.handle_selection)

        # Show Property timer
        # Timer to use a delay before sending MaxSizeChanged signals (so we don't spam libopenshot)
        self.delayed_size = None
        self.delayed_resize_timer = QTimer(self)
        self.delayed_resize_timer.setInterval(100)
        self.delayed_resize_timer.setSingleShot(True)
        self.delayed_resize_timer.timeout.connect(self.delayed_resize_callback)

        self._zoom_emit_timer = QTimer(self)
        self._zoom_emit_timer.setInterval(50)
        self._zoom_emit_timer.setSingleShot(True)
        self._zoom_emit_timer.timeout.connect(self._emit_pending_zoom)
