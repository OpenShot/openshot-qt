""" 
 @file
 @brief This file contains the squeze dialog (i.e see the effect applied on the video file)
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
import shutil
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic
from classes import info, ui_util, settings, qt_types, updates
from classes.logger import log
from classes.app import get_app
from windows.new_preset_name import NewPresetName
import openshot

class CurrentExportingProjects(QDialog):
	""" Current Exporting Projects """
	
	#Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'current-exporting-projects.ui')
	
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

		#set events handlers
		self.btnAdd.clicked.connect(self.add_preset)
		self.btnModified.clicked.connect(self.modified_preset)
		self.btnRename.clicked.connect(self.rename_preset)
		self.btnCopy.clicked.connect(self.copy_preset)
		self.btnDelete.clicked.connect(self.delete_preset)
		
	def add_preset(self):
		""" Add a new preset previously created """
		log.info('A new preset has been created')
		pass
		
	def modified_preset(self):
		""" Modified a preset previously created """
		log.info('A preset has been modified')
		pass
		
	def rename_preset(self):
		""" Rename a preset previously created """
		log.info('A preset has been renamed')
		windo = NewPresetName()
		windo.exec_()

	def copy_preset(self):
		""" Copy a preset previously created """
		log.info('A preset has been copied')
		pass
		
	def delete_preset(self):
		""" Delete a preset previously created """
		log.info('A preset has been deleted')
		pass
