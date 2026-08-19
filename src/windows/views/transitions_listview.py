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

import os

from qt_api import Qt, QSize, QPoint, QPointF
from qt_api import clear_override_cursor
from qt_api import QDrag
from qt_api import QListView, QAbstractItemView

from classes import info
from classes.app import get_app
from classes.logger import log
from .menu import StyledContextMenu, add_bound_action
from .thumbnail_action_overlay import ThumbnailActionViewMixin


class TransitionsListView(ThumbnailActionViewMixin, QListView):
    """ A QListView QWidget used on the main window """
    drag_item_size = QSize(48, 48)
    drag_item_center = QPoint(24, 24)

    def contextMenuEvent(self, event):
        event.accept()

        # Set context menu mode
        app = get_app()
        self.win = app.window
        app.context_menu_object = "transitions"

        menu = StyledContextMenu(parent=self)
        add_bound_action(menu, self.win, "actionDetailsView", app._tr("Details View"), "actionDetailsView_trigger")
        menu.show_at(event)

    def startDrag(self, supportedActions):
        """ Override startDrag method to display custom icon """

        # Get first column indexes for all selected rows
        selected = self.selectionModel().selectedRows(0)

        # Get image of current item
        current = self.selectionModel().currentIndex()
        if not current.isValid() and selected:
            current = selected[0]

        if not current.isValid():
            log.warning("No draggable items found in model!")
            return False

        # Get icon from column 0 on same row as current item
        icon = current.sibling(current.row(), 0).data(Qt.DecorationRole)

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(selected))
        drag.setPixmap(icon.pixmap(self.drag_item_size))
        drag.setHotSpot(self.drag_item_center)
        exec_fn = getattr(drag, "exec", None) or getattr(drag, "exec_", None)
        if exec_fn is None:
            raise AttributeError("QDrag has no exec_/exec method")
        exec_fn()
        clear_override_cursor()

    def filter_changed(self):
        self.refresh_view()

    def refresh_view(self):
        """Filter transitions with proxy class"""
        filter_text = self.win.transitionsFilter.text()
        from qt_api import make_filter_regex, set_proxy_filter
        pattern = filter_text.replace(' ', '.*')
        regex = make_filter_regex(pattern, case_insensitive=True)
        set_proxy_filter(self.transition_model.proxy_model, regex)
        self.transition_model.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.transition_model.proxy_model.sort(0, Qt.AscendingOrder)

    def add_item_to_timeline(self, index):
        """Add the transition at index to the timeline."""
        if not index.isValid():
            log.warning("add_item_to_timeline called with invalid index")
            return

        # Map list_proxy_model -> proxy_model -> source model
        proxy_index = self.transition_model.list_proxy_model.mapToSource(index)
        if not proxy_index or not proxy_index.isValid():
            log.warning("add_item_to_timeline failed to map list_proxy_model index to proxy_index")
            return
        source_index = self.transition_model.proxy_model.mapToSource(proxy_index)
        if not source_index or not source_index.isValid():
            log.warning("add_item_to_timeline failed to map proxy_index to source_index")
            return

        # Column 3 contains the transition file path
        path_item = source_index.sibling(source_index.row(), 3)
        trans_path = path_item.data(Qt.DisplayRole) or path_item.data()
        if not trans_path:
            log.warning("No transition path found for row %s", source_index.row())
            return
        trans_path = os.path.normpath(str(trans_path))

        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            log.warning("No timeline found in window")
            return

        from classes.query import Clip, Transition
        log.info("One-click adding transition '%s' to timeline", trans_path)

        # 1. Determine position (playhead position in seconds)
        pos_seconds = 0.0
        if hasattr(self.win, "_current_timeline_seconds"):
            pos_seconds = self.win._current_timeline_seconds()
        elif hasattr(self.win, "preview_thread"):
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])
            cur_frame = getattr(self.win.preview_thread, "current_frame", None)
            if cur_frame is None and hasattr(self.win.preview_thread, "player") and self.win.preview_thread.player:
                cur_frame = self.win.preview_thread.player.Position()
            if cur_frame:
                pos_seconds = max(0.0, float(cur_frame - 1) / fps_float)

        # 2. Determine target track layer
        track_num = None
        selected_clips = list(getattr(self.win, "selected_clips", []) or [])
        selected_trans = list(getattr(self.win, "selected_transitions", []) or [])
        if selected_clips:
            first_clip = Clip.get(id=selected_clips[0])
            if first_clip and isinstance(first_clip.data, dict):
                track_num = first_clip.data.get("layer")
        elif selected_trans:
            first_tran = Transition.get(id=selected_trans[0])
            if first_tran and isinstance(first_tran.data, dict):
                track_num = first_tran.data.get("layer")

        if track_num is None:
            intersecting_clips = Clip.filter(intersect=pos_seconds)
            if intersecting_clips:
                sorted_clips = sorted(
                    intersecting_clips,
                    key=lambda c: int(c.data.get("layer", 0) if isinstance(c.data, dict) else 0),
                    reverse=True,
                )
                track_num = sorted_clips[0].data.get("layer")

        if track_num is not None:
            try:
                track_num = int(track_num)
            except (TypeError, ValueError):
                track_num = None

        if hasattr(timeline, "_nearest_unlocked_track_number"):
            if track_num is not None:
                track_num = timeline._nearest_unlocked_track_number(track_num)
            if track_num is None and hasattr(timeline, "track_list") and timeline.track_list:
                track_num = timeline._nearest_unlocked_track_number(
                    timeline.track_list[0].data.get("number")
                )

        if track_num is None:
            track_num = 1

        log.info("Adding transition '%s' at position %.2fs on track %s", trans_path, pos_seconds, track_num)

        # 3. Call timeline.addTransition
        item = timeline.addTransition(
            trans_path,
            QPointF(pos_seconds, 0),
            track_num,
            ignore_refresh=False,
            call_manual_move=False,
        )

        # 4. Auto-select added transition
        if item and hasattr(timeline, "_select_added_items"):
            timeline._select_added_items("transition")
        elif item and item.get("id"):
            self.win.addSelection(str(item.get("id")), "transition", clear_existing=True)

        if hasattr(self.win, "statusBar") and self.win.statusBar:
            trans_title = source_index.sibling(source_index.row(), 1).data(Qt.DisplayRole) or "Transition"
            self.win.statusBar.showMessage(get_app()._tr(f"Added {trans_title} transition to timeline"), 3000)

    def __init__(self, model):
        # Invoke parent init
        QListView.__init__(self)

        # Get a reference to the window object
        app = get_app()
        self.win = app.window

        # Get Model data
        self.transition_model = model

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        self.setModel(self.transition_model.list_proxy_model)

        # Remove the default selection model and wire up to the list-specific one
        self.selectionModel().deleteLater()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        if hasattr(self, "setSelectionRectVisible"):
            self.setSelectionRectVisible(False)
        self.setSelectionModel(self.transition_model.list_selection_model)

        # Setup header columns
        self.setIconSize(info.LIST_ICON_SIZE)
        self.setGridSize(info.LIST_GRID_SIZE)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)

        # Initialize thumbnail hover '+' button overlay and mouse tracking
        self.init_thumbnail_action_overlay()

        # setup filter events
        app.window.transitionsFilter.textChanged.connect(self.filter_changed)
        app.window.refreshTransitionsSignal.connect(self.refresh_view)
