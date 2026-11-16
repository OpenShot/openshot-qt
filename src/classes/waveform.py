"""
 @file
 @brief This file has code to generate audio waveform data structures
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

from array import array
import math
import threading
import uuid
from functools import partial

import openshot

from classes.waveform_cache import samples, externalize
from classes.app import get_app
from classes.logger import log
from classes.query import File, Clip
from classes.clip_utils import project_fps_fraction

# Waveform resolution. Older projects did not store their density and used the
# original 20 Hz extraction rate. New v2 waveforms default to 200 Hz.
LEGACY_SAMPLES_PER_SECOND = 20
DEFAULT_SAMPLES_PER_SECOND = 200
SAMPLES_PER_SECOND = DEFAULT_SAMPLES_PER_SECOND

# Waveform formats stored in project UI data. Projects created before waveform
# formats were introduced have no marker, and must retain their original
# normalized, linear display behavior.
LEGACY_WAVEFORM_FORMAT = "normalized_peak_v1"
ABSOLUTE_WAVEFORM_FORMAT = "absolute_peak_v2"
WAVEFORM_FORMAT_KEY = "audio_data_format"
WAVEFORM_RMS_KEY = "audio_data_rms"
WAVEFORM_RATE_KEY = "audio_data_rate"
# Optional per-channel envelopes stored on files: a list with one
# {"audio_data": ..., "audio_data_rms": ...} entry per source channel, sharing
# the file's format and rate. Projects without it regenerate it on demand.
WAVEFORM_CHANNELS_KEY = "audio_data_channels"

# Expand quiet absolute samples without normalizing clips independently. A
# square-root curve keeps the noise floor thin while making normal speech easy
# to edit. A small lookup table avoids power calculations in the paint loop.
WAVEFORM_DISPLAY_EXPONENT = 0.5
WAVEFORM_DISPLAY_LUT_SIZE = 4096


def _build_waveform_display_lut():
    values = []
    for index in range(WAVEFORM_DISPLAY_LUT_SIZE):
        amplitude = index / float(WAVEFORM_DISPLAY_LUT_SIZE - 1)
        values.append(amplitude ** WAVEFORM_DISPLAY_EXPONENT)
    return tuple(values)


WAVEFORM_DISPLAY_LUT = _build_waveform_display_lut()


def waveform_data_format(ui_data):
    """Return the stored waveform format, defaulting old projects to legacy."""
    if not isinstance(ui_data, dict):
        return LEGACY_WAVEFORM_FORMAT
    return ui_data.get(WAVEFORM_FORMAT_KEY) or LEGACY_WAVEFORM_FORMAT


def waveform_sample_rate(ui_data):
    """Return stored waveform density, defaulting older data to 20 Hz."""
    if not isinstance(ui_data, dict):
        return LEGACY_SAMPLES_PER_SECOND
    try:
        rate = int(ui_data.get(WAVEFORM_RATE_KEY) or LEGACY_SAMPLES_PER_SECOND)
    except (TypeError, ValueError):
        rate = LEGACY_SAMPLES_PER_SECOND
    return rate if rate > 0 else LEGACY_SAMPLES_PER_SECOND


def configured_waveform_sample_rate():
    """Return the preferred density for newly generated waveform data."""
    try:
        settings = get_app().get_settings()
        rate = int(settings.get("timeline-waveform-samples-per-second"))
    except (AttributeError, TypeError, ValueError):
        rate = DEFAULT_SAMPLES_PER_SECOND
    return max(20, min(1000, rate))


def waveform_display_amplitude(amplitude, data_format):
    """Map a stored amplitude to display height without per-clip normalization."""
    try:
        amplitude = abs(float(amplitude))
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(amplitude):
        return 0.0
    if data_format != ABSOLUTE_WAVEFORM_FORMAT:
        return amplitude
    if amplitude <= 0.0:
        return 0.0
    index = min(
        WAVEFORM_DISPLAY_LUT_SIZE - 1,
        int(amplitude * (WAVEFORM_DISPLAY_LUT_SIZE - 1)),
    )
    return WAVEFORM_DISPLAY_LUT[index]


TIME_CURVE_RETRY_DELAY = 0.05
TIME_CURVE_MAX_RETRIES = 5

_waveform_retry_counts = {}


def _schedule_waveform_retry(file_id, clip_id, tid, reason=""):
    """Retry waveform generation for clips whose time curve or clip instance isn't ready."""

    attempts = _waveform_retry_counts.get(clip_id, 0)
    if attempts >= TIME_CURVE_MAX_RETRIES:
        _waveform_retry_counts.pop(clip_id, None)
        return False

    _waveform_retry_counts[clip_id] = attempts + 1

    if reason:
        log.debug(
            "Scheduling waveform retry %s/%s for clip %s (%s)",
            attempts + 1,
            TIME_CURVE_MAX_RETRIES,
            clip_id,
            reason,
        )

    timer = threading.Timer(
        TIME_CURVE_RETRY_DELAY,
        partial(get_audio_data, {file_id: [clip_id]}),
        kwargs={"transaction_id": tid},
    )
    timer.daemon = True
    timer.start()
    return True


# Files with a running waveform worker, mapped to clip batches waiting for it.
# Requests for a file which is already being decoded join that worker, so a
# file is never decoded twice at the same time.
_inflight_lock = threading.Lock()
_inflight = {}


def get_audio_data(files: dict, transaction_id=None):
    """Get a Clip object form libopenshot, and grab audio data
        For for the given files and clips, start threads to gather audio data.

        arg1: a dict of clip_ids grouped by their file_id
    """

    for file_id in files:
        batch = (list(files[file_id] or []), transaction_id)
        with _inflight_lock:
            pending = _inflight.get(file_id)
            if pending is not None:
                log.info("Waveform worker already running for file %s, queueing clips", file_id)
                pending.append(batch)
                continue
            _inflight[file_id] = [batch]

        log.info("Clip loaded, start thread")
        t = threading.Thread(target=_waveform_worker, args=[file_id], daemon=True)
        t.start()


def _waveform_worker(file_id):
    """Process every queued clip batch for a file, decoding the file at most once."""
    envelopes = {}
    finished = False
    try:
        while True:
            with _inflight_lock:
                batches = _inflight.get(file_id) or []
                if not batches:
                    _inflight.pop(file_id, None)
                    finished = True
                    return
                _inflight[file_id] = []
            for clip_list, tid in batches:
                try:
                    get_waveform_thread(file_id, clip_list, tid, envelopes)
                except Exception:
                    log.warning("Waveform generation failed for file %s", file_id, exc_info=True)
    finally:
        if not finished:
            # Never leave a file marked busy without a worker, or later requests would wait forever
            with _inflight_lock:
                _inflight.pop(file_id, None)


def _clip_channel_filter(clip):
    """Return the clip's channel filter (-1 for all channels)."""
    try:
        return int(clip.data.get("channel_filter", {}).get("Points", [])[0].get("co", {}).get("Y", -1))
    except (AttributeError, IndexError, TypeError, ValueError):
        return -1


def stored_channel_envelopes(file_ui):
    """Return [(peaks, rms), ...] stored on a file, or None when missing or unreadable."""
    entries = file_ui.get(WAVEFORM_CHANNELS_KEY) if isinstance(file_ui, dict) else None
    if not isinstance(entries, list) or not entries:
        return None
    if waveform_data_format(file_ui) != ABSOLUTE_WAVEFORM_FORMAT:
        return None
    channels = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        peaks = samples(entry.get("audio_data"))
        if not peaks:
            return None
        channels.append((peaks, samples(entry.get(WAVEFORM_RMS_KEY))))
    return channels


def _keyframe_copy(keyframe):
    """Copy a live clip keyframe, so the timeline can keep editing the original."""
    copy = openshot.Keyframe()
    copy.SetJson(keyframe.Json())
    return copy


def get_waveform_thread(file_id, clip_list, transaction_id, envelopes=None):
    """
    For the given file ID and clip IDs, update audio data.

    arg1: file id to get the audio data of.
    arg2: list of clips to update when the audio data is ready.
    arg3: tid: transaction id to group waveform saves together
    arg4: envelopes: dict shared by batches of one worker, holding decoded file envelopes
    """
    if envelopes is None:
        envelopes = {}

    def extract(file, with_channels, tid):
        """Decode the file once, store its envelopes, and return them (or None)."""
        file_data = file.data

        # Open file and access audio data (if audio data is found, otherwise return)
        try:
            temp_clip = openshot.Clip(file_data["path"])
            reader = temp_clip.Reader()
        except RuntimeError as ex:
            log.warning("Unable to open waveform source %s: %s", file_data["path"], ex)
            return None
        if reader.info.has_audio == False:
            log.info(f"file: {file_data['path']} has no audio_data. Skipping")
            return None

        # Show waiting cursor on the GUI thread
        get_app().window.WaitCursorSignal.emit(True)
        try:
            # Extract peak and RMS waveform envelopes. A single decode pass
            # also yields every channel's envelope when separate channels are needed.
            waveformer = openshot.AudioWaveformer(reader)
            sample_rate = configured_waveform_sample_rate()
            # Envelopes arrive as tuples of Python floats (32 bytes per value), so
            # pack each into a float32 array before fetching the next one.
            if with_channels:
                file_audio_data = waveformer.ExtractChannelSamples(sample_rate, False)
                channels = []
                for index in range(file_audio_data.channel_count()):
                    peaks, rms = file_audio_data.channel_vectors(index)
                    channels.append((array("f", peaks), array("f", rms)))
                    del peaks, rms
            else:
                file_audio_data = waveformer.ExtractSamples(-1, sample_rate, False)
                channels = None
            max_samples_vector, rms_samples_vector = (array("f", values) for values in file_audio_data.vectors())

            # Clear data
            file_audio_data.clear()

            ui = {
                "audio_data": max_samples_vector,
                WAVEFORM_RMS_KEY: rms_samples_vector,
                WAVEFORM_FORMAT_KEY: ABSOLUTE_WAVEFORM_FORMAT,
                WAVEFORM_RATE_KEY: sample_rate,
            }
            if channels:
                ui[WAVEFORM_CHANNELS_KEY] = [
                    {"audio_data": peaks, WAVEFORM_RMS_KEY: rms} for peaks, rms in channels
                ]
            ui = externalize({"ui": ui})
            get_app().window.timeline.fileAudioDataReady.emit(file.id, ui, tid)

            # Return audio sample datasets, resolved from the shared cache buffers
            stored = ui["ui"]
            return {
                "peaks": samples(stored["audio_data"]) or max_samples_vector,
                "rms": samples(stored[WAVEFORM_RMS_KEY]) or rms_samples_vector,
                "format": ABSOLUTE_WAVEFORM_FORMAT,
                "rate": sample_rate,
                "channels": stored_channel_envelopes(stored) or channels,
            }
        finally:
            # Restore cursor on the GUI thread even if extraction fails
            get_app().window.WaitCursorSignal.emit(False)

    # Get file query object
    file = File.get(id=file_id)

    # Only generate audio for readers that actually contain audio
    if not file or not file.data.get("has_audio", False):
        log.info("File does not have audio. Skipping")
        return

    # Transaction id to group all deletes together
    if transaction_id:
        tid = transaction_id
    else:
        tid = str(uuid.uuid4())

    clips = []
    for clip_id in clip_list:
        clip = Clip.get(id=clip_id)
        if not clip:
            # Ignore null clip
            log.debug(f"No clip found for ID: {clip_id}. Skipping waveform generation.")
            continue
        clips.append(clip)
    need_channels = any(_clip_channel_filter(clip) != -1 for clip in clips)

    # Reuse envelopes decoded earlier by this worker, then those stored on the file.
    # Decode the file (once) only when they are missing, or channels are needed
    # but were never stored (older projects).
    source = envelopes.get("source")
    if not source or (need_channels and not source.get("channels")):
        file_ui_data = file.data.get("ui", {})
        file_audio_data = samples(file_ui_data.get("audio_data"))
        stored_channels = stored_channel_envelopes(file_ui_data)
        if file_audio_data and (stored_channels or not need_channels):
            log.info("Audio Data already retrieved (or being retrieved).")
            source = {
                "peaks": file_audio_data,
                "rms": samples(file_ui_data.get(WAVEFORM_RMS_KEY)),
                "format": waveform_data_format(file_ui_data),
                "rate": waveform_sample_rate(file_ui_data),
                "channels": stored_channels,
            }
        else:
            log.debug("Generating audio data for file %s" % file.id)
            if not file_audio_data:
                # Save empty 'audio_data' property before we get audio samples
                get_app().window.timeline.fileAudioDataReady.emit(file.id, {"ui": {"audio_data": None}}, tid)
            source = extract(file, need_channels, tid)
        if source:
            envelopes["source"] = source

    if not source or not source.get("peaks"):
        log.info("No audio data found. Aborting")
        return
    log.debug("Audio data found for file: %s" % file.data.get("path"))

    # Loop through each selected clip (which uses this file)
    for clip in clips:
        # Check for channel mapping and filters
        channel_filter = _clip_channel_filter(clip)

        time_points = clip.data.get("time", {}).get("Points", [])
        has_time_curve = isinstance(time_points, list) and len(time_points) > 1

        clip_instance = get_app().window.timeline_sync.timeline.GetClip(clip.id)
        if not clip_instance:
            reason = "clip not yet available in timeline"
            if _schedule_waveform_retry(file_id, clip.id, tid, reason):
                log.info(
                    "Waveform request deferred; clip %s not ready yet. Retrying soon.",
                    clip.id,
                )
            else:
                log.info("Clip not found, bailing out of waveform volume adjustments")
            continue

        time_point_count = clip_instance.time.GetCount()

        if has_time_curve and time_point_count <= 1:
            reason = "time curve not ready"
            if _schedule_waveform_retry(file_id, clip.id, tid, reason):
                log.debug(
                    "Clip %s time curve not ready, scheduling waveform retry", clip.id
                )
                continue

        _waveform_retry_counts.pop(clip.id, None)

        file_audio_data, file_audio_rms = source["peaks"], source["rms"]
        file_audio_format, file_audio_rate = source["format"], source["rate"]
        if channel_filter != -1:
            # Use this channel's envelope, decoded with the others in one pass
            channels = source.get("channels") or []
            if 0 <= channel_filter < len(channels):
                file_audio_data, file_audio_rms = channels[channel_filter]
            else:
                file_audio_data, file_audio_rms = None, None

        # Get File's audio data (since it has changed)
        if not file_audio_data:
            log.info("File has no audio, so we cannot find any waveform audio data")
            continue
        file_audio_rms = file_audio_rms or ()

        # Save empty 'audio_data' property before we get audio samples
        get_app().window.timeline.clipAudioDataReady.emit(
            clip.id, {"ui": {"audio_data": None}}, tid
        )

        # Determine best guess # of samples (based on duration)
        # We don't want to use the len(file_audio_data) due to padding at EOF
        # from libopenshot
        sample_count = round(clip_instance.info.duration * file_audio_rate)
        if not sample_count:
            log.debug(
                "No frames or samples available for clip %s when generating waveform", clip.id
            )
            continue

        file_data_len = len(file_audio_data)
        file_rms_len = len(file_audio_rms)
        # Most clips have no time/volume edits. Reuse the source envelope
        # without per-sample work.
        volume_points = clip.data.get("volume", {}).get("Points", [])
        unity_volume = (len(volume_points) == 1
                        and volume_points[0].get("co", {}).get("Y") == 1)
        if (time_point_count <= 1 and unity_volume and sample_count <= file_data_len
                and (not file_rms_len or sample_count <= file_rms_len)):
            clip_audio_data = file_audio_data[:sample_count]
            clip_audio_rms = file_audio_rms[:sample_count]
        else:
            # Map the clip's time and volume curves onto the envelope in C++
            time_keyframe = _keyframe_copy(clip_instance.time) if time_point_count > 1 else None
            volume_keyframe = _keyframe_copy(clip_instance.volume)
            if time_keyframe is None:
                # Without a time curve, the clip spans its source duration
                file_audio_data = file_audio_data[:sample_count]
                file_audio_rms = file_audio_rms[:sample_count]
            project_fps = project_fps_fraction()
            adjusted = openshot.AudioWaveformer(None).ApplyKeyframes(
                file_audio_data,
                file_audio_rms,
                time_keyframe,
                volume_keyframe,
                openshot.Fraction(int(project_fps.numerator), int(project_fps.denominator)),
                int(file_audio_rate),
            )
            clip_audio_data, clip_audio_rms = adjusted.vectors()
            adjusted.clear()
            if not file_rms_len:
                clip_audio_rms = []
        # Save this data to the clip object
        get_app().window.timeline.clipAudioDataReady.emit(
            clip.id,
            externalize({"ui": {
                "audio_data": clip_audio_data,
                WAVEFORM_RMS_KEY: clip_audio_rms,
                WAVEFORM_FORMAT_KEY: file_audio_format,
                WAVEFORM_RATE_KEY: file_audio_rate,
            }}),
            tid,
        )
