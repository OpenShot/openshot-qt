"""
 @file
 @brief This file loads the main window (i.e. the primary user-interface)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
from uuid import uuid4
from copy import deepcopy

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


class MainWindow(QMainWindow, updates.UpdateWatcher, updates.UpdateInterface):
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

    # Save window settings on close
    def closeEvent(self, event):

        # Close any tutorial dialogs
        self.tutorial_manager.exit_manager()

        # Prompt user to save (if needed)
        if get_app().project.needs_save() and not self.mode == "unittest":
            log.info('Prompt user to save project')
            # Translate object
            _ = get_app()._tr

            # Handle exception
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project before closing?"), QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger(event)
                event.accept()
            elif ret == QMessageBox.Cancel:
                # User canceled prompt - don't quit
                event.ignore()
                return

        # Save settings
        self.save_settings()

        # Track end of session
        track_metric_session(False)

        # Stop threads
        self.StopSignal.emit()

        # Process any queued events
        QCoreApplication.processEvents()

        # Stop preview thread (and wait for it to end)
        self.preview_thread.kill()
        self.preview_parent.background.exit()
        self.preview_parent.background.wait(5000)

        # Close & Stop libopenshot logger
        openshot.ZmqLogger.Instance().Close()
        get_app().logger_libopenshot.kill()

        # Destroy lock file
        self.destroy_lock_file()

    def recover_backup(self):
        """Recover the backup file (if any)"""
        log.info("recover_backup")
        # Check for backup.osp file
        recovery_path = os.path.join(info.BACKUP_PATH, "backup.osp")

        # Load recovery project
        if os.path.exists(recovery_path):
            log.info("Recovering backup file: %s" % recovery_path)
            self.open_project(recovery_path, clear_thumbnails=False)

            # Clear the file_path (which is set by saving the project)
            get_app().project.current_filepath = None
            get_app().project.has_unsaved_changes = True

            # Set Window title
            self.SetWindowTitle()

            # Show message to user
            msg = QMessageBox()
            _ = get_app()._tr
            msg.setWindowTitle(_("Backup Recovered"))
            msg.setText(_("Your most recent unsaved project has been recovered."))
            msg.exec_()

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
                with open(log_path, "r") as f:
                    # Read from bottom up
                    for line in reversed(f.readlines()):
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

                        # Ignore certain unuseful lines
                        if line.strip() and "---" not in line and "libopenshot logging:" not in line and not last_log_line:
                            last_log_line = line

            # Split last stack trace (if any)
            if last_stack_trace:
                # Get top line of stack trace (for metrics)
                last_log_line = last_stack_trace.split("\n")[0].strip()

                # Send stacktrace for debugging (if send metrics is enalbed)
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
            log.error("Unhandled crash detected... will attempt to recover backup project: %s" % info.BACKUP_PATH)
            track_metric_error("unhandled-crash%s" % last_log_line, True)

            # Remove file
            os.remove(lock_path)

            # Recover backup file (this can't happen until after the Main Window has completely loaded)
            QTimer.singleShot(0, self.RecoverBackup.emit)

        else:
            # Normal startup, clear thumbnails
            self.clear_all_thumbnails()

            # Load a blank project (to propagate the default settings)
            get_app().project.load("")

        # Create lock file
        with open(lock_path, 'w') as f:
            f.write(lock_value)

    def destroy_lock_file(self):
        """Destroy the lock file"""
        lock_path = os.path.join(info.USER_PATH, ".lock")

        # Check if it already exists
        if os.path.exists(lock_path):
            # Remove file
            os.remove(lock_path)

    def actionNew_trigger(self, event):

        app = get_app()
        _ = app._tr  # Get translation function

        # Do we have unsaved changes?
        if get_app().project.needs_save():
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
        get_app().project.load("")
        get_app().updates.reset()
        self.updateStatusChanged(False, False)

        # Reset selections
        self.clearSelections()

        self.filesTreeView.refresh_view()
        log.info("New Project created.")

        # Set Window title
        self.SetWindowTitle()

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

    def save_project(self, file_path):
        """ Save a project to a file path, and refresh the screen """
        app = get_app()
        _ = app._tr  # Get translation function

        try:
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

        # Set cursor to waiting
        get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

        try:
            if os.path.exists(file_path.encode('UTF-8')):
                # Clear any previous thumbnails
                if clear_thumbnails:
                    self.clear_all_thumbnails()

                # Load project file
                app.project.load(file_path)

                # Set Window title
                self.SetWindowTitle()

                # Reset undo/redo history
                app.updates.reset()
                self.updateStatusChanged(False, False)

                # Reset selections
                self.clearSelections()

                # Refresh file tree
                self.filesTreeView.refresh_view()

                # Load recent projects again
                self.load_recent_menu()

                log.info("Loaded project {}".format(file_path))

        except Exception as ex:
            log.error("Couldn't open project {}".format(file_path))
            QMessageBox.warning(self, _("Error Opening Project"), str(ex))

        # Restore normal cursor
        get_app().restoreOverrideCursor()

    def clear_all_thumbnails(self):
        """Clear all user thumbnails"""
        try:
            if os.path.exists(info.THUMBNAIL_PATH):
                log.info("Clear all thumbnails: %s" % info.THUMBNAIL_PATH)
                # Remove thumbnail folder
                shutil.rmtree(info.THUMBNAIL_PATH)
                # Create thumbnail folder
                os.mkdir(info.THUMBNAIL_PATH)

            # Clear any blender animations
            if os.path.exists(info.BLENDER_PATH):
                log.info("Clear all animations: %s" % info.BLENDER_PATH)
                # Remove blender folder
                shutil.rmtree(info.BLENDER_PATH)
                # Create blender folder
                os.mkdir(info.BLENDER_PATH)

            # Clear any blender animations
            if os.path.exists(info.BACKUP_PATH):
                log.info("Clear all backups: %s" % info.BACKUP_PATH)
                # Remove backup folder
                shutil.rmtree(info.BACKUP_PATH)
                # Create backup folder
                os.mkdir(info.BACKUP_PATH)
        except:
            log.info("Failed to clear thumbnails: %s" % info.THUMBNAIL_PATH)

    def actionOpen_trigger(self, event):
        app = get_app()
        _ = app._tr
        recommended_path = app.project.current_filepath
        if not recommended_path:
            recommended_path = info.HOME_PATH

        # Do we have unsaved changes?
        if get_app().project.needs_save():
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project first?"), QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger(event)
            elif ret == QMessageBox.Cancel:
                # User canceled prompt
                return

        # Prompt for open project file
        file_path, file_type = QFileDialog.getOpenFileName(self, _("Open Project..."), recommended_path, _("OpenShot Project (*.osp)"))

        # Load project file
        self.open_project(file_path)

    def actionSave_trigger(self, event):
        app = get_app()
        _ = app._tr

        # Get current filepath if any, otherwise ask user
        file_path = app.project.current_filepath
        if not file_path:
            recommended_path = os.path.join(info.HOME_PATH, "%s.osp" % _("Untitled Project"))
            file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project..."), recommended_path, _("OpenShot Project (*.osp)"))

        if file_path:
            # Append .osp if needed
            if ".osp" not in file_path:
                file_path = "%s.osp" % file_path

            # Save project
            self.save_project(file_path)

    def auto_save_project(self):
        """Auto save the project"""
        log.info("auto_save_project")

        # Get current filepath (if any)
        file_path = get_app().project.current_filepath
        if get_app().project.needs_save():
            if file_path:
                # A Real project file exists
                # Append .osp if needed
                if ".osp" not in file_path:
                    file_path = "%s.osp" % file_path

                # Save project
                log.info("Auto save project file: %s" % file_path)
                self.save_project(file_path)

            else:
                # No saved project found
                recovery_path = os.path.join(info.BACKUP_PATH, "backup.osp")
                log.info("Creating backup of project file: %s" % recovery_path)
                get_app().project.save(recovery_path, move_temp_files=False, make_paths_relative=False)

                # Clear the file_path (which is set by saving the project)
                get_app().project.current_filepath = None
                get_app().project.has_unsaved_changes = True

    def actionSaveAs_trigger(self, event):
        app = get_app()
        _ = app._tr

        recommended_path = app.project.current_filepath
        if not recommended_path:
            recommended_path = os.path.join(info.HOME_PATH, "%s.osp" % _("Untitled Project"))
        file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project As..."), recommended_path, _("OpenShot Project (*.osp)"))
        if file_path:
            # Append .osp if needed
            if ".osp" not in file_path:
                file_path = "%s.osp" % file_path

            # Save new project
            self.save_project(file_path)

    def actionImportFiles_trigger(self, event):
        app = get_app()
        _ = app._tr
        recommended_path = app.project.current_filepath
        if not recommended_path:
            recommended_path = os.path.join(info.HOME_PATH)
        files = QFileDialog.getOpenFileNames(self, _("Import File..."), recommended_path)[0]
        for file_path in files:
            self.filesTreeView.add_file(file_path)
            self.filesTreeView.refresh_view()
            log.info("Imported media file {}".format(file_path))

    def actionAdd_to_Timeline_trigger(self, event):
        # Loop through selected files
        f = None
        files = []
        for file_id in self.selected_files:
            # Find matching file
            files.append(File.get(id=file_id))

        # Get current position of playhead
        fps = get_app().project.get(["fps"])
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

    def actionUndo_trigger(self, event):
        log.info('actionUndo_trigger')
        app = get_app()
        app.updates.undo()

        # Update the preview
        self.refreshFrameSignal.emit()

    def actionRedo_trigger(self, event):
        log.info('actionRedo_trigger')
        app = get_app()
        app.updates.redo()

        # Update the preview
        self.refreshFrameSignal.emit()

    def actionPreferences_trigger(self, event):
        # Stop preview thread
        self.SpeedSignal.emit(0)
        ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-start")
        self.actionPlay.setChecked(False)

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

    def actionEffectsShowAll_trigger(self, event):
        self.effectsTreeView.refresh_view()

    def actionEffectsShowVideo_trigger(self, event):
        self.effectsTreeView.refresh_view()

    def actionEffectsShowAudio_trigger(self, event):
        self.effectsTreeView.refresh_view()

    def actionHelpContents_trigger(self, event):
        try:
            webbrowser.open("http://openshotusers.com/?app-menu")
            log.info("Help Contents is open")
        except:
            QMessageBox.information(self, "Error !",
                                    "Unable to open the Help Contents. Please ensure the openshot-doc package is installed.")
            log.info("Unable to open the Help Contents")

    def actionAbout_trigger(self, event):
        """Show about dialog"""
        from windows.about import About
        win = About()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('About Openshot add confirmed')
        else:
            log.info('About Openshot add cancelled')

    def actionReportBug_trigger(self, event):
        try:
            webbrowser.open("https://github.com/OpenShot/openshot-qt/issues/?app-menu-bug")
            log.info("Open the Bug Report GitHub Issues web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Bug Report GitHub Issues web page")
            log.info("Unable to open the Bug Report GitHub Issues web page")

    def actionAskQuestion_trigger(self, event):
        try:
            webbrowser.open("https://github.com/OpenShot/openshot-qt/issues/?app-menu-question")
            log.info("Open the Questions GitHub Issues web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Questions GitHub Issues web page")
            log.info("Unable to open the Questions GitHub Issues web page")

    def actionTranslate_trigger(self, event):
        try:
            webbrowser.open("https://translations.launchpad.net/openshot/2.0")
            log.info("Open the Translate launchpad web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Translation web page")
            log.info("Unable to open the Translation web page")

    def actionDonate_trigger(self, event):
        try:
            webbrowser.open("http://openshot.org/donate/?app-menu")
            log.info("Open the Donate web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Donate web page")
            log.info("Unable to open the Donate web page")

    def actionUpdate_trigger(self, event):
        try:
            webbrowser.open("http://openshot.org/download/?app-toolbar")
            log.info("Open the Download web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Download web page")
            log.info("Unable to open the Download web page")

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

        if self.selected_files:
            # Find matching file
            f = File.get(id=self.selected_files[0])
            if f:
                # Get file path
                previewPath = f.data["path"]

                # Load file into player
                self.LoadFileSignal.emit(previewPath)

                # Trigger play button
                self.actionPlay.setChecked(False)
                self.actionPlay.trigger()

    def previewFrame(self, position_seconds, position_frames, time_code):
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

    def actionAddTrack_trigger(self, event):
        log.info("actionAddTrack_trigger")

        # Get # of tracks
        track_number = len(get_app().project.get(["layers"]))

        # Look for existing Marker
        track = Track()
        track.data = {"number": track_number, "y": 0, "label": "", "lock": False}
        track.save()

    def actionAddTrackAbove_trigger(self, event):
        log.info("actionAddTrackAbove_trigger")

        # Get # of tracks
        max_track_number = len(get_app().project.get(["layers"]))
        selected_layer_id = self.selected_tracks[0]

        # Get selected track data
        existing_track = Track.get(id=selected_layer_id)
        selected_layer_number = int(existing_track.data["number"])

        # Create new track
        track = Track()
        track.data = {"number": max_track_number, "y": 0, "label": "", "lock": False}
        track.save()

        # Loop through all clips on higher layers, and move to new layer (in reverse order)
        for existing_layer in list(reversed(range(selected_layer_number + 1, max_track_number))):
            existing_track.data["label"] = ""
            existing_track.save()

            for clip in Clip.filter(layer=existing_layer):
                clip.data["layer"] = int(clip.data["layer"]) + 1
                clip.save()

    def actionAddTrackBelow_trigger(self, event):
        log.info("actionAddTrackAbove_trigger")

        # Get # of tracks
        max_track_number = len(get_app().project.get(["layers"]))
        selected_layer_id = self.selected_tracks[0]

        # Get selected track data
        existing_track = Track.get(id=selected_layer_id)
        selected_layer_number = int(existing_track.data["number"])

        # Create new track
        track = Track()
        track.data = {"number": max_track_number, "y": 0, "label": "", "lock": False}
        track.save()

        # Loop through all clips on higher layers, and move to new layer (in reverse order)
        for existing_layer in list(reversed(range(selected_layer_number, max_track_number))):
            existing_track.data["label"] = ""
            existing_track.save()

            for clip in Clip.filter(layer=existing_layer):
                clip.data["layer"] = int(clip.data["layer"]) + 1
                clip.save()

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
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Calculate position in seconds
        position = player.Position() / fps_float

        # Look for existing Marker
        marker = Marker()
        marker.data = {"position": position, "icon": "blue.png"}
        marker.save()

    def actionPreviousMarker_trigger(self, event):
        log.info("actionPreviousMarker_trigger")

        # Calculate current position (in seconds)
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = self.preview_thread.current_frame / fps_float
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
            if marker_position < current_position and (abs(marker_position - current_position) > 0.05):
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
            frame_to_seek = int(closest_position * fps_float) + 1
            self.SeekSignal.emit(frame_to_seek)

            # Update the preview and reselct current frame in properties
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(frame_to_seek)

    def actionNextMarker_trigger(self, event):
        log.info("actionNextMarker_trigger")
        log.info(self.preview_thread.current_frame)

        # Calculate current position (in seconds)
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = self.preview_thread.current_frame / fps_float
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
            if marker_position > current_position and (abs(marker_position - current_position) > 0.05):
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
            frame_to_seek = int(closest_position * fps_float) + 1
            self.SeekSignal.emit(frame_to_seek)

            # Update the preview and reselct current frame in properties
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(frame_to_seek)

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
        MOD_MASK = (Qt.CTRL | Qt.ALT | Qt.SHIFT | Qt.META)

        # Detect the current KeySequence pressed (including modifier keys)
        key_value = event.key()
        print(key_value)
        modifiers = int(event.modifiers())
        if (key_value > 0 and key_value != Qt.Key_Shift and key_value != Qt.Key_Alt and
                    key_value != Qt.Key_Control and key_value != Qt.Key_Meta):
            # A valid keysequence was detected
            key = QKeySequence(modifiers + key_value)
        else:
            # No valid keysequence detected
            return

        # Debug
        log.info("keyPressEvent: %s" % (key.toString()))

        # Get the video player object
        player = self.preview_thread.player

        # Get framerate
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])
        playhead_position = float(self.preview_thread.current_frame) / fps_float

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
        elif key.matches(self.getShortcutByName("actionProperties")) == QKeySequence.ExactMatch:
            self.actionProperties.trigger()

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

    def actionRemoveTrack_trigger(self, event):
        log.info('actionRemoveTrack_trigger')

        # Get translation function
        _ = get_app()._tr

        track_id = self.selected_tracks[0]
        max_track_number = len(get_app().project.get(["layers"]))

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

        # Loop through all tracks, and renumber (to keep thing in numerical order)
        for existing_layer in list(range(selected_track_number + 1, max_track_number)):
            # Update existing layer #
            track = Track.get(number=existing_layer)
            track.data["number"] = existing_layer - 1
            track.data["label"] = ""
            track.save()

            for clip in Clip.filter(layer=existing_layer):
                clip.data["layer"] = int(clip.data["layer"]) - 1
                clip.save()

        # Clear selected track
        self.selected_tracks = []

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
        track_name = selected_track.data["label"] or _("Track %s") % selected_track.data["number"]

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
                self.dockProperties]

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
        """ Freeze all dockable widgets on the main screen (no float, moving, or closing) """
        for dock in self.getDocks():
            dock.setFeatures(QDockWidget.NoDockWidgetFeatures)

    def unFreezeDocks(self):
        """ Un-freeze all dockable widgets on the main screen (allow them to be moved, closed, and floated) """
        for dock in self.getDocks():
            dock.setFeatures(QDockWidget.AllDockWidgetFeatures)

    def hideDocks(self):
        """ Hide all dockable widgets on the main screen """
        for dock in self.getDocks():
            dock.hide()

    def actionSimple_View_trigger(self, event):
        """ Switch to the default / simple view  """
        self.removeDocks()
        self.addDocks([self.dockFiles, self.dockTransitions, self.dockEffects, self.dockVideo], Qt.TopDockWidgetArea)
        self.floatDocks(False)
        self.tabifyDockWidget(self.dockFiles, self.dockTransitions)
        self.tabifyDockWidget(self.dockTransitions, self.dockEffects)
        self.showDocks([self.dockFiles, self.dockTransitions, self.dockEffects, self.dockVideo])

        # Set initial size of docks
        simple_state = "AAAA/wAAAAD9AAAAAwAAAAAAAAD8AAAA9PwCAAAAAfwAAAILAAAA9AAAAAAA////+v////8CAAAAAvsAAAAcAGQAbwBjAGsAUAByAG8AcABlAHIAdABpAGUAcwAAAAAA/////wAAAKEA////+wAAABgAZABvAGMAawBLAGUAeQBmAHIAYQBtAGUAAAAAAP////8AAAATAP///wAAAAEAAAEcAAABQPwCAAAAAfsAAAAYAGQAbwBjAGsASwBlAHkAZgByAGEAbQBlAQAAAVgAAAAVAAAAAAAAAAAAAAACAAAEqwAAAdz8AQAAAAL8AAAAAAAAAWQAAAB7AP////oAAAAAAgAAAAP7AAAAEgBkAG8AYwBrAEYAaQBsAGUAcwEAAAAA/////wAAAJgA////+wAAAB4AZABvAGMAawBUAHIAYQBuAHMAaQB0AGkAbwBuAHMBAAAAAP////8AAACYAP////sAAAAWAGQAbwBjAGsARQBmAGYAZQBjAHQAcwEAAAAA/////wAAAJgA////+wAAABIAZABvAGMAawBWAGkAZABlAG8BAAABagAAA0EAAAA6AP///wAABKsAAAD2AAAABAAAAAQAAAAIAAAACPwAAAABAAAAAgAAAAEAAAAOAHQAbwBvAGwAQgBhAHIBAAAAAP////8AAAAAAAAAAA=="
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
        self.showDocks([self.dockFiles, self.dockTransitions, self.dockVideo, self.dockEffects, self.dockProperties])

        # Set initial size of docks
        advanced_state = "AAAA/wAAAAD9AAAAAwAAAAAAAAD8AAABQPwCAAAAAfwAAAG/AAABQAAAAKEA////+gAAAAACAAAAAvsAAAAcAGQAbwBjAGsAUAByAG8AcABlAHIAdABpAGUAcwEAAAAA/////wAAAKEA////+wAAABgAZABvAGMAawBLAGUAeQBmAHIAYQBtAGUAAAAAAP////8AAAATAP///wAAAAEAAAEcAAABQPwCAAAAAvsAAAAYAGQAbwBjAGsASwBlAHkAZgByAGEAbQBlAQAAAVgAAAAVAAAAAAAAAAD7AAAAFgBkAG8AYwBrAEUAZgBmAGUAYwB0AHMBAAABvwAAAUAAAACYAP///wAAAAIAAASrAAABkvwBAAAAA/sAAAASAGQAbwBjAGsARgBpAGwAZQBzAQAAAAAAAAFeAAAAcAD////7AAAAHgBkAG8AYwBrAFQAcgBhAG4AcwBpAHQAaQBvAG4AcwEAAAFkAAABAAAAAHAA////+wAAABIAZABvAGMAawBWAGkAZABlAG8BAAACagAAAkEAAAA6AP///wAAAocAAAFAAAAABAAAAAQAAAAIAAAACPwAAAABAAAAAgAAAAEAAAAOAHQAbwBvAGwAQgBhAHIBAAAAAP////8AAAAAAAAAAA=="
        self.restoreState(qt_types.str_to_bytes(advanced_state))
        QCoreApplication.processEvents()

    def actionFreeze_View_trigger(self, event):
        """ Freeze all dockable widgets on the main screen """
        self.freezeDocks()
        self.actionFreeze_View.setVisible(False)
        self.actionUn_Freeze_View.setVisible(True)

    def actionUn_Freeze_View_trigger(self, event):
        """ Un-Freeze all dockable widgets on the main screen """
        self.unFreezeDocks()
        self.actionFreeze_View.setVisible(True)
        self.actionUn_Freeze_View.setVisible(False)

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
        _ = get_app()._tr

        if not profile:
            profile = get_app().project.get(["profile"])

        # Is this a saved project?
        if not get_app().project.current_filepath:
            # Not saved yet
            self.setWindowTitle("%s [%s] - %s" % (_("Untitled Project"), profile, "OpenShot Video Editor"))
        else:
            # Yes, project is saved
            # Get just the filename
            parent_path, filename = os.path.split(get_app().project.current_filepath)
            filename, ext = os.path.splitext(filename)
            filename = filename.replace("_", " ").replace("-", " ").capitalize()
            self.setWindowTitle("%s [%s] - %s" % (filename, profile, "OpenShot Video Editor"))

    # Update undo and redo buttons enabled/disabled to available changes
    def updateStatusChanged(self, undo_status, redo_status):
        log.info('updateStatusChanged')
        self.actionUndo.setEnabled(undo_status)
        self.actionRedo.setEnabled(redo_status)

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
        s.set('window_state', qt_types.bytes_to_str(self.saveState()))
        s.set('window_geometry', qt_types.bytes_to_str(self.saveGeometry()))

    # Get window settings from setting store
    def load_settings(self):
        s = settings.get_settings()

        # Window state and geometry (also toolbar and dock locations)
        if s.get('window_geometry'): self.restoreGeometry(qt_types.str_to_bytes(s.get('window_geometry')))
        if s.get('window_state'): self.restoreState(qt_types.str_to_bytes(s.get('window_state')))

        # Load Recent Projects
        self.load_recent_menu()

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

    def recent_project_clicked(self, file_path):
        """ Load a recent project when clicked """

        # Load project file
        self.open_project(file_path)

    def setup_toolbars(self):
        _ = get_app()._tr  # Get translation function

        # Start undo and redo actions disabled
        self.actionUndo.setEnabled(False)
        self.actionRedo.setEnabled(False)

        # Add files toolbar =================================================================================
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
        self.filesToolbar.addWidget(self.filesFilter)
        self.actionFilesClear.setEnabled(False)
        self.filesToolbar.addAction(self.actionFilesClear)
        self.tabFiles.layout().addWidget(self.filesToolbar)

        # Add transitions toolbar =================================================================================
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
        self.transitionsToolbar.addWidget(self.transitionsFilter)
        self.actionTransitionsClear.setEnabled(False)
        self.transitionsToolbar.addAction(self.actionTransitionsClear)
        self.tabTransitions.layout().addWidget(self.transitionsToolbar)

        # Add effects toolbar =================================================================================
        self.effectsToolbar = QToolBar("Effects Toolbar")
        self.effectsActionGroup = QActionGroup(self)
        self.effectsActionGroup.setExclusive(True)
        self.effectsActionGroup.addAction(self.actionEffectsShowAll)
        self.effectsActionGroup.addAction(self.actionEffectsShowVideo)
        self.effectsActionGroup.addAction(self.actionEffectsShowAudio)
        self.actionEffectsShowAll.setChecked(True)
        self.effectsToolbar.addAction(self.actionEffectsShowAll)
        self.effectsToolbar.addAction(self.actionEffectsShowVideo)
        self.effectsToolbar.addAction(self.actionEffectsShowAudio)
        self.effectsFilter = QLineEdit()
        self.effectsFilter.setObjectName("effectsFilter")
        self.effectsFilter.setPlaceholderText(_("Filter"))
        self.effectsToolbar.addWidget(self.effectsFilter)
        self.actionEffectsClear.setEnabled(False)
        self.effectsToolbar.addAction(self.actionEffectsClear)
        self.tabEffects.layout().addWidget(self.effectsToolbar)

        # Add Video Preview toolbar ==========================================================================
        self.videoToolbar = QToolBar("Video Toolbar")

        # Add left spacer
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.videoToolbar.addWidget(spacer)

        # Playback controls
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

        self.tabVideo.layout().addWidget(self.videoToolbar)

        # Add Timeline toolbar ================================================================================
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
        self.timelineToolbar.addSeparator()

        # Setup Zoom slider
        self.sliderZoom = QSlider(Qt.Horizontal, self)
        self.sliderZoom.setPageStep(2)
        self.sliderZoom.setRange(1, 800)
        self.sliderZoom.setValue(20)
        self.sliderZoom.setInvertedControls(True)
        self.sliderZoom.resize(100, 16)

        self.zoomScaleLabel = QLabel(_("{} seconds").format(self.sliderZoom.value()))

        # add zoom widgets
        self.timelineToolbar.addAction(self.actionTimelineZoomIn)
        self.timelineToolbar.addWidget(self.sliderZoom)
        self.timelineToolbar.addAction(self.actionTimelineZoomOut)
        self.timelineToolbar.addWidget(self.zoomScaleLabel)

        # Add timeline toolbar to web frame
        self.frameWeb.addWidget(self.timelineToolbar)

        # Add spacer and 'New Version Available' toolbar button (default hidden)
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolBar.addWidget(spacer)
        self.toolBar.addAction(self.actionUpdate)

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
            # Display upgrade toolbar button
            self.actionUpdate.setVisible(True)
            self.actionUpdate.setText(_("New Version Available: %s") % version)
            self.actionUpdate.setToolTip(_("New Version Available: %s") % version)

    def moveEvent(self, event):
        """ Move tutorial dialogs also (if any)"""
        if self.tutorial_manager:
            self.tutorial_manager.re_position_dialog()

    def eventFilter(self, object, e):
        """ Filter out certain types of window events """
        if e.type() == QEvent.WindowActivate:
            self.tutorial_manager.re_show_dialog()
        elif e.type() == QEvent.WindowStateChange and self.isMinimized():
            self.tutorial_manager.minimize()

        return False

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

    def FrameExported(self, path, start_frame, end_frame, current_frame):
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


    def __init__(self, mode=None):

        # Create main window base class
        QMainWindow.__init__(self)
        self.mode = mode    # None or unittest (None is normal usage)
        self.initialized = False

        # set window on app for reference during initialization of children
        get_app().window = self
        _ = get_app()._tr

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
        get_app().updates.add_watcher(self)

        # Get current version of OpenShot via HTTP
        self.FoundVersionSignal.connect(self.foundCurrentVersion)
        get_current_Version()

        # Connect signals
        if not self.mode == "unittest":
            self.RecoverBackup.connect(self.recover_backup)

        # Create the timeline sync object (used for previewing timeline)
        self.timeline_sync = TimelineSync(self)

        # Setup timeline
        self.timeline = TimelineWebView(self)
        self.frameWeb.layout().addWidget(self.timeline)

        # Set Window title
        self.SetWindowTitle()

        # Setup files tree
        if s.get("file_view") == "details":
            self.filesTreeView = FilesTreeView(self)
        else:
            self.filesTreeView = FilesListView(self)
        self.tabFiles.layout().addWidget(self.filesTreeView)

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

        # Create lock file
        self.create_lock_file()

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

        # Install event filter
        self.installEventFilter(self)

        # Save settings
        s.save()

        # Refresh frame
        self.refreshFrameSignal.emit()

        # Main window is initialized
        self.initialized = True