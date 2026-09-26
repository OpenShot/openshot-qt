"""Regression coverage for unsaved asset locations and external title scratch files."""
import copy
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from classes import info
from classes.assets import get_assets_path
from classes.settings import SettingStore
from classes.json_data import JsonDataStore
from tests.test_project_data import DummyApp, DummyAction, ensure_app_state, make_store
from tests.qt_test_app import get_or_create_app


class AssetLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls._owns_app = get_or_create_app(DummyApp)

    def setUp(self):
        ensure_app_state(self.app)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.home = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.user = self.home / '.openshot_qt'
        self.user.mkdir()
        original_user = info.USER_PATH
        for name in ('HOME_PATH', 'USER_PATH', 'BACKUP_FILE', 'RECOVERY_PATH',
                     'ASSETS_PATH', *info._path_defaults):
            self.stack.enter_context(patch.object(info, name, getattr(info, name)))
        self.stack.enter_context(patch.dict(info._path_defaults))
        info.HOME_PATH = str(self.home)
        info.USER_PATH = str(self.user)
        info.BACKUP_FILE = str(self.user / 'backup.osp')
        info.RECOVERY_PATH = str(self.user / 'recovery')
        for name, value in info._path_defaults.items():
            if value.startswith(original_user):
                value = str(self.user) + value[len(original_user):]
                info._path_defaults[name] = value
                setattr(info, name, value)
        info.configure_asset_defaults(str(self.user))

    def test_linux_default_requires_existing_videos_and_checks_write_access(self):
        with patch.object(info.sys, 'platform', 'linux'):
            self.assertEqual(info.default_assets_path(), str(self.user))
            self.assertFalse((self.home / 'Videos').exists())
            (self.home / 'Videos').mkdir()
            expected = self.home / 'Videos' / '.openshot-tmp'
            self.assertEqual(info.default_assets_path(), str(expected))
            self.assertEqual(list(expected.iterdir()), [])
            with patch.object(info.tempfile, 'TemporaryFile', side_effect=PermissionError):
                self.assertEqual(info.default_assets_path(), str(self.user))

    def test_other_platforms_do_not_create_linux_directory(self):
        (self.home / 'Videos').mkdir()
        for platform in ('win32', 'darwin'):
            with self.subTest(platform=platform), patch.object(info.sys, 'platform', platform):
                self.assertEqual(info.default_assets_path(), str(self.user))
        self.assertFalse((self.home / 'Videos' / '.openshot-tmp').exists())

    def test_linux_directory_creation_failure_falls_back(self):
        (self.home / 'Videos').mkdir()
        with patch.object(info.sys, 'platform', 'linux'), \
                patch.object(info.os, 'makedirs', side_effect=PermissionError):
            self.assertEqual(info.default_assets_path(), str(self.user))

    def test_unwritable_asset_subdirectory_falls_back(self):
        root = self.home / 'custom'
        root.mkdir()
        (root / 'blender').write_text('existing file')
        self.assertEqual(info.configure_asset_defaults(str(root)), str(self.user))
        self.assertEqual((root / 'blender').read_text(), 'existing file')

    def test_unusable_preference_falls_back_without_changing_user_storage(self):
        blocked = self.home / 'file'
        blocked.write_text('keep')
        self.assertEqual(info.configure_asset_defaults(str(blocked)), str(self.user))
        self.assertEqual(blocked.read_text(), 'keep')
        self.assertEqual(info.TITLE_PATH, str(self.user / 'title'))

    def test_new_project_reset_restores_configured_asset_defaults(self):
        root = self.home / 'Videos' / '.openshot-tmp'
        info.configure_asset_defaults(str(root))
        self.assertEqual(get_assets_path(), str(root))
        info.set_assets_path(str(self.home / 'saved_assets'))
        info.reset_userdirs()
        self.assertEqual(info.ASSETS_PATH, str(root))
        for name, folder in info._asset_folders.items():
            self.assertEqual(getattr(info, name), str(root / folder))
            self.assertEqual(info.get_default_path(name), str(root / folder))
            self.assertTrue((root / folder).is_dir())
        self.assertEqual(info.USER_PATH, str(self.user))
        self.assertEqual(info.BACKUP_FILE, str(self.user / 'backup.osp'))

    def test_preference_is_initialized_and_preserved_across_loads(self):
        (self.home / 'Videos').mkdir()
        settings = SettingStore()
        with patch.object(info.sys, 'platform', 'linux'):
            settings.load()
            self.assertEqual(settings.get('unsaved-assets-path'), str(self.home / 'Videos' / '.openshot-tmp'))
            custom = str(self.home / 'custom')
            settings.set('unsaved-assets-path', custom)
            settings.save()
            with patch.object(info, 'default_assets_path') as choose_default:
                settings.load()
                choose_default.assert_not_called()
            self.assertEqual(settings.get('unsaved-assets-path'), custom)

    def test_title_scratch_uses_active_assets_and_cleanup_preserves_saved_svg(self):
        from windows.title_editor import TitleEditor
        template = self.home / 'template.svg'
        template.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        for root in (self.home / 'Videos' / '.openshot-tmp', self.home / 'project_assets'):
            with self.subTest(root=root):
                info.set_assets_path(str(root))
                dialogs = []
                for _ in range(2):
                    dialog = types.SimpleNamespace(finished=Mock())
                    dialog._remove_temp_title = types.MethodType(TitleEditor._remove_temp_title, dialog)
                    TitleEditor.create_temp_title(dialog, str(template))
                    self.assertEqual(Path(dialog.filename).parent, root / 'title')
                    self.assertEqual(Path(dialog.filename).read_text(), template.read_text())
                    dialogs.append(dialog)
                self.assertNotEqual(dialogs[0].filename, dialogs[1].filename)
                saved = root / 'title' / 'accepted.svg'
                saved.write_text(template.read_text())
                for dialog in dialogs:
                    scratch = Path(dialog.filename)
                    dialog.filename = str(saved)
                    dialog.finished.connect.call_args.args[0](1)
                    self.assertFalse(scratch.exists())
                self.assertTrue(saved.exists())

    def _load_project(self, store, path, recovery=False):
        # Initialize the JSON reader's damage-detection expressions, retaining
        # the fixture data created through the lightweight project-store helper.
        data = store._data
        JsonDataStore.__init__(store)
        store._data = data
        self.app.window = types.SimpleNamespace(actionClearWaveformData=DummyAction())
        self.app.updates = types.SimpleNamespace(load=Mock())
        defaults = {'files': [], 'clips': [], 'effects': [], 'history': {'undo': [], 'redo': []}}
        with ExitStack() as stack:
            def new():
                info.reset_userdirs()
                store._data = copy.deepcopy(defaults)
            stack.enter_context(patch.object(store, 'new', new))
            for method in ('check_if_paths_are_valid', 'add_to_recent_files',
                           'upgrade_project_data_structures', 'apply_default_audio_settings'):
                stack.enter_context(patch.object(store, method))
            stack.enter_context(patch.object(store, 'get_profile', return_value=object()))
            store.load(str(path), clear_thumbnails=not recovery)

    def test_save_reopen_save_as_and_reset_preserve_title_and_blender_assets(self):
        runtime = self.home / 'Videos' / '.openshot-tmp'
        info.configure_asset_defaults(str(runtime))
        title = runtime / 'title' / 'caption.svg'
        frame = runtime / 'blender' / 'animation' / 'frame0001.png'
        recording = runtime / 'recordings' / 'voice.wav'
        for path in (title, frame, recording):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'asset-content')
        store = make_store()
        store._data = {
            'files': [{'id': str(i), 'path': str(p)} for i, p in enumerate((title, frame, recording))],
            'clips': [{'id': 'C'+str(i), 'file_id': str(i), 'reader': {'path': str(p)}, 'effects': []}
                      for i, p in enumerate((title, frame, recording))],
            'effects': [],
            'history': {'undo': [{'key': ['files'], 'value': {'path': str(title)}}],
                        'redo': [{'key': ['files'], 'value': {'path': str(frame)}}]},
        }
        first = self.home / 'first.osp'
        second = self.home / 'second.osp'
        with patch.object(store, 'add_to_recent_files'):
            store.save(str(first))
        self.assertEqual(info.ASSETS_PATH, str(self.home / 'first_assets'))
        for p in (title, frame, recording):
            self.assertFalse(p.exists())
        self._load_project(store, first)
        first_paths = [Path(f['path']) for f in store._data['files']]
        self.assertTrue(all(p.is_file() for p in first_paths))
        with patch.object(store, 'add_to_recent_files'):
            store.save(str(second))
        self.assertTrue(all(p.is_file() for p in first_paths))
        self._load_project(store, second)
        for file, clip in zip(store._data['files'], store._data['clips']):
            self.assertTrue(file['path'].startswith(str(self.home / 'second_assets') + os.sep))
            self.assertEqual(Path(file['path']).read_bytes(), b'asset-content')
            self.assertEqual(clip['reader']['path'], file['path'])
        for actions in store._data['history'].values():
            path = actions[0]['value']['path']
            self.assertTrue(path.startswith(str(self.home / 'second_assets') + os.sep))
            self.assertTrue(Path(path).is_file())
        info.reset_userdirs()
        self.assertEqual(info.TITLE_PATH, str(runtime / 'title'))

    def test_backup_recovery_keeps_previous_root_after_preference_change(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                old_root = self.user if legacy else self.home / 'old-runtime'
                info.configure_asset_defaults(str(old_root))
                title = old_root / 'title' / 'recovered.svg'
                title.write_text('<svg/>')
                store = make_store()
                store._data = {'files': [{'id': 'T', 'path': str(title)}], 'clips': [], 'effects': []}
                store.save(info.BACKUP_FILE, backup_only=True)
                self.assertTrue(title.exists())
                self.assertNotIn('runtime_assets_path', store._data)
                payload = json.loads(Path(info.BACKUP_FILE).read_text())
                self.assertEqual(payload['runtime_assets_path'], str(old_root))
                if legacy:
                    del payload['runtime_assets_path']
                    Path(info.BACKUP_FILE).write_text(json.dumps(payload))
                info.configure_asset_defaults(str(self.home / 'new-runtime'))
                self._load_project(store, info.BACKUP_FILE, recovery=True)
                store.current_filepath = None  # MainWindow.recover_backup does this.
                self.assertEqual(info.ASSETS_PATH, str(old_root))
                self.assertNotIn('runtime_assets_path', store._data)
                with patch.object(store, 'add_to_recent_files'):
                    store.save(str(self.home / ('recovered-%s.osp' % legacy)))
                self.assertEqual(Path(store._data['files'][0]['path']).read_text(), '<svg/>')
                info.reset_userdirs()
                self.assertEqual(info.ASSETS_PATH, str(self.home / 'new-runtime'))

    def test_recovering_saved_project_does_not_move_original_recordings(self):
        original = self.home / 'original_assets'
        info.set_assets_path(str(original))
        recording = original / 'recordings' / 'voice.wav'
        recording.parent.mkdir(parents=True)
        recording.write_bytes(b'voice')
        store = make_store()
        store._data = {'files': [{'id': 'R', 'path': str(recording)}], 'clips': [], 'effects': []}
        store.save(info.BACKUP_FILE, backup_only=True)
        self._load_project(store, info.BACKUP_FILE, recovery=True)
        store.current_filepath = None
        with patch.object(store, 'add_to_recent_files'):
            store.save(str(self.home / 'recovered.osp'))
        self.assertEqual(recording.read_bytes(), b'voice')
        self.assertEqual(Path(store._data['files'][0]['path']).read_bytes(), b'voice')
