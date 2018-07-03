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

from PyQt5.QtCore import QMimeData, Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes.logger import log
from classes.app import get_app

try:
    import json
except ImportError:
    import simplejson as json


class EffectsStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        files = []
        for item in indexes:
            selected_row = self.itemFromIndex(item).row()
            files.append(self.item(selected_row, 4).text())
        data.setText(json.dumps(files))
        data.setHtml("effect")

        # Return Mimedata
        return data


class EffectsModel():
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
            icon_name = "%s.png" % effect_name.lower()
            icon_path = os.path.join(icons_dir, icon_name)

            # Determine the category of effect (audio, video, both)
            category = None
            if effect_info["has_video"] and effect_info["has_audio"]:
                category = "Audio & Video"
            elif not effect_info["has_video"] and effect_info["has_audio"]:
                category = "Audio"
                icon_path = os.path.join(icons_dir, "audio.png")
            elif effect_info["has_video"] and not effect_info["has_audio"]:
                category = "Video"

            # Filter out effect (if needed)
            if not win.actionEffectsShowAll.isChecked():
                if win.actionEffectsShowVideo.isChecked():
                    if not category == "Video":
                        continue  # to next file, didn't match filter
                elif win.actionEffectsShowAudio.isChecked():
                    if not category == "Audio":
                        continue  # to next file, didn't match filter

            if win.effectsFilter.text() != "":
                if not win.effectsFilter.text().lower() in self.app._tr(title).lower() and not win.effectsFilter.text().lower() in self.app._tr(description).lower():
                    continue

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
                    clip = openshot.Clip(icon_path)
                    reader = clip.Reader()

                    # Open reader
                    reader.Open()

                    # Save thumbnail
                    reader.GetFrame(0).Thumbnail(thumb_path, 98, 64, os.path.join(info.IMAGES_PATH, "mask.png"), "",
                                                 "#000", True)
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
            col.setIcon(QIcon(thumb_path))
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
            if not effect_name in self.model_names:
                self.model.appendRow(row)
                self.model_names[effect_name] = effect_name

    def __init__(self, *args):

        # Create standard model
        self.app = get_app()
        self.model = EffectsStandardItemModel()
        self.model.setColumnCount(5)
        self.model_names = {}
