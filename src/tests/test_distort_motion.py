"""Motion recipe timing, pairing, and native mesh evaluation."""
import copy
import json
import unittest
import uuid

import openshot
from classes.distort_motion import mesh_pose, wave_pose
from windows.views.motion import apply_motion
from windows.views.timeline_backend.enums import MenuAnimate


@unittest.skipUnless(hasattr(openshot, "Distort"), "Requires libopenshot Distort")
class DistortMotionTests(unittest.TestCase):
    def clip(self, start=0, end=5):
        data = json.loads(openshot.Clip().Json())
        data.update(start=start, end=end, duration=end-start, effects=[])
        return data

    def apply(self, data, name):
        base = openshot.Clip()
        base.SetJson(json.dumps(data))
        def reader(path):
            image = openshot.QtImageReader(path)
            image.Open()
            return json.loads(image.Json())
        apply_motion(data, MenuAnimate[name], 30, base_clip=base,
                     load_reader=reader, new_id=lambda: uuid.uuid4().hex)

    def distort(self, data):
        return next(fx for fx in data["effects"] if fx["class_name"] == "Distort" and fx.get("ui-menu") == "motion")

    def value(self, curve, frame):
        native = openshot.Keyframe()
        native.SetJson(json.dumps(curve))
        return native.GetValue(frame)

    def assert_neutral(self, data, frame):
        fx = self.distort(data)
        for i in range(16):
            for axis in ("x", "y"):
                self.assertAlmostEqual(self.value(fx["point_%s_%s" % (i, axis)], frame), 0)

    def test_all_pairs_preserve_resting_geometry_in_both_application_orders(self):
        for style in ("RIBBON", "WAVE", "LENS_RESOLVE"):
            for order in (("IN", "OUT"), ("OUT", "IN")):
                with self.subTest(style=style, order=order):
                    data = self.clip(start=2, end=7)
                    for side in order:
                        self.apply(data, style + "_" + side)
                    self.assertEqual(sum(fx["class_name"] == "Distort" for fx in data["effects"]), 1)
                    self.assert_neutral(data, 91)
                    self.assert_neutral(data, 121)
                    self.assert_neutral(data, 181)
                    effect = openshot.Distort()
                    effect.SetJson(json.dumps(self.distort(data)))
                    self.assertNotEqual(effect.MeshJSON(70), effect.MeshJSON(120))
                    self.assertNotEqual(effect.MeshJSON(200), effect.MeshJSON(120))

    def test_short_trimmed_clips_keep_nonoverlapping_entrance_and_exit(self):
        for style in ("RIBBON", "WAVE", "LENS_RESOLVE"):
            data = self.clip(start=2, end=3)
            self.apply(data, style + "_IN")
            before = copy.deepcopy(self.distort(data))
            self.apply(data, style + "_OUT")
            for i in range(16):
                key = "point_%s_y" % i
                for frame in (61, 65, 70, 75):
                    self.assertEqual(self.value(before[key], frame), self.value(self.distort(data)[key], frame))
            self.assert_neutral(data, 76)

    def test_exit_alone_leaves_earlier_geometry_and_opacity_unchanged(self):
        for style in ("RIBBON", "WAVE", "LENS_RESOLVE"):
            data = self.clip()
            self.apply(data, style + "_OUT")
            self.assert_neutral(data, 1)
            self.assert_neutral(data, 90)
            self.assertEqual(self.value(data["alpha"], 90), 1)

    def test_manual_effects_survive_application_and_motion_reset(self):
        data = self.clip()
        manual = json.loads(openshot.Distort().Json())
        manual["id"] = "manual"
        data["effects"].append(copy.deepcopy(manual))
        self.apply(data, "RIBBON_IN")
        self.assertEqual(data["effects"][0], manual)
        self.apply(data, "NONE")
        self.assertEqual(data["effects"], [manual])

    def test_replacing_entrance_preserves_exit_and_removes_old_companion_motion(self):
        data = self.clip()
        self.apply(data, "LENS_RESOLVE_IN")
        self.apply(data, "RIBBON_OUT")
        before = copy.deepcopy(self.distort(data))
        self.apply(data, "RIBBON_IN")
        self.assertEqual(self.value(data["scale_x"], 1), 1)
        self.apply(data, "WAVE_IN")
        self.assertFalse(any(fx["class_name"] == "Mask" for fx in data["effects"]))
        for frame in (121, 130, 140, 151):
            self.assertEqual(self.value(before["point_5_y"], frame), self.value(self.distort(data)["point_5_y"], frame))

    def test_repeated_application_reuses_one_mesh_without_masks(self):
        data = self.clip()
        for name in ("RIBBON_IN", "RIBBON_OUT", "RIBBON_IN"):
            self.apply(data, name)
        self.assertEqual([fx["class_name"] for fx in data["effects"]], ["Distort"])
        for fx in data["effects"]:
            for value in fx.values():
                if isinstance(value, dict) and "Points" in value:
                    frames = [p["co"]["X"] for p in value["Points"]]
                    self.assertEqual(len(frames), len(set(frames)))

    def test_lens_preserves_placed_clip_scale_and_opacity(self):
        data = self.clip()
        data["scale_x"] = json.loads(openshot.Keyframe(0.4).Json())
        data["scale_y"] = json.loads(openshot.Keyframe(0.6).Json())
        data["alpha"] = json.loads(openshot.Keyframe(0.7).Json())
        original = copy.deepcopy(data["location_x"])
        self.apply(data, "LENS_RESOLVE_IN")
        self.assertAlmostEqual(self.value(data["scale_x"], 31), 0.4)
        self.assertAlmostEqual(self.value(data["scale_y"], 31), 0.6)
        self.assertAlmostEqual(self.value(data["alpha"], 31), 0.7)
        self.assertEqual(data["location_x"], original)
        self.assertAlmostEqual(self.value(data["alpha"], 1), 0)

    def test_mesh_poses_are_neutral_at_rest_and_stagger_columns(self):
        for style in ("ribbon", "stretch", "lens_resolve"):
            self.assertEqual(mesh_pose(style, 1), [(0, 0)]*16)
            self.assertEqual(mesh_pose(style, 0, True), [(0, 0)]*16)
        pose = mesh_pose("ribbon", 0.5)
        self.assertNotEqual(pose[4][1], pose[7][1])

    def test_wave_pass_uses_playhead_and_preserves_entrance_exit_and_opacity(self):
        data = self.clip(start=2, end=7)
        self.apply(data, "RIBBON_IN")
        self.apply(data, "RIBBON_OUT")
        before = copy.deepcopy(data)
        base = openshot.Clip()
        base.SetJson(json.dumps(data))
        apply_motion(data, MenuAnimate.WAVE_PASS, 30, base_clip=base,
                     playhead_frame=61, new_id=lambda: uuid.uuid4().hex)
        # Timeline second 2 maps to source second 4 on this trimmed clip.
        self.assert_neutral(data, 121)
        self.assert_neutral(data, 151)
        fx = self.distort(data)
        self.assertGreater(abs(self.value(fx["point_5_y"], 136)), 0.03)
        for frame in (61, 75, 91, 181, 195, 211):
            self.assertEqual(self.value(fx["point_5_y"], frame),
                             self.value(self.distort(before)["point_5_y"], frame))
        self.assertEqual(data["alpha"], before["alpha"])
        self.assertEqual(data["location_x"], before["location_x"])

    def test_wave_pass_stays_neutral_outside_its_window_and_pins_boundary(self):
        self.assertEqual(wave_pose(0), [(0, 0)]*16)
        self.assertEqual(wave_pose(1), [(0, 0)]*16)
        pose = wave_pose(0.5)
        for index in (0,1,2,3,4,7,8,11,12,13,14,15):
            self.assertAlmostEqual(pose[index][0], 0)
            self.assertAlmostEqual(pose[index][1], 0)
        data = self.clip()
        apply_motion(data, MenuAnimate.WAVE_PASS, 30, playhead_frame=61,
                     new_id=lambda: uuid.uuid4().hex)
        self.assert_neutral(data, 1)
        self.assert_neutral(data, 31)
        self.assert_neutral(data, 61)
        self.assert_neutral(data, 91)
        self.assert_neutral(data, 120)

    def test_entrances_show_mesh_motion_without_reveal_masks(self):
        for style in ("RIBBON", "WAVE", "LENS_RESOLVE"):
            data = self.clip()
            self.apply(data, style+"_IN")
            self.assertEqual([fx["class_name"] for fx in data["effects"]], ["Distort"])
            self.assertGreater(self.value(data["alpha"], 6), 0)
            self.assertLess(self.value(data["alpha"], 6), 1)
            self.assertAlmostEqual(self.value(data["alpha"], 11), 1)
            self.apply(data, style+"_OUT")
            self.assertGreater(self.value(data["alpha"], 146), 0)
            self.assertLess(self.value(data["alpha"], 146), 1)
            self.assertAlmostEqual(self.value(data["alpha"], 151), 0)
        self.assertGreater(max(abs(y) for x,y in mesh_pose("ribbon", 0.3)), 0.2)
        self.assertGreater(max(abs(x) for x,y in mesh_pose("stretch", 0.3)), 0.2)

    def test_wave_has_one_small_return_ripple_without_spring_overshoot(self):
        for exiting in (False, True):
            poses = [mesh_pose("stretch", i / 100, exiting) for i in range(101)]
            horizontal = [pose[5][0] for pose in poses]
            self.assertTrue(all(value >= 0 for value in horizontal))
            for a, b in zip(horizontal, horizontal[1:]):
                if exiting:
                    self.assertGreaterEqual(b, a)
                else:
                    self.assertLessEqual(b, a)
            # Average the two interior rows to isolate the return ripple from
            # the main squeeze. Its displacement remains below 1.5% of height.
            for pose in poses:
                for column in (1, 2):
                    ripple = (pose[4 + column][1] + pose[8 + column][1]) / 2
                    self.assertLess(abs(ripple), 0.015)
        pose = mesh_pose("stretch", 0.7)
        left = (pose[5][1] + pose[9][1]) / 2
        right = (pose[6][1] + pose[10][1]) / 2
        self.assertLess(left, 0)
        self.assertGreater(right, 0)
        self.assertEqual(mesh_pose("stretch", 1), [(0, 0)] * 16)
