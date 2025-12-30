"""
 @file
 @brief Playhead movement and rendering helpers.
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


class PlayheadMixin:
    def centerOnPlayhead(self, emit=True):
        anchor_seconds = 0.0
        if self.fps_float:
            anchor_seconds = max(0.0, (self.current_frame - 1) / self.fps_float)
        width_norm = self.scrollbar_position[1] - self.scrollbar_position[0]
        timeline_w = self.scrollbar_position[2] or 0.0
        view_w = self.scrollbar_position[3] or 0.0
        changed = self._center_on_seconds(
            anchor_seconds,
            width_norm=width_norm if width_norm > 0 else None,
            timeline_w=timeline_w,
            view_w=view_w,
        )
        if not changed:
            return

        slider_positions = list(self.scrollbar_position)
        slider = getattr(self.win, "sliderZoomWidget", None)
        if slider:
            slider.update_scrollbars(slider_positions)
        if emit:
            get_app().window.TimelineScrolled.emit(slider_positions)
        self.geometry.mark_dirty()
        self.update()

    def _move_playhead(self, x_pos):
        fps = get_app().project.get("fps")
        fps_float = float(fps.get("num", 24)) / float(fps.get("den", 1) or 1)
        offset_px = getattr(self, "h_scroll_offset", 0.0)
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return
        seconds = max(0.0, (x_pos - self.track_name_width + offset_px) / pps)
        if fps_float:
            frame = int(round(seconds * fps_float)) + 1
        else:
            frame = 1
        frame = max(1, frame)
        self.win.SeekSignal.emit(frame)

    def update_playhead_pos(self, currentFrame):
        """Callback when position is changed"""
        self.current_frame = currentFrame

        # Schedule repaint
        self.update()

    def handle_play(self):
        """Callback when play button is clicked"""
        self.is_auto_center = True

    def connect_playback(self):
        """Connect playback signals"""
        self.win.preview_thread.position_changed.connect(self.update_playhead_pos)
        self.win.PlaySignal.connect(self.handle_play)

    def _playhead_icon_rect(self):
        """Return QRectF describing the full rendered playhead icon."""
        if not self.playhead_painter.icon_pix:
            return QRectF()
        offset_px = getattr(self, "h_scroll_offset", 0.0)
        frame_seconds = 0.0
        if self.fps_float:
            frame_seconds = max(
                0.0, (max(1, self.current_frame) - 1) / self.fps_float
            )
        x = (
            self.track_name_width
            + frame_seconds * self.pixels_per_second
            - offset_px
        )
        ix = int(round(x))
        icon_w, icon_h = self.playhead_painter.logical_size(
            self.playhead_painter.icon_pix
        )
        return QRectF(
            ix + self.playhead_painter.icon_offset_x,
            self.playhead_painter.icon_offset_y,
            icon_w,
            icon_h,
        )

    def _playhead_handle_rect(self):
        """Return QRectF describing the draggable portion of the playhead."""
        icon_rect = self._playhead_icon_rect()
        if icon_rect.isNull():
            return QRectF()
        timeline_width = (
            float(self.width()) - float(self.track_name_width) - float(self.scroll_bar_thickness)
        )
        if timeline_width <= 0.0:
            return QRectF()
        max_handle_height = min(float(self.ruler_height), icon_rect.height())
        if max_handle_height <= 0.0:
            return QRectF()
        handle_height = icon_rect.height() * 0.12
        handle_height = max(12.0, handle_height)
        handle_height = min(handle_height, max_handle_height)
        handle_area = QRectF(
            icon_rect.x(),
            icon_rect.y(),
            icon_rect.width(),
            handle_height,
        )
        visible_band = QRectF(
            self.track_name_width,
            0.0,
            timeline_width,
            max_handle_height,
        )
        handle_area = handle_area.intersected(visible_band)
        return handle_area if not handle_area.isNull() else QRectF()

    def _playhead_hit(self, pos):
        """Return True if *pos* intersects the draggable playhead handle."""
        handle_rect = self._playhead_handle_rect()
        if handle_rect.isNull():
            return False
        return handle_rect.contains(pos)

    def _startPlayhead(self):
        self.dragging_playhead = True
        self._fix_cursor(self.cursors["hand"])
        self._move_playhead(self._last_event.pos().x())

    def _playheadMove(self):
        if self.dragging_playhead:
            self._move_playhead(self._last_event.pos().x())

    def _finishPlayhead(self):
        self.dragging_playhead = False
        self._release_cursor()
        if self._last_event:
            self._updateCursor(self._last_event.pos())
