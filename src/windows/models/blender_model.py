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

# Try to get the security-patched XML functions from defusedxml
try:
    from defusedxml import minidom as xml
except ImportError:
    from xml.dom import minidom as xml

from PyQt5.QtCore import Qt, QSortFilterProxyModel, QItemSelectionModel
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel

import openshot

from classes import info
from classes.logger import log
from classes.app import get_app


class BlenderFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def lessThan(self, left, right):
        """Sort blender model by a column at runtime"""
        leftData = left.data(self.sortRole())
        rightData = right.data(self.sortRole())

        return leftData < rightData


class BlenderModel():
    def update_model(self, clear=True):
        log.info("updating effects model.")

        _ = self.app._tr

        # Clear all items
        if clear:
            self.model_paths = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Thumb"), _("Name")])

        # get a list of files in the application blender directory
        blender_dir = os.path.join(info.PATH, "blender")
        icons_dir = os.path.join(blender_dir, "icons")

        for file in sorted(os.listdir(blender_dir)):
            path = os.path.join(blender_dir, file)
            if path in self.model_paths:
                continue
            if os.path.isfile(path) and ".xml" in file:
                # load xml effect file
                xmldoc = xml.parse(path)

                # Get column data for model
                title = xmldoc.getElementsByTagName("title")[0].childNodes[0].data
                icon_name = xmldoc.getElementsByTagName("icon")[0].childNodes[0].data
                icon_path = os.path.join(icons_dir, icon_name)
                service = xmldoc.getElementsByTagName("service")[0].childNodes[0].data
                xmldoc.unlink()

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
                        reader.Open()

                        # Save thumbnail
                        reader.GetFrame(0).Thumbnail(
                            thumb_path, 98, 64, "", "",
                            "#000", False, "png", 85, 0.0)
                        reader.Close()
                    except Exception:
                        log.info('Invalid blender image file: %s', icon_path)
                        continue

                # Load icon (using display DPI)
                icon = QIcon()
                icon.addFile(thumb_path)

                row = []
                flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                # Append thumbnail
                col = QStandardItem(self.app._tr(title))
                col.setIcon(icon)
                col.setToolTip(self.app._tr(title))
                col.setFlags(flags)
                row.append(col)

                # Append Name
                col = QStandardItem(self.app._tr(title))
                col.setData(self.app._tr(title), Qt.DisplayRole)
                col.setFlags(flags)
                row.append(col)

                # Append Path
                col = QStandardItem(path)
                col.setData(path, Qt.DisplayRole)
                col.setFlags(flags)
                row.append(col)

                # Append Service
                col = QStandardItem(service)
                col.setData(service, Qt.DisplayRole)
                col.setFlags(flags)
                row.append(col)

                self.model.appendRow(row)
                self.model_paths[path] = path

                # Process events in QT (to keep the interface responsive)
                self.app.processEvents()

    def __init__(self, *args):

        # Create standard model
        self.app = get_app()
        self.model = QStandardItemModel()
        self.model.setColumnCount(3)
        self.model_paths = {}

        # Create proxy model (for sorting and filtering)
        self.proxy_model = BlenderFilterProxyModel()
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(1)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)

        # Create selection model to share between views
        self.selection_model = QItemSelectionModel(self.proxy_model)
