"""Keyframe panel lookup keeps ownership and paths while sharing traversal work."""
import json
import types
import unittest
from unittest.mock import patch

from windows.views.timeline_backend.qwidget import keyframe_panel


class CountingDict(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.visits = 0

    def items(self):
        self.visits += 1
        return super().items()


class KeyframePanelLookupTests(unittest.TestCase):
    def test_shared_scan_preserves_paths_precedence_and_fresh_data(self):
        points = [{"co": {"X": 1, "Y": 0.2}, "interpolation": 1},
                  {"co": {"X": 25, "Y": 0.8}, "interpolation": 0}]
        nested = CountingDict(brightness={"Points": points})
        source = CountingDict(alpha={"Points": points}, effects=[nested, {"brightness": {"Points": []}}],
                              color={"red": {"Points": points}},
                              wheels={"global": {"amount_keyframes": {"Points": points}}})
        props = {key: {"type": "float", "name": key, "points": 2}
                 for key in ("alpha", "brightness", "absent1", "absent2", "absent3", "absent4")}
        props["color"] = {"type": "color", "name": "Color", "points": 2}
        props["wheels"] = {"type": "colorgrade_wheels", "name": "Wheels", "points": 2}
        obj = types.SimpleNamespace(PropertiesJSON=lambda frame: json.dumps(props))
        timeline = types.SimpleNamespace(GetClip=lambda item_id: obj)
        clip = types.SimpleNamespace(id="clip", data=source)
        context = {"fps": 24, "clip_start": 0, "position": 2, "track": 5}
        helper = types.SimpleNamespace(
            fps_float=24, _panel_selected_keyframes={}, normalize_track_number=lambda n: n,
            _panel_selection_frames=lambda selection: set(),
            _panel_selection_contains=lambda *args, **kwargs: False,
        )
        with patch.object(keyframe_panel.Clip, "get", return_value=clip), \
             patch.object(keyframe_panel, "get_app", return_value=types.SimpleNamespace(_tr=lambda text: text)):
            result, _, available = keyframe_panel.KeyframePanelMixin._properties_for_item(
                helper, timeline, "clip", "clip", 1, context=context)
            # One traversal plus one index pass, regardless of absent properties.
            self.assertEqual(source.visits, 2)
            self.assertEqual(nested.visits, 2)
            by_key = {p["key"]: p for p in available}
            self.assertEqual(set(by_key), {"alpha", "brightness", "color", "wheels"})
            self.assertEqual(len(result), 4)
            self.assertEqual(by_key["brightness"]["point_paths"][0],
                             (("dict", "effects"), ("list", 0), ("dict", "brightness"),
                              ("dict", "Points"), ("list", 0)))
            for prop in available:
                self.assertIs(prop["source_meta"]["clip"], clip)
                self.assertEqual(prop["points"][1]["seconds"], 3)
                for path, point in zip(prop["point_paths"], prop["points"]):
                    raw = source
                    for _, key in path:
                        raw = raw[key]
                    self.assertEqual(raw["co"]["Y"], point["value"])
            # Metadata remains independently mutable for each property.
            by_key["alpha"]["source_meta"]["owner"] = "changed"
            self.assertEqual(by_key["brightness"]["source_meta"]["owner"], "clip")
            points.append({"co": {"X": 49, "Y": 1}, "interpolation": 1})
            updated, _, _ = keyframe_panel.KeyframePanelMixin._properties_for_item(
                helper, timeline, "clip", "clip", 1, context=context)
            self.assertTrue(all(len(p["points"]) == 3 for p in updated))




class ColorGradeKeyframeActionsTests(unittest.TestCase):
    def test_grouped_wheel_and_curve_icons_target_only_their_points(self):
        from copy import deepcopy
        from unittest.mock import Mock
        from windows.views.timeline_backend.qwidget.keyframe import KeyframeMixin

        class Helper(KeyframeMixin, keyframe_panel.KeyframePanelMixin):
            pass

        helper = Helper()
        helper.fps_float = 24
        helper.normalize_track_number = lambda n: n
        helper._panel_selected_keyframes = {}
        helper.geometry = types.SimpleNamespace(mark_dirty=Mock())
        helper.update = Mock()
        helper._update_track_panel_properties = Mock()
        helper._clear_panel_selection = Mock()
        helper.win = types.SimpleNamespace(timeline=types.SimpleNamespace(update_clip_data=Mock()))
        points = [{"co": {"X": frame, "Y": 0.5}, "interpolation": 1} for frame in range(1, 16)]
        effect_data = {"id": "grade", "wheels": {"global": {
            "color_keyframes": {c: {"Points": deepcopy(points)} for c in ("red", "green", "blue", "alpha")},
            "amount_keyframes": {"Points": deepcopy(points)}}},
            "curve": {"nodes": [{"x": {"Points": deepcopy(points)}, "y": {"Points": deepcopy(points)}}, {"x": 1.0, "y": 1.0}]}}
        clip = types.SimpleNamespace(id="clip", data={"id": "clip", "effects": [effect_data],
                                                     "alpha": {"Points": deepcopy(points)}})
        effect = types.SimpleNamespace(id="grade", data=effect_data)
        props = {"wheels": {"type": "colorgrade_wheels"}, "curve": {"type": "colorgrade_curve"}}
        native = types.SimpleNamespace(GetClipEffect=lambda _: types.SimpleNamespace(
            PropertiesJSON=lambda _: json.dumps(props)))
        ctx = {"fps": 24, "clip_start": 0, "position": 0, "track": 5,
               "item_type": "effect", "item_id": "grade", "clip_id": "clip"}
        with patch.object(keyframe_panel.Clip, "get", return_value=clip), \
             patch.object(keyframe_panel.Effect, "get", return_value=effect), \
             patch.object(keyframe_panel, "get_app", return_value=types.SimpleNamespace(_tr=lambda s: s)):
            rows, _, _ = helper._properties_for_item(native, "grade", "effect", 1, context=ctx)
            helper._panel_properties = {5: {"context": ctx, "properties": rows}}
            by_key = {row["key"]: row for row in rows}
            self.assertEqual(len(by_key["wheels"]["points"][1]["paths"]), 5)
            self.assertEqual(len(by_key["curve"]["points"][1]["paths"]), 2)
            helper._panel_selected_keyframes = {5: {"wheels": set(range(2, 14))}}
            targets = helper._panel_selected_keyframe_targets()
            self.assertEqual(len(targets), 1)
            self.assertEqual(len(targets[0]["paths"]), 60)
            helper._apply_keyframe_interpolation(2, None, None, targets)
            interpolated = helper.win.timeline.update_clip_data.call_args.args[0]
            self.assertEqual(interpolated["effects"][0]["wheels"]["global"]["amount_keyframes"]["Points"][1]["interpolation"], 2)
            self.assertEqual(interpolated["effects"][0]["wheels"]["global"]["amount_keyframes"]["Points"][0]["interpolation"], 1)
            # Right-clicking a grouped icon exposes the existing keyframe menu,
            # both with a multi-selection and with no previous selection.
            from windows.views.timeline_backend.qwidget import keyframe as keyframe_module
            helper.mapToGlobal = lambda pos: pos
            panel_info = {"point": by_key["wheels"]["points"][1],
                          "property": by_key["wheels"], "context": ctx}
            with patch.object(keyframe_module, "get_app", return_value=types.SimpleNamespace(_tr=lambda s: s)), \
                 patch.object(keyframe_module, "QPixmap"), patch.object(keyframe_module, "QIcon"), \
                 patch.object(keyframe_module, "StyledContextMenu") as menu, \
                 patch.object(keyframe_module, "populate_keyframe_context_menu") as populate, \
                 patch.object(helper, "_apply_keyframe_remove") as remove:
                self.assertTrue(helper.show_keyframe_context_menu(0, panel_info=panel_info))
                menu.return_value.exec_.assert_called_once()
                populate.call_args.kwargs["remove_callback"]()
                self.assertEqual(len(remove.call_args.args[1][0]["paths"]), 60)
                helper._panel_selected_keyframes = {}
                self.assertTrue(helper.show_keyframe_context_menu(0, panel_info=panel_info))
                populate.call_args.kwargs["remove_callback"]()
                self.assertEqual(len(remove.call_args.args[1][0]["paths"]), 5)
            helper._panel_selected_keyframes = {5: {"wheels": set(range(2, 14))}}
            original = deepcopy(clip.data)
            self.assertTrue(helper.delete_selected_keyframes())
            self.assertEqual(clip.data, original)  # Save must capture the unmodified undo state.
            updated = helper.win.timeline.update_clip_data.call_args.args[0]
            self.assertEqual(updated["effects"][0]["id"], "grade")
            self.assertEqual(updated["alpha"]["Points"], points)
            self.assertEqual(updated["effects"][0]["curve"], effect_data["curve"])
            wheel = updated["effects"][0]["wheels"]["global"]
            for channel in list(wheel["color_keyframes"].values()) + [wheel["amount_keyframes"]]:
                self.assertEqual([p["co"]["X"] for p in channel["Points"]], [1, 14, 15])

    def test_unresolved_selection_consumes_delete(self):
        from unittest.mock import Mock
        from windows.views.timeline_backend.qwidget.keyframe import KeyframeMixin
        helper = types.SimpleNamespace(
            win=types.SimpleNamespace(timeline=object()),
            _panel_selected_keyframes={5: {"wheels": {25}}},
            _panel_selected_keyframe_targets=lambda: [],
            _delete_keyframe_marker_target=Mock())
        self.assertTrue(KeyframeMixin.delete_selected_keyframes(helper))
        helper._delete_keyframe_marker_target.assert_not_called()
