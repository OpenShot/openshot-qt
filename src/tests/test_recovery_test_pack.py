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
from pathlib import Path
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
            for key in ('valid', 'comma', 'many', 'bom', 'legacy'):
                source = relocated / manifest['cases'][key]
                data, changes = parse_project(source.read_text(encoding='utf-8'), repair=key != 'valid')
                self.assertEqual(len(data['clips']), 1)
                self.assertNotIn(str(original), json.dumps(data))
                if key == 'many':
                    self.assertEqual(sum(change.startswith('Omit clip ') for change in changes), 48)
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

    def test_generator_refuses_to_overwrite_existing_test_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'user.osp'
            path.write_text('existing', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'empty output folder'):
                self.generator.generate(directory)
            self.assertEqual(path.read_text(encoding='utf-8'), 'existing')
