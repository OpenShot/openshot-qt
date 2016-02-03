"""
 @file
 @brief This file loads the Video Export dialog (i.e where is all preferences)
 @author Jonathan Thomas <jonathan@openshot.org>

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
import locale
import xml.dom.minidom as xml
import functools

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, settings
from classes.app import get_app
from classes.logger import log
from classes.metrics import *


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

        # Get the original timeline settings
        self.original_width = get_app().window.timeline_sync.timeline.info.width
        self.original_height = get_app().window.timeline_sync.timeline.info.height
        fps = get_app().window.timeline_sync.timeline.info.fps
        self.original_fps = { "num" : fps.num, "den" : fps.den }
        self.original_sample_rate = get_app().window.timeline_sync.timeline.info.sample_rate
        self.original_channels = get_app().window.timeline_sync.timeline.info.channels
        self.original_channel_layout = get_app().window.timeline_sync.timeline.info.channel_layout

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
        self.txtImageFormat.setText("%05.png")

        # Loop through Export To options
        export_options = [_("Video & Audio"), _("Image Sequence")]
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


        # ********* Advaned Profile List **********
        # Loop through profiles
        self.profile_names = []
        self.profile_paths = {}
        for file in os.listdir(info.PROFILES_PATH):
            # Load Profile
            profile_path = os.path.join(info.PROFILES_PATH, file)
            profile = openshot.Profile(profile_path)

            # Add description of Profile to list
            self.profile_names.append(profile.info.description)
            self.profile_paths[profile.info.description] = profile_path

        # Sort list
        self.profile_names.sort()

        # Loop through sorted profiles
        box_index = 0
        self.selected_profile_index = 0
        for profile_name in self.profile_names:

            # Add to dropdown
            self.cboProfile.addItem(profile_name, self.profile_paths[profile_name])

            # Set default (if it matches the project)
            if app.project.get(['profile']) == profile_name:
                self.selected_profile_index = box_index

            # increment item counter
            box_index += 1


        # ********* Simple Project Type **********
        # load the simple project type dropdown
        presets = []
        for file in os.listdir(info.EXPORT_PRESETS_DIR):
            xmldoc = xml.parse(os.path.join(info.EXPORT_PRESETS_DIR, file))
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
        log.info('Adjust the framerate of the project')

        # Adjust the main timeline reader
        get_app().updates.update(["width"], self.txtWidth.value())
        get_app().updates.update(["height"], self.txtHeight.value())
        get_app().updates.update(["fps"], {"num" : self.txtFrameRateNum.value(), "den" : self.txtFrameRateDen.value()})
        get_app().updates.update(["sample_rate"], self.txtSampleRate.value())
        get_app().updates.update(["channels"], self.txtChannels.value())
        get_app().updates.update(["channel_layout"], self.cboChannelLayout.currentData())

        # Force ApplyMapperToClips to apply these changes
        get_app().window.timeline_sync.timeline.ApplyMapperToClips()

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
        self.timeline_length_int = round(timeline_length * fps) + 1

        # Set the min and max frame numbers for this project
        self.txtStartFrame.setMaximum(self.timeline_length_int)
        self.txtEndFrame.setMaximum(self.timeline_length_int)
        self.txtStartFrame.setValue(1)
        self.txtEndFrame.setValue(self.timeline_length_int)

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
        for file in os.listdir(info.EXPORT_PRESETS_DIR):
            xmldoc = xml.parse(os.path.join(info.EXPORT_PRESETS_DIR, file))
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
        self.txtFrameRateNum.setValue(profile.info.fps.num)
        self.txtFrameRateDen.setValue(profile.info.fps.den)
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

        # Clear the following options
        self.cboSimpleVideoProfile.clear()
        self.cboSimpleQuality.clear()

        # get translations
        app = get_app()
        _ = app._tr


        # don't do anything if the combo has been cleared
        if selected_target:
            profiles_list = []

            # parse the xml to return suggested profiles
            profile_index = 0
            all_profiles = False
            for file in os.listdir(info.EXPORT_PRESETS_DIR):
                xmldoc = xml.parse(os.path.join(info.EXPORT_PRESETS_DIR, file))
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
                    ac = xmldoc.getElementsByTagName("audiocodec")
                    self.txtAudioCodec.setText(ac[0].childNodes[0].data)
                    sr = xmldoc.getElementsByTagName("samplerate")
                    self.txtSampleRate.setValue(int(sr[0].childNodes[0].data))
                    c = xmldoc.getElementsByTagName("audiochannels")
                    self.txtChannels.setValue(int(c[0].childNodes[0].data))
                    c = xmldoc.getElementsByTagName("audiochannellayout")

                    layout_index = 0
                    for layout in self.channel_layout_choices:
                        if layout == int(c[0].childNodes[0].data):
                            self.cboChannelLayout.setCurrentIndex(layout_index)
                            break
                        layout_index += 1

            # init the profiles combo
            for item in sorted(profiles_list):
                self.cboSimpleVideoProfile.addItem(item, self.profile_paths[item])

            if all_profiles:
                # select the project's current profile
                self.cboSimpleVideoProfile.setCurrentIndex(self.selected_profile_index)

            # set the quality combo
            # only populate with quality settings that exist
            if v_l or a_l:
                self.cboSimpleQuality.addItem(_("Low"), "Low")
            if v_m or a_m:
                self.cboSimpleQuality.addItem(_("Med"), "Med")
            if v_h or a_h:
                self.cboSimpleQuality.addItem(_("High"), "High")

            # Default to the highest quality setting
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
            if self.profile_paths[profile_name] == selected_profile_path:
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
        """ Start exporting video, but don't close window """
        # Disable controls
        self.txtFileName.setEnabled(False)
        self.txtExportFolder.setEnabled(False)
        self.tabWidget.setEnabled(False)
        self.export_button.setEnabled(False)
        self.exporting = True

        # Test the export settings before starting, must be executed out of process
        # to ensure we don't crash Python
        # export_test_path = os.path.join(info.PATH, "windows", "export_test.py")
        # process = subprocess.Popen(["python3", export_test_path, self.txtVideoFormat.text(), self.txtVideoCodec.text(), str(self.txtFrameRateNum.value()), str(self.txtFrameRateDen.value()), str(self.txtWidth.value()), str(self.txtHeight.value()), str(self.txtPixelRatioNum.value()), str(self.txtPixelRatioDen.value()), self.convert_to_bytes(self.txtVideoBitRate.text()), self.txtAudioCodec.text(), str(self.txtSampleRate.value()), str(self.txtChannels.value()), str(openshot.LAYOUT_STEREO), self.convert_to_bytes(self.txtAudioBitrate.text())], stdout=subprocess.PIPE)

        # Check the version of Blender
        test_success = False
        # while process.poll() is None:
        # 	output = str(process.stdout.readline())
        # 	print (output)
        # 	if "*SUCCESS*" in output:
        # 		test_success = True

        # Show error message (if needed)
        if test_success:
            # Test Failed
            print("SORRY, SOMETHING BAD HAPPENDED... TRY AGAIN LATER")

        else:
            # Test Succeeded
            # Determine final exported file path
            export_file_path = os.path.join(self.txtExportFolder.text().strip(), "%s.%s" % (
                self.txtFileName.text().strip(), self.txtVideoFormat.text().strip()))
            log.info(export_file_path)

            # Create FFmpegWriter
            try:
                w = openshot.FFmpegWriter(export_file_path)

                # Set video options
                w.SetVideoOptions(True,
                                  self.txtVideoCodec.text(),
                                  openshot.Fraction(self.txtFrameRateNum.value(),
                                                    self.txtFrameRateDen.value()),
                                  self.txtWidth.value(),
                                  self.txtHeight.value(),
                                  openshot.Fraction(self.txtPixelRatioNum.value(),
                                                    self.txtPixelRatioDen.value()),
                                  False,
                                  False,
                                  int(self.convert_to_bytes(self.txtVideoBitRate.text())))

                # Set audio options
                w.SetAudioOptions(True,
                                  self.txtAudioCodec.text(),
                                  self.txtSampleRate.value(),
                                  self.txtChannels.value(),
                                  self.cboChannelLayout.currentData(),
                                  int(self.convert_to_bytes(self.txtAudioBitrate.text())))

                # Open the writer
                w.Open()

                # Init progress bar
                self.progressExportVideo.setMinimum(self.txtStartFrame.value())
                self.progressExportVideo.setMaximum(self.txtEndFrame.value())

                # Write some test frames
                for frame in range(self.txtStartFrame.value(), self.txtEndFrame.value() + 1):
                    # Update progress bar
                    self.progressExportVideo.setValue(frame)
                    # Process events (to show the progress bar moving)
                    QCoreApplication.processEvents()

                    # Write the frame object to the video
                    w.WriteFrame(get_app().window.timeline_sync.timeline.GetFrame(frame))

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
                    log.info("Error setting invalid # of channels (%s)" % (self.txtChannels.value()))
                    track_metric_error("invalid-channels-%s-%s-%s-%s" % (self.txtVideoFormat.text(), self.txtVideoCodec.text(), self.txtAudioCodec.text(), self.txtChannels.value()))

                elif "InvalidSampleRate" in error_type_str:
                    log.info("Error setting invalid sample rate (%s)" % (self.txtSampleRate.value()))
                    track_metric_error("invalid-sample-rate-%s-%s-%s-%s" % (self.txtVideoFormat.text(), self.txtVideoCodec.text(), self.txtAudioCodec.text(), self.txtSampleRate.value()))

                elif "InvalidFormat" in error_type_str:
                    log.info("Error setting invalid format (%s)" % (self.txtVideoFormat.text()))
                    track_metric_error("invalid-format-%s" % (self.txtVideoFormat.text()))

                elif "InvalidCodec" in error_type_str:
                    log.info("Error setting invalid codec (%s/%s/%s)" % (self.txtVideoFormat.text(), self.txtVideoCodec.text(), self.txtAudioCodec.text()))
                    track_metric_error("invalid-codec-%s-%s-%s" % (self.txtVideoFormat.text(), self.txtVideoCodec.text(), self.txtAudioCodec.text()))

                elif "ErrorEncodingVideo" in error_type_str:
                    log.info("Error encoding video frame (%s/%s/%s)" % (self.txtVideoFormat.text(), self.txtVideoCodec.text(), self.txtAudioCodec.text()))
                    track_metric_error("video-encode-%s-%s-%s" % (self.txtVideoFormat.text(), self.txtVideoCodec.text(), self.txtAudioCodec.text()))

                # Show friendly error
                friendly_error = error_type_str.split("> ")[0].replace("<", "")

                # Prompt error message
                msg = QMessageBox()
                _ = get_app()._tr
                msg.setWindowTitle(_("Export Error"))
                msg.setText(_("Sorry, there was an error exporting your video: \n%s") % friendly_error)
                msg.exec_()


        # Accept dialog
        super(Export, self).accept()

        # Restore timeline settings
        self.restoreTimeline()

        log.info("End Accept")

    def restoreTimeline(self):
        """Restore timeline setting to original settings"""
        log.info("restoreTimeline")

        # Adjust the main timeline reader
        get_app().updates.update(["width"], self.original_width)
        get_app().updates.update(["height"], self.original_height)
        get_app().updates.update(["fps"], self.original_fps)
        get_app().updates.update(["sample_rate"], self.original_sample_rate)
        get_app().updates.update(["channels"], self.original_channels)
        get_app().updates.update(["channel_layout"], self.original_channel_layout)

        # Force ApplyMapperToClips to apply these changes
        get_app().window.timeline_sync.timeline.ApplyMapperToClips()

    def reject(self):

        log.info("Start Reject")
        self.exporting = False

        # Cancel dialog
        super(Export, self).reject()

        # Restore timeline settings
        self.restoreTimeline()

        log.info("End Reject")
