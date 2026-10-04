"""Real Qt layout, native reader, and full application text workflow coverage."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qt_api import QApplication, QImage
from tests.qt_test_app import get_or_create_app
from classes.direct_text import default_text, apply_text, new_text_clip, render_text
import openshot


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
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(), frame.GetWidth() * 4, QImage.Format_RGBA8888).copy()
            reader.Close()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            colors = [image.pixelColor(x, y) for y in range(image.height()) for x in range(image.width())]
            self.assertTrue(any(c.alpha() > 0 and c.red() > c.green() for c in colors))
            changed = copy.deepcopy(original["direct_text"])
            changed["text"] += "\n" + "wrapping words " * 100
            edited = apply_text(original, changed, root)
            self.assertGreater(edited["direct_text"]["height"], original["direct_text"]["height"])
            self.assertNotEqual(edited["reader"]["path"], original["reader"]["path"])
            self.assertTrue(os.path.exists(original["reader"]["path"]))
            self.assertEqual(render_text(edited["direct_text"], root), edited["reader"]["path"])
            self.assertEqual(original["direct_text"]["text"], style["text"])

    def test_full_app_text_workflow(self):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, (str(Path(__file__).resolve().parents[1]), os.environ.get("PYTHONPATH", "")))),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("direct_text_smoke.py"))],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout[-14000:])
        self.assertNotIn("Traceback (most recent call last)", result.stdout, result.stdout[-14000:])
        self.assertIn("TEXT_WORKFLOW_PASSED", result.stdout)
