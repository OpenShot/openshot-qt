"""Exercise semantic typography through the real Properties dock and history."""
import copy
import os
import sys
import tempfile
import traceback

root = tempfile.mkdtemp(prefix="openshot-text-properties-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)
from classes.app import OpenShotApp
from classes.query import Clip
from qt_api import QColor, QFont, QTimer

app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
passed = False


def verify():
    global passed
    try:
        from classes.direct_text import default_text, new_text_clip
        window = app.window
        style = default_text(app.project.get("width"), app.project.get("height"))
        style["text"] = "Visible text"
        clip = Clip()
        clip.data = new_text_clip(style, root, 0.0, app.project.get("layers")[-1]["number"], 4.0)
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

        keys = {model.model.item(row, 0).data()[0] for row in range(model.model.rowCount())}
        assert {"alpha", "location_x", "location_y", "scale_x", "scale_y", "rotation"} <= keys, keys
        for key in ("font_family", "font_bold", "font_italic", "font_size", "color", "background", "alignment", "width", "text"):
            label = model.model.item(item("direct_text." + key).row(), 0).data()[1]
            assert label["points"] == 0 and not label["readonly"], label

        initial = copy.deepcopy(Clip.get(id=clip.id).data)
        for key, value in (("font_family", "DejaVu Sans"), ("font_size", 81),
                           ("font_bold", True), ("font_italic", True),
                           ("alignment", "center"), ("width", 500), ("text", "Typography\nsecond line")):
            model.value_updated(item("direct_text." + key), value=value)
            assert Clip.get(id=clip.id).data["direct_text"][key] == value
        model.color_update(item("direct_text.color"), QColor("#ffdd2200"))
        model.color_update(item("direct_text.background"), QColor("#80445566"))
        after = copy.deepcopy(Clip.get(id=clip.id).data)
        assert QColor(after["direct_text"]["color"]) == QColor("#ffdd2200")
        assert QColor(after["direct_text"]["background"]) == QColor("#80445566")
        assert initial["reader"]["path"] != after["reader"]["path"]
        for key in ("alpha", "location_x", "location_y", "scale_x", "scale_y", "rotation", "position", "start", "end"):
            assert initial[key] == after[key], key
        app.updates.undo()
        assert Clip.get(id=clip.id).data["direct_text"]["background"] == initial["direct_text"]["background"]
        app.updates.redo()
        assert Clip.get(id=clip.id).data["direct_text"] == after["direct_text"]
        assert model.model.item(item("direct_text.font_size").row(), 1).text() == "81"
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
        assert selected_font["font_size"] == 93 and not selected_font["font_bold"] and not selected_font["font_italic"]
        assert selected_font["font_family"] == "DejaVu Serif"
        assert Clip.get(id=clip.id).data["reader"]["path"] != after["reader"]["path"]
        app.updates.undo()
        assert Clip.get(id=clip.id).data["direct_text"] == after["direct_text"]
        # Empty text is a legitimate property edit (no stale visible glyphs).
        model.value_updated(item("direct_text.text"), value="")
        assert Clip.get(id=clip.id).data["direct_text"]["text"] == ""
        app.updates.undo()
        assert Clip.get(id=clip.id).data["direct_text"]["text"] == "Typography\nsecond line"
        locked_data = copy.deepcopy(after)
        layer = copy.deepcopy(next(layer for layer in app.project.get("layers") if layer["number"] == locked_data["layer"]))
        layer["lock"] = True
        # Verify readonly schema independently, without changing project history.
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch("windows.models.properties_model.get_app", return_value=SimpleNamespace(project={"layers": [layer]})):
            assert all(prop["readonly"] for prop in model._direct_text_properties(locked_data).values())
        passed = True
        print("TEXT_PROPERTIES_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


assert app.gui()
QTimer.singleShot(4000, verify)
app.exec_()
sys.exit(0 if passed else 1)
