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

import copy
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import openshot

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication

from classes.project_data import ProjectDataStore
from classes.updates import UpdateManager
from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app


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

    def setUp(self):
        ensure_app_state(self.app)
        self.app.settings = DummySettings()
        self.app.window = None

    def tearDown(self):
        ensure_app_state(self.app)

    def test_new_project_uses_default_track_count(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("classes.project_data.info.USER_DEFAULT_PROJECT", os.path.join(tmpdir, "default.osp")):
            for value, expected in ((None, 5), (1, 1), (3, 3), (8, 8), (100, 100),
                                    (0, 1), (101, 100), ("invalid", 5)):
                with self.subTest(value=value):
                    self.app.settings.set("default-track-count", value)
                    store = ProjectDataStore()
                    tracks = store.get("layers")
                    self.assertEqual(len(tracks), expected)
                    self.assertEqual([track["number"] for track in tracks],
                                     [index * 1000000 for index in range(1, expected + 1)])
                    self.assertEqual(len({track["id"] for track in tracks}), expected)
                    self.assertTrue(all(track["label"] == "" and not track["lock"] for track in tracks))
                    self.assertFalse(store.has_unsaved_changes)

            self.app.settings.set("default-track-count", 2)
            store.new()
            self.assertEqual(len(store.get("layers")), 2)
            store.get("layers")[0]["label"] = "Changed"
            self.assertEqual(store.get("layers")[1]["label"], "")
            store.new()
            self.assertEqual(store.get("layers")[0]["label"], "")

    def test_new_project_preserves_custom_template_tracks(self):
        with open(os.path.join(PATH, "settings", "_default.project"), encoding="utf-8") as handle:
            template = json.load(handle)
        template["layers"] = [{"id": "custom", "number": 7000000, "label": "Voice", "lock": True, "y": 0}]
        template["markers"] = [{"id": "marker", "position": 2}]
        self.app.settings.set("default-track-count", 8)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "default.osp")
            with patch("classes.project_data.info.USER_DEFAULT_PROJECT", template_path):
                for layers in (template["layers"], []):
                    with self.subTest(layers=layers):
                        template["layers"] = layers
                        with open(template_path, "w", encoding="utf-8") as handle:
                            json.dump(template, handle)
                        store = ProjectDataStore()
                        self.assertEqual(store.get("layers"), layers)
                        self.assertEqual(store.get("markers"), template["markers"])

    def test_load_preserves_saved_tracks_over_default_count(self):
        self.app.settings.set("default-track-count", 8)
        self.app.window = types.SimpleNamespace(actionClearWaveformData=DummyAction())
        self.app.updates = types.SimpleNamespace(load=lambda payload: None)
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("classes.project_data.info.USER_DEFAULT_PROJECT", os.path.join(tmpdir, "default.osp")):
            store = ProjectDataStore()
            self.assertEqual(len(store.get("layers")), 8)
            saved = copy.deepcopy(store._data)
            project_path = os.path.join(tmpdir, "saved.osp")
            for layers in ([{"id": "saved", "number": 9000000, "label": "Music", "lock": True, "y": 0}], []):
                with self.subTest(layers=layers):
                    saved["layers"] = layers
                    with open(project_path, "w", encoding="utf-8") as handle:
                        json.dump(saved, handle)
                    with patch.object(store, "check_if_paths_are_valid"), \
                            patch.object(store, "add_to_recent_files"), \
                            patch.object(store, "upgrade_project_data_structures"):
                        store.load(project_path, clear_thumbnails=False)
                    self.assertEqual(store.get("layers"), layers)

    def test_set_deep_merges_tracked_object_updates(self):
        store = make_store()
        store._data = {
            "clips": [
                {
                    "id": "C1",
                    "effects": [
                        {
                            "id": "E1",
                            "name": "Object Detector",
                            "objects": {
                                "E1-0": {
                                    "delta_x": {"Points": []},
                                    "delta_y": {"Points": []},
                                },
                                "E1-1": {
                                    "delta_x": {"Points": []},
                                    "delta_y": {"Points": []},
                                },
                            },
                        }
                    ],
                }
            ]
        }

        store._set(
            ["clips", {"id": "C1"}, "effects", {"id": "E1"}],
            {"objects": {"E1-1": {"delta_x": {"Points": [{"co": {"X": 5, "Y": 0.25}}]}}}},
        )

        objects = store._data["clips"][0]["effects"][0]["objects"]
        self.assertIn("E1-0", objects)
        self.assertEqual(objects["E1-1"]["delta_y"], {"Points": []})
        self.assertEqual(objects["E1-1"]["delta_x"]["Points"][0]["co"], {"X": 5, "Y": 0.25})

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

    def test_load_migrates_flat_thumbnails_into_per_file_folders(self):
        self._check_thumbnail_migration_on_load(unreadable=False)

    def test_load_completes_when_thumbnail_directory_is_unreadable(self):
        self._check_thumbnail_migration_on_load(unreadable=True)

    def _check_thumbnail_migration_on_load(self, unreadable):
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
        loaded = []
        self.app.updates = types.SimpleNamespace(load=lambda payload: loaded.append(payload))

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
                if unreadable:
                    original_listdir = os.listdir

                    def guarded_listdir(path):
                        if path == thumbnail_root:
                            raise PermissionError("protected thumbnail directory")
                        return original_listdir(path)

                    stack.enter_context(patch("classes.thumbnail.os.listdir", side_effect=guarded_listdir))
                ProjectDataStore.load(store, project_path, clear_thumbnails=True)

            self.assertEqual(loaded, [store._data])
            self.assertEqual(store.current_filepath, project_path)
            self.assertFalse(store.has_unsaved_changes)
            self.assertEqual(os.path.exists(flat_thumb), unreadable)
            self.assertEqual(os.path.exists(os.path.join(thumbnail_root, "F1", "8.png")), not unreadable)

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

    def test_upgrade_preserves_location_curves_in_their_original_units(self):
        # Asynchronous keyframes, nonlinear handles, changing sign, and a trim
        # must survive exactly. The engine evaluates them at render time.
        points = {"Points": [
            {"co": {"X": 1, "Y": -0.25}, "interpolation": openshot.BEZIER,
             "handle_left": {"X": 0.2, "Y": 0.8},
             "handle_right": {"X": 0.7, "Y": 0.1}},
            {"co": {"X": 101, "Y": 0.4}, "interpolation": openshot.LINEAR},
        ]}
        for version, library, expected in (
            ("3.5.1", "0.7.0", "canvas"),
            ("3.5.2", "0.7.0", "canvas"),
            ("3.4.0", "0.5.0", "canvas"),
            ("4.0.0", "1.0.0", "geometry"),
        ):
            for mode in (openshot.SCALE_FIT, openshot.SCALE_STRETCH,
                         openshot.SCALE_NONE, openshot.SCALE_CROP):
                with self.subTest(version=version, mode=mode):
                    clip = {
                        "id": "C1", "scale": mode, "start": 1.5, "end": 5,
                        "gravity": openshot.GRAVITY_TOP_RIGHT,
                        "location_x": copy.deepcopy(points),
                        "location_y": {"Points": [{"co": {"X": 1, "Y": 0.25}}]},
                        "scale_x": {"Points": [
                            {"co": {"X": 1, "Y": 0.5}},
                            {"co": {"X": 51, "Y": 2.0}}]},
                        "margin": {"Points": [{"co": {"X": 30, "Y": 0.1}}]},
                        "effects": [],
                    }
                    # Missing media dimensions must not prevent migration.
                    original = copy.deepcopy(clip)
                    store = make_store()
                    store._data = {
                        "version": {"openshot-qt": version, "libopenshot": library},
                        "id": "P1", "width": 1920, "height": 1080,
                        "files": [], "clips": [clip],
                    }
                    store.upgrade_project_data_structures()
                    self.assertEqual(clip, dict(original, location_coordinate_system=expected))
                    store.upgrade_project_data_structures()
                    self.assertEqual(clip, dict(original, location_coordinate_system=expected))
                    # Simulate save/reload with the current version stamp.
                    store._data["version"]["openshot-qt"] = "4.0.1"
                    saved = json.dumps(store._data)
                    store._data = json.loads(saved)
                    store.upgrade_project_data_structures()
                    self.assertEqual(store._data, json.loads(saved))

    def test_location_migration_preserves_deleted_and_redo_clips_in_history(self):
        for version, library, expected in (("3.5.1", "0.7.0", "canvas"),
                                           ("3.5.2", "0.7.0", "canvas"),
                                           ("4.0.0", "1.0.0", "geometry")):
            with self.subTest(version=version):
                clip = {"id": "deleted", "scale": openshot.SCALE_CROP,
                        "location_x": {"Points": [{"co": {"X": 1, "Y": 0.25}}]}}
                effect = {"id": "effect", "brightness": 0.5}
                history = {
                    "undo": [{"type": "delete", "key": ["clips", {"id": "deleted"}],
                              "value": {}, "old_values": copy.deepcopy(clip)}],
                    "redo": [{"type": "insert", "key": ["clips"],
                              "value": copy.deepcopy(clip), "old_values": {}},
                             {"type": "update", "key": ["clips", {"id": "C1"}, "effects"],
                              "value": copy.deepcopy(effect), "old_values": {}},
                             {"type": "update", "key": ["effects", {"id": "E1"}],
                              "value": copy.deepcopy(effect), "old_values": {}}],
                }
                store = make_store()
                store._data = {
                    "version": {"openshot-qt": version, "libopenshot": library},
                    "id": "P1", "clips": [], "history": history,
                }
                store.upgrade_project_data_structures()
                migrated = dict(clip, location_coordinate_system=expected)
                self.assertEqual(history["undo"][0]["old_values"], migrated)
                self.assertEqual(history["redo"][0]["value"], migrated)
                self.assertEqual(history["undo"][0]["value"], {})
                self.assertEqual(history["redo"][1]["value"], effect)
                self.assertEqual(history["redo"][2]["value"], effect)

    def test_location_migration_keeps_explicit_conventions(self):
        for version, library in (("3.5.1", "0.7.0"), ("3.5.2", "0.7.0"),
                                 ("4.0.0", "1.0.0")):
            for coordinates in ("canvas", "geometry"):
                with self.subTest(version=version, coordinates=coordinates):
                    store = make_store()
                    store._data = {
                        "version": {"openshot-qt": version, "libopenshot": library},
                        "id": "P1", "clips": [{"location_coordinate_system": coordinates}],
                    }
                    original = copy.deepcopy(store._data)
                    store.upgrade_project_data_structures()
                    self.assertEqual(store._data, original)

    def test_current_and_development_projects_keep_default_location_behavior(self):
        for version in ("4.0.1", "4.0.2", "4.1.0", "4.0.0-dev", "3.5.1-dev", "3.5.2-dev"):
            with self.subTest(version=version):
                store = make_store()
                store._data = {
                    "version": {"openshot-qt": version, "libopenshot": "1.0.1"},
                    "id": "P1", "clips": [{"scale": openshot.SCALE_CROP}],
                }
                original = copy.deepcopy(store._data)
                store.upgrade_project_data_structures()
                self.assertEqual(store._data, original)

    def test_mixed_generation_clips_keep_units_through_native_save_and_reopen(self):
        clips = []
        for version, library, coordinates in (
            ("3.5.2", "0.7.0", "canvas"),
            ("4.0.0", "1.0.0", "geometry"),
            ("4.0.1", "1.0.1", "auto"),
        ):
            for scale in (openshot.SCALE_FIT, openshot.SCALE_CROP,
                          openshot.SCALE_STRETCH, openshot.SCALE_NONE):
                native = openshot.Clip()
                native.scale = scale
                native.location_x = openshot.Keyframe(-0.4)
                native.location_x.AddPoint(30, 0.3, openshot.BEZIER)
                native.location_y = openshot.Keyframe(0.2)
                clip = json.loads(native.Json())
                clip["id"] = "%s-%s" % (version, scale)
                if version != "4.0.1":
                    del clip["location_coordinate_system"]
                store = make_store()
                store._data = {
                    "id": "P1", "clips": [clip],
                    "version": {"openshot-qt": version, "libopenshot": library},
                }
                store.upgrade_project_data_structures()
                self.assertEqual(clip["location_coordinate_system"], coordinates)
                clips.append(clip)

        # A single saved project can contain imported clips from both older
        # conventions and new clips using auto. Each must retain its own units.
        for saved_version in ("4.0.1", "4.0.2", "4.1.0"):
            with self.subTest(saved_version=saved_version):
                round_tripped = []
                for clip in clips:
                    native = openshot.Clip()
                    native.SetJson(json.dumps(clip))
                    restored = json.loads(native.Json())
                    for field in ("location_coordinate_system", "location_x", "location_y",
                                  "scale", "scale_x", "scale_y"):
                        self.assertEqual(restored[field], clip[field])
                    round_tripped.append(restored)
                original = copy.deepcopy(round_tripped)
                store._data = json.loads(json.dumps({
                    "id": "P1", "clips": round_tripped,
                    "version": {"openshot-qt": saved_version, "libopenshot": "1.0.1"},
                }))
                store.upgrade_project_data_structures()
                clips = store._data["clips"]
                self.assertEqual(clips, original)

    def test_upgrade_does_not_remigrate_development_project(self):
        store = make_store()
        store._data = {
            "version": {"openshot-qt": "3.5.1-dev", "libopenshot": "0.7.0"},
            "id": "P1",
            "width": 1920,
            "height": 1080,
            "files": [],
            "clips": [{
                "id": "C1",
                "scale": openshot.SCALE_CROP,
                "gravity": openshot.GRAVITY_CENTER,
                "reader": {"width": 1080, "height": 1920},
                "location_x": {"Points": [{"co": {"X": 1, "Y": 0.5}}]},
                "location_y": {"Points": [{"co": {"X": 1, "Y": -0.5}}]},
                "effects": [],
            }],
        }

        ProjectDataStore.upgrade_project_data_structures(store)

        clip = store._data["clips"][0]
        self.assertEqual(clip["location_x"]["Points"][0]["co"]["Y"], 0.5)
        self.assertEqual(clip["location_y"]["Points"][0]["co"]["Y"], -0.5)

    def test_orphaned_clips_recover_from_embedded_readers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "overlay.png")
            with open(path, "wb") as image:
                image.write(b"png")
            store = make_store()
            store._data = {
                "files": [{"id": "existing", "path": path}],
                "clips": [
                    {"id": "C1", "file_id": "orphan", "reader": {
                        "id": "orphan", "path": path, "type": "QtImageReader",
                        "has_single_image": True}, "start": 0, "end": .04},
                    {"id": "C2", "file_id": "missing", "reader": {
                        "id": "missing", "path": path + ".png", "type": "QtImageReader",
                        "has_single_image": True}, "start": 0, "end": .04},
                ], "effects": [],
            }
            with open(path + ".png", "wb") as image:
                image.write(b"png")
            with patch("classes.project_data.find_missing_file") as prompt:
                store.check_if_paths_are_valid()
                prompt.assert_not_called()
            self.assertEqual(len(store._data["clips"]), 2)
            self.assertEqual(len(store._data["files"]), 2)
            self.assertEqual(store._data["clips"][0]["file_id"], "existing")
            self.assertEqual(store._data["clips"][0]["reader"]["id"], "existing")
            restored = store._data["files"][1]
            self.assertEqual(restored["id"], "missing")
            self.assertEqual(restored["media_type"], "image")
            self.assertIsNot(restored, store._data["clips"][1]["reader"])
            original = copy.deepcopy(store._data)
            store._data = json.loads(json.dumps(store._data))
            store.check_if_paths_are_valid()
            self.assertEqual(store._data, original)

    def test_issue_6177_generated_projects_load_visible_clips(self):
        import runpy
        from pathlib import Path
        from classes import info
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.object(info, "USER_DEFAULT_PROJECT", os.path.join(directory, "default.osp")))
            stack.enter_context(patch("sys.argv", ["generate_issue_6177_projects.py", directory]))
            generator = Path(PATH).parent / "benchmarks" / "generate_issue_6177_projects.py"
            runpy.run_path(str(generator), run_name="__main__")
            self.app.window = types.SimpleNamespace(actionClearWaveformData=DummyAction())
            self.app.updates = types.SimpleNamespace(load=lambda payload: None)
            for filename in Path(directory).glob("*.osp"):
                with self.subTest(project=filename.name):
                    store = ProjectDataStore()
                    with patch.object(store, "add_to_recent_files"):
                        store.load(str(filename), clear_thumbnails=False)
                    self.assertEqual(len(store._data["files"]), 5)
                    self.assertEqual(len(store._data["clips"]), 5)
                    layers = {layer["number"] for layer in store._data["layers"]}
                    fps = store._data["fps"]
                    timeline = openshot.Timeline(1280, 720, openshot.Fraction(fps["num"], fps["den"]),
                                                 44100, 2, openshot.LAYOUT_STEREO)
                    timeline.Open()
                    native_clips = []
                    for clip in store._data["clips"]:
                        self.assertIn(clip["layer"], layers)
                        self.assertEqual(clip["alpha"]["Points"][0]["co"]["Y"], 1)
                        self.assertGreaterEqual(100 * clip["duration"] / store._data["scale"], 20)
                        native = openshot.Clip()
                        native.SetJson(json.dumps(clip))
                        timeline.AddClip(native)
                        native_clips.append(native)
                    self.assertEqual(bytes(timeline.GetFrame(1).GetPixelsBytes())[:4], bytes((255, 0, 0, 255)))
                    self.assertEqual(bytes(timeline.GetFrame(timeline.GetMaxFrame()).GetPixelsBytes())[:4],
                                     bytes((0, 0, 255, 255)))
                    timeline.Close()

    def test_orphaned_png_survives_native_save_and_load(self):
        from classes import info
        from qt_api import QImage, QColor
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            for name in ("ASSETS_PATH", "THUMBNAIL_PATH", "TITLE_PATH", "BLENDER_PATH",
                         "PROTOBUF_DATA_PATH", "CLIPBOARD_PATH", "COMFYUI_OUTPUT_PATH", "PROXY_PATH"):
                stack.enter_context(patch.object(info, name, os.path.join(directory, name)))
            stack.enter_context(patch.object(info, "USER_DEFAULT_PROJECT", os.path.join(directory, "default.osp")))
            path = os.path.join(directory, "overlay.png")
            image = QImage(16, 16, QImage.Format_RGBA8888)
            image.fill(QColor("red"))
            self.assertTrue(image.save(path))
            native = openshot.Clip(path)
            native.End(.04)
            clip = json.loads(native.Json())
            clip.update(id="C1", file_id="orphan", layer=5000000)
            clip["reader"]["id"] = "orphan"
            store = ProjectDataStore()
            store.apply_profile(store.get_profile(profile_desc="HD 720p 25 fps"))
            store._data["clips"] = [clip]
            store._data["files"] = []
            self.app.window = types.SimpleNamespace(actionClearWaveformData=DummyAction())
            self.app.updates = types.SimpleNamespace(load=lambda payload: None)
            stack.enter_context(patch.object(store, "add_to_recent_files"))
            for backup in (True, False):
                with self.subTest(backup=backup):
                    filename = os.path.join(directory, "saved.osp")
                    store.save(filename, backup_only=backup)
                    store.load(filename, clear_thumbnails=False)
                    self.assertEqual(len(store._data["clips"]), 1)
                    self.assertEqual(len(store._data["files"]), 1)
                    restored = store._data["clips"][0]
                    self.assertEqual(restored["reader"]["path"], path)
                    self.assertEqual(restored["file_id"], store._data["files"][0]["id"])
                    self.assertAlmostEqual(restored["end"], .04)
                    native.SetJson(json.dumps(restored))
                    self.assertAlmostEqual(native.Duration(), .04)

    def test_orphan_recovery_respects_missing_media_skip(self):
        store = make_store()
        store._data = {"files": [], "clips": [
            {"id": "C1", "file_id": "orphan", "reader": {
                "id": "orphan", "path": "/missing/overlay.png", "type": "QtImageReader"}},
            {"id": "C2", "file_id": "orphan", "reader": {
                "id": "orphan", "path": "/missing/overlay.png", "type": "QtImageReader"}},
        ], "effects": []}
        self.app.window = types.SimpleNamespace()
        with patch("classes.project_data.os.path.exists", return_value=False), \
                patch("classes.project_data.find_missing_file", return_value=("", False, True)) as prompt:
            store.check_if_paths_are_valid()
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(store._data["files"], [])
        self.assertEqual(store._data["clips"], [])

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

    def test_first_save_moves_runtime_recording_and_updates_readers(self):
        with patch("classes.project_data.shutil.copy2") as copy_recording:
            self._check_runtime_recording_relocation()
        copy_recording.assert_not_called()

    def test_first_save_copies_runtime_recording_across_filesystems(self):
        import errno
        with patch("classes.project_data.os.rename", side_effect=OSError(errno.EXDEV, "Cross-device move")):
            self._check_runtime_recording_relocation()

    def test_save_copies_locked_runtime_recording_and_updates_readers(self):
        self._check_runtime_recording_relocation(locked=True)

    def test_save_reuses_copied_recording_when_runtime_source_is_locked(self):
        self._check_runtime_recording_relocation(locked=True, target_exists=True)

    def test_failed_recording_copy_does_not_publish_partial_asset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.flac")
            target = os.path.join(tmpdir, "assets", "recording.flac")
            with open(source, "wb") as handle:
                handle.write(b"complete recording")

            def interrupted_copy(_source, destination):
                with open(destination, "wb") as handle:
                    handle.write(b"partial")
                raise OSError("Disk full")

            with patch("classes.project_data.shutil.copy2", side_effect=interrupted_copy):
                with self.assertRaises(OSError):
                    ProjectDataStore._copy_recording_asset(source, target)
            self.assertTrue(os.path.isfile(source))
            self.assertEqual(os.listdir(os.path.dirname(target)), [])

            ProjectDataStore._copy_recording_asset(source, target)
            with open(target, "rb") as handle:
                self.assertEqual(handle.read(), b"complete recording")

    def _check_runtime_recording_relocation(self, locked=False, target_exists=False):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_path = os.path.join(tmpdir, "user")
            recording_root = os.path.join(user_path, "recordings")
            os.makedirs(recording_root)
            recording = os.path.join(recording_root, "Webcam-1.mp4")
            with open(recording, "wb") as handle:
                handle.write(b"recording")

            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")
            expected = os.path.join(asset_path, "recordings", "Webcam-1.mp4")
            if target_exists:
                os.makedirs(os.path.dirname(expected))
                with open(expected, "wb") as handle:
                    handle.write(b"recording")
            runtime_paths = {
                name: os.path.join(tmpdir, name.lower())
                for name in (
                    "THUMBNAIL_PATH", "TITLE_PATH", "BLENDER_PATH",
                    "PROTOBUF_DATA_PATH", "CLIPBOARD_PATH",
                    "COMFYUI_OUTPUT_PATH", "PROXY_PATH",
                )
            }
            for runtime_path in runtime_paths.values():
                os.makedirs(runtime_path)
            store._data = {
                "files": [{"id": "F1", "path": recording}],
                "clips": [{
                    "id": "C1",
                    "file_id": "F1",
                    "reader": {"path": recording},
                    "effects": [],
                }],
            }

            with ExitStack() as stack:
                if locked:
                    original_remove = os.remove
                    original_rename = os.rename

                    def sharing_violation():
                        error = PermissionError("Recording is in use")
                        error.winerror = 32
                        return error

                    def remove(path, *args, **kwargs):
                        if path == recording:
                            raise sharing_violation()
                        return original_remove(path, *args, **kwargs)

                    def rename(source, destination, *args, **kwargs):
                        if source == recording:
                            raise sharing_violation()
                        return original_rename(source, destination, *args, **kwargs)

                    stack.enter_context(patch("classes.project_data.os.remove", side_effect=remove))
                    stack.enter_context(patch("classes.project_data.os.rename", side_effect=rename))
                stack.enter_context(patch("classes.project_data.info.USER_PATH", user_path))
                stack.enter_context(patch("classes.project_data.get_assets_path", return_value=asset_path))
                for name, runtime_path in runtime_paths.items():
                    stack.enter_context(
                        patch("classes.project_data.info.%s" % name, runtime_path)
                    )
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_path)

            self.assertEqual(os.path.exists(recording), locked)
            self.assertTrue(os.path.exists(expected))
            with open(expected, "rb") as handle:
                self.assertEqual(handle.read(), b"recording")
            self.assertEqual(store._data["files"][0]["path"], expected)
            self.assertEqual(store._data["clips"][0]["reader"]["path"], expected)

    def test_save_as_copies_project_recording_and_updates_readers(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_project = os.path.join(tmpdir, "old.osp")
            new_project = os.path.join(tmpdir, "new.osp")
            old_assets = os.path.join(tmpdir, "old_assets")
            new_assets = os.path.join(tmpdir, "new_assets")
            old_recording_root = os.path.join(old_assets, "recordings")
            os.makedirs(old_recording_root)
            recording = os.path.join(old_recording_root, "Screen-1.mp4")
            with open(recording, "wb") as handle:
                handle.write(b"recording")

            store._data = {
                "files": [{"id": "F1", "path": recording}],
                "clips": [{
                    "id": "C1",
                    "file_id": "F1",
                    "reader": {"path": recording},
                    "effects": [],
                }],
            }

            def assets_for(path, create_paths=True):
                return old_assets if path == old_project else new_assets

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.info.USER_PATH", os.path.join(tmpdir, "user")))
                stack.enter_context(patch("classes.project_data.get_assets_path", side_effect=assets_for))
                ProjectDataStore.move_temp_paths_to_project_folder(
                    store, new_project, previous_path=old_project)

            expected = os.path.join(new_assets, "recordings", "Screen-1.mp4")
            self.assertTrue(os.path.exists(recording))
            self.assertTrue(os.path.exists(expected))
            self.assertEqual(store._data["files"][0]["path"], expected)
            self.assertEqual(store._data["clips"][0]["reader"]["path"], expected)

    def test_move_temp_paths_to_project_folder_copies_effect_protobuf_from_stale_path(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            stale_proto_root = os.path.join(tmpdir, "old-runtime-protobuf")
            current_proto_root = os.path.join(tmpdir, "current-project-protobuf")
            thumb_root = os.path.join(tmpdir, "thumbs")
            title_root = os.path.join(tmpdir, "titles")
            blender_root = os.path.join(tmpdir, "blender")
            clipboard_root = os.path.join(tmpdir, "clipboard")
            comfy_root = os.path.join(tmpdir, "comfy")
            proxy_root = os.path.join(tmpdir, "optimized")
            for folder in [
                stale_proto_root, current_proto_root, thumb_root, title_root,
                blender_root, clipboard_root, comfy_root, proxy_root,
            ]:
                os.mkdir(folder)

            stale_proto = os.path.join(stale_proto_root, "E1.data")
            with open(stale_proto, "w", encoding="utf-8") as handle:
                handle.write("object-mask-data")

            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")
            store._data = {
                "files": [],
                "effects": [{"id": "T1", "protobuf_data_path": stale_proto}],
                "clips": [
                    {
                        "id": "C1",
                        "file_id": "",
                        "reader": {},
                        "effects": [{"id": "E1", "protobuf_data_path": stale_proto}],
                    },
                ],
            }

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.get_assets_path", lambda path, create_paths=True: asset_path))
                stack.enter_context(patch("classes.project_data.info.THUMBNAIL_PATH", thumb_root))
                stack.enter_context(patch("classes.project_data.info.TITLE_PATH", title_root))
                stack.enter_context(patch("classes.project_data.info.BLENDER_PATH", blender_root))
                stack.enter_context(patch("classes.project_data.info.PROTOBUF_DATA_PATH", current_proto_root))
                stack.enter_context(patch("classes.project_data.info.CLIPBOARD_PATH", clipboard_root))
                stack.enter_context(patch("classes.project_data.info.COMFYUI_OUTPUT_PATH", comfy_root))
                stack.enter_context(patch("classes.project_data.info.PROXY_PATH", proxy_root))
                ProjectDataStore.move_temp_paths_to_project_folder(store, project_path)

            expected_proto = os.path.join(asset_path, "protobuf_data", "E1.data")
            self.assertTrue(os.path.exists(expected_proto))
            self.assertEqual(store._data["effects"][0]["protobuf_data_path"], expected_proto)
            self.assertEqual(store._data["clips"][0]["effects"][0]["protobuf_data_path"], expected_proto)

    def test_save_updates_active_protobuf_path_to_project_assets(self):
        store = make_store()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "example.osp")
            asset_path = os.path.join(tmpdir, "example_assets")
            store._data = {"files": [], "effects": [], "clips": []}

            with ExitStack() as stack:
                stack.enter_context(patch("classes.project_data.get_assets_path", lambda path, create_paths=True: asset_path))
                stack.enter_context(patch("classes.project_data.info.PROTOBUF_DATA_PATH", os.path.join(tmpdir, "runtime-protobuf")))
                stack.enter_context(patch.object(store, "move_temp_paths_to_project_folder", lambda file_path, previous_path=None: None))
                stack.enter_context(patch.object(store, "write_to_file", lambda *args, **kwargs: None))
                stack.enter_context(patch.object(store, "add_to_recent_files", lambda file_path: None))
                ProjectDataStore.save(store, project_path)
                from classes import info
                self.assertEqual(info.PROTOBUF_DATA_PATH, os.path.join(asset_path, "protobuf_data"))
