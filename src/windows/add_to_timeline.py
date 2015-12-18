"""
 @file
 @brief This file loads the Addtotimeline dialog (i.e add several clips in the timeline)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2014 OpenShot Studios, LLC
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

from PyQt5.QtWidgets import *
from classes import info, ui_util
from classes.logger import log
from windows.views.add_to_timeline_treeview import TimelineTreeView


class AddToTimeline(QDialog):
    """ Add To timeline Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'add-to-timeline.ui')

    def btnMoveUpClicked(self, event):
        """Callback for move up button click"""
        log.info("btnMoveUpClicked")

    def btnMoveDownClicked(self, event):
        """Callback for move up button click"""
        log.info("btnMoveDownClicked")

    def btnShuffleClicked(self, event):
        """Callback for move up button click"""
        log.info("btnShuffleClicked")

    def btnRemoveClicked(self, event):
        """Callback for move up button click"""
        log.info("btnRemoveClicked")


    def __init__(self, files=None):
        # Create dialog class
        QDialog.__init__(self)

        # Load UI from Designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Add custom treeview to window
        self.treeFiles = TimelineTreeView(self)
        self.vboxTreeParent.insertWidget(0, self.treeFiles)

        # Update data in model
        self.treeFiles.timeline_model.update_model(files)

        # Refresh view
        self.treeFiles.refresh_view()

        # Connections
        self.btnMoveUp.clicked.connect(self.btnMoveUpClicked)
        self.btnMoveDown.clicked.connect(self.btnMoveDownClicked)
        self.btnShuffle.clicked.connect(self.btnShuffleClicked)
        self.btnRemove.clicked.connect(self.btnRemoveClicked)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)