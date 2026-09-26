"""
 @file
 @brief This file contains unit tests for JSON data loading and saving
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication

from classes import info
from classes.json_data import JsonDataStore
from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
        }

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()
        from classes.project_data import ProjectDataStore
        from classes.updates import UpdateManager

        self.project = ProjectDataStore()
        self.updates = UpdateManager()
        self.updates.add_listener(self.project)
        self.updates.reset()
        self.window = None

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


def ensure_app_state(app):
    from classes.project_data import ProjectDataStore
    from classes.updates import UpdateManager

    return ensure_qt_app_state(
        app,
        DummySettings,
        project_factory=ProjectDataStore,
        updates_factory=UpdateManager,
        extra_attrs={"window": None},
    )


class JsonDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)

    def test_read_from_file_repairs_windows_drive_corruption(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "broken.osp"
            project_file.write_text(
                '{\n'
                ' "version": {"openshot-qt": "2.6.0"},\n'
                ' "files": [\n'
                '  {\n'
                '   id: "F1",\n'
                '   "path": "C:/media/clip.mp4"\n'
                '  }\n'
                ' ]\n'
                '}\n',
                encoding="utf-8",
            )

            store = JsonDataStore()
            data = store.read_from_file(str(project_file))

            self.assertEqual(data["files"][0]["id"], "F1")
            self.assertTrue(project_file.with_suffix(".osp.bak").exists())
            self.assertIn('"id": "F1"', project_file.read_text(encoding="utf-8"))

    def test_write_relative_and_read_absolute_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            project_file = tmpdir / "project.osp"
            assets_dir = tmpdir / "project_assets"
            transitions_dir = tmpdir / "openshot" / "transitions"
            colors_dir = tmpdir / "colors"

            import classes.json_data as json_data_module

            with ExitStack() as stack:
                stack.enter_context(patch.object(info, "PATH", str(tmpdir / "openshot")))
                stack.enter_context(patch.object(info, "COLORS_PATH", str(colors_dir)))
                stack.enter_context(patch.object(info, "THUMBNAIL_PATH", str(tmpdir / "thumbs")))
                stack.enter_context(
                    patch.object(
                        json_data_module,
                        "get_assets_path",
                        lambda file_path, create_paths=False: str(assets_dir),
                    )
                )
                store = JsonDataStore()
                source = {
                    "path": str(assets_dir / "title" / "intro.svg"),
                    "resource": str(transitions_dir / "common" / "fade.svg"),
                    "lut_path": str(colors_dir / "teal.cube"),
                }

                store.write_to_file(str(project_file), source, path_mode="relative")
                saved = project_file.read_text(encoding="utf-8")

                self.assertIn('"path": "@assets/title/intro.svg"', saved)
                self.assertTrue(
                    '"resource": "@transitions/common/fade.svg"' in saved
                    or f'"resource": "{str(transitions_dir / "common" / "fade.svg")}"' in saved
                )
                self.assertIn('"lut_path": "@colors/teal.cube"', saved)

                loaded = store.read_from_file(str(project_file), path_mode="absolute")
                self.assertEqual(loaded["path"], str(assets_dir / "title" / "intro.svg"))
                self.assertEqual(loaded["resource"], str(transitions_dir / "common" / "fade.svg"))
                self.assertEqual(loaded["lut_path"], str(colors_dir / "teal.cube"))

    def test_empty_lut_path_stays_blank_through_path_conversion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            project_file = tmpdir / "project.osp"
            assets_dir = tmpdir / "project_assets"
            colors_dir = tmpdir / "colors"

            import classes.json_data as json_data_module

            with ExitStack() as stack:
                stack.enter_context(patch.object(info, "PATH", str(tmpdir / "openshot")))
                stack.enter_context(patch.object(info, "COLORS_PATH", str(colors_dir)))
                stack.enter_context(patch.object(info, "THUMBNAIL_PATH", str(tmpdir / "thumbs")))
                stack.enter_context(
                    patch.object(
                        json_data_module,
                        "get_assets_path",
                        lambda file_path, create_paths=False: str(assets_dir),
                    )
                )
                store = JsonDataStore()
                source = {
                    "lut_path": "",
                }

                store.write_to_file(str(project_file), source, path_mode="relative")
                saved = project_file.read_text(encoding="utf-8")
                self.assertIn('"lut_path": ""', saved)

                loaded = store.read_from_file(str(project_file), path_mode="absolute")
                self.assertEqual(loaded["lut_path"], "")

    def test_make_repair_backup_increments_suffix_when_backup_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "project.osp"
            project_file.write_text("{}", encoding="utf-8")
            Path(f"{project_file}.bak").write_text("old", encoding="utf-8")

            store = JsonDataStore()
            store.make_repair_backup(str(project_file), '{"id": "P1"}')

            second_backup = Path(f"{project_file}.bak.1")
            self.assertTrue(second_backup.exists())
            self.assertEqual(second_backup.read_text(encoding="utf-8"), '{"id": "P1"}')
