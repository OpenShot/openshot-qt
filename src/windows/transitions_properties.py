"""
 @file
 @brief This file loads the transitions properties dialog (i.e contextual dialog for transitions and masks)
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

class TransitionsProperties(QDialog):
	""" Transitions Properties Dialog """

	# Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'transitions-properties.ui')
	
	def __init__(self):
		
		# Create dialog class
		QDialog.__init__(self)
		
		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)
		
		# Init UI
		ui_util.init_ui(self)
		
