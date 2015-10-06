""" 
 @file
 @brief This file contains the transitions file treeview, used by the main window
 @author Jonathan Thomas <jonathan@openshot.org>
 
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

from PyQt5.QtCore import QSize, QPoint
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QListView, QMenu

from classes.app import get_app
from windows.models.transition_model import TransitionsModel

try:
    import json
except ImportError:
    import simplejson as json


class TransitionsListView(QListView):
    """ A QListView QWidget used on the main window """
    drag_item_size = 48

    def contextMenuEvent(self, event):
        # Set context menu mode
        app = get_app()
        app.context_menu_object = "transitions"

        menu = QMenu(self)
        menu.addAction(self.win.actionDetailsView)
        menu.addAction(self.win.actionThumbnailView)
        menu.exec_(QCursor.pos())

        # Ignore event, propagate to parent
        event.ignore()
        super().mouseMoveEvent(event)

    def startDrag(self, event):
        """ Override startDrag method to display custom icon """

        # Get image of selected item
        selected_row = self.transition_model.model.itemFromIndex(self.selectionModel().selectedIndexes()[0]).row()
        icon = self.transition_model.model.item(selected_row, 0).icon()

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.transition_model.model.mimeData(self.selectionModel().selectedIndexes()))
        # drag.setPixmap(QIcon.fromTheme('document-new').pixmap(QSize(self.drag_item_size,self.drag_item_size)))
        drag.setPixmap(icon.pixmap(QSize(self.drag_item_size, self.drag_item_size)))
        drag.setHotSpot(QPoint(self.drag_item_size / 2, self.drag_item_size / 2))
        drag.exec_()

    def clear_filter(self):
        get_app().window.transitionsFilter.setText("")

    def filter_changed(self):
        if self.win.transitionsFilter.text() == "":
            self.win.actionTransitionsClear.setEnabled(False)
        else:
            self.win.actionTransitionsClear.setEnabled(True)
        self.refresh_view()

    def refresh_view(self):
        self.transition_model.update_model()

    def __init__(self, *args):
        # Invoke parent init
        QListView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.transition_model = TransitionsModel()

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns
        self.setModel(self.transition_model.model)
        self.setIconSize(QSize(131, 108))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setStyleSheet('QListView::item { padding-top: 2px; }')

        # Refresh view
        self.refresh_view()

        # setup filter events
        app = get_app()
        app.window.transitionsFilter.textChanged.connect(self.filter_changed)
        app.window.actionTransitionsClear.triggered.connect(self.clear_filter)
