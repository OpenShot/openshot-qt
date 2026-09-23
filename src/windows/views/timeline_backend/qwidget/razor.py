"""
 @file
 @brief Razor hover feedback and temporary timeline previews.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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

import math

from qt_api import QCursor, QColor, QEvent, QLabel, QPen, QPointF, QRectF, Qt, QTimer, QToolTip
from classes.app import get_app
from classes.time_parts import secondsToTime


class RazorMixin:
    def _init_razor(self):
        self._razor_pos = None
        self._razor_target = None
        self._razor_preview_frame = None
        self._razor_modifiers = Qt.NoModifier
        self._razor_snap_context = None
        self._razor_hint = QLabel(self)
        self._razor_hint.setObjectName("razorHint")
        self._razor_hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._razor_hint.setFocusPolicy(Qt.NoFocus)
        self._razor_hint.setTextFormat(Qt.PlainText)
        font = QToolTip.font()
        font.setPixelSize(12)
        self._razor_hint.setFont(font)
        self._razor_hint.hide()
        self._razor_timer = QTimer(self)
        self._razor_timer.setInterval(50)
        self._razor_timer.timeout.connect(self._refresh_razor_hover)

    def _razor_in_track_area(self, pos):
        return (pos is not None
                and self.track_name_width <= pos.x() < self.width() - self.scroll_bar_thickness
                and self.ruler_height < pos.y() < self.height() - self.scroll_bar_thickness)

    def _razor_target_at(self, pos, modifiers=None):
        if not self.enable_razor or not self._razor_in_track_area(pos):
            return None
        self.geometry.ensure()
        modifiers = self._razor_modifiers if modifiers is None else modifiers
        mode = "right" if modifiers & Qt.ControlModifier else "left" if modifiers & Qt.ShiftModifier else "both"
        pointer_seconds = self._seconds_from_x(pos.x())
        cut_seconds = self._snap_time(pointer_seconds)
        for rect, obj, _selected, kind in self.geometry.iter_items(reverse=True):
            if not rect.contains(pos):
                continue
            data = obj.data
            if kind not in ("clip", "transition") or self._is_track_locked(data.get("layer")):
                return None
            start = float(data.get("position", 0.0))
            duration = float(data.get("end", 0.0)) - float(data.get("start", 0.0))
            if not start + 1e-7 < cut_seconds < start + duration - 1e-7:
                self.snap.reset(["razor"])
                return None
            context = (str(obj.id), self.pixels_per_second, self.fps_float)
            if context != self._razor_snap_context:
                self.snap.reset(["razor"])
                self._razor_snap_context = context
            # Use trimming's keyframe targets without changing another tool's
            # state. Bounds discard the item's own edges and trimmed-off points.
            previous_keyframes = self._snap_keyframe_seconds
            try:
                self._update_snap_keyframe_targets(obj)
                first_cut = (math.floor(start * self.fps_float + 1e-7) + 1) / self.fps_float
                last_cut = (math.ceil((start + duration) * self.fps_float - 1e-7) - 1) / self.fps_float
                snapped_seconds, snapped = self.snap.snap_position(
                    pointer_seconds, label="razor", bounds=(first_cut, last_cut)
                )
            finally:
                self._snap_keyframe_seconds = previous_keyframes
            if snapped:
                cut_seconds = self._snap_time(snapped_seconds)
            # KEEP_LEFT adds one frame in Slice_Triggered. Compensate only in
            # the callback time, whether or not a shared snap target was found.
            seconds = cut_seconds - (1.0 / self.fps_float if mode == "left" else 0.0)
            return dict(item=obj, kind=kind, rect=QRectF(rect), seconds=seconds,
                        cut_seconds=cut_seconds, frame=int(round(cut_seconds * self.fps_float)) + 1,
                        mode=mode, ripple=mode != "both" and bool(modifiers & Qt.AltModifier))
        return None

    def _reset_razor_snap(self):
        self.snap.reset(["razor"])
        self._razor_snap_context = None

    def _razor_user_seek(self, *args):
        # Explicit navigation/playback supersedes a temporary preview. Do not
        # queue a restore over the user's new position, or resume until movement.
        self._reset_razor_snap()
        self._razor_preview_frame = None
        self._razor_pos = None
        self._razor_target = None
        self._hide_razor_hint()
        self.update()

    def _clear_razor_hover(self):
        self._reset_razor_snap()
        self._hide_razor_hint()
        self._razor_pos = None
        self._razor_target = None
        if self._razor_preview_frame is not None:
            worker = getattr(self.win, "preview_thread", None)
            if worker:
                worker.queue_seek(self.current_frame, False)
            self._razor_preview_frame = None
        self.update()

    def _refresh_razor_hover(self, modifiers=None):
        if modifiers is not None:
            self._razor_modifiers = modifiers
        target = self._razor_target_at(self._razor_pos, self._razor_modifiers)
        if target is None:
            if self._razor_target is not None or self._razor_preview_frame is not None:
                pos = self._razor_pos
                self._clear_razor_hover()
                self._razor_pos = pos
            return
        changed = target != self._razor_target
        self._razor_target = target
        if not self._is_playing():
            data = target["item"].data
            source_seconds = float(data.get("start", 0.0)) + target["cut_seconds"] - float(data.get("position", 0.0))
            frame = max(1, int(round(source_seconds * self.fps_float)) + 1)
            preview_key = (target["kind"], str(target["item"].id), frame)
            if preview_key != self._razor_preview_frame:
                timeline = getattr(self.win, "timeline", None)
                if timeline and timeline.PreviewRazorFrame(
                    preview_key[1], frame, self.current_frame, target["kind"]
                ):
                    self._razor_preview_frame = preview_key
        else:
            self._razor_preview_frame = None
        self._show_razor_hint(target)
        if changed:
            self.update()

    def _hide_razor_hint(self):
        self._razor_hint.hide()

    def _show_razor_hint(self, target):
        time = secondsToTime(target["cut_seconds"], self.fps_float, 1)
        _ = get_app()._tr
        action = {"both": _("Split"), "left": _("Keep left"), "right": _("Keep right")}[target["mode"]]
        if target["ripple"]:
            action += " · " + _("Close gap")
        label = f"{action} · {time['hour']}:{time['min']}:{time['sec']},{time['frame']}"
        self._razor_hint.setText(label)
        self._razor_hint.adjustSize()
        x = self.track_name_width + target["cut_seconds"] * self.pixels_per_second - self.h_scroll_offset
        top = max(self.ruler_height, target["rect"].top())
        # Anchor to the cut, not the mouse Y or the first time this text appeared.
        left = max(self.track_name_width, min(x + 8, self.width() - self.scroll_bar_thickness - self._razor_hint.width()))
        y = max(self.ruler_height, top - self._razor_hint.height() - 4)
        self._razor_hint.move(round(left), round(y))
        self._razor_hint.show()
        self._razor_hint.raise_()

    def _paint_razor(self, painter):
        target = self._razor_target_at(self._razor_pos, self._razor_modifiers)
        if not target:
            return
        rect = target["rect"].intersected(QRectF(
            self.track_name_width, self.ruler_height,
            self.width() - self.track_name_width - self.scroll_bar_thickness,
            self.height() - self.ruler_height - self.scroll_bar_thickness))
        x = self.track_name_width + target["cut_seconds"] * self.pixels_per_second - self.h_scroll_offset
        if rect.isEmpty() or not rect.left() <= x <= rect.right():
            return
        painter.save()
        painter.setClipRect(rect)
        if target["mode"] != "both":
            left, right = (x, rect.right()) if target["mode"] == "left" else (rect.left(), x)
            painter.fillRect(QRectF(left, rect.top(), right - left, rect.height()), QColor(220, 60, 60, 65))
        # A dark outline keeps the light guide legible on any thumbnail.
        painter.setPen(QPen(QColor(0, 0, 0, 220), 3))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.DashLine))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        painter.restore()

    def razor_ripple_at_cursor(self, keep_left):
        """Route the existing ripple actions to the hover only in Razor mode."""
        if not self.enable_razor:
            return False
        pos = self._razor_pos
        if pos is None and self.underMouse():
            pos = QPointF(self.mapFromGlobal(QCursor.pos()))
        if not self._razor_in_track_area(pos):
            return False
        modifiers = Qt.AltModifier | (Qt.ShiftModifier if keep_left else Qt.ControlModifier)
        target = self._razor_target_at(pos, modifiers)
        if target:
            self._clear_razor_hover()
            item_id = str(target["item"].id)
            self.RazorSliceAtCursor(
                item_id if target["kind"] == "clip" else "",
                item_id if target["kind"] == "transition" else "",
                target["seconds"], modifiers,
            )
        # Invalid/locked hover is a no-op, not a cut of a different selection.
        return True

    def focusOutEvent(self, event):
        self._clear_razor_hover()
        super().focusOutEvent(event)

    def event(self, event):
        if (event.type() == QEvent.ShortcutOverride
                and getattr(self, "enable_razor", False)
                and event.key() in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt)):
            # Update before menu/shortcut handling can consume the key press
            # (notably Alt), even while the pointer is stationary.
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if self.enable_razor and event.key() == Qt.Key_Escape:
            action = getattr(self.win, "actionRazorTool", None)
            if action and action.isChecked():
                action.trigger()
            else:
                self.setRazorMode(False)
            event.accept()
            return
        if self.enable_razor:
            modifiers = event.modifiers()
            flag = {Qt.Key_Shift: Qt.ShiftModifier, Qt.Key_Control: Qt.ControlModifier, Qt.Key_Alt: Qt.AltModifier}.get(event.key())
            if flag is not None and event.isAutoRepeat():
                event.accept()
                return
            if flag is not None:
                modifiers |= flag
            self._refresh_razor_hover(modifiers)
            if flag is not None:
                event.accept()
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.enable_razor:
            modifiers = event.modifiers()
            flag = {Qt.Key_Shift: Qt.ShiftModifier, Qt.Key_Control: Qt.ControlModifier, Qt.Key_Alt: Qt.AltModifier}.get(event.key())
            if flag is not None and event.isAutoRepeat():
                event.accept()
                return
            if flag is not None:
                modifiers &= ~flag
            self._refresh_razor_hover(modifiers)
            if flag is not None:
                event.accept()
                return
        super().keyReleaseEvent(event)
