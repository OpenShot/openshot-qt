"""Regression tests for location-aware desktop file dialogs."""

import os
import sys
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

import qt_api


class LocationFileDialogTests(unittest.TestCase):
    def test_portal_theme_uses_qt_dialog(self):
        expected = qt_api.QtWidgets.QFileDialog.DontUseNativeDialog
        with patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "xdgdesktopportal"}):
            self.assertEqual(qt_api.location_file_dialog_options(), expected)

    def test_other_themes_keep_native_dialog(self):
        with patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "gtk3"}):
            self.assertIsNone(qt_api.location_file_dialog_options())

    def test_open_dialog_preserves_directory_with_portal_theme(self):
        selected = [qt_api.QtCore.QUrl.fromLocalFile("/media/recent/video.mp4")]
        callback_results = []

        with patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "xdgdesktopportal"}), \
                patch.object(qt_api, "_is_android_runtime", return_value=False), \
                patch.object(qt_api.QtWidgets.QFileDialog, "getOpenFileUrls",
                             return_value=(selected, "")) as get_urls:
            qt_api.show_open_file_dialog(
                None, "Import", "/media/recent", "", callback_results.extend)

        self.assertEqual(callback_results, selected)
        self.assertEqual(get_urls.call_args.args[2].toLocalFile(), "/media/recent")
        self.assertEqual(
            get_urls.call_args.kwargs["options"],
            qt_api.QtWidgets.QFileDialog.DontUseNativeDialog,
        )

    def test_save_dialog_preserves_directory_with_portal_theme(self):
        callback_results = []

        with patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "xdgdesktopportal"}), \
                patch.object(qt_api, "_is_android_runtime", return_value=False), \
                patch.object(qt_api.QtWidgets.QFileDialog, "getSaveFileName",
                             return_value=("/projects/recent/movie.osp", "")) as get_name:
            qt_api.show_save_file_dialog(
                None, "Save", "movie.osp", "*/*", callback_results.append,
                directory="/projects/recent",
            )

        self.assertEqual(callback_results, ["/projects/recent/movie.osp"])
        self.assertEqual(get_name.call_args.args[2], "/projects/recent/movie.osp")
        self.assertEqual(
            get_name.call_args.kwargs["options"],
            qt_api.QtWidgets.QFileDialog.DontUseNativeDialog,
        )


if __name__ == "__main__":
    unittest.main()
