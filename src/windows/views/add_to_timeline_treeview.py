"""
 @file
 @brief This file contains the add to timeline file treeview
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

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QTreeView, QAbstractItemView

from classes import info
from classes.app import get_app
from windows.models.add_to_timeline_model import TimelineModel


class TimelineTreeView(QTreeView):
    """ A TreeView QWidget used on the add to timeline window """

    def currentChanged(self, selected, deselected):
        # Get selected item
        self.selected = selected
        self.deselected = deselected

        # Get translation object
        _ = self.app._tr

    def contextMenuEvent(self, event):
        # # Ignore event, propagate to parent
        event.ignore()

    def mousePressEvent(self, event):

        # Ignore event, propagate to parent
        event.ignore()
        super().mousePressEvent(event)

    def refresh_view(self):
        self.timeline_model.update_model()
        self.hideColumn(2)

    def __init__(self, *args):
        # Invoke parent init
        QTreeView.__init__(self, *args)

        # Get a reference to the window object
        self.app = get_app()
        self.win = args[0]

        # Get Model data
        self.timeline_model = TimelineModel()

        # Keep track of mouse press start position to determine when to start drag
        self.selected = None
        self.deselected = None

        # Setup header columns
        self.setModel(self.timeline_model.model)
        self.setIconSize(info.TREE_ICON_SIZE)
        self.setIndentation(0)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setWordWrap(True)
        self.setStyleSheet('QTreeView::item { padding-top: 2px; }')

        # Refresh view
        self.refresh_view()
