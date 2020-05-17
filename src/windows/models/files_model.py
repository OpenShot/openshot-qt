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
import json
import re
import glob

from PyQt5.QtCore import (
    QMimeData, Qt, pyqtSignal, QEventLoop, QObject,
    QSortFilterProxyModel, QItemSelectionModel, QPersistentModelIndex,
)
from PyQt5.QtGui import (
    QIcon, QStandardItem, QStandardItemModel
)
from classes import updates
from classes import info
from classes.image_types import is_image
from classes.query import File
from classes.logger import log
from classes.app import get_app
from requests import get

import openshot


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
            file_name = self.sourceModel().data(index)  # file name (i.e. MyVideo.mp4)

            # Fetch the media_type
            index = self.sourceModel().index(sourceRow, 3, sourceParent)
            media_type = self.sourceModel().data(index)  # media type (i.e. video, image, audio)

            index = self.sourceModel().index(sourceRow, 2, sourceParent)
            tags = self.sourceModel().data(index)  # tags (i.e. intro, custom, etc...)

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
        return super().filterAcceptsRow(sourceRow, sourceParent)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        ids = self.parent.selected_file_ids()
        data.setText(json.dumps(ids))
        data.setHtml("clip")

        # Return Mimedata
        return data

    def __init__(self, **kwargs):
        if "parent" in kwargs:
            self.parent = kwargs["parent"]
            kwargs.pop("parent")

        # Call base class implementation
        super().__init__(**kwargs)


class FilesModel(QObject, updates.UpdateInterface):
    ModelRefreshed = pyqtSignal()

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
            elif action.type == "update" and action.key[0].lower() == "files":
                # Do nothing for file updates
                pass
            else:
                # Clear existing items
                self.update_model(clear=True)

    def update_model(self, clear=True, delete_file_id=None):
        log.info("updating files model.")
        app = get_app()

        self.ignore_updates = True

        # Translations
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

        # Clear all items
        if clear:
            self.model_ids = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels(["", _("Name"), _("Tags"), "", "", ""])

        # Get list of files in project
        files = File.filter()  # get all files

        # add item for each file
        row_added_count = 0
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

                # Get thumb path
                thumb_path = self.get_thumb_path(file.id, thumbnail_frame)
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

                row_added_count += 1
                if row_added_count % 2 == 0:
                    # Update every X items
                    get_app().processEvents(QEventLoop.ExcludeUserInputEvents)

            # Refresh view and filters (to hide or show this new item)
            get_app().window.resize_contents()

        self.ignore_updates = False

        # Emit signal when model is updated
        self.ModelRefreshed.emit()

    def get_thumb_path(self, file_id, thumbnail_frame, clear_cache=False):
        """Get thumbnail path by invoking HTTP thumbnail request"""

        # Clear thumb cache (if requested)
        thumb_cache = ""
        if clear_cache:
            thumb_cache = "no-cache/"

        # Connect to thumbnail server and get image
        thumb_server_details = get_app().window.http_server_thread.server_address
        thumb_address = "http://%s:%s/thumbnails/%s/%s/path/%s" % (
        thumb_server_details[0], thumb_server_details[1], file_id, thumbnail_frame, thumb_cache)
        r = get(thumb_address)
        if r.ok:
            # Update thumbnail path to real one
            return r.text
        else:
            return ''

    def update_file_thumbnail(self, file_id):
        """Update/re-generate the thumbnail of a specific file"""
        file = File.get(id=file_id)
        path, filename = os.path.split(file.data["path"])
        name = filename
        if "name" in file.data.keys():
            name = file.data["name"]

        # Refresh thumbnail for updated file
        self.ignore_updates = True
        if file_id in self.model_ids:
            for row_num in range(self.model.rowCount()):
                id_index = self.model.index(row_num, 5)
                if file_id == self.model.data(id_index):
                    # Update thumb for file
                    thumb_index = self.model.index(row_num, 0)
                    thumb_path = self.get_thumb_path(file_id, 1, clear_cache=True)
                    item = self.model.itemFromIndex(thumb_index)
                    item.setIcon(QIcon(thumb_path))
                    item.setText(name)
            # Emit signal when model is updated
            self.ModelRefreshed.emit()

        self.ignore_updates = False

    def selected_file_ids(self):
        """ Get a list of file IDs for all selected files """
        # Get the indexes for column 5 of all selected rows
        selected = self.selection_model.selectedRows(5)

        return [idx.data() for idx in selected]

    def selected_files(self):
        """ Get a list of File objects representing the current selection """
        files = []
        for id in self.selected_file_ids():
            files.append(File.get(id=id))
        return files

    def current_file_id(self):
        """ Get the file ID of the current files-view item, or the first selection """
        cur = self.selection_model.currentIndex()

        if not cur or not cur.isValid() and self.selection_model.hasSelection():
            cur = self.selection_model.selectedIndexes()[0]

        if cur and cur.isValid():
            return cur.sibling(cur.row(), 5).data()

    def current_file(self):
        """ Get the File object for the current files-view item, or the first selection """
        cur_id = self.current_file_id()
        if cur_id:
            return File.get(id=cur_id)

    def __init__(self, *args):

        # Add self as listener to project data updates
        # (undo/redo, as well as normal actions handled within this class all update the model)
        app = get_app()
        app.updates.add_listener(self)

        # Create standard model
        self.model = QStandardItemModel()
        self.model.setColumnCount(6)
        self.model_ids = {}
        self.ignore_updates = False

        self.ignore_image_sequence_paths = []

        # Create proxy model (for sorting and filtering)
        self.proxy_model = FileFilterProxyModel(parent=self)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)

        # Create selection model to share between views
        self.selection_model = QItemSelectionModel(self.proxy_model)

        # Connect signal
        app.window.FileUpdated.connect(self.update_file_thumbnail)

        # Call init for superclass QObject
        super(QObject, FilesModel).__init__(self, *args)
