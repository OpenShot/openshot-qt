"""Waveform jobs tolerate media which is no longer readable."""

import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from classes import waveform


class WaveformErrorTests(unittest.TestCase):
    def test_missing_source_does_not_escape_worker_or_set_wait_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            file = SimpleNamespace(id="file", data={
                "path": os.path.join(directory, "missing.wav"), "has_audio": True})
            app = SimpleNamespace(window=Mock())
            with patch.object(waveform.File, "get", return_value=file), \
                    patch.object(waveform, "get_app", return_value=app):
                waveform.get_waveform_thread("file", [], None)
            app.window.WaitCursorSignal.emit.assert_not_called()
            # Leave the waveform unset, so restoring the media permits a retry.
            app.window.timeline.fileAudioDataReady.emit.assert_called_once()
            self.assertIsNone(app.window.timeline.fileAudioDataReady.emit.call_args[0][1]["ui"]["audio_data"])
