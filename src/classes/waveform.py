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


# Get settings
s = get_app().get_settings()


def get_audio_data(files: dict):
    """Get a Clip object form libopenshot, and grab audio data"""
    """
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
    For the given file, update audio data.

    arg1: file id to get the audio data of.
    arg2: list of clips to update when the audio data is ready.
    """

    file = File.get(id=file_id)

    file_audio_data = file.data.get("ui", {}).get("audio_data", False)
    if not file_audio_data:
        file.getAudioData()
    elif file_audio_data == [-999]:
        count = 0
        while True:
            # Loop until audio data is ready.
            sleep(1)
            if file.data.get("ui").get("audio_data", False) != [-999]:
                break
            count += 1
            if count >= 15:
                # After 15 seconds. Abandon
                log.error("Could not gather audio data")
                return

    # Update clips
    for clip_id in clip_list:
        # Show Audio
        clip = Clip.get(id=clip_id)
        clip.showAudioData()
