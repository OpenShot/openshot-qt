# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup audio checks preserve preferences when the backend fails."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from windows.preview_thread import PlayerWorker


class PreviewAudioDeviceTests(unittest.TestCase):
    def setUp(self):
        self.values = {"default-samplerate": 48000, "playback-audio-device": "Speakers||ALSA"}
        self.settings = Mock()
        self.settings.get.side_effect = self.values.get
        self.settings.set.side_effect = self.values.__setitem__
        self.project = SimpleNamespace(has_unsaved_changes=True, get=Mock(return_value=48000))
        self.updates = Mock()
        self.app = SimpleNamespace(get_settings=lambda: self.settings,
                                   project=self.project, updates=self.updates)
        self.worker = SimpleNamespace(player=Mock(), error_found=Mock())
        self.worker.player.GetError.return_value = ""
        self.worker.player.GetDefaultSampleRate.return_value = 48000
        self.device = self.worker.player.GetCurrentAudioDevice.return_value
        self.device.get_name.return_value = "Speakers"
        self.device.get_type.return_value = "ALSA"
        self.lib_settings = SimpleNamespace()
        self.app_patch = patch("windows.preview_thread.get_app", return_value=self.app)
        self.lib_patch = patch("windows.preview_thread.openshot.Settings", Mock(
            Instance=Mock(return_value=self.lib_settings)))
        self.app_patch.start()
        self.lib_patch.start()
        self.addCleanup(self.app_patch.stop)
        self.addCleanup(self.lib_patch.stop)

    def check(self):
        PlayerWorker.CheckAudioDevice(self.worker)

    def test_failure_preserves_preferences_and_project_on_repeated_checks(self):
        self.worker.player.GetError.return_value = "no channels"
        self.worker.player.GetDefaultSampleRate.return_value = 22050
        self.device.get_name.return_value = "Failed Webcam"
        for _ in range(2):
            self.check()
        self.assertEqual(self.values, {"default-samplerate": 48000,
                                     "playback-audio-device": "Speakers||ALSA"})
        self.settings.set.assert_not_called()
        self.updates.update_untracked.assert_not_called()
        self.worker.player.GetDefaultSampleRate.assert_not_called()
        self.worker.player.GetCurrentAudioDevice.assert_not_called()
        self.worker.error_found.emit.assert_called_with("no channels")
        self.assertTrue(self.project.has_unsaved_changes)
        self.assertEqual(vars(self.lib_settings), {})

    def test_successful_fallback_updates_actual_metadata_without_dirtying_project(self):
        self.worker.player.GetDefaultSampleRate.return_value = 44100
        self.device.get_name.return_value = "Fallback Speakers"
        for dirty in (False, True):
            with self.subTest(dirty=dirty):
                self.values["default-samplerate"] = 48000
                self.project.has_unsaved_changes = dirty
                self.updates.update_untracked.side_effect = lambda *args: setattr(
                    self.project, "has_unsaved_changes", True)
                self.check()
                self.assertEqual(self.project.has_unsaved_changes, dirty)
                self.assertEqual(self.values["default-samplerate"], 44100)
                self.assertEqual(self.values["playback-audio-device"], "Fallback Speakers||ALSA")
        self.updates.update_untracked.assert_called_with(["sample_rate"], 44100)
        self.assertEqual(self.lib_settings.PLAYBACK_AUDIO_DEVICE_NAME, "Fallback Speakers")
        self.assertEqual(self.lib_settings.PLAYBACK_AUDIO_DEVICE_TYPE, "ALSA")
        self.worker.error_found.emit.assert_not_called()

    def test_success_with_unchanged_metadata_does_not_write_settings(self):
        self.check()
        self.settings.set.assert_not_called()
        self.updates.update_untracked.assert_not_called()

    def test_unknown_rate_still_normalizes_legacy_float_setting(self):
        self.values["default-samplerate"] = 48000.0
        self.worker.player.GetDefaultSampleRate.return_value = 0
        self.check()
        self.assertIs(type(self.values["default-samplerate"]), int)
        self.assertEqual(self.values["default-samplerate"], 48000)


if __name__ == "__main__":
    unittest.main()
