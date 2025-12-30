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

import threading
from functools import partial
from classes.app import get_app
from classes.logger import log
from classes.query import File, Clip
from classes.clip_utils import project_fps_fraction, video_length_to_project_frames
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt
import openshot
import uuid

# resolution of audio waveform
SAMPLES_PER_SECOND = 20

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


def get_audio_data(files: dict, transaction_id=None):
    """Get a Clip object form libopenshot, and grab audio data
        For for the given files and clips, start threads to gather audio data.

        arg1: a dict of clip_ids grouped by their file_id
    """

    for file_id in files:
        clip_list = files[file_id]

        log.info("Clip loaded, start thread")
        t = threading.Thread(target=get_waveform_thread, args=[file_id, clip_list, transaction_id], daemon=True)
        t.start()


def get_waveform_thread(file_id, clip_list, transaction_id):
    """
    For the given file ID and clip IDs, update audio data.

    arg1: file id to get the audio data of.
    arg2: list of clips to update when the audio data is ready.
    arg3: tid: transaction id to group waveform saves together
    """

    def getAudioData(file, channel=-1, tid=None):
        """
        Update the file query object with audio data (if found).
        """
        # Ensure that UI attribute exists
        file_data = file.data
        file_audio_data = file_data.get("ui", {}).get("audio_data", [])
        if file_audio_data and channel == -1:
            log.info("Audio Data already retrieved (or being retrieved).")
            return

        # Open file and access audio data (if audio data is found, otherwise return)
        temp_clip = openshot.Clip(file_data["path"])
        if temp_clip.Reader().info.has_audio == False:
            log.info(f"file: {file_data['path']} has no audio_data. Skipping")
            return

        # Show waiting cursor
        get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

        # Extract audio waveform data (for all channels)
        # Use max RMS (root mean squared) value for each sample
        # NOTE: we also have the average RMS value calculated, although we do
        # not use it yet
        waveformer = openshot.AudioWaveformer(temp_clip.Reader())
        file_audio_data = waveformer.ExtractSamples(channel, SAMPLES_PER_SECOND, True)
        samples_vectors = file_audio_data.vectors()
        max_samples_vector = samples_vectors[0]  # max sample value dataset
        rms_samples_vector = samples_vectors[1]  # average RMS sample value dataset

        # Clear data
        file_audio_data.clear()

        # Update file with audio data (only if all channels requested)
        if channel == -1:
            get_app().window.timeline.fileAudioDataReady.emit(file.id, {"ui": {"audio_data": max_samples_vector}}, tid)

        # Restore cursor
        get_app().restoreOverrideCursor()

        # Return audio sample dataset
        return max_samples_vector

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

    # If the file doesn't have audio data, generate it.
    # A pending audio_data process will have audio_data == [-999]
    file_audio_data = file.data.get("ui", {}).get("audio_data", [])
    if not file_audio_data:
        log.debug("Generating audio data for file %s" % file.id)
        # Save empty 'audio_data' property before we get audio samples
        get_app().window.timeline.fileAudioDataReady.emit(file.id, {"ui": {"audio_data": None}}, tid)
        # Generate audio data for a specific file
        file_audio_data = getAudioData(file, tid=tid)

    if not file_audio_data:
        log.info("No audio data found. Aborting")
        return
    log.debug("Audio data found for file: %s" % file.data.get("path"))

    # Loop through each selected clip (which uses this file)
    for clip_id in clip_list:
        clip = Clip.get(id=clip_id)

        if not clip:
            # Ignore null clip
            log.debug(f"No clip found for ID: {clip_id}. Skipping waveform generation.")
            continue

        # Check for channel mapping and filters
        channel_filter = int(
            clip.data.get("channel_filter", {}).get("Points", [])[0].get("co", {}).get("Y", -1)
        )

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

        if time_point_count > 1:
            # When time curves are present, generate waveform data from the clip instance itself
            _waveform_retry_counts.pop(clip.id, None)
            clip_audio_data = []
            channel = channel_filter if channel_filter != -1 else -1
            try:
                waveformer = openshot.AudioWaveformer(clip_instance)
                clip_wave_data = waveformer.ExtractSamples(
                    channel, SAMPLES_PER_SECOND, True
                )
                sample_vectors = clip_wave_data.vectors()
                if sample_vectors:
                    clip_audio_data = list(sample_vectors[0])
                clip_wave_data.clear()
            except Exception:
                log.error(
                    "Error generating clip waveform data for clip %s", clip.id, exc_info=1
                )

            if clip_audio_data:
                get_app().window.timeline.clipAudioDataReady.emit(
                    clip.id, {"ui": {"audio_data": clip_audio_data}}, tid
                )
                continue

            reason = "time curve waveform empty"
            if _schedule_waveform_retry(file_id, clip.id, tid, reason):
                log.debug(
                    "Clip %s waveform generation empty; retry scheduled", clip.id
                )
                continue

            log.warning(
                "Clip %s waveform generation failed after retries; leaving waveform unchanged",
                clip.id,
            )
            continue

        _waveform_retry_counts.pop(clip.id, None)

        if channel_filter != -1:
            # Some kind of filtering is happening, so we need to re-generate waveform data for this clip
            file_audio_data = getAudioData(file, channel_filter, tid=tid)

        # Get File's audio data (since it has changed)
        if not file_audio_data:
            log.info("File has no audio, so we cannot find any waveform audio data")
            continue

        # Save empty 'audio_data' property before we get audio samples
        get_app().window.timeline.clipAudioDataReady.emit(
            clip.id, {"ui": {"audio_data": None}}, tid
        )

        # Loop through samples from the file, applying this clip's volume curve
        clip_audio_data = []
        info = clip_instance.info
        proj_fraction = project_fps_fraction()
        num_frames = video_length_to_project_frames(
            None,
            video_length=getattr(info, 'video_length', None),
            fps=getattr(info, 'fps', None),
            duration=getattr(info, 'duration', None),
            project_fps=proj_fraction,
        )
        if num_frames:
            num_frames = int(num_frames)
        else:
            fallback_frames = getattr(info, 'video_length', 0)
            num_frames = int(fallback_frames) if fallback_frames else 0

        # Determine best guess # of samples (based on duration)
        # We don't want to use the len(file_audio_data) due to padding at EOF
        # from libopenshot
        sample_count = round(clip_instance.info.duration * SAMPLES_PER_SECOND)

        if not num_frames or not sample_count:
            log.debug(
                "No frames or samples available for clip %s when generating waveform", clip.id
            )
            continue

        # Determine sample ratio to FPS
        sample_ratio = float(sample_count / num_frames)

        # Loop through file samples and adjust time/volume values
        # Copy adjusted samples into clip data
        file_data_len = len(file_audio_data)
        if not file_data_len:
            log.debug(
                "File audio data is empty for clip %s, skipping waveform generation",
                clip.id,
            )
            continue
        for sample_index in range(sample_count):
            frame_num = round(sample_index / sample_ratio) + 1
            volume = clip_instance.volume.GetValue(frame_num)
            source_index = sample_index
            if time_point_count > 1:
                # Override sample # using time curve (if set)
                # Don't exceed array size
                source_index = min(
                    round(clip_instance.time.GetValue(frame_num) * sample_ratio),
                    sample_count - 1,
                )
            if file_data_len:
                source_index = min(source_index, file_data_len - 1)
            clip_audio_data.append(file_audio_data[source_index] * volume)

        # Save this data to the clip object
        get_app().window.timeline.clipAudioDataReady.emit(
            clip.id, {"ui": {"audio_data": clip_audio_data}}, tid
        )
