"""Regression tests for the painted About dialog and its animation lifecycle."""

import math
import tempfile
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

# CI discovers this file with src/tests as the import root, not src.
SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)

from qt_api import QApplication, QFile, QIODevice, QRectF, Qt
from tests.qt_test_app import ensure_app_state, get_or_create_app
from tests.source_tree import source_path


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

    def test_release_label_uses_shared_commit_check(self):
        from classes import release_details

        build = {"openshot-qt": {"CI_COMMIT_SHA": "release-sha"},
                 "build_name": "OpenShot-v4.0.1-release-candidate-123",
                 "date": "2026-09-28 12:00"}
        for release, official in (({"sha": "release-sha"}, True),
                                  ({"sha": "different"}, False),
                                  ({}, False), (None, False)):
            with self.subTest(release=release), \
                    patch.object(release_details, "get_build_details", return_value=build), \
                    patch.object(release_details, "get_release_details", return_value=release):
                result = Mock()
                self.dialog.releaseFound.connect(result)
                try:
                    self.dialog.get_release_from_http()
                    result.assert_called_once()
                    text = result.call_args.args[0]
                    self.assertEqual(" | Official" in text, official)
                    self.assertEqual("release-candidate" in text, not official)
                    self.assertIn("2026-09-28", text)
                finally:
                    self.dialog.releaseFound.disconnect(result)

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
        # Qt's minimal backend can retain an alpha channel for opaque pixmaps.
        # Verify the painted pixels, not the backend's storage format.
        image = dialog.background_cache.toImage()
        self.assertTrue(all(image.pixelColor(x, y).alpha() == 255
                            for y in range(image.height()) for x in range(image.width())))
        background = dialog.background_cache.cacheKey()
        logo = dialog.logo_cache.cacheKey()
        dialog.particle_time += 1
        dialog.particle_frame = dialog.current_particle_frame()
        dialog.grab()
        self.assertEqual(dialog.background_cache.cacheKey(), background)
        self.assertEqual(dialog.logo_cache.cacheKey(), logo)
        dialog.resize(860, 580)
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

    def test_gpu_diagnostics_stay_in_copied_version_info(self):
        diagnostics = Mock()
        diagnostics.copy_lines.return_value = ['GPU: Test GPU', 'GPU driver: test']
        self.dialog.app.gpu_diagnostics = diagnostics
        with patch.object(self.dialog, "get_performance_details", return_value=[]):
            copied = self.dialog.build_version_info_markdown()
        self.assertIn('- **GPU:** Test GPU', copied)
        self.assertFalse(hasattr(self.dialog, 'gpuBadge'))

    def test_copied_details_use_markdown_bullets(self):
        with patch.object(self.dialog, 'get_performance_details', return_value=['Cache: Memory']):
            text = self.dialog.build_version_info_markdown()
        heading, blank, *details = text.splitlines()
        self.assertEqual(heading, '**OpenShot Version Info**')
        self.assertEqual(blank, '')
        self.assertTrue(all(line.startswith('- **') for line in details))
        self.assertIn('- **Libraries:** Video ', text)
        self.assertIn('- **Cache:** Memory', text)

    def test_source_checkout_has_four_rows_without_frozen_metadata(self):
        self.dialog.source_details = dict(branch='about-audio-version', commit='1234abcd')
        with patch('windows.about.release_details.get_build_details', return_value={}):
            self.dialog.display_release('')
        self.assertEqual(self.dialog.lblBuildValue.text(), 'Local')
        self.assertEqual(self.dialog.lblReleasedValue.text(), 'Not recorded')
        self.assertIn('Source checkout', self.dialog.lblCommitValue.text())
        for key in ('Library', 'Released', 'Build', 'Commit'):
            self.assertTrue(getattr(self.dialog, 'lbl%sValue' % key).isVisible())

    def test_audio_version_comes_from_runtime_in_dialog_and_clipboard(self):
        with patch('windows.about.openshot.GetAudioVersion', create=True, return_value='9.8.7-dev2'), \
                patch('windows.about.release_details.get_build_details', return_value={}), \
                patch.object(self.dialog, 'get_performance_details', return_value=[]):
            self.dialog.display_release('')
            self.assertIn('Audio 9.8.7-dev2', self.dialog.lblLibraryValue.text())
            self.assertIn('Audio 9.8.7-dev2', self.dialog.build_version_info_markdown())

    def test_build_types_keep_pipeline_number_and_date(self):
        for name, release, expected in (
                ('OpenShot-v4.2.0-dev1-daily-18760-abc-def', None, 'Daily | 18760'),
                ('OpenShot-v4.2.0-release-candidate-18760-abc-def', None, 'RC | 18760'),
                ('OpenShot-v4.2.0-release-candidate-18760-abc-def', {'sha': 'abc'}, 'Release | 18760')):
            metadata = {'build_name': name, 'date': '2026-11-13 12:00',
                        'openshot-qt': {'CI_COMMIT_SHA': 'abc', 'CI_PIPELINE_ID': '18760'}}
            self.dialog.release_metadata = release
            with self.subTest(expected=expected), \
                    patch('windows.about.release_details.get_build_details', return_value=metadata):
                self.dialog.display_release('')
                self.assertEqual(self.dialog.lblBuildValue.text(), expected)
                self.assertEqual(self.dialog.lblReleasedValue.text(), 'November 13, 2026')

    def test_build_matrix_matches_dialog_and_copied_output(self):
        daily = {'build_name': 'OpenShot-v4.2.0-dev1-daily-18760-abc-def',
                 'date': '2026-11-13 12:00', 'openshot-qt': {'CI_COMMIT_SHA': 'abc'}}
        candidate = dict(daily, build_name='OpenShot-v4.2.0-release-candidate-18760-abc-def')
        cases = [
            ('release recorded offline', dict(daily, build_name='OpenShot-v4.2.0'), None, {}, 'exe', 'Release', 'November 13, 2026'),
            ('promoted release', candidate, {'sha': 'abc'}, {}, 'appimage', 'Release | 18760', 'November 13, 2026'),
            ('candidate offline', candidate, None, {}, 'appbundle', 'RC | 18760', 'November 13, 2026'),
            ('daily name number', daily, None, {}, 'msix', 'Daily | 18760', 'November 13, 2026'),
            ('daily pipeline number', dict(daily, **{'openshot-qt': {'CI_PIPELINE_ID': 19000}}), None, {}, 'appimage', 'Daily | 19000', 'November 13, 2026'),
            ('source checkout', {}, None, {'branch': 'develop'}, 'unknown', 'Local', 'Not recorded'),
            ('local frozen', {'build_type': 'local', 'date': '2026-11-13 12:00'}, None, {}, 'exe', 'Local', 'November 13, 2026'),
            ('flatpak', {}, None, {}, 'flatpak', 'External', 'Not recorded'),
            ('snap', {}, None, {}, 'snap', 'External', 'Not recorded'),
            ('package manager', {}, None, {}, 'unknown', 'External', 'Not recorded'),
            ('bad date', dict(daily, date='invalid'), None, {}, 'appimage', 'Daily | 18760', 'Not recorded'),
            ('missing number', {'build_name': 'OpenShot-v4.2.0-dev1-daily', 'openshot-qt': {'CI_PIPELINE_ID': 'NA'}}, None, {}, 'unknown', 'Daily', 'Not recorded'),
        ]
        packages = {'exe': 'Windows installer', 'appimage': 'AppImage', 'appbundle': 'macOS app',
                    'msix': 'MSIX', 'flatpak': 'Flatpak', 'snap': 'Snap'}
        for title, metadata, release, source, package, build, date in cases:
            with self.subTest(build=title), \
                    patch('windows.about.release_details.get_build_details', return_value=metadata), \
                    patch('classes.distribution.get_distribution_info', return_value={'package_type': package}), \
                    patch('classes.distribution.distribution_label', return_value='test distribution'), \
                    patch('windows.about.openshot.GetAudioVersion', create=True, return_value='1.1.0-dev1'), \
                    patch('windows.about.info.VERSION', '4.2.0' if title == 'release recorded offline' else '4.2.0-dev1'), \
                    patch.object(self.dialog, 'get_performance_details', return_value=[]):
                self.dialog.release_metadata = release
                self.dialog.source_details = source
                self.dialog.display_release('')
                copied = self.dialog.build_version_info_markdown()
                expected_package = packages.get(package, 'Source checkout' if source else 'Unknown')
                self.assertEqual(self.dialog.lblBuildValue.toolTip(), build)
                self.assertEqual(self.dialog.lblReleasedValue.toolTip(), date)
                self.assertTrue(self.dialog.lblCommitValue.toolTip().startswith(expected_package + ' | '))
                self.assertIn('- **Build:** ' + build + '\n', copied)
                self.assertIn('- **Build Date:** ' + date + '\n', copied)
                self.assertIn('- **Package:** ' + self.dialog.lblCommitValue.toolTip(), copied)
                self.assertIn('Audio 1.1.0-dev1', copied)
                for key in ('Build', 'Released', 'Library', 'Commit'):
                    self.assertTrue(getattr(self.dialog, 'lbl%sValue' % key).isVisible())
                centers = [getattr(self.dialog, 'lbl%sValue' % key).geometry().center().y()
                           for key in ('Build', 'Released', 'Library', 'Commit')]
                self.assertEqual([b - a for a, b in zip(centers, centers[1:])], [35, 35, 35])

    def test_toolbar_controls_keep_their_position_with_long_build_details(self):
        dialog = self.dialog
        button = dialog.btnCopyVersionInfo
        original = button.mapTo(dialog, button.rect().topLeft())
        build = {'openshot-qt': {'CI_COMMIT_SHA': '123456789abcdef'},
                 'libopenshot': {'CI_COMMIT_SHA': 'abcdef123456789'}}
        with patch('windows.about.release_details.get_build_details', return_value=build), \
                patch.object(dialog, 'get_build_details', return_value=(
                    'OpenShot-v4.2.0-dev1-daily-18760-e3728b21-c56f94cf', '2026-11-13')):
            dialog.display_release('Build details')
        self.app.processEvents()
        self.assertEqual(button.mapTo(dialog, button.rect().topLeft()), original)
        self.assertEqual(button.height(), dialog.pushButton_3.height())
        self.assertIn(' | ', dialog.lblCommitValue.text())
        self.assertTrue(dialog.lblBuildValue.isVisible())

    def test_long_description_keeps_logo_and_controls_separate(self):
        dialog = self.dialog
        dialog.lblAboutDescription.setText(
            "OpenShot Video Editor est un éditeur vidéo primé, gratuit et libre "
            "pour Linux, Mac, Chrome OS et Windows. " * 3)
        dialog.btnCopyVersionInfo.setText("Copier")
        self.app.processEvents()
        dialog.grab()
        self.assertLess(dialog.logo_rect.bottom(), dialog.lblAboutDescription.y())
        self.assertLess(dialog.lblAboutDescription.geometry().bottom(), dialog.aboutToolbar.y())
        self.assertEqual(dialog.btnCopyVersionInfo.y(), dialog.pushButton_3.y())

    def test_license_preserves_plain_text_and_starts_at_top(self):
        from windows.about import License
        dialog = License()
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.textBrowser.toPlainText(),
                         source_path('src/resources/license.txt').read_text())
        self.assertEqual(dialog.textBrowser.textCursor().position(), 0)
        self.assertGreater(dialog.height(), dialog.width() * 0.9)

    def test_changelog_reads_resources_after_empty_legacy_log(self):
        from classes import info
        from windows.about import Changelog
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(info, 'PATH', directory), \
                patch.object(self.app, 'window', Mock(), create=True):
            root = Path(directory)
            (root / 'settings').mkdir()
            (root / 'resources').mkdir()
            (root / 'settings' / 'openshot-qt.log').write_text('')
            (root / 'resources' / 'openshot-qt.log').write_text(
                'abcdef12 2026-11-13 Test Author  Fix dialog spacing\n')
            dialog = Changelog()
            self.addCleanup(dialog.deleteLater)
            dialog.show()
            self.app.processEvents()
            self.assertEqual(dialog.tabChangelog.count(), 1)
            from windows.views.changelog_treeview import ChangelogTreeView
            view = dialog.findChild(ChangelogTreeView)
            self.assertEqual(view.model().rowCount(), 1)
            self.assertEqual(view.model().index(0, 3).data(), 'Fix dialog spacing')
            self.assertTrue(dialog.txtChangeLogFilter_openshot_qt.isClearButtonEnabled())
            dialog.close()

    def test_changelog_empty_state_keeps_footer_available(self):
        from classes import info
        from windows.about import Changelog
        with tempfile.TemporaryDirectory() as directory, patch.object(info, 'PATH', directory):
            dialog = Changelog()
            self.addCleanup(dialog.deleteLater)
            dialog.show()
            self.app.processEvents()
            self.assertFalse(dialog.tabChangelog.isVisible())
            self.assertTrue(dialog.findChild(type(dialog.lblGitHubLink), 'lblEmptyChangelog').isVisible())
            self.assertTrue(dialog.lblGitHubLink.isVisible())
            self.assertTrue(dialog.btnclose.isVisible())
            dialog.btnclose.click()
            self.assertFalse(dialog.isVisible())

    def test_packaged_resources_match_manifest(self):
        images = source_path("images")
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
