# @file
# @brief Run the Properties dock regression in an isolated process
# @author OpenShot Studios, LLC
#
# @section LICENSE
#
# Copyright (c) 2008-2026 OpenShot Studios, LLC
# (http://www.openshotstudios.com). This file is part of
# OpenShot Video Editor (http://www.openshot.org), an open-source project
# dedicated to delivering high quality video editing and animation solutions
# to the world.
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
#

"""Isolate the real Properties dock/timeline/menu layout regression."""
import os
from pathlib import Path
# Isolate the GUI test in its own Python process.
import subprocess  # nosec B404
import sys
import unittest


class PropertiesAnchorTests(unittest.TestCase):
    def test_clip_context_properties_preserves_edge_screen_x(self):
        source = Path(__file__).resolve().parents[1]
        # GitLab stages the native bindings in the repository root. Running a
        # script uses its own directory as sys.path[0], unlike unittest's -m run.
        # Keep explicitly selected bindings ahead of that staged fallback.
        python_path = (str(source), os.environ.get("PYTHONPATH", ""), str(source.parent))
        env = dict(os.environ,
                   PYTHONPATH=os.pathsep.join(filter(None, python_path)),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        # Run our adjacent test script with the current interpreter, without a shell.
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("properties_anchor_smoke.py"))],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=90, shell=False)  # nosec B603
        self.assertEqual(result.returncode, 0, result.stdout[-12000:])
        self.assertNotIn("Traceback (most recent call last)", result.stdout, result.stdout[-12000:])
        self.assertIn("PROPERTIES_ANCHOR_PASSED", result.stdout)
