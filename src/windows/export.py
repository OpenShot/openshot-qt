"""
 @file
 @brief This file loads the Preferences dialog (i.e where is all preferences)
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

		#load the simple project type dropdown
		presets = []
		for file in os.listdir(info.EXPORT_PRESETS_DIR):
			xmldoc = xml.parse(os.path.join(info.EXPORT_PRESETS_DIR, file))
			type = xmldoc.getElementsByTagName("type")
			log.info(os.path.join(info.EXPORT_PRESETS_DIR, file))
			presets.append(_(type[0].childNodes[0].data))
			
		# Exclude duplicates
		presets = list(set(presets))
		for item in sorted(presets):
			self.cboSimpleProjectType.addItem(item, item)
		
		# Connect signals
		self.cboSimpleProjectType.currentIndexChanged.connect(functools.partial(self.cboSimpleProjectType_index_changed, self.cboSimpleProjectType))
			

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
		selected_index = 0
		for profile_name in self.profile_names:
			
			# Add to dropdown
			self.cboSimpleVideoProfile.addItem(profile_name, self.profile_paths[profile_name])

			# Set default (if it matches the project)
			if app.project.get(['profile']) == profile_name:
				selected_index = box_index
			
			# increment item counter
			box_index += 1



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
		
		
		for item in sorted(project_types):
			self.cboSimpleTarget.addItem(item, item)
		
		if selected_project == _("All Formats"):
			pass
			# default to MP4 for this type
			#self.set_dropdown_values(_("OGG (theora/vorbis)"), self.cboSimpleTarget)
			
			# default the profile (based on the current project's profile)
			#self.set_dropdown_values(_(self.project.project_type), self.cboSimpleVideoProfile)
			
		else:
			# choose first taret
			#self.cboSimpleTarget.setEnabled(False)
			pass
		
		
	def accept(self):
		""" Start rendering animation, but don't close window """
		
		log.info("accept")
		
		# Render
		#self.blenderTreeView.Render()

	def reject(self):
		
		log.info("reject")

		# Stop threads
		#self.blenderTreeView.background.quit()
		
		# Cancel dialog
		super(Export, self).reject()