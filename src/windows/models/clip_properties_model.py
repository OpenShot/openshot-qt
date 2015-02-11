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


class ClipPropertiesModel(updates.UpdateInterface):
	
	# This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
	def changed(self, action):
		
		# Send a JSON version of the UpdateAction to the timeline webview method: ApplyJsonDiff()
		if action.type in ["insert", "delete"] and action.key == "clips":
			print ("CLIP CHANGED")
	
	
	def value_updated(self, item):
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
		
		# example code to add a keyframe
		c.alpha.AddPoint(1, 1.0);
		c.alpha.AddPoint(30, 0.0);
		c.scale_y.AddPoint(1, 100.0);
		c.scale_y.AddPoint(30, 25.0);
		
		all_properties = json.loads(c.PropertiesJSON(1))
		
		# Get list of clip properties [ ('Location x', 'location_x', <class 'openshot.Keyframe'>), ('Location y', 'location_y', <class 'openshot.Keyframe'>), ('Open', 'Open', <class 'method'>),... ] 
		#all_properties = sorted([(prop.capitalize().replace('_',' '), prop, type(getattr(c, prop))) for prop in c.__dir__()])

		# Loop through properties, and build a model	
		for property in all_properties.items():
			label = property[1]["name"]
			name = property[1]["name"]
			value = property[1]["value"]
			type = property[1]["type"]
			memo = property[1]["memo"]
			readonly = property[1]["readonly"]
			keyframe = property[1]["keyframe"]
			
			# Hide filtered out properties
			if filter and filter.lower() not in name.lower():
				continue
			
			row = []
			
			# Append Property Name
			col = QStandardItem("Property")
			#col.setData(name, Qt.DisplayRole)
			col.setText(label)
			if keyframe:
				col.setBackground(QColor(42, 130, 218)) # Only highlight background for keyframe'd values
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)
			
			# Append Value
			col = QStandardItem("Value")
			col.setText(str(value))
			if keyframe:
				col.setBackground(QColor(42, 130, 218)) # Only highlight background for keyframe'd values
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
			row.append(col)

			# Append ROW to MODEL (if does not already exist in model)
			self.model.appendRow(row)


	def __init__(self, *args):
		
		# Keep track of the selected items (clips, transitions, etc...)
		self.selected = []

		# Create standard model 
		self.model = ClipStandardItemModel()
		self.model.setColumnCount(2)
		
		#Add self as listener to project data updates (used to update the timeline)
		get_app().updates.add_listener(self)

		# Connect data changed signal
		self.model.itemChanged.connect(self.value_updated)
		