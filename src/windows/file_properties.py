"""
 @file
 @brief This file loads the File Properties dialog
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

from PyQt5.QtWidgets import (
    QDialog, QFileDialog, QDialogButtonBox, QPushButton,
    )

# Python module for libopenshot (required video editing module installed separately)
import openshot

from classes import info, ui_util, settings
from classes.app import get_app
from classes.logger import log
from classes.metrics import track_metric_screen


class FileProperties(QDialog):
    """ File Properties Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'file-properties.ui')

    def __init__(self, file):
        self.file = file

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
        track_metric_screen("file-properties-screen")

        # Add buttons to interface
        self.update_button = QPushButton(_('Update'))
        self.buttonBox.addButton(self.update_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(QPushButton(_('Cancel')), QDialogButtonBox.RejectRole)

        # Dynamically load tabs from settings data
        self.settings_data = settings.get_settings().get_all_settings()

        # Get file properties
        filename = os.path.basename(self.file.data["path"])
        file_extension = os.path.splitext(filename)[1]
        fps_float = float(self.file.data["fps"]["num"]) / float(self.file.data["fps"]["den"])

        tags = ""
        if "tags" in self.file.data.keys():
            tags = self.file.data["tags"]
        name = filename
        if "name" in self.file.data.keys():
            name = self.file.data["name"]

        # Populate fields
        self.txtFileName.setText(name)
        self.txtTags.setText(tags)
        self.txtFilePath.setText(self.file.data["path"])
        self.btnBrowse.clicked.connect(self.browsePath)

        # Populate video fields
        self.txtWidth.setValue(self.file.data["width"])
        self.txtHeight.setValue(self.file.data["height"])
        self.txtFrameRateNum.setValue(self.file.data["fps"]["num"])
        self.txtFrameRateDen.setValue(self.file.data["fps"]["den"])
        self.txtAspectRatioNum.setValue(self.file.data["display_ratio"]["num"])
        self.txtAspectRatioDen.setValue(self.file.data["display_ratio"]["den"])
        self.txtPixelRatioNum.setValue(self.file.data["pixel_ratio"]["num"])
        self.txtPixelRatioDen.setValue(self.file.data["pixel_ratio"]["den"])

        # Disable Framerate if audio stream found
        if self.file.data["has_audio"]:
            self.txtFrameRateNum.setEnabled(False)
            self.txtFrameRateDen.setEnabled(False)

        self.txtStartFrame.setMaximum(int(self.file.data["video_length"]))
        if 'start' not in file.data.keys():
            self.txtStartFrame.setValue(1)
        else:
            self.txtStartFrame.setValue(round(float(file.data["start"]) * fps_float) + 1)

        self.txtEndFrame.setMaximum(int(self.file.data["video_length"]))
        if 'end' not in file.data.keys():
            self.txtEndFrame.setValue(int(self.file.data["video_length"]))
        else:
            self.txtEndFrame.setValue(round(float(file.data["end"]) * fps_float) + 1)

        # Populate video & audio format
        self.txtVideoFormat.setText(file_extension.replace(".", ""))
        self.txtVideoCodec.setText(self.file.data["vcodec"])
        self.txtAudioCodec.setText(self.file.data["acodec"])
        self.txtSampleRate.setValue(int(self.file.data["sample_rate"]))
        self.txtChannels.setValue(int(self.file.data["channels"]))
        self.txtVideoBitRate.setValue(int(self.file.data["video_bit_rate"]))
        self.txtAudioBitRate.setValue(int(self.file.data["audio_bit_rate"]))

        # Populate output field
        self.txtOutput.setText(json.dumps(file.data, sort_keys=True, indent=2))

        # Add channel layouts
        selected_channel_layout_index = 0
        current_channel_layout = 0
        if self.file.data["has_audio"]:
            current_channel_layout = int(self.file.data["channel_layout"])
        self.channel_layout_choices = []
        layouts = [(0, _("Unknown")),
                   (openshot.LAYOUT_MONO, _("Mono (1 Channel)")),
                   (openshot.LAYOUT_STEREO, _("Stereo (2 Channel)")),
                   (openshot.LAYOUT_SURROUND, _("Surround (3 Channel)")),
                   (openshot.LAYOUT_5POINT1, _("Surround (5.1 Channel)")),
                   (openshot.LAYOUT_7POINT1, _("Surround (7.1 Channel)"))]
        for channel_layout_index, layout in enumerate(layouts):
            log.info(layout)
            self.channel_layout_choices.append(layout[0])
            self.cboChannelLayout.addItem(layout[1], layout[0])
            if current_channel_layout == layout[0]:
                selected_channel_layout_index = channel_layout_index

        # Select matching channel layout
        self.cboChannelLayout.setCurrentIndex(selected_channel_layout_index)

        # Load the interlaced options
        self.cboInterlaced.clear()
        self.cboInterlaced.addItem(_("Yes"), "Yes")
        self.cboInterlaced.addItem(_("No"), "No")
        if self.file.data["interlaced_frame"]:
            self.cboInterlaced.setCurrentIndex(0)
        else:
            self.cboInterlaced.setCurrentIndex(1)

        # Switch to 1st page
        self.toolBox.setCurrentIndex(0)

    def browsePath(self):
        # get translations
        app = get_app()
        _ = app._tr

        starting_folder, filename = os.path.split(self.file.data["path"])
        newFilePath = QFileDialog.getOpenFileName(None, _("Locate media file: %s") % filename, starting_folder)[0]
        self.txtFilePath.setText(newFilePath)

    def accept(self):
        # Update file details
        self.file.data["name"] = self.txtFileName.text()
        self.file.data["tags"] = self.txtTags.text()

        # experimental: update file path
        self.file.data["path"] = self.txtFilePath.text()

        # Update Framerate
        self.file.data["fps"]["num"] = self.txtFrameRateNum.value()
        self.file.data["fps"]["den"] = self.txtFrameRateDen.value()

        # Update start / end frame
        fps_float = float(self.file.data["fps"]["num"]) / float(self.file.data["fps"]["den"])
        if self.txtStartFrame.value() != 1 or self.txtEndFrame.value() != self.file.data["video_length"]:
            self.file.data["start"] = (self.txtStartFrame.value() - 1) / fps_float
            self.file.data["end"] = (self.txtEndFrame.value() - 1) / fps_float

        # Save file object
        self.file.save()

        # Accept dialog
        super(FileProperties, self).accept()

    def reject(self):

        # Cancel dialog
        super(FileProperties, self).reject()
