"""Export profile discovery when the optional user directory is missing."""

import os
import importlib
import sys
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

class ExportProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        metrics = ModuleType("classes.metrics")
        metrics.track_metric_screen = Mock()
        metrics.track_metric_error = Mock()
        with patch.dict(sys.modules, {"classes.metrics": metrics}):
            cls.export = importlib.import_module("windows.export")

    def test_missing_user_directory_still_loads_installed_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "installed"
            installed.mkdir()
            profile = installed / "720p"
            profile.write_text("description=HD 720p\nframe_rate_num=30\nframe_rate_den=1\n"
                               "width=1280\nheight=720\nprogressive=1\nsample_aspect_num=1\n"
                               "sample_aspect_den=1\ndisplay_aspect_num=16\ndisplay_aspect_den=9\n"
                               "colorspace=709\n")
            dialog = SimpleNamespace(cboProfile=Mock(), getProfileName=lambda path: path)
            dialog.getProfilePath = lambda name: dialog.profile_paths[name]
            app = SimpleNamespace(project=Mock())
            app.project.get.return_value = "HD 720p"
            with patch.object(self.export, "get_app", return_value=app), \
                    patch.object(self.export.info, "USER_PROFILES_PATH", os.path.join(directory, "missing")), \
                    patch.object(self.export.info, "PROFILES_PATH", str(installed)):
                self.export.Export.load_profiles(dialog)
            self.assertEqual(dialog.profile_paths, {"HD 720p (1280x720)": str(profile)})
            self.assertEqual(dialog.selected_profile, "HD 720p (1280x720)")
            dialog.cboProfile.addItem.assert_called_once_with(str(profile), str(profile))

    def test_gpu_targets_follow_compiled_encoders_with_visible_badges(self):
        from qt_api import QApplication, QComboBox
        from tests.qt_test_app import get_or_create_app
        self.__class__.app, _ = get_or_create_app(lambda: QApplication([]))
        targets = {
            'h264_nvenc': 'MP4 (h.264 nv)',
            'hevc_nvenc': 'MP4 (h.265 nvenc)',
            'h264_qsv': 'MP4 (h.264 qsv)',
            'hevc_qsv': 'MP4 (h.265 qsv)',
            'h264_amf': 'MP4 (h.264 amf)',
            'hevc_amf': 'MP4 (h.265 amf)',
            'h264_videotoolbox': 'MP4 (h.264 videotoolbox)',
        }
        for available in (set(targets), {'h264_videotoolbox'}, set()):
            with self.subTest(available=available), tempfile.TemporaryDirectory() as user_presets:
                combo = QComboBox()
                dialog = SimpleNamespace(cboSimpleTarget=combo)
                selector = Mock()
                selector.itemData.return_value = 'All Formats'
                writer = SimpleNamespace(IsValidCodec=lambda codec: codec in available or codec == 'libx264')
                with patch.object(self.export, 'get_app', return_value=SimpleNamespace(_tr=lambda text: text)), \
                        patch.object(self.export.info, 'USER_PRESETS_PATH', user_presets), \
                        patch.object(self.export.openshot, 'FFmpegWriter', writer):
                    self.export.Export.cboSimpleProjectType_index_changed(dialog, selector, 0)
                shown = {combo.itemText(index): index for index in range(combo.count())}
                self.assertIn('MP4 (h.264)', shown)
                for codec, title in targets.items():
                    self.assertEqual(title in shown, codec in available, codec)
                    if title in shown:
                        self.assertFalse(combo.itemIcon(shown[title]).isNull(), codec)
                combo.deleteLater()
