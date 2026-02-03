"""
 @file
 @brief This file loads the Video Export dialog (i.e where is all preferences)
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
import copy
import functools
import locale
import os
import time
import tempfile
import math

import openshot

# Try to get the security-patched XML functions from defusedxml
try:
    from defusedxml import minidom as xml
except ImportError:
    from xml.dom import minidom as xml

from xml.parsers.expat import ExpatError

from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QSize, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QMessageBox, QDialog, QFileDialog, QDialogButtonBox, QPushButton, QWidget, QLineEdit, QComboBox, QSpinBox, QCheckBox
)
from PyQt5.QtGui import QIcon
from functools import partial
from classes import info
from classes import ui_util
from classes import openshot_rc  # noqa
from classes.logger import log
from classes.app import get_app
from classes.metrics import track_metric_screen, track_metric_error
from classes.query import File

import json


class Export(QDialog):
    """ Export Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'export.ui')

    ExportStarted = pyqtSignal(str, int, int)
    ExportFrame = pyqtSignal(str, int, int, int, str)
    ExportEnded = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations & settings
        _ = get_app()._tr
        self.s = get_app().get_settings()

        track_metric_screen("export-screen")

        # Dynamically load tabs from settings data
        self.settings_data = self.s.get_all_settings()

        # Add buttons to interface
        self.cancel_button = QPushButton(_('Cancel'))
        self.cancel_button.setObjectName("cancelButton")
        self.export_button = QPushButton(_('Export Video'))
        self.export_button.setObjectName("acceptButton")
        self.close_button = QPushButton(_('Done'))
        self.restoring_defaults = False
        self.restore_defaults_button.clicked.connect(self.restore_defaults)

        self.buttonBox.addButton(self.close_button, QDialogButtonBox.RejectRole)
        self.buttonBox.addButton(self.export_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.RejectRole)
        self.close_button.setVisible(False)
        self.exporting = False
        self.vbr = {}
        self.abr = {}

        # Pause playback
        get_app().window.PauseSignal.emit()

        # Hide audio channels
        self.lblChannels.setVisible(False)
        self.txtChannels.setVisible(False)

        # Set OMP thread disabled flag (for stability)
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = True

        # Copy project (so we don't change data in our current project)
        self.project = copy.deepcopy(get_app().project)

        # Clear timeline preview cache (to get more available memory)
        self.old_cache_object = None
        project_timeline = get_app().window.timeline_sync.timeline
        if get_app().window.cache_object:
            self.old_cache_object = get_app().window.cache_object
            get_app().window.cache_object = openshot.CacheMemory(1 * 1024 * 1024) # 1 MB (limit cache for main project during export)
            project_timeline.SetCache(get_app().window.cache_object)
            self.old_cache_object.Clear()

        # Create cache thread
        self.cache_thread = openshot.VideoCacheThread()

        # Get the original timeline settings
        width = int(project_timeline.info.width)
        height = int(project_timeline.info.height)
        fps = project_timeline.info.fps
        sample_rate = int(project_timeline.info.sample_rate)
        channels = int(project_timeline.info.channels)
        channel_layout = int(project_timeline.info.channel_layout)

        # Create new "export" openshot.Timeline object
        self.timeline = openshot.Timeline(
            width, height, openshot.Fraction(fps.num, fps.den),
            sample_rate, channels, channel_layout)
        # Init various properties
        self.timeline.info.sample_rate = sample_rate
        self.timeline.info.channels = channels
        self.timeline.info.channel_layout = channel_layout
        self.timeline.info.has_audio = project_timeline.info.has_audio
        self.timeline.info.has_video = project_timeline.info.has_video
        self.timeline.info.video_length = project_timeline.info.video_length
        self.timeline.info.duration = project_timeline.info.duration

        # Load the "export" Timeline reader with the JSON from the real timeline
        try:
            json_timeline = json.dumps(self.project._data)
            self.timeline.SetJson(json_timeline)
        except Exception as ex:
            msg = QMessageBox()
            msg.setWindowTitle(_("Project Data Error"))
            msg.setText(_("Sorry, an error was encountered while parsing your project data: \n'%(error)s'.\n\n"
                          "Please save your project and inspect in a JSON editor to repair." %
                          {"error": str(ex)}))
            msg.exec_()
            return

        # Open the "export" Timeline reader
        self.timeline.Open()

        # Default export path
        recommended_path = self.s.getDefaultPath(self.s.actionType.EXPORT)
        self.txtExportFolder.setText(recommended_path)

        # Is this a saved project?
        if not get_app().project.current_filepath:
            # Not saved yet
            self.txtFileName.setText(_("Untitled Project"))
        else:
            # Yes, project is saved
            # Get just the filename
            filename = os.path.basename(get_app().project.current_filepath)
            filename = os.path.splitext(filename)[0]
            self.txtFileName.setText(filename)

        # Default image type
        self.txtImageFormat.setText("-%05d.png")

        # Loop through Export To options
        export_options = [_("Video & Audio"), _("Video Only"), _("Audio Only"), _("Image Sequence")]
        for option in export_options:
            # append profile to list
            self.cboExportTo.addItem(option)

        # Add channel layouts
        self.channel_layout_choices = []
        for layout in [(openshot.LAYOUT_MONO, _("Mono (1 Channel)")),
                       (openshot.LAYOUT_STEREO, _("Stereo (2 Channel)")),
                       (openshot.LAYOUT_SURROUND, _("Surround (3 Channel)")),
                       (openshot.LAYOUT_5POINT1, _("Surround (5.1 Channel)")),
                       (openshot.LAYOUT_7POINT1, _("Surround (7.1 Channel)"))]:
            log.info(layout)
            self.channel_layout_choices.append(layout[0])
            self.cboChannelLayout.addItem(layout[1], layout[0])

        # Connect signals
        self.btnBrowse.clicked.connect(functools.partial(self.btnBrowse_clicked))
        self.cboSimpleProjectType.currentIndexChanged.connect(
            functools.partial(self.cboSimpleProjectType_index_changed, self.cboSimpleProjectType))
        self.cboProfile.currentIndexChanged.connect(functools.partial(self.cboProfile_index_changed, self.cboProfile))
        self.cboSimpleTarget.currentIndexChanged.connect(
            functools.partial(self.cboSimpleTarget_index_changed, self.cboSimpleTarget))
        self.cboSimpleVideoProfile.currentIndexChanged.connect(
            functools.partial(self.cboSimpleVideoProfile_index_changed, self.cboSimpleVideoProfile))
        self.cboSimpleQuality.currentIndexChanged.connect(
            functools.partial(self.cboSimpleQuality_index_changed, self.cboSimpleQuality))
        self.cboChannelLayout.currentIndexChanged.connect(self.updateChannels)
        self.ExportFrame.connect(self.updateProgressBar)
        self.btnBrowseProfiles.clicked.connect(self.btnBrowseProfiles_clicked)
        self.checkStartFirstClip.toggled.connect(partial(self.updateFrameRate, True))
        self.checkEndLastClip.toggled.connect(partial(self.updateFrameRate, True))

        # ********* Advanced Profile List **********
        # Loop through profiles
        self.profile_names = []
        self.profile_paths = {}
        self.current_project_profile = get_app().project.get(['profile'])
        self.selected_profile = None
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in reversed(sorted(os.listdir(profile_folder))):
                profile_path = os.path.join(profile_folder, file)
                if os.path.isdir(profile_path):
                    continue
                try:
                    # Load Profile
                    profile = openshot.Profile(profile_path)

                    # Add description of Profile to list
                    profile_name = f"{profile.info.description} ({profile.info.width}x{profile.info.height})"
                    self.profile_names.append(profile_name)
                    self.profile_paths[profile_name] = profile_path

                    # Add to dropdown
                    self.cboProfile.addItem(
                        self.getProfileName(self.getProfilePath(profile_name)), self.getProfilePath(profile_name))

                    # Set default profile (if it matches the project)
                    if self.current_project_profile == profile.info.description:
                        self.selected_profile = profile_name

                except RuntimeError as e:
                    # This exception occurs when there's a problem parsing the Profile file - display a message and continue
                    log.error("Failed to parse file '%s' as a profile: %s" % (profile_path, e))

        # ********* Simple Project Type **********
        # load the simple project type dropdown
        presets = []

        for preset_folder in [info.EXPORT_PRESETS_PATH, info.USER_PRESETS_PATH]:
            for file in os.listdir(preset_folder):
                preset_path = os.path.join(preset_folder, file)
                try:
                    xmldoc = xml.parse(preset_path)
                    type = xmldoc.getElementsByTagName("type")
                    presets.append(_(type[0].childNodes[0].data))

                except ExpatError as e:
                    # This indicates an invalid Preset file - display an error and continue
                    log.error("Failed to parse file '%s' as a preset: %s" % (preset_path, e))

        # Add first project type (always add this one first)
        all_formats_text = _("All Formats")
        self.cboSimpleProjectType.addItem(all_formats_text, all_formats_text)

        # Add remaining project types (exclude duplicates)
        presets = list(set(presets))
        for item in sorted(presets):
            if item != all_formats_text:
                self.cboSimpleProjectType.addItem(item, item)

        # Always select 'All Formats' option
        self.cboSimpleProjectType.setCurrentIndex(0)

        # Populate all profiles
        self.populateAllProfiles(get_app().project.get(['profile']))

        # Connect framerate signals
        self.txtFrameRateNum.valueChanged.connect(self.updateFrameRate)
        self.txtFrameRateDen.valueChanged.connect(self.updateFrameRate)
        self.txtWidth.valueChanged.connect(self.updateFrameRate)
        self.txtHeight.valueChanged.connect(self.updateFrameRate)
        self.txtSampleRate.valueChanged.connect(self.updateFrameRate)
        self.txtChannels.valueChanged.connect(self.updateFrameRate)
        self.cboChannelLayout.currentIndexChanged.connect(self.updateFrameRate)

        # Determine the length of the timeline (in frames)
        self.updateFrameRate()

        # Load previous settings (if any)
        self.load_settings()

    def restore_defaults(self):
        """
        Restore defaults by closing and reopening the dialog.
        """
        # Clear the saved settings
        get_app().updates.ignore_history = True
        get_app().updates.update(["export_settings"], None)
        get_app().updates.ignore_history = False

        log.info("Cleared last-export_settings.")

        # Close the current dialog
        self.restoring_defaults = True
        self.close()

        # Re-open the export dialog (calling the dialog anew)
        QTimer.singleShot(0, get_app().window.actionExportVideo.trigger)

    def getProfilePath(self, profile_name):
        """Get the profile path that matches the name"""
        for profile, path in self.profile_paths.items():
            if profile_name in profile:
                return path

    def getProfileName(self, profile_path):
        """Get the profile name that matches the name"""
        for profile, path in self.profile_paths.items():
            if profile_path == path:
                return profile

    @pyqtSlot(str, int, int, int, str)
    def updateProgressBar(self, title_message, start_frame, end_frame, current_frame, format_of_progress_string):
        """Update progress bar during exporting"""
        if end_frame - start_frame > 0:
            percentage_string = format_of_progress_string % (( current_frame - start_frame ) / ( end_frame - start_frame ) * 100)
        else:
            percentage_string = "100%"
        self.progressExportVideo.setValue(int(current_frame))
        self.progressExportVideo.setFormat(percentage_string)
        self.setWindowTitle("%s %s" % (percentage_string, title_message))

    def updateChannels(self):
        """Update the # of channels to match the channel layout"""
        log.info("updateChannels")
        channels = self.txtChannels.value()
        channel_layout = self.cboChannelLayout.currentData()

        if channel_layout == openshot.LAYOUT_MONO:
            channels = 1
        elif channel_layout == openshot.LAYOUT_STEREO:
            channels = 2
        elif channel_layout == openshot.LAYOUT_SURROUND:
            channels = 3
        elif channel_layout == openshot.LAYOUT_5POINT1:
            channels = 6
        elif channel_layout == openshot.LAYOUT_7POINT1:
            channels = 8

        # Update channels to match layout
        self.txtChannels.setValue(channels)

    def updateFrameRate(self, set_limits=True):
        """Callback for changing the frame rate"""
        # Adjust the main timeline reader
        self.timeline.info.width = self.txtWidth.value()
        self.timeline.info.height = self.txtHeight.value()
        self.timeline.info.fps.num = self.txtFrameRateNum.value()
        self.timeline.info.fps.den = self.txtFrameRateDen.value()
        self.timeline.info.sample_rate = self.txtSampleRate.value()
        self.timeline.info.channels = self.txtChannels.value()
        self.timeline.info.channel_layout = self.cboChannelLayout.currentData()

        # Disable audio (if not needed)
        if self.timeline.info.sample_rate == 0 or self.timeline.info.channels == 0:
            self.timeline.info.has_audio = False
        else:
            self.timeline.info.has_audio = True

        if set_limits:
            if self.checkEndLastClip.isChecked():
                # Set end frame to last clip (right edge)
                timeline_length_int = self.timeline.GetMaxFrame()
            else:
                # Set end frame to project length (full timeline)
                timeline_length_int = self.timeline.info.video_length

            if self.checkStartFirstClip.isChecked():
                # Set the start frame to the first clip position
                timeline_start_int = self.timeline.GetMinFrame()
            else:
                # Set the start frame to the start of the project (0.0)
                timeline_start_int = 1

            # Set the min and max frame numbers for this project
            self.txtStartFrame.setValue(timeline_start_int)
            self.txtEndFrame.setValue(timeline_length_int)

        # Calculate differences between editing/preview FPS and export FPS
        current_fps = get_app().project.get("fps")
        current_fps_float = float(current_fps["num"]) / float(current_fps["den"])
        new_fps_float = float(self.txtFrameRateNum.value()) / float(self.txtFrameRateDen.value())
        self.export_fps_factor = new_fps_float / current_fps_float
        self.original_fps_factor = current_fps_float / new_fps_float

    def cboSimpleProjectType_index_changed(self, widget, index):
        selected_project = widget.itemData(index)

        # set the target dropdown based on the selected project type
        # first clear the combo
        self.cboSimpleTarget.clear()

        # get translations
        _ = get_app()._tr

        # parse the xml files and get targets that match the project type
        project_types = []
        acceleration_types = {}
        for preset_folder in [info.EXPORT_PRESETS_PATH, info.USER_PRESETS_PATH]:
            for file in os.listdir(preset_folder):
                preset_path = os.path.join(preset_folder, file)
                try:
                    xmldoc = xml.parse(preset_path)
                    type = xmldoc.getElementsByTagName("type")

                    if _(type[0].childNodes[0].data) == selected_project:
                        titles = xmldoc.getElementsByTagName("title")
                        videocodecs = xmldoc.getElementsByTagName("videocodec")
                        for title in titles:
                            project_types.append(_(title.childNodes[0].data))
                        for codec in videocodecs:
                            codec_text = ""
                            if codec.childNodes:
                                codec_text = codec.childNodes[0].data
                            if "vaapi" in codec_text and openshot.FFmpegWriter.IsValidCodec(codec_text):
                                acceleration_types[_(title.childNodes[0].data)] = QIcon(":/hw/hw-accel-vaapi.svg")
                            elif "nvenc" in codec_text and openshot.FFmpegWriter.IsValidCodec(codec_text):
                                acceleration_types[_(title.childNodes[0].data)] = QIcon(":/hw/hw-accel-nvenc.svg")
                            elif "dxva2" in codec_text and openshot.FFmpegWriter.IsValidCodec(codec_text):
                                acceleration_types[_(title.childNodes[0].data)] = QIcon(":/hw/hw-accel-dx.svg")
                            elif "videotoolbox" in codec_text and openshot.FFmpegWriter.IsValidCodec(codec_text):
                                acceleration_types[_(title.childNodes[0].data)] = QIcon(":/hw/hw-accel-vtb.svg")
                            elif "qsv" in codec_text and openshot.FFmpegWriter.IsValidCodec(codec_text):
                                acceleration_types[_(title.childNodes[0].data)] = QIcon(":/hw/hw-accel-qsv.svg")
                            elif openshot.FFmpegWriter.IsValidCodec(codec_text) or codec_text == "":
                                acceleration_types[_(title.childNodes[0].data)] = QIcon(":/hw/hw-accel-none.svg")

                except ExpatError as e:
                    # This indicates an invalid Preset file - display an error and continue
                    log.error("Failed to parse file '%s' as a preset: %s" % (preset_path, e))

                # Free up DOM memory
                xmldoc.unlink()

        # Add all targets for selected project type
        preset_index = 0
        selected_preset = 0
        for item in sorted(project_types):
            icon = acceleration_types.get(item)
            if icon:
                self.cboSimpleTarget.setIconSize(QSize(60, 18))
                self.cboSimpleTarget.addItem(icon, item, item)
            else:
                continue

            # Find index of MP4/H.264
            if item == _("MP4 (h.264)"):
                selected_preset = preset_index

            preset_index += 1

        # Select MP4/H.264 as default
        self.cboSimpleTarget.setCurrentIndex(selected_preset)

    def cboProfile_index_changed(self, widget, index):
        selected_profile_path = widget.itemData(index)
        log.info(selected_profile_path)

        # get translations
        _ = get_app()._tr

        # Load profile
        profile = openshot.Profile(selected_profile_path)

        # Load profile settings into advanced editor
        self.txtWidth.setValue(profile.info.width)
        self.txtHeight.setValue(profile.info.height)
        self.txtFrameRateDen.setValue(profile.info.fps.den)
        self.txtFrameRateNum.setValue(profile.info.fps.num)
        self.txtAspectRatioNum.setValue(profile.info.display_ratio.num)
        self.txtAspectRatioDen.setValue(profile.info.display_ratio.den)
        self.txtPixelRatioNum.setValue(profile.info.pixel_ratio.num)
        self.txtPixelRatioDen.setValue(profile.info.pixel_ratio.den)

        # Load the interlaced options
        self.cboInterlaced.clear()
        self.cboInterlaced.addItem(_("No"), "No")
        self.cboInterlaced.addItem(_("Yes Top field first"), "Yes")
        self.cboInterlaced.addItem(_("Yes Bottom field first"), "Yes")
        if profile.info.interlaced_frame:
            self.cboInterlaced.setCurrentIndex(1)
        else:
            self.cboInterlaced.setCurrentIndex(0)

        # Load the 360° / Spherical options
        self.cboSpherical.clear()
        self.cboSpherical.addItem(_("No"), 0)
        self.cboSpherical.addItem(_("Yes"), 1)
        if hasattr(profile.info, "spherical") and profile.info.spherical:
            self.cboSpherical.setCurrentIndex(1)
        else:
            self.cboSpherical.setCurrentIndex(0)

        self.update_all_formats_bitrates()

    def cboSimpleTarget_index_changed(self, widget, index):
        selected_target = widget.itemData(index)
        log.info(selected_target)

        # get translations
        _ = get_app()._tr

        # don't do anything if the combo has been cleared
        if selected_target:
            profiles_list = []
            v_l = v_m = v_h = a_l = a_m = a_h = None

            # Clear the following options (and remember current settings)
            previous_quality = self.cboSimpleQuality.currentIndex()
            if previous_quality < 0:
                previous_quality = self.cboSimpleQuality.count() - 1
            previous_profile = self.cboSimpleVideoProfile.currentText()
            if previous_profile:
                self.selected_profile = previous_profile
            self.cboSimpleVideoProfile.clear()
            self.cboSimpleQuality.clear()

            # parse the xml to return suggested profiles
            profile_index = 0
            all_profiles = False
            for preset_folder in [info.EXPORT_PRESETS_PATH, info.USER_PRESETS_PATH]:
                for file in os.listdir(preset_folder):
                    preset_path = os.path.join(preset_folder, file)
                    try:
                        xmldoc = xml.parse(preset_path)
                        title = xmldoc.getElementsByTagName("title")
                        if _(title[0].childNodes[0].data) == selected_target:
                            profiles = xmldoc.getElementsByTagName("projectprofile")

                            # get the basic profile
                            all_profiles = False
                            if profiles:
                                # Disable profile filter button
                                self.btnBrowseProfiles.setEnabled(False)

                                # if profiles are defined, show them
                                for profile in profiles:
                                    profiles_list.append(_(profile.childNodes[0].data))
                                profiles_list = sorted(profiles_list)
                            else:
                                # show all profiles
                                all_profiles = True

                                # Enable profile filter button
                                self.btnBrowseProfiles.setEnabled(True)
                                for profile_name in self.profile_names:
                                    profiles_list.append(profile_name)

                            # Allow targets to override the following setting (export to)
                            # Export to:  "Video & Audio", "Video Only", "Audio Only", "Image Sequence"
                            # Default to "Video & Audio" if XML export-to element missing
                            export_to_options = [_("Video & Audio"), _("Video Only"),
                                                 _("Audio Only"), _("Image Sequence")]
                            export_to = export_to_options[0]
                            if xmldoc.getElementsByTagName("export-to"):
                                export_to = _(xmldoc.getElementsByTagName("export-to")[0].childNodes[0].data)
                            if export_to in export_to_options:
                                self.cboExportTo.setCurrentIndex(export_to_options.index(export_to))

                            # get the video bit rate(s)
                            videobitrate = xmldoc.getElementsByTagName("videobitrate")
                            for rate in videobitrate:
                                v_l = rate.attributes["low"].value
                                v_m = rate.attributes["med"].value
                                v_h = rate.attributes["high"].value
                                self.vbr = {_("Low"): v_l, _("Med"): v_m, _("High"): v_h}

                            # get the audio bit rates
                            audiobitrate = xmldoc.getElementsByTagName("audiobitrate")
                            for audiorate in audiobitrate:
                                a_l = audiorate.attributes["low"].value
                                a_m = audiorate.attributes["med"].value
                                a_h = audiorate.attributes["high"].value
                                self.abr = {_("Low"): a_l, _("Med"): a_m, _("High"): a_h}

                            # get the remaining values
                            vf = xmldoc.getElementsByTagName("videoformat")
                            self.txtVideoFormat.setText(vf[0].childNodes[0].data)
                            vc = xmldoc.getElementsByTagName("videocodec")
                            if vc[0].childNodes:
                                self.txtVideoCodec.setText(vc[0].childNodes[0].data)
                            else:
                                self.txtVideoCodec.setText("")
                            sr = xmldoc.getElementsByTagName("samplerate")
                            self.txtSampleRate.setValue(int(sr[0].childNodes[0].data))
                            c = xmldoc.getElementsByTagName("audiochannels")
                            self.txtChannels.setValue(int(c[0].childNodes[0].data))
                            c = xmldoc.getElementsByTagName("audiochannellayout")

                            # check for compatible audio codec
                            ac = xmldoc.getElementsByTagName("audiocodec")
                            if ac[0].childNodes:
                                audio_codec_name = ac[0].childNodes[0].data
                                if audio_codec_name == "aac":
                                    # Determine which version of AAC encoder is available
                                    if openshot.FFmpegWriter.IsValidCodec("libfaac"):
                                        self.txtAudioCodec.setText("libfaac")
                                    elif openshot.FFmpegWriter.IsValidCodec("libvo_aacenc"):
                                        self.txtAudioCodec.setText("libvo_aacenc")
                                    elif openshot.FFmpegWriter.IsValidCodec("aac"):
                                        self.txtAudioCodec.setText("aac")
                                    else:
                                        # fallback audio codec
                                        self.txtAudioCodec.setText("ac3")
                                else:
                                    # fallback audio codec
                                    self.txtAudioCodec.setText(audio_codec_name)
                            else:
                                # no valid audio codec
                                self.txtAudioCodec.setText("")

                            for layout_index, layout in enumerate(self.channel_layout_choices):
                                if layout == int(c[0].childNodes[0].data):
                                    self.cboChannelLayout.setCurrentIndex(layout_index)
                                    break

                        # Free up DOM memory
                        xmldoc.unlink()

                    except ExpatError as e:
                        # This indicates an invalid Preset file - display an error and continue
                        log.error("Failed to parse file '%s' as a preset: %s" % (preset_path, e))

            # init the profiles combo
            for item in profiles_list:
                self.cboSimpleVideoProfile.addItem(
                    self.getProfileName(self.getProfilePath(item)), self.getProfilePath(item))

            # select the project's current profile
            profile_index = self.getVideoProfileIndex(self.selected_profile)
            if profile_index != -1:
                # Re-select project profile (if found in list)
                self.cboSimpleVideoProfile.setCurrentIndex(profile_index)
            else:
                # Previous profile not in list, so
                # default to first profile in list
                self.cboSimpleVideoProfile.setCurrentIndex(0)

            # set the quality combo
            # only populate with quality settings that exist
            if v_l or a_l:
                self.cboSimpleQuality.addItem(_("Low"), "Low")
            if v_m or a_m:
                self.cboSimpleQuality.addItem(_("Med"), "Med")
            if v_h or a_h:
                self.cboSimpleQuality.addItem(_("High"), "High")

            # Dynamically scale All Formats bitrates to the selected profile
            self.update_all_formats_bitrates()

            # Default to the highest quality setting (or previous quality setting)
            if previous_quality <= self.cboSimpleQuality.count() - 1:
                self.cboSimpleQuality.setCurrentIndex(previous_quality)
            else:
                self.cboSimpleQuality.setCurrentIndex(self.cboSimpleQuality.count() - 1)

    def getVideoProfileIndex(self, profile_name=None, profile_key=None):
        """Get the index of a profile name or profile key (-1 if not found)"""
        if profile_name:
            for index in range(self.cboSimpleVideoProfile.count()):
                combo_profile = self.cboSimpleVideoProfile.itemText(index)
                if combo_profile == profile_name:
                    return index
            return -1
        if profile_key:
            for index in range(self.cboSimpleVideoProfile.count()):
                combo_profile_path = self.cboSimpleVideoProfile.itemData(index)
                combo_profile = openshot.Profile(combo_profile_path)
                if combo_profile.Key() == profile_key:
                    return index
            return -1

    def cboSimpleVideoProfile_index_changed(self, widget, index):
        selected_profile_path = widget.itemData(index)
        log.info(selected_profile_path)

        # Populate the advanced profile list
        self.populateAllProfiles(selected_profile_path)
        self.update_all_formats_bitrates()

    def populateAllProfiles(self, selected_profile_path):
        """Populate the full list of profiles"""
        # Look for matching profile in advanced options
        for profile_index, profile_name in enumerate(self.profile_names):
            # Check for matching profile
            if self.getProfilePath(profile_name) == selected_profile_path:
                # Matched!
                self.cboProfile.setCurrentIndex(profile_index)
                break

    def cboSimpleQuality_index_changed(self, widget, index):
        selected_quality = widget.itemData(index)
        log.info(selected_quality)

        # get translations
        _ = get_app()._tr

        # Update dynamic bitrate (only used for All Formats)
        self.update_all_formats_bitrates()

        # Set the video and audio bitrates
        if selected_quality:
            self.txtVideoBitRate.setText(_(self.vbr[_(selected_quality)]))
            self.txtAudioBitrate.setText(_(self.abr[_(selected_quality)]))

    def btnBrowse_clicked(self):
        log.info("btnBrowse_clicked")

        # get translations
        _ = get_app()._tr
        default_path = self.s.getDefaultPath(self.s.actionType.EXPORT)

        # update export folder path
        file_path = QFileDialog.getExistingDirectory(self,
                                                     _("Choose a Folder..."),
                                                     default_path)

        # Don't change path if chosen path isn't valid
        if os.path.exists(file_path):
            self.s.setDefaultPath(self.s.actionType.EXPORT, file_path)
            self.txtExportFolder.setText(file_path)

    def btnBrowseProfiles_clicked(self):
        """Search profile button clicked"""
        # Get current selection profile object
        current_profile = openshot.Profile(self.cboSimpleVideoProfile.currentData())

        # Show dialog (init to current selection)
        from windows.profile import Profile
        log.debug("Showing profile dialog")
        win = Profile(current_profile.Key())
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()

        profile = win.selected_profile
        if result == QDialog.Accepted and profile:

            # select the project's current profile
            profile_index = self.getVideoProfileIndex(profile_key=profile.Key())
            if profile_index != -1:
                # Re-select project profile (if found in list)
                self.cboSimpleVideoProfile.setCurrentIndex(profile_index)
            else:
                # Previous profile not in list, so
                # default to first profile in list
                self.cboSimpleVideoProfile.setCurrentIndex(0)

    def convert_to_bytes(self, BitRateString):
        bit_rate_bytes = 0

        # split the string into pieces
        s = BitRateString.lower().split(" ")
        measurement = "kb"

        try:
            # Get Bit Rate
            if len(s) >= 2:
                raw_number_string = s[0]
                raw_measurement = s[1]

                # convert string number to float (based on locale settings)
                raw_number = locale.atof(raw_number_string)

                if "kb" in raw_measurement:
                    # Kbit to bytes
                    bit_rate_bytes = raw_number * 1000.0

                elif "mb" in raw_measurement:
                    # Mbit to bytes
                    bit_rate_bytes = raw_number * 1000.0 * 1000.0

                elif ("crf" in raw_measurement) or ("cqp" in raw_measurement):
                    # Just a number
                    if raw_number > 63:
                        raw_number = 63
                    if raw_number < 0:
                        raw_number = 0
                    bit_rate_bytes = raw_number

                elif "qp" in raw_measurement:
                    # Just a number
                    if raw_number > 255:
                        raw_number = 255
                    if raw_number < 0:
                        raw_number = 0
                    bit_rate_bytes = raw_number

        except:
            log.warning('Failed to convert bitrate string to bytes: %s' % BitRateString)

        # return the bit rate in bytes
        return str(int(bit_rate_bytes))

    def disableControls(self):
        """Disable all controls"""
        self.lblFileName.setEnabled(False)
        self.txtFileName.setEnabled(False)
        self.lblFolderPath.setEnabled(False)
        self.txtExportFolder.setEnabled(False)
        self.exportTabs.setEnabled(False)
        self.export_button.setEnabled(False)
        self.btnBrowse.setEnabled(False)

    def enableControls(self):
        """Enable all controls"""
        self.lblFileName.setEnabled(True)
        self.txtFileName.setEnabled(True)
        self.lblFolderPath.setEnabled(True)
        self.txtExportFolder.setEnabled(True)
        self.exportTabs.setEnabled(True)
        self.export_button.setEnabled(True)
        self.btnBrowse.setEnabled(True)

    def run_export(self, export_file_path, video_settings, audio_settings, export_type,
                   video_bitrate_text=None, profile_path_for_rescale=None):
        """
        Run the encode loop. Uses self.timeline, self.project, self.cache_thread.
        video_bitrate_text: optional string for crf/cqp/qp (e.g. "23 crf"); if None, only numeric bitrate is used.
        profile_path_for_rescale: optional path to profile when export_fps_factor != 1; if None and rescale needed, resolved from project profile.
        """
        _ = get_app()._tr

        def titlestring(sec, fps, mess):
            formatstr = "%(hours)d:%(minutes)02d:%(seconds)02d " + mess + " (%(fps)5.2f FPS)"
            return _(formatstr) % {
                'hours': sec / 3600,
                'minutes': (sec / 60) % 60,
                'seconds': sec % 60,
                'fps': fps}

        if video_bitrate_text is None:
            video_bitrate_text = ""

        # Progress bar if present
        if hasattr(self, 'progressExportVideo') and self.progressExportVideo is not None:
            self.progressExportVideo.setMinimum(int(video_settings.get("start_frame")))
            self.progressExportVideo.setMaximum(int(video_settings.get("end_frame")))
            self.progressExportVideo.setValue(int(video_settings.get("start_frame")))

        # Set lossless cache settings (temporarily)
        export_cache_object = openshot.CacheMemory(250 * 1024 * 1024)
        self.timeline.SetCache(export_cache_object)

        # Compute export_fps_factor from project and video_settings
        current_fps = get_app().project.get("fps") or {"num": 30, "den": 1}
        current_fps_float = float(current_fps.get("num", 30)) / float(current_fps.get("den", 1) or 1)
        fps_num = video_settings.get("fps", {}).get("num", 30)
        fps_den = video_settings.get("fps", {}).get("den", 1) or 1
        new_fps_float = float(fps_num) / float(fps_den)
        export_fps_factor = new_fps_float / current_fps_float

        # Rescale all keyframes (if needed)
        if export_fps_factor != 1.0:
            self.project.rescale_keyframes(export_fps_factor)
            path_to_use = profile_path_for_rescale
            if not path_to_use and hasattr(self, 'cboSimpleVideoProfile') and self.cboSimpleVideoProfile is not None:
                path_to_use = self.cboSimpleVideoProfile.currentData()
            if not path_to_use:
                # Resolve from project profile name
                profile_name = get_app().project.get("profile")
                for folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
                    if not os.path.isdir(folder):
                        continue
                    for f in os.listdir(folder):
                        p = os.path.join(folder, f)
                        if os.path.isfile(p):
                            try:
                                prof = openshot.Profile(p)
                                if prof.info.description == profile_name:
                                    path_to_use = p
                                    break
                            except Exception:
                                pass
                    if path_to_use:
                        break
            if path_to_use:
                profile = openshot.Profile(path_to_use)
                self.project.apply_profile(profile)
                self.timeline.SetJson(json.dumps(self.project._data))

        # Set timeline info from settings (no UI dependency)
        self.timeline.info.width = video_settings.get("width")
        self.timeline.info.height = video_settings.get("height")
        self.timeline.info.fps.num = video_settings.get("fps", {}).get("num", 30)
        self.timeline.info.fps.den = video_settings.get("fps", {}).get("den", 1) or 1
        self.timeline.info.sample_rate = audio_settings.get("sample_rate", 48000)
        self.timeline.info.channels = audio_settings.get("channels", 2)
        self.timeline.info.channel_layout = audio_settings.get("channel_layout", openshot.LAYOUT_STEREO)
        if self.timeline.info.sample_rate == 0 or self.timeline.info.channels == 0:
            self.timeline.info.has_audio = False
        else:
            self.timeline.info.has_audio = True
        # Headless export: force no audio before cache/writer so we never open an audio codec.
        if getattr(self, "_headless", False):
            self.timeline.info.has_audio = False

        # Set MaxSize and apply mappers
        self.timeline.SetMaxSize(video_settings.get("width"), video_settings.get("height"))
        self.timeline.ApplyMapperToClips()

        max_frame = 0
        format_of_progress_string = "%4.1f%% "
        fps_encode = 0

        # Start video cache thread
        self.cache_thread.Reader(self.timeline)
        self.cache_thread.setSpeed(1)
        self.cache_thread.StartThread()

        try:
            w = openshot.FFmpegWriter(export_file_path)

            if export_type in [_("Video & Audio"), _("Video Only"), _("Image Sequence")]:
                # Coerce to exact C++ types (bool, std::string, Fraction, int, int, Fraction, bool, bool, int)
                vc = video_settings.get("vcodec") or "libx264"
                if not isinstance(vc, str):
                    vc = str(vc)
                fps_dict = video_settings.get("fps") or {}
                fps_num = int(fps_dict.get("num", 30))
                fps_den = int(fps_dict.get("den", 1) or 1)
                pr_dict = video_settings.get("pixel_ratio") or {}
                pr_num = int(pr_dict.get("num", 1))
                pr_den = int(pr_dict.get("den", 1) or 1)
                video_bps = _parse_bitrate_to_bps(video_settings.get("video_bitrate"))
                w.SetVideoOptions(
                    True,
                    vc,
                    openshot.Fraction(fps_num, fps_den),
                    int(video_settings.get("width", 1920)),
                    int(video_settings.get("height", 1080)),
                    openshot.Fraction(pr_num, pr_den),
                    bool(video_settings.get("interlace", False)),
                    bool(video_settings.get("topfirst", False)),
                    video_bps,
                )

            in_audio_block = export_type in [_("Video & Audio"), _("Audio Only")]
            # Headless export (e.g. from AI chat): skip audio to avoid "Could not open audio codec" on systems
            # where no encoder works reliably; export video-only so the user always gets a file.
            headless_skip_audio = getattr(self, "_headless", False)
            if in_audio_block and not headless_skip_audio:
                ac = audio_settings.get("acodec") or "aac"
                if not isinstance(ac, str):
                    ac = str(ac)
                ac = _resolve_audio_codec(ac)
                if ac is not None:
                    audio_bps = _parse_bitrate_to_bps(audio_settings.get("audio_bitrate"), default=192000)
                    sr = int(audio_settings.get("sample_rate", 48000))
                    ch = int(audio_settings.get("channels", 2))
                    cl = int(audio_settings.get("channel_layout", openshot.LAYOUT_STEREO))
                    w.SetAudioOptions(
                        True,
                        ac,
                        sr,
                        ch,
                        cl,
                        audio_bps,
                    )
                else:
                    # No audio codec available; tell timeline we have no audio so writer/encode loop don't expect it.
                    self.timeline.info.has_audio = False
            elif in_audio_block and headless_skip_audio:
                self.timeline.info.has_audio = False

            w.PrepareStreams()

            if video_settings.get("spherical"):
                w.AddSphericalMetadata("equirectangular", 0.0, 0.0, 0.0)

            if export_type in [_("Audio Only")]:
                w.SetOption(openshot.AUDIO_STREAM, "muxing_preset", "mp4_faststart")
            else:
                w.SetOption(openshot.VIDEO_STREAM, "muxing_preset", "mp4_faststart")
                if "crf" in video_bitrate_text:
                    w.SetOption(openshot.VIDEO_STREAM, "crf", str(_parse_bitrate_to_bps(video_settings.get("video_bitrate"))))
                elif "cqp" in video_bitrate_text:
                    w.SetOption(openshot.VIDEO_STREAM, "cqp", str(_parse_bitrate_to_bps(video_settings.get("video_bitrate"))))
                elif "qp" in video_bitrate_text:
                    w.SetOption(openshot.VIDEO_STREAM, "qp", str(_parse_bitrate_to_bps(video_settings.get("video_bitrate"))))

            w.Open()

            self.ExportStarted.emit(export_file_path, video_settings.get("start_frame"), video_settings.get("end_frame"))

            progressstep = max(1, round((video_settings.get("end_frame") - video_settings.get("start_frame")) / 1000))
            start_time_export = time.time()
            start_frame_export = video_settings.get("start_frame")
            end_frame_export = video_settings.get("end_frame")
            last_exported_time = time.time()
            last_displayed_exported_portion = 0.0

            for frame in range(video_settings.get("start_frame"), video_settings.get("end_frame") + 1):
                end_time_export = time.time()
                if ((frame % progressstep) == 0) or ((end_time_export - last_exported_time) > 1):
                    current_exported_portion = (frame - start_frame_export) * 1.0 / (end_frame_export - start_frame_export)
                    if (current_exported_portion - last_displayed_exported_portion) > 0.0:
                        digits_after_decimalpoint = math.ceil(-2.0 - math.log10(current_exported_portion - last_displayed_exported_portion))
                    else:
                        digits_after_decimalpoint = 1
                    digits_after_decimalpoint = max(1, min(5, digits_after_decimalpoint))
                    last_displayed_exported_portion = current_exported_portion
                    format_of_progress_string = "%4." + str(digits_after_decimalpoint) + "f%% "
                    last_exported_time = time.time()
                    if (frame - start_frame_export) != 0 and (end_time_export - start_time_export) != 0:
                        seconds_left = round((start_time_export - end_time_export) * (frame - end_frame_export) / (frame - start_frame_export))
                        fps_encode = (frame - start_frame_export) / (end_time_export - start_time_export)
                        if frame == end_frame_export:
                            title_message = _("Finalizing video export, please wait...")
                        else:
                            title_message = titlestring(seconds_left, fps_encode, "Remaining")
                    else:
                        title_message = ""
                    self.ExportFrame.emit(
                        title_message,
                        video_settings.get("start_frame"),
                        video_settings.get("end_frame"),
                        frame,
                        format_of_progress_string
                    )
                    QCoreApplication.processEvents()

                max_frame = frame
                w.WriteFrame(self.timeline.GetFrame(frame))
                if self.cache_thread:
                    self.cache_thread.Seek(frame)

                if not self.exporting:
                    break

            w.Close()

            seconds_run = round((end_time_export - start_time_export))
            title_message = titlestring(seconds_run, fps_encode, "Elapsed")
            self.ExportFrame.emit(
                title_message,
                video_settings.get("start_frame"),
                video_settings.get("end_frame"),
                max_frame,
                format_of_progress_string
            )

        except Exception as e:
            error_type_str = str(e)
            log.info("Error type string: %s" % error_type_str)
            # If audio codec failed (dialog or headless), retry as video-only so user gets a file.
            if "audio codec" in error_type_str.lower() and export_type in [_("Video & Audio"), _("Audio Only")]:
                log.info("Audio codec failed, retrying export as video only")
                self.timeline.info.has_audio = False
                self.run_export(
                    export_file_path,
                    video_settings,
                    audio_settings,
                    _("Video Only"),
                    video_bitrate_text,
                    profile_path_for_rescale,
                )
                return
            track_metric_error("export-error-%s" % error_type_str[:50])
            friendly_error = error_type_str.split("> ")[0].replace("<", "") if "> " in error_type_str else error_type_str
            if hasattr(self, 'cancel_button'):
                msg = QMessageBox()
                msg.setWindowTitle(_("Export Error"))
                msg.setText(_("Sorry, there was an error exporting your video: \n%s") % friendly_error)
                msg.exec_()
            else:
                raise

        self.ExportEnded.emit(export_file_path)
        self.timeline.Close()
        self.timeline.ClearAllCache()
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = False
        if self.cache_thread:
            self.cache_thread.StopThread(10000)
            self.cache_thread.Reader(None)
            self.cache_thread = None
        get_app().window.timeline_sync.timeline.SetCache(self.old_cache_object)
        get_app().window.cache_object = self.old_cache_object

        # Dialog-only: show finished state or close (skip when headless)
        if getattr(self, "_headless", False):
            return
        if hasattr(self, 'cancel_button') and self.cancel_button is not None:
            if self.s.get("show_finished_window") and self.exporting:
                self.cancel_button.setVisible(False)
                self.export_button.setVisible(False)
                self.close_button.setVisible(True)
                from PyQt5.QtGui import QPalette
                p = QPalette()
                p.setColor(QPalette.Highlight, Qt.green)
                self.progressExportVideo.setPalette(p)
                self.show()
            else:
                super(Export, self).accept()

    def accept(self):
        """ Start exporting video """
        # Save export settings
        self.save_settings()

        # Build the export window title
        def titlestring(sec, fps, mess):
            formatstr = "%(hours)d:%(minutes)02d:%(seconds)02d " + mess + " (%(fps)5.2f FPS)"
            title_mes = _(formatstr) % {
                'hours': sec / 3600,
                'minutes': (sec / 60) % 60,
                'seconds': sec % 60,
                'fps': fps}
            return title_mes

        # get translations
        _ = get_app()._tr

        # Init some variables
        seconds_run = 0
        fps_encode = 0

        # Init progress bar
        self.progressExportVideo.setMinimum(int(self.txtStartFrame.value()))
        self.progressExportVideo.setMaximum(int(self.txtEndFrame.value()))
        self.progressExportVideo.setValue(int(self.txtStartFrame.value()))

        # Prompt error message
        if self.txtStartFrame.value() == self.txtEndFrame.value():
            msg = QMessageBox()
            msg.setWindowTitle(_("Export Error"))
            msg.setText(_("Sorry, please select a valid range of frames to export"))
            msg.exec_()

            # Do nothing
            self.enableControls()
            self.exporting = False
            return

        # Disable controls
        self.disableControls()
        self.exporting = True

        # Determine type of export (video+audio, video, audio, image sequences)
        # _("Video & Audio"), _("Video Only"), _("Audio Only"), _("Image Sequence")
        export_type = self.cboExportTo.currentText()

        # Determine final exported file path (and replace blank paths with default ones)
        default_filename = "Untitled Project"
        default_folder = os.path.join(info.HOME_PATH)
        if export_type == _("Image Sequence"):
            file_name_with_ext = "%s%s" % (self.txtFileName.text().strip() or default_filename, self.txtImageFormat.text().strip())
        else:
            file_ext = self.txtVideoFormat.text().strip()
            file_name_with_ext = self.txtFileName.text().strip() or default_filename
            # Append extension, if not already present
            if not file_name_with_ext.endswith(file_ext):
                file_name_with_ext = '{}.{}'.format(file_name_with_ext, file_ext)

        # Remove trailing whitespace, unless such a folder exists.
        folder_path = self.txtExportFolder.text().lstrip()
        if folder_path and not os.path.isdir(folder_path):
            log.debug("Folder path does not exist. Removing trailing whitespace.")
            if os.path.isdir(folder_path.rstrip()):
                log.debug("Directory %s does exist. Using it instead." % folder_path)
                folder_path = folder_path.rstrip()

        export_file_path = os.path.join(folder_path or default_folder, file_name_with_ext)
        log.info("Export path: %s" % export_file_path)

        # Check if filename is valid (by creating a blank file in a temporary place)
        try:
            open(os.path.join(tempfile.gettempdir(), file_name_with_ext), 'w')
        except OSError:
            # Invalid path detected, so use default file name instead
            file_name_with_ext = "%s.%s" % (default_filename, self.txtVideoFormat.text().strip())
            export_file_path = os.path.join(self.txtExportFolder.text().strip() or default_folder, file_name_with_ext)
            log.info("Invalid export path detected, changing to: %s" % export_file_path)

        file = File.get(path=export_file_path)
        if file:
            ret = QMessageBox.question(self,
                _("Export Video"),
                _("%s is an input file.\nPlease choose a different name.") % file_name_with_ext,
                QMessageBox.Ok)
            self.enableControls()
            self.exporting = False
            return

        # Handle exception
        if os.path.exists(export_file_path) and export_type in [_("Video & Audio"), _("Video Only"), _("Audio Only")]:
            # File already exists! Prompt user
            ret = QMessageBox.question(self,
                _("Export Video"),
                _("%s already exists.\nDo you want to replace it?") % file_name_with_ext,
                QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.No:
                # Stop and don't do anything
                # Re-enable controls
                self.enableControls()
                self.exporting = False
                return

        # Init export settings
        interlacedIndex = self.cboInterlaced.currentIndex()
        sphericalIndex = self.cboSpherical.currentIndex()
        video_settings = {  "vformat": self.txtVideoFormat.text(),
                            "vcodec": self.txtVideoCodec.text(),
                            "fps": { "num" : self.txtFrameRateNum.value(), "den": self.txtFrameRateDen.value()},
                            "width": self.txtWidth.value(),
                            "height": self.txtHeight.value(),
                            "pixel_ratio": {"num": self.txtPixelRatioNum.value(), "den": self.txtPixelRatioDen.value()},
                            "video_bitrate": int(self.convert_to_bytes(self.txtVideoBitRate.text())),
                            "start_frame": self.txtStartFrame.value(),
                            "end_frame": self.txtEndFrame.value(),
                            "interlace": interlacedIndex in [1, 2],
                            "topfirst": interlacedIndex == 1,
                            "spherical": sphericalIndex == 1
                          }

        audio_settings = {"acodec": self.txtAudioCodec.text(),
                          "sample_rate": self.txtSampleRate.value(),
                          "channels": self.txtChannels.value(),
                          "channel_layout": self.cboChannelLayout.currentData(),
                          "audio_bitrate": int(self.convert_to_bytes(self.txtAudioBitrate.text()))
                          }

        # Override vcodec and format for Image Sequences
        if export_type == _("Image Sequence"):
            image_ext = os.path.splitext(self.txtImageFormat.text().strip())[1].replace(".", "")
            video_settings["vformat"] = image_ext
            if image_ext in ["jpg", "jpeg"]:
                video_settings["vcodec"] = "mjpeg"
            else:
                video_settings["vcodec"] = image_ext

        # Store updated export folder path in project file
        settings = get_app().get_settings()
        settings.setDefaultPath(settings.actionType.EXPORT, export_file_path)
        # Mark project file as unsaved
        get_app().project.has_unsaved_changes = True

        self.run_export(
            export_file_path,
            video_settings,
            audio_settings,
            export_type,
            video_bitrate_text=self.txtVideoBitRate.text(),
            profile_path_for_rescale=self.cboSimpleVideoProfile.currentData() if self.cboSimpleVideoProfile.currentData() else None,
        )

    def save_settings(self):
        if self.restoring_defaults:
            return  # Ignore saving if we are actively restoring defaults

        # Create a list to store the settings in order
        settings = []

        # Iterate over all children in the dialog in the order they are defined
        for child in self.findChildren(QWidget):
            if child.objectName().startswith("qt_"):
                continue
            setting = {}
            if isinstance(child, QLineEdit):
                setting['name'] = child.objectName()
                setting['type'] = 'QLineEdit'
                setting['value'] = child.text()
            elif isinstance(child, QComboBox):
                setting['name'] = child.objectName()
                setting['type'] = 'QComboBox'
                setting['value'] = child.currentIndex()
            elif isinstance(child, QSpinBox):
                setting['name'] = child.objectName()
                setting['type'] = 'QSpinBox'
                setting['value'] = child.value()
            elif isinstance(child, QCheckBox):
                setting['name'] = child.objectName()
                setting['type'] = 'QCheckBox'
                setting['value'] = child.isChecked()
            # Append the setting to the list
            if setting:
                settings.append(setting)

        # Save all settings as a JSON string
        get_app().updates.ignore_history = True
        get_app().updates.update(["export_settings"], settings)
        get_app().updates.ignore_history = False

        log.info("Export settings saved: %s", settings)

    def load_settings(self):
        # Load the JSON string from settings
        settings = get_app().project.get("export_settings")

        if not settings:
            log.info("No saved settings found.")
            return

        # Iterate over the list of settings and apply them in order
        for setting in settings:
            widget = self.findChild(QWidget, setting['name'])
            if widget:
                if setting['type'] == 'QLineEdit':
                    widget.setText(setting.get('value', ''))
                elif setting['type'] == 'QComboBox':
                    widget.setCurrentIndex(setting.get('value', 0))
                elif setting['type'] in ['QSpinBox', 'QDoubleSpinBox']:
                    widget.setValue(setting.get('value', widget.minimum()))
                elif setting['type'] == 'QCheckBox':
                    widget.setChecked(setting.get('value', False))

        # Update start / end frame after loading settings
        if self.checkStartFirstClip.isChecked():
            self.updateFrameRate(True)
        if self.checkEndLastClip.isChecked():
            self.updateFrameRate(True)

        log.info("Export settings loaded: %s", settings)

    def reject(self):
        self.save_settings()

        if self.exporting and not self.close_button.isVisible():
            # Show confirmation dialog
            _ = get_app()._tr
            result = QMessageBox.question(
                self,
                _("Export Video"),
                _("Are you sure you want to cancel the export?"),
                QMessageBox.No | QMessageBox.Yes)
            if result == QMessageBox.No:
                # Resume export
                return

        # Return scale mode to lower quality scaling (for faster previews)
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = False

        # Stop cache thread and restore project cache
        if self.cache_thread:
            self.cache_thread.StopThread(10000)
            self.cache_thread.Reader(None)
            self.cache_thread = None
        get_app().window.timeline_sync.timeline.SetCache(self.old_cache_object)
        get_app().window.cache_object = self.old_cache_object

        # Cancel dialog
        self.exporting = False
        super(Export, self).reject()

    def calculate_all_formats_bitrate(self, quality_key):
        """Calculate a bitrate using bits-per-pixel guidance for All Formats presets."""
        quality_bpp = {
            "Low": 0.055,    # midpoint of 0.045 - 0.055
            "Med": 0.08,     # midpoint of 0.065 - 0.08
            "High": 0.12     # midpoint of 0.10 - 0.12
        }
        target_bpp = quality_bpp.get(quality_key)
        if target_bpp is None:
            return None

        width = self.txtWidth.value()
        height = self.txtHeight.value()
        fps_den = self.txtFrameRateDen.value() or 1
        fps = self.txtFrameRateNum.value() / fps_den

        if not width or not height or not fps:
            return None

        bitrate_bits_per_sec = width * height * fps * target_bpp
        bitrate_mbps = bitrate_bits_per_sec / 1_000_000.0
        return f"{bitrate_mbps:.2f} Mb/s"

    def update_all_formats_bitrates(self):
        """Refresh dynamic video bitrates when using All Formats presets."""
        _ = get_app()._tr
        if self.cboSimpleProjectType.currentData() != _("All Formats"):
            return

        dynamic_vbr = {}
        for key, translated in [("Low", _("Low")), ("Med", _("Med")), ("High", _("High"))]:
            bitrate = self.calculate_all_formats_bitrate(key)
            if bitrate:
                dynamic_vbr[translated] = bitrate

        if not dynamic_vbr:
            return

        self.vbr = dynamic_vbr
        selected_quality = self.cboSimpleQuality.itemData(self.cboSimpleQuality.currentIndex())
        if selected_quality:
            translated_quality = _(selected_quality)
            if translated_quality in self.vbr:
                self.txtVideoBitRate.setText(self.vbr[translated_quality])


def _parse_bitrate_to_bps(value, default=2000000):
    """
    Convert a bitrate value to integer bits-per-second.
    Accepts int, float, or string like "3.32 Mb/s", "500 kb/s", "23 crf", "22 cqp", "0 qp".
    Returns int; uses default if value is None or parsing fails.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return default
    s = value.strip().lower().split()
    if not s:
        return default
    try:
        raw_number = locale.atof(s[0])
    except (ValueError, TypeError):
        return default
    if len(s) >= 2:
        raw_measurement = s[1]
        if "kb" in raw_measurement:
            return int(raw_number * 1000.0)
        if "mb" in raw_measurement:
            return int(raw_number * 1000.0 * 1000.0)
        if "crf" in raw_measurement or "cqp" in raw_measurement:
            raw_number = max(0, min(63, raw_number))
            return int(raw_number)
        if "qp" in raw_measurement:
            raw_number = max(0, min(255, raw_number))
            return int(raw_number)
    return int(raw_number)


def _resolve_audio_codec(preferred):
    """
    Resolve requested audio codec to one that is available on this system.
    Prevents "Could not open audio codec" when the preferred codec (e.g. aac)
    is not available in the current FFmpeg build. Works cross-platform (Linux, Windows, macOS).
    Uses the same order as the UI profile logic: libfaac, libvo_aacenc, aac, ac3 (first valid wins).
    Returns a string codec name valid for openshot.FFmpegWriter, or None if no codec is available
    (caller should skip SetAudioOptions and export video-only).
    """
    preferred = (preferred or "aac").strip()
    if not preferred:
        preferred = "aac"
    # Use same order as UI profile (export.py preset loading): libfaac, libvo_aacenc, then ac3.
    # Do not use "aac" here — IsValidCodec("aac") is often True but Open() fails ("Could not open audio codec").
    # Only use codecs that typically work at Open(); if none are valid, return None (export video-only).
    aac_order = ("libfaac", "libvo_aacenc", "ac3", "libfdk_aac", "libmp3lame")
    if preferred.lower() == "aac" or preferred in aac_order:
        for codec in aac_order:
            if openshot.FFmpegWriter.IsValidCodec(codec):
                if codec != preferred:
                    log.info("Audio codec %s resolved to %s", preferred, codec)
                return codec
        # No audio codec available; return None so caller skips audio (export video-only).
        log.info("No audio codec available (tried %s), exporting video only", list(aac_order))
        return None
    preferred_valid = openshot.FFmpegWriter.IsValidCodec(preferred)
    if preferred_valid:
        return preferred
    for codec in aac_order:
        if codec != preferred and openshot.FFmpegWriter.IsValidCodec(codec):
            log.info("Audio codec %s not available, using %s", preferred, codec)
            return codec
    return preferred


def get_default_export_settings():
    """
    Build default or last-used export settings from project (no UI).
    Returns (video_settings, audio_settings, export_type, default_path).
    Uses project profile for defaults; if project has export_settings (saved widget list),
    map known widget names into video_settings/audio_settings/export_type.
    """
    from classes.app import get_app
    app = get_app()
    project = app.project
    settings = app.get_settings()
    _ = app._tr

    # Export type options (same order as dialog)
    export_type_options = [_("Video & Audio"), _("Video Only"), _("Audio Only"), _("Image Sequence")]

    # Defaults from project profile
    fps = project.get("fps") or {"num": 30, "den": 1}
    width = project.get("width") or 1920
    height = project.get("height") or 1080
    sample_rate = project.get("sample_rate") or 48000
    channels = project.get("channels") or 2
    channel_layout = getattr(openshot, "LAYOUT_STEREO", 2)

    video_settings = {
        "vformat": "mp4",
        "vcodec": "libx264",
        "fps": {"num": fps.get("num", 30), "den": fps.get("den", 1) or 1},
        "width": width,
        "height": height,
        "pixel_ratio": {"num": 1, "den": 1},
        "video_bitrate": 2000000,
        "start_frame": 1,
        "end_frame": max(1, int(project.get("duration") or 0) or 1),
        "interlace": False,
        "topfirst": False,
        "spherical": False,
    }
    audio_settings = {
        "acodec": "aac",
        "sample_rate": sample_rate,
        "channels": channels,
        "channel_layout": channel_layout,
        "audio_bitrate": 192000,
    }
    export_type = export_type_options[0]
    default_path = os.path.join(settings.getDefaultPath(settings.actionType.EXPORT), "export.mp4")

    # Map saved widget list to logical keys if present
    saved = project.get("export_settings")
    if saved and isinstance(saved, list):
        widget_to_video = {
            "txtVideoFormat": "vformat", "txtVideoCodec": "vcodec",
            "txtWidth": "width", "txtHeight": "height",
            "txtFrameRateNum": ("fps", "num"), "txtFrameRateDen": ("fps", "den"),
            "txtPixelRatioNum": ("pixel_ratio", "num"), "txtPixelRatioDen": ("pixel_ratio", "den"),
            "txtVideoBitRate": "video_bitrate", "txtStartFrame": "start_frame", "txtEndFrame": "end_frame",
        }
        widget_to_audio = {
            "txtAudioCodec": "acodec", "txtSampleRate": "sample_rate",
            "txtChannels": "channels", "txtAudioBitrate": "audio_bitrate",
        }
        widget_to_export_type = "cboExportTo"
        for s in saved:
            name = s.get("name") or ""
            val = s.get("value")
            if name in widget_to_video:
                key = widget_to_video[name]
                if isinstance(key, tuple):
                    if key[0] not in video_settings:
                        video_settings[key[0]] = {}
                    video_settings[key[0]][key[1]] = val
                else:
                    video_settings[key] = val
            elif name in widget_to_audio:
                audio_settings[widget_to_audio[name]] = val
            elif name == "cboChannelLayout":
                audio_settings["channel_layout"] = val
            elif name == widget_to_export_type and isinstance(val, int) and 0 <= val < len(export_type_options):
                export_type = export_type_options[val]

    # Apply chat overrides (set via set_export_setting)
    overrides = project.get("export_overrides") or {}
    for k, v in overrides.items():
        if k in ("width", "height", "start_frame", "end_frame"):
            video_settings[k] = v
        elif k == "fps_num":
            video_settings.setdefault("fps", {})["num"] = v
        elif k == "fps_den":
            video_settings.setdefault("fps", {})["den"] = v
        elif k in ("video_codec", "vcodec"):
            video_settings["vcodec"] = v
        elif k in ("vformat", "format"):
            video_settings["vformat"] = v
        elif k in ("audio_codec", "acodec"):
            audio_settings["acodec"] = v
        elif k == "sample_rate":
            audio_settings["sample_rate"] = v
        elif k == "channels":
            audio_settings["channels"] = v
        elif k in ("output_path", "path"):
            default_path = v

    return video_settings, audio_settings, export_type, default_path


def export_video_headless(export_file_path, video_settings=None, audio_settings=None, export_type=None):
    """
    Run export without showing the dialog. Call from main thread.
    If video_settings, audio_settings, or export_type is None, use default/last-used from project.
    Returns None on success; raises or returns error message on failure.
    """
    from classes.app import get_app
    app = get_app()
    _ = app._tr

    vs, as_, et, default_path = get_default_export_settings()
    if video_settings is None:
        video_settings = vs
    if audio_settings is None:
        audio_settings = as_
    if export_type is None:
        export_type = et
    if not export_file_path:
        export_file_path = default_path
    if not export_file_path:
        export_file_path = os.path.join(info.HOME_PATH, "export.mp4")

    # Ensure directory exists
    export_dir = os.path.dirname(export_file_path)
    if export_dir and not os.path.isdir(export_dir):
        os.makedirs(export_dir, exist_ok=True)

    # Validate frame range
    if video_settings.get("start_frame") == video_settings.get("end_frame"):
        return _("Invalid range of frames to export.")

    # Input file check
    if File.get(path=export_file_path):
        return _("Output path is an input file. Choose a different path.")

    win = Export()
    win.exporting = True
    win._headless = True
    # Headless: always export video-only to avoid "Could not open audio codec".
    if export_type in [_("Video & Audio"), _("Audio Only")]:
        export_type = _("Video Only")
    # Use timeline length for end_frame if not set
    try:
        max_frame = win.timeline.GetMaxFrame()
        if not video_settings.get("end_frame") or video_settings.get("end_frame") < video_settings.get("start_frame", 1):
            video_settings["end_frame"] = max_frame
        if video_settings.get("start_frame", 1) >= video_settings["end_frame"]:
            return _("Invalid range of frames to export.")
    except Exception:
        pass
    try:
        win.run_export(
            export_file_path,
            video_settings,
            audio_settings,
            export_type,
            video_bitrate_text="",
            profile_path_for_rescale=None,
        )
    except Exception as e:
        err = str(e)
        err_lower = err.lower()
        # If opening the audio codec failed, retry with Video Only so the user still gets a video file.
        audio_codec_failed = (
            "audio codec" in err_lower or "open audio codec" in err_lower or "could not open" in err_lower and "audio" in err_lower
        )
        if audio_codec_failed and export_type in [_("Video & Audio"), _("Audio Only")]:
            log.info("Headless export: audio codec failed (%s), retrying as Video Only", err.strip())
            try:
                win2 = Export()
                win2.exporting = True
                win2._headless = True
                max_frame = win2.timeline.GetMaxFrame()
                if not video_settings.get("end_frame") or video_settings["end_frame"] < video_settings.get("start_frame", 1):
                    video_settings = dict(video_settings)
                    video_settings["end_frame"] = max_frame
                win2.run_export(
                    export_file_path,
                    video_settings,
                    audio_settings,
                    _("Video Only"),
                    video_bitrate_text="",
                    profile_path_for_rescale=None,
                )
            except Exception:
                return err
            return None
        return err
    return None
