""" 
 @file
 @brief This file contains the changelog treeview, used by the about window
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

import os
import webbrowser
from urllib.parse import urlparse
from functools import partial

from PyQt5.QtCore import QSize, Qt, QPoint
from PyQt5.QtWidgets import QListView, QTreeView, QMessageBox, QAbstractItemView, QMenu, QSizePolicy, QHeaderView, QApplication
from PyQt5.QtGui import QCursor

from classes.logger import log
from classes.app import get_app
from windows.models.changelog_model import ChangelogModel

try:
    import json
except ImportError:
    import simplejson as json


class ChangelogTreeView(QTreeView):
    """ A ListView QWidget used on the changelog window """
    def resize_contents(self):
        pass

    def refresh_view(self, filter=None):
        self.changelog_model.update_model(filter=filter)

        # Format columns
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(0, 70)
        self.setColumnWidth(1, 85)
        self.setColumnWidth(2, 125)
        self.setColumnWidth(3, 200)

    def contextMenuEvent(self, event):
        log.info('contextMenuEvent')

        # Get data model and selection
        model = self.changelog_model.model
        row = self.indexAt(event.pos()).row()
        if row != -1:
            selected_hash = model.item(row, 0).text()

            menu = QMenu(self)
            copy_action = menu.addAction("Copy Hash")
            copy_action.triggered.connect(partial(self.CopyHashMenuTriggered, selected_hash))
            github_action = menu.addAction("View on GitHub")
            github_action.triggered.connect(partial(self.ChangelogMenuTriggered, selected_hash))
            menu.popup(QCursor.pos())

    def CopyHashMenuTriggered(self, hash=""):
        log.info("CopyHashMenuTriggered")
        clipboard = QApplication.clipboard()
        clipboard.setText(hash)

    def ChangelogMenuTriggered(self, hash=""):
        log.info("ChangelogMenuTriggered")

        try:
            webbrowser.open(self.commit_url % hash)
        except:
            pass

    def __init__(self, commits, commit_url, *args):
        # Invoke parent init
        QListView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.changelog_model = ChangelogModel(commits)
        self.selected = []

        # Setup header columns
        self.setModel(self.changelog_model.model)
        self.setIndentation(0)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setStyleSheet('QTreeView::item { padding-top: 2px; }')
        self.commit_url = commit_url

        # Refresh view
        self.refresh_view()

        # setup filter events
        app = get_app()
