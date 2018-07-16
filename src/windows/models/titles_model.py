""" 
 @file
 @brief This file contains the titles model, used by the title editor window
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
import fnmatch

from PyQt5.QtCore import QMimeData, Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

try:
    import json
except ImportError:
    import simplejson as json


class TitleStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        files = []
        for item in indexes:
            selected_row = self.itemFromIndex(item).row()
            files.append(self.item(selected_row, 2).text())
        data.setText(json.dumps(files))
        data.setHtml("title")

        # Return Mimedata
        return data


class TitlesModel():
    def update_model(self, clear=True):
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

        # get a list of files in the OpenShot /transitions directory
        titles_dir = os.path.join(info.PATH, "titles")

        # Add build-in templates
        titles_list = []
        for filename in sorted(os.listdir(titles_dir)):
            titles_list.append(os.path.join(titles_dir, filename))

        # Add user-defined titles (if any)
        for file in sorted(os.listdir(info.TITLE_PATH)):
            # pretty up the filename for display purposes
            if fnmatch.fnmatch(file, '*.svg'):
                titles_list.append(os.path.join(info.TITLE_PATH, file))

        for path in sorted(titles_list):
            (parent_path, filename) = os.path.split(path)
            (fileBaseName, fileExtension) = os.path.splitext(filename)

            # Skip hidden files (such as .DS_Store, etc...)
            if filename[0] == "." or "thumbs.db" in filename.lower() or filename.lower() == "temp.svg":
                continue

            # split the name into parts (looking for a number)
            suffix_number = None
            name_parts = fileBaseName.split("_")
            if name_parts[-1].isdigit():
                suffix_number = name_parts[-1]

            # get name of transition
            title_name = fileBaseName.replace("_", " ").capitalize()

            # replace suffix number with placeholder (if any)
            if suffix_number:
                title_name = title_name.replace(suffix_number, "%s")
                title_name = self.app._tr(title_name) % suffix_number
            else:
                title_name = self.app._tr(title_name)

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
                    reader.GetFrame(0).Thumbnail(thumb_path, 98, 64, os.path.join(info.IMAGES_PATH, "mask.png"), "", "#000", True)
                    reader.Close()
                    clip.Close()

                except:
                    # Handle exception
                    msg = QMessageBox()
                    msg.setText(_("{} is not a valid image file.".format(filename)))
                    msg.exec_()
                    continue

            row = []

            # Append thumbnail
            col = QStandardItem()
            col.setIcon(QIcon(thumb_path))
            col.setText(title_name)
            col.setToolTip(title_name)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append Filename
            col = QStandardItem("Name")
            col.setData(title_name, Qt.DisplayRole)
            col.setText(title_name)
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

            # Process events in QT (to keep the interface responsive)
            app.processEvents()

    def __init__(self, *args):

        # Create standard model
        self.app = get_app()
        self.model = TitleStandardItemModel()
        self.model.setColumnCount(3)
        self.model_paths = {}
