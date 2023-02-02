"""
 @file
 @brief This file contains the profiles treeview, used by the profile window
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2023 OpenShot Studios, LLC
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

from PyQt5.QtCore import Qt, QItemSelectionModel, QRegExp, pyqtSignal, QTimer
from PyQt5.QtWidgets import QListView, QTreeView, QAbstractItemView, QSizePolicy

from classes.app import get_app
from windows.models.profiles_model import ProfilesModel


class ProfilesTreeView(QTreeView):
    FilterCountChanged = pyqtSignal(int)

    """ A ListView QWidget used on the credits window """
    def selectionChanged(self, selected, deselected):
        if deselected and deselected.first() and self.is_filter_running:
            # Selection changed due to filtering... clear selections
            self.selectionModel().clear()
        if not self.is_filter_running and selected and selected.first() and selected.first().indexes():
            # Selection changed due to user selection or init of treeview
            self.selected_profile_object = selected.first().indexes()[0].data(Qt.UserRole)
        super().selectionChanged(selected, deselected)

    def refresh_view(self, filter_text=""):
        """Filter transitions with proxy class"""
        self.is_filter_running = True
        self.model().setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.model().setFilterRegExp(QRegExp(filter_text.lower()))
        self.model().sort(Qt.DescendingOrder)

        # Format columns
        self.sortByColumn(0, Qt.DescendingOrder)
        self.setColumnHidden(0, True)
        self.is_filter_running = False

        # Update filter count
        self.FilterCountChanged.emit(self.profiles_model.proxy_model.rowCount())

        if self.selectionModel().hasSelection():
            current = self.selectionModel().currentIndex()
            self.scrollTo(current)

    def select_profile(self, profile_index):
        """Select a specific profile Key"""
        self.selectionModel().setCurrentIndex(profile_index, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def get_profile(self):
        """Return the selected profile object, if any"""
        return self.selected_profile_object

    def __init__(self, profiles, *args):
        # Invoke parent init
        QListView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.profiles_model = ProfilesModel(profiles)
        self.selected = []

        # Setup header columns
        self.is_filter_running = False
        self.setModel(self.profiles_model.proxy_model)
        self.setIndentation(0)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setStyleSheet('QTreeView::item { padding-top: 2px; }')
        self.columns = 6
        self.selected_profile_object = None

        # Refresh view
        self.profiles_model.update_model()
        QTimer.singleShot(50, self.refresh_view)

        # Resize columns (initial data)
        for column in range(self.columns):
            self.resizeColumnToContents(column)
