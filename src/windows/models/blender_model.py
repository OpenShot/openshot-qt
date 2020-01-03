"""
 @file
 @brief This file contains the blender model, used by the 3d animated titles screen
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
import xml.dom.minidom as xml

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app


class BlenderModel():
    def update_model(self, clear=True):
        log.info("updating effects model.")
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

        # get a list of files in the OpenShot /effects directory
        effects_dir = os.path.join(info.PATH, "blender")
        icons_dir = os.path.join(effects_dir, "icons")

        for file in sorted(os.listdir(effects_dir)):
            if os.path.isfile(os.path.join(effects_dir, file)) and ".xml" in file:
                # Split path
                path = os.path.join(effects_dir, file)

                # load xml effect file
                xmldoc = xml.parse(path)

                # Get all attributes
                title = xmldoc.getElementsByTagName("title")[0].childNodes[0].data
                description = xmldoc.getElementsByTagName("description")[0].childNodes[0].data
                icon_name = xmldoc.getElementsByTagName("icon")[0].childNodes[0].data
                icon_path = os.path.join(icons_dir, icon_name)
                category = xmldoc.getElementsByTagName("category")[0].childNodes[0].data
                service = xmldoc.getElementsByTagName("service")[0].childNodes[0].data

                # Check for thumbnail path (in build-in cache)
                thumb_path = os.path.join(info.IMAGES_PATH, "cache",  "blender_{}".format(icon_name))

                # Check built-in cache (if not found)
                if not os.path.exists(thumb_path):
                    # Check user folder cache
                    thumb_path = os.path.join(info.CACHE_PATH, "blender_{}".format(icon_name))

                # Check if thumb exists
                if not os.path.exists(thumb_path):

                    try:
                        # Reload this reader
                        clip = openshot.Clip(icon_path)
                        reader = clip.Reader()

                        # Open reader
                        reader.Open()

                        # Determine scale of thumbnail
                        scale = 95.0 / reader.info.width

                        # Save thumbnail
                        reader.GetFrame(0).Thumbnail(thumb_path, 98, 64, "", "",
                                     "#000", False, "png", 85, 0.0)
                        reader.Close()

                    except:
                        # Handle exception
                        msg = QMessageBox()
                        msg.setText(_("{} is not a valid image file.".format(icon_path)))
                        msg.exec_()
                        continue

                row = []

                # Append thumbnail
                col = QStandardItem()
                icon_pixmap = QPixmap(thumb_path)
                scaled_pixmap = icon_pixmap.scaled(QSize(93, 62), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                col.setIcon(QIcon(scaled_pixmap))
                col.setText(self.app._tr(title))
                col.setToolTip(self.app._tr(title))
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                row.append(col)

                # Append Name
                col = QStandardItem("Name")
                col.setData(self.app._tr(title), Qt.DisplayRole)
                col.setText(self.app._tr(title))
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                row.append(col)

                # Append Path
                col = QStandardItem("Path")
                col.setData(path, Qt.DisplayRole)
                col.setText(path)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                row.append(col)

                # Append Service
                col = QStandardItem("Service")
                col.setData(service, Qt.DisplayRole)
                col.setText(service)
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
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
        self.model = QStandardItemModel()
        self.model.setColumnCount(3)
        self.model_paths = {}
