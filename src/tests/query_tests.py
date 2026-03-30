"""
Basic smoke tests for Zenvi / OpenShot query layer.

Run headlessly:
    python3 src/tests/query_tests.py -platform minimal
"""

import os
import sys
import unittest

# Ensure src/ is on the path regardless of where the script is invoked from
SRC_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.abspath(SRC_DIR))

# Strip our own args before Qt/unittest see them (e.g. -platform minimal)
_KNOWN_QT_FLAGS = {"-platform", "-style", "-stylesheet", "-widgetcount",
                   "-reverse", "-qmljsdebugger", "-display", "-geometry"}
_clean_argv = [sys.argv[0]]
_i = 1
while _i < len(sys.argv):
    arg = sys.argv[_i]
    if arg in _KNOWN_QT_FLAGS:
        _i += 2  # skip flag and its value
    elif arg.startswith("-platform=") or arg.startswith("-style="):
        _i += 1  # skip combined form
    else:
        _clean_argv.append(arg)
        _i += 1
sys.argv = _clean_argv


# ── Minimal QApplication setup ────────────────────────────────────────────────

from PyQt5.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(["zenvi-test", "-platform", "minimal"])


# ── Tests ─────────────────────────────────────────────────────────────────────

class InfoTests(unittest.TestCase):
    """Smoke-tests for classes.info."""

    def test_version_format(self):
        from classes import info
        parts = info.VERSION.split(".")
        self.assertEqual(len(parts), 3, f"VERSION should be x.y.z, got {info.VERSION!r}")
        for p in parts:
            self.assertTrue(p.isdigit(), f"Version part {p!r} is not numeric")

    def test_product_name(self):
        from classes import info
        self.assertEqual(info.PRODUCT_NAME, "Zenvi")

    def test_backend_url_points_to_zenvi_pro(self):
        from classes import info
        self.assertIn("zenvi.pro", info.BACKEND_URL,
                      f"BACKEND_URL should point to zenvi.pro, got {info.BACKEND_URL!r}")

    def test_paths_are_strings(self):
        from classes import info
        for attr in ("PATH", "USER_PATH", "PROFILES_PATH", "RESOURCES_PATH"):
            val = getattr(info, attr, None)
            self.assertIsInstance(val, str, f"info.{attr} should be a string")


class SettingsTests(unittest.TestCase):
    """Smoke-tests for classes.settings."""

    def test_settings_loads(self):
        from classes.settings import SettingStore
        s = SettingStore()
        # Should be able to instantiate without error
        self.assertIsNotNone(s)

    def test_default_settings_file_exists(self):
        from classes import info
        default = os.path.join(info.PATH, "settings", "_default.settings")
        self.assertTrue(os.path.exists(default),
                        f"Default settings file not found: {default}")


class AuthManagerTests(unittest.TestCase):
    """Verify auth manager constants."""

    def test_zenvi_website_is_pro(self):
        from classes.auth_manager import ZENVI_WEBSITE
        self.assertNotIn("zenvi.app", ZENVI_WEBSITE,
                         "ZENVI_WEBSITE must not point to zenvi.app")
        self.assertIn("zenvi.pro", ZENVI_WEBSITE,
                      f"ZENVI_WEBSITE should be zenvi.pro, got {ZENVI_WEBSITE!r}")

    def test_supabase_url_configured(self):
        from classes.auth_manager import SUPABASE_URL
        self.assertTrue(SUPABASE_URL.startswith("https://"),
                        f"SUPABASE_URL should be an https URL, got {SUPABASE_URL!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
