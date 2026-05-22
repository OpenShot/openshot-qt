"""
 @file
 @brief This file contains the project file model, used by the project tree
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
import json
import re
import glob
import functools
import uuid

from qt_api import (
    QMimeData, Qt, QUrl, pyqtSignal, QEventLoop, QObject,
    QSortFilterProxyModel, QItemSelectionModel, QItemSelection, QPersistentModelIndex, QModelIndex
)
from qt_api import (
    QIcon, QPixmap, QStandardItem, QStandardItemModel
)
from qt_api import QAbstractItemView
from classes import updates
from classes import info
from classes.image_types import get_media_type
from classes.query import File
from classes.logger import log
from classes.app import get_app
from classes.thumbnail import GetThumbPath
from classes.qt_types import model_index_sibling_at_column

import openshot


IMPORT_READER_MAX_SIZE = 128


def inspect_media(path, max_width=0, max_height=0):
    """Inspect media using the shared libopenshot reader-selection logic.

    The max-size arguments are kept for API compatibility with older callers,
    but are intentionally not applied during metadata inspection. Applying a
    decode-size cap here can cause libopenshot to report preview dimensions in
    reader.Json(), which then stores imported 1080p media as a tiny clip.
    """
    def _inspect_with_reader(inspect_reader):
        reader = openshot.Clip.CreateReader(path, inspect_reader)
        if not reader:
            raise RuntimeError(f"No reader available for path: {path}")

        reader.Open()
        try:
            return json.loads(reader.Json()), float(reader.info.duration or 0.0)
        finally:
            reader.Close()

    try:
        return _inspect_with_reader(False)
    except Exception:
        # Retry with eager inspection so libopenshot can reject an incorrect
        # lightweight reader choice during construction and fall back to the
        # next candidate (for example, unknown-but-supported FFmpeg formats).
        return _inspect_with_reader(True)


class SingleColumnProxyModel(QSortFilterProxyModel):
    """Proxy that exposes only the first column for ListView accessibility"""

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        """Get text data from the underlying source model (bypassing filter proxy)"""
        if index.column() == 0 and role in (Qt.DisplayRole, Qt.AccessibleTextRole):
            # Get the actual text from the root source model (QStandardItemModel)
            # by traversing through the proxy chain
            source_index = self.mapToSource(index)
            filter_proxy = self.sourceModel()
            if filter_proxy:
                root_index = filter_proxy.mapToSource(source_index)
                root_model = filter_proxy.sourceModel()
                if root_model:
                    return root_model.data(root_index, Qt.DisplayRole)
        return super().data(index, role)


class FileFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def data(self, index, role=Qt.DisplayRole):
        """Hide text in column 0 for TreeView - name is shown in column 1"""
        if index.column() == 0 and role in (Qt.DisplayRole, Qt.AccessibleTextRole):
            return ""
        return super().data(index, role)

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter for text"""
        from qt_api import isdeleted, get_proxy_filter_regex, regex_is_empty, regex_matches
        files_filter = get_app().window.filesFilter
        filter_text = "" if isdeleted(files_filter) else files_filter.text()
        if get_app().window.actionFilesShowVideo.isChecked() \
                or get_app().window.actionFilesShowAudio.isChecked() \
                or get_app().window.actionFilesShowImage.isChecked() \
                or filter_text:
            # Fetch the file name
            index = self.sourceModel().index(sourceRow, 0, sourceParent)
            file_name = self.sourceModel().data(index)  # file name (i.e. MyVideo.mp4)

            # Fetch the media_type
            index = self.sourceModel().index(sourceRow, 3, sourceParent)
            media_type = self.sourceModel().data(index)  # media type (i.e. video, image, audio)

            index = self.sourceModel().index(sourceRow, 2, sourceParent)
            tags = self.sourceModel().data(index)  # tags (i.e. intro, custom, etc...)

            if any([
                get_app().window.actionFilesShowVideo.isChecked() and media_type != "video",
                get_app().window.actionFilesShowAudio.isChecked() and media_type != "audio",
                get_app().window.actionFilesShowImage.isChecked() and media_type != "image",
            ]):
                return False

            # Match against regex pattern
            regex = get_proxy_filter_regex(self)
            if not regex_is_empty(regex):
                tag_text = tags or ""
                return regex_matches(regex, file_name) or regex_matches(regex, tag_text)
            return True

        # Continue running built-in parent filter logic
        return super().filterAcceptsRow(sourceRow, sourceParent)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of selected file ids from indexes (more reliable across bindings)
        ids = []
        seen_rows = set()
        for idx in indexes:
            row = idx.row()
            if row in seen_rows:
                continue
            seen_rows.add(row)
            id_index = idx.sibling(row, 5)
            file_id = id_index.data()
            if file_id:
                ids.append(file_id)
        if not ids:
            ids = self.model_owner.selected_file_ids()
        data.setText(json.dumps(ids))
        data.setHtml("clip")
        urls = []
        for file_id in ids:
            try:
                file = File.get(id=file_id)
            except Exception:
                file = None
            if not file:
                continue
            try:
                path = file.absolute_path()
            except Exception:
                path = file.data.get("path")
            if path:
                urls.append(QUrl.fromLocalFile(path))
        if urls:
            data.setUrls(urls)

        # Return Mimedata
        return data

    def get_file_index(self, file_id):
        # Find the index in the proxy model based on the file ID
        if file_id in self.model_owner.model_ids:
            return self.mapFromSource(QModelIndex(self.model_owner.model_ids[file_id]))
        return QModelIndex()

    def __init__(self, **kwargs):
        if "parent" in kwargs:
            self.model_owner = kwargs["parent"]
            kwargs.pop("parent")

        # Call base class implementation
        super().__init__(**kwargs)


class FilesModel(QObject, updates.UpdateInterface):
    ModelRefreshed = pyqtSignal()
    PLACEHOLDER_PREFIX = "__genjob__:"
    PROJECT_FILE_THUMB_ATTEMPTS = 3

    @staticmethod
    def _icon_from_thumbnail_source(thumb_source):
        """Create an icon from freshly loaded thumbnail bytes when possible."""
        thumb_source = str(thumb_source or "")
        if thumb_source:
            pixmap = QPixmap()
            if pixmap.load(thumb_source) and not pixmap.isNull():
                return QIcon(pixmap)
        return QIcon(thumb_source)

    def _thumbnail_source_for_file(self, file, clear_cache=False):
        """Return the thumbnail/artwork source path and display name for a file."""
        path, filename = os.path.split(file.data["path"])
        name = file.data.get("name", filename)
        media_type = file.data.get("media_type")

        if media_type in ["video", "image"]:
            thumbnail_frame = 1
            if 'start' in file.data:
                fps = file.data["fps"]
                fps_float = float(fps["num"]) / float(fps["den"])
                thumbnail_frame = round(float(file.data['start']) * fps_float) + 1
            thumb_source = GetThumbPath(
                file.id,
                thumbnail_frame,
                clear_cache=clear_cache,
                attempts=self.PROJECT_FILE_THUMB_ATTEMPTS,
            )
        else:
            thumb_source = os.path.join(info.PATH, "images", "AudioThumbnail.svg")

        return thumb_source, name, media_type

    def _project_file_icon_for_file(self, file):
        thumb_source, name, media_type = self._thumbnail_source_for_file(file)
        return self._icon_from_thumbnail_source(thumb_source), name, media_type

    def _tooltip_for_file(self, file, name):
        tooltip = str(name or "")
        app = get_app()
        window = getattr(app, "window", None) if app else None
        proxy_service = getattr(window, "proxy_service", None) if window else None
        if not proxy_service or not file:
            return tooltip

        state = proxy_service.get_proxy_state(file)
        if state == "ready":
            return "{} {}".format(tooltip, app._tr("(Optimized)"))
        if state == "missing":
            return "{} {}".format(tooltip, app._tr("(Optimized)"))
        return tooltip

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):

        # Something was changed in the 'files' list
        if action and ((len(action.key) >= 1 and action.key[0].lower() == "files") or action.type == "load"):
            # Refresh project files model
            if action.type == "insert":
                # Don't clear the existing items if only inserting new things
                self.update_model(clear=False)
            elif action.type == "delete" and action.key[0].lower() == "files" and len(action.key) == 2:
                # Delete a top-level file row only when the file object itself was deleted.
                self.update_model(clear=False, delete_file_id=action.key[1].get('id', ''))
            elif action.type in ("update", "delete") and action.key[0].lower() == "files":
                # Update a single file (if found)
                self.update_model(clear=False, update_file_id=action.key[1].get('id', ''))
            else:
                # Clear existing items. For full project loads, batch updates for faster UI rebuild.
                self.update_model(clear=True, progressive_ui=False)

    def update_model(self, clear=True, delete_file_id=None, update_file_id=None, progressive_ui=True):
        log.debug("updating files model.")
        app = get_app()

        self.ignore_updates = True

        # Translations
        _ = app._tr

        # Delete a file (if delete_file_id passed in)
        if delete_file_id in self.model_ids:
            # Use the persistent index we stored to find the row
            id_index = self.model_ids[delete_file_id]

            # sanity check
            if not id_index.isValid() or delete_file_id != id_index.data():
                log.warning("Couldn't remove {} from model!".format(delete_file_id))
                return
            # Delete row from model
            row_num = id_index.row()
            self.model.removeRows(row_num, 1, id_index.parent())
            self.model.submit()
            self.model_ids.pop(delete_file_id)

        # Update a file (if update_file_id passed in)
        if update_file_id in self.model_ids:
            # Use the persistent index we stored to find the row
            id_index = self.model_ids[update_file_id]

            # sanity check
            if not id_index.isValid() or update_file_id != id_index.data():
                log.warning("Couldn't update {} in model!".format(update_file_id))
                return

            # lookup File object
            f = File.get(id=update_file_id)
            if f:
                # Update "tags" in model (if different)
                row_num = id_index.row()
                if f.data.get("tags") != self.model.item(row_num, 2).text():
                    self.model.item(row_num, 2).setText(f.data.get("tags"))
                path, filename = os.path.split(f.data["path"])
                name = f.data.get("name", filename)
                self.model.item(row_num, 0).setToolTip(self._tooltip_for_file(f, name))

        # Clear all items
        if clear:
            self.model_ids = {}
            self.model.clear()

        # Add Headers (all 6 columns - last 3 are hidden but must exist for proper layout)
        self.model.setHorizontalHeaderLabels([
            _("Thumb"), _("Name"), _("Tags"),
            "media_type", "path", "id"
        ])

        # Get list of files in project
        files = File.filter()  # get all files

        # add item for each file
        row_added_count = 0
        for file in files:
            id = file.data["id"]
            if id in self.model_ids and self.model_ids[id].isValid():
                # Ignore files that already exist in model
                continue

            path, filename = os.path.split(file.data["path"])
            tags = file.data.get("tags", "")
            thumb_icon, name, media_type = self._project_file_icon_for_file(file)

            row = []
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt. ItemNeverHasChildren

            # Append thumbnail
            col = QStandardItem(thumb_icon, name)
            col.setToolTip(self._tooltip_for_file(file, name))
            col.setFlags(flags)
            col.setAccessibleText(name)
            row.append(col)

            # Append Filename
            col = QStandardItem(name)
            col.setFlags(flags | Qt.ItemIsEditable)
            col.setAccessibleText(name)
            row.append(col)

            # Append Tags
            col = QStandardItem(tags)
            col.setFlags(flags | Qt.ItemIsEditable)
            row.append(col)

            # Append Media Type
            col = QStandardItem(media_type)
            col.setFlags(flags)
            row.append(col)

            # Append Path
            col = QStandardItem(path)
            col.setFlags(flags)
            row.append(col)

            # Append ID
            col = QStandardItem(id)
            col.setFlags(flags | Qt.ItemIsUserCheckable)
            row.append(col)

            # Append ROW to MODEL (if does not already exist in model)
            if id not in self.model_ids:
                self.model.appendRow(row)
                # Link the file ID hash to that column of the table row by persistent index
                self.model_ids[id] = QPersistentModelIndex(row[5].index())

                row_added_count += 1
                if progressive_ui and row_added_count % 25 == 0:
                    # Update every X items
                    get_app().processEvents(QEventLoop.ExcludeUserInputEvents)

            # Refresh view/filtering incrementally during interactive updates (i.e. imports)
            if progressive_ui:
                get_app().window.resize_contents()

        self.ignore_updates = False

        # Single refresh after bulk updates (i.e. opening a project)
        if not progressive_ui:
            get_app().window.resize_contents()

        # Emit signal when model is updated
        self.ModelRefreshed.emit()
        self._rebuild_generation_placeholders()

    def add_files(self, files, image_seq_details=None, quiet=False,
                  prevent_image_seq=False, prevent_recent_folder=False):
        # Access translations
        app = get_app()
        settings = app.get_settings()
        _ = app._tr

        # Make sure we're working with a list of files
        if not isinstance(files, (list, tuple)):
            files = [files]
        scroll_to_files = []

        start_count = len(files)
        for count, filepath in enumerate(files):
            (dir_path, filename) = os.path.split(filepath)

            # Check for this path in our existing project data
            new_file = File.get(path=filepath)

            # If this file is already found, exit
            if new_file:
                # Still add the file (to be selected and scrolled to)
                scroll_to_files.append(new_file)
                del new_file
                continue

            try:
                # Inspect the file with a lightweight temporary reader.
                file_data, _media_duration = inspect_media(
                    filepath,
                    max_width=IMPORT_READER_MAX_SIZE,
                    max_height=IMPORT_READER_MAX_SIZE,
                )

                # Determine media type
                file_data["media_type"] = get_media_type(file_data)

                # Check for audio-only files
                if file_data.get("has_audio") and not file_data.get("has_video"):
                    # Audio-only file should match the current project size and FPS
                    project = get_app().project
                    file_data["width"] = project.get("width")
                    file_data["height"] = project.get("height")

                # Save new file to the project data
                new_file = File()
                new_file.data = file_data

                # Is this an image sequence / animation?
                seq_info = None
                if not prevent_image_seq:
                    seq_info = image_seq_details or self.get_image_sequence_details(filepath)

                if seq_info:
                    # Update file with image sequence path & name
                    new_path = seq_info.get("path")

                    # Load image sequence (to determine duration and video_length)
                    new_file.data, media_duration = inspect_media(
                        new_path,
                        max_width=IMPORT_READER_MAX_SIZE,
                        max_height=IMPORT_READER_MAX_SIZE,
                    )
                    if media_duration > 0.0:
                        # Update file details
                        new_file.data["media_type"] = "video"
                        duration = new_file.data["duration"]

                        if seq_info and "fps" in seq_info and "length_multiplier" in seq_info:
                            # Blender Titles specify their fps in seq_info
                            fps_num = seq_info.get("fps", {}).get("num", 25)
                            fps_den = seq_info.get("fps", {}).get("den", 1)
                            log.debug("Image Sequence using specified FPS: %s / %s" % (fps_num, fps_den))
                        else:
                            # Get the project's fps, apply to the image sequence.
                            fps_num = get_app().project.get("fps").get("num", 30)
                            fps_den = get_app().project.get("fps").get("den", 1)
                            log.debug("Image Sequence using project FPS: %s / %s" % (fps_num, fps_den))

                        # Adjust FPS (difference between 25 FPS and actual FPS)
                        duration *= 25.0 / (float(fps_num) / float(fps_den))
                        new_file.data["duration"] = duration
                        new_file.data["fps"] = {"num": fps_num, "den": fps_den}
                        new_file.data["video_timebase"] = {"num": fps_den, "den": fps_num}

                        log.info(f"Imported '{new_path}' as image sequence with '{fps_num}/{fps_den}' FPS "
                                 f"and '{duration}' duration")

                        # Remove any other image sequence files from the list we're processing
                        match_glob = "{}{}.{}".format(seq_info.get("base_name"), '[0-9]*', seq_info.get("extension"))
                        log.debug("Removing files from import list with glob: {}".format(match_glob))
                        for seq_file in glob.iglob(os.path.join(seq_info.get("folder_path"), match_glob)):
                            # Don't remove the current file, or we mess up the for loop
                            if seq_file in files and seq_file != filepath:
                                files.remove(seq_file)
                    else:
                        # Failed to import image sequence
                        log.info(f"Failed to parse image sequence pattern {new_path}, ignoring...")
                        continue

                if not seq_info:
                    # Log our not-an-image-sequence import
                    log.info("Imported media file {}".format(filepath))

                # Save file
                new_file.save()
                scroll_to_files.append(new_file)

                if start_count > 15:
                    message = _("Importing %(count)d / %(total)d") % {
                            "count": count,
                            "total": len(files) - 1
                            }
                    app.window.statusBar.showMessage(message, 15000)

                # Let the event loop run to update the status bar
                get_app().processEvents()
                # Update the recent import path
                if not prevent_recent_folder:
                    settings.setDefaultPath(settings.actionType.IMPORT, dir_path)

            except Exception as ex:
                # Log exception
                log.warning("Failed to import {}: {}".format(filepath, ex))

                if not quiet and start_count == 1:
                    # Show message box to user (if importing a single file)
                    app.window.invalidImage(filename)

        # Reset list of ignored paths
        self.ignore_image_sequence_paths = []

        # Select all new files (clear previous selection)
        self.selection_model.clearSelection()
        last_selected_index = QModelIndex()
        for file_object in scroll_to_files:
            # Get the index of the newly added file in the proxy model
            index = self.proxy_model.get_file_index(file_object.id)
            if index.isValid():
                # Select & scroll to selection
                self.selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                get_app().window.filesView.scrollTo(
                    model_index_sibling_at_column(index, 0),
                    QAbstractItemView.PositionAtCenter,
                )
                last_selected_index = index
        if last_selected_index.isValid():
            # Keep current index aligned with the newly selected file so actions
            # (preview/properties/etc.) resolve to the expected item.
            self.selection_model.setCurrentIndex(last_selected_index, QItemSelectionModel.NoUpdate)

        message = _("Imported %(count)d files") % {"count": len(files) - 1}
        app.window.statusBar.showMessage(message, 3000)

    def get_image_sequence_details(self, file_path):
        """Inspect a file path and determine if this is an image sequence"""

        # Get just the file name
        (dirName, fileName) = os.path.split(file_path)

        # Image sequence imports are one per directory per run
        if dirName in self.ignore_image_sequence_paths:
            return None

        extensions = ["png", "jpg", "jpeg", "tif", "svg"]
        match = re.findall(r"(.*[^\d])?(0*)(\d+)\.(%s)" % "|".join(extensions), fileName, re.I)

        if not match:
            # File name does not match an image sequence
            return None

        # Get the parts of image name
        base_name = match[0][0]
        fixlen = match[0][1] > ""
        number = int(match[0][2])
        digits = len(match[0][1] + match[0][2])
        extension = match[0][3]

        full_base_name = os.path.join(dirName, base_name)

        # Check for images which the file names have the different length
        fixlen = fixlen or not (
            glob.glob("%s%s.%s" % (full_base_name, "[0-9]" * (digits + 1), extension))
            or glob.glob("%s%s.%s" % (full_base_name, "[0-9]" * ((digits - 1) if digits > 1 else 3), extension))
        )

        # Check for previous or next image
        for x in range(max(0, number - 100), min(number + 101, 50000)):
            if x != number and os.path.exists(
               "%s%s.%s" % (full_base_name, str(x).rjust(digits, "0") if fixlen else str(x), extension)):
                break  # found one!
        else:
            # We didn't discover an image sequence
            return None

        # Found a sequence, ignore this path (no matter what the user answers)
        # To avoid issues with overlapping/conflicting sets of files,
        # we only attempt one image sequence match per directory
        log.debug("Ignoring path for image sequence imports: {}".format(dirName))
        self.ignore_image_sequence_paths.append(dirName)

        log.info('Prompt user to import sequence starting from {}'.format(fileName))
        if not get_app().window.promptImageSequence(fileName):
            # User said no, don't import as a sequence
            return None

        # generate file glob pattern (for this image sequence)
        if not fixlen:
            zero_pattern = "%d"
        else:
            zero_pattern = "%%0%sd" % digits
        pattern = "%s%s.%s" % (base_name, zero_pattern, extension)
        new_file_path = os.path.join(dirName, pattern)

        # Yes, import image sequence
        parameters = {
            "folder_path": dirName,
            "base_name": base_name,
            "fixlen": fixlen,
            "digits": digits,
            "extension": extension,
            "pattern": pattern,
            "path": new_file_path
        }
        return parameters

    def process_urls(self, qurl_list, import_quietly=False, prevent_image_seq=False,
                     transaction_id=None):
        """Recursively process QUrls from a QDropEvent"""
        media_paths = []

        # Transaction — use caller's transaction_id when provided so the
        # caller can group file imports with subsequent operations (e.g.
        # clip creation on timeline drop) into a single undo step.
        owns_transaction = transaction_id is None
        if owns_transaction:
            transaction_id = str(uuid.uuid4())
        get_app().updates.transaction_id = transaction_id

        for uri in qurl_list:
            filepath = uri.toLocalFile()
            if not os.path.exists(filepath):
                continue
            if filepath.endswith(".osp") and os.path.isfile(filepath):
                # Auto load project passed as argument
                get_app().window.OpenProjectSignal.emit(filepath)
                return True
            if os.path.isdir(filepath):
                import_quietly = True
                log.info("Recursively importing {}".format(filepath))
                try:
                    for r, _, f in os.walk(filepath):
                        media_paths.extend(
                            [os.path.join(r, p) for p in f])
                except OSError:
                    log.warning("Directory recursion failed", exc_info=1)
            elif os.path.isfile(filepath):
                media_paths.append(filepath)
        if not media_paths:
            if owns_transaction:
                get_app().updates.transaction_id = None
            return
        # Import all new media files
        media_paths.sort()
        log.debug("Importing file list: {}".format(media_paths))
        self.add_files(media_paths, quiet=import_quietly, prevent_image_seq=prevent_image_seq)
        if owns_transaction:
            get_app().updates.transaction_id = None

    def update_file_thumbnail(self, file_id):
        """Update/re-generate the thumbnail of a specific file"""
        file = File.get(id=file_id)
        path, filename = os.path.split(file.data["path"])
        name = file.data.get("name", filename)

        # Refresh thumbnail for updated file
        self.ignore_updates = True
        m = self.model

        if file_id in self.model_ids:
            # Look up stored index to ID column
            id_index = self.model_ids[file_id]
            if not id_index.isValid():
                return

            thumb_source, _, _ = self._thumbnail_source_for_file(file, clear_cache=True)
            thumb_icon = self._icon_from_thumbnail_source(thumb_source)

            # Update thumb for file
            thumb_index = id_index.sibling(id_index.row(), 0)
            item = m.itemFromIndex(thumb_index)
            item.setIcon(thumb_icon)
            item.setText(name)
            item.setToolTip(self._tooltip_for_file(file, name))
            item.setAccessibleText(name)

            # Update display name
            text_index = id_index.sibling(id_index.row(), 1)
            item = m.itemFromIndex(text_index)
            item.setText(name)

            # Emit signal when model is updated
            self.ModelRefreshed.emit()

        self.ignore_updates = False

    def selected_file_ids(self):
        """ Get a list of file IDs for all selected files """
        # Get the indexes for column 5 of all selected rows
        selected = self.selection_model.selectedRows(5)
        ids = []
        for idx in selected:
            file_id = idx.data()
            if not file_id or self._is_generation_placeholder(file_id):
                continue
            ids.append(file_id)
        return ids

    def selected_files(self):
        """ Get a list of File objects representing the current selection """
        files = []
        for id in self.selected_file_ids():
            files.append(File.get(id=id))
        return files

    def current_file_id(self):
        """ Get the file ID of the current files-view item, or the first selection """
        # Prefer selected rows first, since currentIndex can become stale when
        # switching between details/list views with separate selection models.
        selected_rows = self.selection_model.selectedRows(5)
        if selected_rows:
            selected_ids = set()
            for row_index in selected_rows:
                file_id = row_index.data()
                if file_id and not self._is_generation_placeholder(file_id):
                    selected_ids.add(file_id)

            current = self.selection_model.currentIndex()
            if current and current.isValid():
                current_id = current.sibling(current.row(), 5).data()
                if current_id and current_id in selected_ids:
                    return current_id
            for row_index in selected_rows:
                file_id = row_index.data()
                if file_id and not self._is_generation_placeholder(file_id):
                    return file_id

        cur = self.selection_model.currentIndex()
        if cur and cur.isValid():
            file_id = cur.sibling(cur.row(), 5).data()
            if file_id and not self._is_generation_placeholder(file_id):
                return file_id

    def current_file(self):
        """ Get the File object for the current files-view item, or the first selection """
        cur_id = self.current_file_id()
        if cur_id:
            return File.get(id=cur_id)
        else:
            return None

    def value_updated(self, item):
        """ Table cell change event - when tags are updated on a file"""
        if item.column() == 2:
            # Get updated tag value
            tags_value = item.data(0)
            f = self.current_file()
            if f:
                # Save tags to file object
                f.data["tags"] = tags_value
                f.save()

    def _sync_tree_to_list_selection(self, selected, deselected):
        """Sync selection from TreeView (proxy_model) to ListView (list_proxy_model)"""
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            # Map selected indexes from proxy_model to list_proxy_model
            list_selection = QItemSelection()
            first_list_index = QModelIndex()
            for index in self.selection_model.selectedRows(0):
                list_index = self.list_proxy_model.mapFromSource(index)
                if list_index.isValid():
                    list_selection.select(list_index, list_index)
                    if not first_list_index.isValid():
                        first_list_index = list_index
            self.list_selection_model.select(
                list_selection,
                QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
            )
            if first_list_index.isValid():
                self.list_selection_model.setCurrentIndex(first_list_index, QItemSelectionModel.NoUpdate)
        finally:
            self._syncing_selection = False

    def _sync_list_to_tree_selection(self, selected, deselected):
        """Sync selection from ListView (list_proxy_model) to TreeView (proxy_model)"""
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            # Map selected indexes from list_proxy_model to proxy_model
            tree_selection = QItemSelection()
            first_tree_index = QModelIndex()
            for index in self.list_selection_model.selectedRows(0):
                tree_index = self.list_proxy_model.mapToSource(index)
                if tree_index.isValid():
                    tree_selection.select(tree_index, tree_index)
                    if not first_tree_index.isValid():
                        first_tree_index = tree_index
            self.selection_model.select(
                tree_selection,
                QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
            )
            if first_tree_index.isValid():
                self.selection_model.setCurrentIndex(first_tree_index, QItemSelectionModel.NoUpdate)
        finally:
            self._syncing_selection = False

    def __init__(self, *args, generation_queue=None, proxy_service=None):
        self.generation_queue = generation_queue
        self.proxy_service = proxy_service

        # Add self as listener to project data updates
        # (undo/redo, as well as normal actions handled within this class all update the model)
        app = get_app()
        app.updates.add_listener(self)

        # Create standard model
        self.model = QStandardItemModel()
        self.model.setColumnCount(6)
        self.model_ids = {}
        self.ignore_updates = False
        self.ignore_image_sequence_paths = []

        # Create proxy model (for sorting and filtering) - used by TreeView
        self.proxy_model = FileFilterProxyModel(parent=self)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)

        # Create single-column proxy for ListView (wraps proxy_model for accessibility)
        self.list_proxy_model = SingleColumnProxyModel()
        self.list_proxy_model.setSourceModel(self.proxy_model)

        # Connect data changed signal
        self.model.itemChanged.connect(self.value_updated)

        # Create selection models for each view
        self.selection_model = QItemSelectionModel(self.proxy_model)
        self.list_selection_model = QItemSelectionModel(self.list_proxy_model)

        # Sync selections between the two selection models
        self._syncing_selection = False
        self.selection_model.selectionChanged.connect(self._sync_tree_to_list_selection)
        self.list_selection_model.selectionChanged.connect(self._sync_list_to_tree_selection)

        # Connect signal
        app.window.FileUpdated.connect(self.update_file_thumbnail)
        app.window.refreshFilesSignal.connect(
            functools.partial(self.update_model, clear=False))
        if self.generation_queue:
            self.generation_queue.file_job_changed.connect(self._refresh_file_generation_display)
            self.generation_queue.queue_changed.connect(self._refresh_all_generation_displays)
            self.generation_queue.job_added.connect(self._on_generation_job_added)
            self.generation_queue.job_updated.connect(self._on_generation_job_updated)
            self.generation_queue.job_finished.connect(self._on_generation_job_finished)
            self.generation_queue.job_removed.connect(self._on_generation_job_removed)
        if self.proxy_service:
            self.proxy_service.file_job_changed.connect(self._refresh_file_generation_display)
            self.proxy_service.queue_changed.connect(self._refresh_all_generation_displays)

        # Call init for superclass QObject
        super().__init__(*args)

        # Attempt to load model testing interface, if requested
        # (will only succeed with Qt 5.11+)
        if info.MODEL_TEST:
            try:
                # Create model tester objects
                from qt_api import QAbstractItemModelTester
                self.model_tests = []
                for m in [self.proxy_model, self.model]:
                    self.model_tests.append(
                        QAbstractItemModelTester(
                            m, QAbstractItemModelTester.FailureReportingMode.Warning)
                    )
                log.info("Enabled {} model tests for emoji data".format(len(self.model_tests)))
            except ImportError:
                pass

    def _is_generation_placeholder(self, file_id):
        return str(file_id or "").startswith(self.PLACEHOLDER_PREFIX)

    def _placeholder_id_for_job(self, job_id):
        return "{}{}".format(self.PLACEHOLDER_PREFIX, str(job_id or ""))

    def _job_id_from_placeholder(self, file_id):
        file_id = str(file_id or "")
        if not self._is_generation_placeholder(file_id):
            return None
        return file_id[len(self.PLACEHOLDER_PREFIX):]

    def _placeholder_row_for_job(self, job_id):
        placeholder_id = self._placeholder_id_for_job(job_id)
        if placeholder_id not in self.model_ids:
            return None
        id_index = self.model_ids[placeholder_id]
        if not id_index.isValid():
            return None
        return id_index.row()

    def _generation_icon_for_job(self, job):
        icon_name = "tool-generate-sparkle.svg"
        try:
            app = get_app()
            window = getattr(app, "window", None)
            generation_service = getattr(window, "generation_service", None)
            if generation_service and isinstance(job, dict):
                template_id = str(job.get("template_id") or "").strip()
                template = generation_service.template_registry.get_template(template_id)
                if template:
                    resolved_icon = generation_service.icon_for_template(template)
                    if resolved_icon:
                        icon_name = resolved_icon
        except Exception:
            pass

        icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", icon_name)
        if os.path.exists(icon_path):
            return QIcon(icon_path)

        emoji_icon_path = os.path.join(info.PATH, "emojis", "color", "svg", "2728.svg")
        if os.path.exists(emoji_icon_path):
            return QIcon(emoji_icon_path)
        return QIcon(":/icons/Humanity/actions/16/media-record.svg")

    def _add_generation_placeholder(self, job_id):
        job = self.generation_queue.get_job(job_id) if self.generation_queue else None
        if not job:
            return
        if job.get("source_file_id"):
            return

        placeholder_id = self._placeholder_id_for_job(job_id)
        if placeholder_id in self.model_ids and self.model_ids[placeholder_id].isValid():
            self._update_generation_placeholder(job_id)
            return

        name = str(job.get("name") or "generation")
        status = str(job.get("status") or "queued")
        progress = int(job.get("progress", 0))
        progress_detail = str(job.get("progress_detail") or "").strip()
        label = name
        if status == "running":
            label = "{} ({}%)".format(name, progress)
            if progress_detail:
                label = "{} [{}]".format(label, progress_detail)
        elif status == "queued":
            label = "{} (Queued)".format(name)
        elif status == "canceling":
            label = "{} (Canceling...)".format(name)

        row = []
        icon = self._generation_icon_for_job(job)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren

        col = QStandardItem(icon, label)
        col.setFlags(flags)
        row.append(col)

        col = QStandardItem(label)
        col.setFlags(flags)
        row.append(col)

        col = QStandardItem("generation")
        col.setFlags(flags)
        row.append(col)

        col = QStandardItem("generation_job")
        col.setFlags(flags)
        row.append(col)

        col = QStandardItem("")
        col.setFlags(flags)
        row.append(col)

        col = QStandardItem(placeholder_id)
        col.setFlags(flags)
        row.append(col)

        self.model.appendRow(row)
        self.model_ids[placeholder_id] = QPersistentModelIndex(row[5].index())
        self.ModelRefreshed.emit()

    def _update_generation_placeholder(self, job_id):
        row = self._placeholder_row_for_job(job_id)
        if row is None:
            self._add_generation_placeholder(job_id)
            return
        job = self.generation_queue.get_job(job_id) if self.generation_queue else None
        if not job:
            return

        name = str(job.get("name") or "generation")
        status = str(job.get("status") or "queued")
        progress = int(job.get("progress", 0))
        progress_detail = str(job.get("progress_detail") or "").strip()
        label = name
        if status == "running":
            label = "{} ({}%)".format(name, progress)
            if progress_detail:
                label = "{} [{}]".format(label, progress_detail)
        elif status == "queued":
            label = "{} (Queued)".format(name)
        elif status == "canceling":
            label = "{} (Canceling...)".format(name)

        self.model.item(row, 0).setIcon(self._generation_icon_for_job(job))
        self.model.item(row, 0).setText(label)
        self.model.item(row, 1).setText(label)
        left = self.model.index(row, 0)
        right = self.model.index(row, 1)
        self.model.dataChanged.emit(left, right, [Qt.DisplayRole, Qt.AccessibleTextRole])
        self.ModelRefreshed.emit()

    def _remove_generation_placeholder(self, job_id):
        placeholder_id = self._placeholder_id_for_job(job_id)
        if placeholder_id not in self.model_ids:
            return
        id_index = self.model_ids.get(placeholder_id)
        if not id_index or not id_index.isValid():
            self.model_ids.pop(placeholder_id, None)
            return
        row = id_index.row()
        self.model.removeRows(row, 1, id_index.parent())
        self.model.submit()
        self.model_ids.pop(placeholder_id, None)
        self.ModelRefreshed.emit()

    def _rebuild_generation_placeholders(self):
        if not self.generation_queue:
            return
        for job in list(self.generation_queue.jobs.values()):
            if job.get("source_file_id"):
                continue
            if job.get("status") in ("completed", "failed", "canceled"):
                self._remove_generation_placeholder(job.get("id"))
            else:
                self._add_generation_placeholder(job.get("id"))

    def _on_generation_job_added(self, job_id, source_file_id):
        if source_file_id:
            return
        self._add_generation_placeholder(job_id)

    def _on_generation_job_updated(self, job_id, status, progress):
        job = self.generation_queue.get_job(job_id) if self.generation_queue else None
        if not job or job.get("source_file_id"):
            return
        if status in ("completed", "failed", "canceled"):
            self._remove_generation_placeholder(job_id)
        else:
            self._update_generation_placeholder(job_id)

    def _on_generation_job_finished(self, job_id, status):
        job = self.generation_queue.get_job(job_id) if self.generation_queue else None
        if not job or job.get("source_file_id"):
            return
        self._remove_generation_placeholder(job_id)

    def _on_generation_job_removed(self, job_id):
        self._remove_generation_placeholder(job_id)

    def _refresh_file_generation_display(self, file_id):
        file_id = str(file_id or "")
        if not file_id:
            return
        if file_id not in self.model_ids:
            return
        id_index = self.model_ids[file_id]
        if not id_index.isValid():
            return
        row = id_index.row()
        file_obj = File.get(id=file_id)
        if file_obj:
            _, filename = os.path.split(file_obj.data["path"])
            name = file_obj.data.get("name", filename)
            self.model.item(row, 0).setToolTip(self._tooltip_for_file(file_obj, name))
        left = self.model.index(row, 0)
        right = self.model.index(row, 0)
        self.model.dataChanged.emit(left, right, [Qt.DisplayRole, Qt.AccessibleTextRole])
        self.ModelRefreshed.emit()

    def _refresh_all_generation_displays(self):
        if self.model.rowCount() < 1:
            return
        left = self.model.index(0, 0)
        right = self.model.index(self.model.rowCount() - 1, 0)
        self.model.dataChanged.emit(left, right, [Qt.DisplayRole, Qt.AccessibleTextRole])
        self.ModelRefreshed.emit()
