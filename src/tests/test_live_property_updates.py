"""Regression coverage for avoiding redundant work during rich-property drags."""
import copy
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
        model, view, effect, app, item, value = self.make_editor()
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

    def test_overview_skips_effects_but_refreshes_clip_geometry(self):
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
