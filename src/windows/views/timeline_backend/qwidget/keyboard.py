"""Keyboard selection, navigation, and editing for the timeline canvas."""

import copy
import uuid

from qt_api import Qt, QEvent
from classes.query import Clip, Transition


class KeyboardMixin:
    def _keyboard_items(self):
        self.geometry.ensure()
        return sorted(Clip.filter() + Transition.filter(),
                      key=lambda c: (c.data['position'], str(c.id)))

    def _keyboard_anchor(self, clips):
        selected = {str(i) for i in self.win.selected_clips + self.win.selected_transitions}
        anchor = getattr(self, '_keyboard_item_id', None)
        return next((c for c in clips if str(c.id) == anchor and anchor in selected),
                    next((c for c in clips if str(c.id) in selected), None))

    def _keyboard_time(self):
        return max(0, self.win.preview_thread.current_frame - 1) / self.fps_float

    def _keyboard_track(self, anchor=None):
        if anchor:
            self._keyboard_layer = anchor.data['layer']
            return anchor.data['layer']
        layers = [t.data['number'] for t in self.track_list]
        layer = getattr(self, '_keyboard_layer', None)
        if layer in layers:
            return layer
        time = self._keyboard_time()
        clips = self._keyboard_items()
        occupied = {c.data['layer'] for c in clips if c.data['position'] <= time <
                    c.data['position'] + c.data['end'] - c.data['start']}
        return next((layer for layer in layers if layer in occupied),
                    next((layer for layer in layers if any(c.data['layer'] == layer for c in clips)),
                         layers[0] if layers else None))

    def _keyboard_select(self, clip, extend=False):
        self._keyboard_end_trim_preview()
        kind = 'clip' if isinstance(clip, Clip) else 'transition'
        self._select_timeline_item(clip.id, kind, not extend)
        self._keyboard_item_id = str(clip.id)
        self._keyboard_layer = clip.data['layer']
        self._keyboard_edge = None
        self._keyboard_reveal(clip)

    def _keyboard_horizontal_fallback(self, clips, layer, position, direction):
        """Continue across tracks when the current track has no neighbor."""
        step = -1 if direction == 'left' else 1
        candidates = [c for c in clips if c.data['layer'] != layer
                      and (c.data['position'] - position) * step > 0]
        if not candidates:
            return None
        layers = [t.data['number'] for t in self.track_list]
        indices = {number: index for index, number in enumerate(layers)}
        origin = indices.get(layer, 0)
        return min(candidates, key=lambda c: (
            abs(c.data['position'] - position),
            abs(indices.get(c.data['layer'], len(layers)) - origin),
            str(c.id),
        ))

    def keyboard_select(self, direction, extend=False):
        clips = self._keyboard_items()
        anchor = self._keyboard_anchor(clips)
        layer = self._keyboard_track(anchor)
        time = self._keyboard_time()
        if direction == 'playhead':
            under = sorted((c for c in clips if c.data['position'] <= time <
                            c.data['position'] + c.data['end'] - c.data['start']),
                           key=lambda c: (-c.data['layer'], c.data['position'], str(c.id)))
            identities = tuple(str(c.id) for c in under)
            cycle_key = (self.win.preview_thread.current_frame, identities)
            previous = getattr(self, '_keyboard_playhead_cycle', None)
            index = 0
            if previous and previous[0] == cycle_key and anchor and str(anchor.id) == previous[1]:
                index = (identities.index(previous[1]) + 1) % len(under)
            if under:
                target = under[index]
                self._keyboard_select(target, extend)
                self._keyboard_playhead_cycle = (cycle_key, str(target.id))
            else:
                self._keyboard_playhead_cycle = None
            return
        self._keyboard_playhead_cycle = None
        if direction in ('up', 'down'):
            layers = [t.data['number'] for t in self.track_list]
            if layer not in layers:
                return
            indices = {number: index for index, number in enumerate(layers)}
            origin = indices[layer]
            step = -1 if direction == 'up' else 1
            candidates = [c for c in clips if c.data['layer'] in indices
                          and (indices[c.data['layer']] - origin) * step > 0]
            if not candidates:
                return
            start = anchor.data['position'] if anchor else time
            end = start + anchor.data['end'] - anchor.data['start'] if anchor else time
            center = (start + end) / 2

            def distance(clip):
                other_start = clip.data['position']
                other_end = other_start + clip.data['end'] - clip.data['start']
                gap = max(0, other_start - end, start - other_end)
                # Favor clips vertically aligned with the selection, even if
                # an intervening track contains unrelated clips elsewhere.
                return (gap, abs(indices[clip.data['layer']] - origin),
                        abs((other_start + other_end) / 2 - center),
                        other_start, str(clip.id))

            self._keyboard_select(min(candidates, key=distance), extend)
            return
        candidates = [c for c in clips if c.data['layer'] == layer]
        if not candidates:
            if direction in ('left', 'right'):
                target = self._keyboard_horizontal_fallback(clips, layer, time, direction)
                if target:
                    self._keyboard_select(target, extend)
            return
        if direction in ('left', 'right') and anchor in candidates:
            index = candidates.index(anchor) + (-1 if direction == 'left' else 1)
            if 0 <= index < len(candidates):
                target = candidates[index]
            else:
                target = self._keyboard_horizontal_fallback(
                    clips, layer, anchor.data['position'], direction)
                if target is None:
                    return
        else:
            under = [c for c in candidates if c.data['position'] <= time <
                     c.data['position'] + c.data['end'] - c.data['start']]
            if not under and direction in ('left', 'right'):
                candidates = [c for c in candidates if
                              (c.data['position'] - time) * (-1 if direction == 'left' else 1) >= 0]
                if not candidates:
                    target = self._keyboard_horizontal_fallback(clips, layer, time, direction)
                    if target:
                        self._keyboard_select(target, extend)
                    return
                target = candidates[-1] if direction == 'left' else candidates[0]
                self._keyboard_select(target, extend)
                return
            target = (under[-1] if under else min(candidates, key=lambda c: min(
                abs(c.data['position'] - time),
                abs(c.data['position'] + c.data['end'] - c.data['start'] - time))))
        self._keyboard_select(target, extend)

    def keyboard_step_frames(self, frames):
        self.win.PauseSignal.emit()
        self.win.SeekSignal.emit(max(1, self.win.preview_thread.current_frame + frames), True)

    def keyboard_edit_point(self, direction):
        clips = self._keyboard_items()
        layer = self._keyboard_track(self._keyboard_anchor(clips))
        frame = self.win.preview_thread.current_frame
        boundaries = {round(t * self.fps_float) + 1 for c in clips if c.data['layer'] == layer
                      for t in (c.data['position'], c.data['position'] + c.data['end'] - c.data['start'])}
        candidates = [f for f in boundaries if (f - frame) * direction > 0]
        if candidates:
            target = min(candidates) if direction > 0 else max(candidates)
            self.win.PauseSignal.emit()
            self.win.SeekSignal.emit(int(target), True)

    def _keyboard_selected_items(self):
        clips = (Clip.get(id=i) for i in self.win.selected_clips)
        transitions = (Transition.get(id=i) for i in self.win.selected_transitions)
        return [clip for clip in clips if clip] + [trans for trans in transitions if trans]

    def keyboard_move_track(self, direction):
        self.geometry.ensure()
        items = self._keyboard_selected_items()
        layers = [t.data['number'] for t in self.track_list]
        moves = []
        for item in items:
            layer = item.data['layer']
            if layer not in layers or self._is_track_locked(layer):
                return
            index = layers.index(layer) + direction
            if not 0 <= index < len(layers) or self._is_track_locked(layers[index]):
                return
            moves.append((item, layers[index]))
        transaction = str(uuid.uuid4())
        for item, layer in moves:
            data = dict(item.data, layer=layer)
            update = self.update_clip_data if isinstance(item, Clip) else self.update_transition_data
            update(data, only_basic_props=True, transaction_id=transaction)
        if moves:
            self._keyboard_end_trim_preview()
            self._keyboard_layer = moves[0][1]
            self._keyboard_edge = None
            item = moves[0][0]
            model = Clip if isinstance(item, Clip) else Transition
            self._keyboard_reveal(model.get(id=item.id) or item)

    def _keyboard_preview_edge(self, clip, edge):
        timeline = getattr(self.win, 'timeline', None)
        if not timeline or not self.fps_float:
            return
        if not getattr(self, '_keyboard_trim_preview', False):
            self.win.TrimPreviewMode.emit()
            self._keyboard_trim_preview = True
        start_frame = int(round(clip.data['start'] * self.fps_float)) + 1
        # End is exclusive: show the final included frame, not the next clip.
        frame = start_frame if edge == 'left' else max(
            start_frame, int(round(clip.data['end'] * self.fps_float)))
        preview = timeline.PreviewClipFrame if isinstance(clip, Clip) else timeline.PreviewTransitionFrame
        preview(str(clip.id), max(1, frame))

    def _keyboard_end_trim_preview(self):
        if not getattr(self, '_keyboard_trim_preview', False):
            return
        self._keyboard_trim_preview = False
        self.win.TimelinePreviewMode.emit()
        frame = self.win.preview_thread.frame_step_position()
        self.win.SeekSignal.emit(frame, False)

    def keyboard_select_edge(self, edge):
        clips = self._keyboard_items()
        clip = self._keyboard_anchor(clips)
        if not clip:
            self.keyboard_select('playhead')
            clip = self._keyboard_anchor(clips)
        if clip:
            self._keyboard_item_id = str(clip.id)
            self._keyboard_edge = (str(clip.id), edge)
            self._keyboard_reveal(clip)
            self._keyboard_preview_edge(clip, edge)
            self.update()

    def keyboard_nudge(self, frames):
        if getattr(self, '_keyboard_nudge_key', None) is not None:
            self._keyboard_preview_nudge(frames)
            return
        self.geometry.ensure()
        items = self._keyboard_selected_items()
        if not items or any(self._is_track_locked(c.data['layer']) for c in items):
            return
        edge = getattr(self, '_keyboard_edge', None)
        clip = next((c for c in items if edge and str(c.id) == edge[0]), None)
        if clip:
            self._keyboard_preview_edge(clip, edge[1])
            # Use the same source limits, frame quantization, and commit path as mouse trimming.
            previous_edge, timing = self._resize_edge, self.enable_timing
            try:
                self._resize_edge, self.enable_timing = edge[1], False
                context = self._build_resize_context(clip)
                target = self._resize_edge_value(clip, edge[1]) + frames / self.fps_float
                if isinstance(clip, Clip):
                    compute, commit = self._compute_clip_resize, self._commit_resized_clip
                else:
                    compute, commit = self._compute_transition_resize, self._commit_resized_transition
                _rect, start, end, position = compute(clip, context, target)
                commit(clip, start, end, position, context, str(uuid.uuid4()), False)
            finally:
                self._resize_edge, self.enable_timing = previous_edge, timing
            self._keyboard_preview_edge(clip, edge[1])
        else:
            self._keyboard_edge = None
            self.Nudge_Triggered(frames, self.win.selected_clips, self.win.selected_transitions)
        item = clip or items[0]
        model = Clip if isinstance(item, Clip) else Transition
        self._keyboard_reveal(model.get(id=item.id) or item)

    def _keyboard_preview_nudge(self, frames):
        """Preview key repeats locally, like a mouse drag; save on release."""
        gesture = getattr(self, '_keyboard_nudge_gesture', None)
        if gesture is None:
            self.geometry.ensure()
            selected = self._keyboard_selected_items()
            if not selected or any(self._is_track_locked(c.data['layer']) for c in selected):
                return
            edge = getattr(self, '_keyboard_edge', None)
            target = next((c for c in selected if edge and str(c.id) == edge[0]), None)
            items = []
            for original in ([target] if target else selected):
                item = copy.copy(original)
                item.data = dict(original.data)
                items.append(item)
            gesture = dict(items=items, initial=[dict(item.data) for item in items],
                           edge=edge if target else None, transaction=str(uuid.uuid4()))
            if target:
                timing = self.enable_timing
                try:
                    self.enable_timing = False
                    gesture['context'] = self._build_resize_context(target)
                finally:
                    self.enable_timing = timing
            self._keyboard_nudge_gesture = gesture

        items = gesture['items']
        if gesture['edge']:
            item = items[0]
            edge = gesture['edge'][1]
            previous_edge, timing = self._resize_edge, self.enable_timing
            try:
                self._resize_edge, self.enable_timing = edge, False
                target = self._resize_edge_value(item, edge) + frames / self.fps_float
                compute = self._compute_clip_resize if isinstance(item, Clip) else self._compute_transition_resize
                _rect, start, end, position = compute(item, gesture['context'], target)
                start, end, position = self._normalize_resize_commit_bounds(start, end, position)
                item.data.update(start=start, end=end, position=position, duration=end-start)
                self._apply_resize_preview_override(item, gesture['context'], start, end, position)
            finally:
                self._resize_edge, self.enable_timing = previous_edge, timing
            self._keyboard_preview_edge(item, edge)
        else:
            minimum = -min(data['position'] for data in gesture['initial'])
            gesture['frames'] = max(gesture.get('frames', 0) + frames, minimum * self.fps_float)
            delta = max(gesture['frames'] / self.fps_float, minimum)
            for item, initial in zip(items, gesture['initial']):
                item.data['position'] = initial['position'] + delta
                overrides = (self._pending_clip_overrides if isinstance(item, Clip)
                             else self._pending_transition_overrides)
                overrides.setdefault(item.id, {})['position'] = item.data['position']
        self._keyframes_dirty = True
        self._keyboard_reveal(items[0])

    def _keyboard_finish_nudge(self):
        gesture = getattr(self, '_keyboard_nudge_gesture', None)
        self._keyboard_nudge_gesture = None
        self._keyboard_nudge_key = None
        if gesture is None:
            return
        changed = []
        for item, original in zip(gesture['items'], gesture['initial']):
            if all(item.data[key] == original[key] for key in ('position', 'start', 'end')):
                continue
            model = Clip if isinstance(item, Clip) else Transition
            current = model.get(id=item.id)
            if current is not None:
                changed.append((item, current))
        timing = self.enable_timing
        try:
            self.enable_timing = False
            for index, (item, current) in enumerate(changed):
                ignore_refresh = index < len(changed) - 1
                if gesture['edge']:
                    commit = self._commit_resized_clip if isinstance(item, Clip) else self._commit_resized_transition
                    commit(item, item.data['start'], item.data['end'], item.data['position'],
                           gesture['context'], gesture['transaction'], ignore_refresh)
                else:
                    update = self.update_clip_data if isinstance(item, Clip) else self.update_transition_data
                    data = dict(current.data, position=item.data['position'])
                    update(data, only_basic_props=True, ignore_refresh=ignore_refresh,
                           transaction_id=gesture['transaction'])
        finally:
            self.enable_timing = timing
            for item in gesture['items']:
                overrides = (self._pending_clip_overrides if isinstance(item, Clip)
                             else self._pending_transition_overrides)
                overrides.pop(item.id, None)
            self.geometry.mark_dirty()
            self._keyframes_dirty = True
            self.update()

    def event(self, event):
        # Shortcut presses are consumed by QShortcut before keyPressEvent.
        # ShortcutOverride still reaches the canvas, including for custom keys.
        if event.type() == QEvent.ShortcutOverride:
            key = getattr(self, '_keyboard_nudge_key', None)
            if key != event.key() or not event.isAutoRepeat():
                self._keyboard_finish_nudge()
            self._keyboard_nudge_key = event.key()
        elif event.type() == QEvent.KeyRelease and not event.isAutoRepeat():
            if event.key() == getattr(self, '_keyboard_nudge_key', None):
                self._keyboard_finish_nudge()
        elif event.type() in (QEvent.FocusOut, QEvent.WindowDeactivate, QEvent.Hide,
                              QEvent.MouseButtonPress):
            self._keyboard_finish_nudge()
        return super().event(event)

    def _keyboard_reveal(self, item):
        self.geometry.mark_dirty()
        self.geometry.ensure()
        rect = self.geometry.calc_item_rect(item, viewport=True)
        left, right = self.track_name_width + 8, self.width() - self.scroll_bar_thickness - 8
        offset = rect.left() - left if rect.left() < left else max(0, rect.right() - right)
        if rect.width() > right - left:
            edge = getattr(self, '_keyboard_edge', None)
            offset = rect.right() - right if edge == (str(item.id), 'right') else rect.left() - left
        total = self.scrollbar_position[2]
        if total:
            self.set_scroll_left((self.h_scroll_offset + offset) / total)
        top, bottom = self.ruler_height + 4, self.height() - self.scroll_bar_thickness - 4
        delta = rect.top() - top if rect.top() < top else max(0, rect.bottom() - bottom)
        total = self.v_scrollbar_position[2]
        if total:
            span = self.v_scrollbar_position[1] - self.v_scrollbar_position[0]
            start = max(0, min(1 - span, self.v_scrollbar_position[0] + delta / total))
            self.v_scrollbar_position[:2] = [start, start + span]
        self.geometry.mark_dirty()
        self.update()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._asset_target_layer = None
        self.update()

    def focusOutEvent(self, event):
        self._keyboard_end_trim_preview()
        super().focusOutEvent(event)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and getattr(self, '_keyboard_edge', None):
            self._keyboard_end_trim_preview()
            self._keyboard_edge = None
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)
