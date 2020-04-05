"""
 @file
 @brief This file contains the emojis listview, used by the main window
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
from PyQt5.QtCore import QMimeData, QSize, QPoint, Qt, pyqtSlot, QRegExp
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QListView

import openshot  # Python module for libopenshot (required video editing module installed separately)
from classes.query import File
from classes.app import get_app
from classes.settings import get_settings
from classes.logger import log
import json


class EmojisListView(QListView):
    """ A QListView QWidget used on the main window """
    drag_item_size = 48

    def dragEnterEvent(self, event):
        # If dragging urls onto widget, accept
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()

    def startDrag(self, event):
        """ Override startDrag method to display custom icon """

        # Get image of selected item
        selected_row = self.emojis_model.model.itemFromIndex(self.emojis_model.proxy_model.mapToSource(self.selectionModel().selectedIndexes()[0])).row()
        icon = self.emojis_model.model.item(selected_row, 0).icon()

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.emojis_model.proxy_model.mimeData(self.selectionModel().selectedIndexes()))
        drag.setPixmap(icon.pixmap(QSize(self.drag_item_size, self.drag_item_size)))
        drag.setHotSpot(QPoint(self.drag_item_size / 2, self.drag_item_size / 2))

        # Create emoji file before drag starts
        data = json.loads(drag.mimeData().text())
        file = self.add_file(data[0])

        # Update mimedata for emoji
        data = QMimeData()
        data.setText(json.dumps([file.id]))
        data.setHtml("clip")
        drag.setMimeData(data)

        # Start drag
        drag.exec_()

    def add_file(self, filepath):
        filename = os.path.basename(filepath)

        # Add file into project
        app = get_app()
        _ = get_app()._tr

        # Check for this path in our existing project data["1F595-1F3FE", "/home/jonathan/apps/openshot-qt-git/src/emojis/color/svg/1F595-1F3FE.svg"]
        file = File.get(path=filepath)

        # If this file is already found, exit
        if file:
            return file

        # Load filepath in libopenshot clip object (which will try multiple readers to open it)
        clip = openshot.Clip(filepath)

        # Get the JSON for the clip's internal reader
        try:
            reader = clip.Reader()
            file_data = json.loads(reader.Json())

            # Determine media type
            file_data["media_type"] = "image"

            # Save new file to the project data
            file = File()
            file.data = file_data
            file.save()
            return file

        except Exception as ex:
            # Log exception
            log.warning("Failed to import file: {}".format(str(ex)))

    @pyqtSlot(str)
    def filter_changed(self):
        self.refresh_view()

        # Save current emoji filter to settings
        s = get_settings()
        setting_emoji_group = s.get('emoji_group_filter') or 'smileys-emotion'
        current_emoji_group = get_app().window.emojiFilterGroup.currentData()
        if setting_emoji_group != current_emoji_group:
            s.set('emoji_group_filter', current_emoji_group)

    def refresh_view(self):
        """Filter transitions with proxy class"""
        filter_text = self.win.emojisFilter.text()
        self.emojis_model.proxy_model.setFilterRegExp(QRegExp(filter_text.replace(' ', '.*')))
        self.emojis_model.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.emojis_model.proxy_model.sort(Qt.AscendingOrder)

    def __init__(self, model):
        # Invoke parent init
        QListView.__init__(self)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.emojis_model = model

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns
        self.setModel(self.emojis_model.proxy_model)
        self.setIconSize(QSize(75, 75))
        self.setGridSize(QSize(90, 100))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(False)
        self.setStyleSheet('QListView::item { padding-top: 2px; }')

        # Load initial emoji model data
        self.emojis_model.update_model()
        self.refresh_view()

        # setup filter events
        app = get_app()
        app.window.emojisFilter.textChanged.connect(self.filter_changed)
        app.window.emojiFilterGroup.currentIndexChanged.connect(self.filter_changed)
