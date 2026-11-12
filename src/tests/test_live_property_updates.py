"""Regression coverage for avoiding redundant work during rich-property drags."""
import copy
import json
import types
import unittest
from unittest.mock import Mock, patch

from qt_api import QApplication, QCoreApplication, QStandardItem, QStandardItemModel, Qt, QWidget

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

from classes.updates import UpdateAction
from windows.models import properties_model
from windows.views import properties_tableview, zoom_slider
from windows.color_grade_editor import default_wheels_data, default_curve_data


class LivePropertyUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_transform_model(self):
        import openshot
        model = properties_model.PropertiesModel.__new__(properties_model.PropertiesModel)
        def prop(name, value, kind="float"):
            return dict(name=name, value=value, type=kind, memo="", readonly=False, keyframe=False,
                        points=1, interpolation=openshot.LINEAR, closest_point_x=1, previous_point_x=1,
                        min=0, max=10, choices=[])
        raw = {"scale_x": prop("Scale X", 1.0), "alpha": prop("Alpha", 1.0), "layer": prop("Track", 1, "int")}
        native = types.SimpleNamespace(Id=lambda: "clip", PropertiesJSON=lambda frame: json.dumps(raw))
        source = types.SimpleNamespace(data={})
        preview = types.SimpleNamespace(mouse_pressed=True, _live_transform_clips={"clip": source})
        action = UpdateAction("update", ["clips", {"id": "clip"}],
                              {"scale_x": {"Point": {"co": {"X": 20, "Y": 1.5}}}})
        context = types.SimpleNamespace(_tr=lambda text: text,
            project={"layers": [{"number": 1, "label": "Original track"}]},
            updates=types.SimpleNamespace(last_action=action),
            window=types.SimpleNamespace(videoPreview=preview, actionAutoKeyframes=None,
                CaptionTextLoaded=Mock(), txtPropertyFilter=types.SimpleNamespace(text=lambda: "")))
        for key, value in dict(selected=[(native, "clip")], selected_ids=[], frame_number=20,
                new_item=True, items={}, ignore_update_signal=False, previous_filter=None,
                filter_base_properties=[], _trim_preview_mode=False).items():
            setattr(model, key, value)
        model.model = QStandardItemModel()
        model.parent = QWidget()
        model.parent.show()
        def cleanup():
            timer = getattr(model, "_live_transform_timer", None)
            if timer is not None:
                timer.stop()
            model.parent.deleteLater()
        self.addCleanup(cleanup)
        return model, raw, context

    def test_equal_property_metadata_does_not_notify_the_view(self):
        model, raw, app = self.make_transform_model()
        with patch.object(properties_model, "get_app", new=lambda: app):
            model.update_model(live_transform=True)
            before = model.items["scale_x"]["row"]
            # Initialize the default background/decoration roles on existing rows.
            model.update_model(live_transform=True)
            changes = []
            model.model.dataChanged.connect(lambda *args: changes.append(args))
            model.update_model(live_transform=True)
            self.assertEqual(changes, [])
            self.assertIs(model.items["scale_x"]["row"][0], before[0])
            raw["scale_x"].update(value=1.5, keyframe=True, points=20)
            model.update_model(live_transform=True)
            self.assertEqual(before[1].text(), "1.500")
            self.assertTrue(changes)
            self.assertEqual(before[0].data()[1]["points"], 20)
            self.assertEqual(before[0].data()[1]["value"], 1.5)

    def test_equal_metadata_still_refreshes_context_and_repairs_external_edits(self):
        model, raw, app = self.make_transform_model()
        with patch.object(properties_model, "get_app", new=lambda: app):
            model.update_model(live_transform=True)
            model.update_model(live_transform=True)
            label = model.items["scale_x"]["row"][0]
            metadata = label.data()
            metadata[1]["min"] = -999
            label.setData(metadata)
            app.project["layers"][0]["label"] = "Renamed track"
            model.update_model(live_transform=True)
            self.assertEqual(label.data()[1]["min"], raw["scale_x"]["min"])
            self.assertEqual(model.items["layer"]["row"][1].text(), "Renamed track")

    def test_transform_properties_refresh_once_per_event_cycle_and_stop_on_release(self):
        model, raw, app = self.make_transform_model()
        source = app.window.videoPreview._live_transform_clips["clip"]
        with patch.object(properties_model, "get_app", new=lambda: app), \
             patch.object(properties_model.Clip, "get", new=lambda **kwargs: source):
            model.update_model(live_transform=True)
            with patch.object(model, "update_model", wraps=model.update_model) as refresh:
                raw["scale_x"]["value"] = 1.5
                for _ in range(100):
                    model.changed(app.updates.last_action)
                refresh.assert_not_called()
                self.app.processEvents()
                refresh.assert_called_once_with("", live_transform=True)
                self.assertEqual(model.items["scale_x"]["row"][1].text(), "1.500")
                model.changed(app.updates.last_action)
                app.window.videoPreview.mouse_pressed = False
                # A normal committed refresh cancels any queued live callback.
                app.updates.last_action = UpdateAction("update", ["clips", {"id": "clip"}], {})
                model.update_model()
                refresh.reset_mock()
                self.app.processEvents()
                refresh.assert_not_called()
                self.assertFalse(model._live_transform_timer.isActive())

    def test_hidden_properties_do_not_schedule_live_work(self):
        model, raw, app = self.make_transform_model()
        model.parent.hide()
        model.changed(app.updates.last_action)
        self.assertIsNone(getattr(model, "_live_transform_timer", None))

    def test_live_auto_keyframes_off_indexes_points_once_and_keeps_correct_target(self):
        model, raw, app = self.make_transform_model()
        app.window.actionAutoKeyframes = types.SimpleNamespace(isChecked=lambda: False)
        class Points(list):
            visits = 0
            def __iter__(self):
                self.visits += 1
                return super().__iter__()
        points = Points([{ "co": {"X": 20, "Y": 2.0}}, {"co": {"X": 1, "Y": 0.0}},
                         {"co": {"X": 10, "Y": 1.0}}])
        source = app.window.videoPreview._live_transform_clips["clip"]
        source.data["scale_x"] = {"Points": points}
        raw["scale_x"].update(points=3, closest_point_x=20, previous_point_x=10)
        with patch.object(properties_model, "get_app", new=lambda: app):
            model.frame_number = 15
            for _ in range(20):
                model.update_model(live_transform=True)
            self.assertEqual(points.visits, 1)
            item = model.items["scale_x"]["row"][1]
            self.assertEqual(item.text(), "1.000")
            self.assertIn("10", item.toolTip())
            points[2]["co"]["Y"] = 3.0
            model.update_model(live_transform=True)
            self.assertEqual(item.text(), "3.000")
            self.assertEqual(points.visits, 1)
            model.frame_number = 30
            model.update_model(live_transform=True)
            self.assertEqual(item.text(), "2.000")
            model.frame_number = 0
            raw["scale_x"].update(closest_point_x=1, previous_point_x=1)
            model.update_model(live_transform=True)
            self.assertEqual(item.text(), "0.000")

    def test_playback_uses_project_curves_instead_of_serializing_native_objects(self):
        for kind, query in (("clip", properties_model.Clip), ("effect", properties_model.Effect),
                            ("transition", properties_model.Transition)):
            with self.subTest(kind=kind):
                model, raw, app = self.make_transform_model()
                app.window.videoPreview.mouse_pressed = False
                app.window.actionAutoKeyframes = types.SimpleNamespace(isChecked=lambda: False)
                source = app.window.videoPreview._live_transform_clips["clip"]
                source.data["scale_x"] = {"Points": [{"co": {"X": 1, "Y": 1.5}}]}
                native = model.selected[0][0]
                native.Json = Mock(side_effect=AssertionError("Do not serialize the native object for each frame"))
                model.selected = [(native, kind)]
                with patch.object(properties_model, "get_app", new=lambda: app), \
                     patch.object(query, "get", new=lambda **kwargs: source):
                    model.update_model()
                    self.assertEqual(model.items["scale_x"]["row"][1].text(), "1.500")
                    source.data["scale_x"]["Points"] = [{"co": {"X": 1, "Y": 2.5}}]
                    model.update_model()
                    self.assertEqual(model.items["scale_x"]["row"][1].text(), "2.500")
                    native.Json.assert_not_called()

    def test_temporary_native_preview_keeps_json_fallback(self):
        model, raw, app = self.make_transform_model()
        app.window.videoPreview.mouse_pressed = False
        app.window.actionAutoKeyframes = types.SimpleNamespace(isChecked=lambda: False)
        native = model.selected[0][0]
        native.Json = Mock(return_value=json.dumps({"scale_x": {"Points": [{"co": {"X": 1, "Y": 2.0}}]}}))
        with patch.object(properties_model, "get_app", new=lambda: app), \
             patch.object(properties_model.Clip, "get", return_value=None):
            model.update_model()
            self.assertEqual(model.items["scale_x"]["row"][1].text(), "2.000")
            native.Json.assert_called_once_with()

    def test_playback_follows_frames_without_resetting_active_editors_or_menus(self):
        from qt_api import QAbstractItemView
        view = types.SimpleNamespace(isVisible=lambda: True, mouse_pressed=False, transaction_id=None,
            update_in_progress=False, menu=None, state=lambda: 0,
            clip_properties_model=types.SimpleNamespace(update_frame=Mock()))
        properties_tableview.PropertiesTableView.playback_frame_changed(view, 30)
        view.clip_properties_model.update_frame.assert_called_once_with(30)
        view.clip_properties_model.update_frame.reset_mock()
        for attr, value in (("mouse_pressed", True), ("transaction_id", "wheel-drag"),
                            ("update_in_progress", True), ("isVisible", lambda: False),
                            ("state", lambda: QAbstractItemView.State.EditingState)):
            old = getattr(view, attr)
            setattr(view, attr, value)
            properties_tableview.PropertiesTableView.playback_frame_changed(view, 31)
            setattr(view, attr, old)
        view.menu = QWidget()
        view.menu.show()
        with patch.object(properties_tableview, "isdeleted", return_value=False):
            properties_tableview.PropertiesTableView.playback_frame_changed(view, 32)
        view.menu.hide()
        view.menu.deleteLater()
        view.menu = None
        view.clip_properties_model.update_frame.assert_not_called()
        properties_tableview.PropertiesTableView.playback_frame_changed(view, 33)
        view.clip_properties_model.update_frame.assert_called_once_with(33)

    def make_editor(self, kind="colorgrade_wheels"):
        key = "wheels" if kind == "colorgrade_wheels" else "curve_all"
        value = default_wheels_data() if key == "wheels" else default_curve_data()
        model = properties_model.PropertiesModel.__new__(properties_model.PropertiesModel)
        model.ignore_update_signal = False
        model.frame_number = 20
        model.model = QStandardItemModel()
        label, item = QStandardItem("Color"), QStandardItem("Color")
        label.setData((key, {"type": kind, "closest_point_x": 1, "previous_point_x": 1,
                             "object_id": None, "wheels" if key == "wheels" else "curve": copy.deepcopy(value)}))
        item.setData([("effect", "effect")])
        model.model.appendRow([label, item])
        model.parent = Mock()
        model.parent.currentIndex.return_value = model.model.index(0, 0)
        model.update_model = Mock()
        model._refresh_selected_effect_filters = Mock()
        effect = types.SimpleNamespace(data={key: copy.deepcopy(value)})
        effect.save = lambda: model.changed(UpdateAction("update", ["clips", {"id": "clip"}, "effects", {"id": "effect"}], effect.data))
        app = types.SimpleNamespace(_tr=lambda text: text, updates=types.SimpleNamespace(ignore_history=False),
                                    window=types.SimpleNamespace(refreshFrameSignal=Mock(), txtPropertyFilter=Mock()))
        view = types.SimpleNamespace(clip_properties_model=model,
                                     live_property_session={"item": item, "property_type": kind, "property_key": key},
                                     viewport=Mock(return_value=Mock()))
        for name in ("_update_live_property_preview", "_update_property_preview", "_update_color_grade_preview_meta"):
            setattr(view, name, types.MethodType(getattr(properties_tableview.PropertiesTableView, name), view))
        return model, view, effect, app, item, value

    def test_wheel_preview_stays_live_without_reloading_model(self):
        model, view, effect, app, _item, value = self.make_editor()
        value["global"]["amount_keyframes"]["Points"][0]["co"]["Y"] = 0.8
        with patch.object(properties_model, "get_app", return_value=app), \
             patch.object(properties_tableview, "get_app", return_value=app), \
             patch.object(properties_model.Effect, "get", return_value=effect):
            properties_tableview.PropertiesTableView.preview_live_property_value(view, value)
            model.update_model.assert_not_called()
            self.assertEqual(effect.data["wheels"], value)
            metadata = model.model.item(0, 0).data()[1]
            self.assertEqual(metadata["preview_wheels"]["global"]["amount"], 0.8)
            self.assertEqual(metadata["preview_frame"], 20)
            view.viewport().update.assert_called_once()
            app.window.refreshFrameSignal.emit.assert_called_once()
            # Completion (and later undo/redo/external saves) must refresh normally.
            effect.save()
            model.update_model.assert_called_once()

    def test_curve_preview_also_avoids_model_reload(self):
        model, view, effect, app, item, value = self.make_editor("colorgrade_curve")
        view._resolve_live_property_item = lambda *args: item
        with patch.object(properties_model, "get_app", return_value=app), \
             patch.object(properties_tableview, "get_app", return_value=app), \
             patch.object(properties_model.Effect, "get", return_value=effect):
            properties_tableview.PropertiesTableView.preview_curve_property_value(view, item, "curve_all", value)
        model.update_model.assert_not_called()
        self.assertEqual(model.model.item(0, 0).data()[1]["preview_frame"], 20)
        view.viewport().update.assert_called_once()

    def test_suppression_is_scoped_and_does_not_hide_other_notifications(self):
        model, view, effect, app, item, value = self.make_editor()
        def save():
            model.changed(UpdateAction("update", ["effects"], effect.data))
            model.update_model.assert_not_called()
            # Equal data in a separate action must not be mistaken for this save.
            model.changed(UpdateAction("update", ["effects"], copy.deepcopy(effect.data)))
            model.update_model.assert_called_once()
            raise RuntimeError("save failed")
        effect.save = save
        with patch.object(properties_model, "get_app", return_value=app), \
             patch.object(properties_model.Effect, "get", return_value=effect):
            with self.assertRaisesRegex(RuntimeError, "save failed"):
                model.value_updated(item, value=value, refresh_model=False)
            self.assertIsNone(model._live_preview_values)
            model.changed(UpdateAction("update", ["effects"], effect.data))
        self.assertEqual(model.update_model.call_count, 2)

    def test_trim_updates_save_consistent_start_end_and_duration(self):
        for key, value, expected in (("end", .08, (0., .08, .08)),
                                     ("start", .04, (.04, .12, .08))):
            with self.subTest(property=key):
                model = properties_model.PropertiesModel.__new__(properties_model.PropertiesModel)
                model.ignore_update_signal = False
                model.frame_number = 1
                model.model = QStandardItemModel()
                label, item = QStandardItem(key), QStandardItem(str(value))
                label.setData((key, {"type": "float", "closest_point_x": 1,
                                    "previous_point_x": 1, "object_id": None}))
                item.setData([("clip", "clip")])
                model.model.appendRow([label, item])
                model.parent = Mock()
                model.parent.currentIndex.return_value.row.return_value = -1
                saved = dict(start=0., end=.12, duration=.12, position=0.,
                             reader={"has_single_image": True})
                clip = types.SimpleNamespace(id="clip", data=copy.deepcopy(saved))
                clip.save = lambda: saved.update(copy.deepcopy(clip.data))
                app = types.SimpleNamespace(_tr=lambda text: text, project={"fps": {"num": 25, "den": 1}},
                                            window=types.SimpleNamespace(refreshFrameSignal=Mock()))
                with patch.object(properties_model, "get_app", return_value=app), \
                        patch.object(properties_model.Clip, "get", return_value=clip):
                    model.value_updated(item, value=value)
                for field, result in zip(("start", "end", "duration"), expected):
                    self.assertAlmostEqual(saved[field], result)

    def test_transition_properties_trim_fits_fade_and_preserves_custom_keyframes(self):
        for kind in ("default", "custom", "animated_mask"):
            for key, value, bounds in (("end", 5., (1, 126)), ("end", 15., (1, 376)),
                                       ("start", 2., (51, 251))):
                with self.subTest(kind=kind, property=key, value=value):
                    model = properties_model.PropertiesModel.__new__(properties_model.PropertiesModel)
                    model.ignore_update_signal = False
                    model.frame_number = 1
                    model.model = QStandardItemModel()
                    label, item = QStandardItem(key), QStandardItem(str(value))
                    label.setData((key, {"type": "float", "closest_point_x": 1,
                                        "previous_point_x": 1, "object_id": None}))
                    item.setData([("transition", "transition")])
                    model.model.appendRow([label, item])
                    model.parent = Mock()
                    model.parent.currentIndex.return_value.row.return_value = -1
                    points = [{"co": {"X": 1, "Y": 1.}, "interpolation": 0},
                              {"co": {"X": 251, "Y": -1.}, "interpolation": 0}]
                    if kind == "custom":
                        points.insert(1, {"co": {"X": 101, "Y": .5}, "interpolation": 1})
                    saved = dict(start=0., end=10., duration=10., position=0.,
                                 reader={"has_single_image": kind != "animated_mask"},
                                 brightness={"Points": points}, contrast={"Points": [{"co": {"X": 1, "Y": 3.}}]})
                    original = copy.deepcopy(saved)
                    transition = types.SimpleNamespace(id="transition", data=copy.deepcopy(saved))
                    transition.save = lambda: saved.update(copy.deepcopy(transition.data))
                    app = types.SimpleNamespace(_tr=lambda text: text, project={"fps": {"num": 25, "den": 1}},
                                                window=types.SimpleNamespace(refreshFrameSignal=Mock()))
                    with patch.object(properties_model, "get_app", return_value=app), \
                            patch.object(properties_model.Transition, "get", return_value=transition):
                        model.value_updated(item, value=value)
                    self.assertEqual(saved[key], value)
                    self.assertEqual(saved["duration"], saved["end"] - saved["start"])
                    expected = original["brightness"]
                    if kind == "default":
                        for point, frame in zip(expected["Points"], bounds):
                            point["co"]["X"] = frame
                    self.assertEqual(saved["brightness"], expected)
                    self.assertEqual(saved["contrast"], original["contrast"])

    def test_overview_skips_effects_and_point_edits_but_refreshes_clip_geometry(self):
        widget = QWidget()
        widget.ignore_updates = False
        widget.clip_rects = ["existing"]
        widget.clip_rects_selected = []
        widget.marker_rects = []
        widget.snap_clip_starts = [2.0, 5.0]
        widget.snap_clip_ends = [2.0, 5.0]
        widget.update = Mock()
        app = types.SimpleNamespace(window=types.SimpleNamespace())
        with patch.object(zoom_slider, "get_app", return_value=app), \
             patch.object(zoom_slider.Track, "filter", return_value=[]) as tracks:
            for key in (["effects", {"id": "effect"}], ["clips", {"id": "clip"}, "effects", {"id": "effect"}]):
                zoom_slider.ZoomSlider.changed(widget, UpdateAction("update", key, {}))
            zoom_slider.ZoomSlider.changed(widget, UpdateAction("update", ["clips", {"id": "clip"}],
                {"scale_x": {"Point": {"co": {"X": 100, "Y": 1.5}}}}))
            tracks.assert_not_called()
            self.assertEqual(widget.clip_rects, ["existing"])
            self.assertEqual(widget.snap_clip_starts, [2.0, 5.0])
            self.assertEqual(widget.snap_clip_ends, [2.0, 5.0])
            widget.update.assert_not_called()
            zoom_slider.ZoomSlider.changed(widget, UpdateAction("update", ["clips", {"id": "clip"}], {"position": 2}))
            tracks.assert_called_once()
            widget.update.assert_called_once()
            self.assertEqual(widget.clip_rects, [])
            self.assertEqual(widget.snap_clip_starts, [])
            self.assertEqual(widget.snap_clip_ends, [])
            # Structural changes retain normal refresh/selection handling.
            for operation in ("insert", "delete"):
                zoom_slider.ZoomSlider.changed(widget, UpdateAction(operation, ["effects"], {}))
            self.assertEqual(widget.update.call_count, 3)

    def test_action_copy_can_omit_history_without_aliasing_or_changing_original(self):
        action = UpdateAction("update", ["clips", {"id": "clip"}],
                              {"location_x": {"Points": [{"co": {"X": 1, "Y": 0.5}}]}},
                              {"location_x": {"Points": [{"co": {"X": 1, "Y": 0.0}}]}}, "transaction")
        original = action.json()
        full = action.copy()
        light = action.copy(include_old_values=False)
        self.assertEqual(full.json(), original)
        self.assertEqual(light.old_values, {})
        self.assertEqual(light.transaction, action.transaction)
        light.key[1]["id"] = "different"
        light.values["location_x"]["Points"][0]["co"]["Y"] = 99
        full.old_values["location_x"]["Points"].clear()
        self.assertEqual(action.json(), original)
        # Prove omitted history is never serialized, even if it cannot be serialized.
        action.old_values = object()
        self.assertEqual(action.copy(include_old_values=False).old_values, {})


if __name__ == "__main__":
    unittest.main()
