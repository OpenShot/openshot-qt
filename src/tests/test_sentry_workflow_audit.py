# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.


"""Cross-layer coverage for the committed September Sentry fixes."""

import copy
import json
import os
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import openshot
from classes import info
from classes.json_data import JsonDataStore
from classes.query import Clip, Effect, QueryObject
from classes.timeline import TimelineSync
from classes.updates import UpdateManager
from tests.test_project_data import make_store
from tests import test_sentry_sep12


class SentryWorkflowAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_sentry_sep12.SentrySeptemberTests.setUpClass.__func__(cls)

    def test_insert_edit_effect_delete_and_history_keep_all_layers_consistent(self):
        store = make_store()
        store._data = {'clips': [], 'effects': [], 'layers': [], 'fps': {'num': 30, 'den': 1}}
        manager = UpdateManager()
        native = openshot.Timeline(320, 180, openshot.Fraction(30, 1), 44100, 2, openshot.LAYOUT_STEREO)
        self.addCleanup(native.Clear)
        window = Mock(proxy_service=None)
        sync = types.SimpleNamespace(timeline=native, window=window)
        window.timeline_sync = sync
        preview = types.SimpleNamespace(win=window, transforming_clips=[], transforming_clip_objects=[],
                                        transforming_clip=None, transforming_clip_object=None,
                                        transforming_effect=None, transforming_effect_object=None)
        preview.refreshTriggered = lambda **kw: self.video.VideoWidget.refreshTriggered(preview, **kw)
        window.videoPreview = preview
        manager.add_listener(types.SimpleNamespace(changed=lambda action: TimelineSync.changed(sync, action)))
        manager.add_listener(store)
        # Query consumers run after the store, as geometry/properties listeners do.
        observations = []
        manager.add_listener(types.SimpleNamespace(changed=lambda action: observations.append(
            (copy.deepcopy([c.data for c in Clip.filter()]), copy.deepcopy(store._data['clips'])))))
        helper = Mock(window=window, show_wait_spinner=False)
        helper.update_clip_data.side_effect = lambda data, **kw: self.timeline.TimelineView.update_clip_data(helper, data, **kw)
        helper.delete_invalid_timeline_item.side_effect = lambda item: self.timeline.TimelineView.delete_invalid_timeline_item(helper, item)
        reader = openshot.DummyReader(openshot.Fraction(30, 1), 320, 180, 44100, 2, 60.0)
        source = openshot.Clip(reader)
        source.Start(5)
        source.End(35)
        effect = openshot.Crop()
        effect.Id('crop')
        source.AddEffect(effect)
        with patch.object(self.app, 'project', store), patch.object(self.app, 'updates', manager), \
                patch.object(self.app, 'window', window):
            QueryObject._cache_version = -1
            # Import through the changed insertion path, including a complete reader.
            helper.update_clip_data(json.loads(source.Json()), ignore_reader=True)
            cid = store._data['clips'][0]['id']
            preview.transforming_clips = [Clip.get(id=cid)]
            preview.refreshTriggered()
            preview.transforming_effect = Effect.get(id='crop')
            preview.transforming_effect_object = native.GetClipEffect('crop')
            baseline = copy.deepcopy(store._data['clips'])
            edited = copy.deepcopy(Clip.get(id=cid).data)
            edited.update(position=12.0, start=7.0, end=25.0, duration=18.0, layer=2)
            edited['scale_x']['Points'][0]['co']['Y'] = 0.75
            edited['effects'][0]['left']['Points'][0]['co']['Y'] = 0.2
            helper.update_clip_data(edited, only_basic_props=False, ignore_reader=True)
            after_edit = copy.deepcopy(store._data['clips'])
            self.assertEqual(native.GetClip(cid).Position(), 12)
            self.assertEqual(native.GetClip(cid).Start(), 7)
            self.assertEqual(native.GetClip(cid).End(), 25)
            self.assertAlmostEqual(json.loads(native.GetClipEffect('crop').PropertiesJSON(1))['left']['value'], 0.2)
            self.assertEqual(int(preview.transforming_effect_object.this), int(native.GetClipEffect('crop').this))
            crop = Effect.get(id='crop')
            crop.data['left']['Points'][0]['co']['Y'] = 0.4
            crop.save()
            after_effect = copy.deepcopy(store._data['clips'])
            self.assertAlmostEqual(json.loads(native.GetClipEffect('crop').PropertiesJSON(1))['left']['value'], 0.4)
            Clip.get(id=cid).delete()
            self.assertIsNone(preview.transforming_clip_object)
            self.assertIsNone(preview.transforming_effect_object)
            self.assertEqual(store._data['clips'], [])
            # A queued partial edit must not resurrect the deleted clip.
            helper.update_clip_data(dict(id=cid, position=12, start=7, end=25, duration=18, layer=2))
            self.assertEqual(store._data['clips'], [])
            self.assertEqual(len(manager.actionHistory), 4)
            self.assertEqual(manager.actionHistory[0].values, baseline[0])
            self.assertEqual(manager.actionHistory[1].values['effects'], after_edit[0]['effects'])
            for expected in (after_effect, after_edit, baseline, []):
                manager.undo()
                self.assertEqual(store._data['clips'], expected)
                self.assertEqual(bool(native.GetClip(cid)), bool(expected))
            for expected in (baseline, after_edit, after_effect, []):
                manager.redo()
                self.assertEqual(store._data['clips'], expected)
                self.assertEqual(bool(native.GetClip(cid)), bool(expected))
            self.assertTrue(observations)
            for query_data, stored_data in observations:
                self.assertEqual(query_data, stored_data)

    def test_save_and_save_as_reopen_title_recording_and_generated_clip_assets(self):
        store = make_store()
        JsonDataStore.__init__(store)
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            user_path = os.path.join(root, 'runtime')
            os.makedirs(os.path.join(user_path, 'recordings'))
            stack.enter_context(patch.object(info, 'USER_PATH', user_path))
            for name in ('THUMBNAIL_PATH', 'TITLE_PATH', 'BLENDER_PATH', 'PROTOBUF_DATA_PATH',
                         'CLIPBOARD_PATH', 'COMFYUI_OUTPUT_PATH', 'PROXY_PATH'):
                path = os.path.join(user_path, name.lower())
                os.makedirs(path)
                stack.enter_context(patch.object(info, name, path))
                stack.enter_context(patch.dict(info._path_defaults, {name: path}))
            title_path = os.path.join(info.TITLE_PATH, 'title.svg')
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="18"><rect width="32" height="18" fill="red"/></svg>'
            with open(title_path, 'w') as stream:
                stream.write(svg)
            recording_path = os.path.join(user_path, 'recordings', 'capture.mov')
            recording_bytes = b'recording payload for relocation verification'
            with open(recording_path, 'wb') as stream:
                stream.write(recording_bytes)
            tracking_path = os.path.join(info.PROTOBUF_DATA_PATH, 'tracking.data')
            with open(tracking_path, 'wb') as stream:
                stream.write(b'tracking payload')
            title = json.loads(openshot.Clip(title_path).Json())
            title.update(id='title', file_id='F1', position=10, start=0, end=10, duration=10, layer=2)
            store._data = {'files': [{'id': 'F1', 'path': title_path}, {'id': 'F2', 'path': recording_path}],
                           'layers': [],
                           'clips': [title, {'id': 'recording', 'file_id': 'F2',
                                             'position': 0, 'start': 0, 'end': 10, 'layer': 1000000,
                                             'reader': {'type': 'FFmpegReader', 'path': recording_path}, 'effects': []},
                                     {'id': 'generated', 'position': 0, 'start': 0, 'end': 10, 'layer': 1000000,
                                      'reader': {'type': 'DummyReader'},
                                      'effects': [{'protobuf_data_path': tracking_path}]}]}
            stack.enter_context(patch.object(store, 'add_to_recent_files'))
            stack.enter_context(patch.object(self.app, 'project', store))
            manager = UpdateManager()
            manager.add_listener(store)
            stack.enter_context(patch.object(self.app, 'updates', manager))
            stack.enter_context(patch.object(self.app, 'window', Mock()))
            initial = store._data
            store._data = {'files': [], 'clips': [], 'layers': [], 'history': {'undo': [], 'redo': []}}
            for collection in ('files', 'clips'):
                for value in initial[collection]:
                    manager.insert([collection], value)
            # This recording has no live file/clip record when the project saves.
            history_only_path = os.path.join(user_path, 'recordings', 'undone.mov')
            with open(history_only_path, 'wb') as stream:
                stream.write(b'undone recording')
            manager.insert(['files'], {'id': 'undone', 'path': history_only_path})
            manager.undo()
            reopened = []
            for name in ('first', 'second'):
                destination = os.path.join(root, name + '.osp')
                manager.save_history(store, 100)
                store.save(destination)
                data = store.read_from_file(destination, path_mode='absolute')
                reopened.append(data)
                if name == 'first':
                    self.assertFalse(os.path.exists(title_path))
                    self.assertFalse(os.path.exists(recording_path))
                for record in data['files']:
                    self.assertTrue(os.path.isfile(record['path']))
                    self.assertTrue(record['path'].startswith(os.path.join(root, name + '_assets')))
                self.assertEqual(data['clips'][0]['reader']['path'], data['files'][0]['path'])
                self.assertEqual(data['clips'][1]['reader']['path'], data['files'][1]['path'])
                self.assertEqual(data['clips'][0]['end'], 10)
                with open(data['clips'][1]['reader']['path'], 'rb') as stream:
                    self.assertEqual(stream.read(), recording_bytes)
                with open(data['clips'][2]['effects'][0]['protobuf_data_path'], 'rb') as stream:
                    self.assertEqual(stream.read(), b'tracking payload')
                restored_title = openshot.Clip()
                restored_title.SetJson(json.dumps(data['clips'][0]))
                restored_title.Open()
                try:
                    self.assertEqual(restored_title.GetFrame(1).GetWidth(), 32)
                finally:
                    restored_title.Close()
                # Active history and reopened history must both restore usable
                # media, without changing the original clip's trim or position.
                for active in (True, False):
                    replay_store = store if active else make_store()
                    replay_manager = manager if active else UpdateManager()
                    if not active:
                        replay_store._data = copy.deepcopy(data)
                        replay_manager.add_listener(replay_store)
                        replay_manager.load_history(replay_store)
                    with patch.object(self.app, 'project', replay_store), \
                            patch.object(self.app, 'updates', replay_manager):
                        replay_manager.redo()
                        undone = replay_store._data['files'][-1]
                        self.assertEqual(undone['id'], 'undone')
                        self.assertTrue(undone['path'].startswith(os.path.join(root, name + '_assets')))
                        with open(undone['path'], 'rb') as stream:
                            self.assertEqual(stream.read(), b'undone recording')
                        replay_manager.undo()
                        for _ in range(3):
                            replay_manager.undo()
                        self.assertEqual(replay_store._data['clips'], [])
                        for _ in range(3):
                            replay_manager.redo()
                        restored = replay_store._data['clips'][0]
                        self.assertEqual((restored['start'], restored['end'], restored['position']), (0, 10, 10))
                        self.assertEqual(restored['reader']['path'], data['clips'][0]['reader']['path'])
                        self.assertTrue(os.path.exists(restored['reader']['path']))
                        self.assertTrue(os.path.exists(replay_store._data['clips'][1]['reader']['path']))
            # Save As must leave the first project's media intact and independent.
            self.assertNotEqual(reopened[0]['files'][1]['path'], reopened[1]['files'][1]['path'])
            for data in reopened:
                with open(data['files'][1]['path'], 'rb') as stream:
                    self.assertEqual(stream.read(), recording_bytes)

    def test_history_asset_relocation_preserves_external_paths_and_failed_copies(self):
        from classes.updates import UpdateAction
        store = make_store()
        store._data = {'history': {'undo': [], 'redo': []}}
        manager = UpdateManager()
        manager.add_listener(store)
        with tempfile.TemporaryDirectory() as root, \
                patch.object(self.app, 'project', store), patch.object(self.app, 'updates', manager):
            source = os.path.join(root, 'assets')
            target = os.path.join(root, 'saved_assets')
            os.makedirs(source)
            paths = [os.path.join(source, name) for name in ('new.svg', 'old.svg')]
            for path in paths:
                with open(path, 'w') as stream:
                    stream.write(path)
            external = os.path.join(root, 'assets-other', 'external.svg')
            payload = {'reader': {'path': paths[0]}, 'title': paths[0], 'position': 12,
                       'effects': [{'resource': external}]}
            manager.actionHistory = [UpdateAction('update', ['clips', {'id': 'clip'}], copy.deepcopy(payload))]
            manager.redoHistory = [UpdateAction('update', ['files', {'id': 'file'}, 'path'], paths[0], paths[1])]
            manager.save_history(store, 100)
            original_copy = store._copy_recording_asset

            def copy_asset(source_path, destination):
                if source_path == paths[1]:
                    raise PermissionError('inaccessible source')
                return original_copy(source_path, destination)

            with patch.object(store, '_copy_recording_asset', side_effect=copy_asset), \
                    patch('classes.project_data.log.warning') as warning:
                store._relocate_history_assets([(source, target)])
            self.assertTrue(warning.called)
            updated = manager.actionHistory[0].values
            self.assertEqual(updated['reader']['path'], os.path.join(target, 'new.svg'))
            self.assertEqual(updated['title'], paths[0])
            self.assertEqual(updated['position'], 12)
            self.assertEqual(updated['effects'][0]['resource'], external)
            self.assertEqual(manager.redoHistory[0].values, os.path.join(target, 'new.svg'))
            self.assertEqual(manager.redoHistory[0].old_values, paths[1])
            self.assertEqual(store._data['history']['redo'][0]['old_values'], paths[1])
            self.assertTrue(all(os.path.isfile(path) for path in paths))
            self.assertFalse(os.path.exists(os.path.join(target, 'old.svg')))
