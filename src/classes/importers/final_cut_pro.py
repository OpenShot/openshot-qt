"""
 @file
 @brief This file is used to import a Final Cut Pro XML file
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

import json
import os
from operator import itemgetter
from xml.dom import minidom

import openshot
from PyQt5.QtWidgets import QFileDialog

from classes import info
from classes.app import get_app
from classes.image_types import is_image
from classes.query import Clip, Track, File
from windows.views.find_file import find_missing_file


def import_xml():
    """Import final cut pro XML file"""
    app = get_app()
    _ = app._tr

    # Get FPS info
    fps_num = app.project.get("fps").get("num", 24)
    fps_den = app.project.get("fps").get("den", 1)
    fps_float = float(fps_num / fps_den)

    # Get XML path
    recommended_path = app.project.current_filepath or ""
    if not recommended_path:
        recommended_path = info.HOME_PATH
    else:
        recommended_path = os.path.dirname(recommended_path)
    file_path = QFileDialog.getOpenFileName(app.window, _("Import XML..."), recommended_path,
                                            _("Final Cut Pro (*.xml)"), _("Final Cut Pro (*.xml)"))[0]

    if not file_path or not os.path.exists(file_path):
        # User canceled dialog
        return

    # Parse XML file
    xmldoc = minidom.parse(file_path)

    # Get video tracks
    video_tracks = []
    for video_element in xmldoc.getElementsByTagName("video"):
        for video_track in video_element.getElementsByTagName("track"):
            video_tracks.append(video_track)
    audio_tracks = []
    for audio_element in xmldoc.getElementsByTagName("audio"):
        for audio_track in audio_element.getElementsByTagName("track"):
            audio_tracks.append(audio_track)

    # Loop through tracks
    track_index = 0
    for tracks in [audio_tracks, video_tracks]:
        for track_element in tracks:
            # Get clipitems on this track (if any)
            clips_on_track = track_element.getElementsByTagName("clipitem")
            if not clips_on_track:
                continue

            # Get # of tracks
            track_index += 1
            all_tracks = app.project.get("layers")
            track_number = list(reversed(sorted(all_tracks, key=itemgetter('number'))))[0].get("number") + 1000000

            # Create new track above existing layer(s)
            track = Track()
            is_locked = False
            if track_element.getElementsByTagName("locked")[0].childNodes[0].nodeValue == "TRUE":
                is_locked = True
            track.data = {"number": track_number, "y": 0, "label": "XML Import %s" % track_index, "lock": is_locked}
            track.save()

            # Loop through clips
            for clip_element in clips_on_track:
                # Get clip path
                xml_file_id = clip_element.getElementsByTagName("file")[0].getAttribute("id")
                clip_path = ""
                if clip_element.getElementsByTagName("pathurl"):
                    clip_path = clip_element.getElementsByTagName("pathurl")[0].childNodes[0].nodeValue
                else:
                    # Skip clipitem if no clippath node found
                    # This usually happens for linked audio clips (which OpenShot combines audio and thus ignores this)
                    continue

                clip_path, is_modified, is_skipped = find_missing_file(clip_path)
                if is_skipped:
                    continue

                # Check for this path in our existing project data
                file = File.get(path=clip_path)

                # Load filepath in libopenshot clip object (which will try multiple readers to open it)
                clip_obj = openshot.Clip(clip_path)

                if not file:
                    # Get the JSON for the clip's internal reader
                    try:
                        reader = clip_obj.Reader()
                        file_data = json.loads(reader.Json())

                        # Determine media type
                        if file_data["has_video"] and not is_image(file_data):
                            file_data["media_type"] = "video"
                        elif file_data["has_video"] and is_image(file_data):
                            file_data["media_type"] = "image"
                        elif file_data["has_audio"] and not file_data["has_video"]:
                            file_data["media_type"] = "audio"

                        # Save new file to the project data
                        file = File()
                        file.data = file_data

                        # Save file
                        file.save()
                    except Exception:
                        # Ignore errors for now
                        pass

                if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
                    # Determine thumb path
                    thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
                else:
                    # Audio file
                    thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

                # Create Clip object
                clip = Clip()
                clip.data = json.loads(clip_obj.Json())
                clip.data["file_id"] = file.id
                clip.data["title"] = clip_element.getElementsByTagName("name")[0].childNodes[0].nodeValue
                clip.data["layer"] = track.data.get("number", 1000000)
                clip.data["image"] = thumb_path
                clip.data["position"] = float(clip_element.getElementsByTagName("start")[0].childNodes[0].nodeValue) / fps_float
                clip.data["start"] = float(clip_element.getElementsByTagName("in")[0].childNodes[0].nodeValue) / fps_float
                clip.data["end"] = float(clip_element.getElementsByTagName("out")[0].childNodes[0].nodeValue) / fps_float

                # Loop through clip's effects
                for effect_element in clip_element.getElementsByTagName("effect"):
                    effectid = effect_element.getElementsByTagName("effectid")[0].childNodes[0].nodeValue
                    keyframes = effect_element.getElementsByTagName("keyframe")
                    if effectid == "opacity":
                        clip.data["alpha"] = {"Points": []}
                        for keyframe_element in keyframes:
                            keyframe_time = float(keyframe_element.getElementsByTagName("when")[0].childNodes[0].nodeValue)
                            keyframe_value = float(keyframe_element.getElementsByTagName("value")[0].childNodes[0].nodeValue) / 100.0
                            clip.data["alpha"]["Points"].append(
                                {
                                    "co": {
                                        "X": round(keyframe_time),
                                        "Y": keyframe_value
                                    },
                                    "interpolation": 1  # linear
                                }
                            )
                    elif effectid == "audiolevels":
                        clip.data["volume"] = {"Points": []}
                        for keyframe_element in keyframes:
                            keyframe_time = float(keyframe_element.getElementsByTagName("when")[0].childNodes[0].nodeValue)
                            keyframe_value = float(keyframe_element.getElementsByTagName("value")[0].childNodes[0].nodeValue) / 100.0
                            clip.data["volume"]["Points"].append(
                                {
                                    "co": {
                                        "X": round(keyframe_time),
                                        "Y": keyframe_value
                                    },
                                    "interpolation": 1  # linear
                                }
                            )

                # Save clip
                clip.save()

            # Update the preview and reselect current frame in properties
            app.window.refreshFrameSignal.emit()
            app.window.propertyTableView.select_frame(app.window.preview_thread.player.Position())
