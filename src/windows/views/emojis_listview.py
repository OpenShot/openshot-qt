"""
 @file
 @brief This file contains the emojis listview, used by the main window
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

from qt_api import QMimeData, QSize, QPoint, QPointF, Qt, QUrl, pyqtSlot
from qt_api import clear_override_cursor
from qt_api import QDrag, QListView
import openshot  # Python module for libopenshot (required video editing module installed separately)
from classes import info
from classes.query import File
from classes.app import get_app
from classes.logger import log
from .thumbnail_action_overlay import ThumbnailActionViewMixin
import json
import uuid


class EmojisListView(ThumbnailActionViewMixin, QListView):
    """ A QListView QWidget used on the main window """
    drag_item_size = QSize(48, 48)
    drag_item_center = QPoint(24, 24)
    emoji_icon_size = QSize(75, 75)
    emoji_grid_size = QSize(80, 95)

    def dragEnterEvent(self, event):
        # If dragging urls onto widget, accept
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()

    def startDrag(self, event):
        """ Override startDrag method to display custom icon """

        # Get image of selected item
        selected = self.selectedIndexes()

        # Start drag operation
        drag = QDrag(self)
        drag.setMimeData(self.model.mimeData(selected))
        icon = self.model.data(selected[0], Qt.DecorationRole)
        drag.setPixmap(icon.pixmap(self.drag_item_size))
        drag.setHotSpot(self.drag_item_center)

        # Create emoji file before drag starts
        data = json.loads(drag.mimeData().text())

        # Get the translated emoji name from the model item
        # Map through proxy_model -> group_model -> standard model
        group_index = self.model.mapToSource(selected[0])
        source_index = self.group_model.mapToSource(group_index)
        selected_item = self.emojis_model.model.itemFromIndex(source_index)
        emoji_name = selected_item.text() if selected_item else None

        # Start a transaction so File + Clip are grouped for undo
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid
        try:
            file = self.add_file(data[0], emoji_name)
            if not file:
                log.warning("Failed to add emoji file for drag: %s", data[0])
                return

            # Update mimedata for emoji
            data = QMimeData()
            data.setText(json.dumps([file.id]))
            data.setHtml("clip")
            try:
                data.setUrls([QUrl.fromLocalFile(file.absolute_path())])
            except Exception:
                file_path = file.data.get("path")
                if file_path:
                    data.setUrls([QUrl.fromLocalFile(file_path)])
            drag.setMimeData(data)

            # Start drag
            exec_fn = getattr(drag, "exec", None) or getattr(drag, "exec_", None)
            if exec_fn is None:
                raise AttributeError("QDrag has no exec_/exec method")
            exec_fn()
            clear_override_cursor()
        finally:
            # End transaction
            get_app().updates.transaction_id = None

    def add_file(self, filepath, emoji_name=None):
        # Add file into project

        app = get_app()
        _ = app._tr

        # Check for this path in our existing project data
        # ["1F595-1F3FE",
        # "openshot-qt-git/src/emojis/color/svg/1F595-1F3FE.svg"]
        file = File.get(path=filepath)

        # If this file is already found, exit
        if file:
            return file

        # Load filepath in libopenshot clip object (which will try multiple readers to open it)
        clip = openshot.Clip(filepath)

        # Get the JSON for the clip's internal reader
        try:
            reader = clip.Reader()
            file_data = json.loads(reader.Json())

            # Determine media type
            file_data["media_type"] = "image"

            # Set friendly emoji name (translated)
            if emoji_name:
                file_data["name"] = emoji_name

            # Save new file to the project data
            file = File()
            file.data = file_data
            file.save()
            return file

        except Exception as ex:
            # Log exception
            log.warning("Failed to import file: {}".format(str(ex)))


    def filter_changed(self, text):
        self.emojis_model.set_text_filter(text)

    def group_changed(self, index):
        group_id = self.win.emojiFilterGroup.itemData(index)
        self.emojis_model.set_group_filter(group_id or "")
        s = get_app().get_settings()
        if s.get("emoji_group_filter") != group_id:
            s.set("emoji_group_filter", group_id)

    def refresh_view(self):
        """Filter emojis with proxy class"""

        col = self.model.sortColumn()
        self.model.sort(col)

    def resize_contents(self):
        pass

    @pyqtSlot()
    def clicked(self, index):
        """If any emoji clicked, set that emoji on the project"""
        # Get selected emoji file_path
        index = index.sibling(index.row(), 5)
        file_path = self.model.data(index, Qt.DisplayRole)

        # Add emoji to project (after checking if not found in project)
        if file_path not in info.EMOJI_FILES:
            self.add_file(file_path)

        # Set emoji file in preferences (displayed on project actions)
        info.PREFERENCES.set("emoji", file_path)
        info.EMOJI_PATH = file_path
        info.EMOJI_ICON = file_path

    def add_item_to_timeline(self, index):
        """Add the emoji at index as a clip to the timeline."""
        if not index or not index.isValid():
            log.warning("add_item_to_timeline called with invalid index")
            return

        from .thumbnail_action_overlay import to_qmodelindex
        index = to_qmodelindex(index)

        # Map through proxy_model -> group_model -> standard model
        group_index = self.model.mapToSource(index)
        if not group_index or not group_index.isValid():
            log.warning("Failed to map index to group_index in EmojisListView")
            return
        source_index = self.group_model.mapToSource(group_index)
        if not source_index or not source_index.isValid():
            log.warning("Failed to map group_index to source_index in EmojisListView")
            return

        selected_item = self.emojis_model.model.itemFromIndex(source_index)
        emoji_name = selected_item.text() if selected_item else "Emoji"
        emoji_path = selected_item.data() if selected_item else None
        if not emoji_path:
            emoji_path = source_index.data(Qt.UserRole + 1)
        if not emoji_path:
            log.warning("No emoji path found for index %s", index.row())
            return

        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            log.warning("No timeline found in window")
            return

        from classes.query import Clip, Transition
        log.info("One-click adding emoji '%s' (%s) to timeline", emoji_name, emoji_path)

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

        log.info("Adding emoji '%s' clip at position %.2fs on track %s", emoji_name, pos_seconds, track_num)

        # 3. Create File + Clip wrapped in a transaction for undo
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid
        try:
            file = self.add_file(emoji_path, emoji_name)
            if not file:
                log.warning("Failed to add emoji file: %s", emoji_path)
                return

            clip = timeline.addClip(
                file.id,
                QPointF(pos_seconds, 0),
                track_num,
                ignore_refresh=False,
                call_manual_move=False,
                auto_transition=False,
            )

            # Auto-select added emoji clip
            if clip and hasattr(timeline, "_select_added_items"):
                timeline._select_added_items("clip")
            elif clip and clip.get("id"):
                self.win.addSelection(str(clip.get("id")), "clip", clear_existing=True)

            if hasattr(self.win, "statusBar") and self.win.statusBar:
                self.win.statusBar.showMessage(get_app()._tr(f"Added {emoji_name} to timeline"), 3000)
        finally:
            get_app().updates.transaction_id = None

    def __init__(self, model, *args):
        # Invoke parent init
        super().__init__(*args)

        # Get a reference to the window object
        self.win = get_app().window

        # Set model (expects a proxy model)
        self.emojis_model = model
        self.group_model = self.emojis_model.group_model
        self.model = self.emojis_model.proxy_model
        self.setModel(self.model)

        # Configure selection behavior
        self.setSelectionMode(QListView.SingleSelection)
        self.setSelectionBehavior(QListView.SelectRows)
        if hasattr(self, "setSelectionRectVisible"):
            self.setSelectionRectVisible(False)

        # Keep track of mouse press start position to determine when to start drag
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # Setup header columns and layout
        self.setIconSize(self.emoji_icon_size)
        self.setGridSize(self.emoji_grid_size)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)

        # Initialize thumbnail hover '+' button overlay and mouse tracking
        self.init_thumbnail_action_overlay()

        self.emojis_model.ModelRefreshed.connect(self.refresh_view)
        # Activate filter and group selection
        _ = get_app()._tr
        self.win.emojisFilter.textChanged.connect(self.filter_changed)
        s = get_app().get_settings()
        default_group_id = s.get("emoji_group_filter") or "smileys-emotion"
        dropdown_index = 0
        self.win.emojiFilterGroup.clear()
        self.win.emojiFilterGroup.addItem(_("All"), "")
        for index, (name, group_id) in enumerate(sorted(self.emojis_model.emoji_groups, key=lambda g: g[0])):
            self.win.emojiFilterGroup.addItem(name, group_id)
            if group_id == default_group_id:
                dropdown_index = index + 1
        self.win.emojiFilterGroup.currentIndexChanged.connect(self.group_changed)
        self.win.emojiFilterGroup.setCurrentIndex(dropdown_index)
