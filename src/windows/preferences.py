"""
 @file
 @brief This file loads the Preferences dialog (i.e where is all preferences)
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
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from windows.profile_manager import ProfileManager 

class Preferences(QDialog):
	""" Preferences Dialog """
	
	#Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'preferences.ui')
	
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
		
		#populate stock icons combo
		for use_stock in [_("Yes"), _("No")]:
			self.cboicons.addItem(use_stock)
			
		#populate output mode combo
		for output_mode in [_("sdl"), _("sdl_preview")]:
			self.cbooutputmode.addItem(output_mode)
			
		#populate scrolling options
		for use_stock in [_("Yes"), _("No")]:
			self.cbosmooth.addItem(use_stock)
		
		#populate icon size option	combo
		for icon_size in [_("Small"), _("Medium")]:
			self.cboiconsize.addItem(icon_size)
			
		#Add signals
		self.btnmanageprofiles.clicked.connect(self.load_profile_manager)
		
	def load_profile_manager(self):
		window = ProfileManager()
		window.exec_()
		
