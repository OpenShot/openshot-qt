"""Verify split ranges, manual animation, and undo in the real main window."""
import copy
import json
import os
import tempfile
import traceback
import unittest

import openshot

root = tempfile.mkdtemp(prefix="openshot-auto-keyframes-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)

from classes.app import OpenShotApp
from classes import version
from classes.query import Clip, File
from qt_api import QImage, QPointF, QTimer, Qt

version.get_current_Version = lambda: None
app = OpenShotApp([], mode="unittest")
from windows.add_to_timeline import AddToTimeline
from windows.views.timeline import MenuSlice
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
checks = unittest.TestCase()
passed = False


def verify():
    global passed
    try:
        window = app.window
        image = QImage(640, 360, QImage.Format_RGBA8888)
        image.fill(Qt.white)
        path = os.path.join(root, "source.png")
        checks.assertTrue(image.save(path))
        native = openshot.Clip(path)
        source = File()
        source.data = json.loads(native.Reader().Json())
        source.data.update(path=path, media_type="image", start=2., end=8., name="Split range")
        source.save()
        source_data = copy.deepcopy(source.data)
        fps = app.project.get("fps")
        fps = fps["num"] / fps["den"]
        start_frame = round(2 * fps) + 1
        layer = app.project.get("layers")[-1]["number"]

        # Drag/drop creation adds a boundary anchor, independent of recording mode.
        window.actionAutoKeyframes.trigger()
        added = window.timeline.addClip(source.id, QPointF(1., 0), layer, call_manual_move=False)
        clip = Clip.get(id=added["id"])
        checks.assertEqual([p["co"]["X"] for p in clip.data["rotation"]["Points"]], [1, start_frame])
        checks.assertEqual(len(clip.data["time"]["Points"]), 1)
        checks.assertEqual(File.get(id=source.id).data, source_data)

        # The Add to Timeline dialog uses the same initialization.
        old_ids = {item.id for item in Clip.filter()}
        dialog = AddToTimeline(files=[source], position=12.)
        dialog.accept()
        dialog.deleteLater()
        other = next(item for item in Clip.filter() if item.id not in old_ids)
        checks.assertEqual([p["co"]["X"] for p in other.data["rotation"]["Points"]], [1, start_frame])

        # Existing animation stays intact on both sides of a slice.
        clip = Clip.get(id=clip.id)
        clip.data["rotation"] = {"Points": [
            {"co": {"X": frame, "Y": value}, "interpolation": 1}
            for frame, value in ((1, 0), (101, 20), (201, 90))]}
        clip.save()
        original_curve = copy.deepcopy(clip.data["rotation"])
        old_ids = {item.id for item in Clip.filter()}
        window.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [clip.id], [], playhead_position=4.)
        right = next(item for item in Clip.filter() if item.id not in old_ids)
        checks.assertEqual(Clip.get(id=clip.id).data["rotation"], original_curve)
        checks.assertEqual(right.data["rotation"], original_curve)

        # Dock edits target the preceding point; undo/redo restores the exact curve.
        model = window.propertyTableView.clip_properties_model
        selection = [{"id": right.id, "type": "clip"}]
        window.selected_items = selection
        model.update_item(selection)
        model.update_item_timeout()
        model.frame_number = 151
        model.update_model()
        item = model.items["rotation"]["row"][1]
        checks.assertEqual(float(item.text()), 20.)
        checks.assertIn("101", item.toolTip())
        model.value_updated(item, value=35)
        checks.assertEqual(Clip.get(id=right.id).data["rotation"]["Points"][1]["co"]["Y"], 35)
        window.actionUndo.trigger()
        checks.assertEqual(Clip.get(id=right.id).data["rotation"], original_curve)
        window.actionRedo.trigger()
        checks.assertEqual(Clip.get(id=right.id).data["rotation"]["Points"][1]["co"]["Y"], 35)

        # Manual insertion uses the evaluated value, not the displayed left value.
        model.frame_number = 151
        model.update_model()
        model.insert_keyframe(model.items["rotation"]["row"][1])
        points = Clip.get(id=right.id).data["rotation"]["Points"]
        checks.assertEqual(len(points), 4)
        checks.assertEqual(next(p["co"]["Y"] for p in points if p["co"]["X"] == 151), 62.5)
        checks.assertFalse(window.actionAutoKeyframes.isChecked())
        passed = True
        print("AUTO_KEYFRAMES_WORKFLOW_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


checks.assertTrue(app.gui())
QTimer.singleShot(4000, verify)
app.exec_()
raise SystemExit(0 if passed else 1)
