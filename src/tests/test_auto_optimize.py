"""Automatic optimization decisions, project lifetime, and real Qt banner actions."""

import copy
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from qt_api import QAction, QMainWindow, QPushButton
from classes.auto_optimize import (MEASUREMENT_VERSION, machine_id, source_fingerprint,
                                   threshold_ms, valid_measurement)
from classes.query import File
from classes.updates import UpdateAction
from tests.test_proxy_service import DummyApp, ensure_app_state
from tests.qt_test_app import get_or_create_app
from windows.auto_optimize import AutoOptimizeController


def video(**changes):
    data = dict(id="V1", media_type="video", type="FFmpegReader", width=3840,
                height=2160, fps=dict(num=60, den=1), duration=10, path="video.mp4")
    data.update(changes)
    return data


def measurement(path, milliseconds=350):
    return dict(version=MEASUREMENT_VERSION, machine=machine_id(),
                source=source_fingerprint(path), frame=1, frame_ms=milliseconds,
                decode_size=[300, 195])


class DetectionTests(unittest.TestCase):
    def test_invalid_thresholds_fall_back_to_200(self):
        for value in (None, "bad", 0, -1, float("nan"), float("inf")):
            self.assertEqual(threshold_ms(value), 200)
        self.assertEqual(threshold_ms("500"), 500)

    def test_invalid_or_foreign_measurements_are_ignored(self):
        with tempfile.NamedTemporaryFile() as source:
            sample = measurement(source.name)
            fingerprint = source_fingerprint(source.name)
            self.assertTrue(valid_measurement(sample, fingerprint))
            for changes in (dict(machine="other"), dict(version=0), dict(source={}),
                            dict(frame=25), dict(frame_ms=-1), dict(frame_ms=float("nan")),
                            dict(frame_ms=float("inf")), dict(frame_ms="350"), dict(frame_ms=True)):
                with self.subTest(changes=changes):
                    self.assertFalse(valid_measurement(dict(sample, **changes), fingerprint))
            self.assertFalse(valid_measurement(sample, None))
            self.assertFalse(valid_measurement(None, fingerprint))


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(DummyApp)
        ensure_app_state(cls.app)

    def setUp(self):
        self.old_data = copy.deepcopy(self.app.project._data)
        self.old_settings = dict(self.app.settings.values)
        self.app.project._data.update(auto_optimize=None, files=[], clips=[])
        self.app.settings.values.update({"auto-optimize": "ask", "optimize-preview-max-size": "1280x720"})
        self.window = QMainWindow()
        self.window.menuFile = self.window.menuBar().addMenu("File")
        self.window.actionSaveFrame = QAction("Save Frame", self.window)
        self.window.menuFile.addAction(self.window.actionSaveFrame)
        self.service = self.window.proxy_service = Mock()
        self.service.get_active_job_for_file.return_value = None
        self.service.has_proxy_reader.return_value = False
        self.service.has_missing_proxy.return_value = False
        self.executor_patch = patch("windows.auto_optimize.ThreadPoolExecutor")
        self.executor = self.executor_patch.start().return_value
        self.executor.submit.return_value.done.return_value = False
        self.addCleanup(self.executor_patch.stop)
        self.controller = AutoOptimizeController(self.window)
        self.controller.timer.stop()
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "video.mp4")
        with open(self.path, "wb") as source:
            source.write(b"source")

    def tearDown(self):
        self.controller.shutdown()
        self.app.updates.updateListeners.remove(self.controller)
        self.window.close()
        self.window.deleteLater()
        self.app.project._data = self.old_data
        self.app.settings.values = self.old_settings
        self.app.updates.reset()
        self.temp.cleanup()

    def add_video(self, id="V1", checked=True, slow=True, **changes):
        data = video(id=id, path=self.path, **changes)
        if checked:
            data["thumbnail_performance"] = measurement(self.path, 350 if slow else 30)
        self.app.updates.insert(["files"], data)
        return data

    def evaluate(self):
        self.controller.evaluate()
        self.controller.timer.stop()

    def test_ask_offers_without_processing_and_accept_hides_immediately(self):
        self.add_video()
        self.evaluate()
        banner = self.controller.area.banners["auto-optimize"]
        self.service.create_for_files.assert_not_called()
        banner.primary.click()
        self.assertNotIn("auto-optimize", self.controller.area.banners)
        self.assertTrue(self.app.project.get("auto_optimize"))
        self.assertTrue(self.controller.action.isChecked())
        self.evaluate()
        files = self.service.create_for_files.call_args.args[0]
        self.assertEqual([file.id for file in files], ["V1"])

    def test_decline_and_close_persist_and_do_not_repeat_for_imports(self):
        for close in (False, True):
            with self.subTest(close=close):
                self.app.project._data.update(auto_optimize=None, files=[])
                self.add_video()
                self.evaluate()
                banner = self.controller.area.banners["auto-optimize"]
                button = banner.close_button if close else next(
                    b for b in banner.findChildren(QPushButton) if b.text() == "Not Now")
                button.click()
                self.assertFalse(self.app.project.get("auto_optimize"))
                self.add_video(id="V2")
                self.controller.changed(UpdateAction("load"))
                self.evaluate()
                self.assertNotIn("auto-optimize", self.controller.area.banners)
                self.service.create_for_files.assert_not_called()

    def test_defaults_and_explicit_project_overrides(self):
        for preference, choice, expected in (
                ("ask", None, "ask"), ("always", None, "always"), ("never", None, "never"),
                ("always", False, "never"), ("never", True, "always")):
            self.app.settings.values["auto-optimize"] = preference
            self.app.project._data["auto_optimize"] = choice
            self.assertEqual(self.controller.mode(), expected)

    def test_always_runs_without_banner_but_never_does_not_even_probe(self):
        self.add_video()
        self.app.settings.values["auto-optimize"] = "never"
        self.evaluate()
        self.service.create_for_files.assert_not_called()
        self.app.settings.values["auto-optimize"] = "always"
        self.evaluate()
        self.service.create_for_files.assert_called_once()
        self.assertNotIn("auto-optimize", self.controller.area.banners)

    def test_attempted_jobs_do_not_restart_after_cancel_failure_or_unlink(self):
        self.add_video()
        self.controller.choose(True)
        self.evaluate()
        self.evaluate()
        self.assertEqual(self.service.create_for_files.call_count, 1)
        self.add_video(id="V2")
        self.evaluate()
        self.assertEqual([f.id for f in self.service.create_for_files.call_args.args[0]], ["V2"])

    def test_existing_optimized_and_missing_sources_are_skipped(self):
        self.add_video()
        self.service.has_proxy_reader.return_value = True
        self.evaluate()
        self.assertFalse(self.controller.area.banners)
        self.service.has_proxy_reader.return_value = False
        os.remove(self.path)
        self.evaluate()
        self.assertFalse(self.controller.area.banners)

    def test_missing_optimized_copy_can_be_rebuilt(self):
        self.add_video()
        self.service.has_proxy_reader.return_value = True
        self.service.has_missing_proxy.return_value = True
        self.controller.choose(True)
        self.evaluate()
        self.service.create_for_files.assert_called_once()

    def test_rapid_imports_share_one_banner(self):
        self.add_video()
        self.evaluate()
        banner = self.controller.area.banners["auto-optimize"]
        self.add_video(id="V2")
        self.evaluate()
        self.assertIs(self.controller.area.banners["auto-optimize"], banner)

    def test_stale_thumbnail_result_cannot_affect_next_project(self):
        self.add_video(checked=False)
        epoch = self.controller.epoch
        sample = measurement(self.path)
        self.controller.changed(UpdateAction("load"))
        self.controller._record_thumbnail(epoch, "V1", sample)
        self.assertNotIn("thumbnail_performance", File.get(id="V1").data)

    def test_measurement_is_saved_without_overwriting_edits_or_undo_history(self):
        self.add_video(checked=False)
        self.app.updates.update(["files", {"id": "V1"}], {"name": "New name"})
        history = list(self.app.updates.actionHistory)
        sample = measurement(self.path)
        self.controller._record_thumbnail(self.controller.epoch, "V1", sample)
        saved = File.get(id="V1").data
        self.assertEqual(saved["thumbnail_performance"], sample)
        self.assertEqual(saved["name"], "New name")
        self.assertEqual(self.app.updates.actionHistory, history)
        self.assertEqual(json.loads(json.dumps(saved))["thumbnail_performance"], sample)
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)

    def test_deleted_or_changed_source_rejects_queued_measurement(self):
        self.add_video(checked=False)
        sample = measurement(self.path)
        with open(self.path, "ab") as source:
            source.write(b"changed")
        self.controller._record_thumbnail(self.controller.epoch, "V1", sample)
        self.assertNotIn("thumbnail_performance", File.get(id="V1").data)
        self.app.updates.delete(["files", {"id": "V1"}])
        self.controller._record_thumbnail(self.controller.epoch, "V1", sample)
        self.assertIsNone(File.get(id="V1"))

    def test_fast_source_never_offers_or_processes(self):
        self.add_video(slow=False)
        self.evaluate()
        self.assertFalse(self.controller.area.banners)
        self.service.create_for_files.assert_not_called()

    def test_menu_can_enable_and_disable_without_banner(self):
        self.controller.action.trigger()
        self.assertIs(self.app.project.get("auto_optimize"), True)
        self.controller.action.trigger()
        self.assertIs(self.app.project.get("auto_optimize"), False)
        self.assertTrue(self.app.project.has_unsaved_changes)

    def test_saved_choice_survives_json_and_old_projects_default_to_undecided(self):
        self.controller.choose(False)
        saved = json.loads(json.dumps(self.app.project._data))
        with open(self.app.project.default_project_filepath) as source:
            defaults = json.load(source)
        self.assertIs(self.app.project.merge_settings(defaults, saved)["auto_optimize"], False)
        self.assertIsNone(self.app.project.merge_settings(defaults, {"id": "old"})["auto_optimize"])

    def test_active_playback_defers_automatic_processing(self):
        self.add_video()
        self.controller.choose(True)
        self.window.preview_thread = SimpleNamespace(player=Mock())
        import openshot
        self.window.preview_thread.player.Mode.return_value = openshot.PLAYBACK_PLAY
        self.evaluate()
        self.service.create_for_files.assert_not_called()
        self.window.preview_thread = None
        self.evaluate()
        self.service.create_for_files.assert_called_once()

    def test_old_project_measures_then_offers_and_queues_remaining_videos(self):
        self.add_video(checked=False)
        self.add_video(id="V2", checked=False)
        self.controller.changed(UpdateAction("load"))
        self.evaluate()
        self.executor.submit.assert_called_once()
        self.assertFalse(self.controller.area.banners)
        self.controller._record_thumbnail(self.controller.epoch, "V1", measurement(self.path))
        self.executor.submit.return_value.done.return_value = True
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)
        self.executor.submit.assert_called_once()
        self.controller.choose(True)
        self.evaluate()
        self.assertEqual(self.executor.submit.call_count, 2)
        self.assertEqual(self.service.create_for_files.call_args[0][0][0].id, "V1")
        self.controller._record_thumbnail(self.controller.epoch, "V2", measurement(self.path))
        self.evaluate()
        self.assertEqual(self.service.create_for_files.call_args[0][0][0].id, "V2")
        self.assertFalse(self.controller.area.banners)

    def test_missing_timings_are_serial_and_timeline_first(self):
        self.add_video(checked=False)
        self.add_video(id="V2", checked=False)
        self.app.project._data["clips"] = [{"file_id": "V2"}]
        self.evaluate()
        self.assertEqual(self.executor.submit.call_args[0][2], "V2")
        self.evaluate()
        self.executor.submit.assert_called_once()

    def test_never_does_not_refresh_missing_timings(self):
        self.add_video(checked=False)
        self.controller.choose(False)
        self.evaluate()
        self.executor.submit.assert_not_called()

    def test_thumbnail_refresh_uses_normal_small_thumbnail_and_records_result(self):
        self.add_video(checked=False)
        sample = {"frame_ms": 350, "frame": 1, "decode_size": [300, 195]}
        with patch("windows.auto_optimize.GenerateThumbnail", return_value=sample) as generate:
            self.controller._measure_thumbnail(
                self.controller.epoch, "V1", self.path, source_fingerprint(self.path))
        self.app.processEvents()
        self.assertEqual(generate.call_args[0][2:5], (1, 100, 65))
        self.assertFalse(os.path.exists(generate.call_args[0][1]))
        self.assertEqual(File.get(id="V1").data["thumbnail_performance"]["frame_ms"], 350)
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)

    def test_failed_refresh_is_not_repeated_on_every_evaluation(self):
        self.add_video(checked=False)
        self.evaluate()
        self.executor.submit.return_value.done.return_value = True
        self.evaluate()
        self.executor.submit.assert_called_once()

    def test_playback_defers_missing_timing_check(self):
        import openshot
        self.add_video(checked=False)
        self.window.preview_thread = SimpleNamespace(player=Mock())
        self.window.preview_thread.player.Mode.return_value = openshot.PLAYBACK_PLAY
        self.evaluate()
        self.executor.submit.assert_not_called()
        self.window.preview_thread = None
        self.evaluate()
        self.executor.submit.assert_called_once()

    def test_background_result_returns_to_ui_and_enables_suggestion(self):
        from concurrent.futures import ThreadPoolExecutor
        self.add_video(checked=False)
        with patch("windows.auto_optimize.ThreadPoolExecutor", ThreadPoolExecutor), \
             patch("windows.auto_optimize.GenerateThumbnail",
                   return_value={"frame_ms": 350, "frame": 1, "decode_size": [300, 195]}):
            self.evaluate()
            self.controller.measurement_future.result(timeout=5)
        self.assertNotIn("thumbnail_performance", File.get(id="V1").data)
        self.app.processEvents()
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)
        self.controller.shutdown()
        self.assertFalse(any(t.is_alive() for t in self.controller.measurement_executor._threads))

    def test_valid_saved_timings_are_reused_on_project_open(self):
        self.add_video()
        self.controller.changed(UpdateAction("load"))
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)

    def test_switching_projects_cancels_automatic_jobs(self):
        self.add_video()
        self.controller.choose(True)
        self.evaluate()
        self.controller.changed(UpdateAction("load"))
        self.service.cancel_job.assert_called_once_with("V1")
        self.assertFalse(self.controller.attempted)

    def test_preference_change_removes_existing_offer(self):
        self.add_video()
        self.evaluate()
        self.app.settings.values["auto-optimize"] = "never"
        self.controller.refresh()
        self.evaluate()
        self.assertFalse(self.controller.area.banners)
        self.assertFalse(self.controller.action.isChecked())

    def test_menu_choice_does_not_destroy_edit_undo_history(self):
        self.add_video()
        history = list(self.app.updates.actionHistory)
        self.controller.choose(True)
        self.assertEqual(self.app.updates.actionHistory, history)

    def test_unwritable_output_does_not_crash_or_repeat(self):
        self.add_video()
        self.controller.choose(True)
        self.service.create_for_files.side_effect = OSError("Permission denied")
        with patch("windows.auto_optimize.log.warning") as warning:
            self.evaluate()
            self.evaluate()
        self.service.create_for_files.assert_called_once()
        warning.assert_called_once()
        self.assertIn("Could not start optimization", self.window.statusBar().currentMessage())

    def test_threshold_boundary_and_preference_changes(self):
        self.add_video()
        self.app.settings.values["auto-optimize-threshold"] = 350
        self.evaluate()
        self.assertFalse(self.controller.area.banners)
        self.app.settings.values["auto-optimize-threshold"] = 349
        self.controller.refresh()
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)

    def test_first_valid_measurement_is_preserved(self):
        self.add_video()
        self.controller._record_thumbnail(self.controller.epoch, "V1", measurement(self.path, 10))
        self.assertEqual(File.get(id="V1").data["thumbnail_performance"]["frame_ms"], 350)

    def test_foreign_measurement_is_replaced_by_local_thumbnail(self):
        self.add_video()
        sample = measurement(self.path)
        sample["machine"] = "other-computer"
        self.app.updates.update_untracked(["files", {"id": "V1"}], {"thumbnail_performance": sample})
        self.evaluate()
        self.assertFalse(self.controller.area.banners)
        self.controller._record_thumbnail(self.controller.epoch, "V1", measurement(self.path, 400))
        self.assertEqual(File.get(id="V1").data["thumbnail_performance"]["machine"], machine_id())

    def test_small_slow_video_qualifies_but_images_and_audio_do_not(self):
        self.add_video(width=640, height=360, duration=1)
        self.evaluate()
        self.assertIn("auto-optimize", self.controller.area.banners)
        for media_type in ("image", "audio"):
            self.app.updates.update(["files", {"id": "V1"}], {"media_type": media_type})
            self.evaluate()
            self.assertFalse(self.controller.area.banners)

    def test_shutdown_ignores_queued_thumbnail(self):
        self.add_video(checked=False)
        self.controller.shutdown()
        self.controller._record_thumbnail(self.controller.epoch, "V1", measurement(self.path))
        self.assertNotIn("thumbnail_performance", File.get(id="V1").data)

    def test_worker_signal_updates_file_only_on_ui_thread(self):
        import threading
        self.add_video(checked=False)
        sample = measurement(self.path)
        worker = threading.Thread(target=lambda: self.controller.thumbnail_measured.emit(
            self.controller.epoch, "V1", sample))
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertNotIn("thumbnail_performance", File.get(id="V1").data)
        self.app.processEvents()
        self.assertEqual(File.get(id="V1").data["thumbnail_performance"], sample)

    def test_new_import_joins_existing_optimization_queue_with_badge(self):
        from concurrent.futures import Future
        from classes.proxy_service import ProxyService

        service = ProxyService(self.window)
        self.window.proxy_service = service
        changed = []
        service.file_job_changed.connect(changed.append)
        try:
            with patch.object(service, "_proxy_root", return_value=self.temp.name), \
                 patch.object(service._executor, "submit", side_effect=lambda *args: Future()) as submit:
                for index in range(10):
                    self.add_video(id="SD%s" % index, slow=False, width=640, height=480)
                self.evaluate()
                self.assertNotIn("auto-optimize", self.controller.area.banners)
                for index in range(3):
                    self.add_video(id="HD%s" % index)
                self.evaluate()
                self.controller.area.banners["auto-optimize"].primary.click()
                self.evaluate()
                self.assertEqual(submit.call_count, 3)
                service._jobs["HD0"]["status"] = "running"
                self.assertEqual(service.get_file_badge("HD1")["label"], "Queued")

                # A newly imported file receives its normal thumbnail measurement.
                self.add_video(id="HD3", checked=False)
                self.controller._record_thumbnail(self.controller.epoch, "HD3", measurement(self.path))
                self.evaluate()
                self.assertEqual(submit.call_count, 4)
                self.assertEqual(service.get_file_badge("HD3")["label"], "Queued")
                self.assertIn("HD3", changed)
                self.assertNotIn("auto-optimize", self.controller.area.banners)
                self.evaluate()
                self.assertEqual(submit.call_count, 4)
        finally:
            service.shutdown()
            self.window.proxy_service = self.service
