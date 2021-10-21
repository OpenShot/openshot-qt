"""
 @file
 @brief This file contains the add to timeline model
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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem, QStandardItemModel, QIcon

from classes import info
from classes.logger import log
from classes.app import get_app


class TimelineModel():
    def update_model(self, files=[], clear=True):
        log.info("updating timeline model.")
        app = get_app()

        # Get window to check filters
        _ = app._tr

        # Set files list (if found)
        if files:
            log.info('set files to %s' % files)
            self.files = files

        # Clear all items
        if clear:
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Thumb"), _("Name")])

        log.info(self.files)

        for file in self.files:
            # Get attributes from file
            path, filename = os.path.split(file.data["path"])

            # Get thumbnail path
            if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
                # Determine thumb path
                thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
            else:
                # Audio file
                thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.svg")

            row = []

            # Look for friendly name attribute (optional)
            name = file.data.get("name", filename)

            # Append thumbnail
            col = QStandardItem()
            col.setIcon(QIcon(thumb_path))
            col.setText((name[:9] + '...') if len(name) > 10 else name)
            col.setToolTip(filename)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            row.append(col)

            # Append Name
            col = QStandardItem("Name")
            col.setData(filename, Qt.DisplayRole)
            col.setText((name[:20] + '...') if len(name) > 15 else name)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            row.append(col)

            # Append Path
            col = QStandardItem("Path")
            col.setData(path, Qt.DisplayRole)
            col.setText(path)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            row.append(col)

            # Add row
            self.model.appendRow(row)

            # Process events in QT (to keep the interface responsive)
            app.processEvents()

    def __init__(self):

        # Create standard model
        self.app = get_app()
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.model_paths = {}
        self.files = []
