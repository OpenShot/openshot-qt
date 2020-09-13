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
        selected = self.selectedIndexes()

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.model.mimeData(selected))
        icon = self.model.data(selected[0], Qt.DecorationRole)
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

    @pyqtSlot(int)
    def group_changed(self, index=-1):
        item = get_app().window.emojiFilterGroup.itemData(index)
        self.group_model.setFilterFixedString(item)
        self.group_model.setFilterKeyColumn(1)

        # Save current emoji filter to settings
        s = get_settings()
        setting_emoji_group = s.get('emoji_group_filter') or 'smileys-emotion'
        if setting_emoji_group != item:
            s.set('emoji_group_filter', item)

        self.refresh_view()

    @pyqtSlot(str)
    def filter_changed(self, filter_text=None):
        """Filter emoji with proxy class"""

        self.model.setFilterRegExp(QRegExp(filter_text, Qt.CaseInsensitive))
        self.model.setFilterKeyColumn(0)
        self.refresh_view()

    def refresh_view(self):
        col = self.model.sortColumn()
        self.model.sort(col)

    def __init__(self, model):
        # Invoke parent init
        QListView.__init__(self)

        # Get external references
        app = get_app()
        _ = app._tr
        self.win = app.window

        # Get Model data
        self.emojis_model = model
        self.group_model = self.emojis_model.group_model
        self.model = self.emojis_model.proxy_model

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns
        self.setModel(self.model)
        self.setIconSize(QSize(75, 75))
        self.setGridSize(QSize(90, 100))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(False)
        self.setStyleSheet('QListView::item { padding-top: 2px; }')

        # Get default emoji filter group
        s = get_settings()
        default_type = s.get('emoji_group_filter') or 'smileys-emotion'

        # setup filter events
        self.win.emojisFilter.textChanged.connect(self.filter_changed)

        # Loop through emoji groups, and populate emoji filter drop-down
        self.win.emojiFilterGroup.clear()
        self.win.emojiFilterGroup.addItem(_("Show All"), "")
        dropdown_index = 0
        for index, emoji_type in enumerate(sorted(self.emojis_model.emoji_groups)):
            self.win.emojiFilterGroup.addItem(_(emoji_type.capitalize()), emoji_type)
            if emoji_type == default_type:
                # Initialize emoji filter group to settings
                # Off by one, due to 'show all' choice above
                dropdown_index = index + 1

        if not self.win.mode == "unittest":
            self.win.emojiFilterGroup.currentIndexChanged.connect(self.group_changed)
        self.win.emojiFilterGroup.setCurrentIndex(dropdown_index)

