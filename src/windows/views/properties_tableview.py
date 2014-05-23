""" 
 @file
 @brief This file contains the properties tableview, used by the main window
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
from urllib.parse import urlparse
from classes import info
from classes.query import File
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTableView, QApplication, QMessageBox, QAbstractItemView, QMenu, QSizePolicy, QHeaderView
from windows.models.clip_properties_model import ClipPropertiesModel
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json

class PropertiesTableView(QTableView):
	""" A Properties Table QWidget used on the main window """ 
	
	def filter_changed(self, value=None):
		""" Filter the list of properties """
		
		# Update model
		self.clip_properties_model.update_model(value)
		
	def __init__(self, *args):
		# Invoke parent init
		QTableView.__init__(self, *args)
		
		# Get a reference to the window object
		self.win = get_app().window
		
		# Get Model data
		self.clip_properties_model = ClipPropertiesModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.selected = []

		# Setup header columns
		self.setModel(self.clip_properties_model.model)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.setWordWrap(True)

		# Get table header
		horizontal_header = self.horizontalHeader()
		horizontal_header.setSectionResizeMode(QHeaderView.Stretch)
		vertical_header = self.verticalHeader()
		vertical_header.setVisible(False)
		
		# Refresh view
		self.clip_properties_model.update_model()
		
		# Resize columns
		self.resizeColumnToContents(0)
		self.resizeColumnToContents(1)

		# Connect filter signals
		get_app().window.txtPropertyFilter.textChanged.connect(self.filter_changed)

	
	
