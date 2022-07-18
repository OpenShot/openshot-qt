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
from time import sleep
import openshot

# Get settings
s = get_app().get_settings()


def get_audio_data(files: dict):
    """Get a Clip object form libopenshot, and grab audio data
        For for the given files and clips, start threads to gather audio data.

        arg1: a dict of clip_ids grouped by their file_id
    """

    for file_id in files:
        clip_list = files[file_id]

        log.info("Clip loaded, start thread")
        t = threading.Thread(target=get_waveform_thread,
                             args=[file_id, clip_list])
        t.daemon = True
        t.start()


def get_waveform_thread(file_id, clip_list):
    """
    For the given file ID and clip IDs, update audio data.

    arg1: file id to get the audio data of.
    arg2: list of clips to update when the audio data is ready.
    """

    def getAudioData(file):
        """
        Update the file query object with audio data (if found).
        """
        get_app().window.actionClearWaveformData.setEnabled(True)
        # Ensure that UI attribute exists
        file_data = file.data
        file_audio_data = file_data.get("ui", {}).get("audio_data", [])
        if file_audio_data:
            log.info("Audio Data already retrieved (or being retrieved).")
            return

        # Open file and access audio data (if audio data is found, otherwise return)
        temp_clip = openshot.Clip(file_data["path"])
        temp_clip.Open()
        temp_clip.Reader().info.has_video = False
        if temp_clip.Reader().info.has_audio == False:
            log.info(f"file: {file_data['path']} has no audio_data. Skipping")
            return

        # Calculate sample rate (and how many samples per second)
        sample_rate = temp_clip.Reader().info.sample_rate
        samples_per_second = 20
        sample_divisor = round(sample_rate / samples_per_second)

        # Loop through audio samples, and create a list of amplitudes
        file_audio_data = []
        for frame_num in range(1, temp_clip.Reader().info.video_length):
            frame = temp_clip.Reader().GetFrame(frame_num)
            sample_num = 0
            max_samples = frame.GetAudioSamplesCount()
            while sample_num < max_samples:
                magnitude_range = sample_divisor
                if sample_num + magnitude_range > frame.GetAudioSamplesCount():
                    magnitude_range = frame.GetAudioSamplesCount() - sample_num
                sample_value = frame.GetAudioSample(-1, sample_num, magnitude_range)
                file_audio_data.append(sample_value)
                sample_num += sample_divisor

        # Update file with audio data
        file.data = {"ui": {"audio_data": file_audio_data}}
        file.save()
        return

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
        getAudioData(file)
    log.debug("Awaiting audio data for file: %s" % file.data.get("path"))
    while True:
        # Loop until audio data is ready.
        sleep(1)
        if file.data.get("ui", {}).get("audio_data", []):
            break
    log.debug("Audio data found for file: %s" % file.data.get("path"))

    # Get file query object again (since it's data might have changed)
    file = File.get(id=file_id)

    # Loop through each selected clip (which uses this file)
    for clip_id in clip_list:
        clip = Clip.get(id=clip_id)
        clip_reader = clip.data.get("reader")

        # Get File's audio data (since it has changed)
        file_audio_data = file.data.get("ui", {}).get("audio_data", [])
        if not file_audio_data:
            log.info("File has no audio, so we cannot find any waveform audio data")
            continue

        # If clip already has waveform, remove it to re-calculate.
        # (Used when volume changes the shape of the waveform)
        if bool(clip.data.get("ui",{}).get("audio_data",[])):
            log.debug("Removing pre-existing audio data")
            del(clip.data["ui"]["audio_data"])
            clip.save()

        # Method and variables for matching a time in seconds to an audio sample
        sample_count = len(file_audio_data)
        file_duration = file.data.get("duration")
        time_per_sample = file_duration / sample_count
        def sample_from_time(time):
            sample_num = max(0, round(time / time_per_sample))
            sample_num = min(sample_count - 1, sample_num)
            return file_audio_data[sample_num]

        # Loop through samples from the file, applying this clip's volume curve
        clip_audio_data = []
        clip_instance = get_app().window.timeline_sync.timeline.GetClip(clip.id)
        num_frames = int(clip_reader.get("video_length"))
        fps = get_app().project.get("fps")
        fps_frac = fps["num"] / fps["den"]
        for frame_num in range(1, num_frames):
            volume = clip_instance.volume.GetValue(frame_num)
            if clip_instance.time.GetCount() > 1:
                # Override frame # using time curve (if set)
                frame_num = clip_instance.time.GetValue(frame_num)
            time = frame_num / fps_frac
            clip_audio_data.append(sample_from_time(time) * volume)

        # Save this data to the clip object
        get_app().window.timeline.audioDataReady.emit(clip.id, {"ui": {"audio_data": clip_audio_data}})
