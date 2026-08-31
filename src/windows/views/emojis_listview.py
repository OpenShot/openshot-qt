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

from qt_api import QMimeData, QSize, QPoint, Qt, QUrl, pyqtSlot
from qt_api import clear_override_cursor
from qt_api import QDrag, QListView
import openshot  # Python module for libopenshot (required video editing module installed separately)
from classes import info
from classes.query import File
from classes.app import get_app
from classes.logger import log
import json
import os
import uuid


def builtin_emoji_reader_data(filepath):
    """Return reader metadata for a bundled 72x72 OpenMoji SVG."""
    emoji_root = os.path.realpath(
        os.path.join(info.PATH, "emojis", "color", "svg")
    )
    resolved_path = os.path.realpath(filepath)
    try:
        is_bundled = os.path.commonpath(
            (emoji_root, resolved_path)
        ) == emoji_root
    except ValueError:
        is_bundled = False
    if not is_bundled or not resolved_path.lower().endswith(".svg"):
        return None

    return {
        "acodec": "",
        "audio_bit_rate": 0,
        "audio_stream_index": -1,
        "audio_timebase": {"den": 1, "num": 1},
        "channel_layout": openshot.LAYOUT_MONO,
        "channels": 0,
        "display_ratio": {"den": 1, "num": 1},
        "duration": 3600.0,
        "file_size": os.path.getsize(resolved_path),
        "fps": {"den": 1, "num": 30},
        "has_audio": False,
        "has_single_image": True,
        "has_video": True,
        "height": 72,
        "interlaced_frame": False,
        "metadata": {},
        "path": resolved_path,
        "pixel_format": -1,
        "pixel_ratio": {"den": 1, "num": 1},
        "sample_rate": 0,
        "top_field_first": True,
        "type": "QtImageReader",
        "vcodec": "",
        "video_bit_rate": 0,
        "video_length": 108000,
        "video_stream_index": -1,
        "video_timebase": {"den": 30, "num": 1},
        "width": 72,
    }


class EmojisListView(QListView):
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

        try:
            # Bundled OpenMoji SVGs are standardized 72x72 single images.
            # Avoid synchronously parsing the SVG through the full libopenshot
            # reader stack before QDrag.exec(), which causes a cold-start hitch.
            file_data = builtin_emoji_reader_data(filepath)
            if file_data is None:
                # User-supplied emoji assets still require normal inspection.
                clip = openshot.Clip(filepath)
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
