"""
 @file
 @brief This file contains the credits treeview, used by the about window
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

import webbrowser
from qt_api import Qt
from qt_api import QTreeView, QAbstractItemView, QSizePolicy, QHeaderView, QApplication
from qt_api import QCursor
from qt_api import make_filter_regex, set_proxy_filter
from functools import partial

from classes.logger import log
from classes.app import get_app
from windows.models.credits_model import CreditsModel
from .menu import StyledContextMenu


class CreditsTreeView(QTreeView):
    """ A ListView QWidget used on the credits window """
    def resize_contents(self):
        pass

    def refresh_view(self):
        """Format columns and sort"""
        # Model is already populated; just adjust view

        # Format columns
        header = self.header()
        header.setMinimumSectionSize(22)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(0, 24)
        self.setColumnWidth(1, 24)
        header.setSectionResizeMode(2, QHeaderView.Interactive if "email" in self.columns else QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Stretch if "email" in self.columns else QHeaderView.Interactive)
        self.setColumnWidth(2, 200)
        self.setColumnWidth(3, 220)
        self.setColumnWidth(4, 280)
        self.sortByColumn(2, Qt.AscendingOrder)

        if "email" not in self.columns:
            self.setColumnHidden(3, True)
        if "website" not in self.columns:
            self.setColumnHidden(4, True)

    def filter_changed(self, text=""):
        """Apply filter text to proxy model"""
        regex = make_filter_regex(text, case_insensitive=True)
        set_proxy_filter(self.model(), regex)
        self.model().setFilterKeyColumn(-1)
        self.model().sort(2, Qt.AscendingOrder)

    def contextMenuEvent(self, event):
        log.info('contextMenuEvent')
        _ = get_app()._tr

        # Get proxy model and selection
        model = self.model()
        index = self.indexAt(event.pos())
        if index.isValid():
            email = model.index(index.row(), 3).data()
            website = model.index(index.row(), 4).data()

            menu = StyledContextMenu(parent=self)
            if email:
                copy_action = menu.addAction(_("Copy E-mail"))
                copy_action.triggered.connect(partial(self.CopyEmailTriggered, email))
            if website:
                github_action = menu.addAction(_("View Website"))
                github_action.triggered.connect(partial(self.ViewWebsite, website))
            menu.popup(QCursor.pos())

    def CopyEmailTriggered(self, email=""):
        log.info("CopyEmailTriggered")
        clipboard = QApplication.clipboard()
        clipboard.setText(email)

    def ViewWebsite(self, website=""):
        log.info("ViewWebsite")
        try:
            webbrowser.open(website)
        except Exception:
            log.warning('Failed to launch web browser to %s' % website)

    def __init__(self, credits, columns, *args):
        # Invoke parent init
        QTreeView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.credits_model = CreditsModel(credits)
        self.selected = []

        # Setup header columns
        self.setIndentation(0)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(False)
        self.setUniformRowHeights(True)
        self.columns = columns

        # Populate model
        self.credits_model.update_model()

        # Set proxy model and shared selection model
        self.setModel(self.credits_model.proxy_model)
        self.selectionModel().deleteLater()
        self.setSelectionModel(self.credits_model.selection_model)

        # Refresh view
        self.refresh_view()
