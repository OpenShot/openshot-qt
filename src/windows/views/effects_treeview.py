"""
 @file
 @brief This file contains the effects file treeview, used by the main window
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

from PyQt5.QtCore import Qt, QSize, QPoint
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QTreeView, QAbstractItemView, QMenu, QSizePolicy

from classes.app import get_app
from classes.logger import log


class EffectsTreeView(QTreeView):
    """ A TreeView QWidget used on the main window """
    drag_item_size = 48

    def contextMenuEvent(self, event):
        # Set context menu mode
        event.accept()
        app = get_app()
        app.context_menu_object = "effects"

        menu = QMenu(self)
        menu.addAction(self.win.actionThumbnailView)
        menu.popup(event.globalPos())

    def startDrag(self, supportedActions):
        """ Override startDrag method to display custom icon """

        # Get first column indexes for all selected rows
        selected = self.selectionModel().selectedRows(0)

        # Get image of current item
        current = self.selectionModel().currentIndex()
        if not current.isValid() and selected:
            current = selected[0]

        if not current.isValid():
            # We can't find anything to drag
            log.warning("No draggable items found in model!")
            return False

        # Get icon from column 0 on same row as current item
        icon = current.sibling(current.row(), 0).data(Qt.DecorationRole)

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(selected))
        drag.setPixmap(icon.pixmap(QSize(self.drag_item_size, self.drag_item_size)))
        drag.setHotSpot(QPoint(self.drag_item_size / 2, self.drag_item_size / 2))
        drag.exec_()

    def refresh_columns(self):
        """Hide certain columns"""
        if type(self) == EffectsTreeView:
            # Only execute when the treeview is active
            self.hideColumn(3)
            self.hideColumn(4)

    def __init__(self, model):
        # Invoke parent init
        QTreeView.__init__(self)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.effects_model = model

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        self.setModel(self.effects_model.proxy_model)

        # Remove the default selection model and wire up to the shared one
        self.selectionModel().deleteLater()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionModel(self.effects_model.selection_model)

        # Setup header columns
        self.setIconSize(QSize(75, 62))
        self.setIndentation(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setStyleSheet('QTreeView::item { padding-top: 2px; }')
        self.effects_model.ModelRefreshed.connect(self.refresh_columns)

        self.refresh_columns()
