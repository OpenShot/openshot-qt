"""
 @file
 @brief Regression tests for launch.py handling of a failed app startup
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os
import sys
import types
import unittest
from unittest.mock import MagicMock

SRC = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _fake(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class LaunchStartupErrorTests(unittest.TestCase):
    """launch.main() must handle a failed OpenShotApp construction gracefully.

    Regression for issue #6099: when the engine failed to import on macOS,
    `app` stayed None and `except Exception: app.show_errors()` crashed with
    AttributeError instead of showing the real startup error.
    """

    FAKES = ("qt_api", "classes.app", "classes.info", "classes.logger_libopenshot",
             "classes.http_client", "classes.sentry")

    def setUp(self):
        self.saved = {name: sys.modules.get(name) for name in self.FAKES}

        qt = MagicMock()
        _fake("qt_api", QtCore=qt, QtWidgets=MagicMock())
        _fake("classes.info",
              SETUP={"version": "test"}, VERSION="test", PATH=SRC,
              SUPPORTED_LANGUAGES=[], setup_userdirs=lambda: None)
        _fake("classes.logger_libopenshot", configure=lambda **kw: None)
        _fake("classes.http_client", configure_ssl_environment=lambda: None)
        _fake("classes.sentry", init_tracing=lambda: None)
        self.app_module = _fake("classes.app")

        sys.modules.pop("launch", None)
        import launch  # noqa: E402
        self.launch = launch
        self.launch.app = None
        self.argv = sys.argv
        sys.argv = ["openshot-qt"]

    def tearDown(self):
        sys.argv = self.argv
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        sys.modules.pop("launch", None)

    def test_failed_construction_shows_startup_error_not_attributeerror(self):
        class BoomApp:
            def __init__(self, argv):
                raise ImportError("simulated engine import failure")

        shown = []

        class StartupError:
            def __init__(self, title="", message="", level="warning"):
                self.title, self.message, self.level = title, message, level

            def show(self):
                shown.append(self.message)
                raise SystemExit(self.message)

        self.app_module.OpenShotApp = BoomApp
        self.app_module.StartupError = StartupError

        with self.assertRaises(SystemExit) as ctx:
            self.launch.main()

        self.assertIn("simulated engine import failure", str(ctx.exception))
        self.assertEqual(shown, [ctx.exception.args[0]])

    def test_successful_construction_never_shows_errors(self):
        class OkApp:
            def __init__(self, argv):
                pass

            def show_errors(self):
                raise AssertionError("show_errors must not be called on the happy path")

            def setApplicationName(self, name):
                pass

            def setApplicationVersion(self, version):
                pass

            def setDesktopFile(self, name):
                pass

            def gui(self):
                return False

        self.app_module.OpenShotApp = OkApp
        self.app_module.StartupError = MagicMock()

        self.launch.main()

        self.app_module.StartupError.assert_not_called()


if __name__ == "__main__":
    unittest.main()