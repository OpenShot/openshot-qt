"""
 @file
 @brief This file contains the emoji model, used by the main window
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

import os

from PyQt5.QtCore import QMimeData, Qt, QSortFilterProxyModel
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

import json


class EmojiStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        files = []
        for item in indexes:
            selected_row = self.itemFromIndex(item).row()
            files.append(self.item(selected_row, 3).text())
        data.setText(json.dumps(files))
        data.setHtml("clip")

        # Return Mimedata
        return data


class EmojiFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter for emoji groups and text filter"""

        if get_app().window.emojiFilterGroup.currentData() and \
                get_app().window.emojiFilterGroup.currentData() != "Show All":
            # Fetch the group name
            index = self.sourceModel().index(sourceRow, 2, sourceParent) # group name column
            group_name = self.sourceModel().data(index) # group name (i.e. common)

            # Fetch the emoji name
            index = self.sourceModel().index(sourceRow, 0, sourceParent) # transition name column
            emoji_name = self.sourceModel().data(index) # emoji name (i.e. Smiley Face)

            # Return, if regExp match in displayed format.
            return get_app().window.emojiFilterGroup.currentData() == group_name and \
                   self.filterRegExp().indexIn(emoji_name) >= 0

        # Continue running built-in parent filter logic
        return super(EmojiFilterProxyModel, self).filterAcceptsRow(sourceRow, sourceParent)


class EmojisModel():
    def update_model(self, clear=True):
        log.info("updating emoji model.")
        app = get_app()

        # Get window to check filters
        win = app.window
        _ = app._tr

        # Clear all items
        if clear:
            self.model_paths = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Thumb"), _("Name")])

        # Get emoji metadata
        emoji_metadata_path = os.path.join(info.PATH, "emojis", "data", "openmoji.json")
        with open(emoji_metadata_path, 'r', encoding="utf-8") as f:
            emoji_metadata = json.load(f)

        # Parse emoji metadata, and reshape data
        emoji_lookup = {}
        for emoji in emoji_metadata:
            emoji_lookup[emoji.get("hexcode")] = emoji

        # get a list of files in the OpenShot /emojis directory
        emojis_dir = os.path.join(info.PATH, "emojis", "color", "svg")
        emoji_paths = [{"type": "common", "dir": emojis_dir, "files": os.listdir(emojis_dir)}, ]
        emoji_groups = {}

        # Add optional user-defined transitions folder
        if os.path.exists(info.EMOJIS_PATH) and os.listdir(info.EMOJIS_PATH):
            emoji_paths.append({"type": "user", "dir": info.EMOJIS_PATH, "files": os.listdir(info.EMOJIS_PATH)})

        for group in emoji_paths:
            type = group["type"]
            dir = group["dir"]
            files = group["files"]

            for filename in sorted(files):
                path = os.path.join(dir, filename)
                fileBaseName = os.path.splitext(filename)[0]

                # Skip hidden files (such as .DS_Store, etc...)
                if filename[0] == "." or "thumbs.db" in filename.lower():
                    continue

                # get name of transition
                emoji = emoji_lookup.get(fileBaseName, {})
                emoji_name = _(emoji.get("annotation", fileBaseName).capitalize())
                emoji_type = emoji.get("group", "user")

                # Track unique emoji groups
                if emoji_type not in emoji_groups.keys():
                    emoji_groups[emoji_type] = emoji_type

                # Check for thumbnail path (in build-in cache)
                thumb_path = os.path.join(info.IMAGES_PATH, "cache",  "{}.png".format(fileBaseName))

                # Check built-in cache (if not found)
                if not os.path.exists(thumb_path):
                    # Check user folder cache
                    thumb_path = os.path.join(info.CACHE_PATH, "{}.png".format(fileBaseName))

                # Generate thumbnail (if needed)
                if not os.path.exists(thumb_path):

                    try:
                        # Reload this reader
                        clip = openshot.Clip(path)
                        reader = clip.Reader()

                        # Open reader
                        reader.Open()

                        # Save thumbnail
                        reader.GetFrame(0).Thumbnail(thumb_path, 75, 75, os.path.join(info.IMAGES_PATH, "mask.png"),
                                                     "", "#000", True, "png", 85)
                        reader.Close()
                        clip.Close()

                    except:
                        # Handle exception
                        log.info('Invalid emoji image file: %s' % filename)
                        msg = QMessageBox()
                        msg.setText(_("{} is not a valid image file.".format(filename)))
                        msg.exec_()
                        continue

                row = []

                # Append thumbnail
                col = QStandardItem()
                col.setIcon(QIcon(thumb_path))
                col.setText(emoji_name)
                col.setToolTip(emoji_name)
                col.setData(emoji_type)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append Filename
                col = QStandardItem("Name")
                col.setData(emoji_name, Qt.DisplayRole)
                col.setText(emoji_name)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append Media Type
                col = QStandardItem("Type")
                col.setData(type, Qt.DisplayRole)
                col.setText(emoji_type)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append Path
                col = QStandardItem("Path")
                col.setData(path, Qt.DisplayRole)
                col.setText(path)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append ROW to MODEL (if does not already exist in model)
                if not path in self.model_paths:
                    self.model.appendRow(row)
                    self.model_paths[path] = path

        # Loop through emoji groups, and populate emoji filter drop-down
        get_app().window.emojiFilterGroup.clear()
        get_app().window.emojiFilterGroup.addItem(_("Show All"), "Show All")
        for emoji_type in sorted(emoji_groups.keys()):
            get_app().window.emojiFilterGroup.addItem(_(emoji_type.capitalize()), emoji_type)

    def __init__(self, *args):

        # Create standard model
        self.app = get_app()
        self.model = EmojiStandardItemModel()
        self.model.setColumnCount(4)
        self.model_paths = {}

        # Create proxy model (for sorting and filtering)
        self.proxy_model = EmojiFilterProxyModel()
        self.proxy_model.setDynamicSortFilter(False)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)
