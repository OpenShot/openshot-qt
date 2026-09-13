"""Regression tests for the painted About dialog and its animation lifecycle."""

import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

# CI discovers this file with src/tests as the import root, not src.
SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)

from qt_api import QApplication, QFile, QIODevice, QRectF, Qt
from tests.qt_test_app import ensure_app_state, get_or_create_app


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
        }

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class AboutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))
        ensure_app_state(cls.app, DummySettings)
        from classes import openshot_rc  # noqa: F401; registers packaged artwork
        from windows.about import About
        cls.About = About

    def setUp(self):
        app_state = types.SimpleNamespace(_tr=lambda text: text, clipboard=self.app.clipboard)
        for target, kwargs in (
                ("windows.about.get_app", {"return_value": app_state}),
                ("windows.about.track_metric_screen", {}),
                ("windows.about.ui_util.center", {}),
                ("windows.about.About.get_current_release", {})):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = self.About()
        self.dialog.display_release("Version 4.0.0<br>libopenshot: 1.0.0")
        self.dialog.show()
        self.app.processEvents()
        self.dialog.grab()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def test_timer_lifecycle(self):
        dialog = self.dialog
        self.assertTrue(dialog.particle_timer.isActive())
        self.assertEqual(dialog.particle_timer.interval(), 50)
        self.assertIs(dialog.particle_timer.parent(), dialog)
        dialog.hide()
        self.assertFalse(dialog.particle_timer.isActive())
        previous_time = dialog.particle_time
        dialog.show()
        self.app.processEvents()
        self.assertTrue(dialog.particle_timer.isActive())
        self.assertEqual(dialog.particle_time, previous_time)
        dialog.showMinimized()
        self.app.processEvents()
        self.assertFalse(dialog.particle_timer.isActive())
        dialog.showNormal()
        self.app.processEvents()
        self.assertTrue(dialog.particle_timer.isActive())
        dialog.reject()
        self.assertFalse(dialog.particle_timer.isActive())

    def test_cache_reuse_and_resize(self):
        dialog = self.dialog
        dialog.particle_timer.stop()
        self.assertEqual(dialog.objectName(), "aboutDialog")
        self.assertTrue(dialog.testAttribute(Qt.WA_OpaquePaintEvent))
        self.assertFalse(dialog.background_cache.hasAlphaChannel())
        background = dialog.background_cache.cacheKey()
        logo = dialog.logo_cache.cacheKey()
        dialog.particle_time += 1
        dialog.particle_frame = dialog.current_particle_frame()
        dialog.grab()
        self.assertEqual(dialog.background_cache.cacheKey(), background)
        self.assertEqual(dialog.logo_cache.cacheKey(), logo)
        dialog.resize(720, 480)
        self.app.processEvents()
        dialog.grab()
        self.assertNotEqual(dialog.background_cache.cacheKey(), background)
        self.assertTrue(dialog.about_logo.isValid())
        self.assertLess(dialog.logo_rect.bottom(), dialog.lblAboutDescription.y())
        self.assertLess(dialog.logo_cache.height(), dialog.background_cache.height())

    def test_fractional_and_high_dpi_cache_invalidation(self):
        dialog = self.dialog
        previous_key = dialog.background_cache.cacheKey()
        for ratio in (1.25, 2.0, 1.0):
            with self.subTest(ratio=ratio), patch.object(dialog, "devicePixelRatioF", return_value=ratio):
                dialog.grab()
                self.assertNotEqual(dialog.background_cache.cacheKey(), previous_key)
                self.assertEqual(dialog.background_cache.devicePixelRatioF(), ratio)
                self.assertEqual(dialog.background_cache.width(), math.ceil(dialog.width() * ratio))
                self.assertEqual(dialog.logo_cache.devicePixelRatioF(), ratio)
                self.assertTrue(all(sprite.devicePixelRatioF() == ratio for sprite in dialog.particle_sprites))
                previous_key = dialog.background_cache.cacheKey()

    def test_motion_stays_bounded_and_visible_over_long_runs(self):
        dialog = self.dialog
        dialog.particle_timer.stop()
        self.assertEqual(len(dialog.particles), 28)
        dialog.particle_time = 0
        first = dialog.current_particle_frame()
        dialog.particle_time = 1
        second = dialog.current_particle_frame()
        for before, after in zip(first, second):
            distance = (before[1] - after[1]) % dialog.height()
            self.assertGreaterEqual(distance, 9)
            self.assertLessEqual(distance, 22)
        for t in (0, 60, 3600, 86400):
            dialog.particle_time = t
            for x, y, opacity, sprite in dialog.current_particle_frame():
                self.assertTrue(0 <= x < dialog.width())
                self.assertTrue(0 <= y < dialog.height())
                self.assertTrue(0 <= opacity <= 1)
                self.assertTrue(0 <= sprite < len(dialog.particle_sprites))

    def test_dirty_region_covers_old_and_new_positions_without_wrap_strip(self):
        dialog = self.dialog
        dialog.particle_timer.stop()
        dialog.particle_frame = [(20, 2, 0.3, 0)]
        new_frame = [(20, dialog.height() - 2, 0.3, 0)]
        clock = types.SimpleNamespace(restart=lambda: 50)
        with patch.object(dialog, "particle_clock", clock), \
                patch.object(dialog, "current_particle_frame", return_value=new_frame), \
                patch.object(dialog, "update") as update:
            dialog.advance_particles()
        region = update.call_args[0][0]
        for x, y in ((20, 2), (20, dialog.height() - 2)):
            self.assertTrue(region.contains(QRectF(x - 6, y - 6, 12, 12).toAlignedRect()))
        self.assertFalse(region.intersects(QRectF(0, 100, dialog.width(), 10).toAlignedRect()))

    def test_copy_and_close_controls(self):
        dialog = self.dialog
        with patch.object(dialog, "build_version_info_markdown", return_value="About test version"):
            dialog.btnCopyVersionInfo.click()
        self.assertEqual(self.app.clipboard().text(), "About test version")
        self.assertTrue(dialog.copy_feedback_label.isVisible())
        dialog.hide_copy_confirmation()
        self.assertFalse(dialog.copy_feedback_label.isVisible())
        dialog.pushButton_3.click()
        self.assertFalse(dialog.isVisible())
        self.assertFalse(dialog.particle_timer.isActive())

    def test_long_description_keeps_logo_and_controls_separate(self):
        dialog = self.dialog
        dialog.lblAboutDescription.setText(
            "OpenShot Video Editor est un éditeur vidéo primé, gratuit et libre "
            "pour Linux, Mac, Chrome OS et Windows. " * 3)
        dialog.btnCopyVersionInfo.setText("Copier")
        self.app.processEvents()
        dialog.grab()
        self.assertLess(dialog.logo_rect.bottom(), dialog.lblAboutDescription.y())
        self.assertLess(dialog.lblAboutDescription.geometry().bottom(), dialog.txtversion.y())
        self.assertLess(dialog.btnCopyVersionInfo.geometry().bottom(), dialog.pushButton_3.y())

    def test_packaged_resources_match_manifest(self):
        images = Path(__file__).resolve().parents[2] / "images"
        for resource in ET.parse(str(images / "openshot.qrc")).getroot():
            for entry in resource:
                name = ":" + resource.get("prefix").rstrip("/") + "/" + entry.get("alias", entry.text)
                with self.subTest(resource=name):
                    file = QFile(name)
                    self.assertTrue(file.open(QIODevice.ReadOnly))
                    self.assertEqual(bytes(file.readAll()), (images / entry.text).read_bytes())
                    file.close()
        self.assertFalse(QFile.exists(":/about/AboutLogo.png"))
        self.assertFalse(QFile.exists(":/about/AboutLogo@2x.png"))


if __name__ == "__main__":
    unittest.main()
