"""
 @file
 @brief This file contains the project file listview, used by the main window
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

from PyQt5.QtCore import QSize, Qt, QPoint, QRegExp
from PyQt5.QtGui import QDrag, QCursor
from PyQt5.QtWidgets import QListView, QAbstractItemView, QMenu, QActionGroup

from classes import settings
from classes.app import get_app
from classes.logger import log
from classes.query import File


class FilesListView(QListView):
    """ A ListView QWidget used on the main window """
    drag_item_size = 48

    def contextMenuEvent(self, event):

        # Set context menu mode
        app = get_app()
        app.context_menu_object = "files"

        index = self.indexAt(event.pos())

        # Get translation function
        _ = get_app()._tr

        # Build menu
        menu = QMenu(self)

        menu.addAction(self.win.actionImportFiles)
        menu.addAction(self.win.actionDetailsView)

        # Sub-menu
        menu.addSeparator()
        sort_menu = QMenu(_("Sort by"), menu)

        # -1 - Unsorted (from original model)
        #  1 - Name
        #  2 - Tags
        #  3 - Type
        #  4 - Path
        #  5 - ID

        all_sorting = [
                        _("Unsorted"),
                        _("Name"),
                        _("Tags"),
                        _("Type"),
                        _("Path"),
                        _("ID")
                    ]

        # Exclusive group
        sorting_type_group = QActionGroup(menu)

        # Update sorting
        self.read_sorting_settings()

        sort_option = None
        for i, sort_by in enumerate(all_sorting):
            sort_option = sort_menu.addAction(sort_by)
            sort_option.setCheckable(True)
            # Store option number inside the action itself
            # Python handles the QVariant conversion here
            if i == 0:
                sort_option.setData(-1)
                if self.sort_column == -1:
                    sort_option.setChecked(True)
            else:
                sort_option.setData(i)
                if self.sort_column == i:
                    sort_option.setChecked(True)

            # Add each to exclusive group
            sort_option.setActionGroup(sorting_type_group)

        # Use menu triggered signal for closely related actions, it carries pointer to the action
        sort_menu.triggered.connect(self.update_sorting)
        menu.addMenu(sort_menu)
        menu.addSeparator()
        menu.addAction
        sort_up = menu.addAction( _("Ascending") )
        sort_down = menu.addAction( _("Descending") )

        sort_down.setCheckable(True)
        sort_up.setCheckable(True)

        # Exclusive group
        sorting_order_group = QActionGroup(menu)
        sort_up.setActionGroup(sorting_order_group)
        sort_down.setActionGroup(sorting_order_group)

        if self.sort_order == Qt.AscendingOrder:
            sort_up.setChecked(True)
        else:
            sort_down.setChecked(True)

        sort_up.toggled.connect(self.sort_ascending)
        sort_down.toggled.connect(self.sort_descending)

        if index.isValid():
            # Look up the model item and our unique ID
            model = self.model()

            # Look up file_id from 5th column of row
            id_index = index.sibling(index.row(), 5)
            file_id = model.data(id_index, Qt.DisplayRole)

            # If a valid file selected, show file related options
            menu.addSeparator()

            # Add edit title option (if svg file)
            file = File.get(id=file_id)
            if file and file.data.get("path").endswith(".svg"):
                menu.addAction(self.win.actionEditTitle)
                menu.addAction(self.win.actionDuplicateTitle)
                menu.addSeparator()

            menu.addAction(self.win.actionPreview_File)
            menu.addAction(self.win.actionSplitClip)
            menu.addAction(self.win.actionAdd_to_Timeline)
            menu.addAction(self.win.actionFile_Properties)
            menu.addSeparator()
            menu.addAction(self.win.actionRemove_from_Project)
            menu.addSeparator()

        # Show menu
        menu.exec_(event.globalPos())

        # The menu may be closed without action taken, thus disconnect old signals
        sort_menu.triggered.disconnect(self.update_sorting)
        sort_up.toggled.disconnect(self.sort_ascending)
        sort_down.toggled.disconnect(self.sort_descending)

    def dragEnterEvent(self, event):
        # If dragging urls onto widget, accept
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()

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

    # Without defining this method, the 'copy' action doesn't show with cursor
    def dragMoveEvent(self, event):
        pass

    # Handle a drag and drop being dropped on widget
    def dropEvent(self, event):
        # Set cursor to waiting
        get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

        media_paths = []
        for uri in event.mimeData().urls():
            log.info('Processing drop event for {}'.format(uri))
            filepath = uri.toLocalFile()
            if os.path.exists(filepath) and os.path.isfile(filepath):
                log.info('Adding file: {}'.format(filepath))
                if ".osp" in filepath:
                    # Auto load project passed as argument
                    self.win.OpenProjectSignal.emit(filepath)
                    event.accept()
                else:
                    media_paths.append(filepath)

        # Import all new media files
        if media_paths and self.files_model.add_files(media_paths):
            event.accept()

        # Restore cursor
        get_app().restoreOverrideCursor()

    # Pass file add requests to the model
    def add_file(self, filepath):
        self.files_model.add_files(filepath)

    def filter_changed(self):
        self.refresh_view()

    def sort_ascending(self, checked=False):
        if checked:
            self.sort_order = Qt.AscendingOrder

            # Save sorting order
            s = settings.get_settings()
            s.set("files_view_sorting_order", 0)

            self.apply_items_sorting()

    def sort_descending(self, checked=False):
        if checked:
            self.sort_order = Qt.DescendingOrder

            # Save sorting order
            s = settings.get_settings()
            s.set("files_view_sorting_order", 1)

            self.apply_items_sorting()

    def update_sorting(self, action):
        # Column:
        # -1 - Unsorted (from original model)
        #  1 - Name
        #  2 - Tags
        #  3 - Type
        #  4 - Path
        #  5 - ID

        # Get what sorting was triggered
        self.sort_column = action.data()

        # Save sorting
        s = settings.get_settings()
        s.set("files_view_sorting", self.sort_column)

        self.apply_items_sorting()

    def apply_items_sorting(self):
        self.model().sort(self.sort_column, self.sort_order)

    def refresh_view(self):
        """Filter files with proxy class"""
        model = self.model()
        filter_text = self.win.filesFilter.text()
        model.setFilterRegExp(QRegExp(filter_text.replace(' ', '.*'), Qt.CaseInsensitive))

        # Update sorting
        self.read_sorting_settings()
        self.apply_items_sorting()

    def resize_contents(self):
        pass

    def read_sorting_settings(self):
        # Get sorting settings
        s = settings.get_settings()
        order = s.get("files_view_sorting_order")
        self.sort_order = Qt.AscendingOrder
        if order == 1:
            self.sort_order = Qt.DescendingOrder

        # Column from the files model to sort by (-1 is unsorted)
        self.sort_column = s.get("files_view_sorting")

    def __init__(self, model, *args):
        # Invoke parent init
        super().__init__(*args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.files_model = model
        self.setModel(self.files_model.proxy_model)

        # Get sorting settings
        self.sort_order = Qt.AscendingOrder
        self.sort_column = -1
        self.read_sorting_settings()

        # Remove the default selection model and wire up to the shared one
        self.selectionModel().deleteLater()
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionModel(self.files_model.selection_model)

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns and layout
        self.setIconSize(QSize(131, 108))
        self.setGridSize(QSize(102, 92))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)

        self.setUniformItemSizes(True)
        self.setStyleSheet('QListView::item { padding-top: 2px; }')

        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)

        self.files_model.ModelRefreshed.connect(self.refresh_view)

        # Load initial files model data
        self.files_model.update_model()

        # setup filter events
        app = get_app()
        app.window.filesFilter.textChanged.connect(self.filter_changed)
        app.window.refreshFilesSignal.connect(self.refresh_view)
