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
import sys
import platform
import shutil
import webbrowser
from operator import itemgetter
from uuid import uuid4
from copy import deepcopy
from time import sleep, time

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QCursor, QKeySequence
from PyQt5.QtWidgets import *
import openshot  # Python module for libopenshot (required video editing module installed separately)

from windows.views.timeline_webview import TimelineWebView
from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.timeline import TimelineSync
from classes.query import File, Clip, Transition, Marker, Track
from classes.metrics import *
from classes.version import *
from classes.conversion import zoomToSeconds, secondsToZoom
from classes.thumbnail import httpThumbnailServerThread
from images import openshot_rc
from windows.views.files_treeview import FilesTreeView
from windows.views.files_listview import FilesListView
from windows.views.transitions_treeview import TransitionsTreeView
from windows.views.transitions_listview import TransitionsListView
from windows.views.effects_treeview import EffectsTreeView
from windows.views.effects_listview import EffectsListView
from windows.views.properties_tableview import PropertiesTableView, SelectionLabel
from windows.views.tutorial import TutorialManager
from windows.video_widget import VideoWidget
from windows.preview_thread import PreviewParent
from classes.exporters.edl import export_edl
from classes.exporters.final_cut_pro import export_xml
from classes.importers.edl import import_edl
from classes.importers.final_cut_pro import import_xml


class MainWindow(QMainWindow, updates.UpdateWatcher):
    """ This class contains the logic for the main window widget """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'main-window.ui')

    previewFrameSignal = pyqtSignal(int)
    refreshFrameSignal = pyqtSignal()
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
    ExportStarted = pyqtSignal(str, int, int)
    ExportFrame = pyqtSignal(str, int, int, int)
    ExportEnded = pyqtSignal(str)
    MaxSizeChanged = pyqtSignal(object)
    InsertKeyframe = pyqtSignal(object)
    OpenProjectSignal = pyqtSignal(str)
    ThumbnailUpdated = pyqtSignal(str)

    # Docks are closable, movable and floatable
    docks_frozen = False

    # Save window settings on close
    def closeEvent(self, event):

        app = get_app()
        # Some window managers handels dragging of the modal messages incorrectly if other windows are open
        # Hide tutorial window first
        self.tutorial_manager.hide_dialog()

        # Prompt user to save (if needed)
        if app.project.needs_save() and not self.mode == "unittest":
            log.info('Prompt user to save project')
            # Translate object
            _ = app._tr

            # Handle exception
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project before closing?"), QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger(event)
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

        # Process any queued events
        QCoreApplication.processEvents()

        # Stop preview thread (and wait for it to end)
        self.preview_thread.player.CloseAudioDevice()
        self.preview_thread.kill()
        self.preview_parent.background.exit()
        self.preview_parent.background.wait(5000)

        # Shut down the webview
        self.timeline.close()

        # Close Timeline
        self.timeline_sync.timeline.Close()
        self.timeline_sync.timeline = None

        # Close & Stop libopenshot logger
        openshot.ZmqLogger.Instance().Close()
        app.logger_libopenshot.kill()
        self.http_server_thread.kill()

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
        lock_value = str(uuid4())

        # Check if it already exists
        if os.path.exists(lock_path):
            # Walk the libopenshot log (if found), and try and find last line before this launch
            log_path = os.path.join(info.USER_PATH, "libopenshot.log")
            last_log_line = ""
            last_stack_trace = ""
            found_stack = False
            log_start_counter = 0
            if os.path.exists(log_path):
                with open(log_path, "rb") as f:
                    # Read from bottom up
                    for raw_line in reversed(self.tail_file(f, 500)):
                        line = str(raw_line, 'utf-8')
                        # Detect stack trace
                        if "End of Stack Trace" in line:
                            found_stack = True
                            continue
                        elif "Unhandled Exception: Stack Trace" in line:
                            found_stack = False
                            continue
                        elif "libopenshot logging:" in line:
                            log_start_counter += 1
                            if log_start_counter > 1:
                                # Found the previous log start, too old now
                                break

                        if found_stack:
                            # Append line to beginning of stacktrace
                            last_stack_trace = line + last_stack_trace

                        # Ignore certain useless lines
                        if line.strip() and "---" not in line and "libopenshot logging:" not in line and not last_log_line:
                            last_log_line = line

            # Split last stack trace (if any)
            if last_stack_trace:
                # Get top line of stack trace (for metrics)
                last_log_line = last_stack_trace.split("\n")[0].strip()

                # Send stacktrace for debugging (if send metrics is enabled)
                track_exception_stacktrace(last_stack_trace, "libopenshot")

            # Clear / normalize log line (so we can roll them up in the analytics)
            if last_log_line:
                # Format last log line based on OS (since each OS can be formatted differently)
                if platform.system() == "Darwin":
                    last_log_line = "mac-%s" % last_log_line[58:].strip()
                elif platform.system() == "Windows":
                    last_log_line = "windows-%s" % last_log_line
                elif platform.system() == "Linux":
                    last_log_line = "linux-%s" % last_log_line.replace("/usr/local/lib/", "")

                # Remove '()' from line, and split. Trying to grab the beginning of the log line.
                last_log_line = last_log_line.replace("()", "")
                log_parts = last_log_line.split("(")
                if len(log_parts) == 2:
                    last_log_line = "-%s" % log_parts[0].replace("logger_libopenshot:INFO ", "").strip()[:64]
                elif len(log_parts) >= 3:
                    last_log_line = "-%s (%s" % (log_parts[0].replace("logger_libopenshot:INFO ", "").strip()[:64], log_parts[1])
            else:
                last_log_line = ""

            # Throw exception (with last libopenshot line... if found)
            log.error("Unhandled crash detected... will attempt to recover backup project: %s" % info.BACKUP_FILE)
            track_metric_error("unhandled-crash%s" % last_log_line, True)

            # Remove file
            self.destroy_lock_file()

        else:
            # Normal startup, clear thumbnails
            self.clear_all_thumbnails()

        # Write lock file (try a few times if failure)
        attempts = 5
        while attempts > 0:
            try:
                # Create lock file
                with open(lock_path, 'w') as f:
                    f.write(lock_value)
                break
            except Exception:
                attempts -= 1
                sleep(0.25)

    def destroy_lock_file(self):
        """Destroy the lock file"""
        lock_path = os.path.join(info.USER_PATH, ".lock")

        # Remove file (try a few times if failure)
        attempts = 5
        while attempts > 0:
            try:
                os.remove(lock_path)
                break
            except Exception:
                attempts -= 1
                sleep(0.25)

    def tail_file(self, f, n, offset=None):
        """Read the end of a file (n number of lines)"""
        avg_line_length = 90
        to_read = n + (offset or 0)

        while True:
            try:
                # Seek to byte position
                f.seek(-(avg_line_length * to_read), 2)
            except IOError:
                # Byte position not found
                f.seek(0)
            pos = f.tell()
            lines = f.read().splitlines()
            if len(lines) >= to_read or pos == 0:
                # Return the lines
                return lines[-to_read:offset and -offset or None]
            avg_line_length *= 2

    def actionNew_trigger(self, event):

        app = get_app()
        _ = app._tr  # Get translation function

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project first?"), QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger(event)
            elif ret == QMessageBox.Cancel:
                # User canceled prompt
                return

        # Clear any previous thumbnails
        self.clear_all_thumbnails()

        # clear data and start new project
        app.project.load("")
        app.updates.reset()
        self.updateStatusChanged(False, False)

        # Reset selections
        self.clearSelections()

        self.filesTreeView.refresh_view()
        log.info("New Project created.")

        # Set Window title
        self.SetWindowTitle()

        # Seek to frame 0
        self.SeekSignal.emit(1)

    def actionAnimatedTitle_trigger(self, event):
        # show dialog
        from windows.animated_title import AnimatedTitle
        win = AnimatedTitle()
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('animated title add confirmed')
        else:
            log.info('animated title add cancelled')

    def actionAnimation_trigger(self, event):
        # show dialog
        from windows.animation import Animation
        win = Animation()
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('animation confirmed')
        else:
            log.info('animation cancelled')

    def actionTitle_trigger(self, event):
        # show dialog
        from windows.title_editor import TitleEditor
        win = TitleEditor()
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('title editor add confirmed')
        else:
            log.info('title editor add cancelled')

    def actionEditTitle_trigger(self, event):

        # Get selected svg title file
        selected_file_id = self.selected_files[0]
        file = File.get(id=selected_file_id)
        file_path = file.data.get("path")

        # Delete thumbnail for this file (it will be recreated soon)
        thumb_path = os.path.join(info.THUMBNAIL_PATH, "{}.png".format(file.id))

        # Check if thumb exists (and delete it)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

        # show dialog for editing title
        from windows.title_editor import TitleEditor
        win = TitleEditor(file_path)
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()

        # Force update of files model (which will rebuild missing thumbnails)
        get_app().window.filesTreeView.refresh_view()

        # Force update of clips
        clips = Clip.filter(file_id=selected_file_id)
        for c in clips:
            # update clip
            c.data["reader"]["path"] = file_path
            c.save()

            # Emit thumbnail update signal (to update timeline thumb image)
            self.ThumbnailUpdated.emit(c.id)

    def actionDuplicateTitle_trigger(self, event):

        # Get selected svg title file
        selected_file_id = self.selected_files[0]
        file = File.get(id=selected_file_id)
        file_path = file.data.get("path")

        # show dialog for editing title
        from windows.title_editor import TitleEditor
        win = TitleEditor(file_path, duplicate=True)
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()

    def actionImportImageSequence_trigger(self, event):
        # show dialog
        from windows.Import_image_seq import ImportImageSeq
        win = ImportImageSeq()
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Import image sequence add confirmed')
        else:
            log.info('Import image sequence add cancelled')

    def actionClearHistory_trigger(self, event):
        """Clear history for current project"""
        get_app().updates.reset()
        log.info('History cleared')

    def save_project(self, file_path):
        """ Save a project to a file path, and refresh the screen """
        app = get_app()
        _ = app._tr  # Get translation function

        try:
            # Update history in project data
            s = settings.get_settings()
            app.updates.save_history(app.project, s.get("history-limit"))

            # Save project to file
            app.project.save(file_path)

            # Set Window title
            self.SetWindowTitle()

            # Load recent projects again
            self.load_recent_menu()

            log.info("Saved project {}".format(file_path))

        except Exception as ex:
            log.error("Couldn't save project %s. %s" % (file_path, str(ex)))
            QMessageBox.warning(self, _("Error Saving Project"), str(ex))

    def open_project(self, file_path, clear_thumbnails=True):
        """ Open a project from a file path, and refresh the screen """

        app = get_app()
        _ = app._tr  # Get translation function

        # First check for empty file_path (probably user cancellation)
        if not file_path:
            # Ignore the request
            return

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project first?"), QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
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
                    self.clear_all_thumbnails()

                # Load project file
                app.project.load(file_path, clear_thumbnails)

                # Set Window title
                self.SetWindowTitle()

                # Reset undo/redo history
                app.updates.reset()
                app.updates.load_history(app.project)

                # Reset selections
                self.clearSelections()

                # Refresh file tree
                QTimer.singleShot(0, self.filesTreeView.refresh_view)

                # Load recent projects again
                self.load_recent_menu()

                log.info("Loaded project {}".format(file_path))
            else:
                # Prepare to use status bar
                self.statusBar = QStatusBar()
                self.setStatusBar(self.statusBar)

                log.info("File not found at {}".format(file_path))
                self.statusBar.showMessage(_("Project {} is missing (it may have been moved or deleted). It has been removed from the Recent Projects menu.".format(file_path)), 5000)
                self.remove_recent_project(file_path)
                self.load_recent_menu()

        except Exception as ex:
            log.error("Couldn't open project {}".format(file_path))
            QMessageBox.warning(self, _("Error Opening Project"), str(ex))

        # Restore normal cursor
        app.restoreOverrideCursor()

    def clear_all_thumbnails(self):
        """Clear all user thumbnails"""
        try:
            openshot_thumbnail_path = os.path.join(info.USER_PATH, "thumbnail")
            if os.path.exists(openshot_thumbnail_path):
                log.info("Clear all thumbnails: %s" % openshot_thumbnail_path)
                shutil.rmtree(openshot_thumbnail_path)
                os.mkdir(openshot_thumbnail_path)

            # Clear any blender animations
            openshot_blender_path = os.path.join(info.USER_PATH, "blender")
            if os.path.exists(openshot_blender_path):
                log.info("Clear all animations: %s" % openshot_blender_path)
                shutil.rmtree(openshot_blender_path)
                os.mkdir(openshot_blender_path)

            # Clear any title animations
            openshot_title_path = os.path.join(info.USER_PATH, "title")
            if os.path.exists(openshot_title_path):
                log.info("Clear all titles: %s" % openshot_title_path)
                shutil.rmtree(openshot_title_path)
                os.mkdir(openshot_title_path)

            # Clear any backups
            if os.path.exists(info.BACKUP_FILE):
                log.info("Clear backup: %s" % info.BACKUP_FILE)
                # Remove backup file
                os.unlink(info.BACKUP_FILE)

        except:
            log.info("Failed to clear thumbnails: %s" % info.THUMBNAIL_PATH)

    def actionOpen_trigger(self, event):
        app = get_app()
        _ = app._tr
        recommended_path = app.project.current_filepath
        if not recommended_path:
            recommended_path = info.HOME_PATH

        # Do we have unsaved changes?
        if app.project.needs_save():
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project first?"), QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger(event)
            elif ret == QMessageBox.Cancel:
                # User canceled prompt
                return

        # Prompt for open project file
        file_path = QFileDialog.getOpenFileName(self, _("Open Project..."), recommended_path, _("OpenShot Project (*.osp)"))[0]

        # Load project file
        self.OpenProjectSignal.emit(file_path)

    def actionSave_trigger(self, event):
        app = get_app()
        _ = app._tr

        # Get current filepath if any, otherwise ask user
        file_path = app.project.current_filepath
        if not file_path:
            recommended_path = os.path.join(info.HOME_PATH, "%s.osp" % _("Untitled Project"))
            file_path = QFileDialog.getSaveFileName(self, _("Save Project..."), recommended_path, _("OpenShot Project (*.osp)"))[0]

        if file_path:
            # Append .osp if needed
            if ".osp" not in file_path:
                file_path = "%s.osp" % file_path

            # Save project
            self.save_project(file_path)

    def auto_save_project(self):
        """Auto save the project"""
        app = get_app()
        s = settings.get_settings()

        # Get current filepath (if any)
        file_path = app.project.current_filepath
        if app.project.needs_save():
            log.info("auto_save_project")

            if file_path:
                # A Real project file exists
                # Append .osp if needed
                if ".osp" not in file_path:
                    file_path = "%s.osp" % file_path
                folder_path, file_name = os.path.split(file_path)
                file_name, file_ext = os.path.splitext(file_name)

                # Make copy of unsaved project file in 'recovery' folder
                recover_path_with_timestamp = os.path.join(info.RECOVERY_PATH, "%d-%s.osp" % (int(time()), file_name))
                shutil.copy(file_path, recover_path_with_timestamp)

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
                log.info("Auto save project file: %s" % file_path)
                self.save_project(file_path)

                # Remove backup.osp (if any)
                if os.path.exists(info.BACKUP_FILE):
                    # Delete backup.osp since we just saved the actual project
                    os.unlink(info.BACKUP_FILE)

            else:
                # No saved project found
                log.info("Creating backup of project file: %s" % info.BACKUP_FILE)
                app.project.save(info.BACKUP_FILE, move_temp_files=False, make_paths_relative=False)

                # Clear the file_path (which is set by saving the project)
                app.project.current_filepath = None
                app.project.has_unsaved_changes = True

    def actionSaveAs_trigger(self, event):
        app = get_app()
        _ = app._tr

        recommended_path = app.project.current_filepath
        if not recommended_path:
            recommended_path = os.path.join(info.HOME_PATH, "%s.osp" % _("Untitled Project"))
        file_path = QFileDialog.getSaveFileName(self, _("Save Project As..."), recommended_path, _("OpenShot Project (*.osp)"))[0]
        if file_path:
            # Append .osp if needed
            if ".osp" not in file_path:
                file_path = "%s.osp" % file_path

            # Save new project
            self.save_project(file_path)

    def actionImportFiles_trigger(self, event):
        app = get_app()
        _ = app._tr
        recommended_path = app.project.get("import_path")
        if not recommended_path or not os.path.exists(recommended_path):
            recommended_path = os.path.join(info.HOME_PATH)
        files = QFileDialog.getOpenFileNames(self, _("Import File..."), recommended_path)[0]
        for file_path in files:
            self.filesTreeView.add_file(file_path)
            self.filesTreeView.refresh_view()
            app.updates.update_untracked(["import_path"], os.path.dirname(file_path))
            log.info("Imported media file {}".format(file_path))

    def actionAdd_to_Timeline_trigger(self, event):
        # Loop through selected files
        f = None
        files = []
        for file_id in self.selected_files:
            # Find matching file
            files.append(File.get(id=file_id))

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

    def actionUploadVideo_trigger(self, event):
        # show window
        from windows.upload_video import UploadVideo
        win = UploadVideo()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Upload Video add confirmed')
        else:
            log.info('Upload Video add cancelled')

    def actionExportVideo_trigger(self, event):
        # show window
        from windows.export import Export
        win = Export()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Export Video add confirmed')
        else:
            log.info('Export Video add cancelled')

    def actionExportEDL_trigger(self, event):
        """Export EDL File"""
        export_edl()

    def actionExportFCPXML_trigger(self, event):
        """Export XML (Final Cut Pro) File"""
        export_xml()

    def actionImportEDL_trigger(self, event):
        """Import EDL File"""
        import_edl()

    def actionImportFCPXML_trigger(self, event):
        """Import XML (Final Cut Pro) File"""
        import_xml()

    def actionUndo_trigger(self, event):
        log.info('actionUndo_trigger')
        get_app().updates.undo()

        # Update the preview
        self.refreshFrameSignal.emit()

    def actionRedo_trigger(self, event):
        log.info('actionRedo_trigger')
        get_app().updates.redo()

        # Update the preview
        self.refreshFrameSignal.emit()

    def actionPreferences_trigger(self, event):
        # Stop preview thread
        self.SpeedSignal.emit(0)
        ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-start")
        self.actionPlay.setChecked(False)

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
        s = settings.get_settings()
        s.save()

        # Restore normal cursor
        get_app().restoreOverrideCursor()

    def actionFilesShowAll_trigger(self, event):
        self.filesTreeView.refresh_view()

    def actionFilesShowVideo_trigger(self, event):
        self.filesTreeView.refresh_view()

    def actionFilesShowAudio_trigger(self, event):
        self.filesTreeView.refresh_view()

    def actionFilesShowImage_trigger(self, event):
        self.filesTreeView.refresh_view()

    def actionTransitionsShowAll_trigger(self, event):
        self.transitionsTreeView.refresh_view()

    def actionTransitionsShowCommon_trigger(self, event):
        self.transitionsTreeView.refresh_view()

    def actionHelpContents_trigger(self, event):
        try:
            webbrowser.open("https://www.openshot.org/%suser-guide/?app-menu" % info.website_language(), new=1)
        except Exception as ex:
            QMessageBox.information(self, "Error !", "Unable to open the online help")
            log.error("Unable to open the Help Contents: {}".format(str(ex)))

    def actionAbout_trigger(self, event):
        """Show about dialog"""
        from windows.about import About
        win = About()
        # Run the dialog event loop - blocking interaction on this window during this time
        win.exec_()

    def actionReportBug_trigger(self, event):
        try:
            webbrowser.open("https://www.openshot.org/%sissues/new/?app-menu" % info.website_language(), new=1)
        except Exception as ex:
            QMessageBox.information(self, "Error !", "Unable to open the Bug Report GitHub Issues web page")
            log.error("Unable to open the Bug Report page: {}".format(str(ex)))

    def actionAskQuestion_trigger(self, event):
        try:
            webbrowser.open("https://www.reddit.com/r/OpenShot/", new=1)
        except Exception as ex:
            QMessageBox.information(self, "Error !", "Unable to open the official OpenShot subreddit web page")
            log.error("Unable to open the subreddit page: {}".format(str(ex)))

    def actionTranslate_trigger(self, event):
        try:
            webbrowser.open("https://translations.launchpad.net/openshot/2.0", new=1)
        except Exception as ex:
            QMessageBox.information(self, "Error !", "Unable to open the Translation web page")
            log.error("Unable to open the translation page: {}".format(str(ex)))

    def actionDonate_trigger(self, event):
        try:
            webbrowser.open("https://www.openshot.org/%sdonate/?app-menu" % info.website_language(), new=1)
        except Exception as ex:
            QMessageBox.information(self, "Error !", "Unable to open the Donate web page")
            log.error("Unable to open the donation page: {}".format(str(ex)))

    def actionUpdate_trigger(self, event):
        try:
            webbrowser.open("https://www.openshot.org/%sdownload/?app-toolbar" % info.website_language(), new=1)
        except Exception as ex:
            QMessageBox.information(self, "Error !", "Unable to open the Download web page")
            log.error("Unable to open the download page: {}".format(str(ex)))

    def actionPlay_trigger(self, event, force=None):

        # Determine max frame (based on clips)
        timeline_length = 0.0
        fps = get_app().window.timeline_sync.timeline.info.fps.ToFloat()
        clips = get_app().window.timeline_sync.timeline.Clips()
        for clip in clips:
            clip_last_frame = clip.Position() + clip.Duration()
            if clip_last_frame > timeline_length:
                # Set max length of timeline
                timeline_length = clip_last_frame

        # Convert to int and round
        timeline_length_int = round(timeline_length * fps) + 1

        if force == "pause":
            self.actionPlay.setChecked(False)
        elif force == "play":
            self.actionPlay.setChecked(True)

        if self.actionPlay.isChecked():
            ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
            self.PlaySignal.emit(timeline_length_int)

        else:
            ui_util.setup_icon(self, self.actionPlay, "actionPlay")  # to default
            self.PauseSignal.emit()

    def actionPreview_File_trigger(self, event):
        """ Preview the selected media file """
        log.info('actionPreview_File_trigger')

        # Loop through selected files (set 1 selected file if more than 1)
        f = None
        for file_id in self.selected_files:
            # Find matching file
            f = File.get(id=file_id)

        # Bail out if no file selected
        if not f:
            log.info(self.selected_files)
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

    def handlePausedVideo(self):
        """Handle the pause signal, by refreshing the properties dialog"""
        self.propertyTableView.select_frame(self.preview_thread.player.Position())

    def movePlayhead(self, position_frames):
        """Update playhead position"""
        # Notify preview thread
        self.timeline.movePlayhead(position_frames)

    def SetPlayheadFollow(self, enable_follow):
        """ Enable / Disable follow mode """
        self.timeline.SetPlayheadFollow(enable_follow)

    def actionFastForward_trigger(self, event):

        # Get the video player object
        player = self.preview_thread.player

        if player.Speed() + 1 != 0:
            self.SpeedSignal.emit(player.Speed() + 1)
        else:
            self.SpeedSignal.emit(player.Speed() + 2)

        if player.Mode() == openshot.PLAYBACK_PAUSED:
            self.actionPlay.trigger()

    def actionRewind_trigger(self, event):

        # Get the video player object
        player = self.preview_thread.player

        if player.Speed() - 1 != 0:
            self.SpeedSignal.emit(player.Speed() - 1)
        else:
            self.SpeedSignal.emit(player.Speed() - 2)

        if player.Mode() == openshot.PLAYBACK_PAUSED:
            self.actionPlay.trigger()

    def actionJumpStart_trigger(self, event):
        log.info("actionJumpStart_trigger")

        # Seek to the 1st frame
        self.SeekSignal.emit(1)

    def actionJumpEnd_trigger(self, event):
        log.info("actionJumpEnd_trigger")

        # Determine max frame (based on clips)
        timeline_length = 0.0
        fps = get_app().window.timeline_sync.timeline.info.fps.ToFloat()
        clips = get_app().window.timeline_sync.timeline.Clips()
        for clip in clips:
            clip_last_frame = clip.Position() + clip.Duration()
            if clip_last_frame > timeline_length:
                # Set max length of timeline
                timeline_length = clip_last_frame

        # Convert to int and round
        timeline_length_int = round(timeline_length * fps) + 1

        # Seek to the 1st frame
        self.SeekSignal.emit(timeline_length_int)

    def actionSaveFrame_trigger(self, event):
        log.info("actionSaveFrame_trigger")

        # Translate object
        app = get_app()
        _ = app._tr

        # Prepare to use the status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Determine path for saved frame - Default export path
        recommended_path = recommended_path = os.path.join(info.HOME_PATH)
        if app.project.current_filepath:
            recommended_path = os.path.dirname(app.project.current_filepath)

        # Determine path for saved frame - Project's export path
        if app.project.get("export_path"):
            recommended_path = app.project.get("export_path")

        framePath = "%s/Frame-%05d.png" % (recommended_path, self.preview_thread.current_frame)

        # Ask user to confirm or update framePath
        framePath = QFileDialog.getSaveFileName(self, _("Save Frame..."), framePath, _("Image files (*.png)"))[0]

        if not framePath:
            # No path specified (save frame cancelled)
            self.statusBar.showMessage(_("Save Frame cancelled..."), 5000)
            return

        # Append .png if needed
        if not framePath.endswith(".png"):
            framePath = "%s.png" % framePath

        app.updates.update(["export_path"], os.path.dirname(framePath))
        log.info("Saving frame to %s" % framePath)

        # Pause playback (to prevent crash since we are fixing to change the timeline's max size)
        app.window.actionPlay_trigger(None, force="pause")

        # Save current cache object and create a new CacheMemory object (ignore quality and scale prefs)
        old_cache_object = self.cache_object
        new_cache_object = openshot.CacheMemory(settings.get_settings().get("cache-limit-mb") * 1024 * 1024)
        self.timeline_sync.timeline.SetCache(new_cache_object)

        # Set MaxSize to full project resolution and clear preview cache so we get a full resolution frame
        self.timeline_sync.timeline.SetMaxSize(app.project.get("width"), app.project.get("height"))
        self.cache_object.Clear()

        # Check if file exists, if it does, get the lastModified time
        if os.path.exists(framePath):
            framePathTime = QFileInfo(framePath).lastModified()
        else:
            framePathTime = QDateTime()

        # Get and Save the frame (return is void, so we cannot check for success/fail here - must use file modification timestamp)
        openshot.Timeline.GetFrame(self.timeline_sync.timeline,self.preview_thread.current_frame).Save(framePath, 1.0)

        # Show message to user
        if os.path.exists(framePath) and (QFileInfo(framePath).lastModified() > framePathTime):
            self.statusBar.showMessage(_("Saved Frame to %s" % framePath), 5000)
        else:
            self.statusBar.showMessage( _("Failed to save image to %s" % framePath), 5000)

        # Reset the MaxSize to match the preview and reset the preview cache
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())
        self.timeline_sync.timeline.SetMaxSize(viewport_rect.width(), viewport_rect.height())
        self.cache_object.Clear()
        self.timeline_sync.timeline.SetCache(old_cache_object)
        self.cache_object = old_cache_object
        old_cache_object = None
        new_cache_object = None

    def actionAddTrack_trigger(self, event):
        log.info("actionAddTrack_trigger")

        # Get # of tracks
        all_tracks = get_app().project.get("layers")
        track_number = list(reversed(sorted(all_tracks, key=itemgetter('number'))))[0].get("number") + 1000000

        # Create new track above existing layer(s)
        track = Track()
        track.data = {"number": track_number, "y": 0, "label": "", "lock": False}
        track.save()

    def actionAddTrackAbove_trigger(self, event):
        log.info("actionAddTrackAbove_trigger")

        # Get # of tracks
        all_tracks = get_app().project.get("layers")
        selected_layer_id = self.selected_tracks[0]

        # Get selected track data
        existing_track = Track.get(id=selected_layer_id)
        if not existing_track:
            # Log error and fail silently
            log.error('No track object found with id: %s' % selected_layer_id)
            return
        selected_layer_number = int(existing_track.data["number"])

        # Get track above selected track (if any)
        previous_track_number = 0
        track_number_delta = 0
        for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
            if track.get("number") == selected_layer_number:
                track_number_delta = previous_track_number - selected_layer_number
                break
            previous_track_number = track.get("number")

        # Calculate new track number (based on gap delta)
        new_track_number = selected_layer_number + 1000000
        if track_number_delta > 2:
            # New track number (pick mid point in track number gap)
            new_track_number = selected_layer_number + int(round(track_number_delta / 2.0))
        else:
            # Loop through tracks above insert point
            for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                if track.get("number") > selected_layer_number:
                    existing_track = Track.get(number=track.get("number"))
                    if not existing_track:
                        # Log error and fail silently, and continue
                        log.error('No track object found with number: %s' % track.get("number"))
                        continue
                    existing_layer = existing_track.data["number"]
                    existing_track.data["number"] = existing_layer + 1000000
                    existing_track.save()

                    # Loop through clips and transitions for track, moving up to new layer
                    for clip in Clip.filter(layer=existing_layer):
                        clip.data["layer"] = int(clip.data["layer"]) + 1000000
                        clip.save()

                    for trans in Transition.filter(layer=existing_layer):
                        trans.data["layer"] = int(trans.data["layer"]) + 1000000
                        trans.save()

        # Create new track at vacated layer
        track = Track()
        track.data = {"number": new_track_number, "y": 0, "label": "", "lock": False}
        track.save()

    def actionAddTrackBelow_trigger(self, event):
        log.info("actionAddTrackBelow_trigger")

        # Get # of tracks
        all_tracks = get_app().project.get("layers")
        selected_layer_id = self.selected_tracks[0]

        # Get selected track data
        existing_track = Track.get(id=selected_layer_id)
        if not existing_track:
            # Log error and fail silently
            log.error('No track object found with id: %s' % selected_layer_id)
            return
        selected_layer_number = int(existing_track.data["number"])

        # Get track below selected track (if any)
        next_track_number = 0
        track_number_delta = 0
        found_track = False
        for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
            if found_track:
                next_track_number = track.get("number")
                track_number_delta = selected_layer_number - next_track_number
                break
            if track.get("number") == selected_layer_number:
                found_track = True
                continue

        # Calculate new track number (based on gap delta)
        new_track_number = selected_layer_number
        if track_number_delta > 2:
            # New track number (pick mid point in track number gap)
            new_track_number = selected_layer_number - int(round(track_number_delta / 2.0))
        else:
            # Loop through tracks from insert point and above
            for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                if track.get("number") >= selected_layer_number:
                    existing_track = Track.get(number=track.get("number"))
                    if not existing_track:
                        # Log error and fail silently, and continue
                        log.error('No track object found with number: %s' % track.get("number"))
                        continue
                    existing_layer = existing_track.data["number"]
                    existing_track.data["number"] = existing_layer + 1000000
                    existing_track.save()

                    # Loop through clips and transitions for track, moving up to new layer
                    for clip in Clip.filter(layer=existing_layer):
                        clip.data["layer"] = int(clip.data["layer"]) + 1000000
                        clip.save()

                    for trans in Transition.filter(layer=existing_layer):
                        trans.data["layer"] = int(trans.data["layer"]) + 1000000
                        trans.save()

        # Create new track at vacated layer
        track = Track()
        track.data = {"number": new_track_number, "y": 0, "label": "", "lock": False}
        track.save()

    def actionArrowTool_trigger(self, event):
        log.info("actionArrowTool_trigger")

    def actionSnappingTool_trigger(self, event):
        log.info("actionSnappingTool_trigger")
        log.info(self.actionSnappingTool.isChecked())

        # Enable / Disable snapping mode
        self.timeline.SetSnappingMode(self.actionSnappingTool.isChecked())

    def actionRazorTool_trigger(self, event):
        """Toggle razor tool on and off"""
        log.info('actionRazorTool_trigger')

        # Enable / Disable razor mode
        self.timeline.SetRazorMode(self.actionRazorTool.isChecked())

    def actionAddMarker_trigger(self, event):
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
        marker.data = {"position": position, "icon": "blue.png"}
        marker.save()

    def actionPreviousMarker_trigger(self, event):
        log.info("actionPreviousMarker_trigger")

        # Calculate current position (in seconds)
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = (self.preview_thread.current_frame - 1) / fps_float
        all_marker_positions = []

        # Get list of marker and important positions (like selected clip bounds)
        for marker in Marker.filter():
            all_marker_positions.append(marker.data["position"])

        # Loop through selected clips (and add key positions)
        for clip_id in self.selected_clips:
            # Get selected object
            selected_clip = Clip.get(id=clip_id)
            if selected_clip:
                all_marker_positions.append(selected_clip.data["position"])
                all_marker_positions.append(selected_clip.data["position"] + (selected_clip.data["end"] - selected_clip.data["start"]))

        # Loop through selected transitions (and add key positions)
        for tran_id in self.selected_transitions:
            # Get selected object
            selected_tran = Transition.get(id=tran_id)
            if selected_tran:
                all_marker_positions.append(selected_tran.data["position"])
                all_marker_positions.append(selected_tran.data["position"] + (selected_tran.data["end"] - selected_tran.data["start"]))

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
        if closest_position != None:
            # Seek
            frame_to_seek = round(closest_position * fps_float) + 1
            self.SeekSignal.emit(frame_to_seek)

            # Update the preview and reselct current frame in properties
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(frame_to_seek)

    def actionNextMarker_trigger(self, event):
        log.info("actionNextMarker_trigger")
        log.info(self.preview_thread.current_frame)

        # Calculate current position (in seconds)
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = (self.preview_thread.current_frame - 1) / fps_float
        all_marker_positions = []

        # Get list of marker and important positions (like selected clip bounds)
        for marker in Marker.filter():
            all_marker_positions.append(marker.data["position"])

        # Loop through selected clips (and add key positions)
        for clip_id in self.selected_clips:
            # Get selected object
            selected_clip = Clip.get(id=clip_id)
            if selected_clip:
                all_marker_positions.append(selected_clip.data["position"])
                all_marker_positions.append(selected_clip.data["position"] + (selected_clip.data["end"] - selected_clip.data["start"]))

        # Loop through selected transitions (and add key positions)
        for tran_id in self.selected_transitions:
            # Get selected object
            selected_tran = Transition.get(id=tran_id)
            if selected_tran:
                all_marker_positions.append(selected_tran.data["position"])
                all_marker_positions.append(selected_tran.data["position"] + (selected_tran.data["end"] - selected_tran.data["start"]))

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
        if closest_position != None:
            # Seek
            frame_to_seek = round(closest_position * fps_float) + 1
            self.SeekSignal.emit(frame_to_seek)

            # Update the preview and reselct current frame in properties
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(frame_to_seek)

    def actionCenterOnPlayhead_trigger(self, event):
        """ Center the timeline on the current playhead position """
        self.timeline.centerOnPlayhead()

    def getShortcutByName(self, setting_name):
        """ Get a key sequence back from the setting name """
        s = settings.get_settings()
        shortcut = QKeySequence(s.get(setting_name))
        return shortcut

    def getAllKeyboardShortcuts(self):
        """ Get a key sequence back from the setting name """
        keyboard_shortcuts = []
        all_settings = settings.get_settings()._data
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
            self.actionPlay_trigger(event, force="pause")
            # Set speed to 0
            if player.Speed() != 0:
                self.SpeedSignal.emit(0)
            # Seek to previous frame
            self.SeekSignal.emit(player.Position() - 1)

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif key.matches(self.getShortcutByName("seekNextFrame")) == QKeySequence.ExactMatch:
            # Pause video
            self.actionPlay_trigger(event, force="pause")
            # Set speed to 0
            if player.Speed() != 0:
                self.SpeedSignal.emit(0)
            # Seek to next frame
            self.SeekSignal.emit(player.Position() + 1)

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif key.matches(self.getShortcutByName("rewindVideo")) == QKeySequence.ExactMatch:
            # Toggle rewind and start playback
            self.actionRewind.trigger()
            ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
            self.actionPlay.setChecked(True)

        elif key.matches(self.getShortcutByName("fastforwardVideo")) == QKeySequence.ExactMatch:
            # Toggle fastforward button and start playback
            self.actionFastForward.trigger()
            ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
            self.actionPlay.setChecked(True)

        elif key.matches(self.getShortcutByName("playToggle")) == QKeySequence.ExactMatch or \
             key.matches(self.getShortcutByName("playToggle1")) == QKeySequence.ExactMatch or \
             key.matches(self.getShortcutByName("playToggle2")) == QKeySequence.ExactMatch or \
             key.matches(self.getShortcutByName("playToggle3")) == QKeySequence.ExactMatch:
            # Toggle playbutton and show properties
            self.actionPlay.trigger()
            self.propertyTableView.select_frame(player.Position())

        elif key.matches(self.getShortcutByName("deleteItem")) == QKeySequence.ExactMatch or \
             key.matches(self.getShortcutByName("deleteItem1")) == QKeySequence.ExactMatch:
            # Delete selected clip / transition
            self.actionRemoveClip.trigger()
            self.actionRemoveTransition.trigger()

        # Boiler plate key mappings (mostly for menu support on Ubuntu/Unity)
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
            if not self.is_transforming and self.selected_clips:
                self.TransformSignal.emit(self.selected_clips[0])
            else:
                self.TransformSignal.emit("")

        elif key.matches(self.getShortcutByName("actionInsertKeyframe")) == QKeySequence.ExactMatch:
            print("actionInsertKeyframe")
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

        # Bubble event on
        event.ignore()


    def actionProfile_trigger(self, event):
        # Show dialog
        from windows.profile import Profile
        win = Profile()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Profile add confirmed')


    def actionSplitClip_trigger(self, event):
        log.info("actionSplitClip_trigger")

        # Loop through selected files (set 1 selected file if more than 1)
        f = None
        for file_id in self.selected_files:
            # Find matching file
            f = File.get(id=file_id)

        # Bail out if no file selected
        if not f:
            log.info(self.selected_files)
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

    def actionRemove_from_Project_trigger(self, event):
        log.info("actionRemove_from_Project_trigger")

        # Loop through selected files
        for file_id in self.selected_files:
            # Find matching file
            f = File.get(id=file_id)
            if f:
                # Remove file
                f.delete()

                # Find matching clips (if any)
                clips = Clip.filter(file_id=file_id)
                for c in clips:
                    # Remove clip
                    c.delete()

        # Clear selected files
        self.selected_files = []

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionRemoveClip_trigger(self, event):
        log.info('actionRemoveClip_trigger')

        # Loop through selected clips
        for clip_id in deepcopy(self.selected_clips):
            # Find matching file
            clips = Clip.filter(id=clip_id)
            for c in clips:
                # Clear selected clips
                self.removeSelection(clip_id, "clip")

                # Remove clip
                c.delete()

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionProperties_trigger(self, event):
        log.info('actionProperties_trigger')

        # Show properties dock
        if not self.dockProperties.isVisible():
            self.dockProperties.show()

    def actionRemoveEffect_trigger(self, event):
        log.info('actionRemoveEffect_trigger')

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
        get_app().window.refreshFrameSignal.emit()

    def actionRemoveTransition_trigger(self, event):
        log.info('actionRemoveTransition_trigger')

        # Loop through selected clips
        for tran_id in deepcopy(self.selected_transitions):
            # Find matching file
            transitions = Transition.filter(id=tran_id)
            for t in transitions:
                # Clear selected clips
                self.removeSelection(tran_id, "transition")

                # Remove transition
                t.delete()

        # Refresh preview
        get_app().window.refreshFrameSignal.emit()

    def actionRemoveTrack_trigger(self, event):
        log.info('actionRemoveTrack_trigger')

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
        get_app().window.refreshFrameSignal.emit()

    def actionLockTrack_trigger(self, event):
        """Callback for locking a track"""
        log.info('actionLockTrack_trigger')

        # Get details of track
        track_id = self.selected_tracks[0]
        selected_track = Track.get(id=track_id)

        # Lock track and save
        selected_track.data['lock'] = True
        selected_track.save()

    def actionUnlockTrack_trigger(self, event):
        """Callback for unlocking a track"""
        log.info('actionUnlockTrack_trigger')

        # Get details of track
        track_id = self.selected_tracks[0]
        selected_track = Track.get(id=track_id)

        # Lock track and save
        selected_track.data['lock'] = False
        selected_track.save()

    def actionRenameTrack_trigger(self, event):
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
        for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
            if track.get("id") == track_id:
                break
            display_count -= 1

        track_name = selected_track.data["label"] or _("Track %s") % display_count

        text, ok = QInputDialog.getText(self, _('Rename Track'), _('Track Name:'), text=track_name)
        if ok:
            # Update track
            selected_track.data["label"] = text
            selected_track.save()

    def actionRemoveMarker_trigger(self, event):
        log.info('actionRemoveMarker_trigger')

        for marker_id in self.selected_markers:
            marker = Marker.filter(id=marker_id)
            for m in marker:
                # Remove track
                m.delete()

    def actionTimelineZoomIn_trigger(self, event):
        self.sliderZoom.setValue(self.sliderZoom.value() - self.sliderZoom.singleStep())

    def actionTimelineZoomOut_trigger(self, event):
        self.sliderZoom.setValue(self.sliderZoom.value() + self.sliderZoom.singleStep())

    def actionFullscreen_trigger(self, event):
        # Toggle fullscreen mode
        if not self.isFullScreen():
            self.showFullScreen()
        else:
            self.showNormal()

    def actionFile_Properties_trigger(self, event):
        log.info("Show file properties")

        # Loop through selected files (set 1 selected file if more than 1)
        f = None
        for file_id in self.selected_files:
            # Find matching file
            f = File.get(id=file_id)

        # show dialog
        from windows.file_properties import FileProperties
        win = FileProperties(f)
        # Run the dialog event loop - blocking interaction on this window during that time
        result = win.exec_()
        if result == QDialog.Accepted:

            # BRUTE FORCE approach: go through all clips and update file path
            clips = Clip.filter(file_id=file_id)
            for c in clips:
                # update clip
                c.data["reader"]["path"] = f.data["path"]
                c.save()

            log.info('File Properties Finished')
        else:
            log.info('File Properties Cancelled')

    def actionDetailsView_trigger(self, event):
        log.info("Switch to Details View")

        # Get settings
        app = get_app()
        s = settings.get_settings()

        # Prepare treeview for deletion
        if self.filesTreeView:
            self.filesTreeView.prepare_for_delete()

        # Files
        if app.context_menu_object == "files":
            s.set("file_view", "details")
            self.tabFiles.layout().removeWidget(self.filesTreeView)
            self.filesTreeView.deleteLater()
            self.filesTreeView = None
            self.filesTreeView = FilesTreeView(self)
            self.tabFiles.layout().addWidget(self.filesTreeView)

        # Transitions
        elif app.context_menu_object == "transitions":
            s.set("transitions_view", "details")
            self.tabTransitions.layout().removeWidget(self.transitionsTreeView)
            self.transitionsTreeView.deleteLater()
            self.transitionsTreeView = None
            self.transitionsTreeView = TransitionsTreeView(self)
            self.tabTransitions.layout().addWidget(self.transitionsTreeView)

        # Effects
        elif app.context_menu_object == "effects":
            s.set("effects_view", "details")
            self.tabEffects.layout().removeWidget(self.effectsTreeView)
            self.effectsTreeView.deleteLater()
            self.effectsTreeView = None
            self.effectsTreeView = EffectsTreeView(self)
            self.tabEffects.layout().addWidget(self.effectsTreeView)

    def actionThumbnailView_trigger(self, event):
        log.info("Switch to Thumbnail View")

        # Get settings
        app = get_app()
        s = settings.get_settings()

        # Prepare treeview for deletion
        if self.filesTreeView:
            self.filesTreeView.prepare_for_delete()

        # Files
        if app.context_menu_object == "files":
            s.set("file_view", "thumbnail")
            self.tabFiles.layout().removeWidget(self.filesTreeView)
            self.filesTreeView.deleteLater()
            self.filesTreeView = None
            self.filesTreeView = FilesListView(self)
            self.tabFiles.layout().addWidget(self.filesTreeView)

        # Transitions
        elif app.context_menu_object == "transitions":
            s.set("transitions_view", "thumbnail")
            self.tabTransitions.layout().removeWidget(self.transitionsTreeView)
            self.transitionsTreeView.deleteLater()
            self.transitionsTreeView = None
            self.transitionsTreeView = TransitionsListView(self)
            self.tabTransitions.layout().addWidget(self.transitionsTreeView)

        # Effects
        elif app.context_menu_object == "effects":
            s.set("effects_view", "thumbnail")
            self.tabEffects.layout().removeWidget(self.effectsTreeView)
            self.effectsTreeView.deleteLater()
            self.effectsTreeView = None
            self.effectsTreeView = EffectsListView(self)
            self.tabEffects.layout().addWidget(self.effectsTreeView)

    def resize_contents(self):
        if self.filesTreeView:
            self.filesTreeView.resize_contents()

    def getDocks(self):
        """ Get a list of all dockable widgets """
        return [self.dockFiles,
                self.dockTransitions,
                self.dockEffects,
                self.dockVideo,
                self.dockProperties,
                self.dockTimeline]

    def removeDocks(self):
        """ Remove all dockable widgets on main screen """
        for dock in self.getDocks():
            self.removeDockWidget(dock)

    def addDocks(self, docks, area):
        """ Add all dockable widgets to the same dock area on the main screen """
        for dock in docks:
            self.addDockWidget(area, dock)

    def floatDocks(self, is_floating):
        """ Float or Un-Float all dockable widgets above main screen """
        for dock in self.getDocks():
            dock.setFloating(is_floating)

    def showDocks(self, docks):
        """ Show all dockable widgets on the main screen """
        for dock in docks:
            if get_app().window.dockWidgetArea(dock) != Qt.NoDockWidgetArea:
                # Only show correctly docked widgets
                dock.show()

    def freezeDocks(self):
        """ Freeze all dockable widgets on the main screen (prevent them being closed, floated, or moved) """
        for dock in self.getDocks():
            dock.setFeatures(QDockWidget.NoDockWidgetFeatures)

    def unFreezeDocks(self):
        """ Un-freeze all dockable widgets on the main screen (allow them to be closed, floated, or moved, as appropriate) """
        for dock in self.getDocks():
            if dock is self.dockTimeline:
                dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
            else:
                dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

    def hideDocks(self):
        """ Hide all dockable widgets on the main screen """
        for dock in self.getDocks():
            dock.hide()

    def actionSimple_View_trigger(self, event):
        """ Switch to the default / simple view  """
        self.removeDocks()

        # Add Docks
        self.addDocks([self.dockFiles, self.dockTransitions, self.dockEffects, self.dockVideo], Qt.TopDockWidgetArea)

        self.floatDocks(False)
        self.tabifyDockWidget(self.dockFiles, self.dockTransitions)
        self.tabifyDockWidget(self.dockTransitions, self.dockEffects)
        self.showDocks([self.dockFiles, self.dockTransitions, self.dockEffects, self.dockVideo])

        # Set initial size of docks
        simple_state = "AAAA/wAAAAD9AAAAAwAAAAAAAAEnAAAC3/wCAAAAAvwAAAJeAAAApwAAAAAA////+gAAAAACAAAAAfsAAAAYAGQAbwBjAGsASwBlAHkAZgByAGEAbQBlAAAAAAD/////AAAAAAAAAAD7AAAAHABkAG8AYwBrAFAAcgBvAHAAZQByAHQAaQBlAHMAAAAAJwAAAt8AAACnAP///wAAAAEAAAEcAAABQPwCAAAAAfsAAAAYAGQAbwBjAGsASwBlAHkAZgByAGEAbQBlAQAAAVgAAAAVAAAAAAAAAAAAAAACAAAERgAAAtj8AQAAAAH8AAAAAAAABEYAAAD6AP////wCAAAAAvwAAAAnAAABwAAAALQA/////AEAAAAC/AAAAAAAAAFcAAAAewD////6AAAAAAIAAAAD+wAAABIAZABvAGMAawBGAGkAbABlAHMBAAAAAP////8AAACYAP////sAAAAeAGQAbwBjAGsAVAByAGEAbgBzAGkAdABpAG8AbgBzAQAAAAD/////AAAAmAD////7AAAAFgBkAG8AYwBrAEUAZgBmAGUAYwB0AHMBAAAAAP////8AAACYAP////sAAAASAGQAbwBjAGsAVgBpAGQAZQBvAQAAAWIAAALkAAAARwD////7AAAAGABkAG8AYwBrAFQAaQBtAGUAbABpAG4AZQEAAAHtAAABEgAAAJYA////AAAERgAAAAEAAAABAAAAAgAAAAEAAAAC/AAAAAEAAAACAAAAAQAAAA4AdABvAG8AbABCAGEAcgEAAAAA/////wAAAAAAAAAA"
        self.restoreState(qt_types.str_to_bytes(simple_state))
        QCoreApplication.processEvents()


    def actionAdvanced_View_trigger(self, event):
        """ Switch to an alternative view """
        self.removeDocks()

        # Add Docks
        self.addDocks([self.dockFiles, self.dockTransitions, self.dockVideo], Qt.TopDockWidgetArea)
        self.addDocks([self.dockEffects], Qt.RightDockWidgetArea)
        self.addDocks([self.dockProperties], Qt.LeftDockWidgetArea)

        self.floatDocks(False)
        self.tabifyDockWidget(self.dockTransitions, self.dockEffects)
        self.showDocks([self.dockFiles, self.dockTransitions, self.dockVideo, self.dockEffects, self.dockProperties])

        # Set initial size of docks
        advanced_state = "AAAA/wAAAAD9AAAAAwAAAAAAAADxAAADKPwCAAAAAvsAAAAcAGQAbwBjAGsAUAByAG8AcABlAHIAdABpAGUAcwEAAAA9AAADKAAAAKEA/////AAAAl4AAACnAAAAAAD////6AAAAAAIAAAAB+wAAABgAZABvAGMAawBLAGUAeQBmAHIAYQBtAGUAAAAAAP////8AAAAAAAAAAAAAAAEAAADVAAADKPwCAAAAAfsAAAAYAGQAbwBjAGsASwBlAHkAZgByAGEAbQBlAQAAAVgAAAAVAAAAAAAAAAAAAAACAAAFDwAAAyH8AQAAAAH8AAAA9wAABQ8AAAD6AP////wCAAAAAvwAAAA9AAACIQAAAVMA/////AEAAAAC/AAAAPcAAAG9AAAAewD////8AgAAAAL7AAAAEgBkAG8AYwBrAEYAaQBsAGUAcwEAAAA9AAAA9gAAAJgA/////AAAATkAAAElAAAAtQEAABz6AAAAAQEAAAAC+wAAAB4AZABvAGMAawBUAHIAYQBuAHMAaQB0AGkAbwBuAHMBAAAAAP////8AAABsAP////sAAAAWAGQAbwBjAGsARQBmAGYAZQBjAHQAcwEAAAC+AAABKgAAAFoA////+wAAABIAZABvAGMAawBWAGkAZABlAG8BAAACugAAA0wAAABHAP////sAAAAYAGQAbwBjAGsAVABpAG0AZQBsAGkAbgBlAQAAAmQAAAD6AAAAlgD///8AAAUPAAAAAQAAAAEAAAACAAAAAQAAAAL8AAAAAQAAAAIAAAABAAAADgB0AG8AbwBsAEIAYQByAQAAAAD/////AAAAAAAAAAA="
        self.restoreState(qt_types.str_to_bytes(advanced_state))
        QCoreApplication.processEvents()

    def actionFreeze_View_trigger(self, event):
        """ Freeze all dockable widgets on the main screen """
        self.freezeDocks()
        self.actionFreeze_View.setVisible(False)
        self.actionUn_Freeze_View.setVisible(True)
        self.docks_frozen = True

    def actionUn_Freeze_View_trigger(self, event):
        """ Un-Freeze all dockable widgets on the main screen """
        self.unFreezeDocks()
        self.actionFreeze_View.setVisible(True)
        self.actionUn_Freeze_View.setVisible(False)
        self.docks_frozen = False

    def actionShow_All_trigger(self, event):
        """ Show all dockable widgets """
        self.showDocks(self.getDocks())

    def actionTutorial_trigger(self, event):
        """ Show tutorial again """
        s = settings.get_settings()

        # Clear tutorial settings
        s.set("tutorial_enabled", True)
        s.set("tutorial_ids", "")

        # Show first tutorial dialog again
        if self.tutorial_manager:
            self.tutorial_manager.exit_manager()
            self.tutorial_manager = TutorialManager(self)

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
            self.setWindowTitle("%s %s [%s] - %s" % (save_indicator, _("Untitled Project"), profile, "OpenShot Video Editor"))
        else:
            # Yes, project is saved
            # Get just the filename
            filename = os.path.basename(app.project.current_filepath)
            filename = os.path.splitext(filename)[0]
            self.setWindowTitle("%s %s [%s] - %s" % (save_indicator, filename, profile, "OpenShot Video Editor"))

    # Update undo and redo buttons enabled/disabled to available changes
    def updateStatusChanged(self, undo_status, redo_status):
        log.info('updateStatusChanged')
        self.actionUndo.setEnabled(undo_status)
        self.actionRedo.setEnabled(redo_status)
        self.SetWindowTitle()

    # Add to the selected items
    def addSelection(self, item_id, item_type, clear_existing=False):
        log.info('main::addSelection: item_id: %s, item_type: %s, clear_existing: %s' % (item_id, item_type, clear_existing))

        # Clear existing selection (if needed)
        if clear_existing:
            if item_type == "clip":
                self.selected_clips.clear()
            elif item_type == "transition":
                self.selected_transitions.clear()
            elif item_type == "effect":
                self.selected_effects.clear()

            # Clear transform (if any)
            self.TransformSignal.emit("")

        if item_id:
            # If item_id is not blank, store it
            if item_type == "clip" and item_id not in self.selected_clips:
                self.selected_clips.append(item_id)
            elif item_type == "transition" and item_id not in self.selected_transitions:
                self.selected_transitions.append(item_id)
            elif item_type == "effect" and item_id not in self.selected_effects:
                self.selected_effects.append(item_id)

            # Change selected item in properties view
            self.show_property_id = item_id
            self.show_property_type = item_type
            self.show_property_timer.start()

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

        # Clear transform (if any)
        get_app().window.TransformSignal.emit("")

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

        # Change selected item in properties view
        self.show_property_timer.start()

    # Update window settings in setting store
    def save_settings(self):
        s = settings.get_settings()

        # Save window state and geometry (saves toolbar and dock locations)
        s.set('window_state_v2', qt_types.bytes_to_str(self.saveState()))
        s.set('window_geometry_v2', qt_types.bytes_to_str(self.saveGeometry()))
        s.set('docks_frozen', self.docks_frozen)

    # Get window settings from setting store
    def load_settings(self):
        s = settings.get_settings()

        # Window state and geometry (also toolbar, dock locations and frozen UI state)
        if s.get('window_state_v2'):
            self.restoreState(qt_types.str_to_bytes(s.get('window_state_v2')))
        if s.get('window_geometry_v2'):
            self.restoreGeometry(qt_types.str_to_bytes(s.get('window_geometry_v2')))
        if s.get('docks_frozen'):
            """ Freeze all dockable widgets on the main screen """
            self.freezeDocks()
            self.actionFreeze_View.setVisible(False)
            self.actionUn_Freeze_View.setVisible(True)
            self.docks_frozen = True

        # Load Recent Projects
        self.load_recent_menu()

        # The method restoreState restores the visibility of the toolBar,
        # but does not set the correct flag in the actionView_Toolbar.
        self.actionView_Toolbar.setChecked(self.toolBar.isVisibleTo(self))

    def load_recent_menu(self):
        """ Clear and load the list of recent menu items """
        s = settings.get_settings()
        _ = get_app()._tr  # Get translation function

        # Get list of recent projects
        recent_projects = s.get("recent_projects")

        # Add Recent Projects menu (after Open File)
        import functools
        if not self.recent_menu:
            # Create a new recent menu
            self.recent_menu = self.menuFile.addMenu(QIcon.fromTheme("document-open-recent"), _("Recent Projects"))
            self.menuFile.insertMenu(self.actionRecent_Placeholder, self.recent_menu)
        else:
            # Clear the existing children
            self.recent_menu.clear()

        # Add recent projects to menu
        for file_path in reversed(recent_projects):
            new_action = self.recent_menu.addAction(file_path)
            new_action.triggered.connect(functools.partial(self.recent_project_clicked, file_path))

    # Remove a project from the Recent menu if OpenShot can't find it
    def remove_recent_project(self, file_path):
        s = settings.get_settings()
        recent_projects = s.get("recent_projects")
        if file_path in recent_projects:
            recent_projects.remove(file_path)
        s.set("recent_projects", recent_projects)
        s.save()

    def recent_project_clicked(self, file_path):
        """ Load a recent project when clicked """

        # Load project file
        self.OpenProjectSignal.emit(file_path)

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
        self.tabFiles.layout().addWidget(self.filesToolbar)

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
        self.effectsFilter.setObjectName("effectsFilter")
        self.effectsFilter.setPlaceholderText(_("Filter"))
        self.effectsFilter.setClearButtonEnabled(True)
        self.effectsToolbar.addWidget(self.effectsFilter)
        self.tabEffects.layout().addWidget(self.effectsToolbar)

        # Add Video Preview toolbar
        self.videoToolbar = QToolBar("Video Toolbar")

        # Add fixed spacer(s) (one for each "Other control" to keep playback controls centered)
        ospacer1 = QWidget(self)
        ospacer1.setMinimumSize(32, 1) # actionSaveFrame
        self.videoToolbar.addWidget(ospacer1)
        #ospacer2 = QWidget(self)
        #ospacer2.setMinimumSize(32, 1) # ???
        #self.videoToolbar.addWidget(ospacer2)

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
        self.actionPlay.setCheckable(True)

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

        # Get project's initial zoom value
        initial_scale = get_app().project.get("scale") or 15
        # Round non-exponential scale down to next lowest power of 2
        initial_zoom = secondsToZoom(initial_scale)

        # Setup Zoom slider
        self.sliderZoom = QSlider(Qt.Horizontal, self)
        self.sliderZoom.setPageStep(1)
        self.sliderZoom.setRange(0, 30)
        self.sliderZoom.setValue(initial_zoom)
        self.sliderZoom.setInvertedControls(True)
        self.sliderZoom.resize(100, 16)

        self.zoomScaleLabel = QLabel( _("{} seconds").format(zoomToSeconds(self.sliderZoom.value())) )

        # add zoom widgets
        self.timelineToolbar.addAction(self.actionTimelineZoomIn)
        self.timelineToolbar.addWidget(self.sliderZoom)
        self.timelineToolbar.addAction(self.actionTimelineZoomOut)
        self.timelineToolbar.addWidget(self.zoomScaleLabel)

        # Add timeline toolbar to web frame
        self.frameWeb.addWidget(self.timelineToolbar)

    def clearSelections(self):
        """Clear all selection containers"""
        self.selected_files = []
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
        log.info('foundCurrentVersion: Found the latest version: %s' % version)
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
        for child in self.findChildren(QDockWidget):
            if child.isFloating() and child.isEnabled():
                child.raise_()
                child.show()

    def hideEvent(self, event):
        """ Have any child windows hide with main window """
        QMainWindow.hideEvent(self, event)
        for child in self.findChildren(QDockWidget):
            if child.isFloating() and child.isVisible():
                child.hide()

    def show_property_timeout(self):
        """Callback for show property timer"""

        # Stop timer
        self.show_property_timer.stop()

        # Emit load properties signal
        self.propertyTableView.loadProperties.emit(self.show_property_id, self.show_property_type)

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
        s = settings.get_settings()
        log.info("InitCacheSettings")
        log.info("cache-mode: %s" % s.get("cache-mode"))
        log.info("cache-limit-mb: %s" % s.get("cache-limit-mb"))

        # Get MB limit of cache (and convert to bytes)
        cache_limit = s.get("cache-limit-mb") * 1024 * 1024 # Convert MB to Bytes

        # Clear old cache
        new_cache_object = None
        if s.get("cache-mode") == "CacheMemory":
            # Create CacheMemory object, and set on timeline
            log.info("Creating CacheMemory object with %s byte limit" % cache_limit)
            new_cache_object = openshot.CacheMemory(cache_limit)
            self.timeline_sync.timeline.SetCache(new_cache_object)

        elif s.get("cache-mode") == "CacheDisk":
            # Create CacheDisk object, and set on timeline
            log.info("Creating CacheDisk object with %s byte limit at %s" % (cache_limit, info.PREVIEW_CACHE_PATH))
            image_format = s.get("cache-image-format")
            image_quality = s.get("cache-quality")
            image_scale = s.get("cache-scale")
            new_cache_object = openshot.CacheDisk(info.PREVIEW_CACHE_PATH, image_format, image_quality, image_scale, cache_limit)
            self.timeline_sync.timeline.SetCache(new_cache_object)

        # Clear old cache before it goes out of scope
        if self.cache_object:
            self.cache_object.Clear()
        # Update cache reference, so it doesn't go out of scope
        self.cache_object = new_cache_object

    def FrameExported(self, title_message, start_frame, end_frame, current_frame):
        """Connect to Unity launcher (for Linux)"""
        try:
            if sys.platform == "linux" and self.has_launcher:
                if not self.unity_launchers:
                    # Get launcher only once
                    from gi.repository import Unity
                    self.unity_launchers.append(Unity.LauncherEntry.get_for_desktop_id("openshot-qt.desktop"))
                    self.unity_launchers.append(Unity.LauncherEntry.get_for_desktop_id("appimagekit-openshot-qt.desktop"))

                # Set progress and show progress bar
                for launcher in self.unity_launchers:
                    launcher.set_property("progress", current_frame / (end_frame - start_frame))
                    launcher.set_property("progress_visible", True)

        except:
            # Just ignore
            self.has_launcher = False

    def ExportFinished(self, path):
        """Export has completed"""
        try:
            if sys.platform == "linux" and self.has_launcher:
                for launcher in self.unity_launchers:
                    # Set progress on Unity launcher and hide progress bar
                    launcher.set_property("progress", 0.0)
                    launcher.set_property("progress_visible", False)
        except:
            pass

    def transformTriggered(self, clip_id):
        """Handle transform signal (to keep track of whether a transform is happening or not)"""
        if clip_id and clip_id in self.selected_clips:
            self.is_transforming = True
        else:
            self.is_transforming = False

    def init_thumbnail_server(self):
        """Initialize and start the thumbnail HTTP server"""
        self.http_server_thread = httpThumbnailServerThread()
        self.http_server_thread.start()

    def __init__(self, mode=None):

        # Create main window base class
        QMainWindow.__init__(self)
        self.mode = mode    # None or unittest (None is normal usage)
        self.initialized = False

        # set window on app for reference during initialization of children
        app = get_app()
        app.window = self
        _ = app._tr

        # Load user settings for window
        s = settings.get_settings()
        self.recent_menu = None

        # Track metrics
        track_metric_session()  # start session

        # Set unique install id (if blank)
        if not s.get("unique_install_id"):
            s.set("unique_install_id", str(uuid4()))

            # Track 1st launch metric
            track_metric_screen("initial-launch-screen")

        # Track main screen
        track_metric_screen("main-screen")

        # Create blank tutorial manager
        self.tutorial_manager = None

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Set all keyboard shortcuts from the settings file
        self.InitKeyboardShortcuts()

        # Init UI
        ui_util.init_ui(self)

        # Setup toolbars that aren't on main window, set initial state of items, etc
        self.setup_toolbars()

        # Add window as watcher to receive undo/redo status updates
        app.updates.add_watcher(self)

        # Get current version of OpenShot via HTTP
        self.FoundVersionSignal.connect(self.foundCurrentVersion)
        get_current_Version()

        # Connect signals
        self.is_transforming = False
        self.TransformSignal.connect(self.transformTriggered)
        if not self.mode == "unittest":
            self.RecoverBackup.connect(self.recover_backup)

        # Init HTTP server for thumbnails
        self.init_thumbnail_server()

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

        # Setup files tree
        if s.get("file_view") == "details":
            self.filesTreeView = FilesTreeView(self)
        else:
            self.filesTreeView = FilesListView(self)
        self.tabFiles.layout().addWidget(self.filesTreeView)
        self.filesTreeView.setFocus()

        # Setup transitions tree
        if s.get("transitions_view") == "details":
            self.transitionsTreeView = TransitionsTreeView(self)
        else:
            self.transitionsTreeView = TransitionsListView(self)
        self.tabTransitions.layout().addWidget(self.transitionsTreeView)

        # Setup effects tree
        if s.get("effects_view") == "details":
            self.effectsTreeView = EffectsTreeView(self)
        else:
            self.effectsTreeView = EffectsListView(self)
        self.tabEffects.layout().addWidget(self.effectsTreeView)

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
        # Timer to use a delay before showing properties (to prevent a mass selection from trying
        # to update the property model hundreds of times)
        self.show_property_id = None
        self.show_property_type = None
        self.show_property_timer = QTimer()
        self.show_property_timer.setInterval(100)
        self.show_property_timer.timeout.connect(self.show_property_timeout)
        self.show_property_timer.stop()

        # Setup video preview QWidget
        self.videoPreview = VideoWidget()
        self.tabVideo.layout().insertWidget(0, self.videoPreview)

        # Load window state and geometry
        self.load_settings()

        # Setup Cache settings
        self.cache_object = None
        self.InitCacheSettings()

        # Start the preview thread
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.timeline_sync.timeline, self.videoPreview)
        self.preview_thread = self.preview_parent.worker

        # Set pause callback
        self.PauseSignal.connect(self.handlePausedVideo)

        # QTimer for Autosave
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setInterval(s.get("autosave-interval") * 1000 * 60)
        self.auto_save_timer.timeout.connect(self.auto_save_project)
        if s.get("enable-auto-save"):
            self.auto_save_timer.start()

        # Set encoding method
        if s.get("hw-decoder"):
                openshot.Settings.Instance().HARDWARE_DECODER = int(str(s.get("hw-decoder")))
        else:
                openshot.Settings.Instance().HARDWARE_DECODER = 0

        # Set graphics card for decoding
        if s.get("graca_number_de"):
            if int(str(s.get("graca_number_de"))) != 0:
                openshot.Settings.Instance().HW_DE_DEVICE_SET = int(str(s.get("graca_number_de")))
            else:
                openshot.Settings.Instance().HW_DE_DEVICE_SET = 0
        else:
            openshot.Settings.Instance().HW_DE_DEVICE_SET = 0

        # Set graphics card for encoding
        if s.get("graca_number_en"):
            if int(str(s.get("graca_number_en"))) != 0:
                openshot.Settings.Instance().HW_EN_DEVICE_SET = int(str(s.get("graca_number_en")))
            else:
                openshot.Settings.Instance().HW_EN_DEVICE_SET = 0
        else:
            openshot.Settings.Instance().HW_EN_DEVICE_SET = 0

        # Set audio playback settings
        if s.get("playback-audio-device"):
                openshot.Settings.Instance().PLAYBACK_AUDIO_DEVICE_NAME = str(s.get("playback-audio-device"))
        else:
                openshot.Settings.Instance().PLAYBACK_AUDIO_DEVICE_NAME = ""

        # Set OMP thread enabled flag (for stability)
        if s.get("omp_threads_enabled"):
            openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = False
        else:
            openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = True

        # Set scaling mode to lower quality scaling (for faster previews)
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = False

        # Set use omp threads number environment variable
        if s.get("omp_threads_number"):
            openshot.Settings.Instance().OMP_THREADS = max(2,int(str(s.get("omp_threads_number"))))
        else:
            openshot.Settings.Instance().OMP_THREADS = 12

        # Set use ffmpeg threads number environment variable
        if s.get("ff_threads_number"):
            openshot.Settings.Instance().FF_THREADS = max(1,int(str(s.get("ff_threads_number"))))
        else:
            openshot.Settings.Instance().FF_THREADS = 8

        # Set use max width decode hw environment variable
        if s.get("decode_hw_max_width"):
            openshot.Settings.Instance().DE_LIMIT_WIDTH_MAX = int(str(s.get("decode_hw_max_width")))

        # Set use max height decode hw environment variable
        if s.get("decode_hw_max_height"):
            openshot.Settings.Instance().DE_LIMIT_HEIGHT_MAX = int(str(s.get("decode_hw_max_height")))

        # Create lock file
        self.create_lock_file()

        # Connect OpenProject Signal
        self.OpenProjectSignal.connect(self.open_project)

        # Show window
        if not self.mode == "unittest":
            self.show()

        # Create tutorial manager
        self.tutorial_manager = TutorialManager(self)

        # Connect to Unity DBus signal (if linux)
        if sys.platform == "linux":
            self.unity_launchers = []
            self.has_launcher = True
            self.ExportFrame.connect(self.FrameExported)
            self.ExportEnded.connect(self.ExportFinished)

        # Save settings
        s.save()

        # Refresh frame
        QTimer.singleShot(100, self.refreshFrameSignal.emit)

        # Main window is initialized
        self.initialized = True
