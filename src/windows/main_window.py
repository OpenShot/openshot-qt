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
from qt_api import (
    Qt, pyqtSignal, pyqtSlot, QCoreApplication, QTimer, QDateTime,
    QFileInfo, QEvent, QUrl, QLocale
)
from qt_api import QIcon, QCursor, QKeySequence, QTextCursor
from qt_api import show_open_file_dialog, show_save_file_dialog, file_exists, ensure_extension, path_basename
from qt_api import (
    QMainWindow, QWidget, QDockWidget,
    QApplication, QMenu, QMessageBox, QDialog, QFileDialog, QInputDialog,
    QAction, QActionGroup, QSizePolicy,
    QStatusBar, QToolBar, QToolButton,
    QLineEdit, QComboBox, QTextEdit, QShortcut, QTabBar, QTabWidget, QAbstractButton,
    QPlainTextEdit, QSpinBox, QDoubleSpinBox
)

from classes import exceptions, info, qt_types, sentry, ui_util, updates, tabstops
from classes.app import get_app
from classes.exporters.edl import export_edl
from classes.exporters.final_cut_pro import export_xml
from classes.importers.edl import import_edl
from classes.importers.final_cut_pro import import_xml
from classes.logger import log
from classes.metrics import track_metric_session, track_metric_screen
from classes.path_utils import comparable_local_path, native_display_path, normalized_local_path
from classes.query import File, Clip, Transition, Marker, Track, Effect
from classes.clipboard import ClipboardManager
from classes.generation_queue import GenerationQueueManager
from classes.generation_service import GenerationService
from classes.proxy_service import ProxyService
from classes.thumbnail import httpThumbnailServerThread, httpThumbnailException
from classes.time_parts import secondsToTimecode
from classes.timeline import TimelineSync
from classes.title_bar import HiddenTitleBar
from classes.version import get_current_Version
from themes.manager import ThemeName
from windows.models.effects_model import EffectsModel
from windows.models.emoji_model import EmojisModel
from windows.models.files_model import FilesModel
from windows.views.optimized_preview_menu import populate_optimized_preview_menu
from windows.models.transition_model import TransitionsModel
from windows.audio_recording import AudioRecordingDockContent, RECORDING_DOCK_MIN_WIDTH
from windows.preview_thread import PreviewParent
from windows.scope_panel import WaveformDockContent, HistogramDockContent, VectorscopeDockContent, AudioMeterWidget
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
    LoadFilePreviewSignal = pyqtSignal(str, bool)
    PlaySignal = pyqtSignal()
    PauseSignal = pyqtSignal()
    StopSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int, bool)
    LoadTimelineAndSeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    SeekPreviousFrame = pyqtSignal()
    SeekNextFrame = pyqtSignal()
    PlayPauseToggleSignal = pyqtSignal()
    RecoverBackup = pyqtSignal()
    FoundVersionSignal = pyqtSignal(str)
    TransformSignal = pyqtSignal(list)
    KeyFrameTransformSignal = pyqtSignal(str, str)
    SelectRegionSignal = pyqtSignal(str)
    MaxSizeChanged = pyqtSignal(object)
    RunScopeSignal = pyqtSignal(int, bool, bool, bool, bool, object, object, object)   # Route scope GetFrame to worker thread to avoid mutex contention
    InsertKeyframe = pyqtSignal()
    OpenProjectSignal = pyqtSignal(str)
    ThumbnailUpdated = pyqtSignal(str, int)
    FileUpdated = pyqtSignal(str)
    CaptionTextUpdated = pyqtSignal(str, object)
    CaptionTextCommitted = pyqtSignal(object)
    CaptionTextLoaded = pyqtSignal(str, object)
    TimelineZoom = pyqtSignal(float)     # Signal to zoom into timeline from zoom slider
    TimelineScrolled = pyqtSignal(list)  # Scrollbar changed signal from timeline
    TimelineResize = pyqtSignal()  # Timeline length changed signal from timeline
    TimelineScroll = pyqtSignal(float)   # Signal to force scroll timeline to specific point
    TimelineCenter = pyqtSignal()        # Signal to force center scroll on playhead
    TrimPreviewMode = pyqtSignal()
    TimelinePreviewMode = pyqtSignal()
    SelectionAdded = pyqtSignal(str, str, bool)  # Signal to add a selection
    SelectionRemoved = pyqtSignal(str, str)      # Signal to remove a selection
    SelectionChanged = pyqtSignal()      # Signal after selections have been changed (added/removed)
    SetKeyframeFilter = pyqtSignal(str)     # Signal to only show keyframes for the selected property
    IgnoreUpdates = pyqtSignal(bool, bool)     # Signal to let widgets know to ignore updates (i.e. batch updates)
    WaitCursorSignal = pyqtSignal(bool)
    ThemeChangedSignal = pyqtSignal(object)     # Signal when theme is changed
    ProjectSaved = pyqtSignal(str)
    ProjectSaveFailed = pyqtSignal(str, str)

    # Save window settings on close
    def closeEvent(self, event):
        app = get_app()
        save_geometry = getattr(self, "saveGeometry", None)
        if callable(save_geometry):
            # A parented modal can temporarily alter the main window's state
            # before shutdown reaches save_settings(). Preserve the state from
            # the instant the user requested the close.
            self._pending_close_geometry = save_geometry()

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
                self._pending_close_geometry = None
                event.ignore()
                return

        # If already shutting down, ignore
        # Some versions of Qt fire this CloseEvent() method twice
        if self.shutting_down:
            log.debug("Already shutting down, skipping the closeEvent() method")
            return

        # Call the class implementation directly so closeEvent() remains usable
        # with lightweight duck-typed test doubles that don't bind methods.
        MainWindow._shutdown(self)

    def _shutdown(self):
        """Perform shutdown without prompting (used by closeEvent and app cleanup)."""
        app = get_app()
        if self.shutting_down:
            log.debug("Already shutting down, skipping the shutdown routine")
            return
        self.shutting_down = True

        # Log the exit routine
        log.info('---------------- Shutting down -----------------')

        # Flush and close UI trace recorder, if enabled
        if getattr(self, "ui_trace_recorder", None):
            self.ui_trace_recorder.close()

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
        from qt_api import isdeleted
        if timeline_widget and getattr(timeline_widget, "thumbnail_manager", None):
            log.info(
                "Shutdown timeline thumbnail thread running=%s",
                timeline_widget.thumbnail_manager._thread.isRunning(),
            )
            if not isdeleted(timeline_widget.thumbnail_manager):
                timeline_widget.thumbnail_manager.shutdown()

        # Stop thumbnail server thread (if any)
        if self.http_server_thread:
            self.http_server_thread.kill()

        # Stop generation queue worker thread (if any)
        if getattr(self, "generation_queue", None):
            self.generation_queue.shutdown()

        # Cleanup temporary generation source files
        if getattr(self, "generation_service", None):
            self.generation_service.shutdown()
            self.generation_service.cleanup_temp_files()
        if getattr(self, "proxy_service", None):
            self.proxy_service.shutdown()

        # Stop ZMQ polling thread (if any)
        if app.logger_libopenshot:
            app.logger_libopenshot.kill()

        # Process any queued events
        QCoreApplication.processEvents()

        # Stop preview thread (and wait for it to end)
        if self.preview_thread:
            if self.preview_parent and getattr(self.preview_parent, "background", None):
                log.info(
                    "Shutdown preview thread running=%s",
                    self.preview_parent.background.isRunning(),
                )
            self.preview_thread.player.CloseAudioDevice()
            self.preview_thread.kill()
            from qt_api import isdeleted
            if self.videoPreview and not isdeleted(self.videoPreview):
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
        self.SeekSignal.emit(1, True)

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
                file.data["ui"].pop("audio_data_format", None)
                file.data["ui"].pop("audio_data_rms", None)
                file.data["ui"].pop("audio_data_rate", None)
                file.save()

        clips = Clip.filter()
        for clip in clips:
            if "audio_data" in clip.data.get("ui", {}):
                log.debug("Clip %s has audio data. Deleting it." % clip.id)
                del clip.data["ui"]["audio_data"]
                clip.data["ui"].pop("audio_data_format", None)
                clip.data["ui"].pop("audio_data_rms", None)
                clip.data["ui"].pop("audio_data_rate", None)
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

    def actionClearOptimizedFiles_trigger(self):
        """Delete and unlink internal optimized files for the current project"""
        _ = get_app()._tr
        ret = QMessageBox.question(
            self,
            _("Delete Optimized Videos?"),
            _("Delete optimized videos from this project's assets folder?"),
            QMessageBox.No | QMessageBox.Yes,
        )
        if ret != QMessageBox.Yes:
            return
        self.proxy_service.delete_internal_project_proxy_files()

    def _refresh_clear_menu_action_states(self):
        has_internal_optimized = bool(getattr(self, "proxy_service", None) and self.proxy_service.has_internal_project_proxy_files())
        self.actionClearOptimizedFiles.setEnabled(has_internal_optimized)

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

                log.info("Saved project %s", file_path)
                self.ProjectSaved.emit(file_path)

            except Exception as ex:
                log.error("Couldn't save project %s", file_path, exc_info=1)
                self.ProjectSaveFailed.emit(file_path, str(ex))

    @pyqtSlot(str)
    def _on_project_saved(self, file_path):
        """Update UI after a project save completes."""
        self.SetWindowTitle()
        self.load_recent_menu()

    @pyqtSlot(str, str)
    def _on_project_save_failed(self, file_path, error_message):
        """Show save errors on the UI thread."""
        _ = get_app()._tr
        QMessageBox.warning(self, _("Error Saving Project"), error_message)

    def save_recovery(self, file_path):
        """Saves the project and manages recovery files based on configured limits."""
        app = get_app()
        s = app.get_settings()
        max_files = s.get("recovery-limit")
        daily_limit = int(max_files * 0.7)
        historical_limit = max_files - daily_limit  # Remaining for previous days

        if not os.path.exists(file_path):
            return

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
             for f in os.listdir(info.RECOVERY_PATH) if f.endswith(".zip") or f.endswith(".osp")),
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

        previous_project_loading = getattr(self, "_project_loading", False)
        self._project_loading = True
        self._pending_project_open_refresh = False
        lib_settings = openshot.Settings.Instance()
        previous_playback_caching = lib_settings.ENABLE_PLAYBACK_CACHING
        lib_settings.ENABLE_PLAYBACK_CACHING = False
        loaded_project = False
        try:
            if file_exists(file_path):
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

                # Update max size (for fast previews)
                self.MaxSizeChanged.emit(self.videoPreview.size())

                # Load recent projects again
                self.load_recent_menu()

                log.info("Loaded project {}".format(file_path))
                loaded_project = True
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
            if loaded_project:
                self._pending_project_open_refresh = True

        except Exception as ex:
            log.error("Couldn't open project %s.", file_path, exc_info=1)
            QMessageBox.warning(self, _("Error Opening Project"), str(ex))
        finally:
            self._project_loading = previous_project_loading
            if not loaded_project:
                lib_settings.ENABLE_PLAYBACK_CACHING = previous_playback_caching
            if self._pending_project_open_refresh:
                self._pending_project_open_refresh = False
                QTimer.singleShot(0, lambda: self.refreshFrameSignal.emit())

        # Restore normal cursor
        app.restoreOverrideCursor()

    def clear_temporary_files(self):
        """Clear all user thumbnails"""
        for temp_dir in [
                info.get_default_path("THUMBNAIL_PATH"),
                info.get_default_path("BLENDER_PATH"),
                info.get_default_path("TITLE_PATH"),
                info.get_default_path("CLIPBOARD_PATH"),
                info.get_default_path("COMFYUI_OUTPUT_PATH"),
                info.get_default_path("PROXY_PATH"),
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

        def _show_open_dialog():
            def _on_file_selected(qurl_list):
                if not qurl_list:
                    return
                file_path = qurl_list[0].toLocalFile() or qurl_list[0].toString()
                if file_path:
                    s.setDefaultPath(s.actionType.LOAD, file_path)
                    self.OpenProjectSignal.emit(file_path)

            show_open_file_dialog(
                self,
                _("Open Project..."),
                recommended_folder,
                _("OpenShot Project (*.osp)"),
                _on_file_selected,
                allow_multiple=False,
            )

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("Save changes to project first?"),
                QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project first, then open
                self.actionSave_trigger()
                _show_open_dialog()
            elif ret == QMessageBox.Cancel:
                return
            else:
                _show_open_dialog()
        else:
            _show_open_dialog()

    def actionSave_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        # If the project already has a path, save immediately without a dialog.
        file_path = app.project.current_filepath
        if file_path:
            s.setDefaultPath(s.actionType.SAVE, file_path)
            file_path = ensure_extension(file_path, ".osp")
            self.save_project(file_path)
            return

        # No existing path — ask the user where to save.
        recommended_folder = s.getDefaultPath(s.actionType.SAVE)
        suggested_name = _("Untitled Project") + ".osp"

        def _on_path(path):
            if not path:
                return
            s.setDefaultPath(s.actionType.SAVE, path)
            self.save_project(ensure_extension(path, ".osp"))

        show_save_file_dialog(
            self,
            _("Save Project..."),
            suggested_name,
            "*/*",
            _on_path,
            directory=recommended_folder,
        )

    def auto_save_project(self):
        """Auto save the project"""
        app = get_app()
        current_data_version = app.updates.data_version

        # Get current filepath (if any)
        file_path = app.project.current_filepath
        if not app.project.needs_save():
            return

        # Skip if no project mutations happened since the last autosave.
        # This avoids rewriting the same backup.osp on every timer tick for
        # untitled/recovered projects that remain "unsaved" by design.
        if current_data_version == self.last_auto_save_data_version:
            return

        if file_path:
            # A Real project file exists
            file_path = ensure_extension(file_path, ".osp")

            # Save project
            log.info("Auto save project file: %s", file_path)
            threading.Thread(target=self.save_project, args=(file_path,), daemon=True).start()

            # Remove backup.osp (if any)
            if os.path.exists(info.BACKUP_FILE):
                try:
                    # Delete backup.osp since we just saved the actual project
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

        self.last_auto_save_data_version = current_data_version

    def actionSaveAs_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        project_file_path = app.project.current_filepath
        suggested_name = path_basename(project_file_path) or ("%s.osp" % _("Untitled Project"))

        def _on_path(path):
            if not path:
                return
            s.setDefaultPath(s.actionType.SAVE, path)
            threading.Thread(target=self.save_project, args=(ensure_extension(path, ".osp"),), daemon=True).start()

        recommended_folder = s.getDefaultPath(s.actionType.SAVE)
        show_save_file_dialog(
            self,
            _("Save Project As..."),
            suggested_name,
            "*/*",
            _on_path,
            directory=recommended_folder,
        )

    def actionImportFiles_trigger(self):
        app = get_app()
        s = app.get_settings()
        _ = app._tr

        recommended_path = s.getDefaultPath(s.actionType.IMPORT)

        def _on_files_selected(qurl_list):
            if not qurl_list:
                return
            app.setOverrideCursor(QCursor(Qt.WaitCursor))
            try:
                self._raise_project_files_dock_if_open()
                self.files_model.process_urls(qurl_list)
                self.refreshFilesSignal.emit()
            finally:
                app.restoreOverrideCursor()

        show_open_file_dialog(self, _("Import Files..."), recommended_path, "", _on_files_selected)

    def _raise_project_files_dock_if_open(self):
        """Select Project Files only when it is already open in the current layout."""
        dock = getattr(self, "dockFiles", None)
        if not dock:
            return
        if self.dockWidgetArea(dock) == Qt.NoDockWidgetArea:
            return
        if not dock.toggleViewAction().isChecked():
            return
        dock.raise_()
        dock.activateWindow()

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

        get_app().window.WaitCursorSignal.emit(True)
        try:
            # Show dialog
            from windows.preferences import Preferences
            win = Preferences()
        finally:
            get_app().window.WaitCursorSignal.emit(False)
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Preferences add confirmed')
        else:
            log.info('Preferences add cancelled')

        # Save settings
        s = get_app().get_settings()
        s.save()

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
        url = "https://www.openshot.org/%suser-guide/?app-menu" % info.website_language()
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the official User Guide url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionReportBug_trigger(self, checked=True):
        url = "https://www.openshot.org/%sissues/new/?app-menu" % info.website_language()
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Bug Report url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionAskQuestion_trigger(self, checked=True):
        url = "https://www.reddit.com/r/OpenShot/"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the official OpenShot subreddit url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionDiscord_trigger(self, checked=True):
        url = "https://www.openshot.org/discord/?app-menu"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Discord community invite url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionTranslate_trigger(self, checked=True):
        url = "https://translations.launchpad.net/openshot/2.0"
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Translation url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionDonate_trigger(self, checked=True):
        url = "https://www.openshot.org/%sdonate/?app-menu" % info.website_language()
        try:
            webbrowser.open(url, new=1)
        except Exception:
            error_msg = f"Unable to open the Donate url: {url}"
            QMessageBox.information(self, "Error", error_msg)
            log.error(error_msg, exc_info=1)

    def actionUpdate_trigger(self, checked=True):
        url = "https://www.openshot.org/%sdownload/?app-toolbar" % info.website_language()
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
        # Get max frame (based on last clip) and current frame.
        timeline_sync = get_app().window.timeline_sync
        if timeline_sync and timeline_sync.timeline:
            last_frame = timeline_sync.GetLastFrame()
            current_frame = self.preview_thread.current_frame
            if current_frame is not None:
                next_frame = current_frame + requested_speed
                return next_frame <= last_frame and next_frame > 0
        return False

    def actionPlay_trigger(self):
        """Toggle play/pause on video preview"""
        player = self.preview_thread.player
        is_actively_playing = (
            player.Mode() == openshot.PLAYBACK_PLAY and
            player.Speed() != 0
        )
        if not is_actively_playing:
            # Start playback
            if self.should_play():
                self.PlaySignal.emit()
        else:
            # Pause playback
            self.PauseSignal.emit()

    def actionPreview_File_trigger(self, checked=True):
        """ Preview the selected media file """
        log.info('actionPreview_File_trigger')

        # Prefer current file, but fall back to selected real files when a generation
        # placeholder row has focus.
        f = self.files_model.current_file()
        if not f:
            selected_files = self.files_model.selected_files()
            if selected_files:
                f = selected_files[0]

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

        if player.Mode() != openshot.PLAYBACK_PLAY:
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
            if player.Mode() != openshot.PLAYBACK_PLAY:
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
        self.SeekSignal.emit(min_frame, True)
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
        self.SeekSignal.emit(get_app().window.timeline_sync.GetLastFrame(), True)
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

    def onTrimPreviewMode(self):
        """Pause active playback before entering timeline trim preview."""
        player = getattr(getattr(self, "preview_thread", None), "player", None)
        if not player:
            return
        is_actively_playing = (
            player.Mode() == openshot.PLAYBACK_PLAY and
            player.Speed() != 0
        )
        if is_actively_playing:
            self.PauseSignal.emit()

    @pyqtSlot(int, bool)
    def _enter_playback_mode(self, _frame=0, _preroll=False):
        """Re-enable video caching when the user seeks or starts playback."""
        if getattr(self, "_project_loading", False):
            return
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

    @pyqtSlot()
    def _enter_playback_mode_play(self):
        if getattr(self, "_project_loading", False):
            return
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

    @pyqtSlot(int)
    def _on_scope_frame(self, frame_number):
        """Record the latest frame number and arm the debounce timer."""
        if not any(
            getattr(self, d, None) and getattr(self, d).isVisible()
            for d in ("dockLumaWaveform", "dockHistogram", "dockVectorscope", "dockAudio")
        ):
            return
        self._scope_pending_frame = frame_number
        if not self._scope_timer.isActive():
            self._scope_timer.start()

    @pyqtSlot(int, bool)
    def _on_scope_seek(self, frame_number, _start_preroll):
        """Catch manual seeks (scrubbing, step buttons) that may not emit position_changed."""
        self._on_scope_frame(frame_number)

    def _scope_region_payload(self):
        if not getattr(self, "_scope_region_enabled", False):
            return None
        preview = getattr(self, "videoPreview", None)
        if not preview:
            return None
        return preview.scopeRegionNormalizedRect()

    @pyqtSlot(bool)
    def _on_scope_region_toggled(self, enabled):
        enabled = bool(enabled)
        self._scope_region_enabled = enabled
        preview = getattr(self, "videoPreview", None)
        if preview:
            preview.setScopeRegionEnabled(enabled)
        for content in (
            getattr(self, "waveform_content", None),
            getattr(self, "histogram_content", None),
            getattr(self, "vectorscope_content", None),
        ):
            if content:
                content.set_scope_region_enabled(enabled)
        self._request_scope_refresh()

    @pyqtSlot()
    def _on_scope_region_changed(self):
        if getattr(self, "_scope_region_enabled", False):
            self._request_scope_refresh()

    @pyqtSlot()
    def _clear_scope_region_mode(self):
        if getattr(self, "_scope_region_enabled", False):
            self._on_scope_region_toggled(False)

    def _any_video_scope_dock_open(self):
        for dock_name in ("dockLumaWaveform", "dockHistogram", "dockVectorscope"):
            dock = getattr(self, dock_name, None)
            if dock and dock.toggleViewAction().isChecked():
                return True
        return False

    def _on_video_scope_visibility_changed(self, _visible):
        if not self._any_video_scope_dock_open():
            self._clear_scope_region_mode()

    @pyqtSlot(str, str, bool)
    def _clear_scope_region_on_selection(self, _item_id, _item_type, _clear_existing=False):
        self._clear_scope_region_mode()

    def _run_scope_analysis(self):
        """Dispatch FrameScope analysis to the worker thread (timer-debounced).

        GetFrame is routed via RunScopeSignal so scope work stays off the UI thread.
        """
        frame_number = self._scope_pending_frame
        if frame_number is None:
            return
        wf_vis   = getattr(self, "dockLumaWaveform", None) and self.dockLumaWaveform.isVisible()
        hist_vis = getattr(self, "dockHistogram",    None) and self.dockHistogram.isVisible()
        vec_vis  = getattr(self, "dockVectorscope",  None) and self.dockVectorscope.isVisible()
        aud_vis  = getattr(self, "dockAudio",        None) and self.dockAudio.isVisible()
        need_video = bool(wf_vis or hist_vis or vec_vis)
        need_audio = bool(aud_vis)
        if not (need_video or need_audio):
            return
        self._scope_wf_vis   = wf_vis
        self._scope_hist_vis = hist_vis
        self._scope_vec_vis  = vec_vis
        self._scope_aud_vis  = aud_vis
        waveform_render = None
        if wf_vis and getattr(self, "waveform_content", None):
            waveform_render = self.waveform_content.render_settings()
        vectorscope_render = None
        if vec_vis and getattr(self, "vectorscope_content", None):
            vectorscope_render = self.vectorscope_content.render_settings()
        self.RunScopeSignal.emit(
            frame_number, wf_vis, hist_vis, vec_vis, aud_vis,
            self._scope_region_payload(), waveform_render, vectorscope_render)

    @pyqtSlot(int, dict, dict)
    def _on_scope_ready(self, frame_number, video, audio):
        """Receive FrameScope results from the worker thread and update scope widgets."""
        current_frame = getattr(self, "_scope_pending_frame", None)
        if current_frame is not None and frame_number < current_frame:
            return
        if video and getattr(self, "_scope_wf_vis", False):
            self.waveform_content.update_data(video)
        if video and getattr(self, "_scope_hist_vis", False):
            self.histogram_content.update_data(video)
        if video and getattr(self, "_scope_vec_vis", False):
            self.vectorscope_content.update_data(video)
        if audio and getattr(self, "_scope_aud_vis", False):
            self.audio_meter.update_data(audio)

    def _request_scope_refresh(self):
        """Analyze the current preview frame immediately after scope docks are shown."""
        preview_thread = getattr(self, "preview_thread", None)
        if not preview_thread or not getattr(preview_thread, "player", None):
            return
        try:
            frame_number = int(preview_thread.player.Position())
        except Exception:
            return
        if frame_number <= 0:
            frame_number = 1
        self._on_scope_frame(frame_number)

    def _anchor_and_show_scope_dock(self, dock):
        """Ensure a scope dock lands in the bottom-right group (below Color Wheels)."""
        color_grade_dock = getattr(
            getattr(self, "propertyTableView", None), "color_grade_wheels_dock", None)
        scope_docks = [self.dockLumaWaveform, self.dockHistogram, self.dockVectorscope, self.dockAudio]

        if self.dockWidgetArea(dock) == Qt.NoDockWidgetArea:
            self.addDocks([dock], Qt.RightDockWidgetArea)
            anchored = [d for d in scope_docks if d is not dock
                        and self.dockWidgetArea(d) != Qt.NoDockWidgetArea
                        and d.isVisible()]
            if anchored:
                # Join the existing bottom scope group
                self.tabifyDockWidget(anchored[-1], dock)
            elif (color_grade_dock and
                  self.dockWidgetArea(color_grade_dock) != Qt.NoDockWidgetArea):
                # First scope dock: split Color Wheels so scope lands below it
                self.splitDockWidget(color_grade_dock, dock, Qt.Vertical)
            self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)
        dock.show()
        dock.raise_()
        self._request_scope_refresh()

    def _on_scope_dock_toggled(self, checked, dock):
        """Called when a scope dock's toggle action fires; re-anchor if needed."""
        if checked:
            self._anchor_and_show_scope_dock(dock)

    def show_scope_video_docks(self):
        """Show video scope docks, anchoring to right if needed."""
        self._anchor_and_show_scope_dock(self.dockLumaWaveform)
        self._anchor_and_show_scope_dock(self.dockHistogram)
        self._anchor_and_show_scope_dock(self.dockVectorscope)
        self.dockLumaWaveform.raise_()

    def show_color_grading_docks(self):
        """Show Color Wheels above the video scope docks on the right side."""
        property_view = getattr(self, "propertyTableView", None)
        color_grade_dock = getattr(property_view, "color_grade_wheels_dock", None)
        if color_grade_dock and property_view:
            if hasattr(property_view, "_ensure_color_grade_wheels_dock_attached"):
                property_view._ensure_color_grade_wheels_dock_attached()
            color_grade_dock.show()
            color_grade_dock.raise_()
        self.show_scope_video_docks()

    def show_scope_audio_dock(self):
        """Show Audio Levels dock, anchoring to right if needed."""
        self._anchor_and_show_scope_dock(self.dockAudio)

    def show_audio_recording_dock(self, start_time=None, track_number=None):
        """Show the Recording dock, pre-filling context when provided."""
        self.WaitCursorSignal.emit(True)
        QApplication.processEvents()
        try:
            self._ensure_audio_recording_dock_content()
            if self.dockWidgetArea(self.dockAudioRecording) == Qt.NoDockWidgetArea:
                self.addDockWidget(Qt.RightDockWidgetArea, self.dockAudioRecording)
            self.dockAudioRecording.show()
            if hasattr(self, "audio_recording_content"):
                self.audio_recording_content.set_recording_context(start_time, track_number)
            self.dockAudioRecording.raise_()
        finally:
            self.WaitCursorSignal.emit(False)

    def _ensure_audio_recording_dock_content(self):
        """Create recording controls only when the user opens recording UI."""
        if getattr(self, "audio_recording_content", None):
            return
        self.audio_recording_content = AudioRecordingDockContent(self)
        self.dockAudioRecording.setMinimumWidth(RECORDING_DOCK_MIN_WIDTH)
        self.dockAudioRecording.setWidget(self.audio_recording_content)

    def _on_audio_recording_visibility_changed(self, visible):
        """Ensure restored Recording View docks are populated when shown."""
        if visible:
            self._ensure_audio_recording_dock_content()
            self.audio_recording_content.activate_if_visible()
        elif getattr(self, "audio_recording_content", None):
            self.audio_recording_content.deactivate_if_hidden()

    def _anchor_and_show_properties_dock(self):
        """Reattach Properties when needed without replacing a view's layout."""
        files_dock = getattr(self, "dockFiles", None)
        props_dock = getattr(self, "dockProperties", None)
        if not props_dock:
            return

        needs_anchor = (
            props_dock.isFloating()
            or self.dockWidgetArea(props_dock) == Qt.NoDockWidgetArea
        )
        if props_dock.isFloating():
            props_dock.setFloating(False)
        if self.dockWidgetArea(props_dock) == Qt.NoDockWidgetArea:
            target_area = (
                self.dockWidgetArea(files_dock)
                if files_dock and self.dockWidgetArea(files_dock) != Qt.NoDockWidgetArea
                else Qt.LeftDockWidgetArea
            )
            self.addDockWidget(target_area, props_dock)

        if (needs_anchor
                and files_dock
                and self.dockWidgetArea(files_dock) != Qt.NoDockWidgetArea):
            if props_dock not in self.tabifiedDockWidgets(files_dock):
                self.tabifyDockWidget(files_dock, props_dock)
            self.setTabPosition(self.dockWidgetArea(files_dock), QTabWidget.North)

        props_dock.show()
        props_dock.raise_()
        self.style_dock_widgets()

    def _on_properties_dock_toggled(self, checked):
        """Re-anchor Properties when it is toggled back on after a view switch."""
        if checked:
            self._anchor_and_show_properties_dock()

    def _scope_docks(self):
        """Return docks that display video/audio scope data."""
        return [
            self.dockAudio,
            self.dockHistogram,
            self.dockLumaWaveform,
            self.dockVectorscope,
        ]

    def _scope_dock_names(self):
        """Return object names for all scope docks."""
        return {dock.objectName() for dock in self._scope_docks()}

    def _view_menu_docks(self):
        """Return non-scope docks managed by the View > Docks menu."""
        scope_dock_names = self._scope_dock_names()
        docks = [
            dock for dock in self.getDocks()
            if (dock.objectName() not in scope_dock_names
                and dock.objectName() not in {"dockTimeline", "dockTutorial"})
        ]
        color_grade_dock = getattr(
            getattr(self, "propertyTableView", None), "color_grade_wheels_dock", None)
        if color_grade_dock and color_grade_dock not in docks:
            docks.append(color_grade_dock)
        return docks

    def _dock_is_open(self, dock):
        """Return True when a dock is attached and visible."""
        return (self.dockWidgetArea(dock) != Qt.NoDockWidgetArea
                and dock.toggleViewAction().isChecked())

    def _add_dock_visibility_actions(
            self, menu, docks, show_text, close_text,
            show_callback=None):
        """Add bulk show/close actions when they are valid for the current dock state."""
        if not docks:
            return

        open_docks = [dock for dock in docks if self._dock_is_open(dock)]
        closed_docks = [dock for dock in docks if dock not in open_docks]
        if not open_docks and not closed_docks:
            return

        menu.addSeparator()
        if closed_docks:
            show_action = QAction(show_text, menu)
            show_action.triggered.connect(
                lambda _=False, _callback=show_callback, _docks=docks:
                _callback() if _callback else self.showDocks(_docks))
            menu.addAction(show_action)
        if open_docks:
            close_action = QAction(close_text, menu)
            close_action.triggered.connect(lambda _=False, _docks=open_docks: self.closeDocks(_docks))
            menu.addAction(close_action)

    def show_all_scope_docks(self):
        """Show all scope docks, anchoring them to the right if needed."""
        for dock in self._scope_docks():
            self._anchor_and_show_scope_dock(dock)
        self.dockLumaWaveform.raise_()

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

    def _track_numbers(self):
        try:
            tracks = get_app().project.get("layers") or []
            return sorted(
                int(track.get("number", 0))
                for track in tracks
                if int(track.get("number", 0) or 0) > 0
            )
        except Exception:
            return []

    def _create_track(self, number):
        number = int(number)
        track = Track()
        track.data = {"number": number, "y": 0, "label": "", "lock": False}
        track.save()
        return number

    def create_track_below(self, layer_number=None):
        """Create a track below layer_number, or below the bottom track."""
        numbers = self._track_numbers()
        if not numbers:
            return self._create_track(1000000)

        if layer_number is not None:
            try:
                layer_number = int(layer_number)
            except (TypeError, ValueError):
                layer_number = None
        if layer_number in numbers:
            index = numbers.index(layer_number)
            if index > 0:
                return numbers[index - 1]

        bottom = numbers[0]
        if bottom > 2:
            return self._create_track(max(1, int(round(bottom / 2.0))))

        self.renumber_all_layers(insert_at=0)
        numbers = self._track_numbers()
        return numbers[0] if numbers else 1000000

    def track_stack_from(self, layer_number, count):
        """Return count tracks starting at layer_number and continuing downward."""
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return []

        try:
            layer_number = int(layer_number)
        except (TypeError, ValueError):
            layer_number = None

        numbers = self._track_numbers()
        if layer_number is None or layer_number <= 0:
            layer_number = numbers[-1] if numbers else self.create_track_below()
        elif layer_number not in numbers:
            self.ensure_tracks_for_layers([layer_number])

        tracks = [layer_number]
        current = layer_number
        while len(tracks) < count:
            current = self.create_track_below(current)
            if current in tracks:
                break
            tracks.append(current)
        return tracks

    def ensure_tracks_for_layers(self, layers):
        """Create any missing positive track numbers needed by upcoming inserts."""
        existing = set(self._track_numbers())
        created = []
        for layer in sorted(set(layers or [])):
            try:
                layer = int(layer)
            except (TypeError, ValueError):
                continue
            if layer <= 0 or layer in existing:
                continue
            self._create_track(layer)
            existing.add(layer)
            created.append(layer)
        return created

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
        self.timeline.setFocus(Qt.OtherFocusReason)

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

            def add_keyframe_positions(value):
                if isinstance(value, dict):
                    points = value.get("Points")
                    if isinstance(points, list):
                        for point in points:
                            try:
                                keyframe_time = (
                                    (point["co"]["X"] - 1) / fps_float
                                    - obj.data["start"] + obj.data["position"]
                                )
                                if clip_start_time < keyframe_time < clip_stop_time:
                                    positions.append(keyframe_time)
                            except (TypeError, KeyError):
                                pass
                        return
                    for child in value.values():
                        add_keyframe_positions(child)
                elif isinstance(value, list):
                    for child in value:
                        add_keyframe_positions(child)

            # add all object keyframes
            for property in obj.data:
                add_keyframe_positions(obj.data[property])

            return positions

        # We can always jump to the beginning of the timeline
        all_marker_positions = [0]
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        frame_duration = float(fps["den"]) / float(fps["num"])

        # If nothing is selected, also add the end of the last clip
        if not self.selected_clips + self.selected_transitions + self.selected_effects:
            last_frame = get_app().window.timeline_sync.GetLastFrame()
            all_marker_positions.append((last_frame - 1) / fps_float)

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

                def add_effect_keyframe_positions(value):
                    if isinstance(value, dict):
                        points = value.get("Points")
                        if isinstance(points, list):
                            for point in points:
                                try:
                                    keyframe_time = (point["co"]["X"] - 1) / fps_float + clip_orig_time
                                    if clip_start_time < keyframe_time < clip_stop_time:
                                        all_marker_positions.append(keyframe_time)
                                except (TypeError, KeyError):
                                    pass
                            return
                        for child in value.values():
                            add_effect_keyframe_positions(child)
                    elif isinstance(value, list):
                        for child in value:
                            add_effect_keyframe_positions(child)

                for prop in effect.data:
                    add_effect_keyframe_positions(effect.data[prop])
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
            frame_to_seek = min(frame_to_seek, get_app().window.timeline_sync.GetLastFrame())
            self.SeekSignal.emit(frame_to_seek, True)

            # Keep properties in sync with the seek target. Avoid forcing
            # refreshFrameSignal here: it can queue a stale seek to the old
            # player position and overwrite this navigation jump.
            get_app().window.propertyTableView.select_frame(frame_to_seek)
        self.timeline.setFocus(Qt.OtherFocusReason)

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
            frame_to_seek = min(frame_to_seek, get_app().window.timeline_sync.GetLastFrame())
            self.SeekSignal.emit(frame_to_seek, True)

            # Keep properties in sync with the seek target. Avoid forcing
            # refreshFrameSignal here: it can queue a stale seek to the old
            # player position and overwrite this navigation jump.
            get_app().window.propertyTableView.select_frame(frame_to_seek)
        self.timeline.setFocus(Qt.OtherFocusReason)

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

            # Detect whether the project profile is actually changing
            current_profile_desc = proj.get("profile")
            current_width = proj.get("width")
            current_height = proj.get("height")
            current_fps = proj.get("fps")
            profile_changed = any([
                current_profile_desc != profile.info.description,
                current_width != profile.info.width,
                current_height != profile.info.height,
                not current_fps,
                current_fps.get("num") != profile.info.fps.num,
                current_fps.get("den") != profile.info.fps.den
            ])

            # Get current FPS (prior to changing)
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
            if profile_changed:
                # Export dialog settings are profile-dependent; reset cache on profile changes.
                get_app().updates.update(["export_settings"], None)

            # Clear transaction id
            get_app().updates.transaction_id = None

            # Seek to the same location, adjusted for new frame rate
            self.SeekSignal.emit(adjusted_frame, True)

            # Refresh frame (since size of preview might have changed)
            QTimer.singleShot(500, lambda: self.refreshFrameSignal.emit())
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

    def comfy_ui_url(self):
        return self.generation_service.comfy_ui_url()

    def is_comfy_available(self, force=False):
        return self.generation_service.is_comfy_available(force=force)

    def refresh_comfy_availability_async(self, timeout=0.5, callback=None):
        return self.generation_service.refresh_comfy_availability_async(timeout=timeout, callback=callback)

    def can_open_generate_dialog(self):
        return self.generation_service.can_open_generate_dialog()

    def active_generation_job_for_file(self, file_id):
        if not getattr(self, "generation_queue", None):
            return None
        return self.generation_queue.get_active_job_for_file(file_id)

    def cancel_generation_job(self, job_id):
        if not job_id:
            log.debug("MainWindow cancel_generation_job ignored; empty job_id")
            return
        log.debug("MainWindow cancel_generation_job requested job=%s", str(job_id))
        if self.generation_queue.cancel_job(job_id):
            log.debug("MainWindow cancel_generation_job accepted job=%s", str(job_id))
            self.statusBar.showMessage("Generation canceled", 3000)
        else:
            log.debug("MainWindow cancel_generation_job rejected job=%s", str(job_id))

    def actionCancelGenerationJob_trigger(self, checked=True):
        file_id = self.current_file_id()
        if not file_id:
            return
        active_job = self.active_generation_job_for_file(file_id)
        if active_job:
            self.cancel_generation_job(active_job.get("id"))

    def actionGenerate_trigger(self, checked=True):
        self.generation_service.action_generate_trigger(checked=checked)

    def _on_generation_job_finished(self, job_id, status):
        self.generation_service.on_generation_job_finished(job_id, status)

    def _optimized_preview_files_for_action(self):
        files = []
        for file_obj in (self.selected_files() or []):
            if not file_obj:
                continue
            data = getattr(file_obj, "data", {}) or {}
            if str(data.get("media_type", "") or "").strip().lower() == "video":
                files.append(file_obj)
        if files:
            return files

        target_ids = [str(file_id or "") for file_id in getattr(self, "_optimized_preview_target_file_ids", []) if str(file_id or "")]
        if not target_ids:
            return []
        return [
            file_obj for file_obj in (File.get(id=file_id) for file_id in target_ids)
            if file_obj and str((getattr(file_obj, "data", {}) or {}).get("media_type", "") or "").strip().lower() == "video"
        ]

    def _optimized_preview_file_for_cancel_action(self):
        file_id = self.current_file_id()
        if file_id:
            file_obj = File.get(id=file_id)
            data = getattr(file_obj, "data", {}) or {}
            if file_obj and str(data.get("media_type", "") or "").strip().lower() == "video":
                return file_obj

        files = self._optimized_preview_files_for_action()
        return files[0] if files else None

    def actionOptimizedPreviewCreate_trigger(self, checked=True):
        files = self._optimized_preview_files_for_action()
        log.debug("actionOptimizedPreviewCreate_trigger files=%s", [getattr(f, "id", None) for f in files])
        self.proxy_service.create_for_files(files)

    def actionOptimizedPreviewUseExisting_trigger(self, checked=True):
        files = self._optimized_preview_files_for_action()
        log.debug("actionOptimizedPreviewUseExisting_trigger files=%s", [getattr(f, "id", None) for f in files])
        self.proxy_service.use_existing_for_files(files)

    def actionOptimizedPreviewRemove_trigger(self, checked=True):
        files = self._optimized_preview_files_for_action()
        log.debug("actionOptimizedPreviewRemove_trigger files=%s", [getattr(f, "id", None) for f in files])
        self.proxy_service.remove_for_files(files)

    def actionOptimizedPreviewCancel_trigger(self, checked=True):
        file_obj = self._optimized_preview_file_for_cancel_action()
        log.debug("actionOptimizedPreviewCancel_trigger file=%s", getattr(file_obj, "id", None))
        if file_obj:
            self.proxy_service.cancel_for_files([file_obj])

    def actionOptimizedPreviewDeleteAndUnlink_trigger(self, checked=True):
        files = self._optimized_preview_files_for_action()
        log.debug("actionOptimizedPreviewDeleteAndUnlink_trigger files=%s", [getattr(f, "id", None) for f in files])
        self.proxy_service.delete_and_unlink_for_files(files)

    def _refresh_optimized_preview_action_states(self):
        if getattr(self, "optimizedPreviewMenu", None):
            populate_optimized_preview_menu(self, self.optimizedPreviewMenu)

    def actionRemove_from_Project_trigger(self):
        log.debug("actionRemove_from_Project_trigger")

        # Transaction id to group all deletes together
        get_app().updates.transaction_id = str(uuid.uuid4())

        # Loop through selected files
        for f in self.selected_files():
            if not f:
                continue

            # Cancel queued/running generation jobs tied to this file
            if getattr(self, "generation_queue", None):
                self.generation_queue.cancel_jobs_for_file(f.data.get("id"))

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

    def actionRemoveClip_trigger(self, checked=True, refresh=True):
        log.debug('actionRemoveClip_trigger')

        locked_tracks = [l.get("number") for l in get_app().project.get('layers') if l.get("lock", False)]
        created_transaction = False
        if not get_app().updates.transaction_id:
            get_app().updates.transaction_id = str(uuid.uuid4())
            created_transaction = True

        try:
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
        finally:
            if created_transaction:
                get_app().updates.transaction_id = None

        # Refresh preview
        if refresh:
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
        if (not self.dockProperties.isVisible()
                or self.dockProperties.isFloating()
                or self.dockWidgetArea(self.dockProperties) == Qt.NoDockWidgetArea):
            self._anchor_and_show_properties_dock()

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

    def actionRemoveTransition_trigger(self, checked=True, refresh=True):
        log.debug('actionRemoveTransition_trigger')

        locked_tracks = [l.get("number")
                         for l in get_app().project.get('layers')
                         if l.get("lock", False)]
        created_transaction = False
        if not get_app().updates.transaction_id:
            get_app().updates.transaction_id = str(uuid.uuid4())
            created_transaction = True

        try:
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
        finally:
            if created_transaction:
                get_app().updates.transaction_id = None

        # Refresh preview
        if refresh:
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

        track_name = selected_track.data["label"] or _("Track %s") % QLocale().toString(display_count)

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
            self.filesTreeView.refresh_view()

        # Transitions
        elif app.context_menu_object == "transitions":
            s.set("transitions_view", "details")
            self.transitionsListView.hide()
            self.transitionsView = self.transitionsTreeView
            self.transitionsView.show()
            self.transitionsTreeView.refresh_columns()

        # Effects
        elif app.context_menu_object == "effects":
            s.set("effects_view", "details")
            self.effectsListView.hide()
            self.effectsView = self.effectsTreeView
            self.effectsView.show()
            self.effectsTreeView.refresh_columns()

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
        property_view = getattr(self, "propertyTableView", None)
        color_grade_dock = getattr(property_view, "color_grade_wheels_dock", None)
        for dock in docks:
            if dock is color_grade_dock and hasattr(property_view, "_ensure_color_grade_wheels_dock_attached"):
                property_view._ensure_color_grade_wheels_dock_attached()
            if dock is getattr(self, "dockAudioRecording", None):
                self._ensure_audio_recording_dock_content()
            if self.dockWidgetArea(dock) != Qt.NoDockWidgetArea:
                # Only show correctly docked widgets
                dock.show()

    def closeDocks(self, docks):
        """Close dockable widgets."""
        for dock in docks:
            if self._dock_is_open(dock):
                dock.hide()

    def addViewDocksMenu(self):
        """Insert dynamic Custom Views, Docks, and Scopes submenus into the View menu."""
        _ = get_app()._tr
        self.custom_views_menu = QMenu(_("My Views"), self.menuView)
        separator_after_views = self.menuWindow.menuAction()
        color_view_index = self.menuView.actions().index(self.actionColor_Grade_View)
        for action in self.menuView.actions()[color_view_index + 1:]:
            if action.isSeparator():
                separator_after_views = action
                break
        mic_icon = QIcon(os.path.join(info.PATH, "themes/cosmic/images/tool-microphone.svg"))
        self.actionAudio_Recording_View = QAction(mic_icon, _("Recording View"), self.menuView)
        self.actionAudio_Recording_View.setObjectName("actionAudio_Recording_View")
        self.actionAudio_Recording_View.setShortcut(QKeySequence("Alt+Shift+3"))
        self.actionAudio_Recording_View.triggered.connect(self.actionAudio_Recording_View_trigger)
        self.menuView.insertAction(separator_after_views, self.actionAudio_Recording_View)
        self.menuView.insertSeparator(separator_after_views)
        self.menuView.insertMenu(separator_after_views, self.custom_views_menu)
        self.custom_views_menu.aboutToShow.connect(self._rebuild_custom_views_menu)
        self.docks_menu = QMenu(_("Docks"), self.menuView)
        self.menuView.insertMenu(self.menuWindow.menuAction(), self.docks_menu)
        self.docks_menu.aboutToShow.connect(self._rebuild_docks_menu)
        self.scopes_menu = QMenu(_("Scopes"), self.menuView)
        self.menuView.insertMenu(self.menuWindow.menuAction(), self.scopes_menu)
        self.scopes_menu.aboutToShow.connect(self._rebuild_scopes_menu)

    def _custom_views(self):
        """Return saved custom views from settings."""
        views = get_app().get_settings().get("custom_views") or []
        if not isinstance(views, list):
            return []
        valid_views = []
        for view in views:
            if not isinstance(view, dict):
                continue
            if not view.get("id") or not view.get("name") or not view.get("state"):
                continue
            valid_views.append(view)
        return valid_views

    def _set_custom_views(self, views):
        """Persist the custom view list."""
        s = get_app().get_settings()
        s.set("custom_views", views)
        if hasattr(s, "save"):
            s.save()

    def _active_custom_view_id(self):
        return (
            getattr(self, "_active_custom_view_id_value", "")
            or get_app().get_settings().get("active_custom_view")
            or ""
        )

    def _set_active_custom_view_id(self, view_id):
        self._active_custom_view_id_value = view_id or ""
        s = get_app().get_settings()
        s.set("active_custom_view", self._active_custom_view_id_value)
        if self._active_custom_view_id_value:
            s.set("active_builtin_view", "")
        if hasattr(s, "save"):
            s.save()

    def _active_builtin_view(self):
        """Return the built-in view whose critical layout should survive restart."""
        value = get_app().get_settings().get("active_builtin_view") or ""
        return value if value in {"simple", "color", "recording"} else ""

    def _set_active_builtin_view(self, view_id):
        """Persist the selected built-in view independently from custom views."""
        value = view_id if view_id in {"simple", "color", "recording"} else ""
        s = get_app().get_settings()
        s.set("active_builtin_view", value)
        if value:
            self._active_custom_view_id_value = ""
            s.set("active_custom_view", "")
        if hasattr(s, "save"):
            s.save()

    def _active_custom_view(self):
        active_id = self._active_custom_view_id()
        for view in self._custom_views():
            if view.get("id") == active_id:
                return view
        return None

    def _current_custom_view_data(self, view_id, name):
        """Capture the current dock layout as a custom view."""
        dock = getattr(self, "dockTimeline", None)
        hidden = [
            d.objectName() for d in self.getDocks()
            if self.dockWidgetArea(d) == Qt.NoDockWidgetArea
        ]
        return {
            "id": view_id,
            "name": name,
            "state": qt_types.bytes_to_str(self.saveState()),
            "hidden_docks": hidden,
            "timeline_height": dock.height() if dock else 0,
        }

    def _rebuild_custom_views_menu(self):
        """Repopulate the Custom Views menu."""
        self.custom_views_menu.clear()
        _ = get_app()._tr
        views = sorted(self._custom_views(), key=lambda view: view.get("name", "").lower())
        active_id = self._active_custom_view_id()

        if views:
            view_group = QActionGroup(self.custom_views_menu)
            for view in views:
                action = QAction(view.get("name", ""), self.custom_views_menu)
                is_active = view.get("id") == active_id
                action.setCheckable(True)
                action.setChecked(is_active)
                action.triggered.connect(
                    functools.partial(self.apply_custom_view, view.get("id")))
                view_group.addAction(action)
                self.custom_views_menu.addAction(action)
            self.custom_views_menu.addSeparator()

        active_view = self._active_custom_view()
        if active_view:
            update_action = QAction(
                _('Update "%s"') % active_view.get("name", ""),
                self.custom_views_menu)
            update_action.triggered.connect(self.update_active_custom_view)
            self.custom_views_menu.addAction(update_action)

            delete_action = QAction(
                _('Delete "%s"') % active_view.get("name", ""),
                self.custom_views_menu)
            delete_action.triggered.connect(self.delete_active_custom_view)
            self.custom_views_menu.addAction(delete_action)
            self.custom_views_menu.addSeparator()

        save_as_action = QAction(_("Save Current View As..."), self.custom_views_menu)
        save_as_action.triggered.connect(self.save_current_view_as)
        self.custom_views_menu.addAction(save_as_action)

    def _rebuild_docks_menu(self):
        """Repopulate the Docks menu so late-created docks (e.g. Color Wheels) are included."""
        self.docks_menu.clear()
        docks = sorted(self._view_menu_docks(), key=lambda d: d.windowTitle())
        for dock in docks:
            action = dock.toggleViewAction()
            action.setEnabled(True)
            self.docks_menu.addAction(action)

    def _rebuild_scopes_menu(self):
        """Repopulate the Scopes menu with scope docks and scope recovery actions."""
        self.scopes_menu.clear()
        _ = get_app()._tr
        docks = sorted(self._scope_docks(), key=lambda d: d.windowTitle())
        for dock in docks:
            action = dock.toggleViewAction()
            action.setEnabled(True)
            self.scopes_menu.addAction(action)
        self._add_dock_visibility_actions(
            self.scopes_menu, docks, _("Show All Scopes"), _("Close All Scopes"),
            show_callback=self.show_all_scope_docks)

    def createPopupMenu(self):
        """Override Qt's right-click context menu to include all closable docks."""
        menu = QMenu(self)
        for dock in sorted(self.getDocks(), key=lambda d: d.windowTitle()):
            if dock.objectName() in {"dockTimeline", "dockTutorial"}:
                continue
            action = dock.toggleViewAction()
            action.setEnabled(True)
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.actionView_Toolbar)
        return menu

    def _restore_hidden_docks(self, hidden_names):
        """Remove docks hidden by a saved layout."""
        if not hidden_names:
            return
        name_to_dock = {d.objectName(): d for d in self.getDocks()}
        for name in hidden_names:
            dock = name_to_dock.get(name)
            if dock:
                self.removeDockWidget(dock)

    def _prepare_docks_for_state_restore(self):
        """Attach removed docks so restoreState can place them."""
        for dock in self.getDocks():
            if self.dockWidgetArea(dock) == Qt.NoDockWidgetArea:
                self.addDockWidget(Qt.TopDockWidgetArea, dock)

    def apply_custom_view(self, view_id, checked=True):
        """Apply a saved custom view by id."""
        view = None
        for custom_view in self._custom_views():
            if custom_view.get("id") == view_id:
                view = custom_view
                break
        if not view:
            return

        self._prepare_docks_for_state_restore()
        self.restoreState(qt_types.str_to_bytes(view.get("state", "")))
        self._restore_hidden_docks(view.get("hidden_docks") or [])
        timeline_height = view.get("timeline_height")
        if timeline_height:
            try:
                self.saved_timeline_height = int(timeline_height)
            except (TypeError, ValueError):
                self.saved_timeline_height = None
            self._apply_saved_timeline_height()
        self._set_active_custom_view_id(view_id)
        QCoreApplication.processEvents()
        self.style_dock_widgets()

    def save_current_view_as(self):
        """Prompt for a name and save the current layout as a custom view."""
        _ = get_app()._tr
        name, ok = QInputDialog.getText(
            self,
            _("Save Current View"),
            _("View Name:"))
        if not ok:
            return
        name = name.strip()
        if not name:
            return

        views = self._custom_views()
        if any(view.get("name", "").lower() == name.lower() for view in views):
            QMessageBox.warning(
                self,
                _("Custom View Exists"),
                _('A custom view named "%s" already exists.') % name)
            return

        view_id = str(uuid.uuid4())
        views.append(self._current_custom_view_data(view_id, name))
        self._set_custom_views(views)
        self._set_active_custom_view_id(view_id)

    def update_active_custom_view(self):
        """Overwrite the active custom view with the current layout."""
        active_view = self._active_custom_view()
        if not active_view:
            return
        views = self._custom_views()
        updated = self._current_custom_view_data(
            active_view.get("id"),
            active_view.get("name", ""))
        views = [
            updated if view.get("id") == active_view.get("id") else view
            for view in views
        ]
        self._set_custom_views(views)

    def delete_active_custom_view(self):
        """Delete the active custom view after confirmation."""
        active_view = self._active_custom_view()
        if not active_view:
            return

        _ = get_app()._tr
        name = active_view.get("name", "")
        ret = QMessageBox.question(
            self,
            _("Delete Custom View"),
            _('Delete "%s"?') % name,
            QMessageBox.No | QMessageBox.Yes,
            QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        views = [
            view for view in self._custom_views()
            if view.get("id") != active_view.get("id")
        ]
        self._set_custom_views(views)
        self._set_active_custom_view_id("")

    def actionSimple_View_trigger(self):
        """ Switch to the default / simple view  """
        self._set_active_custom_view_id("")
        self._set_active_builtin_view("simple")
        self._apply_simple_view_layout()

    def _apply_simple_view_layout(self):
        """Apply the shared Simple View dock topology."""
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

    def actionColor_Grade_View_trigger(self):
        """Switch to a color grading focused view."""
        self._set_active_custom_view_id("")
        self._set_active_builtin_view("color")
        self.removeDocks()

        color_grade_dock = getattr(getattr(self, "propertyTableView", None), "color_grade_wheels_dock", None)

        self.addDocks([self.dockProperties], Qt.LeftDockWidgetArea)
        self.addDocks([self.dockVideo], Qt.TopDockWidgetArea)
        # Right side: Color Wheels top, scope docks tabified below.
        # Order matters: split FIRST, then tabify so the bottom group stays intact.
        if color_grade_dock:
            self.addDocks([color_grade_dock], Qt.RightDockWidgetArea)
        self.addDocks([self.dockLumaWaveform], Qt.RightDockWidgetArea)
        if color_grade_dock:
            self.splitDockWidget(color_grade_dock, self.dockLumaWaveform, Qt.Vertical)
        self.addDocks([self.dockHistogram], Qt.RightDockWidgetArea)
        self.addDocks([self.dockVectorscope], Qt.RightDockWidgetArea)
        self.tabifyDockWidget(self.dockLumaWaveform, self.dockHistogram)
        self.tabifyDockWidget(self.dockHistogram, self.dockVectorscope)
        self.splitDockWidget(self.dockVideo, self.dockTimeline, Qt.Vertical)
        self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)

        self.floatDocks(False)

        docks_to_show = [
            self.dockProperties,
            self.dockVideo,
            self.dockTimeline,
            self.dockLumaWaveform,
            self.dockHistogram,
            self.dockVectorscope,
        ]
        if color_grade_dock:
            docks_to_show.append(color_grade_dock)

        self.showDocks(docks_to_show)
        QCoreApplication.processEvents()
        if color_grade_dock:
            color_grade_dock.raise_()
        self.dockLumaWaveform.raise_()
        self.style_dock_widgets()

        # Defer size adjustment so Qt has finished its layout pass first.
        # Give Color Wheels ~75% of the right column height, scope tab ~25%.
        if color_grade_dock:
            def _resize_right_column():
                available = self.height()
                scope_h = max(120, available // 4)
                wheels_h = available - scope_h
                self.resizeDocks(
                    [color_grade_dock, self.dockLumaWaveform],
                    [wheels_h, scope_h],
                    Qt.Vertical,
                )
            QTimer.singleShot(0, _resize_right_column)

    def actionAudio_Recording_View_trigger(self):
        """Show the Simple View layout with Recording docked on the right."""
        self._set_active_custom_view_id("")
        self._set_active_builtin_view("recording")
        self._ensure_audio_recording_dock_content()
        self._apply_simple_view_layout()
        self.addDocks([self.dockAudioRecording], Qt.RightDockWidgetArea)
        self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)

        self.floatDocks(False)
        self.showDocks([self.dockAudioRecording])
        self.dockAudioRecording.raise_()
        self.style_dock_widgets()

    def _current_timeline_seconds(self):
        """Return the current playhead position in seconds."""
        try:
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])
            return max(0.0, float(self.preview_thread.current_frame - 1) / fps_float)
        except Exception:
            return 0.0

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
        In the format: 00:00:23:000 --> 00:00:26:000.

        When the cursor is on an incomplete timestamp line, use the current playhead position
        as the missing end timestamp. Otherwise, insert a complete caption cue using a short
        default duration.
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
            if clip_data is not None:
                break

        if clip_data is None:
            log.info("No clip owns this caption effect")
            return

        if self.captionTextEdit.isReadOnly():
            return

        # Calculate fps / current seconds
        default_caption_duration = 3.0
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = (self.preview_thread.current_frame - 1) / fps_float
        relative_position = current_position - clip_data.get("position") + clip_data.get("start")

        # Prevent captions before or after the clip
        clip_start = clip_data.get('start')
        clip_end = clip_data.get('end')
        relative_position = max(clip_start, relative_position)
        clip_seconds = clip_data.get("end") - clip_data.get("start")
        relative_position = min(clip_end, relative_position)

        # Get cursor / current line of text (where cursor is located)
        cursor = self.captionTextEdit.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        line_text = cursor.block().text()
        cursor.movePosition(QTextCursor.EndOfLine)
        self.captionTextEdit.setTextCursor(cursor)

        # Convert time in seconds to hours:minutes:seconds:milliseconds
        current_timestamp = secondsToTimecode(relative_position, fps["num"], fps["den"], use_milliseconds=True)

        if "-->" in line_text and line_text.count(':') == 3:
            # Current line has only one timestamp. Add the second and go to the line below it.
            timestamp_parts = line_text.split("-->", 1)
            starting_timestamp = timestamp_parts[0].strip()
            if starting_timestamp == current_timestamp:
                relative_position = min(relative_position + default_caption_duration, clip_end)
                current_timestamp = secondsToTimecode(relative_position, fps["num"], fps["den"], use_milliseconds=True)
            self.captionTextEdit.insertPlainText(current_timestamp)
            self.captionTextEdit.moveCursor(QTextCursor.Down)
            self.captionTextEdit.moveCursor(QTextCursor.EndOfLine)
        else:
            # Current line isn't a starting timestamp, so add a starting timestamp
            caption_start = relative_position
            caption_end = min(caption_start + default_caption_duration, clip_end)
            if caption_end <= caption_start:
                caption_start = max(clip_start, clip_end - min(default_caption_duration, clip_seconds))
                caption_end = clip_end
                current_timestamp = secondsToTimecode(caption_start, fps["num"], fps["den"], use_milliseconds=True)
            end_timestamp = secondsToTimecode(caption_end, fps["num"], fps["den"], use_milliseconds=True)

            placeholder_text = _("Enter caption text...")
            cue_header = "%s --> %s\n" % (current_timestamp, end_timestamp)

            if self.captionTextEdit.textCursor().block().text().strip() != "":
                cursor.movePosition(QTextCursor.End)
                cursor.insertText("\n\n")

            placeholder_start = cursor.position() + len(cue_header)
            cursor.insertText("%s%s" % (cue_header, placeholder_text))
            cursor.setPosition(placeholder_start)
            cursor.setPosition(placeholder_start + len(placeholder_text), QTextCursor.KeepAnchor)
            self.captionTextEdit.setTextCursor(cursor)

        self._focus_caption_editor()

    def captionTextEdit_TextChanged(self):
        """Caption text was edited, start the save timer (to prevent spamming saves)"""
        self.caption_save_timer.start()
        self.caption_commit_timer.start()

    def caption_editor_save(self):
        """Emit the CaptionTextUpdated signal (and if that property is active/selected, it will be saved)"""
        self.CaptionTextUpdated.emit(self.captionTextEdit.toPlainText(), self.caption_model_row)

    def caption_editor_commit(self):
        """Finalize the current caption edit as a single undoable transaction."""
        self.caption_save_timer.stop()
        self.caption_editor_save()
        self.CaptionTextCommitted.emit(self.caption_model_row)

    def _configure_caption_editor(self, editable):
        """Apply the Caption dock's editable/read-only state in one place."""
        focus_widgets = [self.captionTextEdit]
        viewport = self.captionTextEdit.viewport()
        if viewport is not None:
            focus_widgets.append(viewport)
        for widget in focus_widgets:
            widget.setEnabled(True)
            widget.setFocusPolicy(Qt.StrongFocus)
            widget.setProperty("_original_focus_policy", None)
        self.captionTextEdit.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.captionTextEdit.setReadOnly(not editable)

    def _focus_caption_editor(self):
        """Return keyboard focus to the Caption text editor after toolbar actions."""
        self.captionTextEdit.setFocus(Qt.OtherFocusReason)
        QTimer.singleShot(0, lambda: self.captionTextEdit.setFocus(Qt.OtherFocusReason))

    def _caption_editor_has_focus(self):
        """Return True if the Caption editor or its viewport currently owns focus."""
        viewport = self.captionTextEdit.viewport()
        return self.captionTextEdit.hasFocus() or (viewport is not None and viewport.hasFocus())

    def _same_caption_model_row(self, first_row, second_row):
        """Return True when two Caption model row handles reference the same property."""
        if first_row is None or second_row is None:
            return first_row is second_row
        return bool(first_row and second_row and first_row[0] is second_row[0])

    def caption_editor_load(self, new_caption_text, caption_model_row):
        """Load the caption editor with text, or disable it if empty string detected"""
        if (
            self.caption_commit_timer.isActive()
            and self.caption_model_row is not None
            and not self._same_caption_model_row(self.caption_model_row, caption_model_row)
        ):
            self.caption_commit_timer.stop()
            self.caption_editor_commit()

        self.caption_model_row = caption_model_row
        if self.captionTextEdit is None:
            self.captionTextEdit = QTextEdit(self.dockCaptionContents)
            self._configure_caption_editor(False)
            self.tabCaptions.addWidget(self.captionTextEdit)
            self.captionTextEdit.textChanged.connect(self.captionTextEdit_TextChanged)

        new_caption_text = new_caption_text or ""
        if self.captionTextEdit.toPlainText() != new_caption_text:
            current_cursor = self.captionTextEdit.textCursor()
            restore_cursor = caption_model_row is not None and self._caption_editor_has_focus()
            cursor_position = current_cursor.position()
            selection_start = current_cursor.selectionStart()
            selection_end = current_cursor.selectionEnd()

            self.captionTextEdit.blockSignals(True)
            self.captionTextEdit.setPlainText(new_caption_text)
            self.captionTextEdit.blockSignals(False)

            if restore_cursor:
                doc_length = len(new_caption_text)
                cursor = self.captionTextEdit.textCursor()
                cursor.setPosition(min(selection_start, doc_length))
                cursor.setPosition(min(selection_end, doc_length), QTextCursor.KeepAnchor)
                if selection_start == selection_end:
                    cursor.setPosition(min(cursor_position, doc_length))
                self.captionTextEdit.setTextCursor(cursor)

        if caption_model_row is None:
            self._configure_caption_editor(False)
        else:
            self._configure_caption_editor(True)

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
                "%s %s [%s] - %s" % (save_indicator, _("Untitled Project"), profile, "OpenShot Video Editor")))
        else:
            # Yes, project is saved
            # Get just the filename
            filename = os.path.basename(app.project.current_filepath)
            filename = os.path.splitext(filename)[0]
            # Use singleShot since this method can be invoked by our preview thread
            QTimer.singleShot(0, functools.partial(self.setWindowTitle,
                "%s %s [%s] - %s" % (save_indicator, filename, profile, "OpenShot Video Editor")))

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

        # Always keep transform handles in sync with current selection.
        self.TransformSignal.emit(self.selected_clips)

        emitted_transform = False
        for sel in self.selected_items:
            if sel["type"] == "effect":
                effect = Effect.get(id=sel["id"])
                if effect and (
                    effect.data.get("has_tracked_object")
                    or effect.data.get("class_name") in ("Bars", "Blur", "Caption", "Crop", "Pixelate")
                    or all(prop in effect.data for prop in ("left", "top", "right", "bottom"))
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
        close_geometry = getattr(self, "_pending_close_geometry", None)
        geometry = close_geometry if close_geometry is not None else self.saveGeometry()
        s.set('window_geometry_v2', qt_types.bytes_to_str(geometry))
        self._pending_close_geometry = None
        # Qt's saveState() does not capture docks removed via removeDockWidget(); save them explicitly.
        hidden = [d.objectName() for d in self.getDocks()
                  if self.dockWidgetArea(d) == Qt.NoDockWidgetArea]
        s.set('hidden_docks', hidden)
        video = getattr(self, "dockVideo", None)
        if video:
            s.set('video_dock_width', video.width())

    # Get window settings from setting store
    def load_settings(self):
        s = get_app().get_settings()
        # Window state and geometry (also toolbar, dock locations and frozen UI state)
        if s.get('window_geometry_v2'):
            self.saved_geometry = qt_types.str_to_bytes(s.get('window_geometry_v2'))
        if s.get('window_state_v2'):
            self.saved_state = qt_types.str_to_bytes(s.get('window_state_v2'))
        self.saved_video_dock_width = self._positive_int(
            s.get('video_dock_width'))

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
        normalized_projects = []
        seen_projects = set()

        for file_path in recent_projects:
            normalized_path = normalized_local_path(file_path)
            comparable_path = comparable_local_path(normalized_path)
            if not normalized_path or comparable_path in seen_projects:
                continue
            seen_projects.add(comparable_path)
            normalized_projects.append(normalized_path)

        if normalized_projects != recent_projects:
            s.set("recent_projects", normalized_projects)
            s.save()
        recent_projects = normalized_projects

        # Add Recent Projects menu (after Open File)
        if not self.recent_menu:
            # Create a new recent menu
            self.recent_menu = self.menuFile.addMenu(
                QIcon.fromTheme("document-open-recent"),
                _("Recent Projects"))
            self.menuFile.insertMenu(self.actionRecentProjects, self.recent_menu)
        else:
            # Remove all actions individually instead of clear() — PySide6's
            # clear() can delete QActions owned by other parents (e.g. actionClearRecents),
            # crashing the next load_recent_menu call with "C++ object already deleted".
            for _action in list(self.recent_menu.actions()):
                self.recent_menu.removeAction(_action)

        # Add recent projects to menu
        # Show just a placeholder menu, if we have no recent projects list
        if not recent_projects:
            self.recent_menu.addAction(_("No Recent Projects")).setDisabled(True)
            return

        for file_path in reversed(recent_projects):
            # Add each recent project
            native_path = native_display_path(file_path)
            new_action = self.recent_menu.addAction(native_path)
            new_action.setToolTip(native_path)
            new_action.triggered.connect(functools.partial(self.recent_project_clicked, file_path))

        # Add 'Clear Recent Projects' menu to bottom of list
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.actionClearRecents)
        try:
            self.actionClearRecents.triggered.disconnect(self.clear_recents_clicked)
        except TypeError:
            pass
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
            recovery_files = [
                f for f in os.listdir(recovery_dir)
                if (f.endswith(".osp") or f.endswith(".zip")) and "-" in f and current_filepath and f.split("-", 1)[1].startswith(os.path.basename(current_filepath).replace(".osp", ""))
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
                recovered_filename = os.path.splitext(os.path.basename(current_filepath))[0] + f"-{int(time())}-backup.osp"
                recovered_filepath = os.path.join(os.path.dirname(current_filepath), recovered_filename)
                if os.path.exists(current_filepath):
                    shutil.move(current_filepath, recovered_filepath)
                    log.info(f"Backup current project to: {recovered_filepath}")

                # Unzip if the selected recovery file is a .zip file
                if file_path.endswith(".zip"):
                    with zipfile.ZipFile(file_path, 'r') as zipf:
                        # Extract over top original project *.osp file
                        zipf.extractall(os.path.dirname(current_filepath))
                        extracted_files = zipf.namelist()
                        if len(extracted_files) != 1:
                            raise ValueError("Unexpected number of files in recovery zip.")
                else:
                    # Replace the original *.osp project file with the recovery file *.osp
                    shutil.copyfile(file_path, current_filepath)
                log.info(f"Recovery file `{file_path}` restored to: `{current_filepath}`")

                # Open the recovered project
                self.OpenProjectSignal.emit(current_filepath)

            except Exception as ex:
                log.error(f"Error recovering project from `{file_path}` to `{current_filepath}`: {ex}", exc_info=True)

    def remove_recent_project(self, file_path):
        """Remove a project from the Recent menu if OpenShot can't find it"""
        s = get_app().get_settings()
        recent_projects = s.get("recent_projects")
        file_key = comparable_local_path(file_path)
        recent_projects = [
            existing_path for existing_path in recent_projects
            if comparable_local_path(existing_path) != file_key
        ]
        s.set("recent_projects", recent_projects)
        s.save()

    def recent_project_clicked(self, file_path):
        """ Load a recent project when clicked """
        self.OpenProjectSignal.emit(file_path)

    def clear_recents_clicked(self):
        """Clear all recent projects"""
        s = get_app().get_settings()
        s.set("recent_projects", [])
        s.save()

        # Reload recent project list
        self.load_recent_menu()

    def setup_toolbars(self):
        _ = get_app()._tr  # Get translation function

        # Start undo and redo actions disabled
        self.actionUndo.setEnabled(False)
        self.actionRedo.setEnabled(False)

        # Add files toolbar
        self.filesToolbar = QToolBar("Files Toolbar", self.dockFilesContents)
        self.filesToolbar.setObjectName("filesToolbar")
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
        self.filesFilter = QLineEdit(self.filesToolbar)
        self.filesFilter.setObjectName("filesFilter")
        self.filesFilter.setPlaceholderText(_("Filter"))
        self.filesFilter.setClearButtonEnabled(True)
        self.filesToolbar.addWidget(self.filesFilter)
        self.tabFiles.insertWidget(0, self.filesToolbar)

        # Add transitions toolbar
        self.transitionsToolbar = QToolBar("Transitions Toolbar", self.dockTransitionsContents)
        self.transitionsToolbar.setObjectName("transitionsToolbar")
        self.transitionsActionGroup = QActionGroup(self)
        self.transitionsActionGroup.setExclusive(True)
        self.transitionsActionGroup.addAction(self.actionTransitionsShowAll)
        self.transitionsActionGroup.addAction(self.actionTransitionsShowCommon)
        self.actionTransitionsShowAll.setChecked(True)
        self.transitionsToolbar.addAction(self.actionTransitionsShowAll)
        self.transitionsToolbar.addAction(self.actionTransitionsShowCommon)
        self.transitionsFilter = QLineEdit(self.transitionsToolbar)
        self.transitionsFilter.setObjectName("transitionsFilter")
        self.transitionsFilter.setPlaceholderText(_("Filter"))
        self.transitionsFilter.setClearButtonEnabled(True)
        self.transitionsToolbar.addWidget(self.transitionsFilter)
        self.tabTransitions.addWidget(self.transitionsToolbar)

        # Add effects toolbar
        self.effectsToolbar = QToolBar("Effects Toolbar", self.dockEffectsContents)
        self.effectsToolbar.setObjectName("effectsToolbar")
        self.effectsFilter = QLineEdit(self.effectsToolbar)
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
        self.tabEffects.addWidget(self.effectsToolbar)

        # Add emojis toolbar
        self.emojisToolbar = QToolBar("Emojis Toolbar", self.dockEmojisContents)
        self.emojisToolbar.setObjectName("emojisToolbar")
        self.emojiFilterGroup = QComboBox(self.emojisToolbar)
        self.emojisFilter = QLineEdit(self.emojisToolbar)
        self.emojisFilter.setObjectName("emojisFilter")
        self.emojisFilter.setPlaceholderText(_("Filter"))
        self.emojisFilter.setClearButtonEnabled(True)
        self.emojisToolbar.addWidget(self.emojiFilterGroup)
        self.emojisToolbar.addWidget(self.emojisFilter)
        self.tabEmojis.addWidget(self.emojisToolbar)

        # Add Video Preview toolbar
        self.videoToolbar = QToolBar("Video Toolbar", self.dockVideoContents)
        self.videoToolbar.setObjectName("videoToolbar")
        self.tabVideo.addWidget(self.videoToolbar)

        # Add Timeline toolbar
        self.timelineToolbar = QToolBar("Timeline Toolbar", getattr(self, "dockTimelineContents", self))
        self.timelineToolbar.setObjectName("timelineToolbar")

        # Add Video Preview toolbar
        self.captionToolbar = QToolBar(_("Caption Toolbar"), self.dockCaptionContents)

        # Add Caption text editor widget
        self.captionTextEdit = QTextEdit(self.dockCaptionContents)
        self.captionTextEdit.setObjectName("captionTextEdit")
        self._configure_caption_editor(False)

        # Playback controls (centered)
        self.captionToolbar.addAction(self.actionInsertTimestamp)
        self.tabCaptions.addWidget(self.captionToolbar)
        self.tabCaptions.addWidget(self.captionTextEdit)

        # Hook up caption editor signal
        self.captionTextEdit.textChanged.connect(self.captionTextEdit_TextChanged)
        self.caption_save_timer = QTimer(self)
        self.caption_save_timer.setInterval(250)
        self.caption_save_timer.setSingleShot(True)
        self.caption_save_timer.timeout.connect(self.caption_editor_save)
        self.caption_commit_timer = QTimer(self)
        self.caption_commit_timer.setInterval(2500)
        self.caption_commit_timer.setSingleShot(True)
        self.caption_commit_timer.timeout.connect(self.caption_editor_commit)
        self.CaptionTextLoaded.connect(self.caption_editor_load)
        self.caption_model_row = None

        # Get project's initial zoom value
        initial_scale = float(get_app().project.get("scale") or 15.0)

        # Setup Zoom Slider widget
        from windows.views.zoom_slider import ZoomSlider
        self.sliderZoomWidget = ZoomSlider(self)
        self.sliderZoomWidget.setMinimumHeight(20)
        self.sliderZoomWidget.setZoomFactor(initial_scale, emit=False)

        # add zoom widgets
        self.timelineToolbar.addWidget(self.sliderZoomWidget)

        # Add timeline toolbar to web frame
        self.frameWeb.insertWidget(0, self.timelineToolbar)
        self.timelineToolbar.show()

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

    def foundCurrentVersion(self, version):
        """Handle the callback for detecting the current version on openshot.org"""
        _ = get_app()._tr

        # Compare versions (alphabetical compare of version strings should work fine)
        if info.VERSION < version:
            # Update text for QAction
            self.actionUpdate.setVisible(True)
            self.actionUpdate.setText(_("Update Available"))
            self.actionUpdate.setToolTip(_("Update Available: <b>%s</b>") % version)

            # Add toolbar button for non-cosmic dusk themes
            # Cosmic dusk has a hidden toolbar button which is made visible
            # by the setVisible() call above this
            if get_app().theme_manager:
                from themes.manager import ThemeName
                theme = get_app().theme_manager.get_current_theme()
                if theme and theme.name != ThemeName.COSMIC.value:
                    # Add spacer and 'New Version Available' toolbar button (default hidden)
                    spacer = QWidget(self)
                    spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.toolBar.addWidget(spacer)

                    # Add update available button (with icon and text)
                    updateButton = QToolButton(self)
                    updateButton.setDefaultAction(self.actionUpdate)
                    updateButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                    self.toolBar.addWidget(updateButton)
            else:
                log.warning("No ThemeManager loaded yet. Skip update available button.")

        # Initialize sentry exception tracing (now that we know the current version)
        from classes import sentry
        sentry.init_tracing()

    def handleSeek(self, frame, _start_preroll=True):
        """ Always update the property view when we seek to a new position """
        # Notify properties dialog
        if self.propertyTableView:
            self.propertyTableView.select_frame(frame)

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

    def _restore_saved_window_state(self):
        """Restore Qt's serialized dock state after final window sizing."""
        if self._restored_saved_window:
            return
        self._restored_saved_window = True
        if self.saved_state:
            self.restoreState(self.saved_state)
        # Qt state does not remember docks explicitly removed from all areas.
        hidden_names = get_app().get_settings().get('hidden_docks') or []
        self._restore_hidden_docks(hidden_names)
        QTimer.singleShot(0, self._restore_saved_video_dock_width)

    def _restore_saved_video_dock_width(self):
        """Correct Qt 5 fractional-scale drift in the horizontal dock splitter."""
        files = getattr(self, "dockFiles", None)
        video = getattr(self, "dockVideo", None)
        width = self._positive_int(
            getattr(self, "saved_video_dock_width", None))
        if not (files and video and width):
            return
        total_width = files.width() + video.width()
        self.resizeDocks(
            [files, video],
            [max(1, total_width - width), width],
            Qt.Horizontal,
        )

    def _restore_saved_geometry_before_show(self):
        """Restore outer geometry before the window is mapped."""
        if self.saved_geometry:
            self.restoreGeometry(self.saved_geometry)

    @staticmethod
    def _positive_int(value):
        """Return value as a positive int, or None."""
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _force_dock_extent_once(self, dock, size, orientation):
        """Temporarily constrain a dock extent, safely coalescing repeated calls."""
        if not dock:
            return
        size = self._positive_int(size)
        if not size:
            return
        pending = getattr(self, "_pending_dock_extent_restores", None)
        if pending is None:
            pending = {}
            self._pending_dock_extent_restores = pending

        if orientation == Qt.Horizontal:
            size = min(size, max(160, int(self.width() * 0.85)))
            current = dock.width()
            get_limits = lambda: (dock.minimumWidth(), dock.maximumWidth())
            set_fixed = dock.setFixedWidth
            restore = lambda limits: (
                dock.setMinimumWidth(limits[0]),
                dock.setMaximumWidth(limits[1]),
            )
        else:
            size = min(size, max(100, int(self.height() * 0.85)))
            current = dock.height()
            get_limits = lambda: (dock.minimumHeight(), dock.maximumHeight())
            set_fixed = dock.setFixedHeight
            restore = lambda limits: (
                dock.setMinimumHeight(limits[0]),
                dock.setMaximumHeight(limits[1]),
            )

        if current == size and dock not in pending:
            return
        if dock not in pending:
            pending[dock] = get_limits()

            def restore_flexibility():
                limits = pending.pop(dock, None)
                if limits is not None:
                    restore(limits)

            QTimer.singleShot(0, restore_flexibility)
        set_fixed(size)

    def _apply_saved_timeline_height(self):
        """Apply the saved timeline dock height."""
        self._force_dock_extent_once(
            getattr(self, "dockTimeline", None),
            self.saved_timeline_height,
            Qt.Vertical)

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
        self.files_model = FilesModel(generation_queue=self.generation_queue, proxy_service=self.proxy_service)
        self.filesTreeView = FilesTreeView(self.files_model)
        self.filesListView = FilesListView(self.files_model)
        self.files_model.update_model()
        self.tabFiles.insertWidget(-1, self.filesTreeView)
        self.tabFiles.insertWidget(-1, self.filesListView)
        if s.get("file_view") == "details":
            self.filesView = self.filesTreeView
            self.filesListView.hide()
        else:
            self.filesView = self.filesListView
            self.filesTreeView.hide()
        # Show our currently-enabled project files view
        self.filesView.show()
        self.filesView.setFocus()
        if self.filesView == self.filesTreeView:
            self.filesTreeView.refresh_view()

        # Setup transitions tree and list views
        self.transition_model = TransitionsModel()
        self.transitionsTreeView = TransitionsTreeView(self.transition_model)
        self.transitionsListView = TransitionsListView(self.transition_model)
        self.transition_model.update_model()
        self.tabTransitions.insertWidget(-1, self.transitionsTreeView)
        self.tabTransitions.insertWidget(-1, self.transitionsListView)
        if s.get("transitions_view") == "details":
            self.transitionsView = self.transitionsTreeView
            self.transitionsListView.hide()
        else:
            self.transitionsView = self.transitionsListView
            self.transitionsTreeView.hide()
        # Show our currently-enabled transitions view
        self.transitionsView.show()
        self.transitionsView.setFocus()
        if self.transitionsView == self.transitionsTreeView:
            self.transitionsTreeView.refresh_columns()

        # Setup effects tree
        self.effects_model = EffectsModel()
        self.effectsTreeView = EffectsTreeView(self.effects_model)
        self.effectsListView = EffectsListView(self.effects_model)
        self.effects_model.update_model()
        self.tabEffects.insertWidget(-1, self.effectsTreeView)
        self.tabEffects.insertWidget(-1, self.effectsListView)
        if s.get("effects_view") == "details":
            self.effectsView = self.effectsTreeView
            self.effectsListView.hide()
        else:
            self.effectsView = self.effectsListView
            self.effectsTreeView.hide()
        # Show our currently-enabled effects view
        self.effectsView.show()
        self.effectsView.setFocus()
        if self.effectsView == self.effectsTreeView:
            self.effectsTreeView.refresh_columns()

        # Setup emojis view
        self.emojis_model = EmojisModel()
        self.emojis_model.update_model()
        self.emojiListView = EmojisListView(self.emojis_model)
        self.tabEmojis.addWidget(self.emojiListView)

    def _init_generation_actions(self):
        _ = get_app()._tr

        self.actionGenerate = QAction(_("Generate..."), self)
        self.actionGenerate.setObjectName("actionGenerate")
        sparkle_icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", "tool-generate-sparkle.svg")
        self.actionGenerate.setIcon(QIcon(sparkle_icon_path))
        self.actionGenerate.setShortcut(QKeySequence("Ctrl+G"))
        self.actionGenerate.setShortcutContext(Qt.ApplicationShortcut)
        self.actionGenerate.triggered.connect(self.actionGenerate_trigger)

        self.actionCancelGenerationJob = QAction(_("Cancel Job"), self)
        self.actionCancelGenerationJob.setObjectName("actionCancelGenerationJob")
        self.actionCancelGenerationJob.triggered.connect(self.actionCancelGenerationJob_trigger)

    def _init_proxy_actions(self):
        _ = get_app()._tr

        self.actionOptimizedPreviewCreate = QAction(_("Optimize Video"), self)
        self.actionOptimizedPreviewCreate.setObjectName("actionOptimizedPreviewCreate")
        self.actionOptimizedPreviewCreate.triggered.connect(self.actionOptimizedPreviewCreate_trigger)

        self.actionOptimizedPreviewUseExisting = QAction(_("Link to Existing..."), self)
        self.actionOptimizedPreviewUseExisting.setObjectName("actionOptimizedPreviewUseExisting")
        self.actionOptimizedPreviewUseExisting.triggered.connect(self.actionOptimizedPreviewUseExisting_trigger)

        self.actionOptimizedPreviewRemove = QAction(_("Unlink"), self)
        self.actionOptimizedPreviewRemove.setObjectName("actionOptimizedPreviewRemove")
        self.actionOptimizedPreviewRemove.triggered.connect(self.actionOptimizedPreviewRemove_trigger)

        self.actionOptimizedPreviewCancel = QAction(_("Cancel"), self)
        self.actionOptimizedPreviewCancel.setObjectName("actionOptimizedPreviewCancel")
        self.actionOptimizedPreviewCancel.triggered.connect(self.actionOptimizedPreviewCancel_trigger)

        self.actionOptimizedPreviewDeleteAndUnlink = QAction(_("Delete && Unlink"), self)
        self.actionOptimizedPreviewDeleteAndUnlink.setObjectName("actionOptimizedPreviewDeleteAndUnlink")
        self.actionOptimizedPreviewDeleteAndUnlink.triggered.connect(self.actionOptimizedPreviewDeleteAndUnlink_trigger)

        self.optimizedPreviewMenu = None
        if getattr(self, "menuClear", None):
            self.menuClear.aboutToShow.connect(self._refresh_clear_menu_action_states)

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
        """Remove the current selected file, keyframes, effect, clip, or transition."""
        # Set transaction id
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid
        try:
            # If the filesView has focus, remove the item from the project
            if self.filesView.hasFocus():
                self.actionRemove_from_Project_trigger()
            else:
                # Prioritize deleting selected keyframes before deleting clips.
                keyframes_deleted = False
                timeline_widget = getattr(self, "timeline", None)
                if timeline_widget and hasattr(timeline_widget, "delete_selected_keyframes"):
                    try:
                        keyframes_deleted = bool(timeline_widget.delete_selected_keyframes())
                    except Exception:
                        keyframes_deleted = False
                if keyframes_deleted:
                    self.refreshFrameSignal.emit()
                    return
                # Remove selected effects before falling back to clips/transitions.
                self.actionRemoveEffect_trigger()
                # Otherwise, proceed with the normal timeline delete behavior
                self.actionRemoveClip_trigger(refresh=False)
                self.actionRemoveTransition_trigger(refresh=False)
                self.refreshFrameSignal.emit()
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
        copied_object = ClipboardManager.from_mime(mime_data) if mime_data else None

        if mime_data and not mime_data.hasFormat("application/x-openshot-generic"):
            if self.import_files_from_clipboard(mime_data):
                return

        paste_clip_ids = self.selected_clips
        paste_tran_ids = self.selected_transitions
        if isinstance(copied_object, (Clip, Transition)):
            paste_clip_ids = []
            paste_tran_ids = []
        elif isinstance(copied_object, list) and copied_object and all(
            isinstance(obj, (Clip, Transition)) for obj in copied_object
        ):
            paste_clip_ids = []
            paste_tran_ids = []

        self.timeline.context_menu_cursor_position = None
        self.timeline.Paste_Triggered(MenuCopy.PASTE, paste_clip_ids, paste_tran_ids)

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

        if (isinstance(obj, QTabBar)
                and event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.MiddleButton):
            if self._close_dock_tab_from_middle_click(obj, event):
                return True

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
            "actionProperties",
            "actionJumpStart",
            "actionJumpEnd",
            "actionRippleSliceKeepLeft",
            "actionRippleSliceKeepRight"
        ]

        # Check if event type is a shortcut override (keyboard shortcut triggered)
        if event.type() == QEvent.ShortcutOverride:
            focused_widget = self.focusWidget()
            if self._blocks_timeline_shortcuts(focused_widget):
                for action_name in ignored_actions:
                    try:
                        sequences = get_app().window.getShortcutByName(action_name)
                        for sequence in sequences:
                            try:
                                modifiers = event.modifiers()
                                key = event.key()
                                combo = int(modifiers.value) | int(key) if hasattr(modifiers, "value") else int(modifiers) | int(key)
                            except Exception:
                                combo = event.modifiers() | event.key()
                            if (sequence == QKeySequence(combo)):
                                event.accept()
                                return True
                    except KeyError:
                        pass

                return super(MainWindow, self).eventFilter(obj, event)

            # If any of these dock widgets have focus, we want to block specific actions
            if self.emojiListView.hasFocus() or self.filesView.hasFocus() or \
                self.transitionsView.hasFocus() or self.effectsView.hasFocus():

                # Check for each QAction name in the ignored_actions list
                for action_name in ignored_actions:
                    try:
                        # Get the shortcut key sequence
                        sequences = get_app().window.getShortcutByName(action_name)
                        for sequence in sequences:
                            if hasattr(event, "keyCombination"):
                                event_sequence = QKeySequence(event.keyCombination())
                            else:
                                event_sequence = QKeySequence(event.modifiers() | event.key())
                            if sequence == event_sequence:
                                event.accept()
                                return True

                    except KeyError:
                        pass

            # Special handling for propertyTableView with playToggle shortcut
            # Let SPACE propagate to the property table for dropdown/edit activation
            elif self.propertyTableView.hasFocus() and event.key() == get_app().window.getShortcutByName("playToggle"):
                return False

        # Allow all other events to propagate normally
        return super(MainWindow, self).eventFilter(obj, event)

    def _close_dock_tab_from_middle_click(self, tab_bar, event):
        """Close a dock when its tabified dock tab is middle-clicked."""
        tab_index = tab_bar.tabAt(event.pos())
        if tab_index < 0:
            return False

        tabified_docks = [
            dock
            for dock in self.getDocks()
            if dock.isVisible() and self.tabifiedDockWidgets(dock)
        ]
        if not tabified_docks:
            return False

        tab_title = tab_bar.tabText(tab_index)
        tab_titles = {tab_bar.tabText(index) for index in range(tab_bar.count())}
        dock_titles = {dock.windowTitle() for dock in tabified_docks}
        if len(tab_titles & dock_titles) < 2:
            return False

        for dock in tabified_docks:
            if (dock.windowTitle() == tab_title
                    and dock.objectName() != "dockTutorial"
                    and dock.features() & QDockWidget.DockWidgetClosable):
                dock.close()
                event.accept()
                return True
        return False

    def _blocks_timeline_shortcuts(self, widget):
        """Return True when focus should block timeline shortcuts like seek/play."""
        if widget is None:
            return False

        if hasattr(self, "propertyTableView") and self.propertyTableView:
            if widget is self.propertyTableView or self.propertyTableView.isAncestorOf(widget):
                return False

        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
            return True

        if isinstance(widget, (QAbstractButton, QTabBar)):
            return True

        menubar = self.menuBar()
        if menubar and (widget is menubar or menubar.isAncestorOf(widget)):
            return True

        toolbars = [
            getattr(self, "toolBar", None),
            getattr(self, "timelineToolbar", None),
            getattr(self, "videoToolbar", None),
            getattr(self, "filesToolbar", None),
            getattr(self, "transitionsToolbar", None),
            getattr(self, "effectsToolbar", None),
            getattr(self, "emojisToolbar", None),
            getattr(self, "captionToolbar", None),
        ]
        for toolbar in toolbars:
            if toolbar and toolbar.isAncestorOf(widget):
                return True

        return False

    def ignore_updates_callback(self, ignore, show_wait=True):
        """Ignore updates callback - used to stop updating this widget during batch updates"""
        if ignore and not self.ignore_updates:
            if show_wait:
                self._acquire_wait_cursor()
            openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
            get_app().processEvents()
        elif not ignore and self.ignore_updates:
            if show_wait:
                self._release_wait_cursor()
            openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

        if not ignore:
            if getattr(self, "_trim_refresh_pending", False):
                self.ignore_updates = ignore
                return
            self.refreshFrameSignal.emit()
            self.propertyTableView.select_frame(self.preview_thread.player.Position())

        # Keep track of ignore / not ignore
        self.ignore_updates = ignore

    def _acquire_wait_cursor(self):
        """Push a wait cursor request on the GUI thread."""
        app = get_app()
        app.setOverrideCursor(QCursor(Qt.WaitCursor))
        self._wait_cursor_requests += 1

    def _release_wait_cursor(self):
        """Release a wait cursor request on the GUI thread."""
        app = get_app()
        if self._wait_cursor_requests:
            if app.overrideCursor():
                app.restoreOverrideCursor()
            self._wait_cursor_requests -= 1
            return
        if app.overrideCursor():
            app.restoreOverrideCursor()

    def handle_wait_cursor_signal(self, enabled):
        """Handle cross-thread wait cursor requests safely on the GUI thread."""
        if enabled:
            self._acquire_wait_cursor()
        else:
            self._release_wait_cursor()

    def style_dock_widgets(self, theme_changed=False):
        """Check if any dock widget is part of a tabbed group and hide the title text if tabbed."""
        theme = None
        if get_app().theme_manager:
            theme = get_app().theme_manager.get_current_theme()

        if theme_changed:
            # Theme switch invalidates all cached states so every dock gets re-styled.
            for dw in self.getDocks():
                dw._titlebar_state = None

        for dock_widget in self.getDocks():
            # Only count visible tabified siblings — hidden docks in the same group
            # would otherwise make a lone visible dock appear "tabbed".
            tabified_widgets = [w for w in self.tabifiedDockWidgets(dock_widget) if w.isVisible()]

            # Compute the required title-bar state key. setTitleBarWidget internally
            # calls QWidget::setParent → reparentFocusWidgets, which iterates the
            # entire Qt focus chain. When dockLocationChanged fires repeatedly during
            # a drag this becomes O(n²) and freezes the UI. Skip the call when the
            # state hasn't actually changed.
            feature_state = ":".join([
                "close" if dock_widget.features() & QDockWidget.DockWidgetClosable else "no-close",
                "float" if dock_widget.features() & QDockWidget.DockWidgetFloatable else "no-float",
            ])
            show_titlebar_buttons = bool(
                dock_widget.features() & (
                    QDockWidget.DockWidgetClosable
                    | QDockWidget.DockWidgetFloatable))
            if dock_widget.objectName() == "dockTimeline":
                required_state = "timeline"
            elif theme and theme.name == ThemeName.COSMIC.value:
                if tabified_widgets:
                    required_state = f"tabbed:{feature_state}"
                elif dock_widget.isFloating():
                    required_state = "floating"
                else:
                    required_state = f"docked:{dock_widget.windowTitle()}:{feature_state}"
            else:
                required_state = "system"

            if getattr(dock_widget, "_titlebar_state", None) == required_state:
                continue

            dock_widget._titlebar_state = required_state

            if required_state == "timeline":
                dock_widget.setTitleBarWidget(QWidget())
            elif required_state.startswith("tabbed:"):
                dock_widget.setTitleBarWidget(
                    HiddenTitleBar(dock_widget, "", show_buttons=show_titlebar_buttons))
            elif required_state == "floating" or required_state == "system":
                dock_widget.setTitleBarWidget(None)
            else:  # "docked:<title>"
                dock_widget.setTitleBarWidget(
                    HiddenTitleBar(
                        dock_widget, dock_widget.windowTitle(),
                        show_buttons=show_titlebar_buttons))

        # Set tab drawBase property
        self.set_tab_drawbase()

    def _schedule_dock_style_update(self, *_args, theme_changed=False, delay=150):
        """Defer dock titlebar restyling until dock/layout churn has settled."""
        if not hasattr(self, "_dock_style_timer"):
            self._dock_style_timer = QTimer(self)
            self._dock_style_timer.setSingleShot(True)
            self._dock_style_timer.timeout.connect(self._apply_scheduled_dock_style_update)
            self._dock_style_theme_changed = False
        if theme_changed:
            self._dock_style_theme_changed = True
        self._dock_style_timer.start(delay)

    def _on_dock_top_level_changed(self, floating=None, *_args):
        """Handle dock float/dock transitions.

        Floating docks need their title bar state corrected as soon as they
        detach. Broader dock restyling is deferred until the mouse is released:
        setTitleBarWidget() reparents widgets, and doing that while Qt is in a
        native dock drag can interrupt the drag on Windows.
        """
        self._mark_dock_interaction_active()
        if bool(floating):
            sender = getattr(self, "sender", None)
            dock = sender() if sender else None
            if dock and dock.objectName() != "dockTimeline":
                dock._titlebar_state = "floating"
                dock.setTitleBarWidget(None)
        self._schedule_dock_style_update(delay=0)

    def _apply_scheduled_dock_style_update(self):
        if QApplication.mouseButtons() & Qt.LeftButton:
            self._dock_style_timer.start(50)
            return
        theme_changed = bool(getattr(self, "_dock_style_theme_changed", False))
        self._dock_style_theme_changed = False
        self.style_dock_widgets(theme_changed=theme_changed)

    def _mark_dock_interaction_active(self, *_args):
        """Suppress expensive preview/cache churn while docks are being rearranged."""
        self._dock_interaction_active = True
        if not hasattr(self, "_dock_interaction_timer"):
            self._dock_interaction_timer = QTimer(self)
            self._dock_interaction_timer.setSingleShot(True)
            self._dock_interaction_timer.timeout.connect(self._finish_dock_interaction)
        self._dock_interaction_timer.start(250)

    def _finish_dock_interaction(self):
        self._dock_interaction_active = False
        pending_size = getattr(self, "_pending_preview_size", None)
        self._pending_preview_size = None
        if pending_size is not None:
            self.MaxSizeChanged.emit(pending_size)

    def _finish_pending_preview_resize(self):
        """Apply a preview resize deferred until the main window is initialized."""
        if getattr(self, "shutting_down", False):
            self._pending_preview_size = None
            return
        if not getattr(self, "initialized", False):
            QTimer.singleShot(50, self._finish_pending_preview_resize)
            return
        pending_size = getattr(self, "_pending_preview_size", None)
        self._pending_preview_size = None
        if pending_size is not None:
            self.MaxSizeChanged.emit(pending_size)

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
                if not tab_bar.property("_openshot_middle_click_filter"):
                    tab_bar.installEventFilter(self)
                    tab_bar.setProperty("_openshot_middle_click_filter", True)
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
        self.ui_trace_recorder = None
        self.last_auto_save_data_version = -1
        self._project_loading = False
        self._pending_project_open_refresh = False
        self._pending_preview_size = None

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
        self.actionFullscreen.setText(_("Fullscreen"))
        self.actionColor_Grade_View.setText(_("Color View"))

        # Init UI
        ui_util.init_ui(self)

        # Create dock toolbars, set initial state of items, etc
        self.setup_toolbars()
        self.generation_service = GenerationService(self)
        self.proxy_service = ProxyService(self)
        self.generation_queue = GenerationQueueManager(self)
        self.generation_queue.job_finished.connect(self._on_generation_job_finished)
        self._init_generation_actions()
        self._init_proxy_actions()
        self.refresh_comfy_availability_async()

        # Add window as watcher to receive undo/redo status updates
        app.updates.add_watcher(self)

        # Get current version of OpenShot via HTTP
        self.FoundVersionSignal.connect(self.foundCurrentVersion)
        get_current_Version()

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
            log.info(f"Quiting OpenShot due to failed local HTTP thumbnail server: {ex}")
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
        self.frameWeb.addWidget(self.timeline)
        self.frameWeb.setStretch(0, 0)
        self.frameWeb.setStretch(1, 1)
        self.timeline.show()

        # Configure the side docks to full-height
        self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        self.initModels()

        # Create individual scope docks (before addViewDocksMenu so they appear in Docks menu)
        self.waveform_content = WaveformDockContent()
        self.waveform_content.scopeRegionToggled.connect(self._on_scope_region_toggled)
        self.waveform_content.renderSettingsChanged.connect(self._request_scope_refresh)
        self.dockLumaWaveform = QDockWidget(_("Luma Waveform"), self)
        self.dockLumaWaveform.setObjectName("dockLumaWaveform")
        self.dockLumaWaveform.setProperty("_skip_auto_tab_order", True)
        self.dockLumaWaveform.setFocusPolicy(Qt.NoFocus)
        self.dockLumaWaveform.setWidget(self.waveform_content)
        self.dockLumaWaveform.hide()
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockLumaWaveform)

        self.histogram_content = HistogramDockContent()
        self.histogram_content.scopeRegionToggled.connect(self._on_scope_region_toggled)
        self.dockHistogram = QDockWidget(_("Histogram"), self)
        self.dockHistogram.setObjectName("dockHistogram")
        self.dockHistogram.setProperty("_skip_auto_tab_order", True)
        self.dockHistogram.setFocusPolicy(Qt.NoFocus)
        self.dockHistogram.setWidget(self.histogram_content)
        self.dockHistogram.hide()
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockHistogram)

        self.vectorscope_content = VectorscopeDockContent()
        self.vectorscope_content.scopeRegionToggled.connect(self._on_scope_region_toggled)
        self.vectorscope_content.renderSettingsChanged.connect(self._request_scope_refresh)
        self.dockVectorscope = QDockWidget(_("Vectorscope"), self)
        self.dockVectorscope.setObjectName("dockVectorscope")
        self.dockVectorscope.setProperty("_skip_auto_tab_order", True)
        self.dockVectorscope.setFocusPolicy(Qt.NoFocus)
        self.dockVectorscope.setWidget(self.vectorscope_content)
        self.dockVectorscope.hide()
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockVectorscope)

        self.audio_meter = AudioMeterWidget()
        self.dockAudio = QDockWidget(_("Audio Levels"), self)
        self.dockAudio.setObjectName("dockAudio")
        self.dockAudio.setProperty("_skip_auto_tab_order", True)
        self.dockAudio.setFocusPolicy(Qt.NoFocus)
        self.dockAudio.setWidget(self.audio_meter)
        self.dockAudio.hide()
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockAudio)

        self.audio_recording_content = None
        self.dockAudioRecording = QDockWidget(_("Recording"), self)
        self.dockAudioRecording.setObjectName("dockAudioRecording")
        self.dockAudioRecording.setProperty("_skip_auto_tab_order", True)
        self.dockAudioRecording.setFocusPolicy(Qt.NoFocus)
        self.dockAudioRecording.setMinimumWidth(RECORDING_DOCK_MIN_WIDTH)
        self.dockAudioRecording.hide()
        self.addDockWidget(Qt.RightDockWidgetArea, self.dockAudioRecording)

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
        self.propertyTableView.setTabKeyNavigation(False)
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
        self.videoPreview = VideoWidget(self.dockVideoContents)
        self.videoPreview.setObjectName("videoPreview")
        self.videoPreview.regionRectChanged.connect(self._on_scope_region_changed)
        self.videoPreview.scopeRegionCancelled.connect(self._clear_scope_region_mode)
        self.tabVideo.insertWidget(0, self.videoPreview)
        self.videoPreview.show()

        # Load window state and geometry
        self.saved_state = None
        self.saved_geometry = None
        self.saved_video_dock_width = None
        self._restored_saved_window = False
        self.load_settings()

        # Setup Cache settings
        self.cache_object = None
        self.InitCacheSettings()

        # Start the preview thread
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.timeline_sync.timeline, self.videoPreview)
        self.preview_thread = self.preview_parent.worker
        self.sliderZoomWidget.connect_playback()
        self.timeline.connect_playback()

        # Scope analysis: debounced timer dispatches GetFrame+FrameScope to the
        # PlayerWorker thread so the UI thread only handles paint/update work.
        self._scope_pending_frame = None
        self._scope_wf_vis = self._scope_hist_vis = self._scope_vec_vis = self._scope_aud_vis = False
        self._scope_region_enabled = False
        self._dock_interaction_active = False
        self._pending_preview_size = None
        self._scope_timer = QTimer(self)
        self._scope_timer.setSingleShot(True)
        self._scope_timer.setInterval(0)   # latest-wins worker path handles stale frame dropping
        self._scope_timer.timeout.connect(self._run_scope_analysis)
        self.preview_thread.position_changed.connect(self._on_scope_frame)
        self.SeekSignal.connect(self._on_scope_seek)

        # Playback mode: re-enable caching on any seek or play action
        self.SeekSignal.connect(self._enter_playback_mode)
        self.PlaySignal.connect(self._enter_playback_mode_play)

        # Set play/pause callbacks
        self.PauseSignal.connect(self.onPauseCallback)
        self.PlaySignal.connect(self.onPlayCallback)
        self.TrimPreviewMode.connect(self.onTrimPreviewMode)

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

        # Apply user overrides when present, otherwise use runtime-detected libopenshot defaults.
        omp_default = lib_settings.DefaultOMPThreads()
        ff_default = lib_settings.DefaultFFThreads()
        omp_min, omp_max = 2, max(2, omp_default * 3)
        ff_min, ff_max = 2, max(2, ff_default * 3)

        omp_source = "libopenshot default"
        if s.has_user_value("omp_threads_number"):
            omp_value = int(str(s.get("omp_threads_number")))
            lib_settings.OMP_THREADS = max(omp_min, min(omp_value, omp_max))
            omp_source = "user setting"
        else:
            lib_settings.OMP_THREADS = omp_default
        lib_settings.ApplyOpenMPSettings()
        log.info("Initialized OMP threads to %s (%s)", lib_settings.OMP_THREADS, omp_source)

        ff_source = "libopenshot default"
        if s.has_user_value("ff_threads_number"):
            ff_value = int(str(s.get("ff_threads_number")))
            lib_settings.FF_THREADS = max(ff_min, min(ff_value, ff_max))
            ff_source = "user setting"
        else:
            lib_settings.FF_THREADS = ff_default
        log.info("Initialized FFmpeg threads to %s (%s)", lib_settings.FF_THREADS, ff_source)

        # Create lock file
        self.create_lock_file()

        # Connect OpenProject Signal
        self.OpenProjectSignal.connect(self.open_project)

        # Connect Selection signals
        self.SelectionAdded.connect(self.addSelection)
        self.SelectionRemoved.connect(self.removeSelection)
        self.SelectionAdded.connect(self._clear_scope_region_on_selection)
        self._init_ui_trace_recorder()

        # Connect 'ignore update' signal
        self.ignore_updates = False
        self._wait_cursor_requests = 0
        self.IgnoreUpdates.connect(self.ignore_updates_callback)
        self.WaitCursorSignal.connect(self.handle_wait_cursor_signal)

        # Connect playhead moved signals
        self.SeekSignal.connect(self.handleSeek)

        # Connect theme changed signal
        self.ThemeChangedSignal.connect(lambda _=None: self._schedule_dock_style_update(theme_changed=True))
        self.ProjectSaved.connect(self._on_project_saved, Qt.QueuedConnection)
        self.ProjectSaveFailed.connect(self._on_project_save_failed, Qt.QueuedConnection)

        # Connect the signals for each dock widget from self.getDocks()
        for dock_widget in self.getDocks():
            dock_widget.dockLocationChanged.connect(self._schedule_dock_style_update)
            dock_widget.dockLocationChanged.connect(self._mark_dock_interaction_active)
            dock_widget.topLevelChanged.connect(self._on_dock_top_level_changed)
            # Re-style siblings when any dock is shown/hidden (tab group may shrink to 1)
            dock_widget.visibilityChanged.connect(self._schedule_dock_style_update)

        # Re-anchor scope docks when manually enabled after a view switch removed them
        for _dock in [self.dockLumaWaveform, self.dockHistogram, self.dockVectorscope, self.dockAudio]:
            _dock.toggleViewAction().triggered.connect(
                functools.partial(self._on_scope_dock_toggled, dock=_dock))
        for _dock in [self.dockLumaWaveform, self.dockHistogram, self.dockVectorscope]:
            _dock.visibilityChanged.connect(self._on_video_scope_visibility_changed)
        self.dockProperties.toggleViewAction().triggered.connect(self._on_properties_dock_toggled)
        self.dockAudioRecording.visibilityChanged.connect(self._on_audio_recording_visibility_changed)
        if self.dockAudioRecording.isVisible():
            self._ensure_audio_recording_dock_content()

        # Create tutorial manager
        self.tutorial_manager = TutorialManager(self)

        # Apply theme
        theme_name = s.get("theme")
        theme = get_app().theme_manager.apply_theme(theme_name)
        s.set("theme", theme.name)

        # Restore only the outer geometry before mapping. Dock state is applied
        # after the window manager has established the final window size.
        self._restore_saved_geometry_before_show()

        # Save settings
        s.save()

        # Refresh frame
        QTimer.singleShot(100, lambda: self.refreshFrameSignal.emit())

        # Main window is initialized
        self.initialized = True

        # Init all Keyboard shortcuts
        self.initShortcuts()

        # Apply accessibility-friendly tab order after layout settles
        QTimer.singleShot(
            0,
            lambda: tabstops.apply_auto_tab_order(
                self, include_hidden=True, include_disabled=True
            ),
        )
        self._schedule_initial_focus()
        self._install_focus_debugger()

    def _init_ui_trace_recorder(self):
        """Enable env-configured UI trace recording for automated test capture."""
        try:
            from classes.ui_trace_recorder import UiTraceRecorder
            recorder = UiTraceRecorder(self)
            if recorder.enabled:
                self.ui_trace_recorder = recorder
        except Exception:
            log.error("Failed to initialize UI trace recorder", exc_info=1)

    def _schedule_initial_focus(self):
        QTimer.singleShot(0, self._set_initial_focus)

    def _set_initial_focus(self):
        button = None
        if getattr(self, "toolBar", None):
            button = self.toolBar.widgetForAction(getattr(self, "actionNew", None))
        if button:
            button.setFocus(Qt.TabFocusReason)

    def _install_focus_debugger(self):
        if not os.environ.get("OPENSHOT_DEBUG_FOCUS"):
            return
        if hasattr(self, "_focus_debug_installed") and self._focus_debug_installed:
            return
        self._focus_debug_installed = True
        qapp = get_app()
        qapp.focusChanged.connect(self._log_focus_change)
        self._log_tab_chain()

    def _log_focus_change(self, old, new):
        def _describe(widget):
            if widget is None:
                return "None"
            name = widget.objectName() or widget.__class__.__name__
            cls_name = widget.__class__.__name__
            focus_policy = widget.focusPolicy()
            dock = getattr(tabstops, "_parent_dock_widget", lambda w: None)(widget)
            dock_name = dock.objectName() if dock else ""
            dock_title = dock.windowTitle() if dock else ""
            dock_visible = ""
            dock_content_visible = ""
            if dock:
                dock_visible = f"dockVisible={dock.isVisible()}"
                content = dock.widget()
                if content:
                    dock_content_visible = f"contentVisible={content.isVisible()}"
            parts = [name, f"class={cls_name}", f"policy={int(focus_policy)}"]
            if dock_name:
                parts.append(f"dock={dock_name}")
            if dock_title:
                parts.append(f"title={dock_title}")
            if dock_visible:
                parts.append(dock_visible)
            if dock_content_visible:
                parts.append(dock_content_visible)
            return " ".join(parts)

        log.info("Focus changed: %s -> %s", _describe(old), _describe(new))

    def _log_tab_chain(self):
        chain = []
        root = self
        for widget in self.findChildren(QWidget):
            if widget.focusPolicy() == Qt.NoFocus:
                continue
            if not widget.isVisibleTo(root):
                continue
            chain.append(widget)
        chain.sort(key=lambda w: getattr(w, "_tab_order_key", (0, 0, 0, 0)))
        log.info("Tab chain (debug): %s", " | ".join(
            [w.objectName() or w.__class__.__name__ for w in chain]
        ))
