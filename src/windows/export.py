"""
 @file
 @brief This file loads the Video Export dialog (i.e where is all preferences)
 @author Jonathan Thomas <jonathan@openshot.org>

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
import subprocess
import locale
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from windows.profile_manager import ProfileManager
import xml.dom.minidom as xml
import functools
import openshot

class Export(QDialog):
	""" Export Dialog """
	
	#Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'export.ui')
	
	def __init__(self):
		
		#Create dialog class
		QDialog.__init__(self)
		
		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)
		
		#Init UI
		ui_util.init_ui(self)

		#get translations
		app = get_app()
		_ = app._tr
		
		# Get settings
		self.s = settings.get_settings()
		
		# Dynamically load tabs from settings data
		self.settings_data = settings.get_settings().get_all_settings()
		
		# Add buttons to interface
		self.buttonBox.addButton(QPushButton(_('Export Video')), QDialogButtonBox.AcceptRole)
		self.buttonBox.addButton(QPushButton(_('Cancel')), QDialogButtonBox.RejectRole)

		# Default export path
		self.txtExportFolder.setText(info.HOME_PATH)
		
		# Default image type
		self.txtImageFormat.setText("%05.png")
		
		# Loop through Export To options
		export_options = [_("Video & Audio"), _("Image Sequence")]
		for option in export_options:
			# append profile to list
			self.cboExportTo.addItem(option)

		# Connect signals
		self.btnBrowse.clicked.connect(functools.partial(self.btnBrowse_clicked))
		self.cboSimpleProjectType.currentIndexChanged.connect(functools.partial(self.cboSimpleProjectType_index_changed, self.cboSimpleProjectType))
		self.cboProfile.currentIndexChanged.connect(functools.partial(self.cboProfile_index_changed, self.cboProfile))
		self.cboSimpleTarget.currentIndexChanged.connect(functools.partial(self.cboSimpleTarget_index_changed, self.cboSimpleTarget))
		self.cboSimpleVideoProfile.currentIndexChanged.connect(functools.partial(self.cboSimpleVideoProfile_index_changed, self.cboSimpleVideoProfile))
		self.cboSimpleQuality.currentIndexChanged.connect(functools.partial(self.cboSimpleQuality_index_changed, self.cboSimpleQuality))
		
		
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
		presets = list(set(presets))
		for item in sorted(presets):
			self.cboSimpleProjectType.addItem(item, item)
		





	def cboSimpleProjectType_index_changed(self, widget, index):
		selected_project = widget.itemData(index)

		#set the target dropdown based on the selected project type 
		#first clear the combo
		self.cboSimpleTarget.clear()
		
		#get translations
		app = get_app()
		_ = app._tr
		
		#parse the xml files and get targets that match the project type
		project_types = []
		for file in os.listdir(info.EXPORT_PRESETS_DIR):
			xmldoc = xml.parse(os.path.join(info.EXPORT_PRESETS_DIR, file))
			type = xmldoc.getElementsByTagName("type")
			
			if _(type[0].childNodes[0].data) == selected_project:
				titles = xmldoc.getElementsByTagName("title")
				for title in titles:
					project_types.append(_(title.childNodes[0].data))
		
		# Add all targets for selected project type
		for item in sorted(project_types):
			self.cboSimpleTarget.addItem(item, item)

		
	def cboProfile_index_changed(self, widget, index):
		selected_profile_path = widget.itemData(index)
		log.info(selected_profile_path)
		
		#get translations
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
		
		#get translations
		app = get_app()
		_ = app._tr


		#don't do anything if the combo has been cleared
		if selected_target:
			profiles_list = []
			
			#parse the xml to return suggested profiles
			profile_index = 0
			for file in os.listdir(info.EXPORT_PRESETS_DIR):
				xmldoc = xml.parse(os.path.join(info.EXPORT_PRESETS_DIR, file))
				title = xmldoc.getElementsByTagName("title")
				if _(title[0].childNodes[0].data) == selected_target:
					profiles = xmldoc.getElementsByTagName("projectprofile")
					
					#get the basic profile
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

					#get the video bit rate(s)
					videobitrate = xmldoc.getElementsByTagName("videobitrate")
					for rate in videobitrate:
						v_l = rate.attributes["low"].value
						v_m = rate.attributes["med"].value
						v_h = rate.attributes["high"].value
						self.vbr = {_("Low"): v_l, _("Med"): v_m, _("High"): v_h}

					#get the audio bit rates
					audiobitrate = xmldoc.getElementsByTagName("audiobitrate")
					for audiorate in audiobitrate:
						a_l = audiorate.attributes["low"].value
						a_m = audiorate.attributes["med"].value
						a_h = audiorate.attributes["high"].value
						self.abr = {_("Low"): a_l, _("Med"): a_m, _("High"): a_h}
					
					#get the remaining values
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
					
			# init the profiles combo
			for item in sorted(profiles_list):
				self.cboSimpleVideoProfile.addItem(item, self.profile_paths[item])

			if all_profiles:
				# select the project's current profile
				self.cboSimpleVideoProfile.setCurrentIndex(self.selected_profile_index)

			#set the quality combo
			#only populate with quality settings that exist
			if v_l or a_l:
				self.cboSimpleQuality.addItem(_("Low"), "Low")
			if v_m or a_m:
				self.cboSimpleQuality.addItem(_("Med"), "Med")
			if v_h or a_h:
				self.cboSimpleQuality.addItem(_("High"), "High")
		
		
	def cboSimpleVideoProfile_index_changed(self, widget, index):
		selected_profile_path = widget.itemData(index)
		log.info(selected_profile_path)

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

		# Set the video and audio bitrates
		if selected_quality:
			self.txtVideoBitRate.setText(self.vbr[selected_quality])
			self.txtAudioBitrate.setText(self.abr[selected_quality])
		
		
	def btnBrowse_clicked(self):
		log.info("btnBrowse_clicked")
		
		#get translations
		app = get_app()
		_ = app._tr
		
		# update export folder path
		file_path = QFileDialog.getExistingDirectory(self, _("Choose a Folder...")) #, options=QFileDialog.DontUseNativeDialog)
		self.txtExportFolder.setText(file_path)
		


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

		# Test the export settings before starting, must be executed out of process
		# to ensure we don't crash Python
		#export_test_path = os.path.join(info.PATH, "windows", "export_test.py")
		#process = subprocess.Popen(["python3", export_test_path, self.txtVideoFormat.text(), self.txtVideoCodec.text(), str(self.txtFrameRateNum.value()), str(self.txtFrameRateDen.value()), str(self.txtWidth.value()), str(self.txtHeight.value()), str(self.txtPixelRatioNum.value()), str(self.txtPixelRatioDen.value()), self.convert_to_bytes(self.txtVideoBitRate.text()), self.txtAudioCodec.text(), str(self.txtSampleRate.value()), str(self.txtChannels.value()), str(openshot.LAYOUT_STEREO), self.convert_to_bytes(self.txtAudioBitrate.text())], stdout=subprocess.PIPE)

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
			export_file_path = os.path.join(self.txtExportFolder.text().strip(), "%s.%s" % (self.txtFileName.text().strip(), self.txtVideoFormat.text().strip()))
			log.info(export_file_path)
			
			# Create FFmpegWriter
			try:
				w = openshot.FFmpegWriter(export_file_path);
				
				# Set Audio & Video Options
				w.SetVideoOptions(True, self.txtVideoCodec.text(), openshot.Fraction(self.txtFrameRateNum.value(), self.txtFrameRateDen.value()), self.txtWidth.value(), self.txtHeight.value(), openshot.Fraction(self.txtPixelRatioNum.value(), self.txtPixelRatioDen.value()), False, False, int(self.convert_to_bytes(self.txtVideoBitRate.text())));
				w.SetAudioOptions(True, self.txtAudioCodec.text(), self.txtSampleRate.value(), self.txtChannels.value(), openshot.LAYOUT_STEREO, int(self.convert_to_bytes(self.txtAudioBitrate.text())));
		
				# Open the writer
				w.Open();

				# Init progress bar
				self.progressExportVideo.setMinimum(1)
				self.progressExportVideo.setMaximum(100)
				
				# Write some test frames
				#w.WriteFrame(get_app().window.timeline_sync.timeline, 1, 100)
				for frame in range(1, 101):
					self.progressExportVideo.setValue(frame)
					QCoreApplication.processEvents()
					w.WriteFrame(get_app().window.timeline_sync.timeline.GetFrame(frame))
				
				# Close writer
				w.Close()
				
			except:
				log.info("Error writing video file")
		
		
		# Close dialog		
		self.close()

		# Accept dialog
		super(Export, self).accept()

		log.info("End Accept")
		

	def reject(self):
		
		log.info("Start Reject")
		
		# Cancel dialog
		super(Export, self).reject()

		log.info("End Reject")