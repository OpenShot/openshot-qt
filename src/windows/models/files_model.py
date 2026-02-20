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

from PyQt5.QtCore import (
    QMimeData, Qt, pyqtSignal, QEventLoop, QObject, QThread,
    QSortFilterProxyModel, QItemSelectionModel, QPersistentModelIndex, QModelIndex
)
from PyQt5.QtGui import (
    QIcon, QStandardItem, QStandardItemModel
)
from PyQt5.QtWidgets import QAbstractItemView
from classes import updates
from classes import info
from classes.image_types import get_media_type
from classes.query import File
from classes.logger import log
from classes.app import get_app
from classes.thumbnail import GetThumbPath
from classes.tag_manager import get_tag_manager
from classes.gemini_tagger import GeminiVideoTagger

import openshot


class FileFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering model data"""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter for text"""
        if get_app().window.actionFilesShowVideo.isChecked() \
                or get_app().window.actionFilesShowAudio.isChecked() \
                or get_app().window.actionFilesShowImage.isChecked() \
                or get_app().window.filesFilter.text():
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
            return self.filterRegExp().indexIn(file_name) >= 0 or self.filterRegExp().indexIn(tags) >= 0

        # Continue running built-in parent filter logic
        return super().filterAcceptsRow(sourceRow, sourceParent)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        ids = self.parent.selected_file_ids()
        data.setText(json.dumps(ids))
        data.setHtml("clip")

        # Return Mimedata
        return data

    def get_file_index(self, file_id):
        # Find the index in the proxy model based on the file ID
        if file_id in self.parent.model_ids:
            return self.mapFromSource(QModelIndex(self.parent.model_ids[file_id]))
        return QModelIndex()

    def __init__(self, **kwargs):
        if "parent" in kwargs:
            self.parent = kwargs["parent"]
            kwargs.pop("parent")

        # Call base class implementation
        super().__init__(**kwargs)


class GeminiTaggingWorker(QThread):
    """Background worker that tags a single video file using Gemini/Gemma."""

    completed = pyqtSignal(dict, dict, object)

    def __init__(self, file_data, parent=None):
        super().__init__(parent)
        self.file_data = file_data

    def run(self):
        metadata = GeminiVideoTagger.empty_metadata()
        error = None
        try:
            tagger = GeminiVideoTagger()
            if self.file_data.get("media_type") == "video":
                metadata = tagger.analyze_video(self.file_data.get("path"))
        except Exception as exc:  # pragma: no cover - defensive logging
            error = exc
            log.error(f"Gemini tagging worker failed: {exc}")

        self.completed.emit(self.file_data, metadata, error)


class FilesModel(QObject, updates.UpdateInterface):
    ModelRefreshed = pyqtSignal()

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):

        # Something was changed in the 'files' list
        if action and ((len(action.key) >= 1 and action.key[0].lower() == "files") or action.type == "load"):
            # Refresh project files model
            if action.type == "insert":
                # Don't clear the existing items if only inserting new things
                self.update_model(clear=False)
            elif action.type == "delete" and action.key[0].lower() == "files":
                # Don't clear the existing items if only deleting things
                self.update_model(clear=False, delete_file_id=action.key[1].get('id', ''))
            elif action.type == "update" and action.key[0].lower() == "files":
                # Update a single file (if found)
                self.update_model(clear=False, update_file_id=action.key[1].get('id', ''))
            else:
                # Clear existing items
                self.update_model(clear=True)

    def update_model(self, clear=True, delete_file_id=None, update_file_id=None):
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

        # Clear all items
        if clear:
            self.model_ids = {}
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels(["", _("Name"), _("Tags")])

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
            name = file.data.get("name", filename)

            media_type = file.data.get("media_type")

            # Generate thumbnail for file (if needed)
            if media_type in ["video", "image"]:
                # Check for start and end attributes (optional)
                thumbnail_frame = 1
                if 'start' in file.data:
                    fps = file.data["fps"]
                    fps_float = float(fps["num"]) / float(fps["den"])
                    thumbnail_frame = round(float(file.data['start']) * fps_float) + 1

                # Get thumb path
                thumb_icon = QIcon(GetThumbPath(file.id, thumbnail_frame))
            else:
                # Audio file
                thumb_icon = QIcon(os.path.join(info.PATH, "images", "AudioThumbnail.svg"))

            row = []
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt. ItemNeverHasChildren

            # Append thumbnail
            col = QStandardItem(thumb_icon, name)
            col.setToolTip(filename)
            col.setFlags(flags)
            row.append(col)

            # Append Filename
            col = QStandardItem(name)
            col.setFlags(flags | Qt.ItemIsEditable)
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
                if row_added_count % 2 == 0:
                    # Update every X items
                    get_app().processEvents(QEventLoop.ExcludeUserInputEvents)

            # Refresh view and filters (to hide or show this new item)
            get_app().window.resize_contents()

        self.ignore_updates = False

        # Emit signal when model is updated
        self.ModelRefreshed.emit()

    def _tag_file_with_gemini(self, file_data):
        """Run Gemini tagging off the UI thread and wait for completion."""
        loop = QEventLoop()
        result = {
            "metadata": GeminiVideoTagger.empty_metadata(),
            "error": None,
        }

        worker = GeminiTaggingWorker(dict(file_data))

        def _on_complete(_file_data, metadata, error):
            result["metadata"] = metadata or GeminiVideoTagger.empty_metadata()
            result["error"] = error
            loop.quit()

        worker.completed.connect(_on_complete)
        worker.start()
        loop.exec_()
        worker.wait()

        if result["error"]:
            log.warning(f"Gemini tagging returned an error: {result['error']}")

        return result["metadata"]

    def _apply_ai_metadata(self, file_obj, ai_metadata):
        """Attach AI metadata to file and sync tag manager."""
        if not ai_metadata:
            return

        file_obj.data["ai_metadata"] = ai_metadata

        # Populate human-readable tags column with a short summary if empty
        # (legacy UI column name is still "Tags" but we now prefer scene descriptions)
        tags = ai_metadata.get("tags", {}) if isinstance(ai_metadata, dict) else {}
        top_objects = tags.get("objects", []) if isinstance(tags, dict) else []
        if top_objects and not file_obj.data.get("tags"):
            file_obj.data["tags"] = ", ".join(top_objects[:5])

        # If the new scene_descriptions exists, prefer showing the first one
        if not file_obj.data.get("tags"):
            scenes = ai_metadata.get("scene_descriptions", []) if isinstance(ai_metadata, dict) else []
            if isinstance(scenes, list) and scenes:
                first = scenes[0] if isinstance(scenes[0], dict) else None
                if first:
                    desc = (first.get("description") or "").strip()
                    if desc:
                        file_obj.data["tags"] = desc[:120]

        # Sync tag cache for the new file
        try:
            get_tag_manager().update_file_tags(file_obj.id, ai_metadata)
        except Exception as exc:
            log.warning(f"Failed to update tag cache for {file_obj.id}: {exc}")

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
                # Load filepath in libopenshot clip object (which will try multiple readers to open it)
                clip = openshot.Clip(filepath)

                # Get the JSON for the clip's internal reader
                reader = clip.Reader()
                file_data = json.loads(reader.Json())

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
                    clip = openshot.Clip(new_path)
                    new_file.data = json.loads(clip.Reader().Json())
                    if clip and clip.info.duration > 0.0:
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

                # AI tagging (Gemini) before exposing clip to UI
                ai_metadata = GeminiVideoTagger.empty_metadata()
                if new_file.data.get("media_type") == "video":
                    app.window.statusBar.showMessage(
                        _("Processing tags for %(name)s ...") % {"name": filename},
                        0
                    )
                    ai_metadata = self._tag_file_with_gemini(new_file.data)

                new_file.data["ai_metadata"] = ai_metadata

                # Save file after tagging completes so the UI only sees tagged clips
                new_file.save()
                scroll_to_files.append(new_file)
                self._apply_ai_metadata(new_file, ai_metadata)

                # Should we auto-analyze this file with the legacy queue?
                try:
                    s = get_app().get_settings()
                    if s.get('ai-enabled') and s.get('ai-auto-analyze') and not ai_metadata.get('analyzed'):
                        from classes.media_analyzer import get_analysis_queue
                        queue = get_analysis_queue()
                        queue.add_to_queue(
                            new_file.id,
                            new_file.absolute_path(),
                            new_file.data.get('media_type', 'video')
                        )
                except Exception as e:
                    log.warning(f"Failed to queue file for AI analysis: {e}")

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
        for file_object in scroll_to_files:
            # Get the index of the newly added file in the proxy model
            index = self.proxy_model.get_file_index(file_object.id)
            if index.isValid():
                # Select & scroll to selection
                self.selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                get_app().window.filesView.scrollTo(index.siblingAtColumn(0), QAbstractItemView.PositionAtCenter)

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

    def process_urls(self, qurl_list, import_quietly=False, prevent_image_seq=False):
        """Recursively process QUrls from a QDropEvent"""
        media_paths = []

        # Transaction
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid

        for uri in qurl_list:
            filepath = uri.toLocalFile()
            if not os.path.exists(filepath):
                continue
            if filepath.endswith(info.ALL_PROJECT_EXTS) and os.path.isfile(filepath):
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
            return
        # Import all new media files
        media_paths.sort()
        log.debug("Importing file list: {}".format(media_paths))
        self.add_files(media_paths, quiet=import_quietly, prevent_image_seq=prevent_image_seq)
        get_app().updates.transaction_id = None

    def update_file_thumbnail(self, file_id):
        """Update/re-generate the thumbnail of a specific file"""
        file = File.get(id=file_id)
        path, filename = os.path.split(file.data["path"])
        name = file.data.get("name", filename)

        fps = file.data["fps"]
        fps_float = float(fps["num"]) / float(fps["den"])

        # Refresh thumbnail for updated file
        self.ignore_updates = True
        m = self.model

        if file_id in self.model_ids:
            # Look up stored index to ID column
            id_index = self.model_ids[file_id]
            if not id_index.isValid():
                return

            # Generate thumbnail for file (if needed)
            if file.data.get("media_type") in ["video", "image"]:
                # Check for start and end attributes (optional)
                thumbnail_frame = 1
                if 'start' in file.data:
                    thumbnail_frame = round(float(file.data['start']) * fps_float) + 1

                # Get thumb path
                thumb_icon = QIcon(GetThumbPath(file.id, thumbnail_frame, clear_cache=True))
            else:
                # Audio file
                thumb_icon = QIcon(os.path.join(info.PATH, "images", "AudioThumbnail.svg"))

            # Update thumb for file
            thumb_index = id_index.sibling(id_index.row(), 0)
            item = m.itemFromIndex(thumb_index)
            item.setIcon(thumb_icon)
            item.setText(name)

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

        return [idx.data() for idx in selected]

    def selected_files(self):
        """ Get a list of File objects representing the current selection """
        files = []
        for id in self.selected_file_ids():
            files.append(File.get(id=id))
        return files

    def current_file_id(self):
        """ Get the file ID of the current files-view item, or the first selection """
        cur = self.selection_model.currentIndex()

        if not cur or not cur.isValid() and self.selection_model.hasSelection():
            cur = self.selection_model.selectedIndexes()[0]

        if cur and cur.isValid():
            return cur.sibling(cur.row(), 5).data()

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

    def __init__(self, *args):

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

        # Create proxy model (for sorting and filtering)
        self.proxy_model = FileFilterProxyModel(parent=self)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)

        # Connect data changed signal
        self.model.itemChanged.connect(self.value_updated)

        # Create selection model to share between views
        self.selection_model = QItemSelectionModel(self.proxy_model)

        # Connect signal
        app.window.FileUpdated.connect(self.update_file_thumbnail)
        app.window.refreshFilesSignal.connect(
            functools.partial(self.update_model, clear=False))

        # Call init for superclass QObject
        super(QObject, FilesModel).__init__(self, *args)

        # Attempt to load model testing interface, if requested
        # (will only succeed with Qt 5.11+)
        if info.MODEL_TEST:
            try:
                # Create model tester objects
                from PyQt5.QtTest import QAbstractItemModelTester
                self.model_tests = []
                for m in [self.proxy_model, self.model]:
                    self.model_tests.append(
                        QAbstractItemModelTester(
                            m, QAbstractItemModelTester.FailureReportingMode.Warning)
                    )
                log.info("Enabled {} model tests for emoji data".format(len(self.model_tests)))
            except ImportError:
                pass
