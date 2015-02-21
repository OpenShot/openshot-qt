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
from classes.query import File, Clip
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTableView, QApplication, QMessageBox, QAbstractItemView, QMenu, QSizePolicy, QHeaderView
from windows.models.properties_model import PropertiesModel
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json

class PropertiesTableView(QTableView):
	""" A Properties Table QWidget used on the main window """ 
	
	def select_item(self, item_id, item_type):
		""" Update the selected item in the properties window """
		
		# Get translation object
		_ = get_app()._tr
		
		# Set label
		if item_id:
			get_app().window.lblSelectedItem.setText(_("Selection: %s") % item_id)
		else:
			get_app().window.lblSelectedItem.setText(_("No Selection"))
			
		# Update item
		self.clip_properties_model.update_item(item_id, item_type)

	def select_frame(self, frame_number):
		""" Update the values of the selected clip, based on the current frame """
		
		# Update item
		self.clip_properties_model.update_frame(frame_number)
	
	def filter_changed(self, value=None):
		""" Filter the list of properties """
		
		# Update model
		self.clip_properties_model.update_model(value)
		
	def contextMenuEvent(self, pos):
		# Get data model and selection 
		model = self.clip_properties_model.model
		selected = self.selectionModel().selectedIndexes()
		
		# Get the currently selected item
		selected_label = None
		selected_value = None
		for selection in selected:
			selected_row = model.itemFromIndex(selection).row()
			selected_label = model.item(selected_row, 0)
			selected_value = model.item(selected_row, 1)
			self.selected_item = selected_value # keep track of selected value column
			frame_number = self.clip_properties_model.frame_number

		# If item selected
		if selected_label and selected_value:
			# Get data from selected item
			property = selected_label.data()
			property_name = property[1]["name"]
			points = property[1]["points"]
			property_key = property[0]
			clip_id = selected_value.data()
	
			log.info("Context menu shown for %s (%s) for clip %s on frame %s" % (property_name, property_key, clip_id, frame_number))
			
			# Popup context menu (if keyframeable)
			if points > 1:
				menu = QMenu(self)
				Bezier_Action = menu.addAction("BEZIER")
				Bezier_Action.triggered.connect(self.Bezier_Action_Triggered)
				Linear_Action = menu.addAction("LINEAR")
				Linear_Action.triggered.connect(self.Linear_Action_Triggered)
				Constant_Action = menu.addAction("CONSTANT")
				Constant_Action.triggered.connect(self.Constant_Action_Triggered)
				menu.popup(QCursor.pos())
			
	def Bezier_Action_Triggered(self, event):
		log.info("Bezier_Action_Triggered")
		self.clip_properties_model.value_updated(self.selected_item, 0)
		
	def Linear_Action_Triggered(self, event):
		log.info("Linear_Action_Triggered")
		self.clip_properties_model.value_updated(self.selected_item, 1)
		
	def Constant_Action_Triggered(self, event):
		log.info("Constant_Action_Triggered")
		self.clip_properties_model.value_updated(self.selected_item, 2)

		
	def __init__(self, *args):
		# Invoke parent init
		QTableView.__init__(self, *args)
		
		# Get a reference to the window object
		self.win = get_app().window
		
		# Get Model data
		self.clip_properties_model = PropertiesModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.selected = []
		self.selected_item = None

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

	
	
