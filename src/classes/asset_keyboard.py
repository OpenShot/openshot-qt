"""Keyboard access to asset browsers and their timeline destinations."""

import json
import uuid

from qt_api import Qt, QPointF, QAbstractItemView, QToolTip, QItemSelectionModel
from classes.app import get_app
from classes.query import Clip
from classes import tabstops


class AssetKeyboardMixin:
    def _asset_browsers(self):
        return (
            ('files', self.dockFiles, self.filesView),
            ('effects', self.dockEffects, self.effectsView),
            ('transitions', self.dockTransitions, self.transitionsView),
            ('emojis', self.dockEmojis, self.emojiListView),
        )

    @staticmethod
    def _asset_model(view):
        # Some existing views expose their proxy model as an attribute.
        model = view.model
        return model() if callable(model) else model

    def _asset_target_track(self):
        timeline = self.timeline
        timeline.geometry.ensure()
        items = timeline._keyboard_items()
        anchor = timeline._keyboard_anchor(items)
        layers = [track.data['number'] for track in timeline.track_list]
        layer = anchor.data['layer'] if anchor else getattr(timeline, '_keyboard_layer', None)
        if layer not in layers:
            layer = next((n for n in layers if not timeline._is_track_locked(n)), None)
        timeline._keyboard_layer = layer
        timeline._asset_target_layer = layer
        timeline.update()
        return layer

    def _focus_asset_browser(self, kind):
        for name, dock, view in self._asset_browsers():
            if name != kind:
                continue
            if kind != 'effects':
                self._asset_target_track()
            else:
                self.timeline._asset_target_layer = None
                self.timeline.update()
            dock.show()
            dock.raise_()
            tabstops.apply_auto_tab_order(self)
            view.setFocus(Qt.ShortcutFocusReason)
            model = self._asset_model(view)
            if not view.currentIndex().isValid() and model.rowCount():
                view.setCurrentIndex(model.index(0, 0))
            if view.currentIndex().isValid():
                if not view.selectionModel().hasSelection():
                    view.selectionModel().select(view.currentIndex(),
                                                 QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                view.scrollTo(view.currentIndex())
            return

    def focusProjectFiles(self):
        self._focus_asset_browser('files')

    def focusEffects(self):
        self._focus_asset_browser('effects')

    def focusTransitions(self):
        self._focus_asset_browser('transitions')

    def focusEmojis(self):
        self._focus_asset_browser('emojis')

    def addSelectedAsset(self):
        """Apply the browser selection, keeping focus and selection in that browser."""
        browser = next(((kind, view) for kind, _dock, view in self._asset_browsers()
                        if view.hasFocus()), None)
        if browser is None:
            return  # Never treat typing in a filter/editor as an asset command.
        kind, view = browser
        if view.state() == QAbstractItemView.EditingState:
            return
        rows = sorted(view.selectionModel().selectedRows(0), key=lambda index: index.row())
        if not rows:
            return
        model = self._asset_model(view)
        payload = json.loads(model.mimeData(rows).text())
        if not payload:
            return
        timeline = self.timeline
        if kind == 'effects':
            selected = (Clip.get(id=identity) for identity in self.selected_clips)
            clips = [clip for clip in selected if clip]
            if not clips:
                self._asset_message(view, get_app()._tr('Select a timeline clip before applying an effect.'))
                return
            if any(timeline._is_track_locked(clip.data['layer']) for clip in clips):
                self._asset_message(view, get_app()._tr('The selected clips include a locked track.'))
                return
        else:
            layer = self._asset_target_track()
            if layer is None or timeline._is_track_locked(layer):
                self._asset_message(view, get_app()._tr('Choose an unlocked timeline track before adding an asset.'))
                return
        app = get_app()
        previous_transaction = app.updates.transaction_id
        previous_ids = timeline.item_ids
        app.updates.transaction_id = str(uuid.uuid4())
        timeline.item_ids = []
        try:
            if kind == 'effects':
                for clip in clips:
                    for effect in payload:
                        timeline._apply_effect_to_clip(clip, effect)
                return
            fps = app.project.get('fps')
            fps_float = fps['num'] / fps['den']
            position = max(0, self.preview_thread.current_frame - 1) / fps_float
            created = []
            for index, asset in enumerate(payload):
                if kind == 'emojis':
                    source = view.group_model.mapToSource(model.mapToSource(rows[index]))
                    name = view.emojis_model.model.itemFromIndex(source).text()
                    file = view.add_file(asset, name)
                    if not file:
                        continue
                    asset = file.id
                if kind == 'transitions':
                    item = timeline.addTransition(asset, QPointF(position, 0), layer,
                                                  call_manual_move=False)
                else:
                    item = timeline.addClip(asset, QPointF(position, 0), layer,
                                            call_manual_move=False, auto_transition=len(payload) == 1)
                if item:
                    created.append(item)
                    position += item['end'] - item['start']
            item_type = 'transition' if kind == 'transitions' else 'clip'
            for index, item in enumerate(created):
                self.addSelection(item['id'], item_type, clear_existing=index == 0)
            if created:
                timeline._keyboard_item_id = str(created[-1]['id'])
                timeline._keyboard_edge = None
                timeline.geometry.mark_dirty()
                timeline.update()
        finally:
            app.updates.transaction_id = previous_transaction
            timeline.item_ids = previous_ids

    @staticmethod
    def _asset_message(view, text):
        QToolTip.showText(view.mapToGlobal(view.rect().center()), text, view)
