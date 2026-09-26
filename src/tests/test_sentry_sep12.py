"""Regression coverage for the September 12 Sentry fixes."""

import copy
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import openshot
from qt_api import QComboBox, QLabel, QRect
from classes.query import Clip
from tests.qt_test_app import get_or_create_app
from tests.test_project_data import DummyApp, ensure_app_state, make_store


class SentrySeptemberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(DummyApp)
        ensure_app_state(cls.app)
        metrics = types.ModuleType("classes.metrics")
        metrics.track_metric_screen = Mock()
        metrics.track_metric_error = Mock()
        with patch.dict(sys.modules, {"classes.metrics": metrics}):
            cls.export = importlib.import_module("windows.export")
            cls.title = importlib.import_module("windows.title_editor")
            cls.video = importlib.import_module("windows.video_widget")
            cls.timeline = importlib.import_module("windows.views.timeline")

    def test_preview_title_before_worker_start_and_after_shutdown(self):
        dock = Mock()
        helper = Mock()
        helper.centeredViewport.return_value = QRect(0, 0, 320, 180)
        helper.devicePixelRatioF.return_value = 1
        helper.parent.return_value.parent.return_value = dock
        helper.settings = {"preview-fps": False}
        helper.region_enabled = False
        helper.transforming_effect = False
        helper.transforming_clips = False
        player = Mock()
        player.Mode.return_value = openshot.PLAYBACK_PLAY
        player.Speed.return_value = 2.0
        app = types.SimpleNamespace(_tr=lambda text: text)
        with patch.object(self.video, "get_app", return_value=app):
            for window in (types.SimpleNamespace(), types.SimpleNamespace(preview_thread=None)):
                helper.win = window
                self.video.VideoWidget.update_title(helper)
                dock.setWindowTitle.assert_called_with("Video Preview")
            helper.win = types.SimpleNamespace(preview_thread=types.SimpleNamespace(player=player))
            self.video.VideoWidget.update_title(helper)
            dock.setWindowTitle.assert_called_with("Video Preview (2.0x)")
            player.Mode.return_value = openshot.PLAYBACK_PAUSED
            self.video.VideoWidget.update_title(helper)
            dock.setWindowTitle.assert_called_with("Video Preview")

    def test_channel_layout_combo_clear_preserves_native_layout(self):
        combo = QComboBox()
        timeline = openshot.Timeline(320, 180, openshot.Fraction(30, 1),
                                     44100, 2, openshot.LAYOUT_STEREO)
        helper = Mock()
        helper.timeline = timeline
        helper.cboChannelLayout = combo
        for name, value in {"Width": 320, "Height": 180, "FrameRateNum": 30,
                            "FrameRateDen": 1, "SampleRate": 44100, "Channels": 2}.items():
            getattr(helper, "txt" + name).value.return_value = value
        errors = []

        def changed(index):
            try:
                self.export.Export.updateFrameRate(helper, False)
            except Exception as ex:
                errors.append(ex)

        app = types.SimpleNamespace(project={"fps": {"num": 30, "den": 1}})
        with patch.object(self.export, "get_app", return_value=app):
            combo.currentIndexChanged.connect(changed)
            combo.addItem("Mono", openshot.LAYOUT_MONO)
            self.assertEqual(timeline.info.channel_layout, openshot.LAYOUT_MONO)
            combo.clear()
            self.assertEqual(timeline.info.channel_layout, openshot.LAYOUT_MONO)
            combo.addItem("Stereo", openshot.LAYOUT_STEREO)
            self.assertEqual(timeline.info.channel_layout, openshot.LAYOUT_STEREO)
        self.assertEqual(errors, [])

    def test_failed_asset_creation_aborts_save_before_mutating_project(self):
        store = make_store()
        store._data = {"clips": [], "files": []}
        store.current_filepath = "original.osp"
        store.has_unsaved_changes = True
        original = copy.deepcopy(store._data)
        with tempfile.TemporaryDirectory() as root:
            destination = os.path.join(root, "new.osp")
            with patch("classes.assets.os.mkdir", side_effect=PermissionError("denied")), \
                    patch.object(store, "write_to_file") as write, \
                    patch.object(store, "_sync_asset_root") as sync:
                with self.assertRaisesRegex(OSError, "Unable to create project assets"):
                    store.save(destination)
                write.assert_not_called()
                sync.assert_not_called()
            self.assertEqual(store._data, original)
            self.assertEqual(store.current_filepath, "original.osp")
            self.assertTrue(store.has_unsaved_changes)
            # The user can retry in a writable location; no poisoned save state.
            with patch.object(store, "_sync_asset_root"), \
                    patch("classes.project_data.log.error") as error:
                store.move_temp_paths_to_project_folder(destination)
                error.assert_not_called()
            self.assertTrue(os.path.isdir(os.path.join(root, "new_assets", "title")))

    def test_late_clip_update_does_not_reinsert_deleted_clip(self):
        helper = Mock()
        helper.delete_invalid_timeline_item.return_value = False
        helper.show_wait_spinner = False
        partial = {"id": "deleted", "layer": 3000000, "position": 0.0,
                   "start": 0.0, "end": 115.593, "duration": 115.593}
        with patch.object(Clip, "get", return_value=None), \
                patch.object(Clip, "save") as save:
            self.timeline.TimelineView.update_clip_data(helper, json.dumps(partial))
            save.assert_not_called()
            helper.window.IgnoreUpdates.emit.assert_not_called()

    def test_new_clip_keeps_reader_and_existing_clip_uses_partial_update(self):
        helper = Mock()
        helper.delete_invalid_timeline_item.return_value = False
        helper.show_wait_spinner = False
        reader = openshot.DummyReader(openshot.Fraction(30, 1), 320, 180, 44100, 2, 10.0)
        native_clip = openshot.Clip(reader)
        data = json.loads(native_clip.Json())
        data["id"] = "clip"
        saved = []
        with patch.object(Clip, "get", return_value=None), \
                patch.object(Clip, "save", autospec=True,
                             side_effect=lambda clip: saved.append(copy.deepcopy(clip.data))):
            self.timeline.TimelineView.update_clip_data(helper, copy.deepcopy(data),
                                                        only_basic_props=True, ignore_reader=True)
        self.assertEqual(saved[0]["reader"], data["reader"])
        self.assertIn("alpha", saved[0])
        existing = Clip()
        existing.id, existing.type, existing.data = "clip", "update", data
        with patch.object(Clip, "get", return_value=existing), \
                patch.object(Clip, "save", autospec=True,
                             side_effect=lambda clip: saved.append(copy.deepcopy(clip.data))):
            self.timeline.TimelineView.update_clip_data(helper, copy.deepcopy(data))
        self.assertNotIn("reader", saved[1])
        self.assertEqual(saved[1]["id"], "clip")
        self.assertEqual(saved[1]["end"], data["end"])

    def test_svg_preview_recovers_after_unreadable_title(self):
        label = QLabel()
        label.resize(320, 180)
        helper = types.SimpleNamespace(lblPreviewLabel=label, thumbnailReady=Mock())
        app = types.SimpleNamespace(devicePixelRatio=lambda: 1)
        with tempfile.TemporaryDirectory() as root, \
                patch.object(self.title, "get_app", return_value=app):
            helper.filename = os.path.join(root, "title.svg")
            for contents in (None, "<svg", '<svg xmlns="http://www.w3.org/2000/svg" '
                             'width="320" height="180"><rect width="320" height="180" '
                             'fill="red"/></svg>'):
                if contents is not None:
                    with open(helper.filename, "w") as svg:
                        svg.write(contents)
                self.title.TitleEditor.display_svg(helper)
                pixmap = helper.thumbnailReady.emit.call_args[0][0]
                if contents is None or contents == "<svg":
                    self.assertTrue(pixmap.isNull())
                else:
                    self.assertFalse(pixmap.isNull())
                    self.assertGreater(pixmap.toImage().pixelColor(160, 90).red(), 200)

    def test_title_worker_is_reusable_after_failure(self):
        helper = types.SimpleNamespace(filename="title.svg", xmldoc=object(),
                                       is_thread_busy=False, writeToFile=Mock(),
                                       display_svg=Mock(side_effect=RuntimeError("render failed")))
        with self.assertRaisesRegex(RuntimeError, "render failed"):
            self.title.TitleEditor.save_and_reload_thread(helper)
        self.assertFalse(helper.is_thread_busy)
        helper.display_svg.side_effect = None
        self.title.TitleEditor.save_and_reload_thread(helper)
        self.assertFalse(helper.is_thread_busy)
        self.assertEqual(helper.display_svg.call_count, 2)

    def test_svg_thumbnail_failure_closes_reader_and_removes_temp_file(self):
        label = QLabel()
        label.resize(320, 180)
        helper = types.SimpleNamespace(filename="title.svg", lblPreviewLabel=label,
                                       thumbnailReady=Mock())
        reader = Mock()
        reader.info = types.SimpleNamespace(width=320, height=180)
        reader.GetFrame.return_value.Thumbnail.side_effect = RuntimeError("render failed")
        app = types.SimpleNamespace(devicePixelRatio=lambda: 1)
        with tempfile.TemporaryDirectory() as root:
            descriptor, path = tempfile.mkstemp(dir=root)
            with patch.object(self.title.openshot, "QtImageReader", return_value=reader), \
                    patch.object(self.title, "get_app", return_value=app), \
                    patch.object(self.title.tempfile, "mkstemp", return_value=(descriptor, path)):
                self.title.TitleEditor.display_svg(helper)
            reader.Close.assert_called_once_with()
            self.assertFalse(os.path.exists(path))
            self.assertTrue(helper.thumbnailReady.emit.call_args[0][0].isNull())

    def test_redo_title_delete_refreshes_native_selection_before_next_listener(self):
        from classes.timeline import TimelineSync
        from classes.updates import UpdateAction, UpdateManager

        timeline = openshot.Timeline(320, 180, openshot.Fraction(30, 1),
                                     44100, 2, openshot.LAYOUT_STEREO)
        window = types.SimpleNamespace(proxy_service=None, IgnoreUpdates=Mock(), verifySelections=Mock())
        sync = types.SimpleNamespace(timeline=timeline, window=window)
        window.timeline_sync = sync
        preview = types.SimpleNamespace(
            win=window, transforming_clips=[], transforming_clip_objects=[],
            transforming_clip=None, transforming_clip_object=None,
            transforming_effect=None, transforming_effect_object=None)
        preview.refreshTriggered = lambda **kw: self.video.VideoWidget.refreshTriggered(preview, **kw)
        window.videoPreview = preview
        manager = UpdateManager()
        manager.add_listener(types.SimpleNamespace(changed=lambda action: TimelineSync.changed(sync, action)))
        observed = []
        manager.add_listener(types.SimpleNamespace(changed=lambda action: observed.append(
            [clip.id for clip in preview.transforming_clips])))
        rows = {}
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'title.svg')
            with open(path, 'w') as stream:
                stream.write('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="18">'
                             '<rect width="32" height="18" fill="red"/></svg>')
            source = openshot.Clip(path)
            source.Id('title')
            source.End(10)
            value = json.loads(source.Json())
            survivor = copy.deepcopy(value)
            survivor['id'] = 'survivor'
            for data in (value, survivor):
                timeline.ApplyJsonDiff(json.dumps([{
                    'type': 'insert', 'key': ['clips'], 'value': data}]))
                rows[data['id']] = types.SimpleNamespace(id=data['id'], data=data)
            preview.transforming_clips = list(rows.values())
            preview.transforming_clip_objects = [timeline.GetClip(cid) for cid in rows]
            preview.transforming_clip = rows['title']
            preview.transforming_clip_object = timeline.GetClip('title')
            with patch.object(self.video.Clip, 'get', side_effect=lambda id: rows.get(id)), \
                    patch('classes.updates.get_app', return_value=types.SimpleNamespace(window=window)):
                # Move five times, undo those moves, then redo through deletion.
                # Keep the project rows stale until after dispatch, matching the
                # native listener running ahead of the project-data listener.
                for position in range(1, 6):
                    action = UpdateAction('update', ['clips', {'id': 'title'}],
                                          {'position': position}, {'position': position - 1})
                    manager.actionHistory.append(action)
                    manager.dispatch_action(action)
                    self.assertEqual(preview.transforming_clip_object.Position(), position)
                deleted_value = dict(value, position=5)
                action = UpdateAction('delete', ['clips', {'id': 'title'}], None, deleted_value)
                manager.actionHistory.append(action)
                manager.dispatch_action(action)
                self.assertEqual(observed[-1], ['survivor'])
                manager.undo()
                # Select the restored title, then undo/redo its five moves.
                preview.transforming_clips = list(rows.values())
                preview.refreshTriggered()
                for position in range(4, -1, -1):
                    manager.undo()
                    self.assertEqual(preview.transforming_clip_object.Position(), position)
                for position in range(1, 6):
                    manager.redo()
                    self.assertEqual(preview.transforming_clip_object.Position(), position)
                manager.redo()
                self.assertIsNone(timeline.GetClip('title'))
                self.assertEqual(observed[-1], ['survivor'])
                self.assertEqual([c.id for c in preview.transforming_clips], ['survivor'])
                self.assertEqual(len(preview.transforming_clip_objects), 1)
                self.assertEqual(preview.transforming_clip_object.Id(), 'survivor')
                self.assertEqual(preview.transforming_clip_objects[0].Id(), 'survivor')
                # Deleting the remaining selected clip clears every borrowed pointer.
                manager.dispatch_action(UpdateAction('delete', ['clips', {'id': 'survivor'}]))
                self.assertEqual(preview.transforming_clip_objects, [])
                self.assertIsNone(preview.transforming_clip_object)
                self.assertIsNone(preview.transforming_clip)
        timeline.Clear()

    def test_refresh_rebinds_replaced_effect_and_clears_deleted_effect(self):
        timeline = openshot.Timeline(320, 180, openshot.Fraction(30, 1),
                                     44100, 2, openshot.LAYOUT_STEREO)
        reader = openshot.DummyReader(openshot.Fraction(30, 1), 320, 180, 44100, 2, 10.0)
        source = openshot.Clip(reader)
        source.Id('clip')
        effect = openshot.Crop()
        effect.Id('crop')
        source.AddEffect(effect)
        value = json.loads(source.Json())
        timeline.ApplyJsonDiff(json.dumps([{'type': 'insert', 'key': ['clips'], 'value': value}]))
        clip_row = types.SimpleNamespace(id='clip')
        effect_row = types.SimpleNamespace(id='crop')
        preview = types.SimpleNamespace(
            win=types.SimpleNamespace(timeline_sync=types.SimpleNamespace(timeline=timeline)),
            transforming_clips=[], transforming_clip_objects=[],
            transforming_clip=clip_row, transforming_clip_object=timeline.GetClip('clip'),
            transforming_effect=effect_row, transforming_effect_object=timeline.GetClipEffect('crop'))
        with patch.object(self.video.Clip, 'get', return_value=clip_row), \
                patch.object(self.video.Effect, 'get', return_value=effect_row):
            # Full clip updates replace the effect even when its ID is unchanged.
            timeline.ApplyJsonDiff(json.dumps([{
                'type': 'update', 'key': ['clips', {'id': 'clip'}], 'value': value}]))
            self.video.VideoWidget.refreshTriggered(preview)
            self.assertEqual(int(preview.transforming_effect_object.this),
                             int(timeline.GetClipEffect('crop').this))
            timeline.ApplyJsonDiff(json.dumps([{
                'type': 'delete', 'key': ['clips', {'id': 'clip'}], 'value': None}]))
            self.video.VideoWidget.refreshTriggered(preview)
            self.assertIsNone(preview.transforming_effect_object)
            self.assertIsNone(preview.transforming_clip_object)
            self.assertIsNone(preview.transforming_effect)
        timeline.Clear()

    def test_repeated_splits_keep_clip_edges_adjacent(self):
        from classes.timeline import TimelineSync
        from classes.updates import UpdateManager
        store = make_store()
        reader = openshot.DummyReader(openshot.Fraction(24, 1), 320, 180, 44100, 2, 600.0)
        source = openshot.Clip(reader)
        source.Id('long-clip')
        source.Position(10)
        source.Start(30)
        source.End(530)
        data = json.loads(source.Json())
        store._data = {'clips': [data], 'effects': [], 'layers': [], 'fps': {'num': 24, 'den': 1}}
        manager = UpdateManager()
        manager.add_listener(store)
        window = Mock()
        native = openshot.Timeline(320, 180, openshot.Fraction(24, 1), 44100, 2, openshot.LAYOUT_STEREO)
        native.ApplyJsonDiff(json.dumps([{'type': 'insert', 'key': ['clips'], 'value': data}]))
        sync = types.SimpleNamespace(timeline=native, window=window)
        window.timeline_sync = sync
        window.proxy_service = None
        preview = types.SimpleNamespace(win=window, transforming_clips=[], transforming_clip_objects=[],
                                        transforming_clip=None, transforming_clip_object=None,
                                        transforming_effect=None, transforming_effect_object=None)
        preview.refreshTriggered = lambda **kw: self.video.VideoWidget.refreshTriggered(preview, **kw)
        window.videoPreview = preview
        manager.add_listener(types.SimpleNamespace(changed=lambda action: TimelineSync.changed(sync, action)), 0)
        helper = Mock(window=window, show_wait_spinner=False)
        helper.delete_invalid_timeline_item.side_effect = lambda item: self.timeline.TimelineView.delete_invalid_timeline_item(helper, item)
        helper.update_clip_data.side_effect = lambda data, **kw: self.timeline.TimelineView.update_clip_data(helper, data, **kw)
        helper.get_uuid.side_effect = ['cut-1', 'cut-2', 'cut-3', 'keep-left']
        with patch.object(self.app, 'project', store), patch.object(self.app, 'updates', manager), \
                patch.object(self.app, 'window', window):
            for cut in (110, 210, 310):
                target = max(store._data['clips'], key=lambda clip: clip['position'])
                preview.transforming_clips = [Clip.get(id=target['id'])]
                preview.refreshTriggered()
                self.timeline.TimelineView.Slice_Triggered(helper, self.timeline.MenuSlice.KEEP_BOTH,
                                                         [target['id']], [], cut)
                clips = sorted(store._data['clips'], key=lambda clip: clip['position'])
                self.assertEqual([c.data for c in Clip.filter()], store._data['clips'])
                for left, right in zip(clips, clips[1:]):
                    self.assertAlmostEqual(left['position'] + left['end'] - left['start'], right['position'])
                    self.assertAlmostEqual(left['end'], right['start'])
                self.assertAlmostEqual(sum(c['end'] - c['start'] for c in clips), 500)
            # Keeping ten seconds and dragging between tracks must not restore
            # source duration from a query cached before the trim was committed.
            first = clips[0]
            preview.transforming_clips = [Clip.get(id=first['id'])]
            preview.refreshTriggered()
            self.timeline.TimelineView.Slice_Triggered(helper, self.timeline.MenuSlice.KEEP_LEFT,
                                                     [first['id']], [], 20)
            expected_end = 40 + 1 / 24  # KEEP_LEFT includes the playhead frame.
            for layer in (1, 0):
                moved = Clip.get(id=first['id'])
                moved.data['layer'] = layer
                helper.update_clip_data(moved.data, only_basic_props=True, ignore_reader=True)
                saved = next(c for c in store._data['clips'] if c['id'] == first['id'])
                self.assertAlmostEqual(saved['end'], expected_end)
                self.assertEqual(saved['start'], 30)
                self.assertEqual(saved['position'], 10)
                self.assertEqual(saved['layer'], layer)
                self.assertEqual(Clip.get(id=first['id']).data, saved)
        native.Clear()

    def test_razor_consumes_title_and_body_clicks_without_menus_or_drag_release(self):
        from qt_api import QPointF, QRectF, Qt
        from windows.views.timeline_backend.qwidget.base import TimelineWidgetBase
        for item_type in ('clip', 'transition'):
            for y in (20, 80):
                with self.subTest(item_type=item_type, y=y):
                    item = types.SimpleNamespace(id='item')
                    helper = Mock(enable_razor=True, _press_hit=None, _razor_modifiers=Qt.NoModifier)
                    helper._is_timeline_content_pos.return_value = True
                    helper._razor_in_track_area.return_value = True
                    helper._razor_target_at.return_value = {
                        'item': item, 'kind': item_type, 'seconds': 10.0}
                    helper._handle_razor_press.side_effect = lambda pos: TimelineWidgetBase._handle_razor_press(helper, pos)
                    helper._clear_pending_clip_menu_click.side_effect = lambda: TimelineWidgetBase._clear_pending_clip_menu_click(helper)
                    helper._clear_pending_transition_menu_click.side_effect = lambda: TimelineWidgetBase._clear_pending_transition_menu_click(helper)
                    helper._playhead_time_panel_rect.return_value = QRectF()
                    helper._track_toolbar_button_at.return_value = None
                    helper._handle_menu_icon_clicks.return_value = False
                    event = types.SimpleNamespace(pos=lambda: QPointF(50, y), button=lambda: Qt.LeftButton,
                                                  accept=Mock())
                    TimelineWidgetBase.mousePressEvent(helper, event)
                    helper._razor_target_at.assert_called_once_with(QPointF(50, y))
                    helper.RazorSliceAtCursor.assert_called_once_with(
                        'item' if item_type == 'clip' else '',
                        'item' if item_type == 'transition' else '', 10.0, Qt.NoModifier)
                    helper._begin_pending_clip_menu_click.assert_not_called()
                    helper._begin_pending_transition_menu_click.assert_not_called()
                    helper._handle_menu_icon_clicks.assert_not_called()
                    TimelineWidgetBase.mouseReleaseEvent(helper, event)
                    helper.events.released.emit.assert_not_called()
                    self.assertIsNone(helper._press_hit)
