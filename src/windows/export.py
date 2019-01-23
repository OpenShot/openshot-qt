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
import time
import os
import locale
import xml.dom.minidom as xml
import functools

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, settings
from classes.app import get_app
from classes.query import File
from classes.logger import log
from classes.metrics import *

try:
    import json
except ImportError:
    import simplejson as json


class Export(QDialog):
    """ Export Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'export.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # get translations
        app = get_app()
        _ = app._tr

        # Get settings
        self.s = settings.get_settings()

        # Track metrics
        track_metric_screen("export-screen")

        # Dynamically load tabs from settings data
        self.settings_data = settings.get_settings().get_all_settings()

        # Add buttons to interface
        self.export_button = QPushButton(_('Export Video'))
        self.buttonBox.addButton(self.export_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(QPushButton(_('Cancel')), QDialogButtonBox.RejectRole)
        self.exporting = False

        # Update FPS / Profile timer
        # Timer to use a delay before applying new profile/fps data (so we don't spam libopenshot)
        self.delayed_fps_timer = None
        self.delayed_fps_timer = QTimer()
        self.delayed_fps_timer.setInterval(200)
        self.delayed_fps_timer.timeout.connect(self.delayed_fps_callback)
        self.delayed_fps_timer.stop()

        # Pause playback (to prevent crash since we are fixing to change the timeline's max size)
        get_app().window.actionPlay_trigger(None, force="pause")

        # Clear timeline preview cache (to get more available memory)
        get_app().window.timeline_sync.timeline.ClearAllCache()

        # Hide audio channels
        self.lblChannels.setVisible(False)
        self.txtChannels.setVisible(False)

        # Set OMP thread disabled flag (for stability)
        openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = True
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = True

        # Get the original timeline settings
        width = get_app().window.timeline_sync.timeline.info.width
        height = get_app().window.timeline_sync.timeline.info.height
        fps = get_app().window.timeline_sync.timeline.info.fps
        sample_rate = get_app().window.timeline_sync.timeline.info.sample_rate
        channels = get_app().window.timeline_sync.timeline.info.channels
        channel_layout = get_app().window.timeline_sync.timeline.info.channel_layout

        # Create new "export" openshot.Timeline object
        self.timeline = openshot.Timeline(width, height, openshot.Fraction(fps.num, fps.den),
                                          sample_rate, channels, channel_layout)
        # Init various properties
        self.timeline.info.channel_layout = get_app().window.timeline_sync.timeline.info.channel_layout
        self.timeline.info.has_audio = get_app().window.timeline_sync.timeline.info.has_audio
        self.timeline.info.has_video = get_app().window.timeline_sync.timeline.info.has_video
        self.timeline.info.video_length = get_app().window.timeline_sync.timeline.info.video_length
        self.timeline.info.duration = get_app().window.timeline_sync.timeline.info.duration
        self.timeline.info.sample_rate = get_app().window.timeline_sync.timeline.info.sample_rate
        self.timeline.info.channels = get_app().window.timeline_sync.timeline.info.channels

        # Load the "export" Timeline reader with the JSON from the real timeline
        json_timeline = json.dumps(get_app().project._data)
        self.timeline.SetJson(json_timeline)

        # Open the "export" Timeline reader
        self.timeline.Open()

        # Default export path
        recommended_path = recommended_path = os.path.join(info.HOME_PATH)
        if app.project.current_filepath:
            recommended_path = os.path.dirname(app.project.current_filepath)

        export_path = get_app().project.get(["export_path"])
        if os.path.exists(export_path):
            # Use last selected export path
            self.txtExportFolder.setText(export_path)
        else:
            # Default to home dir
            self.txtExportFolder.setText(recommended_path)

        # Is this a saved project?
        if not get_app().project.current_filepath:
            # Not saved yet
            self.txtFileName.setText(_("Untitled Project"))
        else:
            # Yes, project is saved
            # Get just the filename
            parent_path, filename = os.path.split(get_app().project.current_filepath)
            filename, ext = os.path.splitext(filename)
            self.txtFileName.setText(filename.replace("_", " ").replace("-", " ").capitalize())

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
        get_app().window.ExportFrame.connect(self.updateProgressBar)

        # ********* Advanced Profile List **********
        # Loop through profiles
        self.profile_names = []
        self.profile_paths = {}
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in os.listdir(profile_folder):
                # Load Profile
                profile_path = os.path.join(profile_folder, file)
                profile = openshot.Profile(profile_path)

                # Add description of Profile to list
                profile_name = "%s (%sx%s)" % (profile.info.description, profile.info.width, profile.info.height)
                self.profile_names.append(profile_name)
                self.profile_paths[profile_name] = profile_path

        # Sort list
        self.profile_names.sort()

        # Loop through sorted profiles
        box_index = 0
        self.selected_profile_index = 0
        for profile_name in self.profile_names:

            # Add to dropdown
            self.cboProfile.addItem(self.getProfileName(self.getProfilePath(profile_name)), self.getProfilePath(profile_name))

            # Set default (if it matches the project)
            if app.project.get(['profile']) in profile_name:
                self.selected_profile_index = box_index

            # increment item counter
            box_index += 1


        # ********* Simple Project Type **********
        # load the simple project type dropdown
        presets = []
        for preset_path in [info.EXPORT_PRESETS_PATH, info.USER_PRESETS_PATH]:
            for file in os.listdir(preset_path):
                xmldoc = xml.parse(os.path.join(preset_path, file))
                type = xmldoc.getElementsByTagName("type")
                presets.append(_(type[0].childNodes[0].data))

        # Exclude duplicates
        type_index = 0
        selected_type = 0
        presets = list(set(presets))
        for item in sorted(presets):
            self.cboSimpleProjectType.addItem(item, item)
            if item == _("All Formats"):
                selected_type = type_index
            type_index += 1

        # Always select 'All Formats' option
        self.cboSimpleProjectType.setCurrentIndex(selected_type)


        # Populate all profiles
        self.populateAllProfiles(app.project.get(['profile']))

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

    def delayed_fps_callback(self):
        """Callback for fps/profile changed event timer (to delay the timeline mapping so we don't spam libopenshot)"""
        # Stop timer
        self.delayed_fps_timer.stop()

        # Calculate fps
        fps_double = self.timeline.info.fps.ToDouble()

        # Apply mapping if valid fps detected (anything larger than 300 fps is considered invalid)
        if self.timeline and fps_double <= 300.0:
            log.info("Valid framerate detected, sending to libopenshot: %s" % fps_double)
            self.timeline.ApplyMapperToClips()
        else:
            log.warning("Invalid framerate detected, not sending it to libopenshot: %s" % fps_double)

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

    def updateProgressBar(self, path, start_frame, end_frame, current_frame):
        """Update progress bar during exporting"""
        percentage_string = "%4.1f%% " % (( current_frame - start_frame ) / ( end_frame - start_frame ) * 100)
        self.progressExportVideo.setValue(current_frame)
        self.progressExportVideo.setFormat(percentage_string)
        self.setWindowTitle("%s %s" % (percentage_string, path))

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

    def updateFrameRate(self):
        """Callback for changing the frame rate"""
        # Adjust the main timeline reader
        self.timeline.info.width = self.txtWidth.value()
        self.timeline.info.height = self.txtHeight.value()
        self.timeline.info.fps.num = self.txtFrameRateNum.value()
        self.timeline.info.fps.den = self.txtFrameRateDen.value()
        self.timeline.info.sample_rate = self.txtSampleRate.value()
        self.timeline.info.channels = self.txtChannels.value()
        self.timeline.info.channel_layout = self.cboChannelLayout.currentData()

        # Send changes to libopenshot (apply mappings to all framemappers)... after a small delay
        self.delayed_fps_timer.start()

        # Determine max frame (based on clips)
        timeline_length = 0.0
        fps = self.timeline.info.fps.ToFloat()
        clips = self.timeline.Clips()
        for clip in clips:
            clip_last_frame = clip.Position() + clip.Duration()
            if clip_last_frame > timeline_length:
                # Set max length of timeline
                timeline_length = clip_last_frame

        # Convert to int and round
        self.timeline_length_int = round(timeline_length * fps) + 1

        # Set the min and max frame numbers for this project
        self.txtStartFrame.setValue(1)
        self.txtEndFrame.setValue(self.timeline_length_int)

        # Init progress bar
        self.progressExportVideo.setMinimum(self.txtStartFrame.value())
        self.progressExportVideo.setMaximum(self.txtEndFrame.value())
        self.progressExportVideo.setValue(self.txtStartFrame.value())

    def cboSimpleProjectType_index_changed(self, widget, index):
        selected_project = widget.itemData(index)

        # set the target dropdown based on the selected project type
        # first clear the combo
        self.cboSimpleTarget.clear()

        # get translations
        app = get_app()
        _ = app._tr

        # parse the xml files and get targets that match the project type
        project_types = []
        for preset_path in [info.EXPORT_PRESETS_PATH, info.USER_PRESETS_PATH]:
            for file in os.listdir(preset_path):
                xmldoc = xml.parse(os.path.join(preset_path, file))
                type = xmldoc.getElementsByTagName("type")

                if _(type[0].childNodes[0].data) == selected_project:
                    titles = xmldoc.getElementsByTagName("title")
                    for title in titles:
                        project_types.append(_(title.childNodes[0].data))

        # Add all targets for selected project type
        preset_index = 0
        selected_preset = 0
        for item in sorted(project_types):
            self.cboSimpleTarget.addItem(item, item)

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
        app = get_app()
        _ = app._tr

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
        self.cboInterlaced.addItem(_("Yes"), "Yes")
        self.cboInterlaced.addItem(_("No"), "No")
        if profile.info.interlaced_frame:
            self.cboInterlaced.setCurrentIndex(0)
        else:
            self.cboInterlaced.setCurrentIndex(1)

    def cboSimpleTarget_index_changed(self, widget, index):
        selected_target = widget.itemData(index)
        log.info(selected_target)

        # get translations
        app = get_app()
        _ = app._tr

        # don't do anything if the combo has been cleared
        if selected_target:
            profiles_list = []

            # Clear the following options (and remember current settings)
            previous_quality = self.cboSimpleQuality.currentIndex()
            if previous_quality < 0:
                previous_quality = self.cboSimpleQuality.count() - 1
            previous_profile = self.cboSimpleVideoProfile.currentIndex()
            if previous_profile < 0:
                previous_profile = self.selected_profile_index
            self.cboSimpleVideoProfile.clear()
            self.cboSimpleQuality.clear()

            # parse the xml to return suggested profiles
            profile_index = 0
            all_profiles = False
            for preset_path in [info.EXPORT_PRESETS_PATH, info.USER_PRESETS_PATH]:
                for file in os.listdir(preset_path):
                    xmldoc = xml.parse(os.path.join(preset_path, file))
                    title = xmldoc.getElementsByTagName("title")
                    if _(title[0].childNodes[0].data) == selected_target:
                        profiles = xmldoc.getElementsByTagName("projectprofile")

                        # get the basic profile
                        all_profiles = False
                        if profiles:
                            # if profiles are defined, show them
                            for profile in profiles:
                                profiles_list.append(_(profile.childNodes[0].data))
                        else:
                            # show all profiles
                            all_profiles = True
                            for profile_name in self.profile_names:
                                profiles_list.append(profile_name)

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
                        self.txtVideoCodec.setText(vc[0].childNodes[0].data)
                        sr = xmldoc.getElementsByTagName("samplerate")
                        self.txtSampleRate.setValue(int(sr[0].childNodes[0].data))
                        c = xmldoc.getElementsByTagName("audiochannels")
                        self.txtChannels.setValue(int(c[0].childNodes[0].data))
                        c = xmldoc.getElementsByTagName("audiochannellayout")

                        # check for compatible audio codec
                        ac = xmldoc.getElementsByTagName("audiocodec")
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

                        layout_index = 0
                        for layout in self.channel_layout_choices:
                            if layout == int(c[0].childNodes[0].data):
                                self.cboChannelLayout.setCurrentIndex(layout_index)
                                break
                            layout_index += 1

            # init the profiles combo
            for item in sorted(profiles_list):
                self.cboSimpleVideoProfile.addItem(self.getProfileName(self.getProfilePath(item)), self.getProfilePath(item))

            if all_profiles:
                # select the project's current profile
                self.cboSimpleVideoProfile.setCurrentIndex(previous_profile)

            # set the quality combo
            # only populate with quality settings that exist
            if v_l or a_l:
                self.cboSimpleQuality.addItem(_("Low"), "Low")
            if v_m or a_m:
                self.cboSimpleQuality.addItem(_("Med"), "Med")
            if v_h or a_h:
                self.cboSimpleQuality.addItem(_("High"), "High")

            # Default to the highest quality setting (or previous quality setting)
            if previous_quality <= self.cboSimpleQuality.count() - 1:
                self.cboSimpleQuality.setCurrentIndex(previous_quality)
            else:
                self.cboSimpleQuality.setCurrentIndex(self.cboSimpleQuality.count() - 1)

    def cboSimpleVideoProfile_index_changed(self, widget, index):
        selected_profile_path = widget.itemData(index)
        log.info(selected_profile_path)

        # Populate the advanced profile list
        self.populateAllProfiles(selected_profile_path)

    def populateAllProfiles(self, selected_profile_path):
        """Populate the full list of profiles"""
        # Look for matching profile in advanced options
        profile_index = 0
        for profile_name in self.profile_names:
            # Check for matching profile
            if self.getProfilePath(profile_name) == selected_profile_path:
                # Matched!
                self.cboProfile.setCurrentIndex(profile_index)
                break

            # increment index
            profile_index += 1

    def cboSimpleQuality_index_changed(self, widget, index):
        selected_quality = widget.itemData(index)
        log.info(selected_quality)

        # get translations
        app = get_app()
        _ = app._tr

        # Set the video and audio bitrates
        if selected_quality:
            self.txtVideoBitRate.setText(_(self.vbr[_(selected_quality)]))
            self.txtAudioBitrate.setText(_(self.abr[_(selected_quality)]))

    def btnBrowse_clicked(self):
        log.info("btnBrowse_clicked")

        # get translations
        app = get_app()
        _ = app._tr

        # update export folder path
        file_path = QFileDialog.getExistingDirectory(self, _("Choose a Folder..."), self.txtExportFolder.text())
        if os.path.exists(file_path):
            self.txtExportFolder.setText(file_path)

            # update export folder path in project file
            get_app().updates.update(["export_path"], file_path)

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
                    measurement = "kb"
                    bit_rate_bytes = raw_number * 1000.0

                elif "mb" in raw_measurement:
                    measurement = "mb"
                    bit_rate_bytes = raw_number * 1000.0 * 1000.0

        except:
            pass

        # return the bit rate in bytes
        return str(int(bit_rate_bytes))

    def accept(self):
        """ Start exporting video """

        # get translations
        app = get_app()
        _ = app._tr

        # Disable controls
        self.txtFileName.setEnabled(False)
        self.txtExportFolder.setEnabled(False)
        self.tabWidget.setEnabled(False)
        self.export_button.setEnabled(False)
        self.exporting = True

        # Determine type of export (video+audio, video, audio, image sequences)
        # _("Video & Audio"), _("Video Only"), _("Audio Only"), _("Image Sequence")
        export_type = self.cboExportTo.currentText()

        # Determine final exported file path
        if export_type != _("Image Sequence"):
            file_name_with_ext = "%s.%s" % (self.txtFileName.text().strip(), self.txtVideoFormat.text().strip())
        else:
            file_name_with_ext = "%s%s" % (self.txtFileName.text().strip(), self.txtImageFormat.text().strip())
        export_file_path = os.path.join(self.txtExportFolder.text().strip(), file_name_with_ext)
        log.info(export_file_path)

        # Translate object
        _ = get_app()._tr

        file = File.get(path=export_file_path)
        if file:
            ret = QMessageBox.question(self, _("Export Video"), _("%s is an input file.\nPlease choose a different name.") % file_name_with_ext,
                                       QMessageBox.Ok)
            self.txtFileName.setEnabled(True)
            self.txtExportFolder.setEnabled(True)
            self.tabWidget.setEnabled(True)
            self.export_button.setEnabled(True)
            self.exporting = False
            return

        # Handle exception
        if os.path.exists(export_file_path) and export_type in [_("Video & Audio"), _("Video Only"), _("Audio Only")]:
            # File already exists! Prompt user
            ret = QMessageBox.question(self, _("Export Video"), _("%s already exists.\nDo you want to replace it?") % file_name_with_ext,
                                       QMessageBox.No | QMessageBox.Yes)
            if ret == QMessageBox.No:
                # Stop and don't do anything
                # Re-enable controls
                self.txtFileName.setEnabled(True)
                self.txtExportFolder.setEnabled(True)
                self.tabWidget.setEnabled(True)
                self.export_button.setEnabled(True)
                self.exporting = False
                return

        # Init export settings
        video_settings = {  "vformat": self.txtVideoFormat.text(),
                            "vcodec": self.txtVideoCodec.text(),
                            "fps": { "num" : self.txtFrameRateNum.value(), "den": self.txtFrameRateDen.value()},
                            "width": self.txtWidth.value(),
                            "height": self.txtHeight.value(),
                            "pixel_ratio": {"num": self.txtPixelRatioNum.value(), "den": self.txtPixelRatioDen.value()},
                            "video_bitrate": int(self.convert_to_bytes(self.txtVideoBitRate.text())),
                            "start_frame": self.txtStartFrame.value(),
                            "end_frame": self.txtEndFrame.value() + 1
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

        # Set MaxSize (so we don't have any downsampling)
        self.timeline.SetMaxSize(video_settings.get("width"), video_settings.get("height"))

        # Set lossless cache settings (temporarily)
        export_cache_object = openshot.CacheMemory(250)
        self.timeline.SetCache(export_cache_object)

        # Create FFmpegWriter
        try:
            w = openshot.FFmpegWriter(export_file_path)

            # Set video options
            if export_type in [_("Video & Audio"), _("Video Only"), _("Image Sequence")]:
                w.SetVideoOptions(True,
                                  video_settings.get("vcodec"),
                                  openshot.Fraction(video_settings.get("fps").get("num"),
                                                    video_settings.get("fps").get("den")),
                                  video_settings.get("width"),
                                  video_settings.get("height"),
                                  openshot.Fraction(video_settings.get("pixel_ratio").get("num"),
                                                    video_settings.get("pixel_ratio").get("den")),
                                  False,
                                  False,
                                  video_settings.get("video_bitrate"))

            # Set audio options
            if export_type in [_("Video & Audio"), _("Audio Only")]:
                w.SetAudioOptions(True,
                                  audio_settings.get("acodec"),
                                  audio_settings.get("sample_rate"),
                                  audio_settings.get("channels"),
                                  audio_settings.get("channel_layout"),
                                  audio_settings.get("audio_bitrate"))

            # Open the writer
            w.Open()

            # Notify window of export started
            export_file_path = ""
            get_app().window.ExportStarted.emit(export_file_path, video_settings.get("start_frame"), video_settings.get("end_frame"))

            progressstep = max(1 , round(( video_settings.get("end_frame") - video_settings.get("start_frame") ) / 1000))
            start_time_export = time.time()
            start_frame_export = video_settings.get("start_frame")
            end_frame_export = video_settings.get("end_frame")
            # Write each frame in the selected range
            for frame in range(video_settings.get("start_frame"), video_settings.get("end_frame")):
                # Update progress bar (emit signal to main window)
                if (frame % progressstep) == 0:
                    end_time_export = time.time()
                    if ((( frame - start_frame_export ) != 0) & (( end_time_export - start_time_export ) != 0)):
                        seconds_left = round(( start_time_export - end_time_export )*( frame - end_frame_export )/( frame - start_frame_export ))
                        fps_encode = ((frame - start_frame_export)/(end_time_export-start_time_export))
                        export_file_path =  _("%(hours)d:%(minutes)02d:%(seconds)02d Remaining (%(fps)5.2f FPS)") % { 'hours' : seconds_left / 3600,
                                                                                                                      'minutes': (seconds_left / 60) % 60,
                                                                                                                      'seconds': seconds_left % 60,
                                                                                                                      'fps': fps_encode }
                    get_app().window.ExportFrame.emit(export_file_path, video_settings.get("start_frame"), video_settings.get("end_frame"), frame)

                # Process events (to show the progress bar moving)
                QCoreApplication.processEvents()

                # Write the frame object to the video
                w.WriteFrame(self.timeline.GetFrame(frame))

                # Check if we need to bail out
                if not self.exporting:
                    break

            # Close writer
            w.Close()


        except Exception as e:
            # TODO: Find a better way to catch the error. This is the only way I have found that
            # does not throw an error
            error_type_str = str(e)
            log.info("Error type string: %s" % error_type_str)

            if "InvalidChannels" in error_type_str:
                log.info("Error setting invalid # of channels (%s)" % (audio_settings.get("channels")))
                track_metric_error("invalid-channels-%s-%s-%s-%s" % (video_settings.get("vformat"), video_settings.get("vcodec"), audio_settings.get("acodec"), audio_settings.get("channels")))

            elif "InvalidSampleRate" in error_type_str:
                log.info("Error setting invalid sample rate (%s)" % (audio_settings.get("sample_rate")))
                track_metric_error("invalid-sample-rate-%s-%s-%s-%s" % (video_settings.get("vformat"), video_settings.get("vcodec"), audio_settings.get("acodec"), audio_settings.get("sample_rate")))

            elif "InvalidFormat" in error_type_str:
                log.info("Error setting invalid format (%s)" % (video_settings.get("vformat")))
                track_metric_error("invalid-format-%s" % (video_settings.get("vformat")))

            elif "InvalidCodec" in error_type_str:
                log.info("Error setting invalid codec (%s/%s/%s)" % (video_settings.get("vformat"), video_settings.get("vcodec"), audio_settings.get("acodec")))
                track_metric_error("invalid-codec-%s-%s-%s" % (video_settings.get("vformat"), video_settings.get("vcodec"), audio_settings.get("acodec")))

            elif "ErrorEncodingVideo" in error_type_str:
                log.info("Error encoding video frame (%s/%s/%s)" % (video_settings.get("vformat"), video_settings.get("vcodec"), audio_settings.get("acodec")))
                track_metric_error("video-encode-%s-%s-%s" % (video_settings.get("vformat"), video_settings.get("vcodec"), audio_settings.get("acodec")))

            # Show friendly error
            friendly_error = error_type_str.split("> ")[0].replace("<", "")

            # Prompt error message
            msg = QMessageBox()
            _ = get_app()._tr
            msg.setWindowTitle(_("Export Error"))
            msg.setText(_("Sorry, there was an error exporting your video: \n%s") % friendly_error)
            msg.exec_()

        # Notify window of export started
        get_app().window.ExportEnded.emit(export_file_path)

        # Close timeline object
        self.timeline.Close()

        # Clear all cache
        self.timeline.ClearAllCache()

        # Re-set OMP thread enabled flag
        if self.s.get("omp_threads_enabled"):
            openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = False
        else:
            openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = True

            # Return scale mode to lower quality scaling (for faster previews)
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = False

        # Accept dialog
        super(Export, self).accept()

    def reject(self):
        # Re-set OMP thread enabled flag
        if self.s.get("omp_threads_enabled"):
            openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = False
        else:
            openshot.Settings.Instance().WAIT_FOR_VIDEO_PROCESSING_TASK = True

        # Return scale mode to lower quality scaling (for faster previews)
        openshot.Settings.Instance().HIGH_QUALITY_SCALING = False

        # Cancel dialog
        self.exporting = False
        super(Export, self).reject()
