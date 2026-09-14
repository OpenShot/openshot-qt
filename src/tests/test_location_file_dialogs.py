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
    def setUp(self):
        portal = patch.object(qt_api, "_portal_file_dialog", return_value=None)
        self.portal = portal.start()
        self.addCleanup(portal.stop)

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

    def test_native_open_and_cancel_do_not_open_fallback(self):
        selected = [qt_api.QtCore.QUrl.fromLocalFile("/media/vidéo one.mp4")]
        for result in (selected, []):
            with self.subTest(result=result), patch.object(
                    qt_api.QtWidgets.QFileDialog, "getOpenFileUrls") as fallback:
                self.portal.return_value = result
                received = []
                qt_api.show_open_file_dialog(None, "Import", "/media", "Video (*.mp4)", received.append)
                self.assertEqual(received, [result])
                self.portal.assert_called_with(
                    None, "Import", "/media", file_filter="Video (*.mp4)", multiple=True)
                fallback.assert_not_called()

    def test_single_file_fallback(self):
        selected = qt_api.QtCore.QUrl.fromLocalFile("/projects/test.osp")
        for result in (selected, qt_api.QtCore.QUrl()):
            with self.subTest(result=result), patch.object(
                    qt_api.QtWidgets.QFileDialog, "getOpenFileUrl",
                    return_value=(result, "")) as fallback:
                received = []
                qt_api.show_open_file_dialog(
                    None, "Open", "/projects", "Project (*.osp)", received.append, allow_multiple=False)
                self.assertEqual(received, [[selected]] if not result.isEmpty() else [[]])
                self.assertFalse(self.portal.call_args.kwargs["multiple"])
                fallback.assert_called_once()

    def test_native_save_and_cancel_do_not_open_fallback(self):
        selected = qt_api.QtCore.QUrl.fromLocalFile("/projects/vidéo one.osp")
        for result, expected in (([selected], selected.toLocalFile()), ([], "")):
            with self.subTest(result=result), patch.object(
                    qt_api.QtWidgets.QFileDialog, "getSaveFileName") as fallback:
                self.portal.return_value = result
                received = []
                qt_api.show_save_file_dialog(None, "Save", "vidéo one.osp", "*/*",
                                             received.append, directory="/projects")
                self.assertEqual(received, [expected])
                self.portal.assert_called_with(None, "Save", "/projects", save_name="vidéo one.osp")
                fallback.assert_not_called()

    def test_folder_native_cancel_and_fallback(self):
        selected = qt_api.QtCore.QUrl.fromLocalFile("/exports/new")
        with patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "xdgdesktopportal"}), \
                patch.object(qt_api.QtWidgets.QFileDialog, "getExistingDirectory",
                             return_value="/exports/qt") as fallback:
            for result, expected in (([selected], "/exports/new"), ([], "")):
                self.portal.return_value = result
                self.assertEqual(qt_api.get_existing_directory(None, "Export", "/exports"), expected)
                fallback.assert_not_called()
            self.portal.return_value = None
            self.assertEqual(qt_api.get_existing_directory(None, "Export", "/exports"), "/exports/qt")
            fallback.assert_called_once_with(
                None, "Export", "/exports", options=(qt_api.QtWidgets.QFileDialog.DontUseNativeDialog
                                                     | qt_api.QtWidgets.QFileDialog.ShowDirsOnly))

    def test_android_open_bypasses_desktop_portal(self):
        with patch.object(qt_api, "_is_android_runtime", return_value=True), \
                patch.object(qt_api, "_get_callback_bridge"), \
                patch.object(qt_api, "_AndroidFilePicker") as picker:
            qt_api.show_open_file_dialog(None, "Import", "", "", lambda urls: None)
            picker.return_value.open.assert_called_once()
            self.portal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
