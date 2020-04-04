"""
 @file
 @brief This file contains the transitions file treeview, used by the main window
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

from PyQt5.QtCore import QSize, QPoint, QRegExp, Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeView, QAbstractItemView, QMenu, QSizePolicy

from classes.app import get_app
from windows.models.transition_model import TransitionsModel, TransitionFilterProxyModel

import json

class TransitionsTreeView(QTreeView):
    """ A TreeView QWidget used on the main window """
    drag_item_size = 48

    def contextMenuEvent(self, event):
        # Set context menu mode
        app = get_app()
        app.context_menu_object = "transitions"

        menu = QMenu(self)
        menu.addAction(self.win.actionThumbnailView)
        menu.exec_(QCursor.pos())

    def startDrag(self, event):
        """ Override startDrag method to display custom icon """

        # Get image of selected item
        selected_row = self.transition_model.model.itemFromIndex(self.transition_model.proxy_model.mapToSource(self.selectionModel().selectedIndexes()[0])).row()
        icon = self.transition_model.model.item(selected_row, 0).icon()

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.transition_model.proxy_model.mimeData(self.selectionModel().selectedIndexes()))
        drag.setPixmap(icon.pixmap(QSize(self.drag_item_size, self.drag_item_size)))
        drag.setHotSpot(QPoint(self.drag_item_size / 2, self.drag_item_size / 2))
        drag.exec_()

    def refresh_columns(self):
        """Hide certain columns"""
        if type(self) == TransitionsTreeView:
            # Only execute when the treeview is active
            self.hideColumn(2)
            self.hideColumn(3)

    def __init__(self, model):
        # Invoke parent init
        QTreeView.__init__(self)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.transition_model = model

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns
        self.setModel(self.transition_model.proxy_model)
        self.setIconSize(QSize(75, 62))
        self.setIndentation(0)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setStyleSheet('QTreeView::item { padding-top: 2px; }')
        self.transition_model.model.ModelRefreshed.connect(self.refresh_columns)

        # Load initial transition model data
        self.transition_model.update_model()
        self.refresh_columns()

        # setup filter events
        app = get_app()
