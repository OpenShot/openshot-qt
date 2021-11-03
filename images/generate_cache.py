"""
 @file
 @brief This file generates the image cache for openshot-qt, essentially creating multiple
 resolution versions of each image used in the UI, for faster loading and high DPI support.
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
from classes import info
from classes.logger import log
import openshot
from PyQt5.QtWidgets import QApplication

# Try to get the security-patched XML functions from defusedxml
try:
    from defusedxml import minidom as xml
except ImportError:
    from xml.dom import minidom as xml


# Create Qt application (required for SVG font rendering)
svg_app = QApplication([])
icon_size = info.LIST_ICON_SIZE
emoji_size = info.EMOJI_ICON_SIZE


def create_cache_thumbnail(path, width, height, thumb_path):
    """Create a thumbnail image of a specific image file at a specific size"""
    display_scales = [1, 2]
    mask_path = os.path.join(info.IMAGES_PATH, "mask.png")

    for scale in display_scales:
        try:
            # Reload this reader
            clip = openshot.Clip(path)
            reader = clip.Reader()

            # Open reader
            reader.Open()

            scale_thumb_path = thumb_path
            scale_width = width
            scale_height = height
            if scale > 1:
                # Create @2x version of cache image
                clip.scale_x.AddPoint(1.0, 1.0 * scale)
                clip.scale_y.AddPoint(1.0, 1.0 * scale)
                scale_width *= scale
                scale_height *= scale
                suffix = "@%dx" % scale
                thumb_path_base, thumb_path_ext = os.path.splitext(thumb_path)
                scale_thumb_path = "%s%s%s" % (thumb_path_base, suffix, thumb_path_ext)

            # Save thumbnail
            reader.GetFrame(0).Thumbnail(scale_thumb_path, scale_width, scale_height,
                                         mask_path, "", "#000", True, "png", 85)
            reader.Close()
            clip.Close()

        except Exception:
            # Handle exception
            log.debug('Invalid cache image file %s', path, exc_info=1)


#################################################
# TITLES UI CACHE - Create small images for UI
# get a list of files in the OpenShot package directory
titles_dir = os.path.join(info.PATH, "titles")
titles_list = [
    os.path.join(titles_dir, filename)
    for filename in sorted(os.listdir(titles_dir))
    ]

for icon_path in sorted(titles_list):
    filename = os.path.basename(icon_path)
    fileBaseName = os.path.splitext(filename)[0]

    # Check for thumbnail path (in build-in cache)
    thumb_path = os.path.join(info.IMAGES_PATH, "cache", "{}.png".format(fileBaseName))
    create_cache_thumbnail(icon_path, icon_size.width(), icon_size.height(), thumb_path)


#################################################
# EMOJIS UI CACHE - Create small images for UI
# get a list of files in the OpenShot /emojis directory
emojis_dir = os.path.join(info.PATH, "emojis", "color", "svg")
emoji_paths = [(emojis_dir, os.listdir(emojis_dir)), ]

for dir_name, files in emoji_paths:
    for filename in sorted(files):
        icon_path = os.path.join(dir_name, filename)
        fileBaseName = os.path.splitext(filename)[0]

        # Check for thumbnail path (in build-in cache)
        thumb_path = os.path.join(info.IMAGES_PATH, "cache",  "{}.png".format(fileBaseName))
        create_cache_thumbnail(icon_path, emoji_size.width(), emoji_size.height(), thumb_path)


#################################################
# EFFECTS UI CACHE - Create small images for UI
# Get the folder path of effects
effects_dir = os.path.join(info.PATH, "effects")
icons_dir = os.path.join(effects_dir, "icons")

# Get a JSON list of all supported effects in libopenshot
raw_effects_list = json.loads(openshot.EffectInfo.Json())

# Loop through each effect
for effect_info in raw_effects_list:
    # Get basic properties about each effect
    effect_name = effect_info["class_name"]
    # Remove any spaces from icon name
    icon_name = "%s.png" % effect_name.lower().replace(' ', '')
    icon_path = os.path.join(icons_dir, icon_name)

    # Create thumbnail in cache
    thumb_path = os.path.join(info.IMAGES_PATH, "cache", icon_name)
    create_cache_thumbnail(icon_path, icon_size.width(), icon_size.height(), thumb_path)


#################################################
# BLENDER UI CACHE - Create small images for UI
blender_dir = os.path.join(info.PATH, "blender")
icons_dir = os.path.join(blender_dir, "icons")

for file in sorted(os.listdir(blender_dir)):
    path = os.path.join(blender_dir, file)
    if os.path.isfile(path) and ".xml" in file:
        # load xml effect file
        xmldoc = xml.parse(path)
        icon_name = xmldoc.getElementsByTagName("icon")[0].childNodes[0].data
        icon_path = os.path.join(icons_dir, icon_name)

        # Create thumbnail in cache
        thumb_path = os.path.join(info.IMAGES_PATH, "cache",  "blender_{}".format(icon_name))
        create_cache_thumbnail(icon_path, icon_size.width(), icon_size.height(), thumb_path)


#################################################
# TRANSITION UI CACHE - Create small images for UI
transitions_dir = os.path.join(info.PATH, "transitions")
common_dir = os.path.join(transitions_dir, "common")
extra_dir = os.path.join(transitions_dir, "extra")
transition_groups = [
    ("common", common_dir, os.listdir(common_dir)),
    ("extra", extra_dir, os.listdir(extra_dir)),
]
# Loop through transitions
for type, dir, files in transition_groups:
    for filename in sorted(files):
        icon_path = os.path.join(dir, filename)
        fileBaseName = os.path.splitext(filename)[0]

        # Skip hidden files (such as .DS_Store, etc...)
        if filename[0] == "." or "thumbs.db" in filename.lower():
            continue

        # Create thumbnail in cache
        thumb_path = os.path.join(info.IMAGES_PATH, "cache", "{}.png".format(fileBaseName))
        create_cache_thumbnail(icon_path, icon_size.width(), icon_size.height(), thumb_path)
