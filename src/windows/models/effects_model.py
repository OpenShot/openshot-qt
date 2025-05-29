"""
 @file
 @brief This file contains the effects model, used by the main window
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

from PyQt5.QtCore import (
    QObject, QMimeData, Qt, QSize, pyqtSignal,
    QSortFilterProxyModel, QPersistentModelIndex, QItemSelectionModel,
)
from PyQt5.QtGui import QIcon, QPixmap, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMessageBox

import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

import json


class EffectsProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter for common transitions and text filter"""

        if not get_app().window.actionEffectsShowAll.isChecked():
            # Fetch the effect values
            effect_name = self.sourceModel().data(self.sourceModel().index(sourceRow, 1, sourceParent))
            effect_desc = self.sourceModel().data(self.sourceModel().index(sourceRow, 2, sourceParent))
            effect_type = self.sourceModel().data(self.sourceModel().index(sourceRow, 3, sourceParent))

            # Return, if regExp match in displayed format.
            if get_app().window.actionEffectsShowVideo.isChecked():
                return effect_type == "Video" and \
                    (self.filterRegExp().indexIn(effect_name) >= 0 or
                     self.filterRegExp().indexIn(effect_desc) >= 0)
            else:
                return effect_type == "Audio" and \
                    (self.filterRegExp().indexIn(effect_name) >= 0 or
                     self.filterRegExp().indexIn(effect_desc) >= 0)

        # Continue running built-in parent filter logic
        return super(EffectsProxyModel, self).filterAcceptsRow(sourceRow, sourceParent)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of class names for requested effect indexes
        items = [i.sibling(i.row(), 4).data() for i in indexes]
        data.setText(json.dumps(items))
        data.setHtml("effect")

        # Return Mimedata
        return data


class EffectsModel(QObject):
    ModelRefreshed = pyqtSignal()

    def update_model(self, clear=True):
        log.info("updating effects model.")
        app = get_app()

        # Get window to check filters
        win = app.window
        _ = app._tr

        # Clear all items
        if clear:
            self.model_names = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Thumb"), _("Name"), _("Description")])

        # Get the folder path of effects
        effects_dir = os.path.join(info.PATH, "effects")
        icons_dir = os.path.join(effects_dir, "icons")

        # Get a JSON list of all supported effects in libopenshot
        raw_effects_list = json.loads(openshot.EffectInfo.Json())

        # Loop through each effect
        for effect_info in raw_effects_list:
            # Get basic properties about each effect
            effect_name = effect_info["class_name"]
            title = effect_info["name"]
            description = effect_info["description"]
            # Remove any spaces from icon name
            icon_name = "%s.png" % effect_name.lower().replace(' ', '')
            icon_path = os.path.join(icons_dir, icon_name)

            # Determine the category of effect (audio, video, both)
            category = None
            if effect_info["has_video"] and effect_info["has_audio"]:
                category = "Audio & Video"
            elif not effect_info["has_video"] and effect_info["has_audio"]:
                category = "Audio"
            elif effect_info["has_video"] and not effect_info["has_audio"]:
                category = "Video"

            # Check for thumbnail path (in build-in cache)
            thumb_path = os.path.join(info.IMAGES_PATH, "cache", icon_name)

            # Check built-in cache (if not found)
            if not os.path.exists(thumb_path):
                # Check user folder cache
                thumb_path = os.path.join(info.CACHE_PATH, icon_name)

            # Generate thumbnail (if needed)
            if not os.path.exists(thumb_path):

                try:
                    # Reload this reader
                    log.info('Generating thumbnail for %s (%s)' % (thumb_path, icon_path))
                    clip = openshot.Clip(icon_path)
                    reader = clip.Reader()

                    # Open reader
                    reader.Open()

                    # Save thumbnail
                    reader.GetFrame(0).Thumbnail(
                        thumb_path, 98, 64,
                        os.path.join(info.IMAGES_PATH, "mask.png"),
                        "", "#000", True, "png", 85
                    )
                    reader.Close()

                except Exception:
                    # Handle exception
                    log.warning("{} is not a valid image file.".format(icon_path))

            row = []

            # Append thumbnail
            col = QStandardItem()

            # Load icon (using display DPI)
            icon = QIcon()
            icon.addFile(thumb_path)

            col.setIcon(icon)
            col.setText(self.app._tr(title))
            col.setToolTip(self.app._tr(title))
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append Name
            col = QStandardItem("Name")
            col.setData(self.app._tr(title), Qt.DisplayRole)
            col.setText(self.app._tr(title))
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append Description
            col = QStandardItem("Description")
            col.setData(self.app._tr(description), Qt.DisplayRole)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append Category
            col = QStandardItem("Category")
            col.setData(category, Qt.DisplayRole)
            col.setText(category)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append Path
            col = QStandardItem("Effect")
            col.setData(effect_name, Qt.DisplayRole)
            col.setText(effect_name)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            row.append(col)

            # Append ROW to MODEL (if does not already exist in model)
            if effect_name not in self.model_names:
                self.model.appendRow(row)
                self.model_names[effect_name] = QPersistentModelIndex(row[1].index())

        # Emit signal when model is updated
        self.ModelRefreshed.emit()

    def __init__(self, *args):
        # Init QObject superclass
        super().__init__(*args)

        # Create standard model
        self.app = get_app()
        self.model = QStandardItemModel()
        self.model.setColumnCount(5)
        self.model_names = {}

        # Create proxy model (for sorting and filtering)
        self.proxy_model = EffectsProxyModel()
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)
        self.proxy_model.setFilterKeyColumn(-1)

        # Create selection model to share between views
        self.selection_model = QItemSelectionModel(self.proxy_model)

        # Attempt to load model testing interface, if requested
        # (will only succeed with Qt 5.11+)
        if info.MODEL_TEST:
            try:
                # Create model tester objects
                from PyQt5.QtTest import QAbstractItemModelTester
                self.model_tests = []
                for m in [self.proxy_model, self.model]:
                    self.model_tests.append(
                        QAbstractItemModelTester(
                            m, QAbstractItemModelTester.FailureReportingMode.Warning)
                    )
                log.info("Enabled {} model tests for effects data".format(len(self.model_tests)))
            except ImportError:
                pass
