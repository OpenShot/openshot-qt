"""
 @file
 @brief Unit tests for ColorGrade editor helpers
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
import os
import sys
import unittest

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.color_grade_editor import (  # noqa: E402
    _set_color_value,
    _set_keyframe_value,
    _default_curve_node,
    WheelRow,
    colorgrade_keyframe_frames,
    curve_enabled_at_frame,
    curve_nodes_at_frame,
    default_curve_data,
    default_wheels_data,
    is_achromatic_color,
    normalize_curve_data,
    normalize_wheels_data,
    puck_display_color,
    wheel_snapshot,
    wheels_enabled_at_frame,
    wheels_snapshot,
)
from windows.models.properties_model import PropertiesModel  # noqa: E402
from qt_api import QColor  # noqa: E402
import openshot  # noqa: E402


class ColorGradeEditorTests(unittest.TestCase):
    def test_normalized_wheels_own_points_and_handles(self):
        source = default_wheels_data()
        point = source["global"]["color_keyframes"]["red"]["Points"][0]
        point["handle_left"] = {"X": 0.25, "Y": 0.75}
        original = copy.deepcopy(source)
        result = normalize_wheels_data(source)
        result_point = result["global"]["color_keyframes"]["red"]["Points"][0]
        result_point["co"]["Y"] = 42
        result_point["handle_left"]["X"] = 0.9
        result["enabled_keyframes"]["Points"].clear()
        self.assertEqual(source, original)

    def test_keyframe_edit_does_not_mutate_input_handles(self):
        source = {"Points": [{"co": {"X": 1, "Y": 0.5},
                              "handle_right": {"X": 0.25, "Y": 0.75}}]}
        original = copy.deepcopy(source)
        result = _set_keyframe_value(source, 1, 0.8)
        result["Points"][0]["handle_right"]["X"] = 0.9
        self.assertEqual(source, original)

    def test_wheels_snapshot_accepts_legacy_and_animated_data(self):
        for source in ({}, {"enabled": False, "global": {"color": "#ff8800", "amount": 0.7}},
                       {"global": {"amount_keyframes": {"Points": [
                           {"co": {"X": 20, "Y": 1}, "interpolation": openshot.LINEAR},
                           {"co": {"X": 1, "Y": 0}, "interpolation": openshot.LINEAR}]}}}):
            original = copy.deepcopy(source)
            normalized = normalize_wheels_data(source)
            for frame in (1, 10, 20, 30):
                self.assertEqual(wheels_snapshot(source, frame), wheels_snapshot(normalized, frame))
                self.assertEqual(wheels_enabled_at_frame(source, frame), wheels_enabled_at_frame(normalized, frame))
            self.assertEqual(source, original)

    def test_default_curve_data_uses_linear_nodes(self):
        curve = default_curve_data()
        self.assertEqual(len(curve["nodes"]), 2)
        self.assertEqual(curve["nodes"][0]["interpolation"], openshot.LINEAR)
        self.assertEqual(curve["nodes"][1]["interpolation"], openshot.LINEAR)
        self.assertEqual(curve["nodes"][0]["x"]["Points"][0]["interpolation"], openshot.LINEAR)

    def test_new_curve_node_interpolates_after_frame_one_shape_is_added(self):
        node = _default_curve_node(2, 0.5, 0.8, frame_number=24)
        node["y"] = _set_keyframe_value(node["y"], 1, 0.2)
        curve = normalize_curve_data({
            "enabled": {"Points": [{"co": {"X": 1.0, "Y": 1.0}, "interpolation": openshot.LINEAR}]},
            "nodes": [
                _default_curve_node(0, 0.0, 0.0),
                node,
                _default_curve_node(1, 1.0, 1.0),
            ],
        })

        evaluated = {node["id"]: node for node in curve_nodes_at_frame(curve, 12)}

        self.assertGreater(evaluated[2]["y"], 0.2)
        self.assertLess(evaluated[2]["y"], 0.8)

    def test_normalize_curve_data_falls_back_to_default(self):
        self.assertEqual(normalize_curve_data({}), default_curve_data())

    def test_curve_helpers_evaluate_current_frame(self):
        curve = default_curve_data()
        curve["nodes"][0]["y"]["Points"][0]["co"]["Y"] = 0.0
        curve["nodes"][0]["y"]["Points"].append({"co": {"X": 10.0, "Y": 0.5}, "interpolation": openshot.LINEAR})
        nodes = curve_nodes_at_frame(curve, 10)
        self.assertAlmostEqual(nodes[0]["y"], 0.5, places=3)
        self.assertTrue(curve_enabled_at_frame(curve, 1))

    def test_set_keyframe_value_preserves_other_frames(self):
        keyframe = {"Points": [
            {"co": {"X": 1.0, "Y": 0.1}, "interpolation": openshot.LINEAR},
            {"co": {"X": 20.0, "Y": 0.9}, "interpolation": openshot.LINEAR},
        ]}
        updated = _set_keyframe_value(keyframe, 10, 0.5)
        self.assertEqual(len(updated["Points"]), 3)
        self.assertAlmostEqual(updated["Points"][0]["co"]["Y"], 0.1, places=3)
        self.assertAlmostEqual(updated["Points"][1]["co"]["Y"], 0.5, places=3)
        self.assertAlmostEqual(updated["Points"][2]["co"]["Y"], 0.9, places=3)

    def test_set_color_value_preserves_other_frames(self):
        color = {
            "red": {"Points": [
                {"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                {"co": {"X": 20.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
            ]},
            "green": {"Points": [
                {"co": {"X": 1.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
                {"co": {"X": 20.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
            ]},
            "blue": {"Points": [
                {"co": {"X": 1.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
                {"co": {"X": 20.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
            ]},
            "alpha": {"Points": [
                {"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                {"co": {"X": 20.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
            ]},
        }
        updated = _set_color_value(color, 10, QColor("#ffffff"))
        self.assertEqual(len(updated["red"]["Points"]), 3)
        self.assertAlmostEqual(updated["red"]["Points"][0]["co"]["Y"], 255.0, places=3)
        self.assertAlmostEqual(updated["red"]["Points"][1]["co"]["Y"], 255.0, places=3)
        self.assertAlmostEqual(updated["red"]["Points"][2]["co"]["Y"], 0.0, places=3)
        self.assertEqual(wheel_snapshot({"color": updated, "amount": {"Points": [{"co": {"X": 10.0, "Y": 1.0}, "interpolation": openshot.LINEAR}]}, "luma": 0.0}, 10)["color"], "#ffffff")

    def test_normalize_wheels_data_clamps_values(self):
        wheels = normalize_wheels_data({
            "global": {"color": "#zzzzzz", "amount": 5, "luma": -5},
        })
        snapshot = wheel_snapshot(wheels["global"], 1)
        self.assertEqual(snapshot["color"], "#ffffff")
        self.assertEqual(snapshot["amount"], 1.0)
        self.assertEqual(snapshot["luma"], -1.0)

    def test_normalize_wheels_data_supplies_missing_entries(self):
        wheels = normalize_wheels_data({})
        self.assertEqual(wheels, default_wheels_data())

    def test_normalize_wheels_data_preserves_enabled_flag(self):
        wheels = normalize_wheels_data({"enabled": False})
        self.assertFalse(wheels_enabled_at_frame(wheels, 1))

    def test_colorgrade_keyframe_frames_includes_wheel_subkeyframes(self):
        wheels = default_wheels_data()
        wheels["global"]["color_keyframes"]["red"]["Points"].append({
            "co": {"X": 24.0, "Y": 64.0},
            "interpolation": openshot.CONSTANT,
        })
        wheels["highlights"]["luma_keyframes"]["Points"].append({
            "co": {"X": 48.0, "Y": 0.2},
            "interpolation": openshot.LINEAR,
        })

        self.assertEqual(
            colorgrade_keyframe_frames(wheels, "colorgrade_wheels"),
            {1, 24, 48},
        )

    def test_properties_model_applies_interpolation_to_colorgrade_wheel_frame(self):
        wheels = default_wheels_data()
        for keyframe in (
            wheels["global"]["color_keyframes"]["red"],
            wheels["global"]["color_keyframes"]["green"],
            wheels["global"]["amount_keyframes"],
            wheels["shadows"]["luma_keyframes"],
        ):
            keyframe["Points"].append({
                "co": {"X": 24.0, "Y": 0.5},
                "interpolation": openshot.LINEAR,
            })

        helper = PropertiesModel.__new__(PropertiesModel)
        updated, changed = helper._apply_colorgrade_interpolation(
            wheels,
            "colorgrade_wheels",
            1,
            24,
            openshot.CONSTANT,
            [],
        )

        self.assertTrue(changed)
        self.assertEqual(updated["global"]["color_keyframes"]["red"]["Points"][1]["interpolation"], openshot.CONSTANT)
        self.assertEqual(updated["global"]["color_keyframes"]["green"]["Points"][1]["interpolation"], openshot.CONSTANT)
        self.assertEqual(updated["global"]["amount_keyframes"]["Points"][1]["interpolation"], openshot.CONSTANT)
        self.assertEqual(updated["shadows"]["luma_keyframes"]["Points"][1]["interpolation"], openshot.CONSTANT)

    def test_properties_model_applies_interpolation_to_colorgrade_curve_frame(self):
        curve = default_curve_data()
        curve["nodes"][0]["y"]["Points"].append({
            "co": {"X": 32.0, "Y": 0.4},
            "interpolation": openshot.LINEAR,
        })
        curve["nodes"][1]["x"]["Points"].append({
            "co": {"X": 32.0, "Y": 0.8},
            "interpolation": openshot.LINEAR,
        })

        helper = PropertiesModel.__new__(PropertiesModel)
        updated, changed = helper._apply_colorgrade_interpolation(
            curve,
            "colorgrade_curve",
            1,
            32,
            openshot.CONSTANT,
            [],
        )

        self.assertTrue(changed)
        self.assertEqual(updated["nodes"][0]["y"]["Points"][1]["interpolation"], openshot.CONSTANT)
        self.assertEqual(updated["nodes"][1]["x"]["Points"][1]["interpolation"], openshot.CONSTANT)

    def test_properties_model_inserts_colorgrade_wheel_keyframe_without_resetting_payload(self):
        wheels = default_wheels_data()
        wheels["global"]["amount_keyframes"]["Points"].append({
            "co": {"X": 24.0, "Y": 0.8},
            "interpolation": openshot.LINEAR,
        })
        wheels["shadows"]["luma_keyframes"]["Points"].append({
            "co": {"X": 24.0, "Y": -0.4},
            "interpolation": openshot.LINEAR,
        })

        helper = PropertiesModel.__new__(PropertiesModel)
        updated = helper._insert_colorgrade_keyframe(wheels, "colorgrade_wheels", 12)

        self.assertIn(12, colorgrade_keyframe_frames(updated, "colorgrade_wheels"))
        self.assertIn(24, colorgrade_keyframe_frames(updated, "colorgrade_wheels"))
        self.assertEqual(updated["global"]["amount_keyframes"]["Points"][1]["interpolation"], openshot.LINEAR)
        self.assertEqual(updated["global"]["amount_keyframes"]["Points"][-1]["co"]["X"], 24.0)
        self.assertEqual(updated["shadows"]["luma_keyframes"]["Points"][-1]["co"]["X"], 24.0)

    def test_properties_model_removes_colorgrade_wheel_frame_without_clearing_other_frames(self):
        wheels = default_wheels_data()
        for keyframe in (
            wheels["global"]["color_keyframes"]["red"],
            wheels["global"]["color_keyframes"]["green"],
            wheels["global"]["amount_keyframes"],
            wheels["highlights"]["luma_keyframes"],
        ):
            keyframe["Points"].append({
                "co": {"X": 24.0, "Y": 0.5},
                "interpolation": openshot.LINEAR,
            })

        helper = PropertiesModel.__new__(PropertiesModel)
        updated, changed = helper._remove_colorgrade_keyframe(wheels, "colorgrade_wheels", 24)

        self.assertTrue(changed)
        self.assertEqual(colorgrade_keyframe_frames(updated, "colorgrade_wheels"), {1})

    def test_wheel_row_remove_keyframe_targets_active_interpolated_frame(self):
        row = WheelRow.__new__(WheelRow)
        row._frame_number = 12
        row._data = normalize_wheels_data({
            "global": {
                "color_keyframes": {
                    "red": {"Points": [
                        {"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 24.0, "Y": 64.0}, "interpolation": openshot.LINEAR},
                    ]},
                    "green": {"Points": [
                        {"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 24.0, "Y": 128.0}, "interpolation": openshot.LINEAR},
                    ]},
                    "blue": {"Points": [
                        {"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 24.0, "Y": 192.0}, "interpolation": openshot.LINEAR},
                    ]},
                    "alpha": {"Points": [
                        {"co": {"X": 1.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                        {"co": {"X": 24.0, "Y": 255.0}, "interpolation": openshot.LINEAR},
                    ]},
                },
                "amount_keyframes": {"Points": [
                    {"co": {"X": 1.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
                    {"co": {"X": 24.0, "Y": 0.8}, "interpolation": openshot.LINEAR},
                ]},
            }
        })["global"]
        row.dragStarted = type("Signal", (), {"emit": lambda self: None})()
        row.dragFinished = type("Signal", (), {"emit": lambda self: None})()
        row.changed = type("Signal", (), {"emit": lambda self: None})()
        row._apply_data = lambda: None

        row._remove_keyframe()

        self.assertEqual(row._frame_set(), {1})

    def test_wheel_row_remove_slider_keyframe_targets_active_interpolated_frame(self):
        row = WheelRow.__new__(WheelRow)
        row._frame_number = 12
        row._data = normalize_wheels_data({
            "global": {
                "amount_keyframes": {"Points": [
                    {"co": {"X": 1.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
                    {"co": {"X": 24.0, "Y": 0.8}, "interpolation": openshot.LINEAR},
                ]},
                "luma_keyframes": {"Points": [
                    {"co": {"X": 1.0, "Y": 0.0}, "interpolation": openshot.LINEAR},
                    {"co": {"X": 24.0, "Y": -0.4}, "interpolation": openshot.LINEAR},
                ]},
            }
        })["global"]
        row.dragStarted = type("Signal", (), {"emit": lambda self: None})()
        row.dragFinished = type("Signal", (), {"emit": lambda self: None})()
        row.changed = type("Signal", (), {"emit": lambda self: None})()
        row._apply_data = lambda: None

        row._remove_slider_keyframe("amount")

        self.assertEqual(
            [point["co"]["X"] for point in row._data["amount_keyframes"]["Points"]],
            [1.0],
        )
        self.assertEqual(
            [point["co"]["X"] for point in row._data["luma_keyframes"]["Points"]],
            [1.0, 24.0],
        )

    def test_achromatic_color_detection_treats_white_as_neutral(self):
        self.assertTrue(is_achromatic_color(QColor("#ffffff")))
        self.assertTrue(is_achromatic_color(QColor("#808080")))
        self.assertFalse(is_achromatic_color(QColor("#00ff24")))

    def test_puck_display_color_blends_from_neutral_to_hue(self):
        neutral = puck_display_color({"color": "#ff0000", "amount": 0.0})
        full = puck_display_color({"color": "#ff0000", "amount": 1.0})
        self.assertNotEqual(neutral.name(), full.name())
        self.assertEqual(full.name(), "#ff0000")


if __name__ == "__main__":
    unittest.main()
