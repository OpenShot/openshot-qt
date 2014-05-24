""" 
 @file
 @brief This file contains the clip properties model, used by the properties view
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

import os, types
from urllib.parse import urlparse
from classes import updates
from classes import info
from classes.query import File
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeWidget, QApplication, QMessageBox, QTreeWidgetItem, QAbstractItemView
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
    import json
except ImportError:
    import simplejson as json

class ClipStandardItemModel(QStandardItemModel):
	
	def __init__(self, parent=None):
		QStandardItemModel.__init__(self)
		
	def mimeData(self, indexes):
		
		# Create MimeData for drag operation
		data = QMimeData()

		# Get list of all selected file ids
		property_names = []
		for item in indexes:
			selected_row = self.itemFromIndex(item).row()
			property_names.append(self.item(selected_row, 0).data())
		data.setText(json.dumps(property_names))

		# Return Mimedata
		return data


class ClipPropertiesModel():
	
	
	def itemChanged(self, item):
		log.info("itemChanged to %s" % item.text())
		
	
	def update_model(self, filter=""):
		log.info("updating clip properties model.")
		app = get_app()
		
		# Clear previous model data (if any)
		self.model.clear()

		# Add Headers
		self.model.setHorizontalHeaderLabels(["Property", "Value" ])
		
		# Get a generic emtpy clip
		c = openshot.Clip()
		
		# Get list of clip properties [ ('Location x', 'location_x', <class 'openshot.Keyframe'>), ('Location y', 'location_y', <class 'openshot.Keyframe'>), ('Open', 'Open', <class 'method'>),... ] 
		all_properties = sorted([(prop.capitalize().replace('_',' '), prop, type(getattr(c, prop))) for prop in c.__dir__()])

		# Loop through properties, and build a model	
		for property in all_properties:
			label = property[0]
			name = property[1]
			prop_type = property[2]
			
			# Hide certain properties
			if name.startswith("_") or name.lower().startswith("get") or "json" in name.lower() or name.lower() == "this":
				# skip this property
				continue
			
			# Hide filtered out properties
			if filter and filter.lower() not in name.lower():
				continue
			
			# Better determine type of methods
			try:
				if prop_type == types.MethodType:
					# Set type to return value
					prop_type = type(prop_type())
			except:
				# If requires arguments or fails to execute function, skip property
				continue
				
			
			row = []
			
			# Append Property Name
			col = QStandardItem("Property")
			col.setData(name, Qt.DisplayRole)
			col.setText(label)
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)
			
			# Append Value
			col = QStandardItem("Value")
			col.setData("", Qt.DisplayRole)
			col.setText("")
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
			row.append(col)

			# Append ROW to MODEL (if does not already exist in model)
			self.model.appendRow(row)


	def __init__(self, *args):

		# Create standard model 
		self.model = ClipStandardItemModel()
		self.model.setColumnCount(2)

		# Connect data changed signal
		self.model.itemChanged.connect(self.itemChanged)
		