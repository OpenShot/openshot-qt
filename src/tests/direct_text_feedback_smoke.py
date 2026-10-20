"""Text editing feedback: Properties/editor sync, box fitting, remembered and reset styles."""
import importlib
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
        dialog.restore_defaults()
        checks.assertEqual(dialog.style()["font_size"], factory["font_size"])
        checks.assertEqual(dialog.style()["text"], "Preview")
        dialog.reject()
        dialog.deleteLater()
        app.processEvents()

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
