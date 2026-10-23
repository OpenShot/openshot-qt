"""Exercise semantic typography through the real Properties dock and history."""
import copy
import importlib
import os
import sys
import tempfile
import traceback
import unittest

root = tempfile.mkdtemp(prefix="openshot-text-properties-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)
from classes.app import OpenShotApp
from classes import version
# UI workflow checks must not depend on the external update service.
version.get_current_Version = lambda: None
from classes.query import Clip
from qt_api import QColor, QFont, QTimer, QT_API
QTest = importlib.import_module({"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API] + ".QtTest").QTest

app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
checks = unittest.TestCase()
passed = False


def verify():
    global passed
    try:
        from classes.direct_text import default_text, new_text_clip, save_text_asset, evaluated_text_style
        window = app.window
        style = default_text(app.project.get("width"), app.project.get("height"))
        style["text"] = "Visible text"
        clip = Clip()
        clip.data = new_text_clip(style, root, 0.0, app.project.get("layers")[-1]["number"], 4.0)
        asset = save_text_asset(style)
        clip.data["file_id"] = asset.id
        clip.save()
        app.processEvents()
        model = window.propertyTableView.clip_properties_model
        model.update_item([{"id": clip.id, "type": "clip"}])
        model.update_item_timeout()

        def item(key):
            for row in range(model.model.rowCount()):
                if model.model.item(row, 0).data()[0] == key:
                    return model.model.item(row, 1)
            raise AssertionError("Missing property " + key)

        def playhead_at(frame):
            """Move the playhead to a frame within the clip, as the timeline does."""
            data, fps = Clip.get(id=clip.id).data, app.project.get("fps")
            offset = round((data["position"] - data["start"]) * fps["num"] / fps["den"])
            model.update_frame(offset + frame, reload_model=False)

        keys = {model.model.item(row, 0).data()[0] for row in range(model.model.rowCount())}
        checks.assertLessEqual({"alpha", "location_x", "location_y", "scale_x", "scale_y", "rotation"}, keys, keys)
        for key in ("font_family", "font_bold", "font_italic", "font_size", "alignment", "width", "text"):
            label = model.model.item(item("direct_text." + key).row(), 0).data()[1]
            checks.assertTrue(label["points"] == 0 and not label["readonly"], label)

        initial = copy.deepcopy(Clip.get(id=clip.id).data)
        for key, value in (("font_family", "DejaVu Sans"), ("font_size", 81),
                           ("font_bold", True), ("font_italic", True),
                           ("alignment", "center"), ("width", 500), ("text", "Typography\nsecond line")):
            model.value_updated(item("direct_text." + key), value=value)
            checks.assertEqual(Clip.get(id=clip.id).data["direct_text"][key], value)
        model.color_update(item("text_color"), QColor("#ffdd2200"))
        model.color_update(item("text_background"), QColor("#80445566"))
        after = copy.deepcopy(Clip.get(id=clip.id).data)
        checks.assertEqual(QColor(evaluated_text_style(after, 1)["color"]), QColor("#ffdd2200"))
        checks.assertEqual(QColor(evaluated_text_style(after, 1)["background"]), QColor("#80445566"))
        checks.assertNotEqual(initial["reader"]["font"], after["reader"]["font"])
        for key in ("alpha", "location_x", "location_y", "scale_x", "scale_y", "rotation", "position", "start", "end"):
            checks.assertEqual(initial[key], after[key], key)
        app.updates.undo()
        checks.assertEqual(Clip.get(id=clip.id).data["direct_text"]["background"], initial["direct_text"]["background"])
        app.updates.redo()
        checks.assertEqual(Clip.get(id=clip.id).data["direct_text"], after["direct_text"])
        checks.assertEqual(model.model.item(item("direct_text.font_size").row(), 1).text(), "81")
        # Explicit color keys use normal per-clip curves and survive shared edits.
        playhead_at(31)
        model.color_update(item("text_color"), QColor("#0000ff"), force_insert=True)
        animated = Clip.get(id=clip.id).data
        checks.assertEqual(len(animated["text_color"]["red"]["Points"]), 2)
        checks.assertEqual(QColor(evaluated_text_style(animated, 31)["color"]), QColor("#0000ff"))
        checks.assertEqual(animated["reader"]["text_animation"]["color"], animated["text_color"])
        from classes.query import File
        checks.assertEqual(File.get(id=asset.id).data["direct_text"]["color"], style["color"])
        app.updates.undo()
        model.frame_number = 1
        model.remove_keyframe(item("text_color"))
        reset = Clip.get(id=clip.id).data
        checks.assertEqual(QColor(evaluated_text_style(reset, 1)["color"]), QColor(style["color"]))
        checks.assertTrue(all(reset["text_color"][channel]["Points"] for channel in ("red", "green", "blue", "alpha")))
        app.updates.undo()
        checks.assertEqual(Clip.get(id=clip.id).data["text_color"], after["text_color"])
        # Both font entry points use this helper: persist family, size and face,
        # and undo the complete accepted dialog as a single action.
        from unittest.mock import patch
        table = window.propertyTableView
        table.selected_item = item("direct_text.font_family")
        chosen = QFont("DejaVu Serif")
        chosen.setPixelSize(93)
        chosen.setBold(False)
        chosen.setItalic(False)
        with patch("windows.views.properties_tableview.get_font_dialog_selection", return_value=(chosen, True)):
            table._choose_property_font(model.model.item(table.selected_item.row(), 0).data())
        selected_font = Clip.get(id=clip.id).data["direct_text"]
        checks.assertTrue(selected_font["font_size"] == 93 and not selected_font["font_bold"] and not selected_font["font_italic"])
        checks.assertEqual(selected_font["font_family"], "DejaVu Serif")
        checks.assertNotEqual(Clip.get(id=clip.id).data["reader"]["font"], after["reader"]["font"])
        app.updates.undo()
        checks.assertEqual(Clip.get(id=clip.id).data["direct_text"], after["direct_text"])
        # Empty text is a legitimate property edit (no stale visible glyphs).
        model.value_updated(item("direct_text.text"), value="")
        checks.assertEqual(Clip.get(id=clip.id).data["direct_text"]["text"], "")
        app.updates.undo()
        checks.assertEqual(Clip.get(id=clip.id).data["direct_text"]["text"], "Typography\nsecond line")
        locked_data = copy.deepcopy(after)
        layer = copy.deepcopy(next(layer for layer in app.project.get("layers") if layer["number"] == locked_data["layer"]))
        layer["lock"] = True
        # Verify readonly schema independently, without changing project history.
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch("windows.models.properties_model.get_app", return_value=SimpleNamespace(project={"layers": [layer]})):
            checks.assertTrue(all(prop["readonly"] for prop in model._direct_text_properties(locked_data).values()))
        # Reopening an existing selected text must populate Properties immediately,
        # including after Undo; deferred timeline selection cannot leave it blank.
        controller = window.direct_text
        controller.begin(clip.id)
        checks.assertGreater(model.model.rowCount(), 0, "Properties blank when editing selected text")
        checks.assertTrue(item("direct_text.font_size") and item("scale_x"))
        controller.editor.insertPlainText(" edited")
        controller.finish(commit=True)
        window.actionUndo_trigger()
        controller.begin(clip.id)
        checks.assertGreater(model.model.rowCount(), 0, "Properties blank when reopening after Undo")
        checks.assertTrue(item("direct_text.font_size") and item("location_x"))
        QTest.qWait(250)
        checks.assertGreater(model.model.rowCount(), 0, "Queued selection cleared text Properties")
        checks.assertTrue(item("direct_text.font_size") and item("location_x"))
        controller.cancel()
        # Animated colors persist in project JSON without changing sibling clips.
        sibling = Clip()
        sibling.data = new_text_clip(File.get(id=asset.id).data["direct_text"], root, 5.0,
                                     after["layer"], 4.0)
        sibling.data["file_id"] = asset.id
        sibling.save()
        playhead_at(31)
        model.color_update(item("text_color"), QColor("#800000ff"), force_insert=True)
        animated = copy.deepcopy(Clip.get(id=clip.id).data)
        project_path = os.path.join(root, "animated-text.osp")
        app.project.save(project_path)
        app.project.load(project_path, interactive=False)
        restored = Clip.get(id=clip.id).data
        checks.assertEqual(restored["text_color"], animated["text_color"])
        checks.assertEqual(restored["reader"]["text_animation"], animated["reader"]["text_animation"])
        checks.assertEqual(QColor(evaluated_text_style(restored, 31)["color"]), QColor("#800000ff"))
        checks.assertEqual(QColor(evaluated_text_style(Clip.get(id=sibling.id).data, 31)["color"]), QColor(style["color"]))
        passed = True
        print("TEXT_PROPERTIES_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


checks.assertTrue(app.gui())
QTimer.singleShot(4000, verify)
app.exec_()
sys.exit(0 if passed else 1)
