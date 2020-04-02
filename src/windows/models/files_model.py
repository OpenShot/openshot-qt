"""
 @file
 @brief This file contains the project file model, used by the project tree
 @author Noah Figg <eggmunkee@hotmail.com>
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

from PyQt5.QtCore import QMimeData, Qt, pyqtSignal, QSortFilterProxyModel, QEventLoop
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import updates
from classes import info
from classes.query import File
from classes.logger import log
from classes.app import get_app
from requests import get

import json

class FileStandardItemModel(QStandardItemModel):
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
            files.append(self.item(selected_row, 5).text())
        data.setText(json.dumps(files))
        data.setHtml("clip")

        # Return Mimedata
        return data


class FileFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter for text"""

        if get_app().window.actionFilesShowVideo.isChecked() \
                or get_app().window.actionFilesShowAudio.isChecked() \
                or get_app().window.actionFilesShowImage.isChecked() \
                or get_app().window.filesFilter.text():
            # Fetch the file name
            index = self.sourceModel().index(sourceRow, 0, sourceParent)
            file_name = self.sourceModel().data(index) # file name (i.e. MyVideo.mp4)

            # Fetch the media_type
            index = self.sourceModel().index(sourceRow, 3, sourceParent)
            media_type = self.sourceModel().data(index) # media type (i.e. video, image, audio)

            index = self.sourceModel().index(sourceRow, 2, sourceParent)
            tags = self.sourceModel().data(index) # tags (i.e. intro, custom, etc...)

            if get_app().window.actionFilesShowVideo.isChecked():
                if not media_type == "video":
                    return False
            elif get_app().window.actionFilesShowAudio.isChecked():
                if not media_type == "audio":
                    return False
            elif get_app().window.actionFilesShowImage.isChecked():
                if not media_type == "image":
                    return False

            # Match against regex pattern
            return self.filterRegExp().indexIn(file_name) >= 0 or self.filterRegExp().indexIn(tags) >= 0

        # Continue running built-in parent filter logic
        return super(FileFilterProxyModel, self).filterAcceptsRow(sourceRow, sourceParent)


class FilesModel(updates.UpdateInterface):
    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):

        # Something was changed in the 'files' list
        if (len(action.key) >= 1 and action.key[0].lower() == "files") or action.type == "load":
            # Refresh project files model
            if action.type == "insert":
                # Don't clear the existing items if only inserting new things
                self.update_model(clear=False)
            elif action.type == "delete" and action.key[0].lower() == "files":
                # Don't clear the existing items if only deleting things
                self.update_model(clear=False, delete_file_id=action.key[1].get('id', ''))
            else:
                # Clear existing items
                self.update_model(clear=True)

    def update_model(self, clear=True, delete_file_id=None):
        log.info("updating files model.")
        app = get_app()

        # Get window to check filters
        win = app.window
        _ = app._tr

        # Delete a file (if delete_file_id passed in)
        if delete_file_id in self.model_ids:
            for row_num in range(self.model.rowCount()):
                id_index = self.model.index(row_num, 5)
                if delete_file_id == self.model.data(id_index):
                    # Delete row from model
                    self.model.beginRemoveRows(id_index.parent(), row_num, row_num)
                    self.model.removeRow(row_num, id_index.parent())
                    self.model.endRemoveRows()
                    self.model.submit()
                    self.model_ids.pop(delete_file_id)
                    break

        # Skip updates (if needed)
        if self.ignore_update_signal:
            return

        # Clear all items
        if clear:
            self.model_ids = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels(["", _("Name"), _("Tags"), "", "", ""])

        # Get list of files in project
        files = File.filter()  # get all files

        # add item for each file
        for file in files:
            if file.data["id"] in self.model_ids:
                # Ignore files that already exist in model
                continue

            path, filename = os.path.split(file.data["path"])
            tags = ""
            if "tags" in file.data.keys():
                tags = file.data["tags"]
            name = filename
            if "name" in file.data.keys():
                name = file.data["name"]

            # Generate thumbnail for file (if needed)
            if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
                # Check for start and end attributes (optional)
                thumbnail_frame = 1
                if 'start' in file.data.keys():
                    fps = file.data["fps"]
                    fps_float = float(fps["num"]) / float(fps["den"])
                    thumbnail_frame = round(float(file.data['start']) * fps_float) + 1

                # Determine thumb path (default value... a guess)
                thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s-%s.png" % (file.id, thumbnail_frame))

                # Connect to thumbnail server and get image
                thumb_server_details = get_app().window.http_server_thread.server_address
                thumb_address = "http://%s:%s/thumbnails/%s/%s/path/" % (thumb_server_details[0], thumb_server_details[1], file.id, thumbnail_frame)
                r = get(thumb_address)
                if r.ok:
                    # Update thumbnail path to real one
                    thumb_path = r.text
            else:
                # Audio file
                thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

            row = []

            # Append thumbnail
            col = QStandardItem()
            col.setIcon(QIcon(thumb_path))
            col.setText(name)
            col.setToolTip(filename)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append Filename
            col = QStandardItem("Name")
            col.setData(filename, Qt.DisplayRole)
            col.setText(name)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable)
            row.append(col)

            # Append Tags
            col = QStandardItem("Tags")
            col.setData(tags, Qt.DisplayRole)
            col.setText(tags)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable)
            row.append(col)

            # Append Media Type
            col = QStandardItem("Type")
            col.setData(file.data["media_type"], Qt.DisplayRole)
            col.setText(file.data["media_type"])
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable)
            row.append(col)

            # Append Path
            col = QStandardItem("Path")
            col.setData(path, Qt.DisplayRole)
            col.setText(path)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append ID
            col = QStandardItem("ID")
            col.setData(file.data["id"], Qt.DisplayRole)
            col.setText(file.data["id"])
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append ROW to MODEL (if does not already exist in model)
            if not file.data["id"] in self.model_ids:
                self.model.appendRow(row)
                self.model_ids[file.data["id"]] = file.data["id"]
                get_app().processEvents(QEventLoop.ExcludeUserInputEvents)

            # Refresh view and filters (to hide or show this new item)
            get_app().window.resize_contents()

        # Emit signal
        self.model.ModelRefreshed.emit()

    def __init__(self, *args):

        # Add self as listener to project data updates (undo/redo, as well as normal actions handled within this class all update the tree model)
        app = get_app()
        app.updates.add_listener(self)

        # Create standard model
        self.model = FileStandardItemModel()
        self.model.setColumnCount(6)
        self.model_ids = {}
        self.ignore_update_signal = False
