"""Export result tab (success and failure), its labels, and opening/revealing the file."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication, QColor, QPalette, isdeleted
from classes import desktop_open
from windows.export_result import ExportResultTab, export_details, format_duration, format_label, format_size

DETAILS = [("file", "Format", "MP4 (H.264)"), ("film", "Resolution", "HD 720p 30 fps"),
           ("quality", "Quality", "High Quality"), ("size", "File Size", "12.4 MB"),
           ("clock", "Duration", "0:00:01")]


class ExportResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_panel(self, width=620):
        panel = ExportResultTab(lambda text: text)
        panel.resize(width, 420)
        self.addCleanup(lambda: panel.deleteLater() if not isdeleted(panel) else None)
        return panel

    def test_labels(self):
        self.assertEqual(format_label("mp4", "libx264", "aac", "video"), "MP4 (H.264)")
        self.assertEqual(format_label("webm", "libvpx-vp9", "libopus", "video"), "WEBM (VP9)")
        self.assertEqual(format_label("mov", "prores_ks", "pcm_s16le", "video"), "MOV (ProRes)")
        self.assertEqual(format_label("mp3", "", "libmp3lame", "audio"), "MP3")
        self.assertEqual(format_label("ogg", "", "libvorbis", "audio"), "OGG (Vorbis)")
        self.assertEqual(format_label("mkv", "ffv1", "flac", "video"), "MKV (FFV1)")
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(13002342), "12.4 MB")
        self.assertEqual(format_size(5 * 1024 ** 4), "5120.0 GB")
        self.assertEqual(format_duration(0.4), "0:00:00")
        self.assertEqual(format_duration(3725.2), "1:02:05")

    def test_kinds_set_message_and_primary_action(self):
        panel = self.make_panel()
        for kind, button, visible in (("video", "Watch Video", True), ("audio", "Play Audio", True),
                                      ("image_sequence", "Watch Video", False)):
            with self.subTest(kind=kind):
                panel.show_success("/tmp/out.mp4", kind, DETAILS)
                self.assertEqual(panel.location.text(), "/tmp/out.mp4")
                self.assertEqual(panel.primary_button.text(), button)
                self.assertEqual(panel.primary_button.isVisibleTo(panel), visible)
                self.assertEqual(len(panel.cards), len(DETAILS))
        self.assertIn("image sequence", panel.subtitle.text())

    def test_cards_reflow_instead_of_clipping(self):
        panel = self.make_panel(900)
        # Real panels are visible; hidden widgets defer resize events until shown.
        panel.show()
        panel.show_success("/tmp/out.mp4", "video", DETAILS)
        self.assertEqual(panel.columns, 3)
        panel.resize(260, 420)
        QApplication.processEvents()
        self.assertEqual(panel.columns, 1)
        self.assertEqual([panel.cards_layout.getItemPosition(panel.cards_layout.indexOf(card))[:2]
                          for card in panel.cards], [(row, 0) for row in range(len(DETAILS))])

    def test_style_follows_theme_palette(self):
        panel = self.make_panel()
        panel.show_success("/tmp/out.mp4", "video", DETAILS)
        for window_text, link, expected_link in (("#ffffff", "#55aaff", "#55aaff"),
                                                 ("#202020", "#1f6fc5", "#1f6fc5"),
                                                 ("#ffffff", "#0000ff", "#7ab8ff")):
            with self.subTest(text=window_text, link=link):
                palette = QPalette(panel.palette())
                palette.setColor(QPalette.WindowText, QColor(window_text))
                palette.setColor(QPalette.Link, QColor(link))
                panel.setPalette(palette)
                self.assertIn("color: %s" % expected_link, panel.styleSheet())
                self.assertFalse(panel.badge.pixmap().isNull())
                self.assertFalse(panel.copy_button.icon().isNull())

    def test_copy_open_and_reveal_use_exported_path(self):
        panel = self.make_panel()
        panel.show_success("/tmp/out é.mp4", "video", DETAILS)
        with patch("windows.export_result.QToolTip.showText"):
            panel.copy_button.click()
        self.assertEqual(QApplication.clipboard().text(), "/tmp/out é.mp4")
        with patch("windows.export_result.open_file", return_value=True) as opened, \
                patch("windows.export_result.reveal_file", return_value=True) as revealed:
            panel.primary_button.click()
            panel.link_button.click()
        self.assertEqual(opened.call_args[0][1], "/tmp/out é.mp4")
        self.assertEqual(revealed.call_args[0][1], "/tmp/out é.mp4")

    def test_failure_shows_error_copies_report_and_retries(self):
        panel = self.make_panel()
        retry = Mock()
        panel.show_failure("A valid video codec could not be found", DETAILS[:3], retry)
        self.assertEqual(panel.headline.text(), "Export Failed")
        self.assertEqual(panel.primary_button.text(), "Try Again")
        self.assertTrue(panel.error_text.isVisibleTo(panel))
        self.assertFalse(panel.location.isVisibleTo(panel))
        self.assertIn("rgba(229, 72, 77", panel.styleSheet())
        with patch("windows.export_result.QToolTip.showText"):
            panel.link_button.click()
        report = QApplication.clipboard().text()
        self.assertIn("A valid video codec could not be found", report)
        self.assertIn("Format: MP4 (H.264)", report)
        panel.primary_button.click()
        retry.assert_called_once_with()
        panel.show_failure("boom", [], None)
        self.assertFalse(panel.primary_button.isVisibleTo(panel))
        # Success after failure restores success styling and fields.
        panel.show_success("/tmp/out.mp4", "video", DETAILS)
        self.assertIn("rgba(47, 191, 113", panel.styleSheet())
        self.assertFalse(panel.error_text.isVisibleTo(panel))

    def test_tab_never_demands_more_space(self):
        panel = self.make_panel()
        panel.show_success("/tmp/" + "very long folder name/" * 10 + "out.mp4", "video", DETAILS)
        self.assertEqual((panel.minimumSizeHint().width(), panel.minimumSizeHint().height()), (0, 0))

    def test_details_from_dialog(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as output:
            output.write(b"x" * 2048)
            output.flush()
            dialog = SimpleNamespace(
                txtVideoFormat=Mock(text=lambda: "mp4"), txtVideoCodec=Mock(text=lambda: "libx264"),
                txtAudioCodec=Mock(text=lambda: "aac"), txtImageFormat=Mock(text=lambda: "-%05d.png"),
                txtFrameRateNum=Mock(value=lambda: 30), txtFrameRateDen=Mock(value=lambda: 1),
                txtStartFrame=Mock(value=lambda: 1), txtEndFrame=Mock(value=lambda: 90),
                txtWidth=Mock(value=lambda: 1920), txtHeight=Mock(value=lambda: 1080),
                cboSimpleQuality=Mock(currentData=lambda: "High"),
                cboSimpleVideoProfile=Mock(currentText=lambda: "", currentData=lambda: ""))
            video = dict((title, value) for _, title, value in export_details(dialog, output.name, "video", str))
            self.assertEqual(video, {"Format": "MP4 (H.264)", "Resolution": "1920 × 1080, 30 fps",
                                     "Quality": "High Quality", "File Size": "2.0 KB", "Duration": "0:00:03"})
            audio = dict((title, value) for _, title, value in export_details(dialog, output.name, "audio", str))
            self.assertNotIn("Resolution", audio)
            self.assertEqual(audio["Format"], "MP4 (AAC)")
            sequence = dict((title, value) for _, title, value in
                            export_details(dialog, "/missing/out-%05d.png", "image_sequence", str))
            self.assertEqual(sequence["Format"], "PNG")
            self.assertEqual(sequence["Frames"], "90")
            self.assertNotIn("File Size", sequence)


class ExportDialogResultTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.qt_test_app import ensure_app_state
        cls.app = ensure_app_state(QApplication.instance() or QApplication([]),
                                   lambda: SimpleNamespace(get=lambda key: None))

    def make_dialog(self):
        from classes import info, ui_util
        from qt_api import QDialog
        from windows.export import Export
        dialog = Export.__new__(Export)
        QDialog.__init__(dialog)
        ui_util.load_ui(dialog, os.path.join(info.PATH, "windows", "ui", "export.ui"))
        dialog.result_tab = None
        dialog.restoring_defaults = False
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_result_is_a_third_tab_and_settings_stay_browsable_read_only(self):
        dialog = self.make_dialog()
        dialog.show()
        QApplication.processEvents()
        size = dialog.size()
        dialog.exportTabs.setEnabled(False)  # as during export
        app = SimpleNamespace(_tr=lambda text: text, updates=Mock(), project=SimpleNamespace())
        with patch("windows.export.get_app", return_value=app):
            dialog.show_export_result("/tmp/out.mp4", "video_audio")
            QApplication.processEvents()
            self.assertEqual(dialog.exportTabs.count(), 3)
            self.assertEqual(dialog.exportTabs.tabText(2), "Complete")
            self.assertIs(dialog.exportTabs.currentWidget(), dialog.result_tab)
            self.assertEqual(dialog.size(), size)
            self.assertTrue(dialog.exportTabs.isEnabled())
            self.assertTrue(dialog.toolBox.isEnabled())
            for widget in (dialog.txtVideoCodec, dialog.cboSimpleQuality, dialog.txtWidth):
                self.assertFalse(widget.isEnabled())
            dialog.exportTabs.setCurrentIndex(1)
            self.assertIs(dialog.exportTabs.currentWidget(), dialog.Advanced)
            dialog.save_settings()
        names = [setting["name"] for setting in app.updates.update.call_args[0][1]]
        self.assertIn("txtVideoCodec", names)
        self.assertNotIn("exportLocation", names)

    def test_failure_tab_and_retry_reopens_dialog(self):
        dialog = self.make_dialog()
        trigger = Mock()
        app = SimpleNamespace(_tr=lambda text: text, window=SimpleNamespace(
            actionExportVideo=SimpleNamespace(trigger=trigger)))
        with patch("windows.export.get_app", return_value=app):
            dialog.show_export_result("/tmp/out.mp4", "video", "Invalid codec")
        self.assertEqual(dialog.exportTabs.tabText(2), "Export Failed")
        self.assertEqual(dialog.result_tab.error_text.text(), "Invalid codec")
        with patch.object(type(dialog), "reject") as reject, \
                patch("windows.export.get_app", return_value=app), \
                patch("windows.export.QTimer.singleShot", side_effect=lambda ms, fn: fn()):
            dialog.result_tab.primary_button.click()
        reject.assert_called_once_with()
        trigger.assert_called_once_with()


class DesktopOpenTests(unittest.TestCase):
    def test_linux_prefers_portal_then_sanitized_xdg_open_then_qt(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as output, \
                patch.object(desktop_open.sys, "platform", "linux"), \
                patch.dict(os.environ, {"LD_LIBRARY_PATH": "/bundle"}, clear=False), \
                patch.object(desktop_open, "_sandboxed", return_value=False), \
                patch.object(desktop_open.shutil, "which", return_value="/usr/bin/xdg-open"), \
                patch.object(desktop_open.subprocess, "Popen") as popen, \
                patch.object(desktop_open.QDesktopServices, "openUrl", return_value=True) as qt_open:
            with patch("classes.portal_file_dialog.open_file_with_default_application", return_value=True):
                self.assertTrue(desktop_open.open_file(None, output.name))
            popen.assert_not_called()
            with patch("classes.portal_file_dialog.open_file_with_default_application", return_value=None):
                self.assertTrue(desktop_open.open_file(None, output.name))
            self.assertEqual(popen.call_args[0][0], ["/usr/bin/xdg-open", output.name])
            self.assertNotIn("LD_LIBRARY_PATH", popen.call_args[1]["env"])
            qt_open.assert_not_called()
            with patch("classes.portal_file_dialog.open_containing_directory", return_value=None):
                self.assertTrue(desktop_open.reveal_file(None, output.name))
            self.assertEqual(popen.call_args[0][0], ["/usr/bin/xdg-open", os.path.dirname(output.name)])

    def test_sandbox_without_portal_uses_qt(self):
        with patch.object(desktop_open.sys, "platform", "linux"), \
                patch.object(desktop_open, "_sandboxed", return_value=True), \
                patch.object(desktop_open.subprocess, "Popen") as popen, \
                patch("classes.portal_file_dialog.open_file_with_default_application", return_value=None), \
                patch.object(desktop_open.QDesktopServices, "openUrl", return_value=True) as qt_open:
            self.assertTrue(desktop_open.open_file(None, "/tmp/out.mp4"))
        popen.assert_not_called()
        self.assertEqual(qt_open.call_args[0][0].toLocalFile(), "/tmp/out.mp4")

    def test_windows_and_macos_select_the_file(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as output:
            for platform, command in (("win32", ["explorer", "/select,", os.path.normpath(output.name)]),
                                      ("darwin", ["open", "-R", output.name])):
                with self.subTest(platform=platform), patch.object(desktop_open.sys, "platform", platform), \
                        patch.object(desktop_open.subprocess, "Popen") as popen:
                    self.assertTrue(desktop_open.reveal_file(None, output.name))
                    self.assertEqual(popen.call_args[0][0], command)

    def test_failed_launch_falls_back_to_folder_url(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as output, \
                patch.object(desktop_open.sys, "platform", "darwin"), \
                patch.object(desktop_open.subprocess, "Popen", side_effect=OSError("missing")), \
                patch.object(desktop_open.QDesktopServices, "openUrl", return_value=True) as qt_open:
            self.assertTrue(desktop_open.reveal_file(None, output.name))
        self.assertEqual(qt_open.call_args[0][0].toLocalFile(), os.path.dirname(output.name))

    def test_missing_file_opens_its_folder(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(desktop_open, "open_file", return_value=True) as opened:
            self.assertTrue(desktop_open.reveal_file(None, os.path.join(folder, "out-%05d.png")))
        self.assertEqual(opened.call_args[0][1], folder)


if __name__ == "__main__":
    unittest.main()
