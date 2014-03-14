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
from PyQt5.QtWidgets import QTreeView, QApplication, QMessageBox, QAbstractItemView, QMenu, QLabel
from windows.models.blender_model import BlenderModel
import xml.dom.minidom as xml
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
		
		# Clear existing settings
		self.win.clear_effect_controls()

		# Get animation details
		animation = self.get_animation_details()
		
		# Loop through params
		for param in animation["params"]:
			log.info(param["title"])
			
			# Is Hidden Param?
			if param["name"] == "start_frame" or param["name"] == "end_frame":
				# add value to dictionary
				self.params[param["name"]] = int(param["default"])
				
				# skip to next param without rendering the controls
				continue
			
			# Create Label
			label = QLabel()
			label.setText(param["title"])
			label.setToolTip(param["title"])
			self.win.settingsContainer.layout().addWidget(label)
			
		
		
	def get_animation_details(self):
		""" Build a dictionary of all animation settings and properties from XML """
		
		if not self.selected:
			return {}
		
		# Get all selected rows items
		ItemRow = self.blender_model.model.itemFromIndex(self.selected).row()
		animation_title = self.blender_model.model.item(ItemRow, 1).text()
		xml_path = self.blender_model.model.item(ItemRow, 2).text()
		
		# load xml effect file
		xmldoc = xml.parse(xml_path)
		
		# Get list of params
		animation = { "title" : animation_title, "path" : xml_path, "params" : [] }
		xml_params = xmldoc.getElementsByTagName("param")
		
		# Loop through params
		for param in xml_params:
			param_item = {}
			
			# Get details of param
			if param.attributes["title"]:
				param_item["title"] = param.attributes["title"].value
			
			if param.attributes["description"]:
				param_item["description"] = param.attributes["description"].value

			if param.attributes["name"]:
				param_item["name"] = param.attributes["name"].value

			if param.attributes["type"]:
				param_item["type"] = param.attributes["type"].value

			if param.getElementsByTagName("min"):
				param_item["min"] = param.getElementsByTagName("min")[0].childNodes[0].data

			if param.getElementsByTagName("max"):
				param_item["max"] = param.getElementsByTagName("max")[0].childNodes[0].data

			if param.getElementsByTagName("step"):
				param_item["step"] = param.getElementsByTagName("step")[0].childNodes[0].data

			if param.getElementsByTagName("digits"):
				param_item["digits"] = param.getElementsByTagName("digits")[0].childNodes[0].data

			if param.getElementsByTagName("default"):
				if param.getElementsByTagName("default")[0].childNodes:
					param_item["default"] = param.getElementsByTagName("default")[0].childNodes[0].data
				else:
					param_item["default"] = ""
				
			param_item["values"] = {}
			values = param.getElementsByTagName("value")
			for value in values:
				# Get list of values
				name = ""
				num = ""
				
				if value.attributes["name"]:
					name = value.attributes["name"].value
					
				if value.attributes["num"]:
					num = value.attributes["num"].value
					
				# add to parameter
				param_item["values"][name] = num
				
			# Append param object to list
			animation["params"].append(param_item)
			
		# Return animation dictionary
		return animation
		
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
		self.win = args[0]
		
		# Get Model data
		self.blender_model = BlenderModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.selected = None
		self.deselected = None
		
		# Init dictionary which holds the values to the template parameters
		self.params = {}

		# Setup header columns
		self.setModel(self.blender_model.model)
		self.setIconSize(QSize(131, 108))
		self.setIndentation(0)
		self.setSelectionBehavior(QTreeView.SelectRows)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		
		# Refresh view
		self.refresh_view()

