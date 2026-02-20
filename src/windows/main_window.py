"""
 @file
 @brief This file loads the main window (i.e. the primary user-interface)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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

import functools
import json
import os
import re
import shutil
import uuid
import webbrowser
from time import sleep, time
from datetime import datetime
from uuid import uuid4
import zipfile
import threading

import openshot  # Python module for libopenshot (required video editing module installed separately)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QCoreApplication, QTimer, QDateTime, QFileInfo, QEvent, QUrl
)
from PyQt5.QtGui import QIcon, QCursor, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QDockWidget,
    QMessageBox, QDialog, QFileDialog, QInputDialog,
    QAction, QActionGroup, QSizePolicy,
    QStatusBar, QToolBar, QToolButton,
    QLineEdit, QComboBox, QTextEdit, QShortcut, QTabBar
)

from classes import exceptions, info, qt_types, sentry, ui_util, updates
from classes.app import get_app
from classes.exporters.edl import export_edl
from classes.exporters.final_cut_pro import export_xml
from classes.importers.edl import import_edl
from classes.importers.final_cut_pro import import_xml
from classes.logger import log
from classes.metrics import track_metric_session, track_metric_screen
from classes.query import File, Clip, Transition, Marker, Track, Effect
from classes.thumbnail import httpThumbnailServerThread, httpThumbnailException
from classes.time_parts import secondsToTimecode
from classes.timeline import TimelineSync
from classes.title_bar import HiddenTitleBar
from themes.manager import ThemeName
from windows.models.effects_model import EffectsModel
from windows.models.emoji_model import EmojisModel
from windows.models.files_model import FilesModel
from windows.models.transition_model import TransitionsModel
from windows.preview_thread import PreviewParent
from windows.video_widget import VideoWidget
from windows.views.effects_listview import EffectsListView
from windows.views.effects_treeview import EffectsTreeView
from windows.views.emojis_listview import EmojisListView
from windows.views.files_listview import FilesListView
from windows.views.files_treeview import FilesTreeView
from windows.views.properties_tableview import PropertiesTableView, SelectionLabel
from windows.views.timeline import TimelineView
from windows.views.timeline_backend.enums import MenuCopy, MenuSlice
from windows.views.transitions_listview import TransitionsListView
from windows.views.transitions_treeview import TransitionsTreeView
from windows.views.tutorial import TutorialManager


class MainWindow(updates.UpdateWatcher, QMainWindow):
    """ This class contains the logic for the main window widget """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'main-window.ui')

    previewFrameSignal = pyqtSignal(int)
    refreshFrameSignal = pyqtSignal()
    refreshFilesSignal = pyqtSignal()
    refreshTransitionsSignal = pyqtSignal()
    refreshEffectsSignal = pyqtSignal()
    LoadFileSignal = pyqtSignal(str)
    PlaySignal = pyqtSignal()
    PauseSignal = pyqtSignal()
    StopSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    SeekPreviousFrame = pyqtSignal()
    SeekNextFrame = pyqtSignal()
    PlayPauseToggleSignal = pyqtSignal()
    RecoverBackup = pyqtSignal()
    TransformSignal = pyqtSignal(list)
    KeyFrameTransformSignal = pyqtSignal(str, str)
    SelectRegionSignal = pyqtSignal(str)
    MaxSizeChanged = pyqtSignal(object)
    InsertKeyframe = pyqtSignal()
    OpenProjectSignal = pyqtSignal(str)
    ThumbnailUpdated = pyqtSignal(str, int)
    FileUpdated = pyqtSignal(str)
    CaptionTextUpdated = pyqtSignal(str, object)
    CaptionTextLoaded = pyqtSignal(str, object)
    TimelineZoom = pyqtSignal(float)     # Signal to zoom into timeline from zoom slider
    TimelineScrolled = pyqtSignal(list)  # Scrollbar changed signal from timeline
    TimelineResize = pyqtSignal()  # Timeline length changed signal from timeline
    TimelineScroll = pyqtSignal(float)   # Signal to force scroll timeline to specific point
    TimelineCenter = pyqtSignal()        # Signal to force center scroll on playhead
    SelectionAdded = pyqtSignal(str, str, bool)  # Signal to add a selection
    SelectionRemoved = pyqtSignal(str, str)      # Signal to remove a selection
    SelectionChanged = pyqtSignal()      # Signal after selections have been changed (added/removed)
    SetKeyframeFilter = pyqtSignal(str)     # Signal to only show keyframes for the selected property
    IgnoreUpdates = pyqtSignal(bool, bool)     # Signal to let widgets know to ignore updates (i.e. batch updates)
    ThemeChangedSignal = pyqtSignal(object)     # Signal when theme is changed

    # Docks are closable, movable and floatable
    docks_frozen = False

    # Save window settings on close
    def closeEvent(self, event):
        app = get_app()

        # Prompt user to save (if needed)
        if app.project.needs_save():
            log.info('Prompt user to save project')
            # Translate object
            _ = app._tr

            # Handle exception
            ret = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("Save changes to project before closing?"),
                QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger()
                event.accept()
            elif ret == QMessageBox.Cancel:
                # Show tutorial again, if any
                self.tutorial_manager.re_show_dialog()
                # User canceled prompt - don't quit
                event.ignore()
                return

        # If already shutting down, ignore
        # Some versions of Qt fire this CloseEvent() method twice
        if self.shutting_down:
            log.debug("Already shutting down, skipping the closeEvent() method")
            return
        else:
            self.shutting_down = True

        # Log the exit routine
        log.info('---------------- Shutting down -----------------')

        if self.tutorial_manager:
            # Close any tutorial dialogs (if any)
            self.tutorial_manager.hide_dialog()
            self.tutorial_manager.exit_manager()

        # Save settings
        self.save_settings()

        # Track end of session
        track_metric_session(False)

        # Disable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

        # Stop threads
        self.StopSignal.emit()

        # Stop timeline background workers (such as the thumbnail thread) before Qt
        # begins destroying child widgets, to avoid QThread warnings on shutdown.
        timeline_widget = getattr(self, "timeline", None)
        if timeline_widget and getattr(timeline_widget, "thumbnail_manager", None):
            timeline_widget.thumbnail_manager.shutdown()

        # Stop thumbnail server thread (if any)
        if self.http_server_thread:
            self.http_server_thread.kill()

        # Stop ZMQ polling thread (if any)
        if app.logger_libopenshot:
            app.logger_libopenshot.kill()

        # Process any queued events
        QCoreApplication.processEvents()

        # Stop preview thread (and wait for it to end)
        if self.preview_thread:
            self.preview_thread.player.CloseAudioDevice()
            self.preview_thread.kill()
            if self.videoPreview:
                self.videoPreview.deleteLater()
                self.videoPreview = None
            self.preview_parent.Stop()

        # Clean-up Timeline
        if self.timeline_sync and hasattr(self.timeline_sync, 'timeline'):
            # Clear all clips & close all readers
            self.timeline_sync.timeline.Close()
            self.timeline_sync.timeline.Clear()
            self.timeline_sync.timeline = None

        # Destroy lock file
        self.destroy_lock_file()

    def recover_backup(self):
        """Recover the backup file (if any)"""
        log.info("recover_backup")

        # Check for backup file (e.g. backup.flow)
        if os.path.exists(info.BACKUP_FILE):
            # Load recovery project
            log.info("Recovering backup file: %s" % info.BACKUP_FILE)
            self.open_project(info.BACKUP_FILE, clear_thumbnails=False)

            # Clear the file_path (which is set by saving the project)
            project = get_app().project
            project.current_filepath = None
            project.has_unsaved_changes = True

            # Set Window title
            self.SetWindowTitle()

            # Show message to user
            msg = QMessageBox()
            _ = get_app()._tr
            msg.setWindowTitle(_("Backup Recovered"))
            msg.setText(_("Your most recent unsaved project has been recovered."))
            msg.exec_()

        else:
            # No backup project found
            # Load a blank project (to propagate the default settings)
            get_app().project.load("")
            self.actionUndo.setEnabled(False)
            self.actionRedo.setEnabled(False)
            self.actionClearHistory.setEnabled(False)
            self.SetWindowTitle()

    def create_lock_file(self):
        """Create a lock file"""
        lock_path = os.path.join(info.USER_PATH, ".lock")
        # Check if it already exists
        if os.path.exists(lock_path):
            last_log_line = exceptions.libopenshot_crash_recovery()
            if last_log_line:
                log.error(f"Unhandled crash detected: {last_log_line}")
            else:
                log.warning(f"Unhandled shutdown detected: No Log Found")
            self.destroy_lock_file()
        else:
            # Normal startup, clear thumbnails
            self.clear_temporary_files()

        # Reset Sentry component (it can be temporarily changed to libopenshot during
        # the call to libopenshot_crash_recovery above)
        sentry.set_tag("component", "flowcut")

        # Write lock file (try a few times if failure)
        lock_value = str(uuid4())
        for attempt in range(5):
            try:
                # Create lock file
                with open(lock_path, 'w') as f:
                    f.write(lock_value)
                log.debug("Wrote value %s to lock file %s", lock_value, lock_path)
                break
            except OSError:
                log.debug("Failed to write lock file (attempt: %d)", attempt, exc_info=1)
                sleep(0.25)

    def destroy_lock_file(self):
        """Destroy the lock file"""
        lock_path = os.path.join(info.USER_PATH, ".lock")

        # Remove file (try a few times if failure)
        for attempt in range(5):
            try:
                os.remove(lock_path)
                log.debug("Removed lock file {}".format(lock_path))
                break
            except FileNotFoundError:
                break
            except OSError:
                log.debug('Failed to destroy lock file (attempt: %s)' % attempt, exc_info=1)
                sleep(0.25)

    def actionNew_trigger(self):

        app = get_app()
        _ = app._tr  # Get translation function

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("Save changes to project first?"),
                QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger()
            elif ret == QMessageBox.Cancel:
                # User canceled prompt
                return

        # Stop preview thread
        self.SpeedSignal.emit(0)
        self.PauseSignal.emit()

        # Reset selections
        self.clearSelections()

        # Process all events
        QCoreApplication.processEvents()

        # Clear any previous thumbnails
        self.clear_temporary_files()

        # clear data and start new project
        app.project.load("")
        app.updates.reset()
        self.updateStatusChanged(False, False)

        # Load recent projects again
        self.load_recent_menu()

        # Refresh files views
        self.refreshFilesSignal.emit()
        log.info("New Project created.")

        # Set Window title
        self.SetWindowTitle()

        # Seek to frame 0
        self.SeekSignal.emit(1)

        # Update max size (for fast previews)
        self.MaxSizeChanged.emit(self.videoPreview.size())

    def actionAnimatedTitle_trigger(self):
        # show dialog
        from windows.animated_title import AnimatedTitle
        win = AnimatedTitle()
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('animated title add confirmed')
        else:
            log.info('animated title add cancelled')

    def actionAnimation_trigger(self):
        # show dialog
        from windows.animation import Animation
        win = Animation()
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('animation confirmed')
        else:
            log.info('animation cancelled')

    def actionTitle_trigger(self):
        # show dialog
        from windows.title_editor import TitleEditor
        win = TitleEditor()
        # Run the dialog event loop - blocking interaction on this window during that time
        win.exec_()

    def actionEditTitle_trigger(self):
        # Loop through selected files (set 1 selected file if more than 1)
        for f in self.selected_files():
            if f.data.get("path").endswith(".svg"):
                file_path = f.data.get("path")
                file_id = f.id
                break

        if not file_path:
            return

        # show dialog for editing title
        from windows.title_editor import TitleEditor
        win = TitleEditor(edit_file_path=file_path)
        # Run the dialog event loop - blocking interaction on this window during that time
        win.exec_()

        # Update file thumbnail
        self.FileUpdated.emit(file_id)

        # Force update of clips
        for c in Clip.filter(file_id=file_id):
            # update clip
            c.data["reader"]["path"] = file_path
            c.save()

            # Emit thumbnail update signal (to update timeline thumb image)
            self.ThumbnailUpdated.emit(c.id, 1)

        # Update preview
        self.refreshFrameSignal.emit()

    def actionClearAllCache_trigger(self):
        """ Clear all timeline cache - deep clear """
        self.timeline_sync.timeline.ClearAllCache(True)

    def actionDuplicate_trigger(self):
        """Duplicate either the selected file in filesView or the timeline selection."""

        # Check if filesView has focus
        if self.filesView.hasFocus():
            file_path = None

            # Loop through selected files and find the first .svg file
            for f in self.selected_files():
                if f.data.get("path").endswith(".svg"):
                    file_path = f.data.get("path")
                    break

            if not file_path:
                return

            # Show dialog for editing title
            from windows.title_editor import TitleEditor
            win = TitleEditor(edit_file_path=file_path, duplicate=True)
            # Run the dialog event loop (blocking interaction on this window during that time)
            return win.exec_()

        # If filesView doesn't have focus, duplicate timeline selections
        # at the current cursor position
        else:
            self.copyAll()
            self.pasteAll()

    def actionClearWaveformData_trigger(self):
        """Clear audio data from current project"""
        files = File.filter()

        # Transaction id to group all deletes together
        get_app().updates.transaction_id = str(uuid.uuid4())

        for file in files:
            if "audio_data" in file.data.get("ui", {}):
                file_path = file.data.get("path")
                log.debug("File %s has audio data. Deleting it." % os.path.split(file_path)[1])
                del file.data["ui"]["audio_data"]
                file.save()

        clips = Clip.filter()
        for clip in clips:
            if "audio_data" in clip.data.get("ui", {}):
                log.debug("Clip %s has audio data. Deleting it." % clip.id)
                del clip.data["ui"]["audio_data"]
                clip.save()

        # Clear transaction id
        get_app().updates.transaction_id = None

        get_app().window.actionClearWaveformData.setEnabled(False)

    def actionClearHistory_trigger(self):
        """Clear history for current project"""
        project = get_app().project
        project.has_unsaved_changes = True
        get_app().updates.reset()
        log.info('History cleared')

    def save_project(self, file_path):
        """ Save a project to a file path, and refresh the screen """
        with self.lock:
            app = get_app()
            _ = app._tr  # Get translation function

            try:
                # Update history in project data
                s = app.get_settings()
                app.updates.save_history(app.project, s.get("history-limit"))

                # Save recovery file
                self.save_recovery(file_path)

                # Save project to file
                app.project.save(file_path)

                # Set Window title
                self.SetWindowTitle()

                # Load recent projects again
                self.load_recent_menu()

                log.info("Saved project %s", file_path)

            except Exception as ex:
                log.error("Couldn't save project %s", file_path, exc_info=1)
                QMessageBox.warning(self, _("Error Saving Project"), str(ex))

    def save_recovery(self, file_path):
        """Saves the project and manages recovery files based on configured limits."""
        app = get_app()
        s = app.get_settings()
        max_files = s.get("recovery-limit")
        daily_limit = int(max_files * 0.7)
        historical_limit = max_files - daily_limit  # Remaining for previous days

        folder_path, file_name = os.path.split(file_path)
        file_name, file_ext = os.path.splitext(file_name)

        timestamp = int(time())
        recovery_filename = f"{timestamp}-{file_name}.zip"
        recovery_path = os.path.join(info.RECOVERY_PATH, recovery_filename)

        try:
            with zipfile.ZipFile(recovery_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, os.path.basename(file_path))
            log.debug(f"Zipped recovery file created: {recovery_path}")
            self.manage_recovery_files(daily_limit, historical_limit, file_name)
        except Exception as e:
            log.error(f"Failed to create zipped recovery file {recovery_path}: {e}")

    def manage_recovery_files(self, daily_limit, historical_limit, file_name):
        """Ensures recovery files adhere to the configured daily and historical limits."""
        recovery_files = sorted(
            ((f, os.path.getmtime(os.path.join(info.RECOVERY_PATH, f)))
             for f in os.listdir(info.RECOVERY_PATH) if f.endswith(".zip") or f.endswith(info.ALL_PROJECT_EXTS) or f.endswith(info.LEGACY_PROJECT_EXTS)),
            key=lambda x: x[1],
            reverse=True
        )

        project_recovery_files = [
            (f, mod_time) for f, mod_time in recovery_files
            if f"-{file_name}" in f
        ]

        daily_files = []
        historical_files = set()
        retained_files = set()
        now = datetime.now()

        for f, mod_time in project_recovery_files:
            mod_datetime = datetime.fromtimestamp(mod_time)

            if mod_datetime.date() == now.date() and len(daily_files) < daily_limit:
                daily_files.append(f)
                retained_files.add(f)
            elif mod_datetime.date() < now.date() and len(historical_files) < historical_limit:
                if mod_datetime.date() not in historical_files:
                    historical_files.add(mod_datetime.date())
                    retained_files.add(f)

        for f, _ in project_recovery_files:
            if f not in retained_files:
                file_path = os.path.join(info.RECOVERY_PATH, f)
                try:
                    os.unlink(file_path)
                    log.info(f"Deleted excess recovery file: {file_path}")
                except Exception as e:
                    log.error(f"Failed to delete file {file_path}: {e}")

    def open_project(self, file_path, clear_thumbnails=True):
        """ Open a project from a file path, and refresh the screen """

        app = get_app()
        settings = app.get_settings()
        # Set default load-project path to this path.
        settings.setDefaultPath(settings.actionType.LOAD, file_path)
        _ = app._tr  # Get translation function

        # First check for empty file_path (probably user cancellation)
        if not file_path:
            # Ignore the request
            return

        # Stop preview thread
        self.SpeedSignal.emit(0)
        self.PauseSignal.emit()

        # Clear preview selections
        self.videoPreview.clearTransformState()

        # Reset selections
        self.clearSelections()

        # Process all events
        QCoreApplication.processEvents()

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("Save changes to project first?"),
                QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger()
            elif ret == QMessageBox.Cancel:
                # User canceled prompt
                return

        # Set cursor to waiting
        app.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:
            if os.path.exists(file_path):
                # Clear any previous thumbnails
                if clear_thumbnails:
                    self.clear_temporary_files()

                # Load project file
                app.project.load(file_path, clear_thumbnails)

                # Set Window title
                self.SetWindowTitle()

                # Reset undo/redo history
                app.updates.load_history(app.project)

                # Refresh files views
                self.refreshFilesSignal.emit()

                # Refresh thumbnail
                self.refreshFrameSignal.emit()

                # Update max size (for fast previews)
                self.MaxSizeChanged.emit(self.videoPreview.size())

                # Load recent projects again
                self.load_recent_menu()

                log.info("Loaded project {}".format(file_path))
            else:
                log.info("File not found at {}".format(file_path))
                self.statusBar.showMessage(
                    _("Project %s is missing (it may have been moved or deleted). "
                      "It has been removed from the Recent Projects menu." % file_path),
                    5000)
                self.remove_recent_project(file_path)
                self.load_recent_menu()

            # Ensure that playhead, preview thread, and cache all agree that
            # Frame 1 is being previewed
            self.preview_thread.player.Seek(1)
            self.movePlayhead(1)

        except Exception as ex:
            log.error("Couldn't open project %s.", file_path, exc_info=1)
            QMessageBox.warning(self, _("Error Opening Project"), str(ex))

        # Restore normal cursor
        app.restoreOverrideCursor()

    def clear_temporary_files(self):
        """Clear all user thumbnails"""
        for temp_dir in [
                info.get_default_path("THUMBNAIL_PATH"),
                info.get_default_path("BLENDER_PATH"),
                info.get_default_path("TITLE_PATH"),
                info.get_default_path("CLIPBOARD_PATH"),
                ]:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    log.info("Cleared temporary files: %s", temp_dir)
                os.mkdir(temp_dir)
            except Exception:
                log.warning("Failed to clear %s", temp_dir, exc_info=1)

            # Clear any backups
            if os.path.exists(info.BACKUP_FILE):
                try:
                    # Remove backup file
                    os.unlink(info.BACKUP_FILE)
                    log.info("Cleared backup: %s", info.BACKUP_FILE)
                except Exception:
                    log.warning("Could not delete backup file %s",
                                info.BACKUP_FILE, exc_info=1)


    def actionOpen_trigger(self):
        app = get_app()
        _ = app._tr
        s = app.get_settings()
        recommended_folder = s.getDefaultPath(s.actionType.LOAD)

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("Save changes to project first?"),
                QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger()
            elif ret == QMessageBox.Cancel:
                # User canceled prompt
                return

        # Prompt for open project file (accept .flow + legacy extensions)
        file_path = QFileDialog.getOpenFileName(
            self,
            _("Open Project..."),
            recommended_folder,
            _("Flowcut Project (*.flow);;Legacy Project (*.zvn *.osp)"))[0]

        if file_path:
            # Load project file
            self.OpenProjectSignal.emit(file_path)

    def actionSave_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        # Get current filepath if any, otherwise ask user
        file_path = app.project.current_filepath
        if not file_path:
            recommended_folder = s.getDefaultPath(s.actionType.SAVE)
            recommended_path = os.path.join(
                recommended_folder,
                _("Untitled Project") + info.PROJECT_EXT
            )
            file_path = QFileDialog.getSaveFileName(
                self,
                _("Save Project..."),
                recommended_path,
                _("Flowcut Project (*.flow)"))[0]

        if file_path:
            s.setDefaultPath(s.actionType.SAVE, file_path)
            # Append .flow if needed (new save only; existing path kept as-is)
            if not file_path.endswith(info.ALL_PROJECT_EXTS):
                file_path = "%s%s" % (file_path, info.PROJECT_EXT)

            # Save project
            self.save_project(file_path)

    def auto_save_project(self):
        """Auto save the project"""
        import time

        app = get_app()

        # Get current filepath (if any)
        file_path = app.project.current_filepath
        if not app.project.needs_save():
            return

        if file_path:
            # A Real project file exists (keep current path; may be .zvn or .osp)
            # Save project
            log.info("Auto save project file: %s", file_path)
            threading.Thread(target=self.save_project, args=(file_path,), daemon=True).start()

            # Remove backup file (if any)
            if os.path.exists(info.BACKUP_FILE):
                try:
                    # Delete backup since we just saved the actual project
                    os.unlink(info.BACKUP_FILE)
                    log.info(f"Deleted backup file: {info.BACKUP_FILE}")
                except PermissionError:
                    log.warning(f"Permission denied: {info.BACKUP_FILE}. Unable to delete.")
                except Exception as e:
                    log.error(f"Error deleting file {info.BACKUP_FILE}: {e}", exc_info=True)

        else:
            # No saved project found
            log.info("Creating backup of project file: %s", info.BACKUP_FILE)
            app.project.save(info.BACKUP_FILE, backup_only=True)

    def actionSaveAs_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        project_file_path = app.project.current_filepath
        if project_file_path:
            recommended_file_name = os.path.basename(project_file_path)
        else:
            recommended_file_name = "%s%s" % (_("Untitled Project"), info.PROJECT_EXT)
        recommended_folder = s.getDefaultPath(s.actionType.SAVE)
        recommended_path = os.path.join(
            recommended_folder,
            recommended_file_name
        )
        file_path = QFileDialog.getSaveFileName(
            self,
            _("Save Project As..."),
            recommended_path,
            _("Flowcut Project (*.flow)"))[0]
        if file_path:
            s.setDefaultPath(s.actionType.SAVE, file_path)
            # Save As always uses the current project extension
            file_path = os.path.splitext(file_path)[0] + info.PROJECT_EXT

            # Save new project
            threading.Thread(target=self.save_project, args=(file_path,), daemon=True).start()

    def actionImportFiles_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        recommended_path = s.getDefaultPath(s.actionType.IMPORT)

        fd = QFileDialog()
        fd.setDirectory(recommended_path)
        qurl_list = fd.getOpenFileUrls(
            self,
            _("Import Files...")
        )[0]

        # Set cursor to waiting
        app.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:
            # Switch to Files dock
            self.dockFiles.setVisible(True)
            self.dockFiles.raise_()
            self.dockFiles.activateWindow()

            # Import list of files
            self.files_model.process_urls(qurl_list)

            # Refresh files views
            self.refreshFilesSignal.emit()
        finally:
            # Restore cursor
            app.restoreOverrideCursor()

    def invalidImage(self, filename=None):
        """ Show a popup when an image file can't be loaded """
        if not filename:
            return

        # Translations
        _ = get_app()._tr

        # Show message to user
        QMessageBox.warning(
            self,
            None,
            _("%s is not a valid video, audio, or image file.") % filename,
            QMessageBox.Ok
        )

    def promptImageSequence(self, filename=None):
        """ Ask the user whether to import an image sequence """
        if not filename:
            return False

        # Get translations
        app = get_app()
        _ = app._tr

        # Process the event queue first, since we've been ignoring input
        app.processEvents()

        # Display prompt dialog
        ret = QMessageBox.question(
            self,
            _("Import Image Sequence"),
            _("Would you like to import %s as an image sequence?") % filename,
            QMessageBox.No | QMessageBox.Yes
        )
        return ret == QMessageBox.Yes

    def actionAdd_to_Timeline_trigger(self, checked=False):
        # Loop through selected files
        files = self.selected_files()

        # Bail if nothing's selected
        if not files:
            return

        # Get current position of playhead
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        pos = (self.preview_thread.player.Position() - 1) / fps_float

        # show window
        from windows.add_to_timeline import AddToTimeline
        win = AddToTimeline(files, pos)
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('confirmed')
        else:
            log.info('canceled')

    def actionExportVideo_trigger(self, checked=True):
        # show window
        from windows.export import Export
        win = Export()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Export Video add confirmed')
        else:
            log.info('Export Video add cancelled')

    def actionExportEDL_trigger(self, checked=True):
        """Export EDL File"""
        export_edl()

    def actionExportFCPXML_trigger(self, checked=True):
        """Export XML (Final Cut Pro) File"""
        export_xml()

    def actionImportEDL_trigger(self, checked=True):
        """Import EDL File"""
        import_edl()

    def actionImportFCPXML_trigger(self, checked=True):
        """Import XML (Final Cut Pro) File"""
        import_xml()

    def actionUndo_trigger(self, checked=True):
        log.info('actionUndo_trigger')
        get_app().updates.undo()

        # Update the preview
        self.refreshFrameSignal.emit()

    def actionRedo_trigger(self, checked=True):
        log.info('actionRedo_trigger')
        get_app().updates.redo()

        # Update the preview
        self.refreshFrameSignal.emit()

    def actionPreferences_trigger(self, checked=True):
        log.debug("Showing preferences dialog")

        # Stop preview thread
        self.SpeedSignal.emit(0)
        self.PauseSignal.emit()

        # Set cursor to waiting
        get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

        # Show dialog
        from windows.preferences import Preferences
        win = Preferences()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Preferences add confirmed')
        else:
            log.info('Preferences add cancelled')

        # Save settings
        s = get_app().get_settings()
        s.save()

        # Restore normal cursor
        get_app().restoreOverrideCursor()

    def actionFilesShowAll_trigger(self, checked=True):
        self.refreshFilesSignal.emit()

    def actionFilesShowVideo_trigger(self, checked=True):
        self.refreshFilesSignal.emit()

    def actionFilesShowAudio_trigger(self, checked=True):
        self.refreshFilesSignal.emit()

    def actionFilesShowImage_trigger(self, checked=True):
        self.refreshFilesSignal.emit()

    def actionTransitionsShowAll_trigger(self, checked=True):
        self.refreshTransitionsSignal.emit()

    def actionTransitionsShowCommon_trigger(self, checked=True):
        self.refreshTransitionsSignal.emit()

    def actionEffectsShowAll_trigger(self, checked=True):
        self.refreshEffectsSignal.emit()

    def actionEffectsShowVideo_trigger(self, checked=True):
        self.refreshEffectsSignal.emit()

    def actionEffectsShowAudio_trigger(self, checked=True):
        self.refreshEffectsSignal.emit()

    def actionAbout_trigger(self, checked=True):
        """Show about dialog"""
        from windows.about import About
        win = About()
        win.setObjectName("aboutDialog")
        # Run the dialog event loop - blocking interaction on this window during this time
        win.exec_()

    def actionHelpContents_trigger(self, checked=True):
        url = "https://flowcut.app/docs/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the User Guide url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionReportBug_trigger(self, checked=True):
        url = "https://flowcut.app/support/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Bug Report url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionAskQuestion_trigger(self, checked=True):
        url = "https://flowcut.app/community/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the community url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionDiscord_trigger(self, checked=True):
        url = "https://flowcut.app/community/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the community url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionTranslate_trigger(self, checked=True):
        url = "https://flowcut.app/contribute/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Translation url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionDonate_trigger(self, checked=True):
        url = "https://flowcut.app/donate/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Donate url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionUpdate_trigger(self, checked=True):
        url = "https://flowcut.app/download/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Download url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def should_play(self, requested_speed=0):
        """Determine if we should start playback, based on the current frame
        and the total number of frames in our timeline clips. For example,
        if we are at the end of our last clip, and the user clicks play, we
        do not want to start playback."""
        # Get max frame (based on last clip) and current frame
        timeline_sync = get_app().window.timeline_sync
        if timeline_sync and timeline_sync.timeline:
            max_frame = timeline_sync.timeline.GetMaxFrame()
            current_frame = self.preview_thread.current_frame
            if current_frame is not None:
                next_frame = current_frame + requested_speed
                return next_frame <= max_frame and next_frame > 0
        return False

    def actionPlay_trigger(self):
        """Toggle play/pause on video preview"""
        player = self.preview_thread.player
        if player.Mode() == openshot.PLAYBACK_PAUSED:
            # Start playback
            if self.should_play():
                self.PlaySignal.emit()
        else:
            # Pause playback
            self.PauseSignal.emit()

    def actionPreview_File_trigger(self, checked=True):
        """ Preview the selected media file """
        log.info('actionPreview_File_trigger')

        # Loop through selected files (set 1 selected file if more than 1)
        f = self.files_model.current_file()

        # Bail out if no file selected
        if not f:
            log.info("Couldn't find current file for preview window")
            return

        # show dialog
        from windows.cutting import Cutting
        win = Cutting(f, preview=True)
        win.setObjectName("cutting")
        win.show()

    def movePlayhead(self, position_frames):
        """Update playhead position"""
        # Notify preview thread
        if hasattr(self.timeline, 'movePlayhead'):
            self.timeline.movePlayhead(position_frames)

    def SetPlayheadFollow(self, enable_follow):
        """ Enable / Disable follow mode """
        self.timeline.SetPlayheadFollow(enable_follow)

    def actionFastForward_trigger(self, checked=True):
        """Fast forward the video playback"""
        player = self.preview_thread.player
        requested_speed = player.Speed() + 1
        if requested_speed == 0:
            # If paused, fast forward starting at faster than normal playback speed
            requested_speed = 2

        if player.Mode() == openshot.PLAYBACK_PAUSED:
            self.actionPlay_trigger()

        if self.should_play(requested_speed):
            self.SpeedSignal.emit(requested_speed)

    def actionRewind_trigger(self, checked=True):
        """Rewind the video playback"""
        player = self.preview_thread.player
        requested_speed = player.Speed() - 1
        if requested_speed == 0:
            # If paused, rewind starting at normal playback speed (in reverse)
            requested_speed = -1

        if self.should_play(requested_speed):
            if player.Mode() == openshot.PLAYBACK_PAUSED:
                self.actionPlay_trigger()
            self.SpeedSignal.emit(requested_speed)

    def actionJumpStart_trigger(self, checked=True):
        log.debug("actionJumpStart_trigger")

        # Get current player speed/direction
        player = self.preview_thread.player
        current_speed = player.Speed()

        min_frame = 1
        if self.preview_thread and self.preview_thread.timeline:
            min_frame = self.preview_thread.timeline.GetMinFrame()

        # Switch speed back to forward (and then pause)
        # This will allow video caching to start working in the forward direction
        self.SpeedSignal.emit(1)
        self.SpeedSignal.emit(0)

        # Seek to the 1st frame
        self.SeekSignal.emit(min_frame)
        QTimer.singleShot(50, self.actionCenterOnPlayhead_trigger)

        # If playing, continue playing
        if current_speed >= 0:
            self.SpeedSignal.emit(current_speed)
        else:
            # If reversing, pause video
            self.PauseSignal.emit()

    def actionJumpEnd_trigger(self, checked=True):
        log.debug("actionJumpEnd_trigger")

        # Determine last frame (based on clips) & seek there
        max_frame = get_app().window.timeline_sync.timeline.GetMaxFrame()
        self.SeekSignal.emit(max_frame)
        QTimer.singleShot(50, self.actionCenterOnPlayhead_trigger)

    def onPlayCallback(self):
        """Handle when playback is started"""
        # Set icon on Play button
        if self.initialized:
            if get_app().theme_manager:
                theme = get_app().theme_manager.get_current_theme()
                if theme:
                    theme.togglePlayIcon(True)

    def onPauseCallback(self):
        """Handle when playback is paused"""
        # Refresh property window
        self.propertyTableView.select_frame(self.preview_thread.player.Position())

        # Set icon on Pause button
        if self.initialized:
            if get_app().theme_manager:
                theme = get_app().theme_manager.get_current_theme()
                if theme:
                    theme.togglePlayIcon(False)

    def actionSaveFrame_trigger(self, checked=True):
        log.info("actionSaveFrame_trigger")

        # Translate object
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        # Prepare to use the status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Determine path for saved frame - Default export path
        recommended_path = s.getDefaultPath(s.actionType.SAVE)

        framePath = "%s/Frame-%05d.png" % (os.path.basename(recommended_path),
                                           self.preview_thread.current_frame)

        # Ask user to confirm or update framePath
        framePath = QFileDialog.getSaveFileName(self, _("Save Frame..."), framePath, _("Image files (*.png)"))[0]

        if not framePath:
            # No path specified (save frame cancelled)
            self.statusBar.showMessage(_("Save Frame cancelled..."), 5000)
            return
        s.setDefaultPath(s.actionType.SAVE, framePath)

        # Append .png if needed
        if not framePath.endswith(".png"):
            framePath = "%s.png" % framePath

        s.setDefaultPath(s.actionType.EXPORT, framePath)
        log.info("Saving frame to %s", framePath)

        # Pause playback
        self.SpeedSignal.emit(0)
        self.PauseSignal.emit()
        # Temporarily disable playback caching to avoid cache thread races while swapping caches
        lib_settings = openshot.Settings.Instance()
        lib_settings.ENABLE_PLAYBACK_CACHING = False
        try:
            # Save current cache object and create a new CacheMemory object (ignore quality and scale prefs)
            old_cache_object = self.cache_object
            new_cache_object = openshot.CacheMemory(app.get_settings().get("cache-limit-mb") * 1024 * 1024)
            self.timeline_sync.timeline.SetCache(new_cache_object)

            # Set MaxSize to full project resolution and clear cache so we get a full resolution frame
            self.timeline_sync.timeline.SetMaxSize(app.project.get("width"), app.project.get("height"))
            # Deep clear to drop any preview-sized frames cached by clips/readers
            self.timeline_sync.timeline.ClearAllCache(True)

            # Check if file exists, if it does, get the lastModified time
            if os.path.exists(framePath):
                framePathTime = QFileInfo(framePath).lastModified()
            else:
                framePathTime = QDateTime()

            # Get and Save the frame
            # (return is void, so we cannot check for success/fail here
            # - must use file modification timestamp)
            openshot.Timeline.GetFrame(
                self.timeline_sync.timeline, self.preview_thread.current_frame).Save(framePath, 1.0)

            # Show message to user
            if os.path.exists(framePath) and (QFileInfo(framePath).lastModified() > framePathTime):
                self.statusBar.showMessage(_("Saved Frame to %s" % framePath), 5000)
            else:
                self.statusBar.showMessage(_("Failed to save image to %s" % framePath), 5000)

            # Reset the MaxSize to match the preview and reset the preview cache
            viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())
            self.timeline_sync.timeline.SetMaxSize(viewport_rect.width(), viewport_rect.height())
            # Drop the full-res cache entries we created while saving the frame
            self.timeline_sync.timeline.ClearAllCache(True)
            self.cache_object.Clear()
            self.timeline_sync.timeline.SetCache(old_cache_object)
            self.cache_object = old_cache_object
        finally:
            # Restore caching flag
            lib_settings.ENABLE_PLAYBACK_CACHING = True

    def renumber_all_layers(self, insert_at=None, stride=1000000):
        """Renumber all of the project's layers to be equidistant (in
        increments of stride), leaving room for future insertion/reordering.
        Inserts a new track, if passed an insert_at index"""

        app = get_app()

        # Don't track renumbering in undo history
        app.updates.ignore_history = True

        tracks = sorted(app.project.get("layers"), key=lambda x: x['number'])

        log.warning("######## RENUMBERING TRACKS ########")
        log.info("Tracks before: {}".format([{x['number']: x['id']} for x in reversed(tracks)]))

        # Leave placeholder for new track, if insert requested
        if insert_at is not None and int(insert_at) < len(tracks) + 1:
            tracks.insert(int(insert_at), "__gap__")

        # Statistics for end-of-function logging
        renum_count = len(tracks)
        renum_min = stride
        renum_max = renum_count * stride

        # Collect items to renumber
        targets = []
        for (idx, layer) in enumerate(tracks):
            newnum = (idx + 1) * stride

            # Check for insertion placeholder
            if isinstance(layer, str) and layer == "__gap__":
                insert_num = newnum
                continue

            # Look up track info
            oldnum = layer.get('number')
            cur_track = Track.get(number=oldnum)
            if not cur_track:
                log.error('Track number %s not found', oldnum)
                continue

            # Find track elements
            cur_clips = list(Clip.filter(layer=oldnum))
            cur_trans = list(Transition.filter(layer=oldnum))

            # Collect items to be updated with new layer number
            targets.append({
                "number": newnum,
                "track": cur_track,
                "clips": cur_clips,
                "trans": cur_trans,
            })

        # Renumber everything
        for layer in targets:
            try:
                num = layer["number"]
                layer["track"].data["number"] = num
                layer["track"].save()

                for item in layer["clips"] + layer["trans"]:
                    item.data["layer"] = num
                    item.save()
            except (AttributeError, IndexError, ValueError):
                # Ignore references to deleted objects
                continue

        # Re-enable undo tracking for new track insertion
        app.updates.ignore_history = False

        # Create new track and insert at gap point, if requested
        if insert_at is not None:
            track = Track()
            track.data = {"number": insert_num, "y": 0, "label": "", "lock": False}
            track.save()

        log.info("Renumbered {} tracks from {} to {}{}".format(
            renum_count, renum_min, renum_max,
            " (inserted {} at {})".format(insert_num, insert_at) if insert_at else "")
        )

    def actionAddTrack_trigger(self, checked=True):
        log.info("actionAddTrack_trigger")

        # Get # of tracks
        all_tracks = get_app().project.get("layers")
        all_tracks.sort(key=lambda x: x['number'], reverse=True)
        track_number = all_tracks[0].get("number") + 1000000

        # Create new track above existing layer(s)
        track = Track()
        track.data = {"number": track_number, "y": 0, "label": "", "lock": False}
        track.save()

    def actionAddTrackAbove_trigger(self, checked=True):
        # Get selected track
        all_tracks = get_app().project.get("layers")
        selected_layer_id = self.selected_tracks[0]

        log.info("adding track above %s", selected_layer_id)

        # Get track data for selected track
        existing_track = Track.get(id=selected_layer_id)
        if not existing_track:
            # Log error and fail silently
            log.error('No track object found with id: %s', selected_layer_id)
            return
        selected_layer_num = int(existing_track.data["number"])

        # Find track above selected track (if any)
        try:
            tracks = sorted(all_tracks, key=lambda x: x['number'])
            existing_index = tracks.index(existing_track.data)
        except ValueError:
            log.warning("Could not find track %s", selected_layer_num, exc_info=1)
            return
        try:
            next_index = existing_index + 1
            next_layer = tracks[next_index]
            delta = abs(selected_layer_num - next_layer.get('number'))
        except IndexError:
            delta = 2000000

        # Calculate new track number (based on gap delta)
        if delta > 2:
            # New track number (pick mid point in track number gap)
            new_track_num = selected_layer_num + int(round(delta / 2.0))

            # Create new track and insert
            track = Track()
            track.data = {"number": new_track_num, "y": 0, "label": "", "lock": False}
            track.save()
        else:
            # Track numbering is too tight, renumber them all and insert
            self.renumber_all_layers(insert_at=next_index)

        tracks = sorted(get_app().project.get("layers"), key=lambda x: x['number'])

        # Temporarily for debugging
        log.info("Tracks after: {}".format([{x['number']: x['id']} for x in reversed(tracks)]))

    def actionAddTrackBelow_trigger(self, checked=True):
        # Get selected track
        all_tracks = get_app().project.get("layers")
        selected_layer_id = self.selected_tracks[0]

        log.info("adding track below %s", selected_layer_id)

        # Get track data for selected track
        existing_track = Track.get(id=selected_layer_id)
        if not existing_track:
            # Log error and fail silently
            log.error('No track object found with id: %s', selected_layer_id)
            return
        selected_layer_num = int(existing_track.data["number"])

        # Get track below selected track (if any)
        try:
            tracks = sorted(all_tracks, key=lambda x: x['number'])
            existing_index = tracks.index(existing_track.data)
        except ValueError:
            log.warning("Could not find track %s", selected_layer_num, exc_info=1)
            return

        if existing_index > 0:
            prev_index = existing_index - 1
            prev_layer = tracks[prev_index]
            delta = abs(selected_layer_num - prev_layer.get('number'))
        else:
            delta = selected_layer_num

        # Calculate new track number (based on gap delta)
        if delta > 2:
            # New track number (pick mid point in track number gap)
            new_track_num = selected_layer_num - int(round(delta / 2.0))

            log.info("New track num %s (delta %s)", new_track_num, delta)

            # Create new track and insert
            track = Track()
            track.data = {"number": new_track_num, "y": 0, "label": "", "lock": False}
            track.save()
        else:
            # Track numbering is too tight, renumber them all and insert
            self.renumber_all_layers(insert_at=existing_index)

        tracks = sorted(get_app().project.get("layers"), key=lambda x: x['number'])

        # Temporarily for debugging
        log.info("Tracks after: {}".format([{x['number']: x['id']} for x in reversed(tracks)]))

    def actionSnappingTool_trigger(self, checked=True):
        log.info("actionSnappingTool_trigger")
        _ = get_app()._tr

        # Enable / Disable snapping mode
        self.timeline.SetSnappingMode(self.actionSnappingTool.isChecked())
        if self.actionSnappingTool.isChecked():
            self.actionSnappingTool.setText(_("Disable Snapping"))
            self.actionSnappingTool.setToolTip(_("Disable Snapping"))
        else:
            self.actionSnappingTool.setText(_("Enable Snapping"))
            self.actionSnappingTool.setToolTip(_("Enable Snapping"))

    def actionRazorTool_trigger(self, checked=True):
        """Toggle razor tool on and off"""
        log.info('actionRazorTool_trigger')
        _ = get_app()._tr

        # Enable / Disable razor mode
        self.timeline.SetRazorMode(checked)
        if self.actionRazorTool.isChecked():
            self.actionRazorTool.setText(_("Disable Razor"))
            self.actionRazorTool.setToolTip(_("Disable Razor"))
        else:
            self.actionRazorTool.setText(_("Enable Razor"))
            self.actionRazorTool.setToolTip(_("Enable Razor"))

    def actionTimingTool_trigger(self, checked=True):
        """Toggle timing tool on and off"""
        log.info('actionTimingTool_trigger')
        _ = get_app()._tr

        # Enable / Disable timing mode
        self.timeline.SetTimingMode(checked)
        if self.actionTimingTool.isChecked():
            self.actionTimingTool.setText(_("Disable Timing"))
            self.actionTimingTool.setToolTip(_("Disable Timing"))
        else:
            self.actionTimingTool.setText(_("Enable Timing"))
            self.actionTimingTool.setToolTip(_("Enable Timing"))

    def actionAddMarker_trigger(self, checked=True):
        log.info("actionAddMarker_trigger")

        # Get player object
        player = self.preview_thread.player

        # Calculate frames per second
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])

        # Calculate position in seconds
        position = (player.Position() - 1) / fps_float

        # Look for existing Marker
        marker = Marker()
        marker.data = {
            "position": position,
            "icon": "blue.png",
            "vector": "blue",
            }
        marker.save()

    def findAllMarkerPositions(self):
        """Build and return a list of all seekable locations for the currently-selected timeline elements"""

        def getTimelineObjectPositions(obj):
            """Add clip/transition boundaries & keyframes for timeline navigation"""
            positions = []

            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])
            frame_duration = float(fps["den"]) / float(fps["num"])

            clip_start_time = obj.data["position"]
            clip_orig_time = clip_start_time - obj.data["start"]
            # Last frame on clip is -1 frame's duration
            clip_stop_time = clip_orig_time + obj.data["end"] - frame_duration

            # add clip boundaries
            positions.append(clip_start_time)
            positions.append(clip_stop_time)

            # add all object keyframes
            for property in obj.data:
                try:
                    # Try looping through keyframe points
                    for point in obj.data[property]["Points"]:
                        keyframe_time = (point["co"]["X"]-1)/fps_float - obj.data["start"] + obj.data["position"]
                        if clip_start_time < keyframe_time < clip_stop_time:
                            positions.append(keyframe_time)
                except (TypeError, KeyError):
                    pass
                try:
                    # Try looping through color keyframe points
                    for point in obj.data[property]["red"]["Points"]:
                        keyframe_time = (point["co"]["X"]-1)/fps_float - obj.data["start"] + obj.data["position"]
                        if clip_start_time < keyframe_time < clip_stop_time:
                            positions.append(keyframe_time)
                except (TypeError, KeyError):
                    pass

            return positions

        # We can always jump to the beginning of the timeline
        all_marker_positions = [0]
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        frame_duration = float(fps["den"]) / float(fps["num"])

        # If nothing is selected, also add the end of the last clip
        if not self.selected_clips + self.selected_transitions + self.selected_effects:
            all_marker_positions.append(
                # last frame is -1 frame's duration
                get_app().window.timeline_sync.timeline.GetMaxTime() - frame_duration)

        # Get list of marker and important positions (like selected clip bounds)
        for marker in Marker.filter():
            all_marker_positions.append(marker.data["position"])

        if self.selected_effects:
            # Only include keyframes for selected effects
            for effect_id in self.selected_effects:
                effect = Effect.get(id=effect_id)
                if not effect:
                    continue
                parent = effect.parent
                clip_start_time = parent["position"]
                clip_orig_time = clip_start_time - parent["start"]
                clip_stop_time = clip_orig_time + parent["end"] - frame_duration
                # Always include parent clip boundaries
                all_marker_positions.extend([clip_start_time, clip_stop_time])
                for prop in effect.data:
                    try:
                        for point in effect.data[prop]["Points"]:
                            keyframe_time = (point["co"]["X"]-1)/fps_float + clip_orig_time
                            if clip_start_time < keyframe_time < clip_stop_time:
                                all_marker_positions.append(keyframe_time)
                    except (TypeError, KeyError):
                        pass
                    try:
                        for point in effect.data[prop]["red"]["Points"]:
                            keyframe_time = (point["co"]["X"]-1)/fps_float + clip_orig_time
                            if clip_start_time < keyframe_time < clip_stop_time:
                                all_marker_positions.append(keyframe_time)
                    except (TypeError, KeyError):
                        pass
        else:
            # Loop through selected clips (and add key positions)
            for clip_id in self.selected_clips:
                selected_clip = Clip.get(id=clip_id)
                if selected_clip:
                    all_marker_positions.extend(getTimelineObjectPositions(selected_clip))

            # Loop through selected transitions (and add key positions)
            for tran_id in self.selected_transitions:
                selected_tran = Transition.get(id=tran_id)
                if selected_tran:
                    all_marker_positions.extend(getTimelineObjectPositions(selected_tran))

        # remove duplicates
        all_marker_positions = list(set(all_marker_positions))

        return all_marker_positions

    def actionPreviousMarker_trigger(self, checked=True):
        log.info("actionPreviousMarker_trigger")

        # Calculate current position (in seconds)
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = (self.preview_thread.current_frame - 1) / fps_float
        all_marker_positions = self.findAllMarkerPositions()

        # Loop through all markers, and find the closest one to the left
        closest_position = None
        for marker_position in sorted(all_marker_positions):
            # Is marker smaller than position?
            if marker_position < current_position and (abs(marker_position - current_position) > 0.001):
                # Is marker larger than previous marker
                if closest_position and marker_position > closest_position:
                    # Set a new closest marker
                    closest_position = marker_position
                elif not closest_position:
                    # First one found
                    closest_position = marker_position

        # Seek to marker position (if any)
        if closest_position is not None:
            # Seek
            frame_to_seek = round(closest_position * fps_float) + 1
            self.SeekSignal.emit(frame_to_seek)

            # Update the preview and reselect current frame in properties
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(frame_to_seek)

    def actionNextMarker_trigger(self, checked=True):
        log.info("actionNextMarker_trigger")

        # Calculate current position (in seconds)
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = (self.preview_thread.current_frame - 1) / fps_float
        all_marker_positions = self.findAllMarkerPositions()

        # Loop through all markers, and find the closest one to the right
        closest_position = None
        for marker_position in sorted(all_marker_positions):
            # Is marker smaller than position?
            if marker_position > current_position and (abs(marker_position - current_position) > 0.001):
                # Is marker larger than previous marker
                if closest_position and marker_position < closest_position:
                    # Set a new closest marker
                    closest_position = marker_position
                elif not closest_position:
                    # First one found
                    closest_position = marker_position

        # Seek to marker position (if any)
        if closest_position is not None:
            # Seek
            frame_to_seek = round(closest_position * fps_float) + 1
            self.SeekSignal.emit(frame_to_seek)

            # Update the preview and reselct current frame in properties
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(frame_to_seek)

    def actionCenterOnPlayhead_trigger(self, checked=True):
        """ Center the timeline on the current playhead position """
        self.timeline.centerOnPlayhead()

    def handleSeekPreviousFrame(self):
        """Handle previous-frame keypress"""
        player = get_app().window.preview_thread.player
        frame_num = player.Position() - 1

        # Seek to previous frame
        get_app().window.PauseSignal.emit()
        get_app().window.SpeedSignal.emit(0)
        get_app().window.previewFrameSignal.emit(frame_num)

        # Notify properties dialog
        get_app().window.propertyTableView.select_frame(frame_num)

    def handleSeekNextFrame(self):
        """Handle next-frame keypress"""
        player = get_app().window.preview_thread.player
        frame_num = player.Position() + 1

        # Seek to next frame
        get_app().window.PauseSignal.emit()
        get_app().window.SpeedSignal.emit(0)
        get_app().window.previewFrameSignal.emit(frame_num)

        # Notify properties dialog
        get_app().window.propertyTableView.select_frame(frame_num)

    def handlePlayPauseToggleSignal(self):
        """Handle play-pause-toggle keypress"""
        player = get_app().window.preview_thread.player
        frame_num = player.Position()

        # Toggle Play/Pause
        get_app().window.actionPlay_trigger()

        # Notify properties dialog
        get_app().window.propertyTableView.select_frame(frame_num)

    def getShortcutByName(self, setting_name):
        """Get a list of key sequences from the setting name."""
        s = get_app().get_settings()
        shortcut_value = s.get(setting_name)
        if shortcut_value:
            # Split the setting value by the pipe '|' delimiter for multiple shortcuts
            shortcut_parts = shortcut_value.split('|')

            # Create a list of QKeySequence objects from the parts
            return [QKeySequence(part.strip()) for part in shortcut_parts if part.strip()]
        return []

    def getAllKeyboardShortcuts(self):
        """ Get a key sequence back from the setting name """
        keyboard_shortcuts = []
        all_settings = get_app().get_settings()._data
        for setting in all_settings:
            if setting.get('category') == 'Keyboard' and setting.get('type') == 'text':
                keyboard_shortcuts.append(setting)
        return keyboard_shortcuts

    def initShortcuts(self):
        """Initialize / update QShortcuts for the main window actions."""

        # Store all QShortcuts so they don't go out of scope
        if not hasattr(self, 'shortcuts'):
            self.shortcuts = []

        # Clear previous QShortcuts
        for shortcut in self.shortcuts:
            shortcut.setParent(None)  # Remove shortcuts by clearing parent
        self.shortcuts.clear()

        # Set to track all key sequences and prevent duplication
        used_shortcuts = set()

        # Automatically create shortcuts that follow the pattern self.SHORTCUTNAME
        for shortcut in self.getAllKeyboardShortcuts():
            method_name = shortcut.get('setting')

            # Get list of key sequences (divided by | delimiter)
            shortcut_sequences = self.getShortcutByName(method_name)

            # Remove any trailing numbers from the method name (i.e., strip suffix for alternates)
            base_method_name = re.sub(r'\d+$', '', method_name)

            # Apply the shortcuts to the corresponding QAction or method
            if hasattr(self, base_method_name):
                obj = getattr(self, base_method_name)

                key_sequences = [QKeySequence(seq) for seq in shortcut_sequences if seq]  # Create QKeySequence list

                if isinstance(obj, QAction):
                    # Handle QAction with multiple key sequences using setShortcuts()
                    obj.setShortcuts(key_sequences)
                else:
                    # If it's a method, create QShortcuts for each key sequence
                    for key_seq_obj in key_sequences:
                        if key_seq_obj not in used_shortcuts:  # Avoid assigning duplicate shortcuts
                            qshortcut = QShortcut(key_seq_obj, self, activated=obj, context=Qt.WindowShortcut)
                            self.shortcuts.append(qshortcut)  # Keep reference to avoid garbage collection
                            used_shortcuts.add(key_seq_obj)  # Track the shortcut as used
                        else:
                            log.warning(f"Duplicate shortcut {key_seq_obj.toString()} detected for {base_method_name}. Skipping.")
            else:
                log.warning(f"Shortcut {base_method_name} does not have a matching method or QAction.")

        # Log shortcut initialization completion
        log.debug("Shortcuts initialized or updated.")

    def actionProfileDefault_trigger(self, profile=None):
        # Set default profile in settings
        s = get_app().get_settings()
        if profile:
            s.set("default-profile", profile.info.description)
            log.info(f"Setting default profile to '{profile.info.description}'")

    def actionProfileEdit_trigger(self, profile=None, duplicate=False, delete=False, parent=None):
        # Show profile edit dialog
        from windows.profile_edit import EditProfileDialog
        log.debug("Showing profile edit dialog")

        # get translations
        _ = get_app()._tr

        if profile and delete and parent:
            # Delete profile (no dialog)
            error_title = _("Profile Error")
            error_message = _("You can not delete the <b>current</b> or <b>default</b> profile.")
            if os.path.exists(profile.path):
                if (profile.info.description.strip() == get_app().project.get(['profile']).strip() or
                    profile.info.description.strip() == get_app().get_settings().get('default-profile').strip()):
                    QMessageBox.warning(parent, error_title, error_message)
                    return

                log.info(f"Removing custom profile: {profile.path}")
                os.unlink(profile.path)
            parent.profiles_model.remove_row(profile)
        else:
            # Show edit dialog
            win = EditProfileDialog(profile, duplicate)
            result = win.exec_()
            if result == QDialog.Accepted:
                profile = win.profile
                if parent:
                    # Update model and refresh view
                    parent.profiles_model.update_or_insert_row(profile)
                    parent.refresh_view(parent.parent.txtProfileFilter.text())
                else:
                    # Choose the edited profile
                    self.actionProfile_trigger(profile)

    def actionProfile_trigger(self, profile=None):
        # Disable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

        # Show Profile dialog (if profile not passed)
        if not profile:
            # Show dialog
            from windows.profile import Profile
            log.debug("Showing profile dialog")

            # Get current project profile description
            current_project_profile_desc = get_app().project.get(['profile'])

            win = Profile(current_project_profile_desc)
            result = win.exec_()
            profile = win.selected_profile
        else:
            # Profile passed in already
            result = QDialog.Accepted

        # Update profile (if changed)
        if result == QDialog.Accepted and profile:
            # Clear any selections before changing the project profile
            # to prevent invalid selection state from causing crashes
            self.clearSelections()

            proj = get_app().project

            # Group transactions
            tid = str(uuid.uuid4())

            # Get current FPS (prior to changing)
            current_fps = proj.get("fps")
            current_fps_float = float(current_fps["num"]) / float(current_fps["den"])
            fps_factor = float(profile.info.fps.ToFloat() / current_fps_float)

            # Get current playback frame
            current_frame = self.preview_thread.current_frame
            adjusted_frame = round(current_frame * fps_factor)

            # Update timeline settings
            get_app().updates.transaction_id = tid

            # Apply new profile (and any FPS precision updates)
            get_app().updates.update(["profile"], profile.info.description)
            get_app().updates.update(["width"], profile.info.width)
            get_app().updates.update(["height"], profile.info.height)
            get_app().updates.update(["display_ratio"], {"num": profile.info.display_ratio.num, "den": profile.info.display_ratio.den})
            get_app().updates.update(["pixel_ratio"], {"num": profile.info.pixel_ratio.num, "den": profile.info.pixel_ratio.den})
            get_app().updates.update(["fps"], {"num": profile.info.fps.num, "den": profile.info.fps.den})

            # Clear transaction id
            get_app().updates.transaction_id = None

            # Seek to the same location, adjusted for new frame rate
            self.SeekSignal.emit(adjusted_frame)

            # Refresh frame (since size of preview might have changed)
            QTimer.singleShot(500, self.refreshFrameSignal.emit)
            QTimer.singleShot(500, functools.partial(self.MaxSizeChanged.emit,
                                                     self.videoPreview.size()))

        # Enable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

    def actionSplitFile_trigger(self):
        log.debug("actionSplitFile_trigger")

        # Loop through selected files (set 1 selected file if more than 1)
        f = self.files_model.current_file()

        # Bail out if no file selected
        if not f:
            log.warn("Split file action failed, couldn't find current file")
            return

        # show dialog
        from windows.cutting import Cutting
        win = Cutting(f)
        win.setObjectName("cutting")
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Cutting Finished')
        else:
            log.info('Cutting Cancelled')

    def actionRemove_from_Project_trigger(self):
        log.debug("actionRemove_from_Project_trigger")

        # Transaction id to group all deletes together
        get_app().updates.transaction_id = str(uuid.uuid4())

        # Loop through selected files
        for f in self.selected_files():
            if not f:
                continue

            # Find matching clips (if any)
            clips = Clip.filter(file_id=f.data.get("id"))
            for c in clips:
                # Clear selected clips (and update properties and transform handles - to prevent crashes)
                self.removeSelection(c.id, "clip")
                self.emit_selection_signal()
                self.show_property_timeout()

                # Remove clip
                c.delete()

            # Remove file (after clips are deleted)
            f.delete()

        # Clear transaction id
        get_app().updates.transaction_id = None

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionRemoveClip_trigger(self):
        log.debug('actionRemoveClip_trigger')

        locked_tracks = [l.get("number") for l in get_app().project.get('layers') if l.get("lock", False)]

        # Loop through selected clips
        for clip_id in json.loads(json.dumps(self.selected_clips)):
            # Find matching file
            clips = Clip.filter(id=clip_id)
            clips = list(filter(lambda x: x.data.get("layer") not in locked_tracks, clips))
            for c in clips:
                # Clear selected clips
                self.removeSelection(clip_id, "clip")
                self.emit_selection_signal()
                self.show_property_timeout()

                # Remove clip
                c.delete()

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionRippleDelete(self):
        log.debug('actionRippleDelete_trigger')

        locked_tracks = [l.get("number") for l in get_app().project.get('layers') if l.get("lock", False)]

        # Set transaction id (if not already set)
        get_app().updates.transaction_id = get_app().updates.transaction_id or str(uuid.uuid4())

        # Emit signal to ignore updates (start ignoring updates)
        get_app().window.IgnoreUpdates.emit(True, True)

        try:
            # Loop through each selected clip, delete it, and ripple the remaining clips on the same layer
            for clip_id in json.loads(json.dumps(self.selected_clips)):
                clips = Clip.filter(id=clip_id)
                clips = list(filter(lambda x: x.data.get("layer") not in locked_tracks, clips))
                for c in clips:
                    start_position = float(c.data["position"])
                    duration = float(c.data["end"]) - float(c.data["start"])

                    self.removeSelection(c.id, "clip")
                    self.emit_selection_signal()
                    self.show_property_timeout()
                    c.delete()

                    # After deleting, ripple the remaining clips on the same layer
                    self.ripple_delete_gap(start_position, c.data["layer"], duration)

            # Loop through each selected transition, delete it, and ripple the remaining transitions on the same layer
            for transition_id in json.loads(json.dumps(self.selected_transitions)):
                transitions = Transition.filter(id=transition_id)
                transitions = list(filter(lambda x: x.data.get("layer") not in locked_tracks, transitions))
                for t in transitions:
                    start_position = float(t.data["position"])
                    duration = float(t.data["end"]) - float(t.data["start"])

                    self.removeSelection(t.id, "transition")
                    self.emit_selection_signal()
                    self.show_property_timeout()
                    t.delete()

                    # After deleting, ripple the remaining transitions on the same layer
                    self.ripple_delete_gap(start_position, t.data["layer"], duration)

        finally:
            # Emit signal to resume updates (stop ignoring updates)
            get_app().window.IgnoreUpdates.emit(False, True)

            # Clear transaction id
            get_app().updates.transaction_id = None

            # Refresh preview
            get_app().window.refreshFrameSignal.emit()

    def ripple_delete_gap(self, ripple_start, layer, total_gap):
        """Remove the ripple gap and adjust subsequent items on the same layer"""
        clips = [clip for clip in Clip.filter(layer=layer) if clip.data.get("position", 0.0) > ripple_start]
        transitions = [tran for tran in Transition.filter(layer=layer) if tran.data.get("position", 0.0) > ripple_start]

        for clip in clips:
            clip.data["position"] -= total_gap
            clip.save()

        for trans in transitions:
            trans.data["position"] -= total_gap
            trans.save()

    def actionRippleSelect(self):
        """Selects ALL clips or transitions to the right of the current selected item"""
        for clip_id in self.selected_clips:
            self.timeline.addRippleSelection(clip_id, "clip")
        for tran_id in self.selected_transitions:
            self.timeline.addRippleSelection(tran_id, "transition")

    def actionRippleSliceKeepLeft(self):
        """Slice and keep the left side of a clip/transition, and then ripple the position change to the right."""
        self.slice_clips(MenuSlice.KEEP_LEFT, selected_only=True, ripple=True)

    def actionRippleSliceKeepRight(self):
        """Slice and keep the right side of a clip/transition, and then ripple the position change to the right."""
        self.slice_clips(MenuSlice.KEEP_RIGHT, selected_only=True, ripple=True)

    def actionProperties_trigger(self):
        log.debug('actionProperties_trigger')

        # Show properties dock
        if not self.dockProperties.isVisible():
            self.dockProperties.show()

    def actionRemoveEffect_trigger(self):
        log.debug('actionRemoveEffect_trigger')

        # Loop through selected clips
        for effect_id in json.loads(json.dumps(self.selected_effects)):
            log.info("effect id: %s" % effect_id)

            # Find matching file
            clips = Clip.filter()
            found_effect = None
            for c in clips:
                found_effect = False
                log.info("c.data[effects]: %s" % c.data["effects"])

                for effect in c.data["effects"]:
                    if effect["id"] == effect_id:
                        found_effect = effect
                        break

                if found_effect:
                    # Remove found effect from clip data and save clip
                    c.data["effects"].remove(found_effect)

                    # Remove unneeded attributes from JSON
                    c.data.pop("reader")

                    # Save clip
                    c.save()

                    # Clear selected effects
                    self.removeSelection(effect_id, "effect")

        # Refresh preview
        self.refreshFrameSignal.emit()

    def actionRemoveTransition_trigger(self):
        log.debug('actionRemoveTransition_trigger')

        locked_tracks = [l.get("number")
                         for l in get_app().project.get('layers')
                         if l.get("lock", False)]

        # Loop through selected clips
        for tran_id in json.loads(json.dumps(self.selected_transitions)):
            # Find matching file
            transitions = Transition.filter(id=tran_id)
            transitions = list(filter(lambda x: x.data.get("layer") not in locked_tracks, transitions))
            for t in transitions:
                # Clear selected clips
                self.removeSelection(tran_id, "transition")
                self.emit_selection_signal()
                self.show_property_timeout()

                # Remove transition
                t.delete()

        # Refresh preview
        self.refreshFrameSignal.emit()

    def actionRemoveTrack_trigger(self):
        log.debug('actionRemoveTrack_trigger')

        # Get translation function
        _ = get_app()._tr

        # Transaction id to group all deletes together
        get_app().updates.transaction_id = str(uuid.uuid4())

        track_id = self.selected_tracks[0]
        max_track_number = len(get_app().project.get("layers"))

        # Get details of selected track
        selected_track = Track.get(id=track_id)
        selected_track_number = int(selected_track.data["number"])

        # Don't allow user to delete final track
        if max_track_number == 1:
            # Show error and do nothing
            QMessageBox.warning(self, _("Error Removing Track"), _("You must keep at least 1 track"))
            return

        # Remove all clips on this track first
        for clip in Clip.filter(layer=selected_track_number):
            # Clear selected clips (and immediately update properties/handles to avoid stale references)
            self.removeSelection(clip.id, "clip")
            self.emit_selection_signal()
            self.show_property_timeout()
            clip.delete()

        # Remove all transitions on this track first
        for trans in Transition.filter(layer=selected_track_number):
            self.removeSelection(trans.id, "transition")
            self.emit_selection_signal()
            self.show_property_timeout()
            trans.delete()

        # Remove track
        selected_track.delete()

        # Clear transaction id
        get_app().updates.transaction_id = None

        # Clear selected track
        self.selected_tracks = []

        # Refresh preview
        self.refreshFrameSignal.emit()

    def actionLockTrack_trigger(self):
        """Callback for locking a track"""
        log.debug('actionLockTrack_trigger')

        # Get details of track
        track_id = self.selected_tracks[0]
        selected_track = Track.get(id=track_id)

        # Lock track and save
        selected_track.data['lock'] = True
        selected_track.save()

    def actionUnlockTrack_trigger(self):
        """Callback for unlocking a track"""
        log.info('actionUnlockTrack_trigger')

        # Get details of track
        track_id = self.selected_tracks[0]
        selected_track = Track.get(id=track_id)

        # Lock track and save
        selected_track.data['lock'] = False
        selected_track.save()

    def actionRenameTrack_trigger(self):
        """Callback for renaming track"""
        log.info('actionRenameTrack_trigger')

        # Get translation function
        _ = get_app()._tr

        # Get details of track
        track_id = self.selected_tracks[0]
        selected_track = Track.get(id=track_id)

        # Find display track number
        all_tracks = get_app().project.get("layers")
        display_count = len(all_tracks)
        for track in reversed(sorted(all_tracks, key=lambda x: x['number'])):
            if track.get("id") == track_id:
                break
            display_count -= 1

        track_name = selected_track.data["label"] or _("Track %s") % display_count

        text, ok = QInputDialog.getText(self, _('Rename Track'), _('Track Name:'), text=track_name)
        if ok:
            # Update track
            selected_track.data["label"] = text
            selected_track.save()

    def actionRemoveMarker_trigger(self):
        log.info('actionRemoveMarker_trigger')

        for marker_id in self.selected_markers:
            marker = Marker.filter(id=marker_id)
            for m in marker:
                # Remove track
                m.delete()

    def actionZoomToTimeline(self):
        self.sliderZoomWidget.zoomToTimeline()

    def actionTimelineZoomIn_trigger(self):
        self.sliderZoomWidget.zoomIn()

    def actionTimelineZoomOut_trigger(self):
        self.sliderZoomWidget.zoomOut()

    def actionFullscreen_trigger(self):
        # Toggle fullscreen state (current state mask XOR WindowFullScreen)
        self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)

    def actionFile_Properties_trigger(self):
        log.info("Show file properties")

        # Get current selected file (corresponding to menu, if possible)
        f = self.files_model.current_file()
        if not f:
            log.warning("Couldn't find current file for properties window")
            return

        # show dialog
        from windows.file_properties import FileProperties
        win = FileProperties(f)
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('File Properties Finished')
        else:
            log.info('File Properties Cancelled')

    def actionExportFiles_trigger(self):
        from windows.export_clips import clipExportWindow
        f = self.selected_files()
        exp = clipExportWindow(export_clips_arg=f)
        try:
            exp.exec_()
        except:
            log.info("Error in export clips dialog")

    def actionDetailsView_trigger(self):
        log.info("Switch to Details View")

        # Get settings
        app = get_app()
        s = app.get_settings()

        # Files
        if app.context_menu_object == "files":
            s.set("file_view", "details")
            self.filesListView.hide()
            self.filesView = self.filesTreeView
            self.filesView.show()

        # Transitions
        elif app.context_menu_object == "transitions":
            s.set("transitions_view", "details")
            self.transitionsListView.hide()
            self.transitionsView = self.transitionsTreeView
            self.transitionsView.show()

        # Effects
        elif app.context_menu_object == "effects":
            s.set("effects_view", "details")
            self.effectsListView.hide()
            self.effectsView = self.effectsTreeView
            self.effectsView.show()

    def actionThumbnailView_trigger(self):
        log.info("Switch to Thumbnail View")

        # Get settings
        app = get_app()
        s = app.get_settings()

        # Files
        if app.context_menu_object == "files":
            s.set("file_view", "thumbnail")
            self.filesTreeView.hide()
            self.filesView = self.filesListView
            self.filesView.show()

        # Transitions
        elif app.context_menu_object == "transitions":
            s.set("transitions_view", "thumbnail")
            self.transitionsTreeView.hide()
            self.transitionsView = self.transitionsListView
            self.transitionsView.show()

        # Effects
        elif app.context_menu_object == "effects":
            s.set("effects_view", "thumbnail")
            self.effectsTreeView.hide()
            self.effectsView = self.effectsListView
            self.effectsView.show()

    def resize_contents(self):
        if self.filesView == self.filesTreeView:
            self.filesTreeView.resize_contents()

    def getDocks(self):
        """ Get a list of all dockable widgets """
        return self.findChildren(QDockWidget)

    def removeDocks(self):
        """ Remove all dockable widgets on main screen """
        for dock in self.getDocks():
            if self.dockWidgetArea(dock) != Qt.NoDockWidgetArea:
                self.removeDockWidget(dock)

    def addDocks(self, docks, area):
        """ Add all dockable widgets to the same dock area on the main screen """
        for dock in docks:
            self.addDockWidget(area, dock)

    def floatDocks(self, is_floating):
        """ Float or Un-Float all dockable widgets above main screen """
        for dock in self.getDocks():
            if self.dockWidgetArea(dock) != Qt.NoDockWidgetArea:
                dock.setFloating(is_floating)

    def showDocks(self, docks):
        """ Show all dockable widgets on the main screen """
        for dock in docks:
            if self.dockWidgetArea(dock) != Qt.NoDockWidgetArea:
                # Only show correctly docked widgets
                dock.show()

    def freezeDock(self, dock, frozen=True):
        """ Freeze/unfreeze a dock widget on the main screen."""
        if self.dockWidgetArea(dock) == Qt.NoDockWidgetArea:
            # Don't freeze undockable widgets
            return
        if frozen:
            dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        else:
            features = (
                QDockWidget.DockWidgetFloatable
                | QDockWidget.DockWidgetMovable)
            if dock is not self.dockTimeline:
                features |= QDockWidget.DockWidgetClosable
            dock.setFeatures(features)

    @pyqtSlot()
    def freezeMainToolBar(self, frozen=None):
        """Freeze/unfreeze the toolbar if it's attached to the window."""
        if frozen is None:
            frozen = self.docks_frozen
        floating = self.toolBar.isFloating()
        log.debug(
            "%s main toolbar%s",
            "freezing" if frozen and not floating else "unfreezing",
            " (floating)" if floating else "")
        if floating:
            self.toolBar.setMovable(True)
        else:
            self.toolBar.setMovable(not frozen)

    def addViewDocksMenu(self):
        """ Insert a Docks submenu into the View menu """
        _ = get_app()._tr

        self.docks_menu = self.menuView.addMenu(_("Docks"))
        for dock in sorted(self.getDocks(), key=lambda d: d.windowTitle()):
            if (dock.features() & QDockWidget.DockWidgetClosable
               != QDockWidget.DockWidgetClosable):
                # Skip non-closable docs
                continue
            self.docks_menu.addAction(dock.toggleViewAction())

    def actionSimple_View_trigger(self):
        """ Switch to the default / simple view  """
        self.removeDocks()

        # Add Docks
        self.addDocks([
            self.dockFiles,
            self.dockTransitions,
            self.dockEffects,
            self.dockEmojis,
            self.dockVideo,
            self.dockAIChat,
            ], Qt.TopDockWidgetArea)

        self.floatDocks(False)
        self.tabifyDockWidget(self.dockFiles, self.dockTransitions)
        self.tabifyDockWidget(self.dockTransitions, self.dockEffects)
        self.tabifyDockWidget(self.dockEffects, self.dockEmojis)
        self.showDocks([
            self.dockFiles,
            self.dockTransitions,
            self.dockEffects,
            self.dockEmojis,
            self.dockVideo,
        ])
        # Keep AI Chat dock hidden but accessible via menu
        self.dockAIChat.hide()

        # Set initial size of docks
        simple_state = "".join([
            "AAAA/wAAAAD9AAAAAwAAAAAAAAEnAAAC3/wCAAAAA/wAAAJeAAAApwAAAAAA////+gAAAAACAAAAAfsAAAAYAGQAbwBjAGsASwBlAHkAZgByAGEAbQBlAAAAAAD/////AAAAAAAAAAD7AAAAHABkAG8AYwBrAFAAcgBvAHAAZQByAHQAaQBlAHMAAAAAJwAAAt8AAAChAP////sAAAAYAGQAbwBjAGsAVAB1AHQAbwByAGkAYQBsAgAABUQAAAF6AAABYAAAANwAAAABAAABHAAAAUD8AgAAAAH7AAAAGABkAG8AYwBrAEsAZQB5AGYAcgBhAG0AZQEAAAFYAAAAFQAAAAAAAAAAAAAAAgAABEYAAALC/AEAAAAC/AAAAAAAAARGAAAA+gD////8AgAAAAL8AAAAPQAAAa4AAACvAP////wBAAAAAvwAAAAAAAABwQAAAJcA////+gAAAAACAAAABPsAAAASAGQAbwBjAGsARgBpAGwAZQBzAQAAAAD/////AAAAkgD////7AAAAHgBkAG8AYwBrAFQAcgBhAG4AcwBpAHQAaQBvAG4AcwEAAAAA/////wAAAJIA////+wAAABYAZABvAGMAawBFAGYAZgBlAGMAdABzAQAAAAD/////AAAAkgD////7AAAAFABkAG8AYwBrAEUAbQBvAGoAaQBzAQAAAAD/////AAAAkgD////7AAAAEgBkAG8AYwBrAFYAaQBkAGUAbwEAAAHHAAACfwAAAEcA////+wAAABgAZABvAGMAawBUAGkAbQBlAGwAaQBuAGUBAAAB8QAAAQ4AAACWAP////sAAAAiAGQAbwBjAGsAQwBhAHAAdABpAG8AbgBFAGQAaQB0AG8AcgAAAANtAAAA2QAAAFgA////AAAERgAAAAEAAAABAAAAAgAAAAEAAAAC/AAAAAEAAAACAAAAAQAAAA4AdABvAG8AbABCAGEAcgEAAAAA/////wAAAAAAAAAA"
        ])
        self.restoreState(qt_types.str_to_bytes(simple_state))
        QCoreApplication.processEvents()

    def actionAdvanced_View_trigger(self):
        """ Switch to an alternative view """
        self.removeDocks()

        # Add Docks
        self.addDocks([self.dockFiles, self.dockVideo], Qt.TopDockWidgetArea)
        self.addDocks([
            self.dockEffects,
            self.dockTransitions,
            self.dockEmojis,
            self.dockAIChat,
            ], Qt.RightDockWidgetArea)
        self.addDocks([self.dockProperties], Qt.LeftDockWidgetArea)

        self.floatDocks(False)
        self.tabifyDockWidget(self.dockEmojis, self.dockEffects)
        self.showDocks([
            self.dockFiles,
            self.dockTransitions,
            self.dockVideo,
            self.dockEffects,
            self.dockEmojis,
            self.dockProperties,
        ])
        # Keep AI Chat dock hidden but accessible via menu
        self.dockAIChat.hide()

        # Set initial size of docks
        advanced_state = "".join([
            "AAAA/wAAAAD9AAAAAwAAAAAAAADxAAAC3/wCAAAAAvsAAAAcAGQAbwBjAGsAUAByAG8AcABlAHIAdABpAGUAcw"
            "EAAAAnAAAC3wAAAKEA/////AAAAl4AAACnAAAAAAD////6AAAAAAIAAAAB+wAAABgAZABvAGMAawBLAGUAeQBm"
            "AHIAYQBtAGUAAAAAAP////8AAAAAAAAAAAAAAAEAAACZAAAC3/wCAAAAAvsAAAAYAGQAbwBjAGsASwBlAHkAZg"
            "ByAGEAbQBlAQAAAVgAAAAVAAAAAAAAAAD8AAAAJwAAAt8AAAC1AQAAHPoAAAAAAQAAAAL7AAAAFgBkAG8AYwBr"
            "AEUAZgBmAGUAYwB0AHMBAAADrQAAAJkAAABYAP////sAAAAiAGQAbwBjAGsAQwBhAHAAdABpAG8AbgBFAGQAaQ"
            "B0AG8AcgEAAAAA/////wAAAFgA////AAAAAgAAArAAAALY/AEAAAAB/AAAAPcAAAKwAAAA+gD////8AgAAAAL8"
            "AAAAJwAAAcgAAAFHAP////wBAAAAAvwAAAD3AAAArgAAAIIA/////AIAAAAC+wAAABIAZABvAGMAawBGAGkAbA"
            "BlAHMBAAAAJwAAAOQAAACSAP////wAAAERAAAA3gAAAK8BAAAc+gAAAAABAAAAAvsAAAAeAGQAbwBjAGsAVABy"
            "AGEAbgBzAGkAdABpAG8AbgBzAQAAAAD/////AAAAbAD////7AAAAFABkAG8AYwBrAEUAbQBvAGoAaQBzAQAAAP"
            "cAAAEdAAAAggD////7AAAAEgBkAG8AYwBrAFYAaQBkAGUAbwEAAAGrAAAB/AAAAEcA////+wAAABgAZABvAGMA"
            "awBUAGkAbQBlAGwAaQBuAGUBAAAB9QAAAQoAAACWAP///wAAArAAAAABAAAAAQAAAAIAAAABAAAAAvwAAAABAA"
            "AAAgAAAAEAAAAOAHQAbwBvAGwAQgBhAHIBAAAAAP////8AAAAAAAAAAA=="
            ])
        self.restoreState(qt_types.str_to_bytes(advanced_state))
        QCoreApplication.processEvents()

    def actionFreeze_View_trigger(self):
        """ Freeze all dockable widgets on the main screen """
        for dock in self.getDocks():
            self.freezeDock(dock, frozen=True)
        self.freezeMainToolBar(frozen=True)
        self.actionFreeze_View.setVisible(False)
        self.actionUn_Freeze_View.setVisible(True)
        self.docks_frozen = True

    def actionUn_Freeze_View_trigger(self):
        """ Un-Freeze all dockable widgets on the main screen """
        for dock in self.getDocks():
            self.freezeDock(dock, frozen=False)
        self.freezeMainToolBar(frozen=False)
        self.actionFreeze_View.setVisible(True)
        self.actionUn_Freeze_View.setVisible(False)
        self.docks_frozen = False

    def actionShow_All_trigger(self):
        """ Show all dockable widgets """
        self.showDocks(self.getDocks())

    def actionTutorial_trigger(self):
        """ Show tutorial again """
        s = get_app().get_settings()

        # Clear tutorial settings
        s.set("tutorial_enabled", True)
        s.set("tutorial_ids", "")

        # Show first tutorial dialog again
        if self.tutorial_manager:
            self.tutorial_manager.exit_manager()
            self.tutorial_manager = TutorialManager(self)
            self.tutorial_manager.process_visibility()

    def actionInsertTimestamp_trigger(self, event):
        """Insert the current timestamp into the caption editor
        In the format: 00:00:23,000 --> 00:00:24,500. first click to set the initial timestamp,
        move the playehad, second click to set the end timestamp.

        If beginning and ending timestamps would be the same, add 5 seconds to the second.
        """
        # Get translation function
        app = get_app()
        _ = app._tr

        if not self.selected_effects:
            log.info("No caption effect selected")
            return
        effect_data = Effect.filter(id=self.selected_effects[0])[0].data
        effect_id = effect_data.get("id")
        if effect_data.get("type") != "Caption":
            log.info("Captioning an effect that is not a Caption")
            return

        # Get the Clip that owns this caption effect
        clip_data = None
        for clip in Clip.filter():
            for effect in clip.data.get('effects'):
                if effect.get("id") == effect_id:
                    clip_data = clip.data
                    break
            if clip_data != None:
                break

        if clip_data == None:
            log.info("No clip owns this caption effect")
            return

        if self.captionTextEdit.isReadOnly():
            return

        # Calculate fps / current seconds
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = (self.preview_thread.current_frame - 1) / fps_float
        relative_position = current_position - clip_data.get("position") + clip_data.get("start")

        # Prevent captions before or after the clip
        relative_position = max(clip_data.get('start'), relative_position)
        clip_seconds = clip_data.get("end") - clip_data.get("start")
        relative_position = min(clip_data.get('end'), relative_position)

        # Get cursor / current line of text (where cursor is located)
        cursor = self.captionTextEdit.textCursor()
        self.captionTextEdit.moveCursor(QTextCursor.StartOfLine)
        line_text = cursor.block().text()
        self.captionTextEdit.moveCursor(QTextCursor.EndOfLine)

        # Convert time in seconds to hours:minutes:seconds:milliseconds
        current_timestamp = secondsToTimecode(relative_position, fps["num"], fps["den"], use_milliseconds=True)

        # If this line only has one timestamp, and both timestamps are the same, default to 5 second duration
        if "-->"  in line_text and line_text.count(':') == 3 and current_timestamp in line_text:
            # prevent caption with 0 duration
            relative_position += 5.0
            # recalculate the timestamp string
            current_timestamp = secondsToTimecode(relative_position, fps["num"], fps["den"], use_milliseconds=True)

        if "-->" in line_text and line_text.count(':') == 3:
            # Current line has only one timestamp. Add the second and go to the line below it.
            self.captionTextEdit.insertPlainText(current_timestamp)
            self.captionTextEdit.moveCursor(QTextCursor.Down)
            self.captionTextEdit.moveCursor(QTextCursor.EndOfLine)
        else:
            # Current line isn't a starting timestamp, so add a starting timestamp

            # If the current line isn't blank, go to end and add two blank lines
            if (self.captionTextEdit.textCursor().block().text().strip() != ""):
                self.captionTextEdit.moveCursor(QTextCursor.End)
                self.captionTextEdit.insertPlainText("\n\n")
            # Add timestamp, and placeholder caption
            self.captionTextEdit.insertPlainText("%s --> \n%s" % (current_timestamp, _("Enter caption text...")))
            # Return to timestamp line, to await ending timestamp
            self.captionTextEdit.moveCursor(QTextCursor.Up)

    def captionTextEdit_TextChanged(self):
        """Caption text was edited, start the save timer (to prevent spamming saves)"""
        self.caption_save_timer.start()

    def caption_editor_save(self):
        """Emit the CaptionTextUpdated signal (and if that property is active/selected, it will be saved)"""
        self.CaptionTextUpdated.emit(self.captionTextEdit.toPlainText(), self.caption_model_row)

    def caption_editor_load(self, new_caption_text, caption_model_row):
        """Load the caption editor with text, or disable it if empty string detected"""
        self.caption_model_row = caption_model_row
        self.captionTextEdit.setPlainText(new_caption_text.strip())
        if not caption_model_row:
            self.captionTextEdit.setReadOnly(True)
        else:
            self.captionTextEdit.setReadOnly(False)

            # Show this dock
            self.dockCaptionEditor.show()
            self.dockCaptionEditor.raise_()

    def SetWindowTitle(self, profile=None):
        """ Set the window title based on a variety of factors """

        # Get translation function
        app = get_app()
        _ = app._tr

        if not profile:
            profile = app.project.get("profile")

        # Determine if the project needs saving (has any unsaved changes)
        save_indicator = ""
        if app.project.needs_save():
            save_indicator = "*"
            self.actionSave.setEnabled(True)
        else:
            self.actionSave.setEnabled(False)

        # Is this a saved project?
        if not app.project.current_filepath:
            # Not saved yet (use singleShot since this method can be invoked by our preview thread)
            QTimer.singleShot(0, functools.partial(self.setWindowTitle,
                "%s %s [%s] - %s" % (save_indicator, _("Untitled Project"), profile, info.PRODUCT_NAME)))
        else:
            # Yes, project is saved
            # Get just the filename
            filename = os.path.basename(app.project.current_filepath)
            filename = os.path.splitext(filename)[0]
            # Use singleShot since this method can be invoked by our preview thread
            QTimer.singleShot(0, functools.partial(self.setWindowTitle,
                "%s %s [%s] - %s" % (save_indicator, filename, profile, info.PRODUCT_NAME)))

    # Update undo and redo buttons enabled/disabled to available changes
    def updateStatusChanged(self, undo_status, redo_status):
        self.actionUndo.setEnabled(undo_status)
        self.actionRedo.setEnabled(redo_status)
        self.actionClearHistory.setEnabled(undo_status | redo_status)
        self.SetWindowTitle()

    def addSelection(self, item_id, item_type, clear_existing=False):
        """Add an item to the selection list.

        When ``clear_existing`` is True and ``item_id`` is provided, any
        existing selections of **all** types are cleared before adding the new
        item. If ``item_id`` is empty, selections matching ``item_type`` are
        removed instead. This keeps the method focused on simply managing the
        selection list without extra special-casing.
        """
        if clear_existing:
            if item_id or not item_type:
                # Replace the entire selection list
                self.selected_items = []
            else:
                # Remove selections of the specified type only
                self.selected_items = [s for s in self.selected_items if s["type"] != item_type]

        if item_id:
            exists = any(
                s for s in self.selected_items if s["id"] == item_id and s["type"] == item_type
            )
            if not exists:
                self.selected_items.append({"id": item_id, "type": item_type})

            # Change selected item in properties view
            self.show_property_timer.start()

        # Notify UI that selection has potentially changed
        self.selection_timer.start()

    # Remove from the selected items
    def removeSelection(self, item_id, item_type):
        # Remove existing selection (if any)
        if item_id:
            found = False
            for sel in list(self.selected_items):
                if sel["id"] == item_id and sel["type"] == item_type:
                    self.selected_items.remove(sel)
                    found = True
                    break
            if not found:
                for sel in list(self.selected_items):
                    if sel["id"] == item_id:
                        self.selected_items.remove(sel)
                        break

        # Move selection to next selected clip (if any)
        self.show_property_id = ""
        self.show_property_type = ""
        if self.selected_items:
            self.show_property_id = self.selected_items[0]["id"]
            self.show_property_type = self.selected_items[0]["type"]

        # Change selected item
        self.show_property_timer.start()
        self.selection_timer.start()

    def emit_selection_signal(self):
        """Emit a signal for selection changed. Callback for selection timer."""
        if not self.selected_items:
            # Clear properties view (if no other items are selected)
            if self.propertyTableView:
                self.propertyTableView.loadProperties.emit([])

        # Notify UI that selection has been potentially changed
        self.SelectionChanged.emit()

        # Clear caption editor (if nothing is selected)
        get_app().window.CaptionTextLoaded.emit("", None)

        # Update transform handles based on current selection
        if get_app().get_settings().get("auto-transform"):
            self.TransformSignal.emit(self.selected_clips)

            emitted_transform = False
            for sel in self.selected_items:
                if sel["type"] == "effect":
                    effect = Effect.get(id=sel["id"])
                    if effect and (
                        effect.data.get("has_tracked_object")
                        or effect.data.get("class_name") == "Crop"
                    ):
                        clip_id = effect.parent['id']
                        self.KeyFrameTransformSignal.emit(sel["id"], clip_id)
                        emitted_transform = True

            if not emitted_transform:
                self.KeyFrameTransformSignal.emit("", "")

    def selected_files(self):
        """ Return a list of File objects for the Project Files dock's selection """
        return self.files_model.selected_files()

    def selected_file_ids(self):
        """ Return a list of File IDs for the Project Files dock's selection """
        return self.files_model.selected_file_ids()

    def selected_ids(self, item_type):
        """Return list of selected ids matching item_type"""
        return [s["id"] for s in self.selected_items if s["type"] == item_type]

    @property
    def selected_clips(self):
        return self.selected_ids("clip")

    @property
    def selected_transitions(self):
        return self.selected_ids("transition")

    @property
    def selected_effects(self):
        return self.selected_ids("effect")

    def current_file(self):
        """ Return the Project Files dock's currently-active item as a File object """
        return self.files_model.current_file()

    def current_file_id(self):
        """ Return the ID of the Project Files dock's currently-active item """
        return self.files_model.current_file_id()

    # Update window settings in setting store
    def save_settings(self):
        s = get_app().get_settings()

        # Save window state and geometry (saves toolbar and dock locations)
        s.set('window_state_v2', qt_types.bytes_to_str(self.saveState()))
        s.set('window_geometry_v2', qt_types.bytes_to_str(self.saveGeometry()))
        s.set('docks_frozen', self.docks_frozen)
        dock = getattr(self, "dockTimeline", None)
        if dock:
            s.set('timeline_height', dock.height())

    # Get window settings from setting store
    def load_settings(self):
        s = get_app().get_settings()

        # Window state and geometry (also toolbar, dock locations and frozen UI state)
        if s.get('window_geometry_v2'):
            self.saved_geometry = qt_types.str_to_bytes(s.get('window_geometry_v2'))
        if s.get('window_state_v2'):
            self.saved_state = qt_types.str_to_bytes(s.get('window_state_v2'))
        if s.get('docks_frozen'):
            self.actionFreeze_View_trigger()
        else:
            self.actionUn_Freeze_View_trigger()
        timeline_height = s.get('timeline_height')
        if timeline_height:
            try:
                height_value = int(timeline_height)
            except (TypeError, ValueError):
                height_value = None
            if height_value and height_value > 0:
                self.saved_timeline_height = height_value

        # Load Recent Projects
        self.load_recent_menu()

        # The method restoreState restores the visibility of the toolBar,
        # but does not set the correct flag in the actionView_Toolbar.
        self.actionView_Toolbar.setChecked(self.toolBar.isVisibleTo(self))

    def load_recent_menu(self):
        """ Clear and load the list of recent menu items """
        s = get_app().get_settings()
        _ = get_app()._tr  # Get translation function

        # Get list of recent projects
        recent_projects = s.get("recent_projects")

        # Add Recent Projects menu (after Open File)
        if not self.recent_menu:
            # Create a new recent menu
            self.recent_menu = self.menuFile.addMenu(
                QIcon.fromTheme("document-open-recent"),
                _("Recent Projects"))
            self.menuFile.insertMenu(self.actionRecentProjects, self.recent_menu)
        else:
            # Clear the existing children
            self.recent_menu.clear()

        # Add recent projects to menu
        # Show just a placeholder menu, if we have no recent projects list
        if not recent_projects:
            self.recent_menu.addAction(_("No Recent Projects")).setDisabled(True)
            return

        for file_path in reversed(recent_projects):
            # Add each recent project
            new_action = self.recent_menu.addAction(file_path)
            new_action.triggered.connect(functools.partial(self.recent_project_clicked, file_path))

        # Add 'Clear Recent Projects' menu to bottom of list
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.actionClearRecents)
        self.actionClearRecents.triggered.connect(self.clear_recents_clicked)

        # Build recovery menu as well
        self.load_restore_menu()

    def time_ago_string(self, timestamp):
        """ Returns a friendly time difference string for the given timestamp. """
        _ = get_app()._tr

        SECONDS_IN_MINUTE = 60
        SECONDS_IN_HOUR = SECONDS_IN_MINUTE * 60
        SECONDS_IN_DAY = SECONDS_IN_HOUR * 24
        SECONDS_IN_WEEK = SECONDS_IN_DAY * 7
        SECONDS_IN_MONTH = SECONDS_IN_WEEK * 4
        SECONDS_IN_YEAR = SECONDS_IN_MONTH * 12

        delta = datetime.now() - datetime.fromtimestamp(timestamp)
        seconds = delta.total_seconds()

        if seconds < SECONDS_IN_MINUTE:
            return _("{} seconds ago").format(int(seconds))
        elif seconds < SECONDS_IN_HOUR:
            minutes = seconds // SECONDS_IN_MINUTE
            return _("{} minutes ago").format(int(minutes))
        elif seconds < SECONDS_IN_DAY:
            hours = seconds // SECONDS_IN_HOUR
            return _("{} hours ago").format(int(hours))
        elif seconds < SECONDS_IN_WEEK:
            days = seconds // SECONDS_IN_DAY
            return _("{} days ago").format(int(days))
        elif seconds < SECONDS_IN_MONTH:
            weeks = seconds // SECONDS_IN_WEEK
            return _("{} weeks ago").format(int(weeks))
        elif seconds < SECONDS_IN_YEAR:
            months = seconds // SECONDS_IN_MONTH
            return _("{} months ago").format(int(months))
        else:
            years = seconds // SECONDS_IN_YEAR
            return _("{} years ago").format(int(years))

    def load_restore_menu(self):
        """ Clear and load the list of restore version menu items """
        _ = get_app()._tr

        # Add Restore Previous Version menu (after Open File)
        if not self.restore_menu:
            # Create a new restore menu
            self.restore_menu = self.menuFile.addMenu(QIcon.fromTheme("edit-undo"), _("Recovery"))
            self.restore_menu.aboutToShow.connect(self.populate_restore_menu)
            self.menuFile.insertMenu(self.actionRecoveryProjects, self.restore_menu)

    def populate_restore_menu(self):
        """Clear and re-Add the restore project menu items as needed"""
        app = get_app()
        _ = get_app()._tr
        current_filepath = app.project.current_filepath if app.project else None

        # Clear the existing children
        self.restore_menu.clear()

        # Get a list of recovery files matching the current project
        recovery_files = []
        if current_filepath:
            recovery_dir = info.RECOVERY_PATH
            base_no_ext = os.path.splitext(os.path.basename(current_filepath))[0]
            recovery_files = [
                f for f in os.listdir(recovery_dir)
                if (f.endswith(".zip") or f.endswith(info.ALL_PROJECT_EXTS) or f.endswith(info.LEGACY_PROJECT_EXTS)) and "-" in f and f.split("-", 1)[1].startswith(base_no_ext)
            ]

        # Show just a placeholder menu, if we have no recovery files
        if not recovery_files:
            self.restore_menu.addAction(_("No Previous Versions Available")).setDisabled(True)
            return

        # Sort files in descending order (latest first)
        recovery_files.sort(reverse=True)

        for file_name in recovery_files:
            # Extract timestamp from file name
            try:
                timestamp = int(file_name.split("-", 1)[0])
                friendly_time = self.time_ago_string(timestamp)
                full_datetime = datetime.fromtimestamp(timestamp).strftime('%b %d, %H:%M')
                file_path = os.path.join(recovery_dir, file_name)

                # Add each recovery file with a tooltip
                new_action = self.restore_menu.addAction(f"{friendly_time} ({full_datetime})")
                new_action.triggered.connect(functools.partial(self.restore_version_clicked, file_path))
            except ValueError:
                continue

    def restore_version_clicked(self, file_path):
        """Restore a previous project file from the recovery folder"""
        with self.lock:
            app = get_app()
            current_filepath = app.project.current_filepath if app.project else None
            _ = get_app()._tr

            try:
                # Rename the original project file
                current_ext = os.path.splitext(os.path.basename(current_filepath))[1] or info.PROJECT_EXT
                recovered_filename = os.path.splitext(os.path.basename(current_filepath))[0] + f"-{int(time())}-backup{current_ext}"
                recovered_filepath = os.path.join(os.path.dirname(current_filepath), recovered_filename)
                if os.path.exists(current_filepath):
                    shutil.move(current_filepath, recovered_filepath)
                    log.info(f"Backup current project to: {recovered_filepath}")

                # Unzip if the selected recovery file is a .zip file
                if file_path.endswith(".zip"):
                    with zipfile.ZipFile(file_path, 'r') as zipf:
                        # Extract over top original project file
                        zipf.extractall(os.path.dirname(current_filepath))
                        extracted_files = zipf.namelist()
                        if len(extracted_files) != 1:
                            raise ValueError("Unexpected number of files in recovery zip.")
                else:
                    # Replace the original project file with the recovery file
                    shutil.copyfile(file_path, current_filepath)
                log.info(f"Recovery file `{file_path}` restored to: `{current_filepath}`")

                # Open the recovered project
                self.OpenProjectSignal.emit(current_filepath)

            except Exception as ex:
                log.error(f"Error recovering project from `{file_path}` to `{current_filepath}`: {ex}", exc_info=True)

    def remove_recent_project(self, file_path):
        """Remove a project from the Recent menu if it can't be found"""
        s = get_app().get_settings()
        recent_projects = s.get("recent_projects")
        if file_path in recent_projects:
            recent_projects.remove(file_path)
        s.set("recent_projects", recent_projects)
        s.save()

    def recent_project_clicked(self, file_path):
        """ Load a recent project when clicked """
        self.OpenProjectSignal.emit(file_path)

    def clear_recents_clicked(self):
        """Clear all recent projects"""
        s = get_app().get_settings()
        s.set("recent_projects", [])

        # Reload recent project list
        self.load_recent_menu()

    def setup_toolbars(self):
        _ = get_app()._tr  # Get translation function

        # Start undo and redo actions disabled
        self.actionUndo.setEnabled(False)
        self.actionRedo.setEnabled(False)

        # Add files toolbar
        self.filesToolbar = QToolBar("Files Toolbar")
        self.filesActionGroup = QActionGroup(self)
        self.filesActionGroup.setExclusive(True)
        self.filesActionGroup.addAction(self.actionFilesShowAll)
        self.filesActionGroup.addAction(self.actionFilesShowVideo)
        self.filesActionGroup.addAction(self.actionFilesShowAudio)
        self.filesActionGroup.addAction(self.actionFilesShowImage)
        self.actionFilesShowAll.setChecked(True)
        self.filesToolbar.addAction(self.actionFilesShowAll)
        self.filesToolbar.addAction(self.actionFilesShowVideo)
        self.filesToolbar.addAction(self.actionFilesShowAudio)
        self.filesToolbar.addAction(self.actionFilesShowImage)
        self.filesFilter = QLineEdit()
        self.filesFilter.setObjectName("filesFilter")
        self.filesFilter.setPlaceholderText(_("Filter"))
        self.filesFilter.setClearButtonEnabled(True)
        self.filesToolbar.addWidget(self.filesFilter)
        self.tabFiles.layout().insertWidget(0, self.filesToolbar)

        # Add transitions toolbar
        self.transitionsToolbar = QToolBar("Transitions Toolbar")
        self.transitionsActionGroup = QActionGroup(self)
        self.transitionsActionGroup.setExclusive(True)
        self.transitionsActionGroup.addAction(self.actionTransitionsShowAll)
        self.transitionsActionGroup.addAction(self.actionTransitionsShowCommon)
        self.actionTransitionsShowAll.setChecked(True)
        self.transitionsToolbar.addAction(self.actionTransitionsShowAll)
        self.transitionsToolbar.addAction(self.actionTransitionsShowCommon)
        self.transitionsFilter = QLineEdit()
        self.transitionsFilter.setObjectName("transitionsFilter")
        self.transitionsFilter.setPlaceholderText(_("Filter"))
        self.transitionsFilter.setClearButtonEnabled(True)
        self.transitionsToolbar.addWidget(self.transitionsFilter)
        self.tabTransitions.layout().addWidget(self.transitionsToolbar)

        # Add effects toolbar
        self.effectsToolbar = QToolBar("Effects Toolbar")
        self.effectsFilter = QLineEdit()
        self.effectsActionGroup = QActionGroup(self)
        self.effectsActionGroup.setExclusive(True)
        self.effectsActionGroup.addAction(self.actionEffectsShowAll)
        self.effectsActionGroup.addAction(self.actionEffectsShowVideo)
        self.effectsActionGroup.addAction(self.actionEffectsShowAudio)
        self.actionEffectsShowAll.setChecked(True)
        self.effectsToolbar.addAction(self.actionEffectsShowAll)
        self.effectsToolbar.addAction(self.actionEffectsShowVideo)
        self.effectsToolbar.addAction(self.actionEffectsShowAudio)
        self.effectsFilter.setObjectName("effectsFilter")
        self.effectsFilter.setPlaceholderText(_("Filter"))
        self.effectsFilter.setClearButtonEnabled(True)
        self.effectsToolbar.addWidget(self.effectsFilter)
        self.tabEffects.layout().addWidget(self.effectsToolbar)

        # Add emojis toolbar
        self.emojisToolbar = QToolBar("Emojis Toolbar")
        self.emojiFilterGroup = QComboBox()
        self.emojisFilter = QLineEdit()
        self.emojisFilter.setObjectName("emojisFilter")
        self.emojisFilter.setPlaceholderText(_("Filter"))
        self.emojisFilter.setClearButtonEnabled(True)
        self.emojisToolbar.addWidget(self.emojiFilterGroup)
        self.emojisToolbar.addWidget(self.emojisFilter)
        self.tabEmojis.layout().addWidget(self.emojisToolbar)

        # Add Video Preview toolbar
        self.videoToolbar = QToolBar("Video Toolbar")
        self.tabVideo.layout().addWidget(self.videoToolbar)

        # Add Timeline toolbar
        self.timelineToolbar = QToolBar("Timeline Toolbar", self)
        self.timelineToolbar.setObjectName("timelineToolbar")

        # Add Video Preview toolbar
        self.captionToolbar = QToolBar(_("Caption Toolbar"))

        # Add Caption text editor widget
        self.captionTextEdit = QTextEdit()
        self.captionTextEdit.setReadOnly(True)

        # Playback controls (centered)
        self.captionToolbar.addAction(self.actionInsertTimestamp)
        self.tabCaptions.layout().addWidget(self.captionToolbar)
        self.tabCaptions.layout().addWidget(self.captionTextEdit)

        # Hook up caption editor signal
        self.captionTextEdit.textChanged.connect(self.captionTextEdit_TextChanged)
        self.caption_save_timer = QTimer(self)
        self.caption_save_timer.setInterval(1000)
        self.caption_save_timer.setSingleShot(True)
        self.caption_save_timer.timeout.connect(self.caption_editor_save)
        self.CaptionTextLoaded.connect(self.caption_editor_load)
        self.caption_model_row = None

        # Get project's initial zoom value
        initial_scale = float(get_app().project.get("scale") or 15.0)

        # Setup Zoom Slider widget
        from windows.views.zoom_slider import ZoomSlider
        self.sliderZoomWidget = ZoomSlider(self)
        self.sliderZoomWidget.setMinimumHeight(20)
        self.sliderZoomWidget.setZoomFactor(initial_scale)

        # add zoom widgets
        self.timelineToolbar.addWidget(self.sliderZoomWidget)

        # Add timeline toolbar to web frame
        self.frameWeb.addWidget(self.timelineToolbar)

    def clearSelections(self):
        """Clear all selection containers and reset preview transforms"""
        # Reset any active transform state on the video preview. This prevents
        # the preview widget from holding references to libopenshot objects that
        # may become invalid after timeline changes.
        if hasattr(self, "videoPreview") and self.videoPreview:
            self.videoPreview.clearTransformState()

        self.selected_items = []
        self.selected_markers = []
        self.selected_tracks = []

        # Clear selection in properties view
        if self.propertyTableView:
            self.propertyTableView.loadProperties.emit([])

        # Notify UI that selection has been potentially changed
        self.selection_timer.start()

    def verifySelections(self):
        """Clear any invalid selections"""
        for sel in list(self.selected_items):
            if sel["type"] == "clip" and not Clip.get(id=sel["id"]):
                self.removeSelection(sel["id"], "clip")
            elif sel["type"] == "transition" and not Transition.get(id=sel["id"]):
                self.removeSelection(sel["id"], "transition")
            elif sel["type"] == "effect" and not Effect.get(id=sel["id"]):
                self.removeSelection(sel["id"], "effect")

    def handleSeek(self, frame):
        """ Always update the property view when we seek to a new position """
        # Notify properties dialog
        self.propertyTableView.select_frame(frame)

    def on_plan_approved(self, plan_id):
        """Handle director plan approval."""
        log.info(f"Plan approved: {plan_id}")
        try:
            # Execute the plan
            if hasattr(self, 'dockPlanReview') and self.dockPlanReview.current_plan:
                from classes.ai_plan_executor import execute_plan
                from classes.ai_agent_runner import get_main_thread_runner
                from classes import settings

                plan = self.dockPlanReview.current_plan
                model_id = settings.get_settings().get("ai-default-model")
                main_thread_runner = get_main_thread_runner()

                # Get auto mode from settings
                auto_mode = settings.get_settings().get("directors-auto-mode", False)

                # Execute plan
                result = execute_plan(plan, model_id, main_thread_runner, auto_mode)

                # Show result in chat
                if hasattr(self, 'dockAIChat'):
                    success_msg = f"Plan executed: {result['steps_executed']}/{result['steps_total']} steps completed"
                    if result['steps_failed'] > 0:
                        success_msg += f" ({result['steps_failed']} failed)"
                    self.dockAIChat.display_assistant_message(success_msg)

                log.info(f"Plan execution result: {result}")
        except Exception as e:
            log.error(f"Plan execution failed: {e}", exc_info=True)

    def on_plan_rejected(self, plan_id):
        """Handle director plan rejection."""
        log.info(f"Plan rejected: {plan_id}")
        # Just hide the plan review - user rejected it
        if hasattr(self, 'dockPlanReview'):
            self.dockPlanReview.hide()

    def moveEvent(self, event):
        """ Move tutorial dialogs also (if any)"""
        QMainWindow.moveEvent(self, event)
        if self.tutorial_manager:
            self.tutorial_manager.re_position_dialog()

    def resizeEvent(self, event):
        QMainWindow.resizeEvent(self, event)
        if self.tutorial_manager:
            self.tutorial_manager.re_position_dialog()

    def showEvent(self, event):
        """ Have any child windows follow main-window state """
        QMainWindow.showEvent(self, event)
        for child in self.getDocks():
            if child.isFloating() and child.isEnabled():
                child.raise_()
                child.show()
        if (self.saved_geometry or self.saved_state) and not self._restored_saved_window:
            # Delay the restore until after the window is shown so layouts are settled.
            QTimer.singleShot(0, self._restore_saved_window)

    def hideEvent(self, event):
        """ Have any child windows hide with main window """
        QMainWindow.hideEvent(self, event)
        for child in self.getDocks():
            if child.isFloating() and child.isVisible():
                child.hide()

    def _restore_saved_window(self):
        """Apply saved geometry/state after the first show event."""
        if self._restored_saved_window:
            return
        self._restored_saved_window = True
        if self.saved_geometry:
            self.restoreGeometry(self.saved_geometry)
        if self.saved_state:
            self._restore_state_and_timeline()

    def _restore_state_and_timeline(self):
        """Restore saved dock state and then apply timeline height."""
        if self.saved_state:
            self.restoreState(self.saved_state)
        self._apply_saved_timeline_height()

    def _apply_saved_timeline_height(self):
        """Apply the saved timeline dock height without a visible two-pass resize."""
        if self._timeline_height_restored or not self.saved_timeline_height:
            return

        dock = getattr(self, "dockTimeline", None)
        if not dock:
            return

        # If height already matches, skip the resize to avoid an extra layout pass.
        if dock.height() != self.saved_timeline_height:
            self.resizeDocks([dock], [self.saved_timeline_height], Qt.Vertical)
        self._timeline_height_restored = True

    def show_property_timeout(self):
        """Callback for show property timer"""

        # Emit load properties signal with current selection list
        self.propertyTableView.loadProperties.emit(list(self.selected_items))

    def InitCacheSettings(self):
        """Set the correct cache settings for the timeline"""
        # Load user settings
        s = get_app().get_settings()
        log.info("InitCacheSettings")
        log.info("cache-mode: %s" % s.get("cache-mode"))
        log.info("cache-limit-mb: %s" % s.get("cache-limit-mb"))
        log.info("cache-ahead-percent: %s" % s.get("cache-ahead-percent"))
        log.info("cache-preroll-min-frames: %s" % s.get("cache-preroll-min-frames"))
        log.info("cache-preroll-max-frames: %s" % s.get("cache-preroll-max-frames"))
        log.info("cache-max-frames: %s" % s.get("cache-max-frames"))

        # Set preview cache settings
        lib_settings = openshot.Settings.Instance()
        lib_settings.VIDEO_CACHE_PERCENT_AHEAD = s.get("cache-ahead-percent")
        lib_settings.VIDEO_CACHE_MIN_PREROLL_FRAMES = s.get("cache-preroll-min-frames")
        lib_settings.VIDEO_CACHE_MAX_PREROLL_FRAMES = s.get("cache-preroll-max-frames")
        lib_settings.VIDEO_CACHE_MAX_FRAMES = s.get("cache-max-frames")

        # Get MB limit of cache (and convert to bytes)
        cache_limit = s.get("cache-limit-mb") * 1024 * 1024  # Convert MB to Bytes

        # Clear old cache
        new_cache_object = None
        if s.get("cache-mode") == "CacheMemory":
            # Create CacheMemory object, and set on timeline
            log.info("Creating CacheMemory object with %s byte limit" % cache_limit)
            new_cache_object = openshot.CacheMemory(cache_limit)
            self.timeline_sync.timeline.SetCache(new_cache_object)

        elif s.get("cache-mode") == "CacheDisk":
            # Create CacheDisk object, and set on timeline
            log.info("Creating CacheDisk object with %s byte limit at %s" % (
                cache_limit, info.PREVIEW_CACHE_PATH))
            image_format = s.get("cache-image-format")
            image_quality = s.get("cache-quality")
            image_scale = s.get("cache-scale")
            new_cache_object = openshot.CacheDisk(
                info.PREVIEW_CACHE_PATH,
                image_format,
                image_quality,
                image_scale,
                cache_limit,
                )
            self.timeline_sync.timeline.SetCache(new_cache_object)

        # Clear old cache before it goes out of scope
        if self.cache_object:
            self.cache_object.Clear()
        # Update cache reference, so it doesn't go out of scope
        self.cache_object = new_cache_object

    def initModels(self):
        """Set up model/view classes for MainWindow"""
        s = get_app().get_settings()

        # Setup files tree and list view (both share a model)
        self.files_model = FilesModel()
        self.filesTreeView = FilesTreeView(self.files_model)
        self.filesListView = FilesListView(self.files_model)
        self.files_model.update_model()
        self.tabFiles.layout().insertWidget(-1, self.filesTreeView)
        self.tabFiles.layout().insertWidget(-1, self.filesListView)
        if s.get("file_view") == "details":
            self.filesView = self.filesTreeView
            self.filesListView.hide()
        else:
            self.filesView = self.filesListView
            self.filesTreeView.hide()
        # Show our currently-enabled project files view
        self.filesView.show()
        self.filesView.setFocus()

        # Setup transitions tree and list views
        self.transition_model = TransitionsModel()
        self.transitionsTreeView = TransitionsTreeView(self.transition_model)
        self.transitionsListView = TransitionsListView(self.transition_model)
        self.transition_model.update_model()
        self.tabTransitions.layout().insertWidget(-1, self.transitionsTreeView)
        self.tabTransitions.layout().insertWidget(-1, self.transitionsListView)
        if s.get("transitions_view") == "details":
            self.transitionsView = self.transitionsTreeView
            self.transitionsListView.hide()
        else:
            self.transitionsView = self.transitionsListView
            self.transitionsTreeView.hide()
        # Show our currently-enabled transitions view
        self.transitionsView.show()
        self.transitionsView.setFocus()

        # Setup effects tree
        self.effects_model = EffectsModel()
        self.effectsTreeView = EffectsTreeView(self.effects_model)
        self.effectsListView = EffectsListView(self.effects_model)
        self.effects_model.update_model()
        self.tabEffects.layout().insertWidget(-1, self.effectsTreeView)
        self.tabEffects.layout().insertWidget(-1, self.effectsListView)
        if s.get("effects_view") == "details":
            self.effectsView = self.effectsTreeView
            self.effectsListView.hide()
        else:
            self.effectsView = self.effectsListView
            self.effectsTreeView.hide()
        # Show our currently-enabled effects view
        self.effectsView.show()
        self.effectsView.setFocus()

        # Setup emojis view
        self.emojis_model = EmojisModel()
        self.emojis_model.update_model()
        self.emojiListView = EmojisListView(self.emojis_model)
        self.tabEmojis.layout().addWidget(self.emojiListView)

    def actionInsertKeyframe(self):
        log.debug("actionInsertKeyframe")
        if self.selected_clips or self.selected_transitions:
            self.InsertKeyframe.emit()

    def seekPreviousFrame(self):
        """Handle previous-frame keypress"""
        # Ignore certain focused widgets
        get_app().window.SeekPreviousFrame.emit()

    def seekNextFrame(self):
        """Handle next-frame keypress"""
        get_app().window.SeekNextFrame.emit()

    def playToggle(self):
        """Handle play-pause-toggle keypress"""
        get_app().window.PlayPauseToggleSignal.emit()

    def deleteItem(self):
        """Remove the current selected clip / transition or file from the project."""
        # Set transaction id
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid
        try:
            # If the filesView has focus, remove the item from the project
            if self.filesView.hasFocus():
                self.actionRemove_from_Project_trigger()
            else:
                # Otherwise, proceed with the normal timeline delete behavior
                self.actionRemoveClip_trigger()
                self.actionRemoveTransition_trigger()
        finally:
            get_app().updates.transaction_id = None

    def slice_clips(self, slice_type, selected_only=False, ripple=False):
        """Helper function for slicing clips and transitions at the playhead position."""
        # Get framerate and calculate the playhead position
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        playhead_position = float(self.preview_thread.current_frame - 1) / fps_float

        # Get intersecting clips and transitions at the playhead position
        intersecting_clips = Clip.filter(intersect=playhead_position)
        intersecting_trans = Transition.filter(intersect=playhead_position)

        if intersecting_clips or intersecting_trans:
            if selected_only:
                # Filter clips and transitions by selected ones
                clip_ids = [c.id for c in intersecting_clips if c.id in self.selected_clips]
                trans_ids = [t.id for t in intersecting_trans if t.id in self.selected_transitions]
            else:
                # Get all intersecting clip and transition IDs
                clip_ids = [c.id for c in intersecting_clips]
                trans_ids = [t.id for t in intersecting_trans]

            # Trigger the slice action with the appropriate slice type
            self.timeline.Slice_Triggered(slice_type, clip_ids, trans_ids, playhead_position, ripple)

    def sliceAllKeepBothSides(self):
        """Handler for slicing all clips and keeping both sides at the playhead position."""
        self.slice_clips(MenuSlice.KEEP_BOTH)

    def sliceAllKeepLeftSide(self):
        """Handler for slicing all clips and keeping the left side at the playhead position."""
        self.slice_clips(MenuSlice.KEEP_LEFT)

    def sliceAllKeepRightSide(self):
        """Handler for slicing all clips and keeping the right side at the playhead position."""
        self.slice_clips(MenuSlice.KEEP_RIGHT)

    def sliceSelectedKeepBothSides(self):
        """Handler for slicing selected clips and keeping both sides at the playhead position."""
        self.slice_clips(MenuSlice.KEEP_BOTH, selected_only=True)

    def sliceSelectedKeepLeftSide(self):
        """Handler for slicing selected clips and keeping the left side at the playhead position."""
        self.slice_clips(MenuSlice.KEEP_LEFT, selected_only=True)

    def sliceSelectedKeepRightSide(self):
        """Handler for slicing selected clips and keeping the right side at the playhead position."""
        self.slice_clips(MenuSlice.KEEP_RIGHT, selected_only=True)

    def selectAll(self):
        """Select all clips and transitions"""
        # Check if filesView has focus
        if self.filesView.hasFocus():
            # Select all files
            self.filesView.selectAll()
        else:
            # Select all clips / transitions
            self.timeline.SelectAll()

    def selectNone(self):
        """Clear all selections for clips and transitions"""
        self.timeline.ClearAllSelections()

    def copyAll(self):
        """Handle Copy QShortcut (selected clips / transitions)"""
        self.timeline.Copy_Triggered(MenuCopy.ALL, self.selected_clips, self.selected_transitions, [])

    def cutAll(self):
        """Copy and remove the currently selected clip/transition"""
        self.copyAll()
        self.deleteItem()

    def pasteAll(self):
        """Handle Paste QShortcut (at timeline position, same track as original clip)"""
        clipboard = get_app().clipboard()
        mime_data = clipboard.mimeData() if clipboard else None

        if mime_data and not mime_data.hasFormat("application/x-flowcut-generic"):
            if self.import_files_from_clipboard(mime_data):
                return

        self.timeline.context_menu_cursor_position = None
        self.timeline.Paste_Triggered(MenuCopy.PASTE, self.selected_clips, self.selected_transitions)

    def clipboard_contains_media(self, mime_data=None):
        """Check if clipboard contains media files or supported media data."""
        clipboard = None
        if mime_data is None:
            clipboard = get_app().clipboard()
            if not clipboard:
                return False
            mime_data = clipboard.mimeData()

        if not mime_data:
            return False

        urls, has_binary = self._collect_clipboard_media_urls(mime_data, create_files=False)
        return bool(urls or has_binary)

    def _collect_clipboard_media_urls(self, mime_data, create_files):
        """Return a list of QUrls for media items contained in the clipboard."""
        urls = []
        seen_paths = set()

        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path and os.path.exists(path) and path not in seen_paths:
                        urls.append(url)
                        seen_paths.add(path)

        if mime_data.hasText():
            text = mime_data.text()
            if text:
                for part in re.split(r'[\r\n]+', text):
                    part = part.strip()
                    if not part:
                        continue

                    url = None
                    if part.startswith("file://"):
                        temp_url = QUrl(part)
                        if temp_url.isLocalFile():
                            url = temp_url
                    elif os.path.exists(part):
                        url = QUrl.fromLocalFile(part)

                    if url:
                        path = url.toLocalFile()
                        if path and os.path.exists(path) and path not in seen_paths:
                            urls.append(url)
                            seen_paths.add(path)

        if urls:
            return urls, False

        has_binary = False

        for fmt in mime_data.formats():
            fmt_str = str(fmt)
            lower_fmt = fmt_str.lower()
            if lower_fmt.startswith(("image/", "video/", "audio/")):
                data = mime_data.data(fmt_str)
                if data and not data.isEmpty():
                    has_binary = True
                    if create_files:
                        path = self._write_clipboard_bytes(bytes(data), self._extension_for_mime(lower_fmt))
                        if path:
                            url = QUrl.fromLocalFile(path)
                            urls.append(url)
                            seen_paths.add(path)
                            break
                    else:
                        break

        clipboard = get_app().clipboard()
        if not urls and create_files and mime_data.hasImage():
            image = clipboard.image() if clipboard else None
            if image and not image.isNull():
                path = self._write_clipboard_image(image)
                if path:
                    urls.append(QUrl.fromLocalFile(path))
                    has_binary = True
        elif not has_binary and mime_data.hasImage():
            image = clipboard.image() if clipboard else None
            has_binary = bool(image and not image.isNull())

        return urls, has_binary

    def _extension_for_mime(self, mime_type):
        """Return an appropriate file extension for a mime-type."""
        subtype = mime_type.split('/')[-1]
        subtype = subtype.split(';')[0]
        subtype = subtype.split('+')[0]
        mapping = {
            "jpeg": "jpg",
            "x-icon": "ico",
            "x-matroska": "mkv",
            "quicktime": "mov",
            "x-msvideo": "avi",
            "x-wav": "wav",
        }
        return mapping.get(subtype, subtype or "bin")

    def _write_clipboard_bytes(self, data_bytes, extension):
        """Persist clipboard bytes to a file and return its path."""
        if not data_bytes:
            return None

        dest_dir = info.CLIPBOARD_PATH
        os.makedirs(dest_dir, exist_ok=True)

        filename = "clipboard-{}-{}.{}".format(
            datetime.now().strftime("%Y%m%d-%H%M%S"),
            uuid.uuid4().hex[:6],
            extension or "bin",
        )
        filepath = os.path.join(dest_dir, filename)

        try:
            with open(filepath, "wb") as handle:
                handle.write(data_bytes)
        except OSError:
            log.warning("Failed to write clipboard media to %s", filepath, exc_info=1)
            return None

        return filepath

    def _write_clipboard_image(self, image):
        """Persist a clipboard image to disk and return the new path."""
        dest_dir = info.CLIPBOARD_PATH
        os.makedirs(dest_dir, exist_ok=True)

        filename = "clipboard-{}-{}.png".format(
            datetime.now().strftime("%Y%m%d-%H%M%S"),
            uuid.uuid4().hex[:6],
        )
        filepath = os.path.join(dest_dir, filename)

        if image.save(filepath):
            return filepath

        log.warning("Failed to save clipboard image to %s", filepath)
        return None

    def import_files_from_clipboard(self, mime_data=None):
        """Import any media files or data currently stored on the clipboard."""
        clipboard = None
        if mime_data is None:
            clipboard = get_app().clipboard()
            if not clipboard:
                return False
            mime_data = clipboard.mimeData()

        if not mime_data:
            return False

        urls, _ = self._collect_clipboard_media_urls(mime_data, create_files=True)
        if not urls:
            return False

        try:
            get_app().setOverrideCursor(QCursor(Qt.WaitCursor))
            self.files_model.process_urls(urls)
        finally:
            get_app().restoreOverrideCursor()

        return True

    def nudgeLeft(self):
        """Nudge the selected clips to the left"""
        self.timeline.Nudge_Triggered(-1, self.selected_clips, self.selected_transitions)

    def nudgeLeftBig(self):
        """Nudge the selected clip/transition to the left (5 pixels)"""
        self.timeline.Nudge_Triggered(-5, self.selected_clips, self.selected_transitions)

    def nudgeRight(self):
        """Nudge the selected clips to the right"""
        self.timeline.Nudge_Triggered(1, self.selected_clips, self.selected_transitions)

    def nudgeRightBig(self):
        """Nudge the selected clip/transition to the right (5 pixels)"""
        self.timeline.Nudge_Triggered(5, self.selected_clips, self.selected_transitions)

    def eventFilter(self, obj, event):
        """Filter out specific QActions/QShortcuts when certain docks have focus."""

        # List of QAction names to ignore when non-timeline dock widgets have focus
        ignored_actions = [
            "seekPreviousFrame",
            "seekNextFrame",
            "playToggle",
            "actionRewind",
            "actionFastForward",
            "actionRazorTool",
            "actionAddMarker",
            "actionSnappingTool",
            "actionTimingTool",
            "actionJumpStart",
            "actionJumpEnd",
            "actionRippleSliceKeepLeft",
            "actionRippleSliceKeepRight"
        ]

        # Check if event type is a shortcut override (keyboard shortcut triggered)
        if event.type() == QEvent.ShortcutOverride:

            # If any of these dock widgets have focus, we want to block specific actions
            if self.emojiListView.hasFocus() or self.filesView.hasFocus() or \
                self.transitionsView.hasFocus() or self.effectsView.hasFocus():

                # Check for each QAction name in the ignored_actions list
                for action_name in ignored_actions:
                    try:
                        # Get the shortcut key sequence
                        sequences = get_app().window.getShortcutByName(action_name)
                        for sequence in sequences:
                            if (sequence == QKeySequence(event.modifiers() | event.key())):
                                event.accept()
                                return True

                    except KeyError:
                        pass

            # Special handling for propertyTableView with playToggle shortcut
            elif self.propertyTableView.hasFocus() and event.key() == get_app().window.getShortcutByName("playToggle"):
                event.accept()
                return True

        # Allow all other events to propagate normally
        return super(MainWindow, self).eventFilter(obj, event)

    def ignore_updates_callback(self, ignore, show_wait=True):
        """Ignore updates callback - used to stop updating this widget during batch updates"""
        app = get_app()

        if ignore and not self.ignore_updates:
            if show_wait:
                # Wait for mass updates to finish
                app.setOverrideCursor(QCursor(Qt.WaitCursor))
                self._wait_cursor_requests += 1
            openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
            app.processEvents()
        elif not ignore and self.ignore_updates:
            if self._wait_cursor_requests:
                # Ensure we unwind any wait cursors that we previously applied
                while self._wait_cursor_requests and app.overrideCursor():
                    app.restoreOverrideCursor()
                    self._wait_cursor_requests -= 1
                if self._wait_cursor_requests:
                    # Cursor stack unexpectedly empty; reset our counter to keep it accurate
                    self._wait_cursor_requests = 0
            elif show_wait and app.overrideCursor():
                # Fallback for callers expecting an unconditional restore
                app.restoreOverrideCursor()
            openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

        if not ignore:
            self.refreshFrameSignal.emit()
            self.propertyTableView.select_frame(self.preview_thread.player.Position())

        # Keep track of ignore / not ignore
        self.ignore_updates = ignore

    def style_dock_widgets(self):
        """Check if any dock widget is part of a tabbed group and hide the title text if tabbed."""
        theme = None
        if get_app().theme_manager:
            theme = get_app().theme_manager.get_current_theme()

        for dock_widget in self.getDocks():
            # Check if dock is tabbed with other widgets
            tabified_widgets = self.tabifiedDockWidgets(dock_widget)

            if dock_widget.objectName() == "dockTimeline":
                # Hide title bar for timeline widget (ALL themes)
                dock_widget.setTitleBarWidget(QWidget())

            elif theme and theme.name == ThemeName.COSMIC.value:
                # handle COSMIC theme dock widgets
                if tabified_widgets:
                    # Apply custom title bar with grab handle (for grouped/tabbed docks)
                    dock_widget.setTitleBarWidget(HiddenTitleBar(dock_widget, ""))
                elif dock_widget.isFloating():
                    # Use standard system title bar (minimize, maximize, close) for floating docks
                    dock_widget.setTitleBarWidget(None)
                else:
                    # Apply custom title bar with text (no grab handle) for non-tabbed, non-floating docks
                    dock_widget.setTitleBarWidget(HiddenTitleBar(dock_widget, dock_widget.windowTitle()))

            else:
                # for ALL other themes, regardless of floating or tabbed
                # Use standard system title bar (minimize, maximize, close)
                dock_widget.setTitleBarWidget(None)

        # Set tab drawBase property
        self.set_tab_drawbase()

    def set_tab_drawbase(self):
        """Set the drawBase property on all QTabBar objects. This draws a line
        under the tabs, and is not required on all themes."""
        # Get theme tab property
        if get_app().theme_manager:
            theme = get_app().theme_manager.get_current_theme()
            if not theme:
                log.warning("No theme loaded yet. Skip setting TabBar drawBase property.")
                return
            # Each theme can optionally include this property
            draw_base = theme.get_int("QTabBar", "qproperty-drawBase")

            # Loop through all QTabBar objects
            tab_bars = self.findChildren(QTabBar)
            for tab_bar in tab_bars:
                if draw_base is None:
                    tab_bar.setProperty("drawBase", True)
                else:
                    tab_bar.setProperty("drawBase", draw_base)

    def __init__(self, *args):

        # Create main window base class
        super().__init__(*args)
        self.initialized = False
        self.shutting_down = False
        self.lock = threading.Lock()
        self.installEventFilter(self)

        # set window on app for reference during initialization of children
        app = get_app()
        app.window = self
        _ = app._tr

        # Initialize a few things needed to exist
        self.http_server_thread = None
        self.preview_thread = None
        self.timeline_sync = None

        # Load user settings for window
        s = app.get_settings()
        self.recent_menu = None
        self.restore_menu = None

        # Track metrics
        track_metric_session()  # start session

        # Set unique install id (if blank)
        if not s.get("unique_install_id"):
            # This is assumed to be the 1st launch
            s.set("unique_install_id", str(uuid4()))

            # Track 1st launch metric
            track_metric_screen("initial-launch-screen")

            # Track 1st main screen
            track_metric_screen("main-screen")

            # Opt-out of metrics tracking on 1st launch (and prompt user)
            track_metric_screen("metrics-opt-out")
            s.set("send_metrics", False)
        else:
            # Only track main screen
            track_metric_screen("main-screen")

        # Set unique id for Sentry
        sentry.set_user({"id": s.get("unique_install_id")})

        # Create blank tutorial manager
        self.tutorial_manager = None

        # Load UI from designer
        self.selected_items = []
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Create dock toolbars, set initial state of items, etc
        self.setup_toolbars()

        # Add window as watcher to receive undo/redo status updates
        app.updates.add_watcher(self)


        # Initialize and start the thumbnail HTTP server
        try:
            self.http_server_thread = httpThumbnailServerThread()
            self.http_server_thread.start()

        except httpThumbnailException as ex:
            # Show error message to user
            msg = QMessageBox()
            msg.setWindowTitle(_("Error starting local HTTP server"))
            error_title = _("Failed multiple attempts to start server:")
            msg.setText(f"{error_title}\n\n{ex}")
            msg.exec_()

            # Quit event loop, and stop initializing main window
            log.info(f"Quiting Flowcut due to failed local HTTP thumbnail server: {ex}")
            get_app().mode = "quit"
            return

        # Connect signals
        self.RecoverBackup.connect(self.recover_backup)
        self.SeekPreviousFrame.connect(self.handleSeekPreviousFrame)
        self.SeekNextFrame.connect(self.handleSeekNextFrame)
        self.PlayPauseToggleSignal.connect(self.handlePlayPauseToggleSignal)

        # Create the timeline sync object (used for previewing timeline)
        self.timeline_sync = TimelineSync(self)

        # Setup timeline
        self.timeline = TimelineView(self)
        self.frameWeb.layout().addWidget(self.timeline)

        # Configure the side docks to full-height
        self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        self.initModels()

        # Setup AI Chat Dialog (must be before addViewDocksMenu)
        from windows.ai_chat_ui import AIChatWindow
        self.dockAIChat = AIChatWindow(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockAIChat)

        # Setup AI Media Panel (must be before addViewDocksMenu)
        from windows.ai_media_panel import AIMediaPanel
        self.dockAIMedia = AIMediaPanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockAIMedia)
        self.dockAIMedia.setVisible(False)  # Hidden by default

        # Setup Director Panel (must be before addViewDocksMenu)
        try:
            from windows.director_panel_ui import get_director_panel_dock
            self.dockDirectorPanel = get_director_panel_dock(self)
            self.addDockWidget(Qt.RightDockWidgetArea, self.dockDirectorPanel)
            self.dockDirectorPanel.setVisible(False)  # Hidden by default
        except Exception as e:
            log.error(f"Failed to initialize Director Panel: {e}", exc_info=True)

        # Setup Plan Review Panel (must be before addViewDocksMenu)
        try:
            from windows.director_plan_review_ui import get_plan_review_dock
            self.dockPlanReview = get_plan_review_dock(self)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.dockPlanReview)
            self.dockPlanReview.setVisible(False)  # Hidden by default

            # Connect plan approval to execution
            self.dockPlanReview.plan_approved.connect(self.on_plan_approved)
            self.dockPlanReview.plan_rejected.connect(self.on_plan_rejected)
        except Exception as e:
            log.error(f"Failed to initialize Plan Review: {e}", exc_info=True)

        # Plan Graph dock (edit plan hierarchy)
        from plan_graph import PlanGraphDock
        self.plan_graph_dock = PlanGraphDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.plan_graph_dock)
        self.plan_graph_dock.setVisible(False)

        # Thinking dock (director communication window)
        try:
            from windows.thinking_dock import ThinkingDockWidget
            self.thinking_dock = ThinkingDockWidget(self)
            self.addDockWidget(Qt.RightDockWidgetArea, self.thinking_dock)
            self.thinking_dock.setVisible(False)  # Hidden by default, shown when directors run
        except Exception as e:
            log.error(f"Failed to initialize Thinking Dock: {e}", exc_info=True)

        # Add Docks submenu to View menu
        self.addViewDocksMenu()

        # Set up status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Process events before continuing
        # TODO: Figure out why this is needed for a backup recovery to correctly show up on the timeline
        app.processEvents()

        # Setup properties table
        self.txtPropertyFilter.setPlaceholderText(_("Filter"))
        self.propertyTableView = PropertiesTableView(self)
        self.selectionLabel = SelectionLabel(self)
        self.dockPropertiesContents.layout().addWidget(self.selectionLabel, 0, 1)
        self.dockPropertiesContents.layout().addWidget(self.propertyTableView, 2, 1)

        # Show Property timer
        # Timer to use a delay before showing properties
        # (to prevent a mass selection from trying
        # to update the property model hundreds of times)
        self.show_property_id = None
        self.show_property_type = None
        self.show_property_timer = QTimer(self)
        self.show_property_timer.setInterval(100)
        self.show_property_timer.setSingleShot(True)
        self.show_property_timer.timeout.connect(self.show_property_timeout)

        # Selection timer
        # Timer to use a delay before emitting selection signal
        # (to prevent a mass selection from trying
        # to update the zoom slider widget hundreds of times)
        self.selection_timer = QTimer(self)
        self.selection_timer.setInterval(100)
        self.selection_timer.setSingleShot(True)
        self.selection_timer.timeout.connect(self.emit_selection_signal)

        # Init selection containers
        self.clearSelections()

        # Setup video preview QWidget
        self.videoPreview = VideoWidget()
        self.videoPreview.setObjectName("videoPreview")
        self.tabVideo.layout().insertWidget(0, self.videoPreview)

        # Load window state and geometry
        self.saved_state = None
        self.saved_geometry = None
        self.saved_timeline_height = None
        self._restored_saved_window = False
        self._timeline_height_restored = False
        self.load_settings()
        
        # Hide AI Chat dock by default (ensure it stays hidden even after restore state)
        self.dockAIChat.hide()

        # Setup Cache settings
        self.cache_object = None
        self.InitCacheSettings()

        # Start the preview thread
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.timeline_sync.timeline, self.videoPreview)
        self.preview_thread = self.preview_parent.worker
        self.sliderZoomWidget.connect_playback()
        self.timeline.connect_playback()

        # Set play/pause callbacks
        self.PauseSignal.connect(self.onPauseCallback)
        self.PlaySignal.connect(self.onPlayCallback)

        # QTimer for Autosave
        minutes = 1000 * 60
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setInterval(
            int(s.get("autosave-interval") * minutes))
        self.auto_save_timer.timeout.connect(self.auto_save_project)
        if s.get("enable-auto-save"):
            self.auto_save_timer.start()

        lib_settings = openshot.Settings.Instance()

        # Set encoding method
        if s.get("hw-decoder"):
            lib_settings.HARDWARE_DECODER = int(str(s.get("hw-decoder")))
        else:
            lib_settings.HARDWARE_DECODER = 0

        # Set graphics card for decoding
        if s.get("graca_number_de"):
            lib_settings.HW_DE_DEVICE_SET = int(
                str(s.get("graca_number_de")))
        else:
            lib_settings.HW_DE_DEVICE_SET = 0

        # Set graphics card for encoding
        if s.get("graca_number_en"):
                lib_settings.HW_EN_DEVICE_SET = int(
                    str(s.get("graca_number_en")))
        else:
            lib_settings.HW_EN_DEVICE_SET = 0

        # Set audio device settings (used for playback of audio)
        # - OLD settings only includes device name (i.e. "PulseAudio Sound Server")
        # - NEW settings include both device name and type (double pipe delimited)
        #   (i.e. "PulseAudio Sound Server||ALSA")
        playback_buffer_size = s.get("playback-buffer-size") or 512
        playback_device_value = s.get("playback-audio-device") or ""
        playback_device_parts = playback_device_value.split("||")
        playback_device_name = playback_device_parts[0]
        playback_device_type = ""
        if len(playback_device_parts) == 2:
            # This might be empty for older settings, which only included the device name
            playback_device_type = playback_device_parts[1]
        # Set libopenshot settings
        lib_settings.PLAYBACK_AUDIO_DEVICE_NAME = playback_device_name
        lib_settings.PLAYBACK_AUDIO_DEVICE_TYPE = playback_device_type
        lib_settings.PLAYBACK_AUDIO_BUFFER_SIZE = playback_buffer_size

        # Set scaling mode to lower quality scaling (for faster previews)
        lib_settings.HIGH_QUALITY_SCALING = False

        # Set use omp threads number environment variable
        if s.get("omp_threads_number"):
            lib_settings.OMP_THREADS = max(
                2, int(str(s.get("omp_threads_number"))))
        else:
            lib_settings.OMP_THREADS = 12

        # Set use ffmpeg threads number environment variable
        if s.get("ff_threads_number"):
            lib_settings.FF_THREADS = max(
                1, int(str(s.get("ff_threads_number"))))
        else:
            lib_settings.FF_THREADS = 8

        # Set use max width decode hw environment variable
        if s.get("decode_hw_max_width"):
            lib_settings.DE_LIMIT_WIDTH_MAX = int(
                str(s.get("decode_hw_max_width")))

        # Set use max height decode hw environment variable
        if s.get("decode_hw_max_height"):
            lib_settings.DE_LIMIT_HEIGHT_MAX = int(
                str(s.get("decode_hw_max_height")))

        # Create lock file
        self.create_lock_file()

        # Connect OpenProject Signal
        self.OpenProjectSignal.connect(self.open_project)

        # Connect Selection signals
        self.SelectionAdded.connect(self.addSelection)
        self.SelectionRemoved.connect(self.removeSelection)

        # Connect 'ignore update' signal
        self.ignore_updates = False
        self._wait_cursor_requests = 0
        self.IgnoreUpdates.connect(self.ignore_updates_callback)

        # Connect playhead moved signals
        self.SeekSignal.connect(self.handleSeek)

        # Connect theme changed signal
        self.ThemeChangedSignal.connect(self.style_dock_widgets)

        # Connect the signals for each dock widget from self.getDocks()
        for dock_widget in self.getDocks():
            dock_widget.dockLocationChanged.connect(self.style_dock_widgets)

        # Ensure toolbar is movable when floated (even with docks frozen)
        self.toolBar.topLevelChanged.connect(
            functools.partial(self.freezeMainToolBar, None))

        # Create tutorial manager
        self.tutorial_manager = TutorialManager(self)

        # Apply theme
        theme_name = s.get("theme")
        theme = get_app().theme_manager.apply_theme(theme_name)
        s.set("theme", theme.name)

        # Save settings
        s.save()

        # Refresh frame
        QTimer.singleShot(100, self.refreshFrameSignal.emit)

        # Main window is initialized
        self.initialized = True

        # Init all Keyboard shortcuts
        self.initShortcuts()
