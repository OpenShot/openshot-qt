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

"""Generated recovery packs work after extraction to a different directory."""
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch
import shutil
import tempfile
import unittest
import zipfile

from classes.json_data import JsonDataStore
from classes.project_recovery import parse_project, previous_versions, read_version, save_recovered_copy
from qt_api import QApplication
from tests.qt_test_app import get_or_create_app


ROOT = Path(__file__).resolve().parents[2]


def load_helper(name):
    specification = importlib.util.spec_from_file_location(name, ROOT / 'benchmarks' / (name + '.py'))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@unittest.skipUnless((ROOT / 'src').is_dir(),
                     'Recovery-pack generator tests require the source checkout')
class RecoveryTestPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))
        cls.generator = load_helper('generate_recovery_projects')
        cls.installer = load_helper('install_recovery_test_backups')

    def test_relocated_pack_repairs_and_restores_without_original_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original'
            self.generator.generate(original)
            relocated = Path(directory) / 'extracted elsewhere 日本語'
            shutil.move(str(original), relocated)
            manifest = json.loads((relocated / 'manifest.json').read_text(encoding='utf-8'))
            for key in ('valid', 'comma', 'many', 'bom', 'legacy', 'waveform', 'history', 'unreadable_history'):
                source = relocated / manifest['cases'][key]
                data, changes = parse_project(
                    source.read_text(encoding='utf-8'), repair=key != 'valid', original_path=str(source))
                self.assertEqual(len(data['clips']), 1)
                self.assertNotIn(str(original), json.dumps(data))
                if key == 'many':
                    self.assertEqual(sum(change.startswith('Omit clip ') for change in changes), 48)
                if key == 'waveform':
                    self.assertEqual(data['files'][0]['ui'], {'audio_data': [], 'audio_data_rms': []})
                    self.assertEqual(sum('waveform cache' in change for change in changes), 2)
                elif key == 'history':
                    self.assertEqual(len(data['history']['undo']), 1)
                    self.assertIn('discarded 2 of 3', changes[0])
                elif key == 'unreadable_history':
                    self.assertEqual(data['history'], {'undo': [], 'redo': []})
                    self.assertIn('unreadable remainder', changes[0])
                destination = relocated / (key + '-recovered.osp')
                save_recovered_copy(data, str(source), str(destination))
                reopened = JsonDataStore().read_from_file(str(destination), path_mode='absolute')
                self.assertTrue(Path(reopened['clips'][0]['reader']['path']).is_file())
            recovery = Path(directory) / 'isolated recovery'
            installed = self.installer.install_backups(relocated, recovery)
            self.assertEqual(len(installed), 8)
            source = relocated / manifest['cases']['truncated']
            versions = previous_versions(str(source), str(recovery))
            newest, _ = parse_project(read_version(versions[0], str(source)))
            self.assertEqual(len(newest['clips']), 2)
            other_source = Path(directory) / 'other folder' / source.name
            self.assertEqual(previous_versions(str(other_source), str(recovery)), [])
            broken = relocated / manifest['cases']['bad_backup']
            bad_versions = previous_versions(str(broken), str(recovery))
            with self.assertRaises(zipfile.BadZipFile):
                read_version(bad_versions[0], str(broken))
            previous, _ = parse_project(read_version(bad_versions[1], str(broken)))
            self.assertEqual(len(previous['clips']), 1)
            installed_again = self.installer.install_backups(relocated, recovery)
            self.assertFalse(set(installed) & set(installed_again))
            self.assertTrue(all(path.exists() for path in installed))

    def test_history_sample_has_working_undo_and_redo_after_repair(self):
        from classes.updates import UpdateManager
        from tests.test_project_data import make_store
        with tempfile.TemporaryDirectory() as directory:
            root = self.generator.generate(Path(directory) / 'pack')
            source = root / self.generator.CASES['history']
            data, _ = parse_project(source.read_text(), repair=True)
            store = make_store()
            store._data = data
            manager = UpdateManager()
            manager.add_listener(store)
            with patch.object(self.app, 'window', None, create=True), \
                    patch.object(self.app, 'updates', manager, create=True), \
                    patch.object(self.app, 'project', store, create=True):
                manager.load_history(store)
                manager.undo()
                self.assertEqual(store._data['clips'][0]['position'], 1)
                manager.redo()
                self.assertEqual(store._data['clips'][0]['position'], 0)

    @unittest.skipIf(os.name == 'nt', 'Windows filenames cannot contain double quotes')
    def test_quoted_filename_case_repairs_only_after_media_is_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.generator.generate(Path(directory) / 'original')
            relocated = Path(directory) / 'moved pack 日本語'
            shutil.move(str(root), relocated)
            # The main folder and ZIP remain extractable on Windows.
            self.assertTrue(all('"' not in path.name for path in relocated.rglob('*')))
            source = relocated / self.generator.CASES['quotes']
            text = source.read_text(encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'expected one existing file, found 0'):
                parse_project(text, repair=True, original_path=str(source))
            with zipfile.ZipFile(relocated / self.generator.QUOTED_MEDIA_ARCHIVE) as archive:
                archive.extractall(relocated)
            data, changes = parse_project(text, repair=True, original_path=str(source))
            self.assertEqual(sum('filename quote' in change for change in changes), 2)
            self.assertEqual(data['files'][0]['path'], 'Media/' + self.generator.QUOTED_MEDIA_NAME)
            self.assertEqual(data['clips'][0]['reader']['path'], data['files'][0]['path'])
            destination = relocated / 'quotes-recovered.osp'
            save_recovered_copy(data, str(source), str(destination))
            reopened = JsonDataStore().read_from_file(str(destination), path_mode='absolute')
            media_path = reopened['clips'][0]['reader']['path']
            self.assertTrue(Path(media_path).is_file())
            native = self.generator.openshot.Clip(media_path)
            native.Open()
            try:
                self.assertEqual(native.GetFrame(1).GetWidth(), 1280)
            finally:
                native.Close()
            self.assertEqual(source.read_text(encoding='utf-8'), text)

    def test_generator_refuses_to_overwrite_existing_test_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'user.osp'
            path.write_text('existing', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'empty output folder'):
                self.generator.generate(directory)
            self.assertEqual(path.read_text(encoding='utf-8'), 'existing')
