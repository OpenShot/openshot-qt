"""Shared editor for effects and transitions on one timeline track."""

import json
import math
import uuid
from contextlib import contextmanager
from copy import deepcopy

import openshot
from qt_api import QApplication, QColor, QFont, QFontMetrics, QMimeData, QObject, QPointF, QRectF, Qt

from classes.app import get_app
from classes.clipboard import EFFECT_RANGES_MIME
from classes.effect_init import effect_options
from classes.query import Clip, Effect, Track, Transition
from classes.qt_types import font_metrics_horizontal_advance
from windows.views.menu import StyledContextMenu
from windows.views.timeline_backend.enums import MenuSlice


def clip_effect_sort_key(effect):
    """Match the native before/after-transform passes and legacy effect order."""
    phase = not effect.get("apply_before_clip", True)
    order = effect.get("stack_order", -1)
    if order >= 0:
        return phase, 0, order
    return phase, 1, effect.get("layer", 0), effect.get("position", 0), -effect.get("order", 0)


def clip_effect_lanes(rows):
    """Reuse lanes across clips while keeping each clip's stack in order."""
    lanes = []
    previous_lane = {}
    for index, (_, clip, effect, start, end) in enumerate(rows):
        effect_type = effect.get("type") or effect.get("name")
        minimum = previous_lane.get(clip.id, -1) + 1
        for slot in range(minimum, len(lanes)):
            lane_type, entries = lanes[slot]
            if lane_type == effect_type and all(
                end <= rows[entry][3] + 1e-9 or start >= rows[entry][4] - 1e-9 for entry in entries
            ):
                break
        else:
            slot = len(lanes)
            lanes.append((effect_type, []))
        lanes[slot][1].append(index)
        previous_lane[clip.id] = slot
    return [entries for _, entries in lanes]


def shift_effect_keyframes(value, frames):
    """Return the value with animated curves translated on their frame axis."""
    if isinstance(value, dict):
        points = value.get("Points")
        if isinstance(points, list):
            if len(points) < 2:
                return value
            shifted = []
            for point in points:
                coord = point.get("co") if isinstance(point, dict) else None
                if not isinstance(coord, dict) or not isinstance(coord.get("X"), (int, float)):
                    return value
                shifted.append(dict(point, co=dict(coord, X=coord["X"] + frames)))
            return dict(value, Points=shifted)
        return {key: shift_effect_keyframes(child, frames) for key, child in value.items()}
    if isinstance(value, list):
        return [shift_effect_keyframes(child, frames) for child in value]
    return value


class EffectsTray(QObject):
    """An expandable timeline panel with fixed labels and time-aligned bars."""

    header_height = 31
    row_height = 29
    bottom_padding = 5

    def __init__(self, timeline):
        super().__init__(timeline)
        self.timeline = timeline
        self.app = get_app()
        self.translate = self.app._tr
        self.track_id = None
        self.track_number = None
        self.rows = []
        self.selected_id = None
        self.selected_ids = set()
        self.active = False
        self.keyboard_edge = None
        self.nudge_transaction = None
        self._marquee = None
        self._snap_frame = None
        self._razor_line = None
        self.locked = False
        self.hovered = None
        self.drop_target = None
        self.clip_id = None
        self.sections = []
        self.row_slots = []
        self.lane_rows = {}
        self.clips = []
        self.catalog = {data["class_name"]: data for data in json.loads(openshot.EffectInfo.Json())}
        self._press = None
        self._preview = None

    def open_track(self, track_id, clip_id=None, effect_id=None):
        if track_id == self.track_id and not clip_id and not effect_id:
            self.close()
            return
        self.track_id = track_id
        self.clip_id = clip_id
        self.selected_id = effect_id
        self.selected_ids = {effect_id} if effect_id else set()
        self._clear_gesture()
        self.keyboard_edge = None
        self.refresh()
        if clip_id and not effect_id:
            self.selected_id = next((row[2]["id"] for row in self.rows
                                     if row[0] == "clip" and row[1].id == clip_id), None)
        self.selected_ids = {self.selected_id} if self.selected_id else set()
        self.active = bool(clip_id or effect_id)
        self._invalidate()
        if clip_id:
            self._reveal_clip_section(clip_id)

    def _reveal_clip_section(self, clip_id):
        section = next((section for section in self.sections if section[1] == "clip"), None)
        if section is None:
            return
        w = self.timeline
        w.geometry.ensure()
        _, lane, _ = self._bounds()
        slots = [self.row_slots[index] for index, row in enumerate(self.rows)
                 if row[0] == "clip" and row[1].id == clip_id]
        first, last = (min(slots), max(slots)) if slots else (section[0], section[0])
        if first == section[0] + 1:
            first = section[0]
        top_y = lane.top() + self.header_height + first * self.row_height
        end_y = lane.top() + self.header_height + (last + 1) * self.row_height
        bottom = w.height() - w.scroll_bar_thickness
        end_y = min(end_y, top_y + bottom - w.ruler_height)
        delta = top_y - w.ruler_height if top_y < w.ruler_height else max(0.0, end_y - bottom)
        top, right, content_height, view_height = w.v_scrollbar_position
        if delta and content_height > view_height > 0:
            span = right - top
            top = max(0.0, min(top + delta / content_height, 1.0 - span))
            w.v_scrollbar_position[:2] = [top, top + span]
            self._invalidate()

    def close(self):
        self.track_id = None
        self.track_number = None
        self.rows = []
        self.sections = []
        self.row_slots = []
        self.lane_rows = {}
        self.clips = []
        self.selected_id = self.clip_id = self.hovered = self.drop_target = None
        self.clear_selection()
        self._clear_gesture()
        self._invalidate()

    def _invalidate(self):
        self.timeline.geometry.mark_dirty()
        self.timeline.update()

    def height(self, track_number):
        if self.track_id is None or self.track_number != track_number:
            return 0
        return self.header_height + (len(self.lane_rows) + len(self.sections)) * self.row_height + self.bottom_padding

    def _track(self):
        return Track.get(id=self.track_id) if self.track_id else None

    def _selected(self):
        return next((row[:3] for row in self.rows if row[2]["id"] == self.selected_id), None)

    def _frame_rate(self):
        fps = self.app.project.get("fps")
        return fps["num"] / fps["den"]

    def refresh(self):
        track = self._track()
        if not track:
            if self.track_id:
                self.close()
            return
        self.locked = bool(track.data.get("lock"))
        layer = track.data["number"]
        self.track_number = self.timeline.normalize_track_number(layer)
        rows, sections, lanes = [], [], {}

        def section(kind, owner, title):
            sections.append((len(lanes) + len(sections), kind, owner, title))

        def add_lane(entries):
            slot = len(lanes) + len(sections)
            lanes[slot] = list(range(len(rows), len(rows) + len(entries)))
            rows.extend(entries)

        _ = self.translate
        section("track", track, _("Track Effects"))
        for effect in track.data.get("effects") or []:
            trim = effect.get("clip_range") or {}
            add_lane([("track", track, effect, trim.get("start", 0.0), trim.get("end"))])

        section("clip", None, _("Clip Effects"))
        self.clips = sorted(Clip.filter(layer=layer), key=lambda item: item.data["position"])
        clip_rows = []
        for clip in self.clips:
            data = clip.data
            start, end, position = data["start"], data["end"], data["position"]
            for effect in sorted(data.get("effects") or [], key=clip_effect_sort_key):
                trim = effect.get("clip_range") or {}
                first = max(start, trim.get("start", start))
                last = min(end, trim.get("end", end))
                clip_rows.append(("clip", clip, effect, position + first - start, position + last - start))
        for entries in clip_effect_lanes(clip_rows):
            add_lane([clip_rows[index] for index in entries])

        transitions = sorted(Transition.filter(layer=layer), key=lambda item: item.data["position"])
        if transitions:
            section("transition", None, _("Transitions"))
        for transition in transitions:
            data = transition.data
            first = data["position"]
            add_lane([("transition", transition, data, first, first + data["end"] - data["start"])])

        row_slots = [slot for slot, entries in lanes.items() for _ in entries]
        if row_slots != self.row_slots or [row[2]["id"] for row in self.rows] != [row[2]["id"] for row in rows]:
            self._clear_gesture()
            self.hovered = None
        self.sections = sections
        self.lane_rows = lanes
        self.row_slots = row_slots
        self.rows = rows
        self.selected_ids.intersection_update(row[2]["id"] for row in rows)
        if self.selected_id not in self.selected_ids:
            self.selected_id = next(iter(self.selected_ids), None)

    def _bounds(self):
        w = self.timeline
        if self.track_id is None:
            return QRectF(), QRectF(), QRectF()
        for _, track, name in w.geometry.iter_tracks():
            if track.id != self.track_id:
                continue
            y = name.top() + w.vertical_factor
            right = w.width() - w.scroll_bar_thickness
            lane = QRectF(w.track_name_width, y, max(0.0, right - w.track_name_width), self.height(self.track_number))
            panel = QRectF(0, y, right, lane.height())
            visible = panel.intersected(QRectF(0, w.ruler_height, right, w.height() - w.ruler_height - w.scroll_bar_thickness))
            return panel, lane, visible
        return QRectF(), QRectF(), QRectF()

    def _heading_rect(self, lane):
        font = QFont(self.timeline.font())
        font.setBold(True)
        text_width = font_metrics_horizontal_advance(QFontMetrics(font), self.translate("Effects and Transitions"))
        width = max(0.0, min(text_width + 21, lane.right() - 46))
        return QRectF(10, lane.top(), width, self.header_height)

    def _section_rect(self, section, lane):
        y = lane.top() + self.header_height + section[0] * self.row_height
        return QRectF(0, y, lane.right() - 8, self.row_height)

    def _clip_for_add(self):
        selected = self.timeline.window.selected_clips
        clip_id = self.clip_id if self.active else None
        if clip_id is None and len(selected) == 1:
            clip_id = selected[0]
        return next((clip for clip in self.clips if clip.id == clip_id), None)

    def _add_rect(self, lane, section=None):
        section = self.sections[0] if section is None else section
        rect = self._section_rect(section, lane)
        return QRectF(lane.left() + 8, rect.top() + 4, 22, rect.height() - 8)

    def _row_controls(self, index, lane):
        kind, owner, effect, _, _ = self.rows[index]
        if self.locked or self.selected_id != effect["id"] or len(self.selected_ids) != 1 or kind == "transition":
            return ()
        rect = self._row_rect(index, lane)
        left = max(0.0, lane.left() - 86)
        return tuple(
            (name, glyph, QRectF(left + offset * 20, rect.y(), 18, rect.height()), enabled)
            for offset, (name, glyph, enabled) in enumerate((
                ("up", "↑", self._reorder_indices(kind, owner, effect, -1) is not None),
                ("down", "↓", self._reorder_indices(kind, owner, effect, 1) is not None),
                ("delete", "×", True),
                ("keyframes", "◇", True),
            ))
        )

    def _row_rect(self, index, lane):
        top = lane.top() + self.header_height + self.row_slots[index] * self.row_height
        return QRectF(lane.left(), top + 3, max(0.0, lane.width() - 8), self.row_height - 9)

    def _bar_rect(self, index, lane):
        kind, owner, effect, first, last = self.rows[index]
        row = self._row_rect(index, lane)
        w = self.timeline
        if kind == "clip" and w.dragging_items:
            override = w._pending_clip_overrides.get(owner.id, {})
            if override.get("layer", owner.data["layer"]) != self.track_number:
                return QRectF()
            delta = override.get("position", owner.data["position"]) - owner.data["position"]
            first += delta
            last += delta
        scale = w.pixels_per_second
        origin = lane.left() - w.h_scroll_offset
        if last is None:
            last = self.timeline._current_project_duration()
        if self._preview and effect["id"] in self._preview:
            first, last = self._preview[effect["id"]]
        x = origin + first * scale
        end = origin + last * scale
        if end <= x:
            return QRectF()
        return QRectF(x, row.top(), max(2.0, end - x), row.height())

    def _title(self, row):
        kind, owner, effect, _, _ = row
        if kind == "transition":
            return owner.title() or self.translate("Transition")
        return self.translate(effect.get("name") or effect.get("type") or "")

    def paint(self, painter):
        panel, lane, visible = self._bounds()
        if visible.isEmpty():
            return
        theme = self.timeline.theme
        accent = QColor(theme.track_control_color)
        if not accent.isValid():
            accent = QColor("#619ee8")
        background = QColor(theme.track.name_background)
        if not background.isValid():
            background = QColor(theme.track.background)
        well = QColor(theme.track.background)
        label = QColor(theme.track.font_color)
        detail = QColor(label)
        detail.setAlphaF(0.68)
        painter.save()
        painter.setClipRect(visible, Qt.IntersectClip)
        painter.fillRect(panel, background)
        painter.setPen(Qt.NoPen)
        painter.setBrush(well)
        painter.setPen(accent)
        heading = self._heading_rect(lane)
        heading_text = self.translate("Effects and Transitions")
        font = QFont(painter.font())
        font.setBold(True)
        painter.setFont(font)
        title_width = max(0, int(heading.width()) - 17)
        painter.drawText(heading, Qt.AlignVCenter | Qt.AlignLeft,
                         painter.fontMetrics().elidedText(heading_text, Qt.ElideRight, title_width))
        painter.drawText(heading, Qt.AlignVCenter | Qt.AlignRight, "⌄")
        font.setBold(False)
        painter.setFont(font)

        for section in self.sections:
            _, kind, owner, title = section
            if kind == "clip":
                owner = self._clip_for_add()
            rect = self._section_rect(section, lane)
            painter.setPen(Qt.NoPen)
            painter.setBrush(well)
            painter.drawRoundedRect(rect.adjusted(4, 2, 0, -2), 5, 5)
            add = self._add_rect(lane, section)
            if not self.locked and owner is not None:
                painter.setPen(accent)
                painter.drawText(add, Qt.AlignCenter, "+")
            painter.setPen(label)
            label_rect = QRectF(10, rect.y(), max(0, lane.left() - 15), rect.height())
            painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft,
                             painter.fontMetrics().elidedText(title, Qt.ElideRight, int(label_rect.width())))
            if kind == "track":
                hint = self.translate("Whole track")
            elif kind == "clip":
                hint = owner.title() if owner else self.translate("Drop an effect below a clip")
            else:
                hint = ""
            painter.setPen(detail)
            painter.drawText(rect.adjusted(add.right() + 7, 0, -6, 0),
                             Qt.AlignLeft | Qt.AlignVCenter, hint)
        if self.drop_target:
            bounds, caption = self.drop_target
            tint = QColor(accent)
            tint.setAlphaF(0.25)
            painter.fillRect(bounds, tint)
            painter.setPen(accent)
            painter.drawText(bounds.adjusted(0, 0, -10, 0), Qt.AlignRight | Qt.AlignVCenter, caption)

        for entries in self.lane_rows.values():
            index = next((entry for entry in entries if self.rows[entry][2]["id"] == self.selected_id), entries[0])
            well_rect = self._row_rect(index, lane)
            if not well_rect.intersects(visible):
                continue
            title = self._title(self.rows[index])
            painter.setPen(label)
            controls = self._row_controls(index, lane)
            label_end = controls[0][2].left() if controls else lane.left()
            name = QRectF(10, well_rect.top(), max(0.0, label_end - 15), well_rect.height())
            painter.drawText(name, Qt.AlignVCenter | Qt.AlignLeft,
                             painter.fontMetrics().elidedText(title, Qt.ElideRight, int(name.width())))
            for _, glyph, control, enabled in controls:
                painter.setPen(Qt.NoPen)
                painter.setBrush(well)
                painter.drawRoundedRect(control, 4, 4)
                color = QColor(accent)
                if not enabled:
                    color.setAlphaF(0.42)
                painter.setPen(color)
                painter.drawText(control, Qt.AlignCenter, glyph)
            painter.setPen(Qt.NoPen)
            painter.setBrush(well)
            painter.drawRoundedRect(well_rect, 5, 5)
        for index, row in enumerate(self.rows):
            well_rect = self._row_rect(index, lane)
            if not well_rect.intersects(visible):
                continue
            kind, _, effect, _, _ = row
            title = self._title(row)
            bar = self._bar_rect(index, lane).intersected(well_rect)
            if bar.isEmpty():
                continue
            chosen = effect["id"] in self.selected_ids
            painter.setBrush(QColor("#f9fbff") if not chosen else QColor("#dcecff"))
            painter.setPen(accent if chosen else Qt.NoPen)
            painter.drawRoundedRect(bar, 4, 4)
            painter.setPen(QColor("#955010") if kind == "track" else QColor("#1557a7"))
            margin = 10 if chosen and kind != "transition" else 4
            pill_text = painter.fontMetrics().elidedText(title, Qt.ElideRight, max(0, int(bar.width()) - 2 * margin))
            painter.drawText(bar.adjusted(margin, 0, -margin, 0), Qt.AlignCenter, pill_text)
            if (chosen or self.hovered == index) and kind != "transition" and not self.locked:
                full = self._bar_rect(index, lane)
                for edge_index, edge in enumerate((full.left(), full.right())):
                    if chosen and self.keyboard_edge == edge_index:
                        painter.setPen(accent)
                    else:
                        painter.setPen(QColor("#955010") if kind == "track" else QColor("#1557a7"))
                    if well_rect.left() <= edge <= well_rect.right():
                        x = min(max(edge, bar.left() + 3), bar.right() - 3)
                        painter.drawLine(QPointF(x, bar.center().y() - 4), QPointF(x, bar.center().y() + 4))

        origin = lane.left() - self.timeline.h_scroll_offset
        if self._snap_frame is not None:
            x = origin + self._snap_frame / self._frame_rate() * self.timeline.pixels_per_second
            if lane.left() <= x <= lane.right():
                painter.setPen(accent)
                painter.drawLine(QPointF(x, visible.top()), QPointF(x, visible.bottom()))
        if self._razor_line and self.timeline.enable_razor:
            index, frame = self._razor_line
            if index < len(self.rows):
                rect = self._row_rect(index, lane)
                x = origin + frame / self._frame_rate() * self.timeline.pixels_per_second
                painter.setPen(QColor("#df4343"))
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        if self._marquee:
            tint = QColor(accent)
            tint.setAlphaF(0.2)
            painter.setBrush(tint)
            painter.setPen(accent)
            painter.drawRect(self._marquee)
        painter.restore()

    def _hit(self, pos):
        panel, lane, visible = self._bounds()
        if not visible.contains(pos):
            return None
        if pos.y() < panel.top() + self.header_height:
            return ("close" if self._heading_rect(lane).contains(pos) else "blank", None)
        for section_index, section in enumerate(self.sections):
            if self._section_rect(section, lane).contains(pos):
                owner = self._clip_for_add() if section[1] == "clip" else section[2]
                if not self.locked and owner is not None and self._add_rect(lane, section).contains(pos):
                    return ("add", section_index)
                return ("blank", None)
        slot = int((pos.y() - panel.top() - self.header_height) // self.row_height)
        entries = self.lane_rows.get(slot, ())
        if pos.x() < lane.left():
            index = next((entry for entry in entries if self.rows[entry][2]["id"] == self.selected_id), None)
            if index is None and len(entries) == 1:
                index = entries[0]
            if index is not None:
                for name, _, rect, enabled in self._row_controls(index, lane):
                    if rect.contains(pos):
                        return (name if enabled else "blank", index)
                return ("row", index)
        else:
            for index in reversed(entries):
                if self._bar_rect(index, lane).intersected(self._row_rect(index, lane)).contains(pos):
                    return ("row", index)
        return ("blank", None)

    def _trim_edge(self, index, pos):
        kind, _, effect, _, _ = self.rows[index]
        if kind == "transition" or self.locked:
            return None
        _, lane, _ = self._bounds()
        bar = self._bar_rect(index, lane)
        if pos.x() < lane.left() or not bar.contains(pos):
            return None
        distances = (abs(pos.x() - bar.left()), abs(pos.x() - bar.right()))
        if min(distances) <= 7:
            return 0 if distances[0] < distances[1] else 1
        return None

    def cursor(self, pos):
        hit = self._hit(pos)
        if not hit:
            return None
        target, index = hit
        if target == "row" and self.rows[index][0] != "transition" and not self.locked:
            _, lane, _ = self._bounds()
            if self.timeline.enable_razor and self._bar_rect(index, lane).contains(pos) and pos.x() >= lane.left():
                return self.timeline.cursors["razor"]
            if self._trim_edge(index, pos) is not None:
                return Qt.SizeHorCursor
        return Qt.ArrowCursor if target == "blank" else Qt.PointingHandCursor

    def _clear_gesture(self):
        self._press = self._preview = self._marquee = None
        self._snap_frame = self._razor_line = None

    def cancel(self):
        if self._press is not None:
            self._clear_gesture()
            self.timeline.update()
        else:
            self._set_selection(set())
            self.clear_selection()

    def select_all(self):
        if not self.active:
            return False
        self._set_selection({row[2]["id"] for row in self.rows if row[0] != "transition"}, self.selected_id)
        return True

    def clear_selection(self):
        self.selected_ids.clear()
        self.selected_id = None
        self.active = False
        self.keyboard_edge = None
        self.nudge_transaction = None
        self.timeline.update()

    def _set_selection(self, ids, primary=None):
        selected = set(ids)
        previous = self.selected_id
        row = next((row for row in self.rows if row[2]["id"] == primary and primary in selected), None)
        if row is None:
            row = next((row for row in self.rows if row[2]["id"] in selected), None)
        self.selected_ids = selected
        self.selected_id = row[2]["id"] if row else None
        if row:
            kind, owner, _, _, _ = row
            if kind == "clip":
                self.clip_id = owner.id
            self.timeline.window.addSelection(self.selected_id, "transition" if kind == "transition" else "effect", True)
        elif previous:
            self.timeline.window.removeSelection(previous, "effect")
        self.timeline.update()

    def _selection_rows(self):
        return [row for row in self.rows if row[0] != "transition" and row[2]["id"] in self.selected_ids]

    def press(self, pos, button, modifiers=Qt.NoModifier):
        hit = self._hit(pos)
        if hit is None or button not in (Qt.LeftButton, Qt.RightButton):
            return False
        target, index = hit
        if not self.active:
            clip = self._clip_for_add()
            self.clip_id = clip.id if clip else None
        self.active = True
        self.keyboard_edge = None
        extend = bool(modifiers & (Qt.ControlModifier | Qt.ShiftModifier))
        edge = None
        rows = []
        _, lane, _ = self._bounds()
        if target == "row":
            kind, _, effect, _, _ = self.rows[index]
            effect_id = effect["id"]
            editable_bar = (kind != "transition" and not self.locked and pos.x() >= lane.left()
                            and self._bar_rect(index, lane).contains(pos))
            if button == Qt.LeftButton and editable_bar and self.timeline.enable_razor:
                mode = MenuSlice.KEEP_BOTH
                if modifiers & Qt.ControlModifier:
                    mode = MenuSlice.KEEP_RIGHT
                elif modifiers & Qt.ShiftModifier:
                    mode = MenuSlice.KEEP_LEFT
                frame = self._cut_frame(self.rows[index], self.timeline._seconds_from_x(pos.x()))
                self._slice([self.rows[index]], mode, frame)
                return True
            if extend and button == Qt.LeftButton and kind != "transition":
                self._set_selection(self.selected_ids ^ {effect_id}, effect_id)
                return True
            if effect_id not in self.selected_ids:
                self._select_row(index)
            elif effect_id != self.selected_id:
                self._set_selection(self.selected_ids, effect_id)
            if button == Qt.RightButton:
                self._show_menu(pos)
                return True
            if editable_bar:
                edge = self._trim_edge(index, pos)
                rows = self._selection_rows()
        if button == Qt.RightButton:
            return True
        self._press = (hit, QPointF(pos), edge, rows, extend)
        return True

    def _row_frames(self, row):
        kind, owner, _, first, last = row
        fps = self._frame_rate()
        if kind == "clip":
            start = owner.data["position"]
            end = start + owner.data["end"] - owner.data["start"]
        else:
            start = 0.0
            end = max(self.timeline._current_project_duration(), last or 0.0)
        return tuple(round(value * fps) for value in (start, end, first, last if last is not None else end))

    def _adjust_ranges(self, rows, delta, edge, *, snap=False):
        self._snap_frame = None
        fps = self._frame_rate()
        ranges = {}
        lower, upper = -float("inf"), float("inf")
        for row in rows:
            start, end, first, last = self._row_frames(row)
            if last <= first:
                continue
            ranges[row[2]["id"]] = (first, last)
            lower = max(lower, start - first if edge != 1 else first + 1 - last)
            upper = min(upper, end - last if edge != 0 else last - 1 - first)
        if not ranges:
            return {}
        delta = min(upper, max(lower, delta))
        if snap and self.timeline.enable_snapping:
            extra = [value for row in self.rows if row[2]["id"] not in ranges
                     for value in row[3:] if value is not None]
            candidates = []
            for frame_range in ranges.values():
                for index in (0, 1) if edge is None else (edge,):
                    frame = frame_range[index]
                    snapped, found = self.timeline.snap.snap_position(
                        (frame + delta) / fps, label="effect-range",
                        bounds=((frame + lower) / fps, (frame + upper) / fps), extra_seconds=extra,
                    )
                    if found:
                        snap_frame = round(snapped * fps)
                        candidates.append((snap_frame - frame, snap_frame))
                    self.timeline.snap.reset(["effect-range"])
            if candidates:
                delta, self._snap_frame = min(candidates, key=lambda candidate: abs(candidate[0] - delta))
        if delta == 0:
            return {}
        return {effect_id: ((first + (delta if edge != 1 else 0)) / fps,
                            (last + (delta if edge != 0 else 0)) / fps)
                for effect_id, (first, last) in ranges.items()}

    def move(self, pos):
        if self._press is None:
            hit = self._hit(pos)
            hover = hit[1] if hit and hit[0] == "row" else None
            razor_line = None
            if hover is not None and self.timeline.enable_razor and not self.locked:
                row = self.rows[hover]
                _, lane, _ = self._bounds()
                if row[0] != "transition" and pos.x() >= lane.left():
                    _, _, first, last = self._row_frames(row)
                    frame = self._cut_frame(row, self.timeline._seconds_from_x(pos.x()))
                    if first < frame < last:
                        razor_line = (hover, frame)
            if hover != self.hovered or razor_line != self._razor_line:
                self.hovered, self._razor_line = hover, razor_line
                self.timeline.update()
            return False
        (target, _), anchor, edge, rows, _ = self._press
        offset = pos - anchor
        distance = abs(offset.x()) if rows else offset.manhattanLength()
        if distance < QApplication.startDragDistance() and self._preview is None and self._marquee is None:
            return True
        if rows and self.timeline.pixels_per_second > 0:
            delta = round(offset.x() / self.timeline.pixels_per_second * self._frame_rate())
            self._preview = self._adjust_ranges(rows, delta, edge, snap=True)
        if target == "blank":
            _, lane, visible = self._bounds()
            self._marquee = QRectF(anchor, pos).normalized().intersected(lane).intersected(visible)
        self.timeline.update()
        return True

    def release(self, pos):
        if self._press is None:
            return False
        self.move(pos)
        hit, anchor, edge, rows, extend = self._press
        preview, marquee = self._preview, self._marquee
        self._clear_gesture()
        target, index = hit
        if preview:
            self._save_ranges(rows, preview, move_keys=edge is None)
        elif marquee is not None:
            _, lane, _ = self._bounds()
            ids = {row[2]["id"] for i, row in enumerate(self.rows) if row[0] != "transition"
                   and marquee.intersects(self._bar_rect(i, lane).intersected(self._row_rect(i, lane)))}
            self._set_selection(self.selected_ids | ids if extend else ids)
        elif self._hit(pos) == hit and (pos - anchor).manhattanLength() < QApplication.startDragDistance():
            if target == "close":
                self.close()
            elif target == "add":
                slot, kind, owner, title = self.sections[index]
                if kind == "clip":
                    owner = self._clip_for_add()
                if owner is not None:
                    self._add_menu(pos, (slot, kind, owner, title))
            elif target in ("up", "down"):
                self._move(-1 if target == "up" else 1)
            elif target == "delete":
                self.delete_selected()
            elif target == "keyframes":
                self._show_keyframes()
            elif target == "row":
                self._select_row(index)
            elif target == "blank" and not extend:
                self._set_selection(set())
                section, _ = self._drop_section(pos)
                if section and section[1] != "transition":
                    self.clip_id = section[2].id if section[1] == "clip" and section[2] else None
        self.timeline.update()
        return True

    def _select_row(self, index):
        self.active = True
        self._set_selection({self.rows[index][2]["id"]})

    def nudge(self, frames):
        rows = self._selection_rows()
        if not rows or not self.active:
            return False
        if not self.locked:
            if getattr(self.timeline, "_keyboard_nudge_key", None) is not None and self.nudge_transaction is None:
                self.nudge_transaction = str(uuid.uuid4())
            changes = self._adjust_ranges(rows, frames, self.keyboard_edge)
            self._save_ranges(rows, changes, self.nudge_transaction, move_keys=self.keyboard_edge is None)
        return True

    def select_edge(self, edge):
        if not self.active or not self._selection_rows():
            return False
        self.keyboard_edge = 0 if edge == "left" else 1
        self.timeline.update()
        return True

    def double_click(self, pos):
        hit = self._hit(pos)
        if hit is None:
            return False
        if hit[0] == "row":
            self._select_row(hit[1])
            self._show_properties()
        return True

    def tooltip(self, pos):
        hit = self._hit(pos)
        if hit is None:
            return ""
        target, index = hit
        _ = self.translate
        if target == "add":
            return _("Add Track Effect") if self.sections[index][1] == "track" else _("Add Clip Effect")
        if target == "close":
            return _("Hide effects and transitions")
        if target in ("up", "down", "delete", "keyframes"):
            return {"up": _("Move Up"), "down": _("Move Down"), "delete": _("Remove Effect"), "keyframes": _("Keyframes")}[target]
        if target == "row":
            row = self.rows[index]
            kind, owner, _, _, _ = row
            if kind == "clip":
                return self._title(row) + " · " + owner.title()
            if kind == "track":
                return self._title(row) + " · " + _("Track effect")
            return self._title(row) + " · " + _("Transition")
        return ""

    def _drop_section(self, pos):
        _, lane, visible = self._bounds()
        if not visible.contains(pos):
            return None, None
        slot = int((pos.y() - lane.top() - self.header_height) // self.row_height)
        section = next((section for section in reversed(self.sections) if section[0] <= slot), None)
        if section and section[1] == "clip":
            hit = self._hit(pos)
            if hit and hit[0] == "row":
                clip = self.rows[hit[1]][1]
            elif pos.x() >= lane.left():
                seconds = self.timeline._seconds_from_x(pos.x())
                clip = next((clip for clip in reversed(self.clips)
                             if clip.data["position"] <= seconds <
                             clip.data["position"] + clip.data["end"] - clip.data["start"]), None)
            else:
                clip = self._clip_for_add()
            section = (section[0], section[1], clip, section[3])
        return section, lane

    def preview_drop(self, pos, effect_name=None):
        section, lane = self._drop_section(pos) if pos is not None else (None, None)
        target = None
        if section and section[2] is not None and not self.locked:
            _, kind, owner, _ = section
            if effect_name:
                if kind == "clip" or self._can_add(effect_name):
                    name = owner.title() if kind == "clip" else self.timeline._track_display_label(owner)
                    caption = self.translate("Apply to %s") % name
                else:
                    caption = self.translate("Apply this effect to a clip")
                target = self._section_rect(section, lane), caption
        if target != self.drop_target:
            self.drop_target = target
            self.timeline.update()

    def drop(self, pos, effect_name):
        section, lane = self._drop_section(pos)
        self.preview_drop(None)
        if lane is None:
            return False
        if section and section[2] is not None:
            self._apply_to_section(section, effect_name)
        return True

    def _apply_to_section(self, section, name):
        if self.locked:
            return
        if section[1] == "track":
            self._add_effect(name)
        else:
            clip = Clip.get(id=section[2].id)
            if clip:
                self.timeline._apply_effect_to_clip(clip, name)
                self._reveal_clip_section(clip.id)

    def _can_add(self, name):
        # Source-dependent effects need a clip reader or tracked objects.
        data = self.catalog.get(name)
        return (data is not None and not data.get("has_tracked_object")
                and name not in effect_options and name not in {"ObjectMask", "PitchShift"})

    def _add_menu(self, pos, section):
        track = self._track()
        if not track or track.data.get("lock"):
            return
        _ = self.translate
        menu = StyledContextMenu(parent=self.timeline)
        for name, data in sorted(self.catalog.items(), key=lambda entry: _(entry[1]["name"])):
            if section[1] == "clip" or self._can_add(name):
                menu.addAction(_(data["name"]), lambda checked=False, value=name: self._apply_to_section(section, value))
        menu.show_at(self.timeline.mapToGlobal(pos.toPoint()))

    def _show_menu(self, pos):
        if self._selected() is None:
            return
        _ = self.translate
        menu = StyledContextMenu(parent=self.timeline)
        menu.addAction(_("Properties"), self._show_properties)
        menu.addAction(_("Keyframes"), self._show_keyframes)
        if self._selection_rows():
            menu.addSeparator()
            menu.addAction(_("Copy Effects"), self.copy_selected)
            if not self.locked:
                menu.addAction(_("Remove Effects"), self.delete_selected)
                menu.addAction(_("Reset Effect Timing"), self.reset_timing)
                slice_menu = StyledContextMenu(title=_("Slice at Playhead"), parent=menu)
                for label, mode in ((_("Keep Both Sides"), MenuSlice.KEEP_BOTH),
                                    (_("Keep Left Side"), MenuSlice.KEEP_LEFT),
                                    (_("Keep Right Side"), MenuSlice.KEEP_RIGHT)):
                    slice_menu.addAction(label, lambda checked=False, mode=mode: self.slice_selected(mode))
                menu.addMenu(slice_menu)
        menu.show_at(self.timeline.mapToGlobal(pos.toPoint()))

    def _cut_frame(self, row, seconds):
        _, _, first, last = self._row_frames(row)
        fps = self._frame_rate()
        if last - first < 2:
            return first
        snapped, found = self.timeline.snap.snap_position(
            seconds, label="effect-razor", bounds=((first + 1) / fps, (last - 1) / fps)
        )
        self.timeline.snap.reset(["effect-razor"])
        return round((snapped if found else seconds) * fps)

    def slice_selected(self, mode):
        rows = self._selection_rows()
        if not self.active or not rows:
            return False
        frame = max(0, (self.timeline.current_frame or 1) - 1)
        self._slice(rows, mode, frame)
        return True

    def _slice(self, rows, mode, frame):
        if self.locked:
            return
        changes, splits = {}, {}
        fps = self._frame_rate()
        for row in rows:
            _, _, first, last = self._row_frames(row)
            if not first < frame < last:
                continue
            effect_id = row[2]["id"]
            changes[effect_id] = (frame / fps, last / fps) if mode == MenuSlice.KEEP_RIGHT else (first / fps, frame / fps)
            if mode == MenuSlice.KEEP_BOTH:
                splits[effect_id] = (frame / fps, last / fps)
        if not splits:
            self._save_ranges(rows, changes)
            return
        added = set()
        with self._transaction():
            for kind, owner, ids in self._owners(rows):
                stack = []
                for effect in self._stack(kind, owner):
                    effect_id = effect["id"]
                    if effect_id not in ids or effect_id not in splits:
                        stack.append(effect)
                        continue
                    left = dict(effect, clip_range=self._owner_range(kind, owner, changes[effect_id]))
                    right = dict(effect, id=self.app.project.generate_id(),
                                 clip_range=self._owner_range(kind, owner, splits[effect_id]))
                    stack.extend((left, right))
                    added.update((effect_id, right["id"]))
                if kind == "clip":
                    stack = [dict(effect, stack_order=i) for i, effect in enumerate(stack)]
                self._save_stack(owner, stack, refresh=False)
        self._set_selection(added, self.selected_id)
        self.timeline.window.refreshFrameSignal.emit()

    def copy_selected(self):
        rows = self._selection_rows()
        if not self.active or not rows:
            return False
        effects = []
        for kind, owner, effect, first, last in rows:
            data = deepcopy(effect)
            if kind == "clip" and data.get("clip_range"):
                position = owner.data["position"]
                data["clip_range"] = {"start": first - position, "end": last - position}
            source_frame = round(owner.data["start"] * self._frame_rate()) if kind == "clip" else 0
            effects.append({"kind": kind, "effect": data, "source_frame": source_frame})
        mime = QMimeData()
        mime.setData(EFFECT_RANGES_MIME, json.dumps(effects).encode("utf-8"))
        QApplication.clipboard().setMimeData(mime)
        return True

    def paste_effects(self, mime, clip=None):
        if self.locked:
            return
        try:
            entries = json.loads(bytes(mime.data(EFFECT_RANGES_MIME)))
        except (UnicodeDecodeError, ValueError):
            return
        if not isinstance(entries, list):
            return
        selected = self._selected()
        if clip is None and self.active and self.clip_id and (selected is None or selected[0] == "clip"):
            clip = Clip.get(id=self.clip_id)
        kind = "clip" if clip else "track"
        owner = clip or self._track()
        if owner is None or (clip and self.timeline._is_track_locked(clip.data["layer"])):
            return

        stack = self._stack(kind, owner)
        if kind == "clip":
            # Preserve legacy stack ordering before appending within each transform pass.
            stack = [dict(effect, stack_order=i) for i, effect in enumerate(stack)]

        pasted, ids = [], {}
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("kind") != kind:
                continue
            data = entry.get("effect")
            if not isinstance(data, dict) or not isinstance(data.get("type"), str) or data["type"] not in self.catalog:
                continue
            if kind == "clip" and data.get("clip_range"):
                trim = data["clip_range"]
                if not isinstance(trim, dict) or not all(
                    isinstance(trim.get(key), (int, float)) and math.isfinite(trim[key]) for key in ("start", "end")
                ):
                    continue
                start = owner.data["start"]
                first = max(start, start + trim["start"])
                last = min(owner.data["end"], start + trim["end"])
                if round((last - first) * self._frame_rate()) < 1:
                    continue
                data = dict(data, clip_range={"start": first, "end": last})
            source_frame = entry.get("source_frame")
            if kind == "clip" and isinstance(source_frame, int):
                frames = round(owner.data["start"] * self._frame_rate()) - source_frame
                if frames:
                    data = shift_effect_keyframes(data, frames)
            original_id = data.get("id")
            new_id = self.app.project.generate_id()
            if isinstance(original_id, str):
                ids[original_id] = new_id
            pasted.append(dict(data, id=new_id, stack_order=len(stack) + len(pasted)))
        if not pasted:
            return
        for data in pasted:
            source = data.get("mask_source_id")
            if isinstance(source, str) and source in ids:
                data["mask_source_id"] = ids[source]
        self._save_stack(owner, stack + pasted)
        self.active = True
        self._set_selection({data["id"] for data in pasted})
        if clip:
            self._reveal_clip_section(clip.id)

    def _show_keyframes(self):
        selected = self._selected()
        if selected is None:
            return
        kind, owner, effect = selected
        selection_kind = "transition" if kind == "transition" else "effect"
        self.timeline.window.addSelection(effect["id"], selection_kind, True)
        self.timeline._toggle_track_panel(self.track_number)

    def _stack(self, kind, owner):
        effects = owner.data.get("effects") or []
        return sorted(effects, key=clip_effect_sort_key) if kind == "clip" else list(effects)

    def _reorder_indices(self, kind, owner, effect, step):
        stack = self._stack(kind, owner)
        index = next((i for i, entry in enumerate(stack) if entry["id"] == effect["id"]), -1)
        neighbor = index + step
        if index < 0 or not 0 <= neighbor < len(stack):
            return None
        if kind == "clip" and stack[neighbor].get("apply_before_clip", True) != effect.get("apply_before_clip", True):
            return None
        return index, neighbor

    def _save_stack(self, owner, effects, *, refresh=True):
        owner.data = {"effects": effects}
        owner.save()
        if refresh:
            self.timeline.window.refreshFrameSignal.emit()

    @contextmanager
    def _transaction(self, transaction=None):
        updates = self.app.updates
        previous = updates.transaction_id
        updates.transaction_id = previous or transaction or str(uuid.uuid4())
        try:
            yield
        finally:
            updates.transaction_id = previous

    def _add_effect(self, name):
        track = self._track()
        if not track or track.data.get("lock") or not self._can_add(name):
            return
        effect = openshot.EffectInfo().CreateEffect(name)
        if effect is None:
            return
        data = json.loads(effect.Json())
        if data.get("has_tracked_object"):
            return
        data["id"] = self.app.project.generate_id()
        self._save_stack(track, self._stack("track", track) + [data])
        self.active = True
        self._set_selection({data["id"]})

    def _move(self, step):
        row = self._selected()
        if row is None or self.locked:
            return
        kind, owner, effect = row
        owner = (Clip if kind == "clip" else Track).get(id=owner.id)
        if owner is None:
            return
        indices = self._reorder_indices(kind, owner, effect, step)
        if indices is None:
            return
        index, neighbor = indices
        stack = self._stack(kind, owner)
        stack[index], stack[neighbor] = stack[neighbor], stack[index]
        if kind == "track":
            self._save_stack(owner, stack)
            return

        updates = self.app.updates
        previous_transaction = updates.transaction_id
        updates.transaction_id = previous_transaction or str(uuid.uuid4())
        try:
            for order, entry in enumerate(stack):
                if entry.get("stack_order") != order:
                    key = ["clips", {"id": owner.id}, "effects", {"id": entry["id"]}]
                    updates.update(key, {"stack_order": order})
        finally:
            updates.transaction_id = previous_transaction
        self.timeline.window.refreshFrameSignal.emit()

    def _show_properties(self):
        row = self._selected()
        if row is None:
            return
        kind, _, effect = row
        self.timeline.window.addSelection(effect["id"], "transition" if kind == "transition" else "effect", True)
        self.timeline.window.actionProperties_trigger()

    def _owners(self, rows):
        groups = {}
        for kind, owner, effect, _, _ in rows:
            groups.setdefault((kind, owner.id), set()).add(effect["id"])
        for (kind, owner_id), ids in groups.items():
            owner = (Clip if kind == "clip" else Track).get(id=owner_id)
            if owner is not None:
                yield kind, owner, ids

    def delete_selected(self):
        rows = self._selection_rows()
        if not self.active or not rows:
            return False
        if not self.locked:
            with self._transaction():
                for kind, owner, ids in self._owners(rows):
                    self._save_stack(owner, [effect for effect in self._stack(kind, owner)
                                             if effect["id"] not in ids], refresh=False)
            for _, _, effect, _, _ in rows:
                self.timeline.window.removeSelection(effect["id"], "effect")
            self._set_selection(set())
            self.timeline.window.refreshFrameSignal.emit()
        return True

    def reset_timing(self):
        if not self.locked:
            rows = self._selection_rows()
            self._save_ranges(rows, {row[2]["id"]: None for row in rows if row[2].get("clip_range")})

    def _owner_range(self, kind, owner, seconds):
        offset = owner.data["start"] - owner.data["position"] if kind == "clip" else 0.0
        return {key: time + offset for key, time in zip(("start", "end"), seconds)}

    def _save_ranges(self, rows, ranges, transaction=None, *, move_keys=False):
        if not ranges:
            return
        with self._transaction(transaction):
            for kind, owner, effect, first, _ in rows:
                effect_id = effect["id"]
                if effect_id not in ranges:
                    continue
                current = Effect.get(id=effect_id)
                if current:
                    seconds = ranges[effect_id]
                    patch = {"clip_range": self._owner_range(kind, owner, seconds) if seconds else None}
                    if move_keys and seconds:
                        frames = round((seconds[0] - first) * self._frame_rate())
                        shifted = shift_effect_keyframes(current.data, frames)
                        patch.update({key: value for key, value in shifted.items() if value != current.data[key]})
                    current.data = patch
                    current.save()
        self.timeline.window.refreshFrameSignal.emit()
