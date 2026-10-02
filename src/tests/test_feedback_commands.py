"""Feedback hooks exercise real command handlers with external work stubbed out."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication, QDialog


class FeedbackCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.qt_test_app import ensure_app_state
        cls.app = ensure_app_state(QApplication.instance() or QApplication([]),
                                   lambda: SimpleNamespace(get=lambda key: None))

    def test_profile_changes_count_once_but_same_profile_and_cancel_do_not(self):
        from windows.main_window import MainWindow

        data = {"profile": "Old", "width": 640, "height": 480, "fps": {"num": 24, "den": 1}}
        project = SimpleNamespace(get=lambda key: data.get(key[0] if isinstance(key, list) else key))
        app = SimpleNamespace(project=project, updates=SimpleNamespace(
            transaction_id=None, update=lambda key, value: data.__setitem__(key[0], value)))
        ratio = SimpleNamespace(num=1, den=1)
        profile = SimpleNamespace(info=SimpleNamespace(description="New", width=1280, height=720,
            fps=SimpleNamespace(num=24, den=1, ToFloat=lambda: 24), pixel_ratio=ratio, display_ratio=ratio))
        window = SimpleNamespace(clearSelections=Mock(), preview_thread=SimpleNamespace(current_frame=1),
            SeekSignal=Mock(), refreshFrameSignal=Mock(), MaxSizeChanged=Mock(), videoPreview=Mock())
        with patch("windows.main_window.get_app", return_value=app), \
                patch("windows.main_window.record_feedback_action") as record, \
                patch("windows.main_window.QTimer.singleShot"), \
                patch("windows.main_window.openshot.Settings"):
            MainWindow.actionProfile_trigger(window, profile)
            MainWindow.actionProfile_trigger(window, profile)
            with patch("windows.profile.Profile", return_value=SimpleNamespace(
                    exec_=lambda: QDialog.Rejected, selected_profile=profile)):
                MainWindow.actionProfile_trigger(window)
            record.assert_called_once_with("profile")

    def test_regular_title_counts_only_a_successful_creation(self):
        from windows.title_editor import TitleEditor
        for saved, editing, expected in ((True, False, 1), (False, False, 0), (True, True, 0)):
            with self.subTest(saved=saved, editing=editing):
                dialog = TitleEditor.__new__(TitleEditor)
                dialog.svg_watcher = SimpleNamespace(path=None)
                QDialog.__init__(dialog)
                self.addCleanup(dialog.deleteLater)
                dialog.edit_file_path = "existing.svg" if editing else None
                dialog.duplicate = False
                dialog.txtFileName = Mock(text=lambda: "test-feedback-title")
                dialog.xmldoc = Mock()
                dialog.writeToFile = Mock(return_value=saved)
                app = SimpleNamespace(_tr=lambda text: text, window=SimpleNamespace(files_model=Mock()))
                with patch("windows.title_editor.get_app", return_value=app), \
                        patch("windows.title_editor.os.path.exists", return_value=False), \
                        patch("windows.title_editor.record_feedback_action") as record:
                    dialog.accept()
                self.assertEqual(record.call_count, expected)

    def test_title_write_failure_reports_failure(self):
        from windows.title_editor import TitleEditor
        with patch("builtins.open", side_effect=OSError("disk full")):
            self.assertFalse(TitleEditor.writeToFile(
                SimpleNamespace(filename="title.svg"), Mock(toxml=lambda: '<svg/>')))

    def test_animated_title_excludes_previews_cancelled_and_failed_renders(self):
        from windows.views.blender_listview import BlenderListView
        for final, cancelled, exit_code, expected in (
                (True, False, 0, 1), (False, False, 0, 0),
                (True, True, 0, 0), (True, False, 1, 0)):
            with self.subTest(final=final, cancelled=cancelled, exit_code=exit_code):
                view = SimpleNamespace(final_render=final, params={"file_name": "Title"},
                    unique_folder_name="test", fps={"num": 24, "den": 1}, win=Mock(),
                    worker=SimpleNamespace(canceled=cancelled, process=SimpleNamespace(returncode=exit_code)))
                app = SimpleNamespace(window=SimpleNamespace(files_model=Mock()))
                with patch("windows.views.blender_listview.get_app", return_value=app), \
                        patch("windows.views.blender_listview.record_feedback_action") as record:
                    BlenderListView.render_finished(view)
                self.assertEqual(record.call_count, expected)

    def test_effect_drop_counts_success_but_not_cancelled_processing(self):
        import json
        from windows.views.timeline import TimelineView
        effect = SimpleNamespace(Id=Mock(), Json=lambda: json.dumps({"id": "effect", "class_name": "Blur"}))
        clip = SimpleNamespace(id="clip", data={"effects": []})
        view = SimpleNamespace(update_clip_data=Mock())
        app = SimpleNamespace(project=SimpleNamespace(generate_id=lambda: "effect"), updates=Mock())
        with patch("windows.views.timeline.get_app", return_value=app), \
                patch("windows.views.timeline.record_feedback_action") as record:
            with patch("windows.views.timeline.effect_options", {}), \
                    patch("windows.views.timeline.openshot.EffectInfo", return_value=SimpleNamespace(
                        CreateEffect=lambda name: effect)):
                TimelineView._apply_effect_to_clip(view, clip, "Blur")
            record.assert_called_once_with("effects")
            record.reset_mock()
            with patch("windows.views.timeline.effect_options", {"Tracker": {}}), \
                    patch("windows.process_effect.ProcessEffect", return_value=SimpleNamespace(
                        exec_=lambda: QDialog.Rejected)):
                TimelineView._apply_effect_to_clip(view, clip, "Tracker")
            record.assert_not_called()

    def test_export_counts_only_after_writer_success_not_cancel_or_failure(self):
        from windows.export import Export
        for outcome in ("success", "cancel", "write-error", "close-error"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as folder:
                dialog = Export.__new__(Export)
                QDialog.__init__(dialog)
                self.addCleanup(dialog.deleteLater)
                for name in ("save_settings", "enableControls", "disableControls", "updateFrameRate",
                             "progressExportVideo", "timeline", "cache_thread"):
                    setattr(dialog, name, Mock())
                for name, value in {"txtStartFrame": 1, "txtEndFrame": 3,
                        "txtFrameRateNum": 24, "txtFrameRateDen": 1, "txtWidth": 16, "txtHeight": 16,
                        "txtPixelRatioNum": 1, "txtPixelRatioDen": 1,
                        "txtSampleRate": 48000, "txtChannels": 2}.items():
                    setattr(dialog, name, Mock(value=lambda value=value: value))
                for name, text in {"txtFileName": "feedback-export", "txtVideoFormat": "mp4",
                        "txtVideoCodec": "mpeg4", "txtExportFolder": folder,
                        "txtVideoBitRate": "1000", "txtAudioCodec": "aac", "txtAudioBitrate": "128"}.items():
                    setattr(dialog, name, Mock(text=lambda text=text: text))
                dialog.cboExportTo = Mock(currentText=lambda: "Video Only")
                dialog.cboInterlaced = Mock(currentIndex=lambda: 0)
                dialog.cboSpherical = Mock(currentIndex=lambda: 0)
                dialog.cboChannelLayout = Mock(currentData=lambda: 3)
                dialog.convert_to_bytes = int
                dialog.export_fps_factor = 1.0
                dialog.old_cache_object = None
                dialog.s = Mock(get=lambda key: False)
                app = SimpleNamespace(_tr=lambda text: text, get_settings=Mock,
                    project=SimpleNamespace(), window=SimpleNamespace(timeline_sync=Mock()))
                writer = Mock()
                if outcome == "cancel":
                    writer.WriteFrame.side_effect = lambda frame: setattr(dialog, "exporting", False)
                elif outcome == "write-error":
                    writer.WriteFrame.side_effect = RuntimeError("write failed")
                elif outcome == "close-error":
                    writer.Close.side_effect = RuntimeError("close failed")
                with patch("windows.export.get_app", return_value=app), \
                        patch("windows.export.File.get", return_value=None), \
                        patch("windows.export.openshot.FFmpegWriter", return_value=writer), \
                        patch("windows.export.openshot.CacheMemory"), \
                        patch("windows.export.openshot.Settings"), \
                        patch("windows.export.QMessageBox"), \
                        patch("windows.export.open", Mock()), \
                        patch("windows.export.record_feedback_action") as record:
                    dialog.accept()
                self.assertEqual(record.call_count, int(outcome == "success"))
