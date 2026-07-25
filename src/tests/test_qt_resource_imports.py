"""Tests for binding-neutral generated Qt resource modules."""

import importlib.util
from pathlib import Path
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = SOURCE_ROOT / "language" / "neutralize_resource_import.py"


def load_helper():
    spec = importlib.util.spec_from_file_location(
        "neutralize_resource_import", HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QtResourceImportTests(unittest.TestCase):
    def test_checked_in_resource_modules_use_qt_api(self):
        resource_modules = (
            SOURCE_ROOT / "classes" / "openshot_rc.py",
            SOURCE_ROOT / "language" / "openshot_lang.py",
        )
        for resource_module in resource_modules:
            with self.subTest(resource_module=resource_module.name):
                source = resource_module.read_text(encoding="utf-8")
                self.assertIn("from qt_api import QtCore", source)
                self.assertNotRegex(
                    source, r"from (PyQt5|PyQt6|PySide6) import QtCore"
                )

    def test_neutralizes_supported_resource_compiler_imports(self):
        helper = load_helper()
        for binding_import in helper.BINDING_IMPORTS:
            with self.subTest(binding_import=binding_import):
                source = "{}\nQtCore.qVersion()\n".format(binding_import)
                updated = helper.neutralize_import(source)
                self.assertIn(helper.NEUTRAL_IMPORT, updated)
                self.assertNotIn(binding_import, updated)

    def test_rejects_unrecognized_generated_import(self):
        helper = load_helper()
        with self.assertRaisesRegex(ValueError, "No supported QtCore import"):
            helper.neutralize_import("from UnknownQt import QtCore\n")


if __name__ == "__main__":
    unittest.main()
