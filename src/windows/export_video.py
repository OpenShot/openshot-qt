"""
 @file
 @brief This file loads the Export Video dialog (i.e export video clip in another or not format)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2014 OpenShot Studios, LLC
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
import fnmatch
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from classes import info, ui_util, settings, qt_types, updates
from classes.logger import log
from classes.app import get_app
from windows.squeze import Squeze
from windows.presets import Presets
from windows.current_exporting_projects import CurrentExportingProjects
from windows.progress_bar_export import ProgressBarExport
import openshot


class ExportVideo(QDialog):
    """ Export Video Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'export-video.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        #Init UI
        ui_util.init_ui(self)

        #get translations
        self.app = get_app()
        _ = self.app._tr

        self.preset_name = ""
        self.project = self.app.project

        #set events handlers
        self.btnfolder.clicked.connect(self.choose_folder_output)
        self.btndeletepreset.clicked.connect(self.delete_preset)
        self.btnapplypreset.clicked.connect(self.apply_preset)
        self.cbopreset.activated.connect(self.load_preset)
        self.chkentiresequence.stateChanged.connect(self.lenght_group_state)
        self.chkprojectprofilesettings.stateChanged.connect(self.direction_group)
        self.cbosqueze.activated.connect(self.load_squeze)
        self.cmbformatvideo.activated.connect(self.load_format_video)
        self.cmbvideo.activated.connect(self.video_codecs)
        self.cmbcompressionmethod.activated.connect(self.load_compression_method_activated)
        self.btnpreserveratio.clicked.connect(self.preserve_ratio)
        self.spbrate.valueChanged.connect(self.rate_changed)
        self.spbmax.valueChanged.connect(self.max_changed)
        self.cmbaudio.activated.connect(self.audio_codecs)
        self.cmbsimplerate.activated.connect(self.simple_rate_changed)
        self.cmbchannels.activated.connect(self.channels_selected)
        self.sliderbitrate.valueChanged.connect(self.bitrate_changed)
        self.cmbformatimage.activated.connect(self.format_image)
        self.sliderquality.valueChanged.connect(self.quality_changed)
        self.spbdigits.valueChanged.connect(self.digits_changed)
        self.spbinterval.valueChanged.connect(self.interval_changed)
        self.spboffset.valueChanged.connect(self.offset_changed)
        self.lblprefix.textChanged.connect(self.new_prefix)
        self.lblsuffix.textChanged.connect(self.new_suffix)
        self.btnloadffmpegcommand.clicked.connect(self.load_ffmpeg_command)
        self.btnexportcommand.clicked.connect(self.load_export_command)
        self.btnexport.clicked.connect(self.run_progress_bar_export)
        #self.lblframename.textChanged.connect(self.new_frame_name)


        #Init some variables
        self.chkentiresequence.setEnabled(True)
        #self.chkentiresequence.setChecked()
        self.label_17.setEnabled(False)
        self.spbfrom.setEnabled(False)
        self.label_18.setEnabled(False)
        self.spbto.setEnabled(False)
        self.chkprojectprofilesettings.setEnabled(True)
        #self.chkprojectprofilesettings.isChecked(True)
        self.chkoriginalsize.setEnabled(False)
        self.label_20.setEnabled(False)
        self.spbwidth.setEnabled(False)
        self.label_21.setEnabled(False)
        self.btnpreserveratio.setEnabled(False)
        self.spbheight.setEnabled(False)
        self.chkdirectcopy.setEnabled(True)
        self.lblfilename.setText("My Awesome Movie")
        self.lblfilename.setFocus()
        self.lblfilename.selectAll()


        #Populate new preset name
        self.cbopreset.addItem("<Select a Preset or Create your own>")
        self.preset_path = os.path.join(info.PATH, 'presets')
        for file in sorted(os.listdir(self.preset_path)):
            if fnmatch.fnmatch(file, '*.xml'):
                (fileName, fileExtension) = os.path.splitext(file)
            self.cbopreset.addItem(file.replace("_", " "))

        #populate compression method

        compression_method = [_("Average Bit Rate")]
        for method in compression_method:
            self.cmbcompressionmethod.addItem(method)

        # populate image format Qcombobox
        image_extension = [_(".jpg"), _(".jpeg"), _(".png"), _(".bmp"), _(".svg"), _(".thm"), _(".gif"), _(".ppm"),
                           _(".pgm"),
                           _(".tif"), _(".tiff")]
        for extension in image_extension:
            self.cmbformatimage.addItem(extension)

        #populate format combo
        format_video = [_('.mkv'), _('.mov'), _('.mp4'), _('.dnxhd'), _('.dvd'), _('vob'), _('.mpg'), _('mpegts'), _('mpegps'),
                        _('.dv'), _('.avi'), _('.webm'), _('.ts'), _('.ogg'), _('.3gp2'), _('.3gp'), _('.roq'), _('rm'),
                        _('.divx'), _('.xvid'), _('.m2ts'), _('.r3d'), _('.MPG'), _('.flv'), _('avm2'), _('.asf'), _('.m4v'),
                        _('.h264'), _('.ac3'), _('.mp2'), _('.mp3'), _('.wav'), _('.ogg'), _('.flac'), _('.aac'), _('.wma'),
                        _('.opus'), _('.alaw'), _('.mulaw'), _('.mka')]

        for keys in format_video:
            self.cmbformatvideo.addItem(keys)

        for extension in format_video:
            self.cmbextension.addItem(extension)

        #populate video codecs combo
        video_codec = {'Xvid': 'libxvid', 'H264/MPEG-4 AVC':'libx264', 'OGG VORBIS': 'ogg', 'DV': 'dv', 'VP8': 'libvpx', 'Motion JPEG': 'mjepg',
                       'VP9': 'libvpx', 'H261': 'h261', 'H263': '263', 'Theora': '', 'Dirac': 'dirac', 'WMV': 'wmv', 'FLV': 'flv'}
        for keys in video_codec:
            self.cmbvideo.addItem(keys)

        aspect_ratio = [_('4/3'), _('16/9')]
        for ratio in aspect_ratio:
            self.cmbaspectratio.addItem(ratio)

        frame_per_seconds = [_('23.976'), _('24'), _('25'), _('29.976'), _('30'), _('50'), _('60')]
        for fps in frame_per_seconds:
            self.cmbfps.addItem(fps)

        #populate audio codecs combo
        audio_codec = {'MP3': 'libmp3lame', 'OGG VORBIS': 'oggvorbis','MP2': 'mpeg2audio', 'FLAC': 'flac',
                       'AAC-LC': 'aac', 'WAVE': 'wav', 'AC3': 'ac3', 'DTS': 'dts', 'WMA': 'wma', 'AMR-NB': '',
                       'PCM 8 bits': 'u8', 'PCM 16 bits little-endian': 'u16le', 'PCM 16 bits big-endian': 'u16be'}
        for keys in audio_codec:
            self.cmbaudio.addItem(keys)

        #Populate simplerate combo
        simple_rate = [_('Copy'), _('8000'), _('11025'), _('16000'), _('22050'), _('24000'), _('32000'), _('44100'),
                       _('48000')]
        for rate in simple_rate:
            self.cmbsimplerate.addItem(rate)

        #populate audio channels
        audio_channels = [_('Copy'), _('Mono'), _('Stereo'), _('Join Stereo'), _('DTS')]
        for channels in audio_channels:
            self.cmbchannels.addItem(channels)

        #populate bitrate
        #audio_bitrates = [_('32'), _('40'), _('48'), _('56'), _('64'), _('80'), _('96'), _('112'), _('128'), _('144'),
                          #_('160'), _('160'), _('168'), _('176'), _('184'), _('192'), _('200'), _('208'), _('216'),
                          #_('224'), _('232'), _('240'), _('248'), _('256'), _('264'), _('272'), _('280'), _('288'),
                          #_('296'), _('304'), _('312'), _('320'), _('328'), _('336'), _('344'), _('352'), _('360'), _('368'), _('376'), _('384'), _('392'), _('400'), _('408'),
                          #_('416'), _('424'), _('432'), _('440'), _('448'), _('456'), _('464'), _('472'), _('480'), _('488'), _('496'), _('504'), _('512'), _('520'), _('528'),
                          #_('536'), _('544'), _('552'), _('560'), _('568'), _('576'), _('584'), _('592'), _('600'), _('608'), _('616'), _('624'), _('632'), _('640')]
        #for bitrates in audio_bitrates:
            #self.sliderbitrate.value(bitrates)



    def choose_folder_output(self):
        """ Choose a folder for the render """

        app = get_app()
        _ = app._tr

        output_path = QFileDialog.getExistingDirectory(self, _("Choose Export Directory..."), self.lbldestination.text())

        if len(output_path) > 0:
            self.lbldestination.setText(output_path)
            log.info("Exported project to {}".format(output_path))

    def lenght_group_state(self):
        """ State of the Lenght Group """


        # if state == Qt.Checked:
        #self.chkentiresequence.isChecked(True)
        #else:
        # self.chkentiresequence.isChecked(False)
        #pass

    def direction_group(self):
        """ State of the Direction Group """
        pass


    def load_squeze(self):
        """ Display Squeze Screen """
        log.info('Squeze screen has been called')
        windo = Squeze()
        windo.exec_()


    def load_export_command(self):
        """" Display Export FFmpeg Command Pesonalized """
        log.info('FFmpeg Command Personlized screen has been called')
        windo = Presets()
        windo.exec_()


    def load_ffmpeg_command(self):
        """ Load a ffmpeg command Personalized"""
        log.info('Load an existing ffmpeg command')
        windo = Presets()
        windo.exec_()


    def delete_preset(self):
        """ Remove a preset """
        pass


    def apply_preset(self):
        """ Use the preset selectionned in the preset combobox"""
        pass


    def lblfilename_changed(self):
        """ Type a new name for the output file """
        pass


    def load_extension(self):
        """ Show the file extension """
        pass


    def load_destination(self):
        """ Show where the file will be written """
        pass


    def load_preset(self, preset_name=None):
        """ Run a preset or Create one """
        # Todo find a way to add custom Item and avoid to run for each item the preset screen
        log.info('The Current Exporting Project screen has been called')
        windo = CurrentExportingProjects()
        windo.exec_()

        if self.cbopreset.currentIndex() > 0:
            preset = self.cbopreset.currentText()
            self.preset_name = preset.replace(".xml", "")
            self.preset_name = 'Custom' + preset_name


    def preserve_ratio(self):
        """ Keep the aspect ratio """
        pass


    def load_compression_method_activated(self):
        """ Choose two different method following the size or the quality """

        # Todo find a way to display the corresponding screen
        app = get_app()
        _ = app._tr

        if self.cmbcompressionmethod.currentText():
            windo = AverageBitRate()
            windo.exec_()

    def load_format_video(self):
        """ Load all video format """
        # log.info('The Video Format {} has been used'.format(format))
        pass


    def video_codecs(self):
        """ Display all Codecs Video """
        # log.info('The Video codec {} has been used'.format(video))
        pass


    def rate_changed(self):
        """ Rate is changed """
        # log.info('The Rate {} has been changed to {}'.format(initial_value, final_value))
        pass


    def max_changed(self):
        """ Max Rate is changed """
        # log.info('The Max Rate {} has been changed to {}'.format(initial_value, final_value))
        pass


    def audio_codecs(self):
        """ Display all Codecs Audio """
        # log.info('The Rate {} has been changed to {}'.format(initial_value, final_value))
        pass


    def simple_rate_changed(self):
        """ Display the Simple Rate choosen """
        # log.info('The Simple Rate {} has been changed to {}'.format(initial_simplerate, final_simplerate))
        pass


    def channels_selected(self):
        """ Display the Channel choosen """
        # log.info('The Channel {} has been changed to {}'.format(initial_channel, final_channel))
        pass


    def bitrate_changed(self):
        """ Display the Bitrate """
        # log.info('The Bitrate {} has been changed to {}'.format(initial_bitrate, final_bitrate))
        pass


    def format_image(self):
        """ Display all Format Image """
        # log.info('The Format Image {} has been changed to {}'.format(initial_format, final_format))
        pass


    def quality_changed(self):
        """ Display the Quality """
        # log.info('The Quality {} has been changed to {}'.format(initial_quality, final_quality))
        pass


    def digits_changed(self):
        """ Display Digits """
        # log.info('Digits {} have been changed to {}'.format(initial_digits, final_digits))
        pass


    def interval_changed(self):
        """ Display interval """
        # log.info(' Interval {} has been changed to {}'.format(initial_interval, final_interval)
        pass


    def offset_changed(self):
        """ Display offset """
        # log.info('Offset {} has been changed to {}'.format(initial_offset, final_offset))
        pass


    def new_prefix(self):
        """ Display the new prefix """
        # log.info('The prefix {} has been changed to {}'.format(initial_prefix, final_prefix))
        pass


    def new_suffix(self):
        """ Display the new suffix """
        # log.info('The suffix {} has been changed to {}'.format(initial_suffix, final_suffix))
        pass


    def run_progress_bar_export(self):
        """ Run the conversion and show a progress bar for this one until it will be finished """
        log.info('Conversion has been started')
        windo = ProgressBarExport()
        windo.exec_()


        # def new_frame_name(self):
        #""" Display the new frame name """
        #log.info('')
        #pass


class AverageBitRate(QDialog):
    """ Average Bitrate Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'compression-method.ui')

    def __init__(self):
        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)

        # get translations
        self.app = get_app()
        _ = self.app._tr

        #set events handlers
        self.cbosize.activated.connect(self.cbosize_changed)
        #self.spnsize.valueChanged(int).connect(self.spnsize_changed)

        #Init some variables

        #Populate compression-method
        compression_method = [_("Target File Size"), _("Constant Quality")]
        for method in compression_method:
            self.cbosize.addItem(method)

        self.hide_quality_values()

    def cbosize_changed(self):
        """
        Following the item selected, change the method of compression
        """
        if self.cbosize.currentIndex() == 0:
            self.lcdquality.setVisible(False)
            self.qualityslider.setVisible(False)
            self.label_4.setVisible(False)
            self.spnsize.setVisible(True)
            self.label_2.setVisible(True)
            self.label_3.setVisible(True)
            log.info('The Target size screen has been called')
        else:
            self.spnsize.setVisible(False)
            self.label_2.setVisible(False)
            self.label_3.setVisible(False)
            self.lcdquality.setVisible(True)
            self.qualityslider.setVisible(True)
            self.label_4.setVisible(True)
            log.info('The quality screen has been called')

    def spnsize_changed(self):
        """
        The user can change the size of the file
        """
        pass

    def hide_quality_values(self):
        """
        When the screen is displayed the first time and one the first item, parameters of Quality are hidden
        """
        self.lcdquality.setVisible(False)
        self.qualityslider.setVisible(False)
        self.label_4.setVisible(False)
        self.spnsize.setVisible(True)
        self.label_2.setVisible(True)
        self.label_3.setVisible(True)


