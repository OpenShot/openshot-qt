"""Real Qt layout, native reader, and full application text workflow coverage."""
import copy
import json
import os
from pathlib import Path
import subprocess  # nosec B404 - Launch controlled local processes without a shell.
import sys
import tempfile
import unittest

from qt_api import QApplication, QImage
from tests.qt_test_app import get_or_create_app
from classes.direct_text import default_text, apply_text, new_text_clip, render_text
import openshot


def smoke_python_path():
    """Import path for smoke scripts: src, plus wherever this process found
    openshot (CI copies it into the working directory, which a script's
    subprocess does not search)."""
    paths = [str(Path(__file__).resolve().parents[1]), os.path.dirname(os.path.abspath(openshot.__file__)),
             os.environ.get("PYTHONPATH", "")]
    return os.pathsep.join(filter(None, paths))


class DirectTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))

    def test_native_reader_unicode_alpha_and_immutable_history(self):
        with tempfile.TemporaryDirectory() as root:
            style = default_text(640, 360)
            style.update(text="café\nالعربية 🎉", font_family="Font That Does Not Exist", color="#ff0000")
            original = new_text_clip(style, root, 0, 1000000, 4)
            reader = openshot.Clip()
            reader.SetJson(json.dumps(original))
            reader.Open()
            frame = reader.GetFrame(1)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(), frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
            reader.Close()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            colors = [image.pixelColor(x, y) for y in range(image.height()) for x in range(image.width())]
            self.assertTrue(any(c.alpha() > 0 and c.red() > c.green() for c in colors))
            changed = copy.deepcopy(original["direct_text"])
            changed["text"] += "\n" + "wrapping words " * 100
            edited = apply_text(original, changed, root)
            self.assertGreater(edited["direct_text"]["height"], original["direct_text"]["height"])
            self.assertNotEqual(edited["reader"]["text"], original["reader"]["text"])
            self.assertEqual(original["reader"]["type"], "QtTextReader")
            self.assertFalse(original["reader"]["path"])
            self.assertTrue(os.path.exists(render_text(edited["direct_text"], root)))
            self.assertEqual(original["direct_text"]["text"], style["text"])

    def test_editor_layout_matches_native_styling(self):
        from qt_api import QColor, QPainter, QPen, QRectF, QAbstractTextDocumentLayout, QPalette, Qt
        from classes.direct_text import text_document
        style = default_text(640, 360)
        style.update(text="Styled text\nWrapping words " * 3, font_size=28, font_bold=True, line_spacing=1.4,
                     alignment="right", background_padding=18, stroke_width=1, stroke="#0000ff",
                     border_width=2, border="#00ff00", background="#80404040")
        data = new_text_clip(style, None, 0, 1000000, 4)
        style = data["direct_text"]
        expected = QImage(style["width"], style["height"], QImage.Format_ARGB32_Premultiplied)
        expected.fill(QColor(style["background"]))
        painter = QPainter(expected)
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QPalette.Text, QColor(style["color"]))
        for document in (text_document(style, outline=True), text_document(style)):
            document.documentLayout().draw(painter, context)
        pen = QPen(QColor(style["border"]), style["border_width"])
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(1, 1, style["width"] - 2, style["height"] - 2))
        painter.end()
        reader = openshot.Clip()
        reader.SetJson(json.dumps(data))
        reader.Open()
        frame = reader.GetFrame(1)
        actual = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                        frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
        reader.Close()
        self.assertEqual(expected.convertToFormat(QImage.Format_RGBA8888_Premultiplied), actual)

    def test_line_spacing_and_rounded_corners(self):
        from classes.direct_text import fit_height, reader_data, apply_line_spacing, text_document
        style = default_text(640, 360)
        style.update(text="One\nTwo\nThree", background="#ff0000ff", width=300)
        normal = fit_height(dict(style))["height"]
        spaced = fit_height(dict(style, line_spacing=1.5))["height"]
        self.assertGreater(spaced, normal * 1.3)
        # Editing can add lines without the spacing; it is reapplied once, then stable.
        document = text_document(dict(style, line_spacing=1.5))
        from qt_api import QTextCursor
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.End)
        cursor.insertBlock(document.firstBlock().blockFormat().__class__())
        self.assertTrue(apply_line_spacing(document, dict(style, line_spacing=1.5)))
        self.assertFalse(apply_line_spacing(document, dict(style, line_spacing=1.5)))

        def render(**changes):
            reader = openshot.QtTextReader()
            reader.SetJson(json.dumps(reader_data(fit_height(dict(style, **changes)), {"num": 30, "den": 1})))
            reader.Open()
            frame = reader.GetFrame(1)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                           frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
            reader.Close()
            return image
        self.assertEqual(render().pixelColor(0, 0).alpha(), 255)
        rounded = render(background_corner=24)
        self.assertEqual(rounded.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(rounded.pixelColor(0, rounded.height() // 2).alpha(), 255)

    def test_text_readers_follow_project_frame_rate(self):
        from classes.direct_text import reader_data, set_text_keyframe, sync_text_fps
        style = default_text(320, 180)
        style.update(text="", background="#ffff0000", width=160, height=90)
        reader = reader_data(style, {"num": 60000, "den": 1001})
        self.assertEqual(reader["fps"], {"num": 60000, "den": 1001})
        self.assertEqual(reader["video_timebase"], {"num": 1001, "den": 60000})

        # Background fades red -> blue across project frames 1..61 at 60 fps.
        clip = new_text_clip(style, None, 0, 1, 4)
        clip.update(id="TEXT", scale=openshot.SCALE_STRETCH)
        clip = set_text_keyframe(clip, "background", "#ffff0000", 1, True)
        clip = set_text_keyframe(clip, "background", "#ff0000ff", 61, True)
        timeline = openshot.Timeline(160, 90, openshot.Fraction(60, 1), 44100, 2, openshot.LAYOUT_STEREO)
        project = json.loads(timeline.Json())
        project.update(fps={"num": 60, "den": 1}, files=[dict(reader, id="F1")], clips=[clip])
        clip["file_id"] = "F1"
        sync_text_fps(project)
        self.assertEqual(project["files"][0]["fps"], {"num": 60, "den": 1})
        self.assertEqual(clip["reader"]["fps"], {"num": 60, "den": 1})
        timeline.SetJson(json.dumps(project))
        timeline.Open()
        try:
            frame = timeline.GetFrame(31)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                           frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
        finally:
            timeline.Close()
        middle = image.pixelColor(80, 45)
        self.assertLessEqual(abs(middle.red() - 128), 3)
        self.assertLessEqual(abs(middle.blue() - 128), 3)

    def test_old_style_names_upgrade(self):
        from classes.direct_text import upgrade_style_names, initialize_text_curves, reader_data
        style = default_text(320, 180)
        old = {"stroke": "stroke_color", "border": "border_color", "background_padding": "padding"}
        for new, previous in old.items():
            style[previous] = style.pop(new)
        style["stroke_color"] = "#ff00ff00"
        clip = {"direct_text": style, "text_stroke_color": json.loads(openshot.Color("#ff00ff00").Json()),
                "text_style_overrides": ["stroke_color", "color"]}
        self.assertTrue(upgrade_style_names(clip))
        self.assertFalse(upgrade_style_names(clip))
        for new, previous in old.items():
            self.assertIn(new, clip["direct_text"])
            self.assertNotIn(previous, clip["direct_text"])
        self.assertEqual(clip["text_style_overrides"], ["color", "stroke"])
        self.assertNotIn("text_stroke_color", clip)
        clip["reader"] = reader_data(clip["direct_text"])
        reader = initialize_text_curves(clip)["reader"]
        self.assertEqual(reader["stroke"], "#ff00ff00")
        self.assertIn("stroke", reader["text_animation"])

    def test_full_app_text_workflow(self):
        env = dict(os.environ, PYTHONPATH=smoke_python_path(),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("direct_text_smoke.py"))],  # nosec B603 - Fixed test executable and argument array; no shell.
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout[-14000:])
        self.assertNotIn("Traceback (most recent call last)", result.stdout, result.stdout[-14000:])
        self.assertIn("TEXT_WORKFLOW_PASSED", result.stdout)
