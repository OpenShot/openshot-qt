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
	
	#Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'export-video.ui')
	
	def __init__(self):
		
		#Create dialog class
		QDialog.__init__(self)
		
		#Load UI from designer
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
		self.btnsavepreset.clicked.connect(self.save_preset)
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
		#self.chkentiresequence.isChecked(True)
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

		#Populate new preset name
		self.cbopreset.addItem("<Select a Preset or Create your own>")
		self.preset_path = os.path.join(info.PATH, 'presets')
		for file in sorted(os.listdir(self.preset_path)):
			if fnmatch.fnmatch(file, '*.xml'):
				(fileName, fileExtension) = os.path.splitext(file)
			self.cbopreset.addItem(file.replace("_", " "))
			
		#populate compression method
		for compression_method in [_("Average Bit Rate Size"), _("Average Bit Rate Quality")]:
			self.cmbcompressionmethod.addItem(compression_method)  
			
		#populate image format Qcombobox
		image_extension = [_(".jpg"), (".jpeg"), (".png"), (".bmp"), (".svg"), (".thm"), (".gif"), (".ppm"), (".pgm"), (".tif"), (".tiff")]
		for extension in image_extension:
			self.cmbformatimage.addItem(extension)

	def choose_folder_output(self):
		""" Choose a folder for the render """
		
		app = get_app()
		_ = app._tr
		
		files = QFileDialog.getOpenFileNames(self, _("Export File..."))[0]
		#for file_path in files:
			#self.filesTreeView.add_file(file_path)
			#self.filesTreeView.refresh_view()
			#log.info("Exported project {}".format(file_path))
			
	def lenght_group_state(self):
		""" State of the Lenght Group """
		#if state == Qt.Checked:
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
		
	def save_preset(self):
		""" Save a new preset in the Current Exporting Project screen"""
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
		#Todo find a way to add custom Item and avoid to run for each item the preset screen
		log.info('The Current Exporting Project screen has been called')
		windo = CurrentExportingProjects()
		windo.exec_()

		if self.cbopreset.currentIndex() >0:
			preset = self.cbopreset.currentText()
			self.preset_name = preset.replace(".xml", "")
			self.preset_name = 'Custom' + preset_name
	
	def preserve_ratio(self):
		""" Keep the aspect ratio """
		pass
				
	def load_compression_method_activated(self):
		""" Choose two different method following the size or the quality """
		
		#Todo find a way to display the corresponding screen 
		
		#compression_method = self.cmbcompressionmethod.setCurrentText()
		#if compression_method.is_selected == _("Average Bit Rate Size"):
			#self.cmbcompressionmethod["compression_method"] = "Average Bit Rate Size"
			#msg = QMessagebox()
			#msg.setText(_("Average Bit Rate Size Screen is launched"))
			#msg.exec_()
		#else:
			#self.cmbcompressionmethod["compression_method"] = "Average Bit Rate Quality"
			#msg = QMessageBox()
			#msg.setText(_("Average Bit Rate Quality Screen is launched"))
			#msg.exec_()
		pass
		
	def load_format_video(self):
		""" Load all video format """
		#log.info('The Video Format {} has been used'.format(format))
		pass
		
	def video_codecs(self):
		""" Display all Codecs Video """
		#log.info('The Video codec {} has been used'.format(video)) 
		pass
		
	def rate_changed(self):
		""" Rate is changed """
		#log.info('The Rate {} has been changed to {}'.format(initial_value, final_value))
		pass

	def max_changed(self):
		""" Max Rate is changed """
		#log.info('The Max Rate {} has been changed to {}'.format(initial_value, final_value))
		pass
		
	def audio_codecs(self):
		""" Display all Codecs Audio """
		#log.info('The Rate {} has been changed to {}'.format(initial_value, final_value))
		pass
		
	def simple_rate_changed(self):
		""" Display the Simple Rate choosen """
		#log.info('The Simple Rate {} has been changed to {}'.format(initial_simplerate, final_simplerate))
		pass
		
	def channels_selected(self):
		""" Display the Channel choosen """
		#log.info('The Channel {} has been changed to {}'.format(initial_channel, final_channel))
		pass
		
	def bitrate_changed(self):
		""" Display the Bitrate """
		#log.info('The Bitrate {} has been changed to {}'.format(initial_bitrate, final_bitrate))
		pass
			
	def format_image(self):
		""" Display all Format Image """
		#log.info('The Format Image {} has been changed to {}'.format(initial_format, final_format))
		pass
		
	def quality_changed(self):
		""" Display the Quality """
		#log.info('The Quality {} has been changed to {}'.format(initial_quality, final_quality))
		pass
		
	def digits_changed(self):
		""" Display Digits """
		#log.info('Digits {} have been changed to {}'.format(initial_digits, final_digits))
		pass
		
	def interval_changed(self):
		""" Display interval """
		#log.info(' Interval {} has been changed to {}'.format(initial_interval, final_interval)
		pass
		
	def offset_changed(self):
		""" Display offset """
		#log.info('Offset {} has been changed to {}'.format(initial_offset, final_offset))
		pass
	
	def new_prefix(self):
		""" Display the new prefix """
		#log.info('The prefix {} has been changed to {}'.format(initial_prefix, final_prefix))
		pass	
	
	def new_suffix(self):
		""" Display the new suffix """
		#log.info('The suffix {} has been changed to {}'.format(initial_suffix, final_suffix))
		pass
		
	def run_progress_bar_export(self):
		""" Run the conversion and show a progress bar for this one until it will be finished """
		log.info('Conversion has been started')
		windo = ProgressBarExport()
		windo.exec_() 
		
	#def new_frame_name(self):
		#""" Display the new frame name """
		#log.info('')
		#pass
