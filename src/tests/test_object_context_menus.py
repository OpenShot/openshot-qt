"""Context-menu commands must target the requested objects and remain undoable."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

import openshot


class ObjectContextMenuTests(unittest.TestCase):
    def test_object_menus_and_complete_track_moves(self):
        source = Path(__file__).resolve().parents[1]
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   PYTHONPATH=os.pathsep.join(filter(None, (str(source),
                       os.path.dirname(os.path.abspath(openshot.__file__)), os.environ.get("PYTHONPATH")))))
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("object_context_menus_smoke.py"))],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout[-18000:])
        self.assertIn("OBJECT_MENUS_PASSED", result.stdout)
