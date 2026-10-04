"""Isolate the real Properties dock/timeline/menu layout regression."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class PropertiesAnchorTests(unittest.TestCase):
    def test_clip_context_properties_preserves_edge_screen_x(self):
        env = dict(os.environ,
                   PYTHONPATH=os.pathsep.join(filter(None, (str(Path(__file__).resolve().parents[1]), os.environ.get("PYTHONPATH", "")))),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("properties_anchor_smoke.py"))],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout[-12000:])
        self.assertNotIn("Traceback (most recent call last)", result.stdout, result.stdout[-12000:])
        self.assertIn("PROPERTIES_ANCHOR_PASSED", result.stdout)
