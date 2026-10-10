"""Exercise value edits and explicit insertion with recording disabled."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

import openshot
from classes.keyframe_editing import initialize_split_clip_keyframes
from qt_api import QApplication, QColor, QStandardItem, QStandardItemModel
from windows.models import properties_model
from windows import video_widget
from windows.color_grade_editor import default_wheels_data, _set_keyframe_value


def curve(*frames):
    return {"Points": [{"co": {"X": frame, "Y": value}, "interpolation": 1}
                       for frame, value in frames]}


class AutoKeyframeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.action = Mock()
        self.action.isChecked.return_value = False
        self.app = types.SimpleNamespace(
            _tr=lambda s: s, project={"fps": {"num": 25, "den": 1}},
            updates=types.SimpleNamespace(transaction_id=None),
            window=types.SimpleNamespace(actionAutoKeyframes=self.action,
                                         refreshFrameSignal=Mock()))
        self.preview = types.SimpleNamespace(transaction_id="drag")
        self.saved = {"rotation": curve((1, 0), (51, 20), (101, 90)),
                      "start": 2., "end": 4.04, "position": 10.}

        def get_clip(**kwargs):
            clip = types.SimpleNamespace(id="clip", data=copy.deepcopy(self.saved))
            clip.save = lambda: self.saved.update(copy.deepcopy(clip.data))
            return clip

        for module in (properties_model, video_widget):
            self.enterContext(patch.object(module, "get_app", return_value=self.app))
            self.enterContext(patch.object(module.Clip, "get", side_effect=get_clip))

    # unittest.TestCase.enterContext is unavailable on Python 3.8.
    def enterContext(self, context):
        value = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return value

    def editor(self, frame, key="rotation", kind="float", value=55):
        model = properties_model.PropertiesModel.__new__(properties_model.PropertiesModel)
        model.ignore_update_signal = False
        model._trim_preview_mode = False
        model.frame_number = frame
        model.model = QStandardItemModel()
        label, item = QStandardItem(key), QStandardItem(str(value))
        label.setData((key, {"type": kind, "closest_point_x": 101,
                            "previous_point_x": 51, "object_id": None, "value": value}))
        item.setData([("clip", "clip")])
        model.model.appendRow([label, item])
        model.parent = Mock()
        model.parent.currentIndex.return_value.row.return_value = -1
        return model, item

    def test_dock_and_preview_target_same_preceding_point(self):
        original = copy.deepcopy(self.saved)
        for frame, target in ((1, 1), (50, 1), (51, 51), (75, 51), (150, 101)):
            for source in ("dock", "preview"):
                with self.subTest(frame=frame, source=source):
                    self.saved = copy.deepcopy(original)
                    if source == "dock":
                        model, item = self.editor(frame)
                        model.value_updated(item, value=30)
                    else:
                        video_widget.VideoWidget.updateClipProperty(self.preview, "clip", frame, "rotation", 30)
                    expected = copy.deepcopy(original["rotation"])
                    next(p for p in expected["Points"] if p["co"]["X"] == target)["co"]["Y"] = 30
                    self.assertEqual(self.saved["rotation"], expected)
                    self.assertEqual(self.saved["start"], 2.)

    def test_trimmed_constant_and_curve_without_frame_one(self):
        for frames, expected in ((((1, 0),), 1), (((51, 20), (101, 90)), 51), ((), 1)):
            self.saved["rotation"] = curve(*frames)
            model, item = self.editor(25)
            model.value_updated(item, value=15)
            points = self.saved["rotation"]["Points"]
            self.assertEqual(len(points), max(1, len(frames)))
            self.assertEqual(next(p["co"]["Y"] for p in points if p["co"]["X"] == expected), 15)

    def test_manual_insertion_samples_playhead_then_edits_new_point(self):
        model, item = self.editor(76, value=55)
        item.setText("20")  # Dock displays the preceding point when recording is off.
        model.insert_keyframe(item)
        self.assertEqual(self.saved["rotation"]["Points"][-1]["co"], {"X": 76, "Y": 55})
        model.value_updated(item, value=65)
        self.assertEqual(self.saved["rotation"]["Points"][-1]["co"], {"X": 76, "Y": 65})
        self.assertEqual(self.saved["rotation"]["Points"][1]["co"]["Y"], 20)

    def test_enabled_mode_still_creates_at_playhead(self):
        self.action.isChecked.return_value = True
        model, item = self.editor(76)
        model.value_updated(item, value=55)
        video_widget.VideoWidget.updateClipProperty(self.preview, "clip", 80, "rotation", 60)
        self.assertEqual([p["co"]["X"] for p in self.saved["rotation"]["Points"]], [1, 51, 101, 76, 80])

    def test_effect_channels_choose_their_own_target_and_save_together(self):
        effect = types.SimpleNamespace(data={"objects": {"tracked": {
            "delta_x": curve((1, 0), (40, .1)), "delta_y": curve((1, 0), (60, .2))}}}, save=Mock())
        with patch.object(video_widget.Effect, "get", return_value=effect):
            video_widget.VideoWidget.updateEffectProperties(
                self.preview, "effect", 50, "tracked", {"delta_x": .3, "delta_y": .4})
        values = effect.data["objects"]["tracked"]
        self.assertEqual(values["delta_x"], curve((1, 0), (40, .3)))
        self.assertEqual(values["delta_y"], curve((1, .4), (60, .2)))
        effect.save.assert_called_once()
        self.assertEqual(self.app.updates.transaction_id, "drag")

    def test_color_edit_and_explicit_color_insertion(self):
        self.saved["color"] = {channel: curve((1, 0), (51, 20), (101, 90))
                               for channel in ("red", "green", "blue", "alpha")}
        model, item = self.editor(76, "color", "color")
        model.color_update(item, QColor(100, 110, 120, 130))
        for channel, value in zip(("red", "green", "blue", "alpha"), (100, 110, 120, 130)):
            self.assertEqual(self.saved["color"][channel], curve((1, 0), (51, value), (101, 90)))
        model.color_update(item, QColor(150, 160, 170, 180), force_insert=True)
        self.assertEqual(self.saved["color"]["red"]["Points"][-1]["co"], {"X": 76, "Y": 150})

    def test_nested_wheel_edit_does_not_insert_or_touch_other_channels(self):
        original = default_wheels_data()
        original["global"]["amount_keyframes"] = curve((1, 0), (51, .2), (101, .8))
        self.saved["wheels"] = copy.deepcopy(original)
        updated = copy.deepcopy(original)
        updated["global"]["amount_keyframes"] = _set_keyframe_value(
            updated["global"]["amount_keyframes"], 76, .5)
        model, item = self.editor(76, "wheels", "colorgrade_wheels")
        model.value_updated(item, value=updated)
        expected = copy.deepcopy(original)
        expected["global"]["amount_keyframes"]["Points"][1]["co"]["Y"] = .5
        self.assertEqual(self.saved["wheels"], expected)

    def test_split_file_anchor_starts_animation_at_visible_edge(self):
        for fps in (25, 30000 / 1001):
            with self.subTest(fps=fps):
                data = {"start": 2.0, "rotation": curve((1, 0)),
                        "scale_x": curve((1, 1)), "time": curve((1, 1))}
                initialize_split_clip_keyframes(data, fps)
                start = round(2 * fps) + 1
                self.assertEqual(data["rotation"], curve((1, 0), (start, 0)))
                self.assertEqual(data["scale_x"], curve((1, 1), (start, 1)))
                self.assertEqual(data["time"], curve((1, 1)))
                animation = openshot.Keyframe()
                animation.SetJson(json.dumps(data["rotation"]))
                animation.AddPoint(start + 50, 90, openshot.LINEAR)
                self.assertEqual(animation.GetValue(start), 0)
                self.assertAlmostEqual(animation.GetValue(start + 25), 45)
                self.assertEqual(animation.GetValue(start + 50), 90)

    def test_initialization_preserves_existing_animation_and_does_not_duplicate_anchors(self):
        data = {"start": 2., "rotation": curve((1, 0), (101, 90)),
                "alpha": curve((1, 1)), "reader": {"custom": curve((1, 7))}}
        existing = copy.deepcopy(data["rotation"])
        initialize_split_clip_keyframes(data, 25)
        initialize_split_clip_keyframes(data, 25)
        self.assertEqual(data["rotation"], existing)
        self.assertEqual(data["alpha"], curve((1, 1), (51, 1)))
        self.assertEqual(data["reader"]["custom"], curve((1, 7)))


class AutoKeyframeWorkflowTests(unittest.TestCase):
    def test_split_creation_slicing_manual_insertion_and_undo(self):
        source = Path(__file__).resolve().parents[1]
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   PYTHONPATH=os.pathsep.join(filter(None, (
                       str(source), os.environ.get("PYTHONPATH", ""), str(source.parent)))))
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("auto_keyframes_smoke.py"))],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout[-12000:])
        self.assertIn("AUTO_KEYFRAMES_WORKFLOW_PASSED", result.stdout)
