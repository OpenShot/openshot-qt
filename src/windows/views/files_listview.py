"""
 @file
 @brief This file contains the project file listview, used by the main window
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

import glob
import os
import re

import openshot  # Python module for libopenshot (required video editing module installed separately)
from PyQt5.QtCore import QSize, Qt, QPoint, QRegExp
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QListView, QMessageBox, QAbstractItemView, QMenu

from classes.app import get_app
from classes.image_types import is_image
from classes.logger import log
from classes.query import File
from windows.models.files_model import FilesModel, FileFilterProxyModel

import json

class FilesListView(QListView):
    """ A ListView QWidget used on the main window """
    drag_item_size = 48

    def contextMenuEvent(self, event):

        # Set context menu mode
        app = get_app()
        app.context_menu_object = "files"

        index = self.indexAt(event.pos())

        # Build menu
        menu = QMenu(self)

        menu.addAction(self.win.actionImportFiles)
        menu.addAction(self.win.actionDetailsView)

        if index.isValid():
            # Look up the model item and our unique ID
            model = self.model()

            # Look up file_id from 5th column of row
            id_index = index.sibling(index.row(), 5)
            file_id = model.data(id_index, Qt.DisplayRole)

            # If a valid file selected, show file related options
            menu.addSeparator()

            # Add edit title option (if svg file)
            file = File.get(id=file_id)
            if file and file.data.get("path").endswith(".svg"):
                menu.addAction(self.win.actionEditTitle)
                menu.addAction(self.win.actionDuplicateTitle)
                menu.addSeparator()

            menu.addAction(self.win.actionPreview_File)
            menu.addAction(self.win.actionSplitClip)
            menu.addAction(self.win.actionAdd_to_Timeline)
            menu.addAction(self.win.actionFile_Properties)
            menu.addSeparator()
            menu.addAction(self.win.actionRemove_from_Project)
            menu.addSeparator()

        # Show menu
        menu.exec_(event.globalPos())

    def dragEnterEvent(self, event):
        # If dragging urls onto widget, accept
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()

    def startDrag(self, supportedActions):
        """ Override startDrag method to display custom icon """

        # The relevant model for index values
        model = self.model()

        # Get image of selected item
        selected_rows = self.selectionModel().selectedRows(0)
        icon = selected_rows[0].data(Qt.DecorationRole)

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(model.mimeData(self.selectionModel().selectedIndexes()))
        drag.setPixmap(icon.pixmap(QSize(self.drag_item_size, self.drag_item_size)))
        drag.setHotSpot(QPoint(self.drag_item_size / 2, self.drag_item_size / 2))
        drag.exec_()

    # Without defining this method, the 'copy' action doesn't show with cursor
    def dragMoveEvent(self, event):
        pass

    def add_file(self, filepath):
        filename = os.path.basename(filepath)

        # Add file into project
        app = get_app()
        _ = get_app()._tr

        # Check for this path in our existing project data
        file = File.get(path=filepath)

        # If this file is already found, exit
        if file:
            return

        # Load filepath in libopenshot clip object (which will try multiple readers to open it)
        clip = openshot.Clip(filepath)

        # Get the JSON for the clip's internal reader
        try:
            reader = clip.Reader()
            file_data = json.loads(reader.Json())

            # Determine media type
            if file_data["has_video"] and not is_image(file_data):
                file_data["media_type"] = "video"
            elif file_data["has_video"] and is_image(file_data):
                file_data["media_type"] = "image"
            elif file_data["has_audio"] and not file_data["has_video"]:
                file_data["media_type"] = "audio"
            else:
                # If neither set, just assume video
                file_data["media_type"] = "video"

            # Save new file to the project data
            file = File()
            file.data = file_data

            # Is this file an image sequence / animation?
            image_seq_details = self.get_image_sequence_details(filepath)
            if image_seq_details:
                # Update file with correct path
                folder_path = image_seq_details["folder_path"]
                file_name = image_seq_details["file_path"]
                base_name = image_seq_details["base_name"]
                fixlen = image_seq_details["fixlen"]
                digits = image_seq_details["digits"]
                extension = image_seq_details["extension"]

                if not fixlen:
                    zero_pattern = "%d"
                else:
                    zero_pattern = "%%0%sd" % digits

                # Generate the regex pattern for this image sequence
                pattern = "%s%s.%s" % (base_name, zero_pattern, extension)

                # Split folder name
                folderName = os.path.basename(folder_path)
                if not base_name:
                    # Give alternate name
                    file.data["name"] = "%s (%s)" % (folderName, pattern)

                # Load image sequence (to determine duration and video_length)
                image_seq = openshot.Clip(os.path.join(folder_path, pattern))

                # Update file details
                file.data["path"] = os.path.join(folder_path, pattern)
                file.data["media_type"] = "video"
                file.data["duration"] = image_seq.Reader().info.duration
                file.data["video_length"] = image_seq.Reader().info.video_length

            # Save file
            file.save()
            # Reset list of ignored paths
            self.ignore_image_sequence_paths = []

            return True

        except Exception as ex:
            # Log exception
            log.warning("Failed to import file: {}".format(str(ex)))
            # Show message to user
            msg = QMessageBox()
            msg.setText(_("{} is not a valid video, audio, or image file.".format(filename)))
            msg.exec_()
            return False

    def get_image_sequence_details(self, file_path):
        """Inspect a file path and determine if this is an image sequence"""

        # Get just the file name
        (dirName, fileName) = os.path.split(file_path)
        extensions = ["png", "jpg", "jpeg", "gif", "tif", "svg"]
        match = re.findall(r"(.*[^\d])?(0*)(\d+)\.(%s)" % "|".join(extensions), fileName, re.I)

        if not match:
            # File name does not match an image sequence
            return None
        else:
            # Get the parts of image name
            base_name = match[0][0]
            fixlen = match[0][1] > ""
            number = int(match[0][2])
            digits = len(match[0][1] + match[0][2])
            extension = match[0][3]

            full_base_name = os.path.join(dirName, base_name)

            # Check for images which the file names have the different length
            fixlen = fixlen or not (
                glob.glob("%s%s.%s" % (full_base_name, "[0-9]" * (digits + 1), extension))
                or glob.glob("%s%s.%s" % (full_base_name, "[0-9]" * ((digits - 1) if digits > 1 else 3), extension))
            )

            # Check for previous or next image
            for x in range(max(0, number - 100), min(number + 101, 50000)):
                if x != number and os.path.exists(
                   "%s%s.%s" % (full_base_name, str(x).rjust(digits, "0") if fixlen else str(x), extension)):
                    is_sequence = True
                    break
            else:
                is_sequence = False

            if is_sequence and dirName not in self.ignore_image_sequence_paths:
                log.info('Prompt user to import image sequence from {}'.format(dirName))
                # Ignore this path (temporarily)
                self.ignore_image_sequence_paths.append(dirName)

                # Translate object
                _ = get_app()._tr

                # Handle exception
                ret = QMessageBox.question(self, _("Import Image Sequence"),
                                           _("Would you like to import %s as an image sequence?") % fileName,
                                           QMessageBox.No | QMessageBox.Yes)
                if ret == QMessageBox.Yes:
                    # Yes, import image sequence
                    log.info('Importing {} as image sequence {}'.format(file_path, base_name + '*.' + extension))
                    parameters = {
                        "file_path": file_path,
                        "folder_path": dirName,
                        "base_name": base_name,
                        "fixlen": fixlen,
                        "digits": digits,
                        "extension": extension
                    }
                    return parameters
                else:
                    return None
            else:
                return None

    # Handle a drag and drop being dropped on widget
    def dropEvent(self, event):
        # Reset list of ignored image sequences paths
        self.ignore_image_sequence_paths = []

        # Set cursor to waiting
        get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

        for uri in event.mimeData().urls():
            log.info('Processing drop event for {}'.format(uri))
            filepath = uri.toLocalFile()
            if os.path.exists(filepath) and os.path.isfile(filepath):
                log.info('Adding file: {}'.format(filepath))
                if ".osp" in filepath:
                    # Auto load project passed as argument
                    self.win.OpenProjectSignal.emit(filepath)
                    event.accept()
                else:
                    # Auto import media file
                    if self.add_file(filepath):
                        event.accept()

        # Restore cursor
        get_app().restoreOverrideCursor()

    def filter_changed(self):
        self.refresh_view()

    def refresh_view(self):
        """Filter files with proxy class"""
        model = self.model()
        filter_text = self.win.filesFilter.text()
        model.setFilterRegExp(QRegExp(filter_text.replace(' ', '.*'), Qt.CaseInsensitive))

        col = model.sortColumn()
        model.sort(col)

    def resize_contents(self):
        pass

    def __init__(self, model, *args):
        # Invoke parent init
        super().__init__(*args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.files_model = model
        self.setModel(self.files_model.proxy_model)

        # Remove the default selection model and wire up to the shared one
        self.selectionModel().deleteLater()
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionModel(self.files_model.selection_model)

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.ignore_image_sequence_paths = []

        # Setup header columns and layout
        self.setIconSize(QSize(131, 108))
        self.setGridSize(QSize(102, 92))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)

        self.setUniformItemSizes(True)
        self.setStyleSheet('QListView::item { padding-top: 2px; }')

        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)

        self.files_model.ModelRefreshed.connect(self.refresh_view)

        # Load initial files model data
        self.files_model.update_model()

        # setup filter events
        app = get_app()
        app.window.filesFilter.textChanged.connect(self.filter_changed)
        app.window.refreshFilesSignal.connect(self.refresh_view)
