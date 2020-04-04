"""
 @file
 @brief This file contains the transitions model, used by the main window
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

from PyQt5.QtCore import QMimeData, Qt, QSortFilterProxyModel, pyqtSignal
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

import json

class TransitionStandardItemModel(QStandardItemModel):
    ModelRefreshed = pyqtSignal()

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
        data.setHtml("transition")

        # Return Mimedata
        return data


class TransitionFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter for common transitions and text filter"""

        if get_app().window.actionTransitionsShowCommon.isChecked():
            # Fetch the group name
            index = self.sourceModel().index(sourceRow, 2, sourceParent) # group name column
            group_name = self.sourceModel().data(index) # group name (i.e. common)

            # Fetch the transitions name
            index = self.sourceModel().index(sourceRow, 0, sourceParent) # transition name column
            trans_name = self.sourceModel().data(index) # transition name (i.e. Fade In)

            # Return, if regExp match in displayed format.
            return "common" == group_name and self.filterRegExp().indexIn(trans_name) >= 0

        # Continue running built-in parent filter logic
        return super(TransitionFilterProxyModel, self).filterAcceptsRow(sourceRow, sourceParent)

    def lessThan(self, left, right):
        """Sort with both group name and transition name"""
        leftData = self.sourceModel().data(left)
        leftGroup = self.sourceModel().data(left, 257) # Strange way to access 'type' column in model
        rightData = self.sourceModel().data(right)
        rightGroup = self.sourceModel().data(right, 257)

        return leftGroup < rightGroup and leftData < rightData


class TransitionsModel():
    def update_model(self, clear=True):
        log.info("updating transitions model.")
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
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")
        transition_groups = [{"type": "common", "dir": common_dir, "files": os.listdir(common_dir)},
                             {"type": "extra", "dir": extra_dir, "files": os.listdir(extra_dir)}]

        # Add optional user-defined transitions folder
        if (os.path.exists(info.TRANSITIONS_PATH) and os.listdir(info.TRANSITIONS_PATH)):
            transition_groups.append({"type": "user", "dir": info.TRANSITIONS_PATH, "files": os.listdir(info.TRANSITIONS_PATH)})

        for group in transition_groups:
            type = group["type"]
            dir = group["dir"]
            files = group["files"]

            for filename in sorted(files):
                path = os.path.join(dir, filename)
                fileBaseName = os.path.splitext(filename)[0]

                # Skip hidden files (such as .DS_Store, etc...)
                if filename[0] == "." or "thumbs.db" in filename.lower():
                    continue

                # split the name into parts (looking for a number)
                suffix_number = None
                name_parts = fileBaseName.split("_")
                if name_parts[-1].isdigit():
                    suffix_number = name_parts[-1]

                # get name of transition
                trans_name = fileBaseName.replace("_", " ").capitalize()

                # replace suffix number with placeholder (if any)
                if suffix_number:
                    trans_name = trans_name.replace(suffix_number, "%s")
                    trans_name = self.app._tr(trans_name) % suffix_number
                else:
                    trans_name = self.app._tr(trans_name)

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
                        reader.GetFrame(0).Thumbnail(thumb_path, 98, 64, os.path.join(info.IMAGES_PATH, "mask.png"),
                                                     "", "#000", True, "png", 85)
                        reader.Close()
                        clip.Close()

                    except:
                        # Handle exception
                        log.info('Invalid transition image file: %s' % filename)
                        msg = QMessageBox()
                        msg.setText(_("{} is not a valid image file.".format(filename)))
                        msg.exec_()
                        continue

                row = []

                # Append thumbnail
                col = QStandardItem()
                col.setIcon(QIcon(thumb_path))
                col.setText(trans_name)
                col.setToolTip(trans_name)
                col.setData(type)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append Filename
                col = QStandardItem("Name")
                col.setData(trans_name, Qt.DisplayRole)
                col.setText(trans_name)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                row.append(col)

                # Append Media Type
                col = QStandardItem("Type")
                col.setData(type, Qt.DisplayRole)
                col.setText(type)
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

        # Emit signal when model is updated
        self.model.ModelRefreshed.emit()

    def __init__(self, *args):

        # Create standard model
        self.app = get_app()
        self.model = TransitionStandardItemModel()
        self.model.setColumnCount(4)
        self.model_paths = {}

        # Create proxy model (for sorting and filtering)
        self.proxy_model = TransitionFilterProxyModel()
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)
