"""
 @file
 @brief Shared metadata and cached artwork for bundled emojis
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

import os
import openshot
from classes import info


def builtin_emoji_reader_data(filepath):
    """Return reader metadata for a bundled 72x72 OpenMoji SVG."""
    emoji_root = os.path.realpath(
        os.path.join(info.PATH, "emojis", "color", "svg")
    )
    resolved_path = os.path.realpath(filepath)
    try:
        is_bundled = os.path.commonpath(
            (emoji_root, resolved_path)
        ) == emoji_root
    except ValueError:
        is_bundled = False
    if not is_bundled or not resolved_path.lower().endswith(".svg"):
        return None

    return {
        "acodec": "",
        "audio_bit_rate": 0,
        "audio_stream_index": -1,
        "audio_timebase": {"den": 1, "num": 1},
        "channel_layout": openshot.LAYOUT_MONO,
        "channels": 0,
        "display_ratio": {"den": 1, "num": 1},
        "duration": 3600.0,
        "file_size": os.path.getsize(resolved_path),
        "fps": {"den": 1, "num": 30},
        "has_audio": False,
        "has_single_image": True,
        "has_video": True,
        "height": 72,
        "interlaced_frame": False,
        "metadata": {},
        "path": resolved_path,
        "pixel_format": -1,
        "pixel_ratio": {"den": 1, "num": 1},
        "sample_rate": 0,
        "top_field_first": True,
        "type": "QtImageReader",
        "vcodec": "",
        "video_bit_rate": 0,
        "video_length": 108000,
        "video_stream_index": -1,
        "video_timebase": {"den": 30, "num": 1},
        "width": 72,
    }



def builtin_emoji_thumbnail(filepath):
    """Use existing browser artwork without starting a native thumbnail reader."""
    root = os.path.realpath(os.path.join(info.PATH, "emojis", "color", "svg"))
    path = os.path.realpath(filepath)
    try:
        if os.path.commonpath((root, path)) != root or not path.lower().endswith(".svg"):
            return None
    except ValueError:
        return None
    name = os.path.splitext(os.path.basename(path))[0] + ".png"
    for folder in (os.path.join(info.IMAGES_PATH, "cache"), info.CACHE_PATH):
        thumbnail = os.path.join(folder, name)
        if os.path.isfile(thumbnail):
            return thumbnail
    return None
