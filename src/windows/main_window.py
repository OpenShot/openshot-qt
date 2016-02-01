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
import webbrowser
from copy import deepcopy

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
import openshot  # Python module for libopenshot (required video editing module installed separately)

from windows.views.timeline_webview import TimelineWebView
from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.timeline import TimelineSync
from classes.query import File, Clip, Transition, Marker, Track
from classes.metrics import *
from images import openshot_rc
from windows.views.files_treeview import FilesTreeView
from windows.views.files_listview import FilesListView
from windows.views.transitions_treeview import TransitionsTreeView
from windows.views.transitions_listview import TransitionsListView
from windows.views.effects_treeview import EffectsTreeView
from windows.views.effects_listview import EffectsListView
from windows.views.properties_tableview import PropertiesTableView
from windows.video_widget import VideoWidget
from windows.preview_thread import PreviewParent


class MainWindow(QMainWindow, updates.UpdateWatcher, updates.UpdateInterface):
    """ This class contains the logic for the main window widget """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'main-window.ui')

    previewFrameSignal = pyqtSignal(int)
    refreshFrameSignal = pyqtSignal()
    LoadFileSignal = pyqtSignal(str)
    PlaySignal = pyqtSignal()
    PauseSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)

    # Save window settings on close
    def closeEvent(self, event):

        # Prompt user to save (if needed)
        if get_app().project.needs_save():
            log.info('Prompt user to save project')
            # Translate object
            _ = get_app()._tr

            # Handle exception
            ret = QMessageBox.question(self, _("Unsaved Changes"), _("Save changes to project before closing?"), QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                # Save project
                self.actionSave_trigger(event)
                event.accept()

        # Save settings
        self.save_settings()

        # Track end of session
        track_metric_session(False)

        # Stop threads
        self.preview_thread.kill()

        # Wait for thread
        self.preview_parent.background.wait(250)

    def actionNew_trigger(self, event):
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
            log.error("Couldn't save project {}".format(file_path))
            QMessageBox.warning(self, _("Error Saving Project"), str(ex))

    def open_project(self, file_path):
        """ Open a project from a file path, and refresh the screen """

        app = get_app()
        _ = app._tr  # Get translation function

        try:
            if os.path.exists(file_path.encode('UTF-8')):
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

    def actionOpen_trigger(self, event):
        app = get_app()
        _ = app._tr
        recommended_path = app.project.current_filepath
        if not recommended_path:
            recommended_path = info.HOME_PATH
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
        app = get_app()
        app.updates.undo()

    def actionRedo_trigger(self, event):
        app = get_app()
        app.updates.redo()

    def actionPreferences_trigger(self, event):
        # Show dialog
        from windows.preferences import Preferences
        win = Preferences()
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()
        if result == QDialog.Accepted:
            log.info('Preferences add confirmed')
        else:
            log.info('Preferences add cancelled')

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
            webbrowser.open("http://openshotusers.com/")
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
            webbrowser.open("https://bugs.launchpad.net/openshot/+filebug")
            log.info("Open the Report Bug Launchpad web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the launchpad web page")
            log.info("Unable to open the Report Bug launchpad web page")

    def actionAskQuestion_trigger(self, event):
        try:
            webbrowser.open("https://answers.launchpad.net/openshot/+addquestion")
            log.info("Open the Question launchpad web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Question web page")
            log.info("Unable to open the Question web page")

    def actionTranslate_trigger(self, event):
        try:
            webbrowser.open("https://translations.launchpad.net/openshot")
            log.info("Open the Translate launchpad web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Translation web page")
            log.info("Unable to open the Translation web page")

    def actionDonate_trigger(self, event):
        try:
            webbrowser.open("http://openshot.org/donate/")
            log.info("Open the Donate web page with success")
        except:
            QMessageBox.information(self, "Error !", "Unable to open the Donate web page")
            log.info("Unable to open the Donate web page")

    def actionPlay_trigger(self, event, force=None):

        if force == "pause":
            self.actionPlay.setChecked(False)
        elif force == "play":
            self.actionPlay.setChecked(True)

        if self.actionPlay.isChecked():
            ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
            self.PlaySignal.emit()

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
        track.data = {"number": track_number, "y": 0, "label": ""}
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
        track.data = {"number": max_track_number, "y": 0, "label": ""}
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
        track.data = {"number": max_track_number, "y": 0, "label": ""}
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

        # Loop through all markers, and find the closest one to the left
        closest_position = None
        for marker in Marker.filter():
            marker_position = marker.data["position"]

            # Is marker smaller than position?
            if marker_position < current_position:
                # Is marker larger than previous marker
                if closest_position and marker_position > closest_position:
                    # Set a new closest marker
                    closest_position = marker_position
                elif not closest_position:
                    # First one found
                    closest_position = marker_position

        # Seek to marker position (if any)
        if closest_position:
            # Seek
            frame_to_seek = int(closest_position * fps_float)
            self.SeekSignal.emit(frame_to_seek)

    def actionNextMarker_trigger(self, event):
        log.info("actionNextMarker_trigger")
        log.info(self.preview_thread.current_frame)

        # Calculate current position (in seconds)
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])
        current_position = self.preview_thread.current_frame / fps_float

        # Loop through all markers, and find the closest one to the right
        closest_position = None
        for marker in Marker.filter():
            marker_position = marker.data["position"]

            # Is marker smaller than position?
            if marker_position > current_position:
                # Is marker larger than previous marker
                if closest_position and marker_position < closest_position:
                    # Set a new closest marker
                    closest_position = marker_position
                elif not closest_position:
                    # First one found
                    closest_position = marker_position

        # Seek to marker position (if any)
        if closest_position:
            # Seek
            frame_to_seek = int(closest_position * fps_float)
            self.SeekSignal.emit(frame_to_seek)

    def keyPressEvent(self, event):
        """ Add some shortkey for Player """
        self.key = ""

        # Get the video player object
        player = self.preview_thread.player

        log.info("keyPressEvent: player.Position(): %s" % player.Position())

        # Basic shortcuts i.e just a letter
        if event.key() == Qt.Key_Left:
            # Pause video
            self.actionPlay_trigger(event, force="pause")
            # Set speed to 0
            if player.Speed() != 0:
                self.SpeedSignal.emit(0)
            # Seek to previous frame
            self.SeekSignal.emit(player.Position() - 1)

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif event.key() == Qt.Key_Right:
            # Pause video
            self.actionPlay_trigger(event, force="pause")
            # Set speed to 0
            if player.Speed() != 0:
                self.SpeedSignal.emit(0)
            # Seek to next frame
            self.SeekSignal.emit(player.Position() + 1)

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif event.key() == Qt.Key_Up:
            self.actionPlay.trigger()

        elif event.key() == Qt.Key_Down:
            self.actionPlay.trigger()

        elif event.key() == Qt.Key_C:
            self.actionPlay.trigger()

        elif event.key() == Qt.Key_J:
            self.actionRewind.trigger()
            ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
            self.actionPlay.setChecked(True)

        elif event.key() == Qt.Key_K or event.key() == Qt.Key_Space:
            self.actionPlay.trigger()

            # Notify properties dialog
            self.propertyTableView.select_frame(player.Position())

        elif event.key() == Qt.Key_L:
            self.actionFastForward.trigger()
            ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
            self.actionPlay.setChecked(True)

        elif event.key() == Qt.Key_M:
            self.actionPlay.trigger()

        elif event.key() == Qt.Key_D:
            # Add the Ctrl key
            if event.modifiers() & Qt.ControlModifier:
                self.actionFastForward.trigger()

        elif event.key() == Qt.Key_End:
            # Add the Ctrl key
            if event.modifiers() & Qt.ControlModifier:
                self.actionFastForward.trigger()

        elif event.key() == Qt.Key_Home:
            # Add the Ctrl key
            if event.modifiers() & Qt.ControlModifier:
                self.actionFastForward.trigger()

        elif event.key() == Qt.Key_Delete:
            # Delete selected clip / transition
            self.actionRemoveClip.trigger()
            self.actionRemoveTransition.trigger()

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

        track_id = self.selected_tracks[0]
        max_track_number = len(get_app().project.get(["layers"]))

        # Get details of selected track
        selected_track = Track.get(id=track_id)
        selected_track_number = int(selected_track.data["number"])

        # Revove all clips on this track first
        for clip in Clip.filter(layer=selected_track_number):
            clip.delete()

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
        # Hide fullscreen button, and display exit fullscreen button
        self.actionFullscreen.setVisible(False)
        self.actionExit_Fullscreen.setVisible(True)

    def actionExit_Fullscreen_trigger(self, event):
        # Hide exit fullscreen button, and display fullscreen button
        self.actionExit_Fullscreen.setVisible(False)
        self.actionFullscreen.setVisible(True)

    def actionDetailsView_trigger(self, event):
        log.info("Switch to Details View")

        # Get settings
        app = get_app()
        s = settings.get_settings()

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

    # Init fullscreen menu visibility
    def init_fullscreen_menu(self):
        if self.isFullScreen():
            self.actionFullscreen_trigger(None)
        else:
            self.actionExit_Fullscreen_trigger(None)

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
        # Clear existing selection (if needed)
        if clear_existing:
            if item_type == "clip":
                self.selected_clips.clear()
            elif item_type == "transition":
                self.selected_transitions.clear()
            elif item_type == "effect":
                self.selected_effects.clear()

        if item_type == "clip" and item_id not in self.selected_clips:
            self.selected_clips.append(item_id)
        elif item_type == "transition" and item_id not in self.selected_transitions:
            self.selected_transitions.append(item_id)
        elif item_type == "effect" and item_id not in self.selected_effects:
            self.selected_effects.append(item_id)

        # Change selected item in properties view
        self.propertyTableView.select_item(item_id, item_type)

    # Remove from the selected items
    def removeSelection(self, item_id, item_type):
        if item_type == "clip" and item_id in self.selected_clips:
            self.selected_clips.remove(item_id)
        elif item_type == "transition" and item_id in self.selected_transitions:
            self.selected_transitions.remove(item_id)
        elif item_type == "effect" and item_id in self.selected_effects:
            self.selected_effects.remove(item_id)

        # Move selection to next selected clip (if any)
        if item_type == "clip" and self.selected_clips:
            self.propertyTableView.select_item(self.selected_clips[0], item_type)
        elif item_type == "transition" and self.selected_transitions:
            self.propertyTableView.select_item(self.selected_transitions[0], item_type)
        elif item_type == "effect" and self.selected_effects:
            self.propertyTableView.select_item(self.selected_effects[0], item_type)
        else:
            # Clear selection in properties view
            self.propertyTableView.select_item("", "")

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
        self.timelineToolbar.addSeparator()
        self.timelineToolbar.addAction(self.actionAddMarker)
        self.timelineToolbar.addAction(self.actionPreviousMarker)
        self.timelineToolbar.addAction(self.actionNextMarker)
        self.timelineToolbar.addSeparator()

        # Setup Zoom slider
        self.sliderZoom = QSlider(Qt.Horizontal, self)
        self.sliderZoom.setPageStep(6)
        self.sliderZoom.setRange(8, 200)
        self.sliderZoom.setValue(20)
        self.sliderZoom.setInvertedControls(True)
        # self.sliderZoom.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.sliderZoom.resize(100, 16)

        self.zoomScaleLabel = QLabel(_("{} seconds").format(self.sliderZoom.value()))

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

    def __init__(self):

        # Create main window base class
        QMainWindow.__init__(self)

        # set window on app for reference during initialization of children
        get_app().window = self
        _ = get_app()._tr

        # Track metrics
        track_metric_session()  # start session
        track_metric_screen("main-screen")

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Load user settings for window
        s = settings.get_settings()
        self.recent_menu = None

        # Init UI
        ui_util.init_ui(self)

        # Setup toolbars that aren't on main window, set initial state of items, etc
        self.setup_toolbars()

        # Add window as watcher to receive undo/redo status updates
        get_app().updates.add_watcher(self)

        # Init selection containers
        self.clearSelections()

        # Init fullscreen menu visibility
        self.init_fullscreen_menu()

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
        self.dockPropertiesContent.layout().addWidget(self.propertyTableView, 3, 1)

        # Setup video preview QWidget
        self.videoPreview = VideoWidget()
        self.tabVideo.layout().insertWidget(0, self.videoPreview)

        # Load window state and geometry
        self.load_settings()

        # Create the timeline sync object (used for previewing timeline)
        self.timeline_sync = TimelineSync(self)

        # Start the preview thread
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.timeline_sync.timeline, self.videoPreview)
        self.preview_thread = self.preview_parent.worker