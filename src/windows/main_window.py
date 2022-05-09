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

import os
import shutil
import webbrowser
import functools
from copy import deepcopy
from time import sleep
from uuid import uuid4

import openshot  # Python module for libopenshot (required video editing module installed separately)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QCoreApplication, PYQT_VERSION_STR,
    QTimer, QDateTime, QFileInfo, QUrl,
    )
from PyQt5.QtGui import QIcon, QCursor, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QDockWidget,
    QMessageBox, QDialog, QFileDialog, QInputDialog,
    QAction, QActionGroup, QSizePolicy,
    QStatusBar, QToolBar, QToolButton,
    QLineEdit, QComboBox, QTextEdit
)

from classes import exceptions, info, qt_types, sentry, ui_util, updates
from classes.app import get_app
from classes.exporters.edl import export_edl
from classes.exporters.final_cut_pro import export_xml
from classes.importers.edl import import_edl
from classes.importers.final_cut_pro import import_xml
from classes.logger import log
from classes.metrics import track_metric_session, track_metric_screen
from classes.query import Clip, Transition, Marker, Track, Effect
from classes.thumbnail import httpThumbnailServerThread
from classes.time_parts import secondsToTimecode
from classes.timeline import TimelineSync
from classes.version import get_current_Version
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
from windows.views.webview import TimelineWebView
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
    PlaySignal = pyqtSignal(int)
    PauseSignal = pyqtSignal()
    StopSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    RecoverBackup = pyqtSignal()
    FoundVersionSignal = pyqtSignal(str)
    WaveformReady = pyqtSignal(str, list)
    TransformSignal = pyqtSignal(str)
    KeyFrameTransformSignal = pyqtSignal(str, str)
    SelectRegionSignal = pyqtSignal(str)
    MaxSizeChanged = pyqtSignal(object)
    InsertKeyframe = pyqtSignal(object)
    OpenProjectSignal = pyqtSignal(str)
    ThumbnailUpdated = pyqtSignal(str)
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

    # Docks are closable, movable and floatable
    docks_frozen = False

    # Save window settings on close
    def closeEvent(self, event):

        app = get_app()
        # Some window managers handels dragging of the modal messages incorrectly if other windows are open
        # Hide tutorial window first
        self.tutorial_manager.hide_dialog()

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

        # Log the exit routine
        log.info('---------------- Shutting down -----------------')

        # Close any tutorial dialogs
        self.tutorial_manager.exit_manager()

        # Save settings
        self.save_settings()

        # Track end of session
        track_metric_session(False)

        # Stop threads
        self.StopSignal.emit()

        # Stop thumbnail server thread
        self.http_server_thread.kill()

        # Stop ZMQ polling thread
        get_app().logger_libopenshot.kill()

        # Process any queued events
        QCoreApplication.processEvents()

        # Stop preview thread (and wait for it to end)
        self.preview_thread.player.CloseAudioDevice()
        self.preview_thread.kill()
        self.preview_parent.background.exit()
        self.preview_parent.background.wait(5000)

        # Close Timeline
        if self.timeline_sync and self.timeline_sync.timeline:
            self.timeline_sync.timeline.Close()
            self.timeline_sync.timeline = None

        # Destroy lock file
        self.destroy_lock_file()

    def recover_backup(self):
        """Recover the backup file (if any)"""
        log.info("recover_backup")

        # Check for backup.osp file
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
            self.SetWindowTitle()

    def create_lock_file(self):
        """Create a lock file"""
        lock_path = os.path.join(info.USER_PATH, ".lock")
        # Check if it already exists
        if os.path.exists(lock_path):
            last_log_line = exceptions.libopenshot_crash_recovery() or "No Log Detected"
            log.error(f"Unhandled crash detected: {last_log_line}")
            self.destroy_lock_file()
        else:
            # Normal startup, clear thumbnails
            self.clear_temporary_files()

        # Reset Sentry component (it can be temporarily changed to libopenshot during
        # the call to libopenshot_crash_recovery above)
        sentry.set_tag("component", "openshot-qt")

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

        # Clear any previous thumbnails
        self.clear_temporary_files()

        # clear data and start new project
        app.project.load("")
        app.updates.reset()
        self.updateStatusChanged(False, False)

        # Reset selections
        self.clearSelections()

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
            self.ThumbnailUpdated.emit(c.id)

        # Update preview
        self.refreshFrameSignal.emit()

    def actionDuplicateTitle_trigger(self):

        file_path = None

        # Loop through selected files (set 1 selected file if more than 1)
        for f in self.selected_files():
            if f.data.get("path").endswith(".svg"):
                file_path = f.data.get("path")
                break

        if not file_path:
            return

        # show dialog for editing title
        from windows.title_editor import TitleEditor
        win = TitleEditor(edit_file_path=file_path, duplicate=True)
        # Run the dialog event loop - blocking interaction on this window during that time
        return win.exec_()

    def actionClearHistory_trigger(self):
        """Clear history for current project"""
        project = get_app().project
        project.has_unsaved_changes = True
        get_app().updates.reset()
        log.info('History cleared')

    def save_project(self, file_path):
        """ Save a project to a file path, and refresh the screen """
        app = get_app()
        _ = app._tr  # Get translation function

        try:
            # Update history in project data
            s = app.get_settings()
            app.updates.save_history(app.project, s.get("history-limit"))

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

    def open_project(self, file_path, clear_thumbnails=True):
        """ Open a project from a file path, and refresh the screen """

        app = get_app()
        _ = app._tr  # Get translation function

        # First check for empty file_path (probably user cancellation)
        if not file_path:
            # Ignore the request
            return

        # Stop preview thread
        self.SpeedSignal.emit(0)
        self.PauseSignal.emit()
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
                self.actionSave.trigger()
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
                app.updates.reset()
                app.updates.load_history(app.project)

                # Reset selections
                self.clearSelections()

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

        # Prompt for open project file
        file_path = QFileDialog.getOpenFileName(
            self,
            _("Open Project..."),
            recommended_folder,
            _("OpenShot Project (*.osp)"))[0]

        if file_path:
            # Don't open if dialog canceled.
            s.setDefaultPath(s.actionType.LOAD,file_path)

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
                _("Untitled Project") + ".osp"
            )
            file_path = QFileDialog.getSaveFileName(
                self,
                _("Save Project..."),
                recommended_path,
                _("OpenShot Project (*.osp)"))[0]

        if file_path:
            s.setDefaultPath(s.actionType.SAVE, file_path)
            # Append .osp if needed
            if not file_path.endswith(".osp"):
                file_path = "%s.osp" % file_path

            # Save project
            self.save_project(file_path)

    def auto_save_project(self):
        """Auto save the project"""
        import time

        app = get_app()
        s = app.get_settings()

        # Get current filepath (if any)
        file_path = app.project.current_filepath
        if not app.project.needs_save():
            return

        if file_path:
            # A Real project file exists
            # Append .osp if needed
            if not file_path.endswith(".osp"):
                    file_path = "%s.osp" % file_path
            folder_path, file_name = os.path.split(file_path)
            file_name, file_ext = os.path.splitext(file_name)

            # Make copy of unsaved project file in 'recovery' folder
            recover_path_with_timestamp = os.path.join(
                info.RECOVERY_PATH, "%d-%s.osp" % (int(time.time()), file_name))
            if os.path.exists(file_path):
                shutil.copy(file_path, recover_path_with_timestamp)
            else:
                log.warning(
                    "Existing project *.osp file not found during recovery process: %s",
                    file_path)

            # Find any recovery file older than X auto-saves
            old_backup_files = []
            backup_file_count = 0
            for backup_filename in reversed(sorted(os.listdir(info.RECOVERY_PATH))):
                if ".osp" in backup_filename:
                    backup_file_count += 1
                    if backup_file_count > s.get("recovery-limit"):
                        old_backup_files.append(os.path.join(info.RECOVERY_PATH, backup_filename))

            # Delete recovery files which are 'too old'
            for backup_filepath in old_backup_files:
                os.unlink(backup_filepath)

            # Save project
            log.info("Auto save project file: %s", file_path)
            self.save_project(file_path)

            # Remove backup.osp (if any)
            if os.path.exists(info.BACKUP_FILE):
                # Delete backup.osp since we just saved the actual project
                os.unlink(info.BACKUP_FILE)

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
            recommended_file_name = "%s.osp" % _("Untitled Project")
        recommended_folder = s.getDefaultPath(s.actionType.SAVE)
        recommended_path = os.path.join(
            recommended_folder,
            recommended_file_name
        )
        file_path = QFileDialog.getSaveFileName(
            self,
            _("Save Project As..."),
            recommended_path,
            _("OpenShot Project (*.osp)"))[0]
        if file_path:
            s.setDefaultPath(s.actionType.SAVE, file_path)
            # Append .osp if needed
            if ".osp" not in file_path:
                file_path = "%s.osp" % file_path

            # Save new project
            self.save_project(file_path)

    def actionImportFiles_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        recommended_path = s.getDefaultPath(s.actionType.IMPORT)

        # PyQt through 5.13.0 had the 'directory' argument mis-typed as str
        if PYQT_VERSION_STR < '5.13.1':
            dir_type = "str"
            start_location = str(recommended_path)
        else:
            dir_type = "QUrl"
            start_location = QUrl.fromLocalFile(recommended_path)

        log.debug("Calling getOpenFileURLs() with %s directory argument", dir_type)
        qurl_list = QFileDialog.getOpenFileUrls(
            self,
            _("Import Files..."),
            start_location,
            )[0]

        if len(qurl_list):
            # If any files were imported,
            # Use the folder of the LAST one as the new default path.
            s.setDefaultPath(s.actionType.IMPORT, qurl_list[-1].path())
        # Set cursor to waiting
        app.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:
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

    def actionHelpContents_trigger(self, checked=True):
        try:
            webbrowser.open("https://www.openshot.org/%suser-guide/?app-menu" % info.website_language(), new=1)
        except Exception:
            QMessageBox.information(self, "Error !", "Unable to open the online help")
            log.error("Unable to open the Help Contents", exc_info=1)

    def actionAbout_trigger(self, checked=True):
        """Show about dialog"""
        from windows.about import About
        win = About()
        # Run the dialog event loop - blocking interaction on this window during this time
        win.exec_()

    def actionReportBug_trigger(self, checked=True):
        try:
            webbrowser.open("https://www.openshot.org/%sissues/new/?app-menu" % info.website_language(), new=1)
        except Exception:
            QMessageBox.information(self, "Error !", "Unable to open the Bug Report GitHub Issues web page")
            log.error("Unable to open the Bug Report page", exc_info=1)

    def actionAskQuestion_trigger(self, checked=True):
        try:
            webbrowser.open("https://www.reddit.com/r/OpenShot/", new=1)
        except Exception:
            QMessageBox.information(self, "Error !", "Unable to open the official OpenShot subreddit web page")
            log.error("Unable to open the subreddit page", exc_info=1)

    def actionTranslate_trigger(self, checked=True):
        try:
            webbrowser.open("https://translations.launchpad.net/openshot/2.0", new=1)
        except Exception:
            QMessageBox.information(self, "Error !", "Unable to open the Translation web page")
            log.error("Unable to open the translation page", exc_info=1)

    def actionDonate_trigger(self, checked=True):
        try:
            webbrowser.open("https://www.openshot.org/%sdonate/?app-menu" % info.website_language(), new=1)
        except Exception:
            QMessageBox.information(self, "Error !", "Unable to open the Donate web page")
            log.error("Unable to open the donation page", exc_info=1)

    def actionUpdate_trigger(self, checked=True):
        try:
            webbrowser.open("https://www.openshot.org/%sdownload/?app-toolbar" % info.website_language(), new=1)
        except Exception:
            QMessageBox.information(self, "Error !", "Unable to open the Download web page")
            log.error("Unable to open the download page", exc_info=1)

    def should_play(self, requested_speed=0):
        """Determine if we should start playback, based on the current frame
        and the total number of frames in our timeline clips. For example,
        if we are at the end of our last clip, and the user clicks play, we
        do not want to start playback."""
        # Get max frame (based on last clip) and current frame
        max_frame = get_app().window.timeline_sync.timeline.GetMaxFrame()
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
                max_frame = get_app().window.timeline_sync.timeline.GetMaxFrame()
                self.PlaySignal.emit(max_frame)
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
        win.show()

    def previewFrame(self, position_frames):
        """Preview a specific frame"""
        # Notify preview thread
        self.previewFrameSignal.emit(position_frames)

        # Notify properties dialog
        self.propertyTableView.select_frame(position_frames)

    def movePlayhead(self, position_frames):
        """Update playhead position"""
        # Notify preview thread
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
            self.actionPlay.trigger()

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
                self.actionPlay.trigger()
            self.SpeedSignal.emit(requested_speed)

    def actionJumpStart_trigger(self, checked=True):
        log.debug("actionJumpStart_trigger")

        # Seek to the 1st frame
        self.SeekSignal.emit(1)

    def actionJumpEnd_trigger(self, checked=True):
        log.debug("actionJumpEnd_trigger")

        # Determine last frame (based on clips) & seek there
        max_frame = get_app().window.timeline_sync.timeline.GetMaxFrame()
        self.SeekSignal.emit(max_frame)

    def onPlayCallback(self):
        """Handle when playback is started"""
        # Set icon on Play button
        ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")

    def onPauseCallback(self):
        """Handle when playback is paused"""
        # Refresh property window
        self.propertyTableView.select_frame(self.preview_thread.player.Position())

        # Set icon on Pause button
        ui_util.setup_icon(self, self.actionPlay, "actionPlay")

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

        app.updates.update_untracked(["export_path"], os.path.dirname(framePath))
        log.info("Saving frame to %s", framePath)

        # Pause playback
        self.SpeedSignal.emit(0)
        self.PauseSignal.emit()

        # Save current cache object and create a new CacheMemory object (ignore quality and scale prefs)
        old_cache_object = self.cache_object
        new_cache_object = openshot.CacheMemory(app.get_settings().get("cache-limit-mb") * 1024 * 1024)
        self.timeline_sync.timeline.SetCache(new_cache_object)

        # Set MaxSize to full project resolution and clear preview cache so we get a full resolution frame
        self.timeline_sync.timeline.SetMaxSize(app.project.get("width"), app.project.get("height"))
        self.cache_object.Clear()

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
        self.cache_object.Clear()
        self.timeline_sync.timeline.SetCache(old_cache_object)
        self.cache_object = old_cache_object
        old_cache_object = None
        new_cache_object = None

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

        # Enable / Disable snapping mode
        self.timeline.SetSnappingMode(self.actionSnappingTool.isChecked())

    def actionRazorTool_trigger(self, checked=True):
        """Toggle razor tool on and off"""
        log.info('actionRazorTool_trigger')

        # Enable / Disable razor mode
        self.timeline.SetRazorMode(checked)

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
            """ Add boundaries & all keyframes of a timeline object (clip, transition...) to all_marker_positions """
            positions = []

            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            clip_start_time = obj.data["position"]
            clip_orig_time = clip_start_time - obj.data["start"]
            clip_stop_time = clip_orig_time + obj.data["end"]

            # add clip boundaries
            positions.append(clip_start_time)
            positions.append(clip_stop_time)

            # add all keyframes
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

            # Add all Effect keyframes
            if "effects" in obj.data:
                for effect_data in obj.data["effects"]:
                    for prop in effect_data:
                        try:
                            # Try looping through keyframe points
                            for point in effect_data[prop]["Points"]:
                                keyframe_time = (point["co"]["X"]-1)/fps_float + clip_orig_time
                                if clip_start_time < keyframe_time < clip_stop_time:
                                    positions.append(keyframe_time)
                        except (TypeError, KeyError):
                            pass
                        try:
                            # Try looping through color keyframe points
                            for point in effect_data[prop]["red"]["Points"]:
                                keyframe_time = (point["co"]["X"]-1)/fps_float + clip_orig_time
                                if clip_start_time < keyframe_time < clip_stop_time:
                                    positions.append(keyframe_time)
                        except (TypeError, KeyError):
                            pass

            return positions

        # We can always jump to the beginning of the timeline
        all_marker_positions = [0]

        # If nothing is selected, also add the end of the last clip
        if not self.selected_clips + self.selected_transitions:
            all_marker_positions.append(
                get_app().window.timeline_sync.timeline.GetMaxTime())

        # Get list of marker and important positions (like selected clip bounds)
        for marker in Marker.filter():
            all_marker_positions.append(marker.data["position"])

        # Loop through selected clips (and add key positions)
        for clip_id in self.selected_clips:
            # Get selected object
            selected_clip = Clip.get(id=clip_id)
            if selected_clip:
                all_marker_positions.extend(getTimelineObjectPositions(selected_clip))

        # Loop through selected transitions (and add key positions)
        for tran_id in self.selected_transitions:
            # Get selected object
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
            if marker_position < current_position and (abs(marker_position - current_position) > 0.1):
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

            # Update the preview and reselct current frame in properties
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
            if marker_position > current_position and (abs(marker_position - current_position) > 0.1):
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

    def getShortcutByName(self, setting_name):
        """ Get a key sequence back from the setting name """
        s = get_app().get_settings()
        shortcut = QKeySequence(s.get(setting_name))
        return shortcut

    def getAllKeyboardShortcuts(self):
        """ Get a key sequence back from the setting name """
        keyboard_shortcuts = []
        all_settings = get_app().get_settings()._data
        for setting in all_settings:
            if setting.get('category') == 'Keyboard':
                keyboard_shortcuts.append(setting)
        return keyboard_shortcuts

    def keyPressEvent(self, event):
        """ Process key press events and match with known shortcuts"""
        # Detect the current KeySequence pressed (including modifier keys)
        key_value = event.key()
        modifiers = int(event.modifiers())

        # Abort handling if the key sequence is invalid
        if (key_value <= 0 or key_value in
           [Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Control, Qt.Key_Meta]):
            return

        # A valid keysequence was detected
        event.accept()
        key = QKeySequence(modifiers + key_value)

        # Get the video player object
        player = self.preview_thread.player

        # Get framerate
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        playhead_position = float(self.preview_thread.current_frame - 1) / fps_float

        # Basic shortcuts i.e just a letter
        if key.matches(self.getShortcutByName("seekPreviousFrame")) == QKeySequence.ExactMatch:
            # Pause video
            self.PauseSignal.emit()
            self.SpeedSignal.emit(0)
            # Seek to previous frame
            self.SeekSignal.emit(player.Position() - 1)

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif key.matches(self.getShortcutByName("seekNextFrame")) == QKeySequence.ExactMatch:
            # Pause video
            self.PauseSignal.emit()
            self.SpeedSignal.emit(0)
            # Seek to next frame
            self.SeekSignal.emit(player.Position() + 1)

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif key.matches(self.getShortcutByName("rewindVideo")) == QKeySequence.ExactMatch:
            # Toggle rewind and start playback
            self.actionRewind.trigger()

        elif key.matches(self.getShortcutByName("fastforwardVideo")) == QKeySequence.ExactMatch:
            # Toggle fastforward button and start playback
            self.actionFastForward.trigger()

        elif any([
                key.matches(self.getShortcutByName("playToggle")) == QKeySequence.ExactMatch,
                key.matches(self.getShortcutByName("playToggle1")) == QKeySequence.ExactMatch,
                key.matches(self.getShortcutByName("playToggle2")) == QKeySequence.ExactMatch,
                key.matches(self.getShortcutByName("playToggle3")) == QKeySequence.ExactMatch,
                ]):
            # Toggle playbutton and show properties
            self.actionPlay.trigger()
            self.propertyTableView.select_frame(player.Position())

        elif any([
                key.matches(self.getShortcutByName("deleteItem")) == QKeySequence.ExactMatch,
                key.matches(self.getShortcutByName("deleteItem1")) == QKeySequence.ExactMatch,
                ]):
            # Delete selected clip / transition
            self.actionRemoveClip.trigger()
            self.actionRemoveTransition.trigger()

        # Menu shortcuts
        elif key.matches(self.getShortcutByName("actionNew")) == QKeySequence.ExactMatch:
            self.actionNew.trigger()
        elif key.matches(self.getShortcutByName("actionOpen")) == QKeySequence.ExactMatch:
            self.actionOpen.trigger()
        elif key.matches(self.getShortcutByName("actionSave")) == QKeySequence.ExactMatch:
            self.actionSave.trigger()
        elif key.matches(self.getShortcutByName("actionUndo")) == QKeySequence.ExactMatch:
            self.actionUndo.trigger()
        elif key.matches(self.getShortcutByName("actionSaveAs")) == QKeySequence.ExactMatch:
            self.actionSaveAs.trigger()
        elif key.matches(self.getShortcutByName("actionImportFiles")) == QKeySequence.ExactMatch:
            self.actionImportFiles.trigger()
        elif key.matches(self.getShortcutByName("actionRedo")) == QKeySequence.ExactMatch:
            self.actionRedo.trigger()
        elif key.matches(self.getShortcutByName("actionExportVideo")) == QKeySequence.ExactMatch:
            self.actionExportVideo.trigger()
        elif key.matches(self.getShortcutByName("actionQuit")) == QKeySequence.ExactMatch:
            self.actionQuit.trigger()
        elif key.matches(self.getShortcutByName("actionPreferences")) == QKeySequence.ExactMatch:
            self.actionPreferences.trigger()
        elif key.matches(self.getShortcutByName("actionAddTrack")) == QKeySequence.ExactMatch:
            self.actionAddTrack.trigger()
        elif key.matches(self.getShortcutByName("actionAddMarker")) == QKeySequence.ExactMatch:
            self.actionAddMarker.trigger()
        elif key.matches(self.getShortcutByName("actionPreviousMarker")) == QKeySequence.ExactMatch:
            self.actionPreviousMarker.trigger()
        elif key.matches(self.getShortcutByName("actionNextMarker")) == QKeySequence.ExactMatch:
            self.actionNextMarker.trigger()
        elif key.matches(self.getShortcutByName("actionCenterOnPlayhead")) == QKeySequence.ExactMatch:
            self.actionCenterOnPlayhead.trigger()
        elif key.matches(self.getShortcutByName("actionTimelineZoomIn")) == QKeySequence.ExactMatch:
            self.actionTimelineZoomIn.trigger()
        elif key.matches(self.getShortcutByName("actionTimelineZoomOut")) == QKeySequence.ExactMatch:
            self.actionTimelineZoomOut.trigger()
        elif key.matches(self.getShortcutByName("actionTitle")) == QKeySequence.ExactMatch:
            self.actionTitle.trigger()
        elif key.matches(self.getShortcutByName("actionAnimatedTitle")) == QKeySequence.ExactMatch:
            self.actionAnimatedTitle.trigger()
        elif key.matches(self.getShortcutByName("actionDuplicateTitle")) == QKeySequence.ExactMatch:
            self.actionDuplicateTitle.trigger()
        elif key.matches(self.getShortcutByName("actionEditTitle")) == QKeySequence.ExactMatch:
            self.actionEditTitle.trigger()
        elif key.matches(self.getShortcutByName("actionFullscreen")) == QKeySequence.ExactMatch:
            self.actionFullscreen.trigger()
        elif key.matches(self.getShortcutByName("actionAbout")) == QKeySequence.ExactMatch:
            self.actionAbout.trigger()
        elif key.matches(self.getShortcutByName("actionThumbnailView")) == QKeySequence.ExactMatch:
            self.actionThumbnailView.trigger()
        elif key.matches(self.getShortcutByName("actionDetailsView")) == QKeySequence.ExactMatch:
            self.actionDetailsView.trigger()
        elif key.matches(self.getShortcutByName("actionProfile")) == QKeySequence.ExactMatch:
            self.actionProfile.trigger()
        elif key.matches(self.getShortcutByName("actionAdd_to_Timeline")) == QKeySequence.ExactMatch:
            self.actionAdd_to_Timeline.trigger()
        elif key.matches(self.getShortcutByName("actionSplitClip")) == QKeySequence.ExactMatch:
            self.actionSplitClip.trigger()
        elif key.matches(self.getShortcutByName("actionSnappingTool")) == QKeySequence.ExactMatch:
            self.actionSnappingTool.trigger()
        elif key.matches(self.getShortcutByName("actionJumpStart")) == QKeySequence.ExactMatch:
            self.actionJumpStart.trigger()
        elif key.matches(self.getShortcutByName("actionJumpEnd")) == QKeySequence.ExactMatch:
            self.actionJumpEnd.trigger()
        elif key.matches(self.getShortcutByName("actionSaveFrame")) == QKeySequence.ExactMatch:
            self.actionSaveFrame.trigger()
        elif key.matches(self.getShortcutByName("actionProperties")) == QKeySequence.ExactMatch:
            self.actionProperties.trigger()
        elif key.matches(self.getShortcutByName("actionTransform")) == QKeySequence.ExactMatch:
            if self.selected_clips:
                self.TransformSignal.emit(self.selected_clips[0])
        elif key.matches(self.getShortcutByName("actionInsertKeyframe")) == QKeySequence.ExactMatch:
            log.debug("actionInsertKeyframe")
            if self.selected_clips or self.selected_transitions:
                self.InsertKeyframe.emit(event)

        # Timeline keyboard shortcuts
        elif key.matches(self.getShortcutByName("sliceAllKeepBothSides")) == QKeySequence.ExactMatch:
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if intersecting_clips or intersecting_trans:
                # Get list of clip ids
                clip_ids = [c.id for c in intersecting_clips]
                trans_ids = [t.id for t in intersecting_trans]
                self.timeline.Slice_Triggered(0, clip_ids, trans_ids, playhead_position)
        elif key.matches(self.getShortcutByName("sliceAllKeepLeftSide")) == QKeySequence.ExactMatch:
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if intersecting_clips or intersecting_trans:
                # Get list of clip ids
                clip_ids = [c.id for c in intersecting_clips]
                trans_ids = [t.id for t in intersecting_trans]
                self.timeline.Slice_Triggered(1, clip_ids, trans_ids, playhead_position)
        elif key.matches(self.getShortcutByName("sliceAllKeepRightSide")) == QKeySequence.ExactMatch:
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if intersecting_clips or intersecting_trans:
                # Get list of clip ids
                clip_ids = [c.id for c in intersecting_clips]
                trans_ids = [t.id for t in intersecting_trans]
                self.timeline.Slice_Triggered(2, clip_ids, trans_ids, playhead_position)
        elif key.matches(self.getShortcutByName("sliceSelectedKeepBothSides")) == QKeySequence.ExactMatch:
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if intersecting_clips or intersecting_trans:
                # Get list of clip ids
                clip_ids = [c.id for c in intersecting_clips if c.id in self.selected_clips]
                trans_ids = [t.id for t in intersecting_trans if t.id in self.selected_transitions]
                self.timeline.Slice_Triggered(0, clip_ids, trans_ids, playhead_position)
        elif key.matches(self.getShortcutByName("sliceSelectedKeepLeftSide")) == QKeySequence.ExactMatch:
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if intersecting_clips or intersecting_trans:
                # Get list of clip ids
                clip_ids = [c.id for c in intersecting_clips if c.id in self.selected_clips]
                trans_ids = [t.id for t in intersecting_trans if t.id in self.selected_transitions]
                self.timeline.Slice_Triggered(1, clip_ids, trans_ids, playhead_position)
        elif key.matches(self.getShortcutByName("sliceSelectedKeepRightSide")) == QKeySequence.ExactMatch:
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if intersecting_clips or intersecting_trans:
                # Get list of ids that are also selected
                clip_ids = [c.id for c in intersecting_clips if c.id in self.selected_clips]
                trans_ids = [t.id for t in intersecting_trans if t.id in self.selected_transitions]
                self.timeline.Slice_Triggered(2, clip_ids, trans_ids, playhead_position)

        elif key.matches(self.getShortcutByName("copyAll")) == QKeySequence.ExactMatch:
            self.timeline.Copy_Triggered(-1, self.selected_clips, self.selected_transitions)
        elif key.matches(self.getShortcutByName("pasteAll")) == QKeySequence.ExactMatch:
            self.timeline.Paste_Triggered(9, float(playhead_position), -1, [], [])
        elif key.matches(self.getShortcutByName("nudgeLeft")) == QKeySequence.ExactMatch:
            self.timeline.Nudge_Triggered(-1, self.selected_clips, self.selected_transitions)
        elif key.matches(self.getShortcutByName("nudgeRight")) == QKeySequence.ExactMatch:
            self.timeline.Nudge_Triggered(1, self.selected_clips, self.selected_transitions)

        # Select All / None
        elif key.matches(self.getShortcutByName("selectAll")) == QKeySequence.ExactMatch:
            self.timeline.SelectAll()

        elif key.matches(self.getShortcutByName("selectNone")) == QKeySequence.ExactMatch:
            self.timeline.ClearAllSelections()

        # If we didn't act on the event, forward it to the base class
        else:
            super().keyPressEvent(event)

    def actionProfile_trigger(self):
        # Show dialog
        from windows.profile import Profile
        log.debug("Showing preferences dialog")
        win = Profile()
        # Run the dialog event loop - blocking interaction on this window during this time
        win.exec_()
        log.debug("Preferences dialog closed")

    def actionSplitClip_trigger(self):
        log.debug("actionSplitClip_trigger")

        # Loop through selected files (set 1 selected file if more than 1)
        f = self.files_model.current_file()

        # Bail out if no file selected
        if not f:
            log.warn("Split clip action failed, couldn't find current file")
            return

        # show dialog
        from windows.cutting import Cutting
        win = Cutting(f)
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Cutting Finished')
        else:
            log.info('Cutting Cancelled')

    def actionRemove_from_Project_trigger(self):
        log.debug("actionRemove_from_Project_trigger")

        # Loop through selected files
        for f in self.selected_files():
            if not f:
                continue

            # Find matching clips (if any)
            clips = Clip.filter(file_id=f.data.get("id"))
            for c in clips:
                # Remove clip
                c.delete()

            # Remove file (after clips are deleted)
            f.delete()

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionRemoveClip_trigger(self):
        log.debug('actionRemoveClip_trigger')

        locked_tracks = [l.get("number")
                         for l in get_app().project.get('layers')
                         if l.get("lock", False)]

        # Loop through selected clips
        for clip_id in deepcopy(self.selected_clips):
            # Find matching file
            clips = Clip.filter(id=clip_id)
            clips = list(filter(lambda x: x.data.get("layer") not in locked_tracks, clips))
            for c in clips:
                # Clear selected clips
                self.removeSelection(clip_id, "clip")

                # Remove clip
                c.delete()

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionProperties_trigger(self):
        log.debug('actionProperties_trigger')

        # Show properties dock
        if not self.dockProperties.isVisible():
            self.dockProperties.show()

    def actionRemoveEffect_trigger(self):
        log.debug('actionRemoveEffect_trigger')

        # Loop through selected clips
        for effect_id in deepcopy(self.selected_effects):
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
        for tran_id in deepcopy(self.selected_transitions):
            # Find matching file
            transitions = Transition.filter(id=tran_id)
            transitions = list(filter(lambda x: x.data.get("layer") not in locked_tracks, transitions))
            for t in transitions:
                # Clear selected clips
                self.removeSelection(tran_id, "transition")

                # Remove transition
                t.delete()

        # Refresh preview
        self.refreshFrameSignal.emit()

    def actionRemoveTrack_trigger(self):
        log.debug('actionRemoveTrack_trigger')

        # Get translation function
        _ = get_app()._tr

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

        # Revove all clips on this track first
        for clip in Clip.filter(layer=selected_track_number):
            clip.delete()

        # Revove all transitions on this track first
        for trans in Transition.filter(layer=selected_track_number):
            trans.delete()

        # Remove track
        selected_track.delete()

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

            # BRUTE FORCE approach: go through all clips and update file path
            clips = Clip.filter(file_id=f.data["id"])
            for c in clips:
                # update clip
                c.data["reader"]["path"] = f.data["path"]
                c.save()

            log.info('File Properties Finished')
        else:
            log.info('File Properties Cancelled')

    def actionExportClips_trigger(self):
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
            # Not saved yet
            self.setWindowTitle(
                "%s %s [%s] - %s" % (
                    save_indicator,
                    _("Untitled Project"),
                    profile,
                    "OpenShot Video Editor",
                    ))
        else:
            # Yes, project is saved
            # Get just the filename
            filename = os.path.basename(app.project.current_filepath)
            filename = os.path.splitext(filename)[0]
            self.setWindowTitle(
                "%s %s [%s] - %s" % (
                    save_indicator,
                    filename,
                    profile,
                    "OpenShot Video Editor",
                    ))

    # Update undo and redo buttons enabled/disabled to available changes
    def updateStatusChanged(self, undo_status, redo_status):
        log.info('updateStatusChanged')
        self.actionUndo.setEnabled(undo_status)
        self.actionRedo.setEnabled(redo_status)
        self.SetWindowTitle()

    def addSelection(self, item_id, item_type, clear_existing=False):
        """ Add to (or clear) the selected items list for a given type. """
        if not item_id:
            log.debug('addSelection: item_type: {}, clear_existing: {}'.format(
                item_type, clear_existing))
        else:
            log.info('addSelection: item_id: {}, item_type: {}, clear_existing: {}'.format(
                item_id, item_type, clear_existing))

        s = get_app().get_settings()

        # Clear existing selection (if needed)
        if clear_existing:
            if item_type == "clip":
                self.selected_clips.clear()
                self.TransformSignal.emit("")
            elif item_type == "transition":
                self.selected_transitions.clear()
            elif item_type == "effect":
                self.selected_effects.clear()

            # Clear caption editor (if nothing is selected)
            get_app().window.CaptionTextLoaded.emit("", None)

        if item_id:
            # If item_id is not blank, store it
            if item_type == "clip" and item_id not in self.selected_clips:
                self.selected_clips.append(item_id)
                if s.get("auto-transform"):
                    self.TransformSignal.emit(self.selected_clips[-1])
            elif item_type == "transition" and item_id not in self.selected_transitions:
                self.selected_transitions.append(item_id)
            elif item_type == "effect" and item_id not in self.selected_effects:
                self.selected_effects.append(item_id)

                effect = Effect.get(id=item_id)
                if effect:
                    if effect.data.get("has_tracked_object"):
                        # Show bounding boxes transform on preview
                        clip_id = effect.parent['id']
                        self.KeyFrameTransformSignal.emit(item_id, clip_id)


            # Change selected item in properties view
            self.show_property_id = item_id
            self.show_property_type = item_type
            self.show_property_timer.start()

        # Notify UI that selection has been potentially changed
        self.selection_timer.start()

    # Remove from the selected items
    def removeSelection(self, item_id, item_type):
        # Remove existing selection (if any)
        if item_id:
            if item_type == "clip" and item_id in self.selected_clips:
                self.selected_clips.remove(item_id)
            elif item_type == "transition" and item_id in self.selected_transitions:
                self.selected_transitions.remove(item_id)
            elif item_type == "effect" and item_id in self.selected_effects:
                self.selected_effects.remove(item_id)

        if not self.selected_clips:
            # Clear transform (if no other clips are selected)
            self.TransformSignal.emit("")

            # Clear caption editor (if nothing is selected)
            get_app().window.CaptionTextLoaded.emit("", None)

        # Move selection to next selected clip (if any)
        self.show_property_id = ""
        self.show_property_type = ""
        if item_type == "clip" and self.selected_clips:
            self.show_property_id = self.selected_clips[0]
            self.show_property_type = item_type
        elif item_type == "transition" and self.selected_transitions:
            self.show_property_id = self.selected_transitions[0]
            self.show_property_type = item_type
        elif item_type == "effect" and self.selected_effects:
            self.show_property_id = self.selected_effects[0]
            self.show_property_type = item_type

        # Change selected item
        self.show_property_timer.start()
        self.selection_timer.start()

    def emit_selection_signal(self):
        """Emit a signal for selection changed. Callback for selection timer."""
        # Notify UI that selection has been potentially changed
        self.SelectionChanged.emit()

    def selected_files(self):
        """ Return a list of File objects for the Project Files dock's selection """
        return self.files_model.selected_files()

    def selected_file_ids(self):
        """ Return a list of File IDs for the Project Files dock's selection """
        return self.files_model.selected_file_ids()

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
            self.menuFile.insertMenu(self.actionRecent_Placeholder, self.recent_menu)
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

    def remove_recent_project(self, file_path):
        """Remove a project from the Recent menu if OpenShot can't find it"""
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

        # Add fixed spacer(s) (one for each "Other control" to keep playback controls centered)
        ospacer1 = QWidget(self)
        ospacer1.setMinimumSize(32, 1)  # actionSaveFrame
        self.videoToolbar.addWidget(ospacer1)

        # Add left spacer
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.videoToolbar.addWidget(spacer)

        # Playback controls (centered)
        self.videoToolbar.addAction(self.actionJumpStart)
        self.videoToolbar.addAction(self.actionRewind)
        self.videoToolbar.addAction(self.actionPlay)
        self.videoToolbar.addAction(self.actionFastForward)
        self.videoToolbar.addAction(self.actionJumpEnd)

        # Add right spacer
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.videoToolbar.addWidget(spacer)

        # Other controls (right-aligned)
        self.videoToolbar.addAction(self.actionSaveFrame)

        self.tabVideo.layout().addWidget(self.videoToolbar)

        # Add Timeline toolbar
        self.timelineToolbar = QToolBar("Timeline Toolbar", self)

        self.timelineToolbar.addAction(self.actionAddTrack)
        self.timelineToolbar.addSeparator()

        # rest of options
        self.timelineToolbar.addAction(self.actionSnappingTool)
        self.timelineToolbar.addAction(self.actionRazorTool)
        self.timelineToolbar.addSeparator()
        self.timelineToolbar.addAction(self.actionAddMarker)
        self.timelineToolbar.addAction(self.actionPreviousMarker)
        self.timelineToolbar.addAction(self.actionNextMarker)
        self.timelineToolbar.addAction(self.actionCenterOnPlayhead)
        self.timelineToolbar.addSeparator()

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
        self.caption_save_timer.setInterval(100)
        self.caption_save_timer.setSingleShot(True)
        self.caption_save_timer.timeout.connect(self.caption_editor_save)
        self.CaptionTextLoaded.connect(self.caption_editor_load)
        self.caption_model_row = None

        # Get project's initial zoom value
        initial_scale = get_app().project.get("scale") or 15.0

        # Setup Zoom Slider widget
        from windows.views.zoom_slider import ZoomSlider
        self.sliderZoomWidget = ZoomSlider(self)
        self.sliderZoomWidget.setMinimumSize(200, 20)
        self.sliderZoomWidget.setZoomFactor(initial_scale)

        # add zoom widgets
        self.timelineToolbar.addWidget(self.sliderZoomWidget)

        # Add timeline toolbar to web frame
        self.frameWeb.addWidget(self.timelineToolbar)

    def clearSelections(self):
        """Clear all selection containers"""
        self.selected_clips = []
        self.selected_transitions = []
        self.selected_markers = []
        self.selected_tracks = []
        self.selected_effects = []

        # Clear selection in properties view
        if self.propertyTableView:
            self.propertyTableView.loadProperties.emit("", "")

    def foundCurrentVersion(self, version):
        """Handle the callback for detecting the current version on openshot.org"""
        _ = get_app()._tr

        # Compare versions (alphabetical compare of version strings should work fine)
        if info.VERSION < version:
            # Add spacer and 'New Version Available' toolbar button (default hidden)
            spacer = QWidget(self)
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.toolBar.addWidget(spacer)

            # Update text for QAction
            self.actionUpdate.setVisible(True)
            self.actionUpdate.setText(_("Update Available"))
            self.actionUpdate.setToolTip(_("Update Available: <b>%s</b>") % version)

            # Add update available button (with icon and text)
            updateButton = QToolButton()
            updateButton.setDefaultAction(self.actionUpdate)
            updateButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.toolBar.addWidget(updateButton)

        # Initialize sentry exception tracing (now that we know the current version)
        from classes import sentry
        sentry.init_tracing()

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

    def hideEvent(self, event):
        """ Have any child windows hide with main window """
        QMainWindow.hideEvent(self, event)
        for child in self.getDocks():
            if child.isFloating() and child.isVisible():
                child.hide()

    def show_property_timeout(self):
        """Callback for show property timer"""

        # Emit load properties signal
        self.propertyTableView.loadProperties.emit(
            self.show_property_id,
            self.show_property_type)

    def InitKeyboardShortcuts(self):
        """Initialize all keyboard shortcuts from the settings file"""

        # Translate object
        _ = get_app()._tr

        # Update all action-based shortcuts (from settings file)
        for shortcut in self.getAllKeyboardShortcuts():
            for action in self.findChildren(QAction):
                if shortcut.get('setting') == action.objectName():
                    action.setShortcut(QKeySequence(_(shortcut.get('value'))))

    def InitCacheSettings(self):
        """Set the correct cache settings for the timeline"""
        # Load user settings
        s = get_app().get_settings()
        log.info("InitCacheSettings")
        log.info("cache-mode: %s" % s.get("cache-mode"))
        log.info("cache-limit-mb: %s" % s.get("cache-limit-mb"))

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

    def __init__(self, *args):

        # Create main window base class
        super().__init__(*args)
        self.initialized = False

        # set window on app for reference during initialization of children
        app = get_app()
        app.window = self
        _ = app._tr

        # Load user settings for window
        s = app.get_settings()
        self.recent_menu = None

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
        ui_util.load_ui(self, self.ui_path)

        # Set all keyboard shortcuts from the settings file
        self.InitKeyboardShortcuts()

        # Init UI
        ui_util.init_ui(self)

        # Create dock toolbars, set initial state of items, etc
        self.setup_toolbars()

        # Add window as watcher to receive undo/redo status updates
        app.updates.add_watcher(self)

        # Get current version of OpenShot via HTTP
        self.FoundVersionSignal.connect(self.foundCurrentVersion)
        get_current_Version()

        # Connect signals
        self.RecoverBackup.connect(self.recover_backup)

        # Initialize and start the thumbnail HTTP server
        self.http_server_thread = httpThumbnailServerThread()
        self.http_server_thread.start()

        # Create the timeline sync object (used for previewing timeline)
        self.timeline_sync = TimelineSync(self)

        # Setup timeline
        self.timeline = TimelineWebView(self)
        self.frameWeb.layout().addWidget(self.timeline)

        # Configure the side docks to full-height
        self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        self.initModels()

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
        self.dockPropertiesContent.layout().addWidget(self.selectionLabel, 0, 1)
        self.dockPropertiesContent.layout().addWidget(self.propertyTableView, 2, 1)

        # Init selection containers
        self.clearSelections()

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

        # Setup video preview QWidget
        self.videoPreview = VideoWidget()
        self.tabVideo.layout().insertWidget(0, self.videoPreview)

        # Load window state and geometry
        self.saved_state = None
        self.saved_geometry = None
        self.load_settings()

        # Setup Cache settings
        self.cache_object = None
        self.InitCacheSettings()

        # Start the preview thread
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.timeline_sync.timeline, self.videoPreview)
        self.preview_thread = self.preview_parent.worker
        self.sliderZoomWidget.connect_playback()

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

        # Set audio playback settings
        if s.get("playback-audio-device"):
            lib_settings.PLAYBACK_AUDIO_DEVICE_NAME = str(s.get("playback-audio-device"))
        else:
            lib_settings.PLAYBACK_AUDIO_DEVICE_NAME = ""

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

        # Ensure toolbar is movable when floated (even with docks frozen)
        self.toolBar.topLevelChanged.connect(
            functools.partial(self.freezeMainToolBar, None))

        # Show window
        self.show()

        # Create tutorial manager
        self.tutorial_manager = TutorialManager(self)

        # Apply saved window geometry/state from settings
        if self.saved_geometry:
            self.restoreGeometry(self.saved_geometry)
        if self.saved_state:
            self.restoreState(self.saved_state)

        # Save settings
        s.save()

        # Refresh frame
        QTimer.singleShot(100, self.refreshFrameSignal.emit)

        # Main window is initialized
        self.initialized = True
