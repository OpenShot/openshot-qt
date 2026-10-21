"""Text editing feedback: Properties/editor sync, box fitting, remembered and reset styles."""
import importlib
import json
import os
import sys
import tempfile
import traceback
import unittest
from unittest.mock import patch

root = tempfile.mkdtemp(prefix="openshot-text-feedback-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)
from classes.app import OpenShotApp
from classes import version
# UI workflow checks must not depend on the external update service.
version.get_current_Version = lambda: None
from classes.query import Clip
from qt_api import QColor, QFont, QFontInfo, QImage, QTimer, QT_API
QTest = importlib.import_module({"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API] + ".QtTest").QTest

app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
checks = unittest.TestCase()
passed = False


def ink_height(pixmap):
    """Rows holding text pixels brighter than the black preview background."""
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    rows = [y for y in range(image.height())
            if any(QColor(image.pixel(x, y)).lightness() > 128 for x in range(0, image.width(), 2))]
    return rows[-1] - rows[0] if rows else 0


def verify():
    global passed
    try:
        from classes.direct_text import default_text, default_font_family
        from windows.text_style import TextStyleDialog
        from windows.color_picker import ColorPicker
        window = app.window
        controller = window.direct_text
        model = window.propertyTableView.clip_properties_model
        factory = default_text(app.project.get("width"), app.project.get("height"))

        def item(key):
            for row in range(model.model.rowCount()):
                if model.model.item(row, 0).data()[0] == key:
                    return model.model.item(row, 1)
            raise AssertionError("Missing property " + key)

        def select(clip_id):
            model.update_item([{"id": clip_id, "type": "clip"}])
            model.update_item_timeout()

        # The default font is a real installed face, never a generic alias
        # (which Windows shows as "MS Shell Dlg 2").
        family = default_font_family()
        checks.assertNotIn(family, ("Sans Serif", "MS Shell Dlg 2"))
        checks.assertEqual(QFontInfo(QFont(family)).family(), family)

        # While typing, Properties edits reach the editor and its style bar,
        # and style bar edits show in Properties, all before committing.
        controller.arm()
        app.processEvents()
        clip_id = controller.clip_id
        checks.assertTrue(clip_id and controller.draft is not None)
        model.value_updated(item("direct_text.font_size"), value=90)
        checks.assertEqual(controller.draft["font_size"], 90)
        checks.assertEqual(controller.toolbar.size.value(), 90)
        checks.assertEqual(item("direct_text.font_size").text(), "90")
        controller.toolbar.size.setValue(70)
        checks.assertEqual(item("direct_text.font_size").text(), "70")
        # A style change that grows the box shows every line while typing.
        controller.style_changed("line_spacing", 2.0)
        checks.assertEqual(controller.proxy.size().toSize(), controller.editor.size())
        checks.assertEqual(item("direct_text.line_spacing").text(), "2.000")
        controller.style_changed("line_spacing", 1.0)
        controller.style_changed("color", "#ffff0000")
        color = model.model.item(item("text_color").row(), 0).data()[1]
        checks.assertEqual((color["red"]["value"], color["green"]["value"], color["alpha"]["value"]), (255, 0, 255))
        label = model.model.item(item("direct_text.font_size").row(), 0).data()[1]
        checks.assertTrue(label.get("step_drag"), "Font size drags in single steps")
        controller.finish(commit=True)
        checks.assertEqual(Clip.get(id=clip_id).data["direct_text"]["font_size"], 70)

        # The box fits its text, so a huge font and back leaves it where it was.
        select(clip_id)
        before = Clip.get(id=clip_id).data
        model.value_updated(item("direct_text.font_size"), value=450)
        checks.assertGreater(Clip.get(id=clip_id).data["direct_text"]["height"], before["direct_text"]["height"])
        model.value_updated(item("direct_text.font_size"), value=70)
        after = Clip.get(id=clip_id).data
        checks.assertEqual(after["direct_text"]["height"], before["direct_text"]["height"])
        checks.assertEqual(after["location_y"], before["location_y"])

        # Letter spacing reaches the native reader.
        model.value_updated(item("direct_text.letter_spacing"), value=12)
        checks.assertEqual(Clip.get(id=clip_id).data["reader"]["letter_spacing"], 12)
        # Padding (Edit Style > Background) is editable in Properties too, and
        # the box grows to fit it.
        height = Clip.get(id=clip_id).data["direct_text"]["height"]
        model.value_updated(item("direct_text.background_padding"), value=40)
        checks.assertEqual(Clip.get(id=clip_id).data["reader"]["background_padding"], 40)
        checks.assertGreater(Clip.get(id=clip_id).data["direct_text"]["height"], height)
        model.value_updated(item("direct_text.background_padding"), value=12)

        # New text starts with the last style used.
        controller.arm()
        app.processEvents()
        checks.assertEqual(controller.draft["font_size"], 70)
        checks.assertEqual(controller.draft["letter_spacing"], 12)
        checks.assertEqual(QColor(controller.draft["color"]), QColor("#ffff0000"))
        controller.discard()

        # Clip menu: Edit Style opens a dialog titled Edit Style; Reset Style
        # restores factory defaults, keeping the words.
        titles = []
        app.clipboard().setText("")  # offscreen platforms start without clipboard data
        with patch("windows.views.timeline.StyledContextMenu.show_at", lambda menu, pos: menu):
            menu = window.timeline.ShowClipMenu(clip_id)
        text_menu = next(a.menu() for a in menu.actions() if a.text().replace("&", "") == "Text")
        actions = {a.text(): a for a in text_menu.actions()}
        with patch.object(TextStyleDialog, "exec_", lambda dialog: titles.append(dialog.windowTitle()) or 0):
            actions["Edit Style…"].trigger()
        checks.assertEqual(titles, ["Edit Style"])
        words = Clip.get(id=clip_id).data["direct_text"]["text"]
        actions["Reset Style"].trigger()
        reset = Clip.get(id=clip_id).data
        for key in ("font_family", "font_size", "letter_spacing", "color", "alignment"):
            checks.assertEqual(reset["direct_text"][key], factory[key], key)
        checks.assertEqual(reset["direct_text"]["text"], words)
        checks.assertEqual(reset["text_style_overrides"], [])
        checks.assertEqual(reset["reader"]["text_animation"], {})
        app.updates.undo()
        checks.assertEqual(Clip.get(id=clip_id).data["direct_text"]["font_size"], 70)
        app.updates.redo()

        # The dialog preview shows font size changes: the scale follows the
        # box width only, so bigger text draws bigger.
        style = dict(factory, text="Preview")
        dialog = TextStyleDialog(style, window)
        dialog.show()
        dialog.render_preview()
        small = ink_height(dialog.preview.pixmap())
        dialog.toolbar.size.setValue(style["font_size"] * 2)
        dialog.render_preview()
        checks.assertGreater(ink_height(dialog.preview.pixmap()), small * 1.6)
        checks.assertEqual(dialog.windowTitle(), "Edit Text")
        # Shrinking the dialog never squeezes the settings into the divider.
        dialog.resize(100, dialog.height())
        app.processEvents()
        checks.assertGreaterEqual(dialog.width(), dialog.layout().minimumSize().width())
        checks.assertEqual((dialog.spins["line_spacing"].value(), dialog.spins["background_corner"].value()),
                           (1.0, 0))
        dialog.restore_defaults()
        checks.assertEqual(dialog.style()["font_size"], factory["font_size"])
        checks.assertEqual(dialog.style()["text"], "Preview")
        dialog.reject()
        dialog.deleteLater()
        app.processEvents()

        # Copy > Text Style pastes the look (and its keyframes) onto other
        # text clips, keeping their words; other clips and empty paste ignore it.
        from classes.direct_text import (new_text_clip, save_text_asset, save_clip_data, set_text_keyframe,
                                         initialize_text_curves)
        from windows.views.timeline_backend.enums import MenuCopy
        import copy
        import openshot
        layer = app.project.get("layers")[-1]["number"]

        def make(text, position):
            style = dict(factory, text=text)
            data = new_text_clip(style, None, position, layer, 2)
            data["id"] = app.project.generate_id()
            asset = save_text_asset(data["direct_text"])
            data.update(file_id=asset.id, reader=copy.deepcopy(asset.data))
            save_clip_data(data)
            return data["id"]

        source, target = make("Source", 40), make("Target", 44)
        source_style = dict(Clip.get(id=source).data["direct_text"], font_size=91, stroke_width=3)
        save_text_asset(source_style, Clip.get(id=source).data["file_id"])
        save_clip_data(set_text_keyframe(Clip.get(id=source).data, "color", "#ff00ff00", 1, True))
        image_path = os.path.join(root, "red.png")
        image = QImage(32, 32, QImage.Format_ARGB32)
        image.fill(QColor("red"))
        image.save(image_path)
        native = openshot.Clip(image_path)
        video = json.loads(native.Json())
        native.Close()
        video.update(id=app.project.generate_id(), layer=layer, position=50, start=0, end=2)
        window.timeline.update_clip_data(video, only_basic_props=False, ignore_reader=False)
        video_before = copy.deepcopy(Clip.get(id=video["id"]).data)

        with patch("windows.views.timeline.StyledContextMenu.show_at", lambda menu, pos: menu):
            menu = window.timeline.ShowClipMenu(source)
        copy_menu = next(a.menu() for a in menu.actions() if a.text().replace("&", "") == "Copy")
        checks.assertIn("Text Style", [a.text() for a in copy_menu.actions()])
        keyframe_menu = next(a.menu() for a in copy_menu.actions() if a.menu())
        checks.assertTrue(next(a for a in keyframe_menu.actions() if a.text() == "Text Style").isEnabled())

        window.timeline.Copy_Triggered(MenuCopy.TEXT_STYLE, [source], [], [])
        clips_before = len(app.project.get("clips"))
        window.timeline._handle_paste_callback([], [], {"position": 0, "track": layer})
        checks.assertEqual(len(app.project.get("clips")), clips_before, "A style alone is not a clip")
        window.timeline._handle_paste_callback([target, video["id"]], [], {"position": 0, "track": layer})
        pasted = Clip.get(id=target).data
        checks.assertEqual((pasted["direct_text"]["font_size"], pasted["direct_text"]["stroke_width"]), (91, 3))
        checks.assertEqual(pasted["direct_text"]["text"], "Target")
        checks.assertEqual(pasted["text_style_overrides"], ["color"])
        checks.assertEqual(pasted["text_color"], Clip.get(id=source).data["text_color"])
        checks.assertIn("color", pasted["reader"]["text_animation"])
        checks.assertEqual(Clip.get(id=video["id"]).data, video_before)
        app.updates.undo()
        checks.assertEqual(Clip.get(id=target).data["direct_text"]["font_size"], factory["font_size"])
        checks.assertEqual(Clip.get(id=target).data["text_style_overrides"], [])
        app.updates.redo()

        # Copy > Keyframes > Text Style: only the clip's own text curves, and
        # Keyframes > All includes them; a video clip ignores text keyframes.
        save_clip_data(initialize_text_curves(dict(Clip.get(id=target).data, text_style_overrides=[])))
        window.timeline.Copy_Triggered(MenuCopy.KEYFRAMES_TEXT, [source], [], [])
        window.timeline._handle_paste_callback([target], [], {"position": 0, "track": layer})
        checks.assertEqual(Clip.get(id=target).data["text_style_overrides"], ["color"])
        window.timeline.Copy_Triggered(MenuCopy.KEYFRAMES_ALL, [source], [], [])
        window.timeline._handle_paste_callback([video["id"]], [], {"position": 0, "track": layer})
        checks.assertFalse([key for key in Clip.get(id=video["id"]).data if key.startswith("text_")])

        # Choosing a color for a transparent background starts opaque.
        # Dialogs left for interpreter exit intermittently crash PyQt5's
        # cleanup, so each is deleted here, and this one has no parent.
        picker = ColorPicker(QColor(0, 0, 0, 0))
        checks.assertEqual(picker.currentColor().alpha(), 255)
        picker.reject()
        picker.deleteLater()
        app.processEvents()
        passed = True
        print("TEXT_FEEDBACK_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


checks.assertTrue(app.gui())
QTimer.singleShot(4000, verify)
app.exec_()
sys.exit(0 if passed else 1)
