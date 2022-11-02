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
from classes.app import get_app
from classes.logger import log
from classes.query import File, Clip
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt
import openshot

# Get settings
s = get_app().get_settings()

# resolution of audio waveform
SAMPLES_PER_SECOND = 20


def get_audio_data(files: dict):
    """Get a Clip object form libopenshot, and grab audio data
        For for the given files and clips, start threads to gather audio data.

        arg1: a dict of clip_ids grouped by their file_id
    """

    for file_id in files:
        clip_list = files[file_id]

        log.info("Clip loaded, start thread")
        t = threading.Thread(target=get_waveform_thread, args=[file_id, clip_list], daemon=True)
        t.start()


def get_waveform_thread(file_id, clip_list):
    """
    For the given file ID and clip IDs, update audio data.

    arg1: file id to get the audio data of.
    arg2: list of clips to update when the audio data is ready.
    """

    def getAudioData(file, channel=-1):
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
            get_app().window.timeline.fileAudioDataReady.emit(file.id, {"ui": {"audio_data": max_samples_vector}})

        # Restore cursor
        get_app().restoreOverrideCursor()

        # Return audio sample dataset
        return max_samples_vector

    # Get file query object
    file = File.get(id=file_id)

    # Only generate audio for readers that actually contain audio
    if not file.data.get("has_audio", False):
        log.info("File does not have audio. Skipping")
        return

    # If the file doesn't have audio data, generate it.
    # A pending audio_data process will have audio_data == [-999]
    file_audio_data = file.data.get("ui", {}).get("audio_data", [])
    if not file_audio_data:
        # Generate audio data for a specific file
        log.debug("Generating audio data for file %s" % file.id)
        file_audio_data = getAudioData(file)

    if not file_audio_data:
        log.info("No audio data found. Aborting")
        return
    log.debug("Audio data found for file: %s" % file.data.get("path"))

    # Loop through each selected clip (which uses this file)
    for clip_id in clip_list:
        clip = Clip.get(id=clip_id)

        # Check for channel mapping and filters
        channel_filter = int(clip.data.get("channel_filter", {}).get("Points", [])[0].get("co", {}).get("Y", -1))
        if channel_filter != -1:
            # Some kind of filtering is happening, so we need to re-generate waveform data for this clip
            file_audio_data = getAudioData(file, channel_filter)

        # Get File's audio data (since it has changed)
        if not file_audio_data:
            log.info("File has no audio, so we cannot find any waveform audio data")
            continue

        # If clip already has waveform, remove it to re-calculate.
        # (Used when volume changes the shape of the waveform)
        if bool(clip.data.get("ui", {}).get("audio_data", [])):
            log.debug("Removing pre-existing audio data")
            get_app().window.timeline.audioDataReady.emit(clip.id, {"ui": {"audio_data": None}})

        # Loop through samples from the file, applying this clip's volume curve
        clip_audio_data = []
        clip_instance = get_app().window.timeline_sync.timeline.GetClip(clip.id)
        num_frames = clip_instance.info.video_length

        # Determine best guess # of samples (based on duration)
        # We don't want to use the len(file_audio_data) due to padding at EOF
        # from libopenshot
        sample_count = round(clip_instance.info.duration * SAMPLES_PER_SECOND)

        # Determine sample ratio to FPS
        sample_ratio = float(sample_count / num_frames)

        # Loop through file samples and adjust time/volume values
        # Copy adjusted samples into clip data
        for sample_index in range(sample_count):
            frame_num = round(sample_index / sample_ratio) + 1
            volume = clip_instance.volume.GetValue(frame_num)
            if clip_instance.time.GetCount() > 1:
                # Override sample # using time curve (if set)
                # Don't exceed array size
                sample_index = min(round(clip_instance.time.GetValue(frame_num) * sample_ratio), sample_count - 1)
            clip_audio_data.append(file_audio_data[sample_index] * volume)

        # Save this data to the clip object
        get_app().window.timeline.audioDataReady.emit(clip.id, {"ui": {"audio_data": clip_audio_data}})
