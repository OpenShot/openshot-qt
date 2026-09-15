"""Regressions for the small fixes in the September 10 Sentry review."""

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

from qt_api import QPointF, QComboBox
from classes.query import Clip
from tests.qt_test_app import get_or_create_app
from tests.test_project_data import DummyApp, ensure_app_state, make_store


class SentryMiscTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(DummyApp)
        ensure_app_state(cls.app)
        # Other GUI tests can leave a partial metrics stub in sys.modules.
        # Export selection does not need telemetry; isolate that dependency.
        metrics = types.ModuleType("classes.metrics")
        metrics.track_metric_screen = Mock()
        metrics.track_metric_error = Mock()
        with patch.dict(sys.modules, {"classes.metrics": metrics}):
            cls.export = importlib.import_module("windows.export")
        cls.timeline = importlib.import_module("windows.views.timeline")
        cls.properties = importlib.import_module("windows.views.properties_tableview")

    def test_asset_relocation_keeps_clips_without_file_ids(self):
        with tempfile.TemporaryDirectory() as root:
            title_root = os.path.join(root, "title")
            os.mkdir(title_root)
            source = os.path.join(title_root, "title.svg")
            with open(source, "w") as handle:
                handle.write("title contents")
            protobuf = os.path.join(root, "tracking.data")
            with open(protobuf, "w") as handle:
                handle.write("tracking contents")
            generated = {"id": "generated", "image": "original.png", "effects": [
                {"id": "E1", "protobuf_data_path": protobuf}]}
            legacy = {"id": "legacy", "reader": {"id": "F1", "path": source}}
            normal = {"id": "normal", "file_id": "F1", "reader": {"path": source}}
            store = make_store()
            store._data = {"files": [{"id": "F1", "path": source}],
                           "clips": [generated, legacy, normal]}
            sync_assets = store._sync_asset_root

            def sync_test_assets(source_path, target_path, **kwargs):
                if source_path == title_root:
                    return sync_assets(source_path, target_path, **kwargs)

            with patch.object(store, "_sync_asset_root", side_effect=sync_test_assets), \
                    patch("classes.project_data.info.TITLE_PATH", title_root), \
                    patch("classes.project_data.log.error") as error:
                store.move_temp_paths_to_project_folder(os.path.join(root, "project.osp"))
            error.assert_not_called()
            self.assertEqual(generated["image"], "original.png")
            assets = os.path.join(root, "project_assets")
            self.assertEqual(generated["effects"][0]["protobuf_data_path"],
                             os.path.join(assets, "protobuf_data", "tracking.data"))
            for clip in (legacy, normal):
                self.assertEqual(clip["reader"]["path"], os.path.join(assets, "title", "title.svg"))
                self.assertEqual(clip["image"], os.path.join(assets, "thumbnail", "F1.png"))
            with open(os.path.join(assets, "title", "title.svg")) as handle:
                self.assertEqual(handle.read(), "title contents")

    def test_clip_title_without_media_path(self):
        clip = Clip()
        for reader in ({}, {"path": None}, {"path": ""}):
            with self.subTest(reader=reader):
                clip.data = {"reader": reader, "title": "Generated clip"}
                self.assertEqual(clip.title(), "Generated clip")
                del clip.data["title"]
                self.assertEqual(clip.title(), "")
        clip.data = {"reader": {"path": os.path.join("media", "video.mp4")}}
        self.assertEqual(clip.title(), "video.mp4")
        clip.data["file_id"] = "F1"
        with patch("classes.query.File.get", return_value=types.SimpleNamespace(data={"name": "Renamed"})):
            self.assertEqual(clip.title(), "Renamed")

    def test_export_combo_clear_preserves_settings_and_valid_selection_loads(self):
        combo = QComboBox()
        helper = MagicMock()
        profile = Mock()
        with patch.object(self.export.openshot, "Profile", return_value=profile) as constructor, \
                patch.object(self.export, "get_app", return_value=types.SimpleNamespace(_tr=lambda s: s)):
            combo.currentIndexChanged.connect(
                lambda index: self.export.Export.cboProfile_index_changed(helper, combo, index))
            combo.addItem("HD", "/profiles/hd")
            constructor.assert_called_once_with("/profiles/hd")
            helper.txtWidth.setValue.assert_called_once_with(profile.info.width)
            helper.reset_mock()
            constructor.reset_mock()
            combo.clear()
            combo.addItem("Empty", None)
            constructor.assert_not_called()
            self.assertEqual(helper.mock_calls, [])

    def test_clip_menu_before_preview_frame_and_during_seek(self):
        for frame, displayed_frame, seconds in ((None, 0, 0.0), (None, 61, 2.0),
                                                 (1, 61, 0.0), (61, 1, 2.0)):
            with self.subTest(frame=frame, displayed_frame=displayed_frame):
                helper = MagicMock()
                helper.current_frame = displayed_frame
                helper.window.selected_clips = ["C1"]
                helper.window.selected_transitions = []
                helper.window.preview_thread.current_frame = frame
                clip = Clip()
                clip.data = {"reader": {}, "start": 0, "end": 10, "position": 0}
                app = MagicMock()
                app._tr = lambda s: s
                app.project.get.return_value = {"num": 30, "den": 1}
                menu = MagicMock()
                with patch.object(self.timeline, "get_app", return_value=app), \
                        patch.object(self.timeline.Clip, "get", return_value=clip), \
                        patch.object(self.timeline.ClipboardManager, "from_mime", return_value=None), \
                        patch.object(self.timeline, "StyledContextMenu", return_value=menu):
                    self.timeline.TimelineView.ShowClipMenu(helper, "C1")
                menu.show_at.assert_called_once()
                callbacks = [call[0][0] for call in menu.addAction.return_value.triggered.connect.call_args_list]
                slices = [callback for callback in callbacks if getattr(callback, "func", None) is helper.Slice_Triggered]
                self.assertTrue(slices)
                self.assertTrue(all(callback.args[3] == seconds for callback in slices))

    def test_tracked_object_menus_allow_empty_results_and_keep_valid_choices(self):
        payload = json.dumps({"visible_objects_id": ["E1-0"], "visible_objects_index": [0],
                              "visible_class_names": ["Person"]})
        for key in ("parentObjectId", "selected_object_index", "class_filter"):
            for raw in ("", payload):
                with self.subTest(key=key, raw=raw):
                    helper = MagicMock()
                    helper.menu_reset = True
                    helper.clip_properties_model.frame_number = 1
                    helper.files_model.rowCount.return_value = 0
                    prop = (key, {"readonly": False, "name": "Objects", "type": "int",
                                  "points": 0, "choices": []})
                    label = Mock()
                    label.data.return_value = prop
                    value = Mock()
                    value.data.return_value = [("C1", "clip")]
                    index = helper.indexAt.return_value
                    index.row.return_value = 0
                    index.model.return_value.item.side_effect = lambda row, column: label if column == 0 else value
                    other = types.SimpleNamespace(id="C2", data={"title": "Other", "effects": [
                        {"id": "E1", "has_tracked_object": True}]})
                    app = MagicMock()
                    app._tr = lambda s: s
                    app.window.timeline_sync.timeline.GetClipEffect.return_value.GetVisibleObjects.return_value = raw
                    with patch.object(self.properties, "get_app", return_value=app), \
                            patch.object(self.properties.Clip, "filter", return_value=[other]), \
                            patch.object(self.properties, "_event_posf", return_value=QPointF()), \
                            patch.object(self.properties, "StyledContextMenu", return_value=MagicMock()):
                        self.properties.PropertiesTableView.contextMenuEvent(helper, Mock())
                    helper.build_menu.assert_called_once()
                    serialized = str(helper.choices)
                    if raw:
                        self.assertIn("E1-0" if key == "parentObjectId" else "Person", serialized)
                    else:
                        self.assertNotIn("E1-0", serialized)
                        self.assertNotIn("Person", serialized)
                    if key == "parentObjectId":
                        self.assertIn("Other", serialized)


if __name__ == "__main__":
    unittest.main()
