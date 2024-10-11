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

from PyQt5.QtCore import QSize, Qt, QPoint, QRegExp
from PyQt5.QtGui import QDrag, QCursor, QPixmap, QPainter, QIcon
from PyQt5.QtWidgets import QListView, QAbstractItemView

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.query import File
from .menu import StyledContextMenu


class FilesListView(QListView):
    """ A ListView QWidget used on the main window """
    drag_item_size = QSize(48, 48)
    drag_item_center = QPoint(24, 24)

    def contextMenuEvent(self, event):
        event.accept()

        # Set context menu mode
        app = get_app()
        _ = app._tr
        app.context_menu_object = "files"

        index = self.indexAt(event.pos())

        # Build menu
        menu = StyledContextMenu(parent=self)

        menu.addAction(self.win.actionImportFiles)
        menu.addAction(self.win.actionDetailsView)

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
                menu.addAction(self.win.actionDuplicate)
                menu.addSeparator()

            menu.addAction(self.win.actionPreview_File)
            menu.addSeparator()
            menu.addAction(self.win.actionSplitFile)
            menu.addAction(self.win.actionExportFiles)
            menu.addSeparator()
            menu.addAction(self.win.actionAdd_to_Timeline)

            # Add Profile menu
            profile_menu = StyledContextMenu(title=_("Choose Profile"), parent=self)
            profile_icon = get_app().window.actionProfile.icon()
            profile_missing_icon = QIcon(":/icons/Humanity/actions/16/list-add.svg")
            profile_menu.setIcon(profile_icon)

            # Get file's profile
            file_profile = file.profile()
            if file_profile.info.description:
                action = profile_menu.addAction(profile_icon, file_profile.info.description)
                action.triggered.connect(lambda: get_app().window.actionProfile_trigger(file_profile))
            else:
                action = profile_menu.addAction(profile_missing_icon, _(f"Create Profile") + f": {file_profile.ShortName()}")
                action.triggered.connect(lambda: get_app().window.actionProfileEdit_trigger(file_profile, duplicate=True))
            menu.addMenu(profile_menu)

            menu.addAction(self.win.actionFile_Properties)
            menu.addSeparator()
            menu.addAction(self.win.actionRemove_from_Project)
            menu.addSeparator()

        # Show menu
        menu.popup(event.globalPos())

    def mouseDoubleClickEvent(self, event):
        super(FilesListView, self).mouseDoubleClickEvent(event)
        # Preview File, File Properties, or Split File (depending on Shift/Ctrl)
        if int(get_app().keyboardModifiers() & Qt.ShiftModifier) > 0:
            get_app().window.actionSplitFile.trigger()
        elif int(get_app().keyboardModifiers() & Qt.ControlModifier) > 0:
            get_app().window.actionFile_Properties.trigger()
        else:
            get_app().window.actionPreview_File.trigger()

    def dragEnterEvent(self, event):
        # If dragging urls onto widget, accept
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        event.accept()
        event.setDropAction(Qt.CopyAction)

    def startDrag(self, supportedActions):
        """ Override startDrag method to display custom icon """

        # Get first column indexes for all selected rows
        selected = self.selectionModel().selectedRows(0)

        # Check if there are any selected items
        if not selected:
            log.warning("No draggable items found in model!")
            return False

        # Get icons from up to 3 selected items
        icons = []
        for i in range(min(3, len(selected))):
            current = selected[i]
            icon = current.sibling(current.row(), 0).data(Qt.DecorationRole)
            if icon:
                icons.append(icon.pixmap(self.drag_item_size))

        # If no icons were retrieved, abort the drag
        if not icons:
            log.warning("No valid icons found for dragging!")
            return False

        # Calculate the total width of the composite pixmap including gaps
        gap = 1  # 1 pixel gap between icons
        total_width = (self.drag_item_size.width() * len(icons)) + (gap * (len(icons) - 1))

        # Create a composite pixmap to hold the icons in a row
        composite_pixmap = QPixmap(total_width, self.drag_item_size.height())
        composite_pixmap.fill(Qt.transparent)  # Start with a transparent background

        # Use a QPainter to draw the icons in a row with 1 pixel gap between them
        painter = QPainter(composite_pixmap)
        for idx, icon_pixmap in enumerate(icons):
            x_offset = idx * (self.drag_item_size.width() + gap)  # Position each icon with a gap
            painter.drawPixmap(int(x_offset), 0, icon_pixmap)
        painter.end()

        # Start the drag operation
        drag = QDrag(self)

        # Combine all selected items into the mime data
        mime_data = self.model().mimeData(selected)
        drag.setMimeData(mime_data)

        # Set the composite pixmap for the drag operation
        drag.setPixmap(composite_pixmap)

        # Set the hot spot to the center of the composite pixmap
        drag.setHotSpot(composite_pixmap.rect().center())

        # Execute the drag operation
        drag.exec_(supportedActions)

    # Without defining this method, the 'copy' action doesn't show with cursor
    def dragMoveEvent(self, event):
        event.accept()

    # Handle a drag and drop being dropped on widget
    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            # Nothing we're interested in
            event.reject()
            return
        event.accept()
        # Use try/finally so we always reset the cursor
        try:
            # Set cursor to waiting
            get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

            qurl_list = event.mimeData().urls()
            log.info("Processing drop event for {} urls".format(len(qurl_list)))
            self.files_model.process_urls(qurl_list)
        finally:
            # Restore cursor
            get_app().restoreOverrideCursor()

    # Pass file add requests to the model
    def add_file(self, filepath):
        self.files_model.add_files(filepath)

    def filter_changed(self):
        self.refresh_view()

    def refresh_view(self):
        """Filter files with proxy class"""
        model = self.model()
        filter_text = self.win.filesFilter.text()
        model.setFilterRegExp(QRegExp(filter_text.replace(' ', '.*'), Qt.CaseInsensitive))

        col = model.sortColumn()
        model.sort(col)

    def resize_contents(self):
        pass

    def __init__(self, model, *args):
        # Invoke parent init
        super().__init__(*args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.files_model = model
        self.setModel(self.files_model.proxy_model)

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
        self.setIconSize(info.LIST_ICON_SIZE)
        self.setGridSize(info.LIST_GRID_SIZE)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)

        self.setUniformItemSizes(True)
        self.setStyleSheet('QListView::item { padding-top: 2px; }')

        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)

        self.files_model.ModelRefreshed.connect(self.refresh_view)

        # setup filter events
        app = get_app()
        app.window.filesFilter.textChanged.connect(self.filter_changed)
