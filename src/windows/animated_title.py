"""
 @file
 @brief This file loads the animated title dialog (i.e Blender animation automation)
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

import sys
import os
import time
import uuid
import shutil
import subprocess
import re
import math

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.metrics import *
from windows.views.blender_listview import BlenderListView

import json

class AnimatedTitle(QDialog):
    """ Animated Title Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'animated-title.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Track metrics
        track_metric_screen("animated-title-screen")

        # Add render button
        app = get_app()
        _ = app._tr
        self.btnRender = QPushButton(_('Render'))
        self.btnCancel = QPushButton(_('Cancel'))
        self.buttonBox.addButton(self.btnRender, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.btnCancel, QDialogButtonBox.RejectRole)

        # Add blender treeview
        self.blenderView = BlenderListView(self)
        self.verticalLayout.addWidget(self.blenderView)

        # Init variables
        self.unique_folder_name = str(uuid.uuid1())
        self.output_dir = os.path.join(info.USER_PATH, "blender")
        self.selected_template = ""
        self.is_rendering = False
        self.my_blender = None

        # Clear all child controls
        self.clear_effect_controls()

    def accept(self):
        """ Start rendering animation, but don't close window """

        # Render
        self.blenderView.Render()

    def close(self):
        """ Actually close window and accept dialog """

        # Re-enable interface
        self.blenderView.enable_interface()

        # Accept dialog
        super().accept()

    def closeEvent(self, event):

        # Stop threads
        self.blenderView.background.quit()

        # Re-enable interface
        self.blenderView.enable_interface()

    def reject(self):

        # Stop threads
        self.blenderView.Cancel()
        self.blenderView.background.quit()

        # Cancel dialog
        super().reject()

    def clear_effect_controls(self):
        """ Clear all child widgets used for settings """

        # Loop through child widgets
        for child in self.settingsContainer.children():
            try:
                self.settingsContainer.layout().removeWidget(child)
                child.deleteLater()
            except:
                log.warning('Failed to remove child widget for effect controls')
