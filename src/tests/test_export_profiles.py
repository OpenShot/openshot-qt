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

    def test_export_choices_distinguish_missing_nvenc_from_unavailable_vulkan(self):
        from qt_api import QApplication, QComboBox, QSize, Qt
        from classes.export_settings import encoder_support
        self.__class__.app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "installed"
            user = Path(directory) / "user"
            installed.mkdir(); user.mkdir()
            for title, codec in (("CPU", "libx264"), ("NVIDIA", "h264_nvenc"), ("Vulkan", "h264_vulkan")):
                (installed / (title + ".xml")).write_text(
                    "<export-option><type>All Formats</type><title>%s</title>"
                    "<videocodec>%s</videocodec></export-option>" % (title, codec))
            api = SimpleNamespace(FFmpegWriter=SimpleNamespace(IsValidCodec=Mock(
                side_effect=lambda codec: codec != "h264_nvenc")), GpuEncoders=Mock(return_value=[]))
            target = QComboBox()
            project = QComboBox(); project.addItem("All Formats", "All Formats")
            dialog = SimpleNamespace(cboSimpleTarget=target)
            with patch.object(self.export, "get_app", return_value=SimpleNamespace(_tr=lambda text: text)), \
                    patch.object(self.export.info, "EXPORT_PRESETS_PATH", str(installed)), \
                    patch.object(self.export.info, "USER_PRESETS_PATH", str(user)), \
                    patch.object(self.export, "encoder_support", side_effect=lambda codec: encoder_support(codec, api, {})), \
                    patch.object(self.export.log, "info") as log_info:
                self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                self.assertEqual([target.itemText(n) for n in range(target.count())], ["CPU"])
                details = log_info.call_args.args[1]
                self.assertIn("not included", details["h264_nvenc"]["reason"])
                self.assertIn("did not open", details["h264_vulkan"]["reason"])
                self.assertEqual(target.iconSize(), QSize(64, 22))
                self.assertIn("Software encoder", target.itemData(0, Qt.ToolTipRole))
                api.FFmpegWriter.IsValidCodec.side_effect = lambda codec: True
                self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                self.assertEqual([target.itemText(n) for n in range(target.count())], ["CPU", "NVIDIA"])
                self.assertFalse(target.itemIcon(1).isNull())
