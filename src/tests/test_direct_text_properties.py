"""Properties dock regression coverage for editable text clips."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class DirectTextPropertiesTests(unittest.TestCase):
    def test_real_properties_dock_and_undo(self):
        env = dict(os.environ,
                   PYTHONPATH=os.pathsep.join(filter(None, (str(Path(__file__).resolve().parents[1]), os.environ.get("PYTHONPATH", "")))),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("direct_text_properties_smoke.py"))],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout[-14000:])
        self.assertNotIn("Traceback (most recent call last)", result.stdout, result.stdout[-14000:])
        self.assertIn("TEXT_PROPERTIES_PASSED", result.stdout)
