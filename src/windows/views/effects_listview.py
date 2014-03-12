""" 
 @file
 @brief This file contains the effects file listview, used by the main window
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
from PyQt5.QtWidgets import QListView, QApplication, QMessageBox, QAbstractItemView, QMenu
from windows.models.effects_model import EffectsModel
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json

class EffectsListView(QListView):
	""" A TreeView QWidget used on the main window """ 
	drag_item_size = 32
	
	def currentChanged(self, selected, deselected):
		# get selected item
		self.selected = selected
		self.deselected = deselected
		
	def contextMenuEvent(self, event):
		# Set context menu mode
		app = get_app()
		app.context_menu_object = "effects"
		
		menu = QMenu(self)
		menu.addAction(self.win.actionDetailsView)
		menu.addAction(self.win.actionThumbnailView)
		menu.exec_(QCursor.pos())

	def mouseMoveEvent(self, event):
		#If mouse drag detected, set the proper data and icon and start dragging
		if self.selected and event.buttons() & Qt.LeftButton == Qt.LeftButton and (event.pos() - self.startDragPos).manhattanLength() >= QApplication.startDragDistance():
			# Get selected item
			dragItemRow = self.effects_model.model.itemFromIndex(self.selected).row()
			
			# Get all selected rows items
			dragItem = []
			for col in range(5):
				dragItem.append(self.effects_model.model.item(dragItemRow, col))
			
			# Setup data based on item being dragged
			data = QMimeData()
			data.setText(dragItem[4].text()) # Add file path to mimedata
			# Start drag operation
			drag = QDrag(self)
			drag.setMimeData(data)
			drag.setPixmap(QIcon.fromTheme('document-new').pixmap(QSize(self.drag_item_size,self.drag_item_size)))
			drag.setHotSpot(QPoint(self.drag_item_size/2,self.drag_item_size/2))
			drag.exec_()

			# Accept event
			event.accept()
			return
		
		# Ignore event, propagate to parent 
		event.ignore()
		super().mouseMoveEvent(event)
	
	def mousePressEvent(self, event):
		# Save position of mouse press to check for drag
		self.startDragPos = event.pos()
		
		# Ignore event, propagate to parent 
		event.ignore()
		super().mousePressEvent(event)
		
		
	def clear_filter(self):
		get_app().window.effectsFilter.setText("")
		
	def filter_changed(self):
		self.effects_model.update_model()
		if self.win.effectsFilter.text() == "":
			self.win.actionEffectsClear.setEnabled(False)
		else:
			self.win.actionEffectsClear.setEnabled(True)
			
	def __init__(self, *args):
		# Invoke parent init
		QListView.__init__(self, *args)
		
		# Get a reference to the window object
		self.win = get_app().window
		
		# Get Model data
		self.effects_model = EffectsModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.startDragPos = None
		self.selected = None
		self.deselected = None

		# Setup header columns
		self.setModel(self.effects_model.model)
		self.setIconSize(QSize(131, 108))
		self.setViewMode(QListView.IconMode)
		self.setResizeMode(QListView.Adjust)

		# setup filter events
		app = get_app()
		app.window.effectsFilter.textChanged.connect(self.filter_changed)
		app.window.actionEffectsClear.triggered.connect(self.clear_filter)
		

	
	
