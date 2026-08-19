"""
 @file
 @brief This file contains the effects file listview, used by the main window
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

from qt_api import QSize, QPoint, Qt
from qt_api import clear_override_cursor
from qt_api import QDrag
from qt_api import QListView, QAbstractItemView

from classes import info
from classes.app import get_app
from classes.logger import log
from .menu import StyledContextMenu, add_bound_action
from .thumbnail_action_overlay import ThumbnailActionViewMixin


class EffectsListView(ThumbnailActionViewMixin, QListView):
    """ A TreeView QWidget used on the main window """
    drag_item_size = QSize(48, 48)
    drag_item_center = QPoint(24, 24)

    def contextMenuEvent(self, event):
        # Set context menu mode
        app = get_app()
        self.win = app.window
        app.context_menu_object = "effects"

        menu = StyledContextMenu(parent=self)
        add_bound_action(menu, self.win, "actionDetailsView", app._tr("Details View"), "actionDetailsView_trigger")
        menu.show_at(event)

    def startDrag(self, event):
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
        filter_text = self.win.effectsFilter.text()
        from qt_api import make_filter_regex, set_proxy_filter
        pattern = filter_text.replace(' ', '.*')
        regex = make_filter_regex(pattern, case_insensitive=True)
        set_proxy_filter(self.effects_model.proxy_model, regex)
        self.effects_model.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.effects_model.proxy_model.sort(0, Qt.AscendingOrder)

    def add_item_to_timeline(self, index):
        """Add the effect at index to the timeline."""
        if not index.isValid():
            log.warning("add_item_to_timeline called with invalid index")
            return

        # Map list_proxy_model -> proxy_model -> source model
        proxy_index = self.effects_model.list_proxy_model.mapToSource(index)
        if not proxy_index or not proxy_index.isValid():
            log.warning("add_item_to_timeline failed to map list_proxy_model index to proxy_index")
            return
        source_index = self.effects_model.proxy_model.mapToSource(proxy_index)
        if not source_index or not source_index.isValid():
            log.warning("add_item_to_timeline failed to map proxy_index to source_index")
            return

        # Column 4 contains the effect class_name (e.g. "Blur", "Color")
        effect_name_item = source_index.sibling(source_index.row(), 4)
        effect_name = effect_name_item.data(Qt.DisplayRole) or effect_name_item.data()
        if not effect_name:
            log.warning("No effect name found for row %s", source_index.row())
            return

        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            log.warning("No timeline found in window")
            return

        from classes.query import Clip
        log.info("One-click adding effect '%s' to timeline", effect_name)

        # 1. If clips are selected on the timeline, apply effect to each selected clip
        selected_clip_ids = list(getattr(self.win, "selected_clips", []) or [])
        applied = False
        if selected_clip_ids:
            log.info("Applying effect '%s' to %d selected clips: %s", effect_name, len(selected_clip_ids), selected_clip_ids)
            for clip_id in selected_clip_ids:
                clip = Clip.get(id=clip_id)
                if clip:
                    timeline._apply_effect_to_clip(clip, effect_name)
                    applied = True
            if applied and hasattr(self.win, "statusBar") and self.win.statusBar:
                self.win.statusBar.showMessage(get_app()._tr(f"Applied {effect_name} effect to selected clip(s)"), 3000)
            return

        # 2. Check for clips under the current playhead position
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

        intersecting_clips = Clip.filter(intersect=pos_seconds)
        if intersecting_clips:
            # Sort by layer descending so the top-most visual clip is targeted
            sorted_clips = sorted(
                intersecting_clips,
                key=lambda c: int(c.data.get("layer", 0) if isinstance(c.data, dict) else 0),
                reverse=True,
            )
            target_clip = sorted_clips[0]
            log.info("Applying effect '%s' to clip under playhead (id=%s, layer=%s)", effect_name, target_clip.id, target_clip.data.get("layer"))
            timeline._apply_effect_to_clip(target_clip, effect_name)
            if hasattr(self.win, "statusBar") and self.win.statusBar:
                self.win.statusBar.showMessage(get_app()._tr(f"Applied {effect_name} effect to clip"), 3000)
            return

        # 3. Fallback: if no clip at playhead, find the nearest clip on the timeline
        all_clips = Clip.filter()
        if all_clips:
            def clip_dist(c):
                data = c.data if isinstance(c.data, dict) else {}
                c_pos = float(data.get("position", 0.0) or 0.0)
                c_start = float(data.get("start", 0.0) or 0.0)
                c_end = float(data.get("end", c_start) or c_start)
                c_finish = c_pos + (c_end - c_start)
                if c_pos <= pos_seconds <= c_finish:
                    return 0.0
                return min(abs(pos_seconds - c_pos), abs(pos_seconds - c_finish))

            nearest_clip = min(all_clips, key=clip_dist)
            log.info("Applying effect '%s' to nearest clip on timeline (id=%s, layer=%s)", effect_name, nearest_clip.id, nearest_clip.data.get("layer"))
            timeline._apply_effect_to_clip(nearest_clip, effect_name)
            if hasattr(self.win, "statusBar") and self.win.statusBar:
                self.win.statusBar.showMessage(get_app()._tr(f"Applied {effect_name} effect to clip"), 3000)
            return

        log.warning("Cannot add effect '%s': No clips found on timeline. Add a clip first.", effect_name)
        if hasattr(self.win, "statusBar") and self.win.statusBar:
            self.win.statusBar.showMessage(get_app()._tr("Please add a clip to the timeline before applying effects"), 4000)

    def __init__(self, model):
        # Invoke parent init
        QListView.__init__(self)

        # Get a reference to the window object
        app = get_app()
        self.win = app.window

        # Get Model data
        self.effects_model = model

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        self.setModel(self.effects_model.list_proxy_model)

        # Remove the default selection model and wire up to the list-specific one
        self.selectionModel().deleteLater()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        if hasattr(self, "setSelectionRectVisible"):
            self.setSelectionRectVisible(False)
        self.setSelectionModel(self.effects_model.list_selection_model)

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
        app.window.effectsFilter.textChanged.connect(self.filter_changed)
        app.window.refreshEffectsSignal.connect(self.refresh_view)
