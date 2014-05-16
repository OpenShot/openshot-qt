""" 
 @file
 @brief This file loads the animated title dialog (i.e Blender animation automation)
 @author Noah Figg <eggmunkee@hotmail.com>
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

import sys, os
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.query import File
from windows.views.blender_treeview import BlenderTreeView
import time, uuid, shutil
import threading, subprocess, re
import math
import subprocess
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json


class AnimatedTitle(QDialog):
	""" Animated Title Dialog """
	
	# Path to ui file
	ui_path = os.path.join(info.PATH, 'windows','ui', 'animated-title.ui')
		
	def __init__(self):

		#Create dialog class
		QDialog.__init__(self)

		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)

		#Init UI
		ui_util.init_ui(self)
		
		# Add blender treeview
		self.blenderTreeView = BlenderTreeView(self)
		self.verticalLayout.addWidget(self.blenderTreeView)
		
		# Add render button
		app = get_app()
		_ = app._tr
		self.buttonBox.addButton(QPushButton(_('Render')), QDialogButtonBox.AcceptRole)
		self.buttonBox.addButton(QPushButton(_('Cancel')), QDialogButtonBox.RejectRole)

		# Init variables
		self.unique_folder_name = str(uuid.uuid1())
		self.output_dir = os.path.join(info.USER_PATH, "blender")
		self.selected_template = ""
		self.is_rendering = False
		self.my_blender = None
		
		# Clear all child controls
		self.clear_effect_controls()
		
	def accept(self):
		""" Start rendering animation, but don't close window """
		
		# Render
		self.blenderTreeView.Render()

	def close(self):
		""" Actually close window and accept dialog """
		
		# Re-enable interface
		self.blenderTreeView.enable_interface()
		
		# Accept dialog
		super(AnimatedTitle, self).accept()

	def closeEvent(self, event):

		# Stop threads
		self.blenderTreeView.background.quit()
		
		# Re-enable interface
		self.blenderTreeView.enable_interface()
		
	def reject(self):

		# Stop threads
		self.blenderTreeView.background.quit()
		
		# Cancel dialog
		super(AnimatedTitle, self).reject()

	def add_file(self, filepath):
		""" Add an animation to the project file tree """
		path, filename = os.path.split(filepath)
		
		# Add file into project
		app = get_app()

		# Check for this path in our existing project data
		file = File.get(path=filepath)
		
		# If this file is already found, exit
		if file:
			return

		# Get the JSON for the clip's internal reader
		try:
			# Open image sequence in FFmpegReader
			reader = openshot.FFmpegReader(filepath)
			reader.Open()
			
			# Serialize JSON for the reader
			file_data = json.loads(reader.Json())
	
			# Set media type
			file_data["media_type"] = "video"
	
			# Save new file to the project data
			file = File()
			file.data = file_data
			file.save()
			return True
		
		except:
			# Handle exception
			msg = QMessageBox()
			msg.setText(app._tr("{} is not a valid video, audio, or image file.".format(filename)))
			msg.exec_()
			return False
		
	def clear_effect_controls(self):
		""" Clear all child widgets used for settings """
		
		# Loop through child widgets
		for child in self.settingsContainer.children():
			try:
				self.settingsContainer.layout().removeWidget(child)
				child.deleteLater()
			except:
				pass

