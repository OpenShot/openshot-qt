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

import webbrowser
from functools import partial

from qt_api import Qt
from qt_api import QTreeView, QAbstractItemView, QSizePolicy, QHeaderView, QApplication
from qt_api import QCursor
from qt_api import make_filter_regex, set_proxy_filter

from classes.logger import log
from classes.app import get_app
from windows.models.changelog_model import ChangelogModel
from .menu import StyledContextMenu


class ChangelogTreeView(QTreeView):
    """ A ListView QWidget used on the changelog window """
    def resize_contents(self):
        pass

    def refresh_view(self):
        """Format columns and sort"""
        # Model already populated

        # Format columns
        header = self.header()
        header.setMinimumSectionSize(60)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.setColumnWidth(0, self.fontMetrics().horizontalAdvance("0000000000") + 16)
        self.setColumnWidth(1, self.fontMetrics().horizontalAdvance("0000-00-00") + 16)
        self.setColumnWidth(2, 170)

    def showEvent(self, event):
        super().showEvent(event)
        # Parent dialog typography is applied after the view is constructed.
        self.refresh_view()

    def filter_changed(self, text=""):
        """Apply filter text to proxy model"""
        regex = make_filter_regex(text, case_insensitive=True)
        set_proxy_filter(self.model(), regex)
        self.model().setFilterKeyColumn(-1)
        self.model().sort(1, Qt.AscendingOrder)

    def contextMenuEvent(self, event):
        log.info('contextMenuEvent')
        _ = get_app()._tr

        # Get data model and selection
        model = self.model()
        index = self.indexAt(event.pos())
        if index.isValid():
            selected_hash = model.index(index.row(), 0).data()

            menu = StyledContextMenu(parent=self)
            copy_action = menu.addAction(_("Copy Hash"))
            copy_action.triggered.connect(partial(self.CopyHashMenuTriggered, selected_hash))
            github_action = menu.addAction(_("View on GitHub"))
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
        except Exception:
            log.warning('Failed to launch web browser to %s' % self.commit_url)

    def __init__(self, commits, commit_url, *args):
        # Invoke parent init
        QTreeView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.changelog_model = ChangelogModel(commits)
        self.selected = []

        # Populate model
        self.changelog_model.update_model()

        # Setup header columns
        self.setModel(self.changelog_model.proxy_model)
        self.setIndentation(0)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(False)
        self.setUniformRowHeights(True)
        self.selectionModel().deleteLater()
        self.setSelectionModel(self.changelog_model.selection_model)
        self.commit_url = commit_url

        # Refresh view
        self.refresh_view()
