""" 
 @file
 @brief This file contains the blender file treeview, used by the 3d animated titles screen
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
from classes import updates
from classes import info
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeView, QApplication, QMessageBox, QAbstractItemView, QMenu
from windows.models.blender_model import BlenderModel
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json

class BlenderTreeView(QTreeView):
	""" A TreeView QWidget used on the animated title window """ 

	def currentChanged(self, selected, deselected):
		# get selected item
		self.selected = selected
		self.deselected = deselected
		
	def contextMenuEvent(self, event):
		menu = QMenu(self)
		menu.addAction(self.win.actionDetailsView)
		menu.addAction(self.win.actionThumbnailView)
		menu.exec_(QCursor.pos())
		
		# Ignore event, propagate to parent 
		event.ignore()
		super().mouseMoveEvent(event)
	
	def mousePressEvent(self, event):

		# Ignore event, propagate to parent 
		event.ignore()
		super().mousePressEvent(event)
		
	def refresh_view(self):
		self.blender_model.update_model()
		self.hideColumn(2)
			
	def __init__(self, *args):
		# Invoke parent init
		QTreeView.__init__(self, *args)
		
		# Get a reference to the window object
		self.win = get_app().window
		
		# Get Model data
		self.blender_model = BlenderModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.selected = None
		self.deselected = None

		# Setup header columns
		self.setModel(self.blender_model.model)
		self.setIconSize(QSize(131, 108))
		self.setIndentation(0)
		self.setSelectionBehavior(QTreeView.SelectRows)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		
		# Refresh view
		self.refresh_view()

