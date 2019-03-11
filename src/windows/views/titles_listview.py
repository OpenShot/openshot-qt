""" 
 @file
 @brief This file contains the titles treeview, used by the title editor window
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

from PyQt5.QtCore import QSize, QPoint, QTimer, Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QListView, QMenu

from classes.app import get_app
from windows.models.titles_model import TitlesModel

try:
    import json
except ImportError:
    import simplejson as json


class TitlesListView(QListView):
    """ A QListView QWidget used on the title editor window """

    def currentChanged(self, selected, deselected):
        # Get selected item
        self.selected = selected
        self.deselected = deselected

        # Get translation object
        _ = get_app()._tr

        # Get all selected rows items
        if self.title_model.model.itemFromIndex(self.selected):
            ItemRow = self.title_model.model.itemFromIndex(self.selected).row()
            title_path = self.title_model.model.item(ItemRow, 2).text()

            # Display title in graphicsView
            self.win.filename = title_path

            # Create temp version of title
            self.win.create_temp_title(title_path)

            # Add all widgets for editing
            self.win.load_svg_template()

            # Display temp image (slight delay to allow screen to be shown first)
            QTimer.singleShot(50, self.win.display_svg)

    def refresh_view(self):
        self.title_model.update_model()

    def __init__(self, *args):
        # Invoke parent init
        QListView.__init__(self, *args)

        # Get a reference to the window object
        self.app = get_app()
        self.win = args[0]

        # Get Model data
        self.title_model = TitlesModel()

        # Setup header columns
        self.setModel(self.title_model.model)
        self.setIconSize(QSize(131, 108))
        self.setGridSize(QSize(102, 92))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideRight)
        self.setStyleSheet('QListView::item { padding-top: 10px; }')

        # Refresh view
        self.refresh_view()