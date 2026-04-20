"""
 @file
 @brief This file contains unit tests for project data loading and migration
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
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication

from classes.project_data import ProjectDataStore
from classes.updates import UpdateManager
from qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app


class DummySettings:
    actionType = types.SimpleNamespace(IMPORT="import")

    def __init__(self):
        self.values = {
            "recent_projects": [],
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
        }
        self.saved = False
        self.default_paths = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.saved = True

    def setDefaultPath(self, action, value):
        self.default_paths[action] = value


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()
        self.project = None
        self.updates = None
        self.window = None

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


def ensure_app_state(app):
    return ensure_qt_app_state(
        app,
        DummySettings,
        project_factory=ProjectDataStore,
        updates_factory=UpdateManager,
        extra_attrs={"window": None},
    )


class DummyAction:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = value


class ReaderStub:
    def __init__(self, json_text):
        self.json_text = json_text
        self.open_calls = 0
        self.close_calls = 0

    def Open(self):
        self.open_calls += 1

    def Json(self):
        return self.json_text

    def Close(self):
        self.close_calls += 1


def make_store():
    store = ProjectDataStore.__new__(ProjectDataStore)
    store.data_type = "project data"
    store.current_filepath = None
    store.has_unsaved_changes = False
    store._data = {}
    return store


class ProjectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def setUp(self):
        ensure_app_state(self.app)
        self.app.settings = DummySettings()
        self.app.window = None

    def tearDown(self):
        ensure_app_state(self.app)

    def test_load_restores_history_and_enables_waveform_clear(self):
        store = make_store()
        default_project = {
            "clips": [],
            "effects": [],
            "markers": [],
            "layers": [],
            "files": [],
            "history": {"undo": [], "redo": []},
            "version": {"openshot-qt": "3.4.0", "libopenshot": "0.5.0"},
        }
        loaded_project = {
            "clips": [],
            "effects": [],
            "markers": [],
            "layers": [],
            "files": [{"id": "F1", "ui": {"audio_data": [0.1, 0.2]}}],
            "version": {"openshot-qt": "3.4.0", "libopenshot": "0.5.0"},
        }

        loaded_payloads = []
        clear_waveform_action = DummyAction()
        self.app.window = types.SimpleNamespace(actionClearWaveformData=clear_waveform_action)
        self.app.updates = types.SimpleNamespace(load=loaded_payloads.append)

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "example.osp")
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(store, "new", lambda: setattr(store, "_data", default_project.copy()))
                )
                stack.enter_context(
                    patch.object(
                        store,
                        "read_from_file",
                        lambda file_path, path_mode="ignore": loaded_project.copy(),
                    )
                )
                stack.enter_context(patch.object(store, "check_if_paths_are_valid", lambda: None))
                stack.enter_context(patch.object(store, "add_to_recent_files", lambda file_path: None))
                stack.enter_context(patch.object(store, "upgrade_project_data_structures", lambda: None))
                stack.enter_context(patch.object(store, "get_profile", lambda **kwargs: object()))
                stack.enter_context(patch.object(store, "apply_default_audio_settings", lambda: None))
                ProjectDataStore.load(store, project_path, clear_thumbnails=False)

        self.assertEqual(store.current_filepath, project_path)
        self.assertFalse(store.has_unsaved_changes)
        self.assertEqual(store._data["history"], {"undo": [], "redo": []})
        self.assertTrue(clear_waveform_action.enabled)
        self.assertEqual(loaded_payloads, [store._data])

    def test_repair_capped_media_dimensions_updates_file_and_clip_reader(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = os.path.join(tmpdir, "source.mp4")
            with open(media_path, "wb") as handle:
                handle.write(b"video")

            store._data = {
                "files": [{
                    "id": "F1",
                    "path": media_path,
                    "has_video": True,
                    "has_audio": True,
                    "width": 128,
                    "height": 72,
                    "display_ratio": {"num": 16, "den": 9},
                    "pixel_ratio": {"num": 1, "den": 1},
                }],
                "clips": [{
                    "id": "C1",
                    "reader": {
                        "id": "F1",
                        "path": media_path,
                        "width": 128,
                        "height": 72,
                    },
                }],
            }
            reader = ReaderStub(
                '{"id":"F1","path":"%s","has_video":true,"has_audio":true,'
                '"width":1920,"height":1080,'
                '"display_ratio":{"num":16,"den":9},'
                '"pixel_ratio":{"num":1,"den":1},'
                '"fps":{"num":30000,"den":1001},'
                '"video_length":300,"duration":10.0}' % media_path.replace("\\", "\\\\")
            )

            with patch("classes.project_data.openshot.Clip.CreateReader", return_value=reader):
                ProjectDataStore._repair_capped_media_dimensions(store)

        self.assertEqual(reader.open_calls, 1)
        self.assertEqual(reader.close_calls, 1)
        self.assertEqual(store._data["files"][0]["width"], 1920)
        self.assertEqual(store._data["files"][0]["height"], 1080)
        self.assertEqual(store._data["clips"][0]["reader"]["width"], 1920)
        self.assertEqual(store._data["clips"][0]["reader"]["height"], 1080)

    def test_load_migrates_flat_thumbnails_into_per_file_folders(self):
        store = make_store()
        project_data = {
            "clips": [],
            "effects": [],
            "markers": [],
            "layers": [],
            "files": [{"id": "F1", "path": "/project/source.mp4"}],
            "history": {"undo": [], "redo": []},
            "version": {"openshot-qt": "3.4.0", "libopenshot": "0.5.0"},
        }

        clear_waveform_action = DummyAction()
        self.app.window = types.SimpleNamespace(actionClearWaveformData=clear_waveform_action)
        self.app.updates = types.SimpleNamespace(load=lambda payload: None)

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "example.osp")
            assets_path = os.path.join(tmpdir, "example_assets")
            thumbnail_root = os.path.join(assets_path, "thumbnail")
            os.makedirs(thumbnail_root, exist_ok=True)
            flat_thumb = os.path.join(thumbnail_root, "F1-8.png")
            with open(flat_thumb, "w", encoding="utf-8") as handle:
                handle.write("thumb")

            default_thumb_root = os.path.join(tmpdir, "default-thumbs")
            os.mkdir(default_thumb_root)

            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(store, "new", lambda: setattr(store, "_data", project_data.copy()))
                )
                stack.enter_context(
                    patch.object(
                        store,
                        "read_from_file",
                        lambda file_path, path_mode="ignore": project_data.copy(),
                    )
                )
                stack.enter_context(patch.object(store, "check_if_paths_are_valid", lambda: None))
                stack.enter_context(patch.object(store, "add_to_recent_files", lambda file_path: None))
                stack.enter_context(patch.object(store, "upgrade_project_data_structures", lambda: None))
                stack.enter_context(patch.object(store, "get_profile", lambda **kwargs: object()))
                stack.enter_context(patch.object(store, "apply_default_audio_settings", lambda: None))
                stack.enter_context(patch("classes.project_data.get_assets_path", return_value=assets_path))
                stack.enter_context(patch("classes.project_data.info.get_default_path", return_value=default_thumb_root))
                ProjectDataStore.load(store, project_path, clear_thumbnails=True)

            self.assertFalse(os.path.exists(flat_thumb))
            self.assertTrue(os.path.exists(os.path.join(thumbnail_root, "F1", "8.png")))

    def test_upgrade_project_data_structures_migrates_25_crop_effect(self):
        store = make_store()
        self.app.project = types.SimpleNamespace(generate_id=lambda: "EFF-1")
        store._data = {
            "version": {"openshot-qt": "2.5.1", "libopenshot": "0.2.7"},
            "id": "T0",
            "clips": [{
                "id": "C1",
                "effects": [],
                "crop_x": {"Points": [{"co": {"Y": 0.25}}]},
                "crop_y": {"Points": [{"co": {"Y": 0.0}}]},
                "crop_width": {"Points": [{"co": {"Y": 0.75}}]},
                "crop_height": {"Points": [{"co": {"Y": 0.5}}]},
            }],
        }

        with patch.object(store, "generate_id", lambda digits=10: "NEW-PROJECT-ID"):
            ProjectDataStore.upgrade_project_data_structures(store)

        clip = store._data["clips"][0]
        self.assertNotIn("crop_x", clip)
        self.assertTrue(clip["effects"])
        effect = clip["effects"][0]
        self.assertEqual(effect["id"], "EFF-1")
        self.assertEqual(effect["x"]["Points"][0]["co"]["Y"], 0.25)
        self.assertEqual(effect["right"]["Points"][0]["co"]["Y"], 0.25)
        self.assertEqual(effect["bottom"]["Points"][0]["co"]["Y"], 0.5)
        self.assertEqual(store._data["id"], "NEW-PROJECT-ID")

    def test_add_to_recent_files_moves_existing_path_to_end(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            one = os.path.join(tmpdir, "one.osp")
            two = os.path.join(tmpdir, "two.osp")
            three = os.path.join(tmpdir, "three.osp")
            self.app.settings.values["recent_projects"] = [one, two, three]

            ProjectDataStore.add_to_recent_files(store, two)

            self.assertEqual(
                self.app.settings.values["recent_projects"],
                [one, three, two],
            )
            self.assertTrue(self.app.settings.saved)

    def test_move_temp_paths_to_project_folder_copies_proxy_reader_into_project_assets(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            proxy_root = os.path.join(tmpdir, "runtime-optimized")
            os.mkdir(proxy_root)
            proxy_file = os.path.join(proxy_root, "F1.mp4")
            with open(proxy_file, "wb") as handle:
                handle.write(b"proxy")

            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")
            target_proxy_path = os.path.join(asset_path, "optimized")

            store._data = {
                "files": [
                    {
                        "id": "F1",
                        "path": os.path.join(tmpdir, "source.mp4"),
                        "proxy_reader": {
                            "id": "F1",
                            "path": proxy_file,
                        },
                    }
                ],
                "clips": [],
            }

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.get_assets_path", lambda path, create_paths=True: asset_path))
                stack.enter_context(patch("classes.project_data.info.PROXY_PATH", proxy_root))
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", os.path.join(tmpdir, "thumbs")))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", os.path.join(tmpdir, "titles")))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", os.path.join(tmpdir, "blender")))
                stack.enter_context(patch("classes.project_data.info.PROTOBUF_DATA_PATH", os.path.join(tmpdir, "protobuf")))
                stack.enter_context(patch("classes.project_data.info.CLIPBOARD_PATH", os.path.join(tmpdir, "clipboard")))
                stack.enter_context(patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", os.path.join(tmpdir, "comfy")))
                for folder in ("thumbs", "titles", "blender", "protobuf", "clipboard", "comfy"):
                    os.mkdir(os.path.join(tmpdir, folder))
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_path)

            self.assertTrue(os.path.exists(os.path.join(target_proxy_path, "F1.mp4")))
            self.assertEqual(
                store._data["files"][0]["proxy_reader"]["path"],
                os.path.join(target_proxy_path, "F1.mp4"),
            )

    def test_load_migrates_legacy_proxy_folder_to_optimized(self):
        store = make_store()
        project_data = {
            "clips": [],
            "effects": [],
            "markers": [],
            "layers": [],
            "files": [{
                "id": "F1",
                "path": "/project/source.mp4",
                "proxy_reader": {"path": ""},
            }],
            "history": {"undo": [], "redo": []},
            "version": {"openshot-qt": "3.4.0", "libopenshot": "0.5.0"},
        }

        clear_waveform_action = DummyAction()
        self.app.window = types.SimpleNamespace(actionClearWaveformData=clear_waveform_action)
        self.app.updates = types.SimpleNamespace(load=lambda payload: None)

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "example.osp")
            assets_path = os.path.join(tmpdir, "example_assets")
            legacy_proxy_root = os.path.join(assets_path, "proxies")
            os.makedirs(legacy_proxy_root, exist_ok=True)
            legacy_proxy = os.path.join(legacy_proxy_root, "F1.mp4")
            with open(legacy_proxy, "wb") as handle:
                handle.write(b"proxy")
            project_data["files"][0]["proxy_reader"]["path"] = legacy_proxy

            default_thumb_root = os.path.join(tmpdir, "default-thumbs")
            os.mkdir(default_thumb_root)

            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(store, "new", lambda: setattr(store, "_data", project_data.copy()))
                )
                stack.enter_context(
                    patch.object(
                        store,
                        "read_from_file",
                        lambda file_path, path_mode="ignore": project_data.copy(),
                    )
                )
                stack.enter_context(patch.object(store, "check_if_paths_are_valid", lambda: None))
                stack.enter_context(patch.object(store, "add_to_recent_files", lambda file_path: None))
                stack.enter_context(patch.object(store, "upgrade_project_data_structures", lambda: None))
                stack.enter_context(patch.object(store, "get_profile", lambda **kwargs: object()))
                stack.enter_context(patch.object(store, "apply_default_audio_settings", lambda: None))
                stack.enter_context(patch("classes.project_data.get_assets_path", return_value=assets_path))
                stack.enter_context(patch("classes.project_data.info.get_default_path", return_value=default_thumb_root))
                ProjectDataStore.load(store, project_path, clear_thumbnails=True)

            expected_proxy = os.path.join(assets_path, "optimized", "F1.mp4")
            self.assertFalse(os.path.exists(legacy_proxy))
            self.assertTrue(os.path.exists(expected_proxy))
            self.assertEqual(store._data["files"][0]["proxy_reader"]["path"], expected_proxy)

    def test_upgrade_project_data_structures_migrates_tracker_alpha_and_parent(self):
        store = make_store()
        store._data = {
            "version": {"openshot-qt": "3.1.1", "libopenshot": "0.3.0"},
            "id": "P1",
            "clips": [
                {
                    "id": "PARENT",
                    "effects": [{
                        "name": "Tracker",
                        "display_box_text": {"Points": [{"co": {"Y": 0.25}}]},
                        "objects": {
                            "obj-1": {
                                "child_clip_id": "CHILD",
                                "background_alpha": {"Points": [{"co": {"Y": 0.2}}]},
                                "stroke_alpha": {"Points": [{"co": {"Y": 0.8}}]},
                            }
                        },
                    }],
                },
                {"id": "CHILD", "effects": []},
            ],
        }

        ProjectDataStore.upgrade_project_data_structures(store)

        effect = store._data["clips"][0]["effects"][0]
        tracked = effect["objects"]["obj-1"]
        self.assertEqual(effect["display_box_text"]["Points"][0]["co"]["Y"], 0.75)
        self.assertEqual(tracked["background_alpha"]["Points"][0]["co"]["Y"], 0.8)
        self.assertEqual(tracked["stroke_alpha"]["Points"][0]["co"]["Y"], 0.19999999999999996)
        self.assertEqual(store._data["clips"][1]["parentObjectId"], "obj-1")

    def test_check_if_paths_are_valid_updates_missing_file_and_syncs_clip_reader(self):
        store = make_store()
        old_path = "/missing/file.mp4"
        new_path = "/found/file.mp4"
        store._data = {
            "files": [{"id": "F1", "path": old_path}],
            "clips": [{"id": "C1", "file_id": "F1", "reader": {"path": old_path}}],
            "effects": [],
        }

        self.app.window = types.SimpleNamespace()

        with ExitStack() as stack:
            stack.enter_context(
                patch("classes.project_data.os.path.exists", side_effect=lambda p: p == new_path)
            )
            stack.enter_context(
                patch("classes.project_data.find_missing_file", return_value=(new_path, True, False))
            )
            ProjectDataStore.check_if_paths_are_valid(store)

        self.assertEqual(store._data["files"][0]["path"], new_path)
        self.assertEqual(store._data["clips"][0]["reader"]["path"], new_path)
        self.assertEqual(self.app.settings.default_paths[self.app.settings.actionType.IMPORT], new_path)

    def test_check_if_paths_are_valid_reuses_decision_for_duplicate_missing_effect_paths(self):
        store = make_store()
        missing_path = "/missing/shared-mask.svg"
        new_path = "/found/shared-mask.svg"
        store._data = {
            "files": [],
            "clips": [],
            "effects": [
                {"id": "E1", "resource": missing_path},
                {"id": "E2", "resource": missing_path},
            ],
        }

        self.app.window = types.SimpleNamespace()
        calls = []

        def fake_find_missing_file(path, prompt_state):
            calls.append(path)
            return new_path, True, False

        with ExitStack() as stack:
            stack.enter_context(
                patch("classes.project_data.os.path.exists", side_effect=lambda p: p == new_path)
            )
            stack.enter_context(
                patch("classes.project_data.find_missing_file", side_effect=fake_find_missing_file)
            )
            ProjectDataStore.check_if_paths_are_valid(store)

        self.assertEqual(calls, [missing_path])
        self.assertEqual(store._data["effects"][0]["resource"], new_path)
        self.assertEqual(store._data["effects"][1]["resource"], new_path)

    def test_check_if_paths_are_valid_removes_missing_effect_when_skipped(self):
        store = make_store()
        missing_path = "/missing/mask.svg"
        store._data = {
            "files": [],
            "clips": [],
            "effects": [{"id": "E1", "resource": missing_path}],
        }

        self.app.window = types.SimpleNamespace()

        with ExitStack() as stack:
            stack.enter_context(patch("classes.project_data.os.path.exists", return_value=False))
            stack.enter_context(
                patch("classes.project_data.find_missing_file", return_value=("", False, True))
            )
            ProjectDataStore.check_if_paths_are_valid(store)

        self.assertEqual(store._data["effects"], [])

    def test_check_if_paths_are_valid_reuses_skip_decision_for_duplicate_missing_paths(self):
        store = make_store()
        missing_path = "/missing/shared.svg"
        store._data = {
            "files": [],
            "clips": [],
            "effects": [
                {"id": "E1", "resource": missing_path},
                {"id": "E2", "resource": missing_path},
            ],
        }

        self.app.window = types.SimpleNamespace()
        calls = []

        def fake_find_missing_file(path, prompt_state):
            calls.append(path)
            prompt_state["last_skip"] = "all"
            return "", False, True

        with ExitStack() as stack:
            stack.enter_context(patch("classes.project_data.os.path.exists", return_value=False))
            stack.enter_context(
                patch("classes.project_data.find_missing_file", side_effect=fake_find_missing_file)
            )
            ProjectDataStore.check_if_paths_are_valid(store)

        self.assertEqual(calls, [missing_path])
        self.assertEqual(store._data["effects"], [])

    def test_check_if_paths_are_valid_repairs_missing_clip_effect_reader_path(self):
        store = make_store()
        missing_path = "/missing/effect-mask.svg"
        found_path = "/found/effect-mask.svg"
        store._data = {
            "files": [],
            "clips": [{
                "id": "C1",
                "effects": [{
                    "id": "E1",
                    "mask_reader": {"path": missing_path},
                }],
            }],
            "effects": [],
        }

        self.app.window = types.SimpleNamespace()

        with ExitStack() as stack:
            stack.enter_context(
                patch("classes.project_data.os.path.exists", side_effect=lambda p: p == found_path)
            )
            stack.enter_context(
                patch("classes.project_data.find_missing_file", return_value=(found_path, True, False))
            )
            ProjectDataStore.check_if_paths_are_valid(store)

        self.assertEqual(
            store._data["clips"][0]["effects"][0]["mask_reader"]["path"],
            found_path,
        )

    def test_move_temp_paths_to_project_folder_updates_title_file_and_clip_reader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = os.path.abspath(tmpdir)
            old_title_dir = os.path.join(tmpdir, "working_title")
            old_thumb_dir = os.path.join(tmpdir, "working_thumb")
            old_blender_dir = os.path.join(tmpdir, "working_blender")
            old_proto_dir = os.path.join(tmpdir, "working_proto")
            old_clipboard_dir = os.path.join(tmpdir, "working_clipboard")
            old_comfy_dir = os.path.join(tmpdir, "working_comfy")
            for path in [
                old_title_dir, old_thumb_dir, old_blender_dir,
                old_proto_dir, old_clipboard_dir, old_comfy_dir,
            ]:
                os.mkdir(path)

            title_path = os.path.join(old_title_dir, "title.svg")
            with open(title_path, "w", encoding="utf-8") as handle:
                handle.write("<svg />")

            store = make_store()
            store._data = {
                "files": [{"id": "F1", "path": title_path}],
                "clips": [{"id": "C1", "file_id": "F1", "reader": {"path": title_path}, "effects": []}],
            }

            target_assets = os.path.join(tmpdir, "project_assets")
            project_file = os.path.join(tmpdir, "project.osp")

            with ExitStack() as stack:
                stack.enter_context(
                    patch("classes.project_data.get_assets_path", return_value=target_assets)
                )
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", old_thumb_dir))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", old_title_dir))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", old_blender_dir))
                stack.enter_context(
                    patch("classes.project_data.info.PROTOBUF_DATA_PATH", old_proto_dir)
                )
                stack.enter_context(
                    patch("classes.project_data.info.CLIPBOARD_PATH", old_clipboard_dir)
                )
                stack.enter_context(
                    patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", old_comfy_dir)
                )
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_file)

            expected_title = os.path.join(target_assets, "title", "title.svg")
            self.assertEqual(store._data["files"][0]["path"], expected_title)
            self.assertEqual(store._data["clips"][0]["reader"]["path"], expected_title)
            self.assertTrue(os.path.exists(expected_title))

    def test_move_temp_paths_to_project_folder_copies_nested_thumbnail_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = os.path.abspath(tmpdir)
            old_title_dir = os.path.join(tmpdir, "working_title")
            old_thumb_dir = os.path.join(tmpdir, "working_thumb")
            old_blender_dir = os.path.join(tmpdir, "working_blender")
            old_proto_dir = os.path.join(tmpdir, "working_proto")
            old_clipboard_dir = os.path.join(tmpdir, "working_clipboard")
            old_comfy_dir = os.path.join(tmpdir, "working_comfy")
            for path in [
                old_title_dir, old_thumb_dir, old_blender_dir,
                old_proto_dir, old_clipboard_dir, old_comfy_dir,
            ]:
                os.mkdir(path)

            nested_thumb_dir = os.path.join(old_thumb_dir, "F1")
            os.mkdir(nested_thumb_dir)
            nested_thumb_path = os.path.join(nested_thumb_dir, "8.png")
            with open(nested_thumb_path, "w", encoding="utf-8") as handle:
                handle.write("thumb")

            store = make_store()
            store._data = {"files": [], "clips": []}

            target_assets = os.path.join(tmpdir, "project_assets")
            project_file = os.path.join(tmpdir, "project.osp")

            with ExitStack() as stack:
                stack.enter_context(
                    patch("classes.project_data.get_assets_path", return_value=target_assets)
                )
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", old_thumb_dir))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", old_title_dir))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", old_blender_dir))
                stack.enter_context(
                    patch("classes.project_data.info.PROTOBUF_DATA_PATH", old_proto_dir)
                )
                stack.enter_context(
                    patch("classes.project_data.info.CLIPBOARD_PATH", old_clipboard_dir)
                )
                stack.enter_context(
                    patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", old_comfy_dir)
                )
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_file)

            self.assertTrue(os.path.exists(os.path.join(target_assets, "thumbnail", "F1", "8.png")))

    def test_move_temp_paths_to_project_folder_moves_runtime_proxy_and_cleans_source(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            proxy_root = os.path.join(tmpdir, "runtime-optimized")
            os.mkdir(proxy_root)
            proxy_file = os.path.join(proxy_root, "F1.mp4")
            with open(proxy_file, "wb") as handle:
                handle.write(b"proxy")

            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")
            target_proxy_path = os.path.join(asset_path, "optimized")

            store._data = {
                "files": [
                    {
                        "id": "F1",
                        "path": os.path.join(tmpdir, "source.mp4"),
                        "proxy_reader": {
                            "id": "F1",
                            "path": proxy_file,
                        },
                    }
                ],
                "clips": [],
            }

            default_paths = {
                "PROXY_PATH": proxy_root,
                "THUMBNAIL_PATH": os.path.join(tmpdir, "thumbs"),
                "TITLE_PATH": os.path.join(tmpdir, "titles"),
                "BLENDER_PATH": os.path.join(tmpdir, "blender"),
                "PROTOBUF_DATA_PATH": os.path.join(tmpdir, "protobuf"),
                "CLIPBOARD_PATH": os.path.join(tmpdir, "clipboard"),
                "COMFYUI_OUTPUT_PATH": os.path.join(tmpdir, "comfy"),
            }

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.get_assets_path", lambda path, create_paths=True: asset_path))
                stack.enter_context(patch("classes.project_data.info.PROXY_PATH", proxy_root))
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", default_paths["THUMBNAIL_PATH"]))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", default_paths["TITLE_PATH"]))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", default_paths["BLENDER_PATH"]))
                stack.enter_context(patch("classes.project_data.info.PROTOBUF_DATA_PATH", default_paths["PROTOBUF_DATA_PATH"]))
                stack.enter_context(patch("classes.project_data.info.CLIPBOARD_PATH", default_paths["CLIPBOARD_PATH"]))
                stack.enter_context(patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", default_paths["COMFYUI_OUTPUT_PATH"]))
                stack.enter_context(
                    patch(
                        "classes.project_data.info.get_default_path",
                        side_effect=default_paths.get,
                    )
                )
                for name, folder in default_paths.items():
                    if name != "PROXY_PATH":
                        os.mkdir(folder)
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_path)

            self.assertTrue(os.path.exists(os.path.join(target_proxy_path, "F1.mp4")))
            self.assertFalse(os.path.exists(proxy_file))
            self.assertEqual(
                store._data["files"][0]["proxy_reader"]["path"],
                os.path.join(target_proxy_path, "F1.mp4"),
            )

    def test_move_temp_paths_to_project_folder_removes_runtime_duplicates_when_target_exists(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            title_root = os.path.join(tmpdir, "runtime-title")
            os.mkdir(title_root)
            source_title = os.path.join(title_root, "title.svg")
            with open(source_title, "w", encoding="utf-8") as handle:
                handle.write("<svg />")

            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")
            target_title_path = os.path.join(asset_path, "title")
            os.makedirs(target_title_path, exist_ok=True)
            existing_title = os.path.join(target_title_path, "title.svg")
            with open(existing_title, "w", encoding="utf-8") as handle:
                handle.write("<svg />")

            store._data = {
                "files": [{"id": "F1", "path": source_title}],
                "clips": [{"id": "C1", "file_id": "F1", "reader": {"path": source_title}, "effects": []}],
            }

            default_paths = {
                "THUMBNAIL_PATH": os.path.join(tmpdir, "thumbs"),
                "TITLE_PATH": title_root,
                "BLENDER_PATH": os.path.join(tmpdir, "blender"),
                "PROTOBUF_DATA_PATH": os.path.join(tmpdir, "protobuf"),
                "CLIPBOARD_PATH": os.path.join(tmpdir, "clipboard"),
                "COMFYUI_OUTPUT_PATH": os.path.join(tmpdir, "comfy"),
                "PROXY_PATH": os.path.join(tmpdir, "optimized"),
            }

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.get_assets_path", lambda path, create_paths=True: asset_path))
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", default_paths["THUMBNAIL_PATH"]))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", default_paths["TITLE_PATH"]))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", default_paths["BLENDER_PATH"]))
                stack.enter_context(patch("classes.project_data.info.PROTOBUF_DATA_PATH", default_paths["PROTOBUF_DATA_PATH"]))
                stack.enter_context(patch("classes.project_data.info.CLIPBOARD_PATH", default_paths["CLIPBOARD_PATH"]))
                stack.enter_context(patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", default_paths["COMFYUI_OUTPUT_PATH"]))
                stack.enter_context(patch("classes.project_data.info.PROXY_PATH", default_paths["PROXY_PATH"]))
                stack.enter_context(
                    patch(
                        "classes.project_data.info.get_default_path",
                        side_effect=default_paths.get,
                    )
                )
                for name, folder in default_paths.items():
                    if name != "TITLE_PATH":
                        os.mkdir(folder)
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_path)

            self.assertFalse(os.path.exists(source_title))
            self.assertTrue(os.path.exists(existing_title))
            self.assertEqual(store._data["files"][0]["path"], existing_title)
            self.assertEqual(store._data["clips"][0]["reader"]["path"], existing_title)

    def test_move_temp_paths_to_project_folder_updates_blender_and_protobuf_paths_together(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            blender_root = os.path.join(tmpdir, "runtime-blender")
            protobuf_root = os.path.join(tmpdir, "runtime-protobuf")
            thumb_root = os.path.join(tmpdir, "thumbs")
            title_root = os.path.join(tmpdir, "titles")
            clipboard_root = os.path.join(tmpdir, "clipboard")
            comfy_root = os.path.join(tmpdir, "comfy")
            proxy_root = os.path.join(tmpdir, "optimized")
            for folder in [blender_root, protobuf_root, thumb_root, title_root, clipboard_root, comfy_root, proxy_root]:
                os.mkdir(folder)

            blender_job_root = os.path.join(blender_root, "0NHHRJD8L4")
            os.mkdir(blender_job_root)
            blender_asset = os.path.join(blender_job_root, "TitleFileName%04d.png")
            with open(blender_asset, "w", encoding="utf-8") as handle:
                handle.write("frame-seq")

            protobuf_asset = os.path.join(protobuf_root, "B5ONPQNB8X.data")
            with open(protobuf_asset, "w", encoding="utf-8") as handle:
                handle.write("tracker-data")

            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")

            store._data = {
                "files": [
                    {"id": "F1", "path": blender_asset},
                ],
                "clips": [
                    {
                        "id": "C1",
                        "file_id": "F1",
                        "reader": {"path": blender_asset},
                        "effects": [
                            {"id": "E1", "protobuf_data_path": protobuf_asset},
                        ],
                    },
                ],
            }

            default_paths = {
                "THUMBNAIL_PATH": thumb_root,
                "TITLE_PATH": title_root,
                "BLENDER_PATH": blender_root,
                "PROTOBUF_DATA_PATH": protobuf_root,
                "CLIPBOARD_PATH": clipboard_root,
                "COMFYUI_OUTPUT_PATH": comfy_root,
                "PROXY_PATH": proxy_root,
            }

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.get_assets_path", lambda path, create_paths=True: asset_path))
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", default_paths["THUMBNAIL_PATH"]))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", default_paths["TITLE_PATH"]))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", default_paths["BLENDER_PATH"]))
                stack.enter_context(patch("classes.project_data.info.PROTOBUF_DATA_PATH", default_paths["PROTOBUF_DATA_PATH"]))
                stack.enter_context(patch("classes.project_data.info.CLIPBOARD_PATH", default_paths["CLIPBOARD_PATH"]))
                stack.enter_context(patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", default_paths["COMFYUI_OUTPUT_PATH"]))
                stack.enter_context(patch("classes.project_data.info.PROXY_PATH", default_paths["PROXY_PATH"]))
                stack.enter_context(
                    patch(
                        "classes.project_data.info.get_default_path",
                        side_effect=default_paths.get,
                    )
                )
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_path)

            expected_blender = os.path.join(asset_path, "blender", "0NHHRJD8L4", "TitleFileName%04d.png")
            expected_protobuf = os.path.join(asset_path, "protobuf_data", "B5ONPQNB8X.data")
            self.assertEqual(store._data["files"][0]["path"], expected_blender)
            self.assertEqual(store._data["clips"][0]["reader"]["path"], expected_blender)
            self.assertEqual(
                store._data["clips"][0]["effects"][0]["protobuf_data_path"],
                expected_protobuf,
            )
            self.assertTrue(os.path.exists(expected_blender))
            self.assertTrue(os.path.exists(expected_protobuf))
