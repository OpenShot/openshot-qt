"""Exercise timeline copy/paste callbacks using the actual serialized clipboard."""

import copy
import importlib
import json
import types
import unittest
from unittest.mock import Mock

from classes.clipboard import ClipboardManager
from classes.project_data import ProjectDataStore
from classes.query import QueryObject
from classes.updates import UpdateManager
from tests.test_project_data import DummyApp, ensure_app_state
from tests.qt_test_app import get_or_create_app


class TimelineClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(DummyApp)
        ensure_app_state(cls.app)
        cls.timeline = importlib.import_module('windows.views.timeline')

    def setUp(self):
        ensure_app_state(self.app)
        self.store = ProjectDataStore()
        self.app.project = self.store
        self.app.updates = UpdateManager()
        self.app.updates.add_listener(self.store)
        QueryObject._cache.clear()
        QueryObject._cache_version = None
        self.app.window = types.SimpleNamespace(ensure_tracks_for_layers=Mock(),
                                               IgnoreUpdates=Mock(), verifySelections=Mock())
        self.host = types.SimpleNamespace(
            get_uuid=lambda: 'paste-transaction',
            window=types.SimpleNamespace(direct_text=types.SimpleNamespace(paste_style=Mock())),
            _extend_timeline_to_fit_items=Mock(), _select_inserted_paste_items=Mock())
        self.host._assign_new_effect_ids = lambda data: self.timeline.TimelineView._assign_new_effect_ids(self.host, data)
        self.store._data['clips'] = [self.clip('C1', 2.0, 3000000), self.clip('C2', 20.0, 1000000)]
        self.store._data['effects'] = [self.transition('T1', 5.0), self.transition('T2', 30.0)]

    def tearDown(self):
        self.app.clipboard().clear()
        self.app.window = None

    def clip(self, clip_id, position, layer):
        return {'id': clip_id, 'position': position, 'layer': layer, 'start': 1.0, 'end': 5.0,
                'reader': {'type': 'FFmpegReader', 'path': 'movie.mp4'}, 'alpha': {'Points': [{'co': {'X': 1, 'Y': 0.5}}]},
                'effects': [{'id': 'E-' + clip_id, 'class_name': 'Blur', 'radius': {'Points': []}}]}

    def transition(self, transition_id, position):
        return {'id': transition_id, 'position': position, 'layer': 3000000, 'start': 0.0, 'end': 2.0,
                'reader': {'type': 'QtImageReader', 'path': 'fade.svg'}, 'brightness': {'Points': [{'co': {'X': 1, 'Y': 0.2}}]},
                'contrast': {'Points': []}}

    def copy_items(self, action, clips=None, transitions=None, effects=None):
        self.timeline.TimelineView.Copy_Triggered(self.host, action, clips or [], transitions or [], effects or [])
        # No mocked serializer/deserializer: Qt owns the data as it does in the UI.
        mime = self.app.clipboard().mimeData()
        self.assertTrue(mime.hasText())
        return json.loads(mime.text())

    def paste(self, clips=None, transitions=None, position=50.0, layer=3000000):
        self.timeline.TimelineView._handle_paste_callback(
            self.host, clips or [], transitions or [], {'position': position, 'track': layer})
        self.assertIsNone(self.app.updates.transaction_id)

    def test_imported_legacy_clip_paste_keeps_existing_track(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from unittest.mock import patch
        from tests.source_tree import source_path
        from windows.main_window import MainWindow

        window = self.app.window
        window.actionClearWaveformData = Mock()
        window.removeSelection = Mock()
        window.show_property_timer = Mock()
        window.selection_timer = Mock()
        # Exercise real track allocation: mocking it hides zero-numbered tracks.
        for name in ('_track_numbers', '_create_track', 'create_track_below',
                     'track_stack_from', 'ensure_tracks_for_layers'):
            setattr(window, name, types.MethodType(getattr(MainWindow, name), window))
        fixture = source_path('src/tests/fixtures/legacy/manual/Legacy Pickle Test Pack.zip')
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(fixture) as archive:
                archive.extractall(folder)
            path = str(Path(folder) / 'Legacy Pickle Test Pack' / 'Legacy PNG Test.osp')
            with patch.object(self.store, 'add_to_recent_files'):
                self.store.load(path, clear_thumbnails=False, interactive=False)
            original_layers = copy.deepcopy(self.store.get('layers'))
            source = self.store.get('clips')[0]
            self.copy_items(self.timeline.MenuCopy.CLIP, clips=[source['id']])
            self.paste(position=8.0, layer=source['layer'])
            self.assertEqual(self.store.get('layers'), original_layers)
            self.assertEqual(len(self.store.get('clips')), 4)
            self.assertEqual(self.store.get('clips')[-1]['layer'], source['layer'])
            self.app.updates.undo()
            self.assertEqual(len(self.store.get('clips')), 3)
            self.assertEqual(self.store.get('layers'), original_layers)

    def test_partial_clip_copy_keeps_source_identity_and_target_timing(self):
        before = copy.deepcopy(self.store._data['clips'])
        text = self.copy_items(self.timeline.MenuCopy.KEYFRAMES_ALPHA, clips=['C1'])
        self.assertEqual(text, {'alpha': before[0]['alpha']})
        self.assertNotIn('id', text)
        self.assertEqual(ClipboardManager.from_mime(self.app.clipboard().mimeData()).id, 'C1')
        self.paste(clips=['C1', 'C2'])
        source, target = self.store.get('clips')
        self.assertEqual(source, before[0])
        for key in ('id', 'position', 'layer', 'start', 'end'):
            self.assertEqual(target[key], before[1][key])
        self.assertEqual(target['alpha'], before[0]['alpha'])
        self.app.updates.undo()
        self.assertEqual(self.store.get('clips'), before)

    def test_transition_properties_paste_preserves_target_timing(self):
        before = copy.deepcopy(self.store._data['effects'])
        self.copy_items(self.timeline.MenuCopy.KEYFRAMES_BRIGHTNESS, transitions=['T1'])
        self.paste(transitions=['T1', 'T2'])
        source, target = self.store.get('effects')
        self.assertEqual(source, before[0])
        for key in ('id', 'position', 'layer', 'start', 'end'):
            self.assertEqual(target[key], before[1][key])
        self.assertEqual(target['brightness'], before[0]['brightness'])

    def test_full_mixed_selection_inserts_new_ids_and_keeps_relative_offsets(self):
        source_clip = copy.deepcopy(self.store._data['clips'][0])
        source_transition = copy.deepcopy(self.store._data['effects'][0])
        self.copy_items(self.timeline.MenuCopy.ALL, clips=['C1'], transitions=['T1'])
        self.paste(position=50.0, layer=4000000)
        clips, transitions = self.store.get('clips'), self.store.get('effects')
        self.assertEqual(len(clips), 3)
        self.assertEqual(len(transitions), 3)
        inserted_clip, inserted_transition = clips[-1], transitions[-1]
        self.assertEqual((inserted_clip['position'], inserted_transition['position']), (50.0, 53.0))
        self.assertEqual((inserted_clip['layer'], inserted_transition['layer']), (4000000, 4000000))
        self.assertNotEqual(inserted_clip['id'], 'C1')
        self.assertNotEqual(inserted_transition['id'], 'T1')
        self.assertNotEqual(inserted_clip['effects'][0]['id'], source_clip['effects'][0]['id'])
        self.assertEqual(clips[0], source_clip)
        self.assertEqual(transitions[0], source_transition)
        self.host._extend_timeline_to_fit_items.assert_called_once()
        self.host._select_inserted_paste_items.assert_called_once()
        # The same clipboard can be pasted again without its source data being mutated.
        self.paste(position=70.0, layer=4000000)
        self.assertEqual(self.store.get('clips')[-1]['position'], 70.0)

    def test_full_single_clip_paste_without_target_inserts(self):
        self.copy_items(self.timeline.MenuCopy.CLIP, clips=['C1'])
        self.paste(position=40.0)
        self.assertEqual(len(self.store.get('clips')), 3)
        self.assertEqual(self.store.get('clips')[-1]['position'], 40.0)

    def test_partial_copy_without_target_does_not_insert(self):
        self.copy_items(self.timeline.MenuCopy.KEYFRAMES_ALPHA, clips=['C1'])
        self.paste()
        self.assertEqual(len(self.store.get('clips')), 2)
        self.host._extend_timeline_to_fit_items.assert_not_called()

    def test_effect_copy_to_clip_assigns_new_effect_id(self):
        self.store._data['clips'][1]['effects'] = []
        self.copy_items(self.timeline.MenuCopy.EFFECT, effects=['E-C1'])
        self.paste(clips=['C2'])
        effect = self.store.get('clips')[1]['effects'][0]
        self.assertEqual(effect['class_name'], 'Blur')
        self.assertNotEqual(effect['id'], 'E-C1')
        self.assertEqual(self.store.get('clips')[0]['effects'][0]['id'], 'E-C1')

    def test_all_effects_copy_merges_by_effect_class(self):
        self.copy_items(self.timeline.MenuCopy.ALL_EFFECTS, clips=['C1'])
        self.paste(clips=['C2'])
        effects = self.store.get('clips')[1]['effects']
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0]['class_name'], 'Blur')
        self.assertNotEqual(effects[0]['id'], 'E-C1')

    def test_text_style_copy_uses_existing_style_consumer(self):
        from classes.direct_text import copied_text_style
        source = self.store._data['clips'][0]
        source.update({'direct_text': {'font': 'Noto Sans', 'text': 'Hello'}})
        style = copied_text_style(source)
        self.copy_items(self.timeline.MenuCopy.TEXT_STYLE, clips=['C1'])
        self.paste(clips=['C2'])
        self.host.window.direct_text.paste_style.assert_called_once_with(['C2'], style)

    def test_every_partial_copy_action_preserves_existing_json_shape(self):
        curve = {"Points": [{"co": {"X": 1, "Y": 0.5}}]}
        source = self.store._data['clips'][0]
        for key in ('scale_x', 'scale_y', 'shear_x', 'shear_y', 'rotation',
                    'location_x', 'location_y', 'time', 'volume'):
            source[key] = copy.deepcopy(curve)
        source['gravity'] = 0
        actions = {
            'KEYFRAMES_ALPHA': {'alpha'}, 'KEYFRAMES_SCALE': {'gravity', 'scale_x', 'scale_y'},
            'KEYFRAMES_SHEAR': {'shear_x', 'shear_y'}, 'KEYFRAMES_ROTATE': {'gravity', 'rotation'},
            'KEYFRAMES_LOCATION': {'gravity', 'location_x', 'location_y'},
            'KEYFRAMES_TIME': {'time'}, 'KEYFRAMES_VOLUME': {'volume'}, 'ALL_EFFECTS': {'effects'},
            'KEYFRAMES_ALL': {'alpha', 'gravity', 'scale_x', 'scale_y', 'shear_x', 'shear_y',
                              'rotation', 'location_x', 'location_y', 'time', 'volume'},
        }
        original = copy.deepcopy(source)
        for action, keys in actions.items():
            with self.subTest(action=action):
                QueryObject._cache.clear()
                text = self.copy_items(getattr(self.timeline.MenuCopy, action), clips=['C1'])
                self.assertEqual(set(text), keys)
                self.assertEqual(text, {key: original[key] for key in keys})
                restored = ClipboardManager.from_mime(self.app.clipboard().mimeData())
                self.assertIsInstance(restored, self.timeline.Clip)
                self.assertEqual(restored.id, 'C1')
                self.assertEqual(restored.data, text)
                self.assertEqual(self.store.get('clips')[0], original)

    def test_full_clip_copy_applies_properties_without_changing_target_timing(self):
        before = copy.deepcopy(self.store._data['clips'])
        self.copy_items(self.timeline.MenuCopy.CLIP, clips=['C1'])
        self.paste(clips=['C1', 'C2'])
        source, target = self.store.get('clips')
        self.assertEqual(source, before[0])
        for key in ('id', 'position', 'layer', 'start', 'end'):
            self.assertEqual(target[key], before[1][key])
        self.assertEqual(target['reader'], before[0]['reader'])
        self.assertEqual(target['alpha'], before[0]['alpha'])

    def test_multitrack_copy_preserves_track_order_and_offsets(self):
        self.app.window.track_stack_from = lambda target, count: [4000000, 3000000][:count]
        self.copy_items(self.timeline.MenuCopy.ALL, clips=['C1', 'C2'])
        self.paste(position=50.0, layer=4000000)
        inserted = self.store.get('clips')[-2:]
        self.assertEqual([clip['position'] for clip in inserted], [50.0, 68.0])
        self.assertEqual([clip['layer'] for clip in inserted], [4000000, 3000000])

    def shortcut_host(self):
        from windows.main_window import MainWindow
        self.host.selected_clips = ['C2']
        self.host.selected_transitions = ['T2']
        self.host.import_files_from_clipboard = Mock(return_value=False)
        self.host.timeline = types.SimpleNamespace(
            context_menu_cursor_position='old-position',
            Paste_Triggered=Mock(side_effect=lambda action, clips, transitions: self.paste(clips, transitions)))
        return MainWindow

    def test_keyboard_paste_full_clip_inserts_at_playhead_despite_selection(self):
        self.copy_items(self.timeline.MenuCopy.CLIP, clips=['C1'])
        main = self.shortcut_host()
        main.pasteAll(self.host)
        self.host.timeline.Paste_Triggered.assert_called_once_with(self.timeline.MenuCopy.PASTE, [], [])
        self.assertIsNone(self.host.timeline.context_menu_cursor_position)
        self.assertEqual(len(self.store.get('clips')), 3)
        self.assertEqual(self.store.get('clips')[-1]['position'], 50.0)

    def test_keyboard_paste_partial_clip_applies_to_selection(self):
        self.copy_items(self.timeline.MenuCopy.KEYFRAMES_ALPHA, clips=['C1'])
        main = self.shortcut_host()
        main.pasteAll(self.host)
        self.host.timeline.Paste_Triggered.assert_called_once_with(self.timeline.MenuCopy.PASTE, ['C2'], ['T2'])
        self.assertEqual(len(self.store.get('clips')), 2)

    def test_keyboard_cut_keeps_serialized_copy_before_delete(self):
        main = self.shortcut_host()
        self.host.copyAll = lambda: main.copyAll(self.host)
        self.host.timeline.Copy_Triggered = lambda *args: self.timeline.TimelineView.Copy_Triggered(self.host, *args)
        copied = []
        self.host.deleteItem = lambda: copied.append(ClipboardManager.from_mime(self.app.clipboard().mimeData()))
        main.cutAll(self.host)
        self.assertEqual(len(copied), 1)
        self.assertEqual([obj.id for obj in copied[0]], ['C2', 'T2'])

    def test_non_openshot_media_paste_retains_import_fallback(self):
        from qt_api import QMimeData
        main = self.shortcut_host()
        mime = QMimeData()
        mime.setText('/tmp/example.png')
        self.app.clipboard().setMimeData(mime)
        self.host.import_files_from_clipboard.return_value = True
        main.pasteAll(self.host)
        self.host.import_files_from_clipboard.assert_called_once()
        self.host.timeline.Paste_Triggered.assert_not_called()
