"""Shared editor for effects and transitions on one timeline track."""

import json
import uuid

import openshot
from qt_api import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget, QFormLayout,
    QHBoxLayout, QLabel, QPushButton, QSpinBox, QTimer, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from classes.app import get_app
from classes.effect_init import effect_options
from classes.query import Clip, Effect, Track, Transition


def clip_effect_sort_key(effect):
    """Match the native before/after-transform passes and legacy effect order."""
    phase = not effect.get("apply_before_clip", True)
    order = effect.get("stack_order", -1)
    if order >= 0:
        return phase, 0, order
    return phase, 1, effect.get("layer", 0), effect.get("position", 0), -effect.get("order", 0)


class EffectsTray(QDockWidget):
    def __init__(self, timeline):
        app = get_app()
        _ = app._tr
        super().__init__(_("Effects and Transitions"), timeline.window)
        self.timeline = timeline
        self.app = app
        self.translate = _
        self.setObjectName("dockTimelineEffects")
        self.track_id = None
        self._rows = []

        body = QWidget(self)
        layout = QVBoxLayout(body)
        controls = QHBoxLayout()
        self.video = QCheckBox(_("Show video"))
        self.audio = QCheckBox(_("Play audio"))
        self.video.clicked.connect(lambda checked: self._set_track("hidden", not checked))
        self.audio.clicked.connect(lambda checked: self._set_track("muted", not checked))
        controls.addWidget(self.video)
        controls.addWidget(self.audio)
        controls.addStretch(1)

        self.catalog = QComboBox()
        supported = [
            (_(effect["name"]), effect["class_name"])
            for effect in json.loads(openshot.EffectInfo.Json())
            if effect["class_name"] not in effect_options
            and not effect.get("has_tracked_object")
            and effect["class_name"] not in {"ObjectMask", "PitchShift"}
        ]
        for title, name in sorted(supported):
            self.catalog.addItem(title, name)
        controls.addWidget(self.catalog)
        self.add_button = self._button(controls, _("Add track effect"), self._add_effect)
        layout.addLayout(controls)

        self.list = QTreeWidget()
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setHeaderLabels([_("Effect"), _("Applies to"), _("Timeline frames")])
        self.list.currentItemChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(lambda *_: self._show_properties())
        layout.addWidget(self.list)

        actions = QHBoxLayout()
        self.up_button = self._button(actions, _("Move Up"), lambda: self._move(-1))
        self.down_button = self._button(actions, _("Move Down"), lambda: self._move(1))
        self.range_button = self._button(actions, _("Trim Effect"), self._edit_range)
        self.properties_button = self._button(actions, _("Properties"), self._show_properties)
        self.remove_button = self._button(actions, _("Remove Effect"), self._remove)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.setWidget(body)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)
        self.app.updates.add_listener(self)

    @staticmethod
    def _button(layout, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def open_track(self, track_id, clip_id=None, effect_id=None):
        self.track_id = track_id
        self.refresh(clip_id=clip_id, effect_id=effect_id)
        self.show()
        self.raise_()

    def changed(self, action):
        if action.type == "load":
            self.hide()
            self.track_id = None
        elif self.isVisible() and action.key and action.key[0] in {"layers", "clips", "effects", "fps"}:
            self._refresh_timer.start(0)

    def _track(self):
        return Track.get(id=self.track_id) if self.track_id else None

    def _selected(self):
        item = self.list.currentItem()
        index = self.list.indexOfTopLevelItem(item) if item is not None else -1
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def _frame_rate(self):
        fps = self.app.project.get("fps")
        return fps["num"] / fps["den"]

    def refresh(self, clip_id=None, effect_id=None):
        track = self._track()
        if not track:
            self.list.clear()
            self._rows.clear()
            self.hide()
            return
        _ = self.translate
        row = self._selected()
        if row and effect_id is None and clip_id is None:
            effect_id = row[2]["id"]

        self.setWindowTitle(_("Effects and Transitions") + " — " + self.timeline._track_display_label(track))
        locked = bool(track.data.get("lock"))
        self.video.setChecked(not track.data.get("hidden"))
        self.audio.setChecked(not track.data.get("muted"))
        for control in (self.add_button, self.video, self.audio, self.catalog):
            control.setEnabled(not locked)
        self.list.clear()
        self._rows = []
        selected = None

        def add(kind, owner, effect, scope, span):
            nonlocal selected
            title = effect.get("name") or effect.get("type") or _("Transition")
            item = QTreeWidgetItem([_(title), scope, span])
            self._rows.append((kind, owner, effect))
            self.list.addTopLevelItem(item)
            if effect["id"] == effect_id or (selected is None and kind == "clip" and owner.id == clip_id):
                selected = item

        layer = track.data["number"]
        for effect in track.data.get("effects") or []:
            add("track", track, effect, _("Track"), _("Entire track"))

        clips = sorted(Clip.filter(layer=layer), key=lambda clip: clip.data.get("position", 0.0))
        fps = self._frame_rate()
        for clip in clips:
            for effect in sorted(clip.data.get("effects") or [], key=clip_effect_sort_key):
                clip_range = effect.get("clip_range") or {}
                position = clip.data["position"]
                start = clip.data["start"]
                end = clip.data["end"]
                first = max(start, clip_range.get("start", start))
                last = min(end, clip_range.get("end", end))
                if first >= last:
                    span = _("Outside clip")
                elif not clip_range:
                    span = _("Entire clip")
                else:
                    span = self._span(position + first - start, position + last - start, fps)
                add("clip", clip, effect, _("Clip") + " · " + clip.title(), span)

        for transition in sorted(Transition.filter(layer=layer), key=lambda item: item.data["position"]):
            data = transition.data
            first = data["position"]
            last = first + data["end"] - data["start"]
            add("transition", transition, data, _("Transition"), self._span(first, last, fps))

        if selected is not None:
            self.list.setCurrentItem(selected)
        for column in (0, 1):
            self.list.resizeColumnToContents(column)
        self._update_buttons()

    @staticmethod
    def _span(start, end, fps):
        return f"{round(start * fps) + 1}–{round(end * fps)}"

    def _stack(self, kind, owner):
        effects = owner.data.get("effects") or []
        return sorted(effects, key=clip_effect_sort_key) if kind == "clip" else list(effects)

    def _update_buttons(self, *_):
        row = self._selected()
        track = self._track()
        editable = bool(row and track and not track.data.get("lock"))
        kind, owner, effect = row or (None, None, None)
        self.properties_button.setEnabled(editable)
        self.range_button.setEnabled(editable and kind == "clip")
        self.remove_button.setEnabled(editable and kind != "transition")
        stack = self._stack(kind, owner) if editable and kind != "transition" else []
        index = next((i for i, entry in enumerate(stack) if entry["id"] == effect["id"]), -1)
        for step, button in ((-1, self.up_button), (1, self.down_button)):
            neighbor = index + step
            same_phase = (
                kind != "clip" or (0 <= neighbor < len(stack) and
                stack[neighbor].get("apply_before_clip", True) == effect.get("apply_before_clip", True))
            )
            button.setEnabled(index >= 0 and 0 <= neighbor < len(stack) and same_phase)

    def _set_track(self, name, value):
        self.timeline.set_track_render_setting(self.track_id, name, value)

    def _save_stack(self, owner, effects):
        owner.data = {"effects": effects}
        owner.save()
        self.timeline.window.refreshFrameSignal.emit()

    def _add_effect(self):
        track = self._track()
        if not track or track.data.get("lock"):
            return
        effect = openshot.EffectInfo().CreateEffect(self.catalog.currentData())
        if effect is None:
            return
        effect.Id(self.app.project.generate_id())
        self._save_stack(track, self._stack("track", track) + [json.loads(effect.Json())])
        self.refresh(effect_id=effect.Id())

    def _move(self, step):
        if not (self.up_button if step < 0 else self.down_button).isEnabled():
            return
        kind, owner, effect = self._selected()
        owner = (Clip if kind == "clip" else Track).get(id=owner.id)
        if owner is None:
            return
        stack = self._stack(kind, owner)
        index = next((i for i, entry in enumerate(stack) if entry["id"] == effect["id"]), -1)
        neighbor = index + step
        if index < 0 or not 0 <= neighbor < len(stack):
            return
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
        if not self.properties_button.isEnabled():
            return
        kind, _, effect = self._selected()
        self.timeline.window.addSelection(effect["id"], "transition" if kind == "transition" else "effect", True)
        self.timeline.window.actionProperties_trigger()

    def _remove(self):
        if not self.remove_button.isEnabled():
            return
        kind, owner, effect = self._selected()
        owner = (Clip if kind == "clip" else Track).get(id=owner.id)
        if owner is not None:
            stack = [entry for entry in self._stack(kind, owner) if entry["id"] != effect["id"]]
            self._save_stack(owner, stack)
            self.timeline.window.removeSelection(effect["id"], "effect")

    def _edit_range(self):
        if not self.range_button.isEnabled():
            return
        _, clip, effect = self._selected()
        _ = self.translate
        fps = self._frame_rate()
        first = round(clip.data["start"] * fps)
        last = round(clip.data["end"] * fps)
        length = last - first
        if length < 1:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(_("Trim Effect"))
        layout = QFormLayout(dialog)
        entire = QCheckBox(_("Entire clip"))
        clip_range = effect.get("clip_range") or {}
        entire.setChecked(not clip_range)
        start = QSpinBox()
        end = QSpinBox()
        start.setRange(1, length)
        end.setRange(1, length)
        start.setValue(round(clip_range.get("start", clip.data["start"]) * fps) - first + 1)
        end.setValue(round(clip_range.get("end", clip.data["end"]) * fps) - first)
        end.setValue(max(start.value(), end.value()))
        start.valueChanged.connect(lambda value: end.setValue(max(value, end.value())))
        end.valueChanged.connect(lambda value: start.setValue(min(value, start.value())))
        for spin in (start, end):
            spin.setDisabled(entire.isChecked())
            entire.toggled.connect(spin.setDisabled)
        layout.addRow(entire)
        layout.addRow(QLabel(_("Frame numbers are relative to the visible clip.")))
        layout.addRow(_("First frame"), start)
        layout.addRow(_("Last frame"), end)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return
        current = Effect.get(id=effect["id"])
        if current:
            current.data = {"clip_range": None if entire.isChecked() else {
                "start": (first + start.value() - 1) / fps,
                "end": (first + end.value()) / fps,
            }}
            current.save()
            self.timeline.window.refreshFrameSignal.emit()
