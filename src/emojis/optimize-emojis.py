"""
 @file optimize-emojis.py
 @brief Remove unused emojis from the emojis/color/svg folder, and optimize data JSON file
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

from classes import info
import os
import json

REMOVE_GROUPS = ['flags', 'extras-unicode', 'component', 'people-body']
REMOVE_SUBGROUPS = ['alphanum', 'keycap', 'transport-sign', 'religion,', 'animals-nature', 'climate-environment',
                    'emergency', 'flags', 'food-drink', 'gardening', 'healthcare', 'objects', 'people',
                    'smileys-emotion', 'symbol-other', 'symbols', 'technology', 'travel-places']


# Get emoji metadata
emoji_metadata_path = os.path.join(info.PATH, "emojis", "data", "openmoji.json")
with open(emoji_metadata_path, 'r', encoding="utf-8") as f:
    emoji_metadata = json.load(f)

# Parse emoji metadata, and reshape data
emoji_lookup = {}
for emoji in emoji_metadata:
    if emoji.get('group') not in REMOVE_GROUPS and emoji.get('subgroups') not in REMOVE_SUBGROUPS:
        emoji_lookup[emoji.get("hexcode")] = emoji

# Loop through files and remove unused emojis
emoji_removed_count = 0
emoji_file_path = os.path.join(info.PATH, "emojis", "color", "svg")
for filename in os.listdir(emoji_file_path):
    fileBaseName = os.path.splitext(filename)[0]
    emoji = emoji_lookup.get(fileBaseName, {})
    if not emoji:
        # Remove unused emoji
        emoji_path = os.path.join(emoji_file_path, filename)
        os.unlink(emoji_path)
        emoji_removed_count += 1
        print('Removed emoji: %s' % emoji_path)

# Save optimized data file
emoji_metadata_optimized_path = os.path.join(info.PATH, "emojis", "data", "openmoji-optimized.json")
with open(emoji_metadata_optimized_path, 'w', encoding='utf-8') as file:
    file.write(json.dumps(emoji_lookup))

print('Emojis Optimized (%s removed)!' % emoji_removed_count)
