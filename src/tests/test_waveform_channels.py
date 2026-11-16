"""
 @file
 @brief Waveform generation decodes each file once, keeps per-channel envelopes,
        and stays compatible with waveform data saved by older projects.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import struct
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import wave

import openshot

from classes import waveform
from classes import waveform_cache


# The real class, captured before tests patch openshot.AudioWaveformer
REAL_WAVEFORMER = openshot.AudioWaveformer

SAMPLE_RATE = 8000
SECONDS = 2.0
LEFT_LEVEL = 0.8
RIGHT_LEVEL = 0.2


def write_stereo_wav(path, left=LEFT_LEVEL, right=RIGHT_LEVEL, seconds=SECONDS, rate=SAMPLE_RATE):
    """Write a stereo 16-bit WAV with a different sine level on each channel."""
    frames = []
    for index in range(int(seconds * rate)):
        value = math.sin(2 * math.pi * 440 * index / rate)
        frames.append(struct.pack('<hh', int(32767 * left * value), int(32767 * right * value)))
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b''.join(frames))


def keyframe(*points):
    """Build a real libopenshot keyframe from (x, y) points."""
    result = openshot.Keyframe()
    for x, y in points:
        result.AddPoint(x, y, openshot.LINEAR)
    return result


def keyframe_json(*points):
    return {"Points": [{"co": {"X": x, "Y": y}, "interpolation": openshot.LINEAR} for x, y in points]}


class CountingWaveformer:
    """Wrap AudioWaveformer, counting decode passes over the source media."""

    def __init__(self, harness, reader):
        self.harness = harness
        self.inner = REAL_WAVEFORMER(reader)

    def ExtractSamples(self, *args):
        self.harness.decodes.append(("mixed", args))
        return self.inner.ExtractSamples(*args)

    def ExtractChannelSamples(self, *args):
        self.harness.decodes.append(("channels", args))
        return self.inner.ExtractChannelSamples(*args)

    def ApplyKeyframes(self, *args):
        return self.inner.ApplyKeyframes(*args)


class WaveformHarness:
    """A project file with clips, wired to waveform.py with GUI signals captured."""

    def __init__(self, test, path, file_ui=None, duration=SECONDS):
        self.test = test
        self.file = types.SimpleNamespace(id="F1", data={
            "id": "F1", "path": str(path), "has_audio": True, "channels": 2,
            "ui": file_ui if file_ui is not None else {},
        })
        self.clips = {}
        self.instances = {}
        self.duration = duration
        self.file_emits = []
        self.clip_emits = []
        self.decodes = []
        self.app = types.SimpleNamespace(
            window=types.SimpleNamespace(
                WaitCursorSignal=types.SimpleNamespace(emit=lambda *_args: None),
                timeline_sync=types.SimpleNamespace(
                    timeline=types.SimpleNamespace(GetClip=self.instances.get)),
                timeline=types.SimpleNamespace(
                    fileAudioDataReady=types.SimpleNamespace(emit=self._file_ready),
                    clipAudioDataReady=types.SimpleNamespace(
                        emit=lambda clip_id, ui, tid: self.clip_emits.append((clip_id, ui, tid))),
                ),
            ),
            get_settings=lambda: types.SimpleNamespace(get=lambda _key: 200),
        )

    def _file_ready(self, file_id, ui, tid):
        self.file_emits.append((file_id, ui, tid))
        # Mirror UpdateManager: a file update replaces the whole "ui" dictionary
        self.file.data.update(copy.deepcopy(ui))

    def add_clip(self, clip_id, channel=-1, volume=((1, 1.0),), time=((1, 1.0),)):
        self.clips[clip_id] = types.SimpleNamespace(id=clip_id, data={
            "id": clip_id, "file_id": "F1",
            "channel_filter": keyframe_json((1, channel)),
            "volume": keyframe_json(*volume),
            "time": keyframe_json(*time),
        })
        self.instances[clip_id] = types.SimpleNamespace(
            info=types.SimpleNamespace(duration=self.duration),
            time=keyframe(*time),
            volume=keyframe(*volume),
        )

    def run(self, clip_ids, tid="tid-1", envelopes=None, waveformer=None):
        factory = waveformer or (lambda reader: CountingWaveformer(self, reader))
        with patch.object(waveform.File, "get", return_value=self.file), \
                patch.object(waveform.Clip, "get", side_effect=lambda id=None: self.clips.get(id)), \
                patch.object(waveform, "get_app", return_value=self.app), \
                patch.object(waveform, "project_fps_fraction", return_value=Fraction(30, 1)), \
                patch.object(waveform.openshot, "AudioWaveformer", side_effect=factory):
            waveform.get_waveform_thread("F1", clip_ids, tid, envelopes)

    def clip_samples(self, clip_id, key="audio_data"):
        """Return the final (non-placeholder) envelope emitted for a clip."""
        for emitted_id, ui, _tid in reversed(self.clip_emits):
            if emitted_id == clip_id and ui["ui"].get(key) is not None:
                return list(waveform_cache.samples(ui["ui"][key])), ui["ui"]
        return None, None

    def stored_file_ui(self):
        return self.file.data.get("ui", {})


class WaveformChannelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache_patch = patch.object(waveform_cache, "cache_directory", lambda: str(self.root / "cache"))
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        waveform_cache._buffers.clear()
        waveform_cache._buffer_bytes = 0
        waveform._waveform_retry_counts.clear()
        self.wav = self.root / "stereo.wav"
        write_stereo_wav(self.wav)

    def assertLevel(self, values, level, places=1):
        """Assert the envelope's middle sits at the expected peak level."""
        self.assertTrue(values)
        middle = values[len(values) // 2]
        self.assertAlmostEqual(middle, level, places=places)

    # --- Separate audio (one decode pass for every channel) ---------------------------

    def test_separate_channels_decode_the_file_once(self):
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("C0", channel=0)
        harness.add_clip("C1", channel=1)
        harness.run(["C0", "C1"])

        self.assertEqual([kind for kind, _args in harness.decodes], ["channels"])
        left, left_ui = harness.clip_samples("C0")
        right, _ = harness.clip_samples("C1")
        self.assertLevel(left, LEFT_LEVEL)
        self.assertLevel(right, RIGHT_LEVEL)
        self.assertEqual(len(left), int(SECONDS * 200))
        self.assertEqual(left_ui[waveform.WAVEFORM_RATE_KEY], 200)
        self.assertEqual(left_ui[waveform.WAVEFORM_FORMAT_KEY], waveform.ABSOLUTE_WAVEFORM_FORMAT)

        # The file keeps its mixed envelope, plus per-channel envelopes for later reuse
        stored = harness.stored_file_ui()
        self.assertLevel(list(waveform_cache.samples(stored["audio_data"])), LEFT_LEVEL)
        channels = waveform.stored_channel_envelopes(stored)
        self.assertEqual(len(channels), 2)
        self.assertLevel(list(channels[1][0]), RIGHT_LEVEL)
        # Stored as small cache references, never inline arrays in the project JSON
        self.assertLess(len(json.dumps(stored)), 2000)
        for entry in stored[waveform.WAVEFORM_CHANNELS_KEY]:
            self.assertTrue(waveform_cache.is_reference(entry["audio_data"]))
            self.assertTrue(waveform_cache.is_reference(entry[waveform.WAVEFORM_RMS_KEY]))

    def test_all_channels_clip_with_separated_channels_shares_one_decode(self):
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("ALL", channel=-1)
        harness.add_clip("C1", channel=1)
        harness.run(["ALL", "C1"])
        self.assertEqual(len(harness.decodes), 1)
        self.assertLevel(harness.clip_samples("ALL")[0], LEFT_LEVEL)
        self.assertLevel(harness.clip_samples("C1")[0], RIGHT_LEVEL)

    def test_stored_channel_envelopes_are_reused_without_decoding(self):
        first = WaveformHarness(self, self.wav)
        first.add_clip("C0", channel=0)
        first.run(["C0"])
        self.assertEqual(len(first.decodes), 1)

        # Reopen the project: a new worker sees only the saved file data
        waveform_cache._buffers.clear()
        waveform_cache._buffer_bytes = 0
        second = WaveformHarness(self, self.wav, file_ui=json.loads(json.dumps(first.stored_file_ui())))
        second.add_clip("C1", channel=1)
        second.add_clip("ALL", channel=-1)
        second.run(["C1", "ALL"])
        self.assertEqual(second.decodes, [])
        self.assertLevel(second.clip_samples("C1")[0], RIGHT_LEVEL)
        self.assertLevel(second.clip_samples("ALL")[0], LEFT_LEVEL)

    def test_mixed_only_files_decode_without_channels(self):
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("ALL", channel=-1)
        harness.run(["ALL"])
        self.assertEqual([kind for kind, _args in harness.decodes], ["mixed"])
        self.assertNotIn(waveform.WAVEFORM_CHANNELS_KEY, harness.stored_file_ui())

    def test_invalid_channel_produces_no_waveform(self):
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("C9", channel=9)
        harness.run(["C9"])
        self.assertEqual(harness.clip_samples("C9"), (None, None))

    def test_missing_channel_cache_file_is_regenerated(self):
        first = WaveformHarness(self, self.wav)
        first.add_clip("C0", channel=0)
        first.run(["C0"])
        saved = json.loads(json.dumps(first.stored_file_ui()))

        # The waveform cache was cleared (or the project moved without its assets)
        for path in (self.root / "cache").iterdir():
            path.unlink()
        waveform_cache._buffers.clear()
        waveform_cache._buffer_bytes = 0

        second = WaveformHarness(self, self.wav, file_ui=saved)
        second.add_clip("C1", channel=1)
        second.run(["C1"])
        self.assertEqual([kind for kind, _args in second.decodes], ["channels"])
        self.assertLevel(second.clip_samples("C1")[0], RIGHT_LEVEL)

    def test_worker_reuses_decoded_envelopes_across_batches(self):
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("C0", channel=0)
        harness.add_clip("C1", channel=1)
        envelopes = {}
        harness.run(["C0"], envelopes=envelopes)
        # Simulate the GUI thread not having saved the file data yet
        harness.file.data["ui"] = {}
        harness.run(["C1"], envelopes=envelopes)
        self.assertEqual(len(harness.decodes), 1)
        self.assertLevel(harness.clip_samples("C1")[0], RIGHT_LEVEL)

    # --- Backwards compatibility with older projects ----------------------------------

    def test_legacy_inline_waveform_is_reused_for_all_channel_clips(self):
        legacy_ui = {"audio_data": [0.5] * 40}  # 20 Hz normalized_peak_v1, no format or rate keys
        harness = WaveformHarness(self, self.wav, file_ui=legacy_ui)
        harness.add_clip("ALL", channel=-1)
        harness.run(["ALL"])
        self.assertEqual(harness.decodes, [])
        values, ui = harness.clip_samples("ALL")
        self.assertEqual(values, [0.5] * 40)
        self.assertEqual(ui[waveform.WAVEFORM_FORMAT_KEY], waveform.LEGACY_WAVEFORM_FORMAT)
        self.assertEqual(ui[waveform.WAVEFORM_RATE_KEY], waveform.LEGACY_SAMPLES_PER_SECOND)

    def test_legacy_project_separating_channels_regenerates_consistently(self):
        legacy_ui = {"audio_data": [0.5] * 40}
        harness = WaveformHarness(self, self.wav, file_ui=legacy_ui)
        harness.add_clip("C1", channel=1)
        harness.run(["C1"])
        self.assertEqual([kind for kind, _args in harness.decodes], ["channels"])

        # Mixed and channel envelopes are replaced together, never mixing 20 Hz and 200 Hz data
        stored = harness.stored_file_ui()
        self.assertEqual(stored[waveform.WAVEFORM_RATE_KEY], 200)
        self.assertEqual(stored[waveform.WAVEFORM_FORMAT_KEY], waveform.ABSOLUTE_WAVEFORM_FORMAT)
        mixed = waveform_cache.samples(stored["audio_data"])
        for peaks, rms in waveform.stored_channel_envelopes(stored):
            self.assertEqual(len(peaks), len(mixed))
            self.assertEqual(len(rms), len(mixed))
        values, ui = harness.clip_samples("C1")
        self.assertLevel(values, RIGHT_LEVEL)
        self.assertEqual(ui[waveform.WAVEFORM_RATE_KEY], 200)

    def test_channel_envelopes_with_legacy_format_are_ignored(self):
        legacy_channels = {
            "audio_data": [0.5] * 40,
            waveform.WAVEFORM_CHANNELS_KEY: [{"audio_data": [0.1] * 40}, {"audio_data": [0.1] * 40}],
        }
        self.assertIsNone(waveform.stored_channel_envelopes(legacy_channels))
        self.assertIsNone(waveform.stored_channel_envelopes({}))
        self.assertIsNone(waveform.stored_channel_envelopes(None))
        broken = {waveform.WAVEFORM_FORMAT_KEY: waveform.ABSOLUTE_WAVEFORM_FORMAT,
                  waveform.WAVEFORM_CHANNELS_KEY: [{"audio_data": [0.1]}, "bad"]}
        self.assertIsNone(waveform.stored_channel_envelopes(broken))

    def test_saved_project_with_inline_channel_arrays_is_externalized(self):
        ui = {"ui": {
            "audio_data": [0.25] * 1000,
            waveform.WAVEFORM_RMS_KEY: [0.125] * 1000,
            waveform.WAVEFORM_FORMAT_KEY: waveform.ABSOLUTE_WAVEFORM_FORMAT,
            waveform.WAVEFORM_RATE_KEY: 200,
            waveform.WAVEFORM_CHANNELS_KEY: [
                {"audio_data": [0.5] * 1000, waveform.WAVEFORM_RMS_KEY: [0.25] * 1000},
                {"audio_data": [0.1] * 1000, waveform.WAVEFORM_RMS_KEY: [0.05] * 1000},
            ],
        }}
        project = {"files": [ui], "history": {"undo": [copy.deepcopy(ui)]}}
        waveform_cache.externalize(project)
        self.assertLess(len(json.dumps(project)), 2000)

        # Saving copies every referenced envelope (channels included) into the project assets
        assets = self.root / "project_assets" / "waveforms"
        waveform_cache.transfer(project, str(assets))
        self.assertEqual(len(list(assets.iterdir())), 5)

        # Another machine only has the project and its assets
        self.cache_patch.stop()
        with patch.object(waveform_cache, "cache_directory", lambda: str(self.root / "other")):
            waveform_cache._buffers.clear()
            waveform_cache._buffer_bytes = 0
            loaded = json.loads(json.dumps(project))
            waveform_cache.transfer(loaded, str(assets), importing=True)
            channels = waveform.stored_channel_envelopes(loaded["files"][0]["ui"])
            self.assertEqual(len(channels), 2)
            self.assertAlmostEqual(channels[1][0][0], 0.1, places=5)
        self.cache_patch.start()

    # --- Volume and time curves (applied in libopenshot) ------------------------------

    def test_volume_curve_scales_peak_and_rms(self):
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("FADE", channel=0, volume=((1, 0.0), (60, 1.0)))
        harness.add_clip("HALF", channel=0, volume=((1, 0.5),))
        harness.add_clip("FULL", channel=0)
        harness.run(["FADE", "HALF", "FULL"])
        full, _ = harness.clip_samples("FULL")
        full_rms, _ = harness.clip_samples("FULL", waveform.WAVEFORM_RMS_KEY)
        half, _ = harness.clip_samples("HALF")
        half_rms, _ = harness.clip_samples("HALF", waveform.WAVEFORM_RMS_KEY)
        fade, _ = harness.clip_samples("FADE")
        self.assertEqual(len(half), len(full))
        self.assertEqual(len(fade), len(full))
        for index in range(0, len(full), 37):
            self.assertAlmostEqual(half[index], full[index] * 0.5, places=4)
            self.assertAlmostEqual(half_rms[index], full_rms[index] * 0.5, places=4)
        # Fade-in starts silent and reaches full level by frame 60 (2 seconds)
        self.assertAlmostEqual(fade[0], 0.0, places=4)
        self.assertLess(fade[100], fade[300])
        self.assertAlmostEqual(fade[-1], full[-1], places=2)

    def test_time_curve_slows_and_reverses_waveform(self):
        frames = int(SECONDS * 30)
        harness = WaveformHarness(self, self.wav)
        harness.add_clip("FULL", channel=-1)
        harness.add_clip("SLOW", channel=-1, time=((1, 1), (frames * 2, frames)))
        harness.add_clip("REV", channel=-1, time=((1, frames), (frames, 1)))
        harness.run(["FULL", "SLOW", "REV"])
        full, _ = harness.clip_samples("FULL")
        slow, _ = harness.clip_samples("SLOW")
        rev, _ = harness.clip_samples("REV")
        # Slowed to half speed: twice as many waveform samples (within one sample)
        self.assertAlmostEqual(len(slow), len(full) * 2, delta=1)
        self.assertAlmostEqual(len(rev), len(full), delta=1)
        self.assertLevel(slow, LEFT_LEVEL)
        self.assertLevel(rev, LEFT_LEVEL)

    def test_clip_shorter_than_source_is_trimmed(self):
        harness = WaveformHarness(self, self.wav, duration=1.0)
        harness.add_clip("SHORT", channel=1, volume=((1, 0.5),))
        harness.run(["SHORT"])
        values, _ = harness.clip_samples("SHORT")
        self.assertEqual(len(values), 200)
        self.assertLevel(values, RIGHT_LEVEL * 0.5, places=2)


class WaveformWorkerTests(unittest.TestCase):
    """Concurrent requests for one file share a single worker."""

    def setUp(self):
        waveform._inflight.clear()
        self.addCleanup(waveform._inflight.clear)

    def test_requests_for_a_running_file_join_its_worker(self):
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        calls = []

        def fake_thread(file_id, clip_list, tid, envelopes):
            calls.append((file_id, list(clip_list), tid))
            envelopes.setdefault("decodes", 0)
            if "source" not in envelopes:
                envelopes["source"] = True
                envelopes["decodes"] += 1
                started.set()
                release.wait(5)
            if len(calls) == 3:
                envelopes_seen.append(dict(envelopes))
                finished.set()

        envelopes_seen = []
        with patch.object(waveform, "get_waveform_thread", side_effect=fake_thread):
            waveform.get_audio_data({"F1": ["C1"]}, transaction_id="t1")
            self.assertTrue(started.wait(5))
            waveform.get_audio_data({"F1": ["C2"]}, transaction_id="t2")
            waveform.get_audio_data({"F1": ["C3"]}, transaction_id="t3")
            release.set()
            self.assertTrue(finished.wait(5))

        self.assertEqual(calls, [("F1", ["C1"], "t1"), ("F1", ["C2"], "t2"), ("F1", ["C3"], "t3")])
        self.assertEqual(envelopes_seen[0]["decodes"], 1)
        self._wait_for_idle("F1")

    def test_failed_batches_do_not_block_later_requests(self):
        done = threading.Event()
        calls = []

        def failing_thread(file_id, clip_list, tid, envelopes):
            calls.append(tid)
            if tid == "boom":
                raise RuntimeError("decoder failed")
            done.set()

        with patch.object(waveform, "get_waveform_thread", side_effect=failing_thread):
            waveform.get_audio_data({"F1": ["C1"]}, transaction_id="boom")
            self._wait_for_idle("F1")
            waveform.get_audio_data({"F1": ["C1"]}, transaction_id="retry")
            self.assertTrue(done.wait(5))
        self.assertEqual(calls, ["boom", "retry"])
        self._wait_for_idle("F1")

    def test_different_files_decode_in_parallel(self):
        barrier = threading.Barrier(2, timeout=5)

        def parallel_thread(file_id, clip_list, tid, envelopes):
            barrier.wait()

        with patch.object(waveform, "get_waveform_thread", side_effect=parallel_thread):
            waveform.get_audio_data({"F1": ["C1"], "F2": ["C2"]})
            self._wait_for_idle("F1")
            self._wait_for_idle("F2")
        self.assertFalse(barrier.broken)

    def _wait_for_idle(self, file_id):
        for _attempt in range(500):
            with waveform._inflight_lock:
                if file_id not in waveform._inflight:
                    return
            threading.Event().wait(0.01)
        self.fail("waveform worker for %s never finished" % file_id)


if __name__ == "__main__":
    unittest.main()
