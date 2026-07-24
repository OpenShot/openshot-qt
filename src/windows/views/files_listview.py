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
import uuid

from qt_api import QSize, Qt, QPoint
from qt_api import clear_override_cursor
from qt_api import modifiers_has
from qt_api import QDrag, QCursor, QPixmap, QPainter, QIcon, QColor, QFontMetrics
from qt_api import (
    QListView, QAbstractItemView, QItemSelectionModel,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
)

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.query import File
from classes.qt_types import font_metrics_horizontal_advance
from .ai_tools_menu import add_ai_tools_menu
from .files_thumbnail_overlay import paint_media_overlay, paint_proxy_badge, paint_meta_badges
from .menu import StyledContextMenu, add_bound_action
from .optimized_preview_menu import add_optimized_preview_menu


def _is_generation_placeholder(file_id):
    return str(file_id or "").startswith("__genjob__:")


def _job_id_from_placeholder(file_id):
    file_id = str(file_id or "")
    if not _is_generation_placeholder(file_id):
        return None
    return file_id.split(":", 1)[1]


class FilesListProgressDelegate(QStyledItemDelegate):
    """Paint a thin progress line over list-view thumbnails."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        # list_proxy_model index -> proxy_model index -> source model index
        proxy_index = self.view.files_model.list_proxy_model.mapToSource(index)
        if not proxy_index or not proxy_index.isValid():
            return
        source_index = self.view.files_model.proxy_model.mapToSource(proxy_index)
        if not source_index or not source_index.isValid():
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else self.view.style()
        deco_rect = style.subElementRect(QStyle.SE_ItemViewItemDecoration, opt, opt.widget)
        if not deco_rect.isValid():
            return

        state_mouse_over = getattr(QStyle, "State_MouseOver", None)
        if state_mouse_over is None:
            state_flag = getattr(QStyle, "StateFlag", None)
            state_mouse_over = getattr(state_flag, "State_MouseOver", None) if state_flag else None
        hovered = bool(state_mouse_over and (option.state & state_mouse_over))

        media_type = source_index.sibling(source_index.row(), 3).data(Qt.DisplayRole)
        paint_media_overlay(painter, deco_rect, media_type, hovered=hovered)

        file_id = source_index.sibling(source_index.row(), 5).data(Qt.DisplayRole)

        file_obj2 = File.get(id=file_id) if (file_id and not _is_generation_placeholder(file_id)) else None
        if file_obj2:
            paint_meta_badges(
                painter, deco_rect, media_type,
                duration=float(file_obj2.data.get("duration", 0) or 0),
                width=int(file_obj2.data.get("width", 0) or 0),
                height=int(file_obj2.data.get("height", 0) or 0),
                hovered=hovered)

        queue = getattr(self.view.win, "generation_queue", None)
        generation_badge = None
        if file_id and queue:
            generation_badge = queue.get_file_badge(file_id)
            if not generation_badge and _is_generation_placeholder(file_id):
                job = queue.get_job(_job_id_from_placeholder(file_id))
                if job and job.get("status") in ("queued", "running", "canceling"):
                    label = "Queued" if job.get("status") == "queued" else "Generating"
                    generation_badge = {
                        "status": job.get("status"),
                        "progress": int(job.get("progress", 0)),
                        "label": label,
                        "job_id": job.get("id"),
                    }

        proxy_badge = None
        proxy_service = getattr(self.view.win, "proxy_service", None)
        if file_id and proxy_service and not _is_generation_placeholder(file_id):
            proxy_badge = proxy_service.get_file_badge(file_id)
            file_obj = File.get(id=file_id)
            if file_obj:
                paint_proxy_badge(painter, deco_rect, proxy_service.get_proxy_state(file_obj))

        self._paint_progress_bar(painter, deco_rect, generation_badge, QColor("#53A0ED"), 0)
        self._paint_progress_bar(painter, deco_rect, proxy_badge, QColor("#3AA1FF"), 1)

    def _paint_progress_bar(self, painter, deco_rect, badge, fill_color, stack_index):
        if not badge:
            return

        progress = int(badge.get("progress", 0))
        status = str(badge.get("status", "")).strip().lower()
        if status in ("queued", "running", "canceling"):
            progress = max(progress, 2)
        if progress <= 0:
            return

        bar_height = 3
        bar_margin = 2
        bottom_offset = (bar_height + 1) * int(stack_index)
        full_rect = deco_rect.adjusted(1, 0, -1, 0)
        full_rect.setTop(deco_rect.bottom() - bar_height - bar_margin - bottom_offset + 1)
        full_rect.setHeight(bar_height)
        if full_rect.width() <= 2:
            return

        fill_width = max(1, int((full_rect.width() * min(progress, 100)) / 100.0))
        fill_rect = full_rect.adjusted(0, 0, -(full_rect.width() - fill_width), 0)

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#283241"))
        painter.drawRect(full_rect)
        painter.setBrush(fill_color)
        painter.drawRect(fill_rect)
        if status == "queued":
            label = "Queued"
            fm = QFontMetrics(painter.font())
            text_w = font_metrics_horizontal_advance(fm, label)
            text_h = fm.height()
            pad_x = 5
            pad_y = 2
            badge_w = text_w + (pad_x * 2)
            badge_h = text_h + (pad_y * 2)
            badge_bottom = full_rect.top() - 3
            badge_top = max(deco_rect.top() + 3, badge_bottom - badge_h + 1)
            badge_rect = deco_rect.adjusted(3, badge_top - deco_rect.top(), 0, 0)
            badge_rect.setWidth(badge_w)
            badge_rect.setHeight(badge_h)
            painter.setBrush(QColor(18, 22, 30, 220))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QColor("#EAF5FF"))
            painter.drawText(badge_rect, Qt.AlignCenter, label)
        painter.restore()


class FilesListView(QListView):
    """ A ListView QWidget used on the main window """
    drag_item_size = QSize(48, 48)
    drag_item_center = QPoint(24, 24)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model() and self.model().rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor("#8B95A5"))
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)
            text = "Drag media here or press ⌘I" if os.name == 'posix' else "Drag media here or press Ctrl+I"
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, text)

    def contextMenuEvent(self, event):
        event.accept()

        # Set context menu mode
        app = get_app()
        self.win = app.window
        _ = app._tr
        app.context_menu_object = "files"

        index = self.indexAt(event.pos())
        if not index.isValid():
            self.clearSelection()
        else:
            self.selectionModel().setCurrentIndex(index, QItemSelectionModel.NoUpdate)

        # Build menu
        menu = StyledContextMenu(parent=self)

        add_bound_action(menu, self.win, "actionImportFiles", _("Import Files..."), "actionImportFiles_trigger")

        source_file = None

        active_job = None
        file_id = None
        if index.isValid():
            model = self.model()
            source_index = model.mapToSource(index)
            id_index = source_index.sibling(source_index.row(), 5)
            file_id = model.sourceModel().data(id_index, Qt.DisplayRole)
            if _is_generation_placeholder(file_id):
                job_id = _job_id_from_placeholder(file_id)
                queue = getattr(self.win, "generation_queue", None)
                active_job = queue.get_job(job_id) if queue else None
                if active_job and active_job.get("status") not in ("queued", "running", "canceling"):
                    active_job = None
            else:
                active_job = self.win.active_generation_job_for_file(file_id)
                source_file = File.get(id=file_id)
        add_ai_tools_menu(self.win, menu, source_file=source_file)

        if not active_job:
            self.win.actionGenerate.setEnabled(self.win.can_open_generate_dialog())
        if active_job:
            cancel_action = menu.addAction(_("Cancel Job"))
            delete_icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", "track-delete-enabled.svg")
            if os.path.exists(delete_icon_path):
                cancel_action.setIcon(QIcon(delete_icon_path))
            else:
                cancel_action.setIcon(self.win.actionRemove_from_Project.icon())
            cancel_action.triggered.connect(
                lambda checked=False, job_id=active_job.get("id"): self.win.cancel_generation_job(job_id)
            )
        menu.addSeparator()
        add_bound_action(menu, self.win, "actionDetailsView", _("Details View"), "actionDetailsView_trigger")

        if index.isValid():
            # Look up the model item and our unique ID
            model = self.model()
            source_index = model.mapToSource(index)

            # Look up file_id from 5th column of row
            id_index = source_index.sibling(source_index.row(), 5)
            file_id = model.sourceModel().data(id_index, Qt.DisplayRole)

            # If a valid file selected, show file related options
            menu.addSeparator()

            # Add edit title option (if svg file)
            file = File.get(id=file_id)
            if not file:
                menu.popup(event.globalPos())
                return
            if file and file.data.get("path").endswith(".svg"):
                add_bound_action(menu, self.win, "actionEditTitle", _("Edit Title"), "actionEditTitle_trigger")
                add_bound_action(menu, self.win, "actionDuplicate", _("Duplicate"), "actionDuplicate_trigger")
                menu.addSeparator()

            add_bound_action(menu, self.win, "actionPreview_File", _("Preview File"), "actionPreview_File_trigger")
            add_optimized_preview_menu(self.win, menu)
            menu.addSeparator()
            add_bound_action(menu, self.win, "actionSplitFile", _("Split Clip"), "actionSplitFile_trigger")
            add_bound_action(menu, self.win, "actionExportFiles", _("Export Selected Clips"), "actionExportFiles_trigger")
            menu.addSeparator()
            add_bound_action(menu, self.win, "actionAdd_to_Timeline", _("Add to Timeline"), "actionAdd_to_Timeline_trigger")

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

            add_bound_action(menu, self.win, "actionFile_Properties", _("File Properties"), "actionFile_Properties_trigger")
            menu.addSeparator()
            add_bound_action(menu, self.win, "actionRemove_from_Project", _("Remove from Project"), "actionRemove_from_Project_trigger")
            menu.addSeparator()

        # Show menu
        menu.show_at(event)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid() and event.button() in (Qt.LeftButton, Qt.RightButton):
            self.clearSelection()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        super(FilesListView, self).mouseDoubleClickEvent(event)
        index = self.indexAt(event.pos())
        if index.isValid():
            self.setCurrentIndex(index)
            self.selectionModel().select(
                index,
                QItemSelectionModel.ClearAndSelect,
            )
        # Preview File, File Properties, or Split File (depending on Shift/Ctrl)
        if modifiers_has(get_app().keyboardModifiers(), Qt.ShiftModifier):
            get_app().window.actionSplitFile.trigger()
        elif modifiers_has(get_app().keyboardModifiers(), Qt.ControlModifier):
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
        selected = [
            idx for idx in selected
            if not _is_generation_placeholder(
                self.model().sourceModel().data(self.model().mapToSource(idx).sibling(self.model().mapToSource(idx).row(), 5), Qt.DisplayRole)
            )
        ]

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

        # Start a transaction so all clips are grouped for a single undo
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid

        # Execute the drag operation
        exec_fn = getattr(drag, "exec", None) or getattr(drag, "exec_", None)
        if exec_fn is None:
            raise AttributeError("QDrag has no exec_/exec method")
        exec_fn(supportedActions)
        clear_override_cursor()

        # End transaction
        get_app().updates.transaction_id = None

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
        filter_text = self.win.filesFilter.text()
        # Apply filter to the source proxy model (not the single-column wrapper)
        from qt_api import make_filter_regex, set_proxy_filter
        pattern = filter_text.replace(' ', '.*')
        regex = make_filter_regex(pattern, case_insensitive=True)
        set_proxy_filter(self.files_model.proxy_model, regex)

        col = self.files_model.proxy_model.sortColumn()
        if col >= 0:
            self.files_model.proxy_model.sort(col)

    def resize_contents(self):
        pass

    def __init__(self, model, *args):
        # Invoke parent init
        super().__init__(*args)

        # Get a reference to the window object
        app = get_app()
        self.win = app.window

        # Get Model data
        self.files_model = model
        self.setModel(self.files_model.list_proxy_model)

        # Remove the default selection model and wire up to the list-specific one
        self.selectionModel().deleteLater()
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionModel(self.files_model.list_selection_model)
        self.setItemDelegate(FilesListProgressDelegate(self))

        # Enable passive hover tracking so thumbnail overlays can react to mouse-over
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns and layout
        self.setModelColumn(0)  # Only display first column in icon mode
        self.setIconSize(info.LIST_ICON_SIZE)
        self.setGridSize(info.LIST_GRID_SIZE)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)

        self.setUniformItemSizes(True)

        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)

        self.files_model.ModelRefreshed.connect(self.refresh_view)

        # setup filter events
        app = get_app()
        app.window.filesFilter.textChanged.connect(self.filter_changed)
