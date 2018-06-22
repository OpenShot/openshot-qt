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

import platform
import threading
from copy import deepcopy
from classes import info
from classes.app import get_app
from classes.logger import log
from classes import settings
import openshot


# Get settings
s = settings.get_settings()


def get_audio_data(clip_id, file_path, channel_filter, volume_keyframe):
    """Get a Clip object form libopenshot, and grab audio data"""
    clip = openshot.Clip(file_path)
    clip.Open()

    # Disable video stream (for speed improvement)
    clip.Reader().info.has_video = False

    log.info("Clip loaded, start thread")
    t = threading.Thread(target=get_waveform_thread, args=[clip, clip_id, file_path, channel_filter, volume_keyframe])
    t.start()

def get_waveform_thread(clip, clip_id, file_path, channel_filter=-1, volume_keyframe=None):
    """Get the audio data from a clip in a separate thread"""
    audio_data = []
    sample_rate = clip.Reader().info.sample_rate

    # How many samples per second do we need (to approximate the waveform)
    samples_per_second = 20
    sample_divisor = round(sample_rate / samples_per_second)
    log.info("Getting waveform for sample rate: %s" % sample_rate)

    sample = 0
    for frame_number in range(1, clip.Reader().info.video_length):
        # Get frame object
        frame = clip.Reader().GetFrame(frame_number)

        # Get volume for this frame
        volume = 1.0
        if volume_keyframe:
            volume = volume_keyframe.GetValue(frame_number)

        # Loop through samples in frame (hopping through it to get X # of data points per second)
        while True:
            # Determine amount of range
            magnitude_range = sample_divisor
            if sample + magnitude_range > frame.GetAudioSamplesCount():
                magnitude_range = frame.GetAudioSamplesCount() - sample

            # Get audio data for this channel
            if sample < frame.GetAudioSamplesCount():
                audio_data.append(frame.GetAudioSample(channel_filter, sample, magnitude_range) * volume)
            else:
                # Adjust starting sample for next frame
                sample = max(0, sample - frame.GetAudioSamplesCount())
                break # We are done with this frame

            # Jump to next sample needed
            sample += sample_divisor

    # Close reader
    clip.Close()

    # Emit signal when done
    log.info("get_waveform_thread completed")
    get_app().window.WaveformReady.emit(clip_id, audio_data)
