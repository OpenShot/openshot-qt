""" 
 @file
 @brief This file contains the credits treeview, used by the about window
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
from urllib.parse import urlparse

from PyQt5.QtCore import QSize, Qt, QPoint
from PyQt5.QtWidgets import QListView, QTreeView, QMessageBox, QAbstractItemView, QMenu, QSizePolicy, QHeaderView

from classes.logger import log
from classes.app import get_app
from windows.models.credits_model import CreditsModel

try:
    import json
except ImportError:
    import simplejson as json


class CreditsTreeView(QTreeView):
    """ A ListView QWidget used on the credits window """
    def resize_contents(self):
        pass

    def refresh_view(self, filter=None):
        self.credits_model.update_model(filter=filter)

        # Format columns
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(0, 22)
        self.setColumnWidth(1, 22)
        self.setColumnWidth(2, 150)
        self.setColumnWidth(3, 150)
        self.setColumnWidth(4, 150)
        self.sortByColumn(2, Qt.AscendingOrder)

        if "email" not in self.columns:
            self.setColumnHidden(3, True)
        if "website" not in self.columns:
            self.setColumnHidden(4, True)

    def __init__(self, credits, columns, *args):
        # Invoke parent init
        QListView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.credits_model = CreditsModel(credits)
        self.selected = []

        # Setup header columns
        self.setModel(self.credits_model.model)
        self.setIndentation(0)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setStyleSheet('QTreeView::item { padding-top: 2px; }')
        self.columns = columns


        # Refresh view
        self.refresh_view()

        # setup filter events
        app = get_app()
