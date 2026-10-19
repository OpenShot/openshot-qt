"""Export celebration: confetti preference, overlay lifecycle and export wiring."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication, QDialog, QImage, QPainter, QWidget, Qt, isdeleted
from windows import confetti
from windows.confetti import ConfettiCannon, celebrate_export, should_celebrate


class Settings:
    def __init__(self, mode="first", celebrated=False):
        self.data = {"export-celebration": mode, "export-celebrated": celebrated}
        self.saved = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        self.saved = dict(self.data)


class ConfettiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.qt_test_app import ensure_app_state
        cls.app = ensure_app_state(QApplication.instance() or QApplication([]),
                                   lambda: SimpleNamespace(get=lambda key: None))

    def make_parent(self):
        parent = QWidget()
        parent.resize(800, 600)
        self.addCleanup(lambda: parent.deleteLater() if not isdeleted(parent) else None)
        return parent

    def test_preference_modes(self):
        for mode, celebrated, expected in (
                ("first", False, True), ("first", True, False),
                ("all", False, True), ("all", True, True),
                ("none", False, False), ("none", True, False),
                (None, False, True), ("unknown", True, False)):
            with self.subTest(mode=mode, celebrated=celebrated):
                self.assertEqual(should_celebrate(Settings(mode, celebrated)), expected)

    def test_first_export_celebrates_once_and_persists(self):
        settings = Settings()
        parent = self.make_parent()
        cannon = celebrate_export(settings, parent)
        self.assertIsInstance(cannon, ConfettiCannon)
        self.assertTrue(settings.saved["export-celebrated"])
        cannon.finish()
        self.assertIsNone(celebrate_export(settings, parent))

    def test_none_never_fires_or_marks_celebrated(self):
        settings = Settings("none")
        self.assertIsNone(celebrate_export(settings, self.make_parent()))
        self.assertEqual(settings.saved, {})

    def test_failure_never_breaks_export(self):
        settings = Settings()
        with patch.object(settings, "save", side_effect=OSError("disk full")):
            self.assertIsNone(celebrate_export(settings, self.make_parent()))

    def test_overlay_is_click_through_tracks_resize_and_deletes_itself(self):
        parent = self.make_parent()
        cannon = ConfettiCannon(parent, seed=1).fire()
        self.assertTrue(cannon.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertEqual(cannon.geometry(), parent.rect())
        # Real parents are visible; hidden widgets defer resize events until shown.
        parent.show()
        parent.resize(500, 400)
        self.assertEqual(cannon.geometry(), parent.rect())
        self.assertTrue(cannon.timer.isActive())
        with patch.object(cannon, "elapsed_ms", return_value=confetti.DURATION_MS):
            cannon.tick()
        self.assertFalse(cannon.timer.isActive())
        self.assertTrue(cannon.isHidden())

    def test_cannons_fire_up_from_both_corners_then_fall(self):
        parent = self.make_parent()
        cannon = ConfettiCannon(parent, count=40, seed=2)
        left = [p for p in cannon.particles if p.vx > 0]
        right = [p for p in cannon.particles if p.vx < 0]
        self.assertEqual(len(left), len(right))
        self.assertTrue(all(p.x == 0 for p in left) and all(p.x == 800 for p in right))
        self.assertTrue(all(p.vy < 0 for p in cannon.particles))
        for _ in range(150):
            for particle in cannon.particles:
                particle.advance(1 / 60)
        self.assertTrue(all(p.vy > 0 for p in cannon.particles))
        # Paint a frame offscreen to exercise the renderer.
        image = QImage(800, 600, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        cannon.last_ms = 1000
        cannon.render(image)
        cannon.deleteLater()

    def test_export_celebrates_and_invites_only_after_writer_success(self):
        from windows.export import Export
        for outcome in ("success", "cancel", "write-error"):
            for finished_window in (True, False):
                with self.subTest(outcome=outcome, finished_window=finished_window), \
                        tempfile.TemporaryDirectory() as folder:
                    dialog = Export.__new__(Export)
                    QDialog.__init__(dialog)
                    self.addCleanup(dialog.deleteLater)
                    for name in ("save_settings", "enableControls", "disableControls", "updateFrameRate",
                                 "progressExportVideo", "timeline", "cache_thread",
                                 "cancel_button", "export_button", "close_button"):
                        setattr(dialog, name, Mock())
                    for name, value in {"txtStartFrame": 1, "txtEndFrame": 3,
                            "txtFrameRateNum": 24, "txtFrameRateDen": 1, "txtWidth": 16, "txtHeight": 16,
                            "txtPixelRatioNum": 1, "txtPixelRatioDen": 1,
                            "txtSampleRate": 48000, "txtChannels": 2}.items():
                        setattr(dialog, name, Mock(value=lambda value=value: value))
                    for name, text in {"txtFileName": "celebrate-export", "txtVideoFormat": "mp4",
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
                    dialog.s = Mock(get=lambda key: finished_window if key == "show_finished_window" else False)
                    controller = Mock()
                    window = SimpleNamespace(timeline_sync=Mock(), feedback_controller=controller)
                    app = SimpleNamespace(_tr=lambda text: text, get_settings=Mock,
                        project=SimpleNamespace(), window=window)
                    writer = Mock()
                    if outcome == "cancel":
                        writer.WriteFrame.side_effect = lambda frame: setattr(dialog, "exporting", False)
                    elif outcome == "write-error":
                        writer.WriteFrame.side_effect = RuntimeError("write failed")
                    with patch("windows.export.get_app", return_value=app), \
                            patch("windows.export.File.get", return_value=None), \
                            patch("windows.export.openshot.FFmpegWriter", return_value=writer), \
                            patch("windows.export.openshot.CacheMemory"), \
                            patch("windows.export.openshot.Settings"), \
                            patch("windows.export.QMessageBox"), \
                            patch("windows.export.open", Mock()), \
                            patch.object(Export, "show"), \
                            patch.object(Export, "show_export_complete") as summary, \
                            patch("windows.export.celebrate_export") as celebrate:
                        dialog.accept()
                    succeeded = outcome == "success"
                    self.assertEqual(celebrate.call_count, int(succeeded))
                    self.assertEqual(controller.record_export.call_count, int(succeeded))
                    self.assertEqual(summary.call_count, int(succeeded and finished_window))
                    if summary.called:
                        self.assertEqual(summary.call_args[0][1], "video")
                    if succeeded:
                        expected_parent = dialog if finished_window else window
                        self.assertIs(celebrate.call_args[0][1], expected_parent)


if __name__ == "__main__":
    unittest.main()
