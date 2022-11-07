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

from PyQt5.QtCore import Qt, QObject, QMimeData, QSortFilterProxyModel, QItemSelectionModel
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

import json


class TitleFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def lessThan(self, left, right):
        """Sort titles model by a column at runtime"""
        leftData = left.data(self.sortRole())
        rightData = right.data(self.sortRole())

        return leftData < rightData


class TitleStandardItemModel(QStandardItemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("titles.model")

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        files = [
            self.itemFromIndex(i).data(TitleRoles.PathRole)
            for i in indexes
        ]
        data.setText(json.dumps(files))
        data.setHtml("title")

        # Return Mimedata
        return data


class TitleRoles:
    PathRole = Qt.UserRole + 11


class TitlesModel(QObject):
    def update_model(self, clear=True):
        log.debug("Updating title model")
        # Get window to check filters
        _ = self.app._tr

        # Clear all items
        if clear:
            self.model_paths = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Name")])

        # get a list of files in the OpenShot package directory
        titles_dir = os.path.join(info.PATH, "titles")
        titles_list = [
            os.path.join(titles_dir, filename)
            for filename in sorted(os.listdir(titles_dir))
            ]
        # Add user-defined titles (if any)
        titles_list.extend([
            os.path.join(info.USER_TITLES_PATH, filename)
            for filename in sorted(os.listdir(info.USER_TITLES_PATH))
            if fnmatch.fnmatch(filename, '*.svg')
            ])

        for path in sorted(titles_list):
            filename = os.path.basename(path)
            fileBaseName = os.path.splitext(filename)[0]

            # Skip hidden files (such as .DS_Store, etc...)
            if (filename[0] == "."
               or "thumbs.db" in filename.lower()
               or filename.lower() == "temp.svg"):
                continue

            # split the name into parts (looking for a number)
            suffix_number = None
            name_parts = fileBaseName.split("_")
            if name_parts[-1].isdigit():
                suffix_number = name_parts[-1]

            # get name of title template
            title_name = fileBaseName.replace("_", " ").capitalize()

            # replace suffix number with placeholder (if any)
            if suffix_number:
                title_name = title_name.replace(suffix_number, "%s")
                title_name = self.app._tr(title_name) % suffix_number
            else:
                title_name = self.app._tr(title_name)

            # Check for thumbnail path (in build-in cache)
            thumb_path = os.path.join(info.IMAGES_PATH, "cache", "{}.png".format(fileBaseName))
            if not os.path.exists(thumb_path):
                # Check user folder cache (if not found)
                thumb_path = os.path.join(info.CACHE_PATH, "{}.png".format(fileBaseName))
            if not os.path.exists(thumb_path):
                # Generate thumbnail (if needed)
                try:
                    # Reload this reader
                    clip = openshot.Clip(path)
                    reader = clip.Reader()
                    reader.Open()

                    # Save thumbnail to disk
                    reader.GetFrame(0).Thumbnail(
                        thumb_path, 98, 64,
                        os.path.join(info.IMAGES_PATH, "mask.png"),
                        "", "#000", True, "png", 85
                    )
                    reader.Close()
                    clip.Close()
                except Exception as ex:
                    log.info('Failed to open {} as title: {}'.format(filename, ex))
                    msg = QMessageBox()
                    msg.setText(_("%s is not a valid image file." % filename))
                    msg.exec_()
                    continue

            # Load icon (using display DPI)
            icon = QIcon()
            icon.addFile(thumb_path)

            # Create item entry for model
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled
            item = QStandardItem(icon, title_name)
            item.setData(path, TitleRoles.PathRole)
            item.setToolTip(title_name)
            item.setFlags(flags)
            # Append to MODEL (if does not already exist)
            if path not in self.model_paths:
                self.model.appendRow([item])
                self.model_paths[path] = path

            # Process events in QT (to keep the interface responsive)
            self.app.processEvents()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("TitlesModel")
        # Create standard model
        self.app = get_app()
        self.model = TitleStandardItemModel(self.parent())
        self.model.setColumnCount(1)
        self.model_paths = {}

        # Create proxy model (for sorting and filtering)
        self.proxy_model = TitleFilterProxyModel()
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(1)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)

        # Create selection model to share between views
        self.selection_model = QItemSelectionModel(self.proxy_model)

        # Attempt to load model testing interface, if requested
        # (will only succeed with Qt 5.11+)
        if info.MODEL_TEST:
            try:
                # Create model tester objects
                from PyQt5.QtTest import QAbstractItemModelTester
                QAbstractItemModelTester(
                    self.model, QAbstractItemModelTester.FailureReportingMode.Warning)
                log.info("Enabled model tests for title editor data")
            except ImportError:
                pass
