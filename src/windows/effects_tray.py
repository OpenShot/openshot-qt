"""Shared editor for effects and transitions on one timeline track."""

import json
import uuid

import openshot
from qt_api import QApplication, QColor, QFont, QFontMetrics, QObject, QPointF, QRectF, Qt

from classes.app import get_app
from classes.effect_init import effect_options
from classes.query import Clip, Effect, Track, Transition
from classes.qt_types import font_metrics_horizontal_advance
from windows.views.menu import StyledContextMenu


def clip_effect_sort_key(effect):
    """Match the native before/after-transform passes and legacy effect order."""
    phase = not effect.get("apply_before_clip", True)
    order = effect.get("stack_order", -1)
    if order >= 0:
        return phase, 0, order
    return phase, 1, effect.get("layer", 0), effect.get("position", 0), -effect.get("order", 0)


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
        self.locked = False
        self._press = None
        self._preview = None

    def open_track(self, track_id):
        if track_id == self.track_id:
            self.close()
            return
        self.track_id = track_id
        self.selected_id = None
        self.refresh()
        self._invalidate()

    def close(self):
        self.track_id = None
        self.track_number = None
        self.rows = []
        self.selected_id = None
        self._press = self._preview = None
        self._invalidate()

    def _invalidate(self):
        self.timeline.geometry.mark_dirty()
        self.timeline.update()

    def height(self, track_number):
        if self.track_id is None or self.track_number != track_number:
            return 0
        return self.header_height + max(1, len(self.rows)) * self.row_height + self.bottom_padding

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
        rows = [("track", track, effect, 0.0, None) for effect in track.data.get("effects") or []]
        for clip in sorted(Clip.filter(layer=layer), key=lambda item: item.data["position"]):
            data = clip.data
            start, end, position = data["start"], data["end"], data["position"]
            for effect in sorted(data.get("effects") or [], key=clip_effect_sort_key):
                trim = effect.get("clip_range") or {}
                first = max(start, trim.get("start", start))
                last = min(end, trim.get("end", end))
                rows.append(("clip", clip, effect, position + first - start, position + last - start))
        for transition in sorted(Transition.filter(layer=layer), key=lambda item: item.data["position"]):
            data = transition.data
            first = data["position"]
            rows.append(("transition", transition, data, first, first + data["end"] - data["start"]))
        if rows != self.rows:
            self._press = self._preview = None
        self.rows = rows

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

    def _add_rect(self, lane):
        heading = self._heading_rect(lane)
        return QRectF(heading.right() + 9, lane.top() + 5, 24, 22)

    def _row_controls(self, index, lane):
        kind, owner, effect, _, _ = self.rows[index]
        if self.locked or self.selected_id != effect["id"] or kind == "transition":
            return ()
        rect = self._row_rect(index, lane)
        left = max(0.0, lane.left() - 66)
        return tuple(
            (name, glyph, QRectF(left + offset * 20, rect.y(), 18, rect.height()), enabled)
            for offset, (name, glyph, enabled) in enumerate((
                ("up", "↑", self._reorder_indices(kind, owner, effect, -1) is not None),
                ("down", "↓", self._reorder_indices(kind, owner, effect, 1) is not None),
                ("delete", "×", True),
            ))
        )

    def _row_rect(self, index, lane):
        top = lane.top() + self.header_height + index * self.row_height
        return QRectF(lane.left(), top + 3, max(0.0, lane.width() - 8), self.row_height - 9)

    def _bar_rect(self, index, lane):
        kind, _, effect, first, last = self.rows[index]
        row = self._row_rect(index, lane)
        w = self.timeline
        scale = w.pixels_per_second
        origin = lane.left() - w.h_scroll_offset
        if self._preview and self.selected_id == effect["id"]:
            first, last = self._preview
        x = origin + first * scale
        end = origin + last * scale if last is not None else row.right()
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
        if not self.locked:
            painter.drawRoundedRect(self._add_rect(lane), 5, 5)
            painter.setPen(accent)
            painter.drawText(self._add_rect(lane), Qt.AlignCenter, "+")
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

        for index, row in enumerate(self.rows):
            well_rect = self._row_rect(index, lane)
            if not well_rect.intersects(visible):
                continue
            kind, owner, effect, _, _ = row
            title = self._title(row)
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
            bar = self._bar_rect(index, lane).intersected(well_rect)
            if bar.isEmpty():
                continue
            chosen = self.selected_id == effect["id"]
            painter.setBrush(QColor("#f9fbff") if not chosen else QColor("#dcecff"))
            painter.setPen(accent if chosen else Qt.NoPen)
            painter.drawRoundedRect(bar, 4, 4)
            painter.setPen(QColor("#955010") if kind == "track" else QColor("#1557a7"))
            margin = 10 if chosen and kind == "clip" else 4
            pill_text = painter.fontMetrics().elidedText(title, Qt.ElideRight, max(0, int(bar.width()) - 2 * margin))
            painter.drawText(bar.adjusted(margin, 0, -margin, 0), Qt.AlignCenter, pill_text)
            if chosen and kind == "clip" and not self.locked:
                full = self._bar_rect(index, lane)
                for edge in (full.left(), full.right()):
                    if well_rect.left() <= edge <= well_rect.right():
                        x = min(max(edge, bar.left() + 3), bar.right() - 3)
                        painter.drawLine(QPointF(x, bar.center().y() - 4), QPointF(x, bar.center().y() + 4))

        if not self.rows:
            painter.setPen(detail)
            painter.drawText(self._row_rect(0, lane).adjusted(10, 0, 0, 0),
                             Qt.AlignLeft | Qt.AlignVCenter, self.translate("Add a track effect with +"))
        painter.restore()

    def _hit(self, pos):
        panel, lane, visible = self._bounds()
        if not visible.contains(pos):
            return None
        if pos.y() < panel.top() + self.header_height:
            if not self.locked and self._add_rect(lane).contains(pos):
                return ("add", None)
            return ("close" if self._heading_rect(lane).contains(pos) else "blank", None)
        index = int((pos.y() - panel.top() - self.header_height) // self.row_height)
        if 0 <= index < len(self.rows):
            for name, _, rect, enabled in self._row_controls(index, lane):
                if rect.contains(pos):
                    return (name if enabled else "blank", index)
            bar = self._bar_rect(index, lane)
            well = self._row_rect(index, lane)
            if pos.x() < lane.left() or bar.intersected(well).contains(pos):
                return ("row", index)
        return ("blank", None)

    def _trim_edge(self, index, pos):
        kind, _, effect, _, _ = self.rows[index]
        if kind != "clip" or self.selected_id != effect["id"] or self.locked:
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
        if target == "row" and self._trim_edge(index, pos) is not None:
            return Qt.SizeHorCursor
        return Qt.ArrowCursor if target == "blank" else Qt.PointingHandCursor

    def press(self, pos, button):
        hit = self._hit(pos)
        if hit is None or button not in (Qt.LeftButton, Qt.RightButton):
            return False
        target, index = hit
        if button == Qt.RightButton:
            if target == "row":
                self._select_row(index)
                self.timeline.update()
                self._show_menu(pos)
            return True
        edge = self._trim_edge(index, pos) if target == "row" else None
        self._press = (hit, QPointF(pos), edge)
        return True

    def move(self, pos):
        if self._press is None:
            return False
        (_, index), anchor, edge = self._press
        if edge is not None and (pos - anchor).manhattanLength() >= QApplication.startDragDistance():
            _, clip, _, first, last = self.rows[index]
            fps = self._frame_rate()
            scale = self.timeline.pixels_per_second
            if scale > 0 and last > first:
                delta = round((pos.x() - anchor.x()) / scale * fps)
                start = round(clip.data["position"] * fps)
                end = start + round((clip.data["end"] - clip.data["start"]) * fps)
                first, last = round(first * fps), round(last * fps)
                if edge == 0:
                    first = min(max(start, first + delta), last - 1)
                else:
                    last = max(min(end, last + delta), first + 1)
                self._preview = (first / fps, last / fps)
                self.timeline.update()
        return True

    def release(self, pos):
        if self._press is None:
            return False
        self.move(pos)
        hit, anchor, _ = self._press
        preview = self._preview
        self._press = self._preview = None
        target, index = hit
        if preview is not None:
            _, clip, effect, first, last = self.rows[index]
            if preview != (first, last):
                position = clip.data["position"]
                start = clip.data["start"]
                self._save_range(effect["id"], {key: start + value - position
                                 for key, value in zip(("start", "end"), preview)})
        elif self._hit(pos) == hit and (pos - anchor).manhattanLength() < QApplication.startDragDistance():
            if target == "close":
                self.close()
            elif target == "add":
                self._add_menu(pos)
            elif target in ("up", "down"):
                self._move(-1 if target == "up" else 1)
            elif target == "delete":
                self._remove()
            elif target == "row":
                self._select_row(index)
        self.timeline.update()
        return True

    def _select_row(self, index):
        kind, _, effect, _, _ = self.rows[index]
        self.selected_id = effect["id"]
        selection_kind = "transition" if kind == "transition" else "effect"
        self.timeline.window.addSelection(self.selected_id, selection_kind, True)

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
            return _("Add track effect")
        if target == "close":
            return _("Hide effects and transitions")
        if target in ("up", "down", "delete"):
            return {"up": _("Move Up"), "down": _("Move Down"), "delete": _("Remove Effect")}[target]
        if target == "row":
            row = self.rows[index]
            kind, owner, _, _, _ = row
            if kind == "clip":
                return self._title(row) + " · " + owner.title()
            if kind == "track":
                return self._title(row) + " · " + _("Track effect")
            return self._title(row) + " · " + _("Transition")
        return ""

    def drop(self, pos, effect_name):
        hit = self._hit(pos)
        if hit is None:
            return False
        if hit[0] == "add":
            self._add_effect(effect_name)
        return True

    def _can_add(self, name):
        # Source-dependent effects need a clip reader or tracked objects.
        return name not in effect_options and name not in {"ObjectMask", "PitchShift"}

    def _add_menu(self, pos):
        track = self._track()
        if not track or track.data.get("lock"):
            return
        _ = self.translate
        menu = StyledContextMenu(parent=self.timeline)
        for data in sorted(json.loads(openshot.EffectInfo.Json()), key=lambda item: _(item["name"])):
            name = data["class_name"]
            if self._can_add(name) and not data.get("has_tracked_object"):
                menu.addAction(_(data["name"]), lambda checked=False, value=name: self._add_effect(value))
        menu.show_at(self.timeline.mapToGlobal(pos.toPoint()))

    def _show_menu(self, pos):
        if self._selected():
            menu = StyledContextMenu(parent=self.timeline)
            menu.addAction(self.translate("Properties"), self._show_properties)
            menu.show_at(self.timeline.mapToGlobal(pos.toPoint()))

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

    def _save_stack(self, owner, effects):
        owner.data = {"effects": effects}
        owner.save()
        self.timeline.window.refreshFrameSignal.emit()

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
        self.selected_id = data["id"] = self.app.project.generate_id()
        self._save_stack(track, self._stack("track", track) + [data])

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

    def _remove(self):
        row = self._selected()
        if row is None or self.locked:
            return
        kind, owner, effect = row
        owner = (Clip if kind == "clip" else Track).get(id=owner.id)
        if owner is not None:
            stack = [entry for entry in self._stack(kind, owner) if entry["id"] != effect["id"]]
            self._save_stack(owner, stack)
            self.timeline.window.removeSelection(effect["id"], "effect")

    def _save_range(self, effect_id, clip_range):
        current = Effect.get(id=effect_id)
        if current:
            current.data = {"clip_range": clip_range}
            current.save()
            self.timeline.window.refreshFrameSignal.emit()
