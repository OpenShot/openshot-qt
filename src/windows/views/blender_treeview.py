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
from classes.query import File
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from windows.models.blender_model import BlenderModel
import xml.dom.minidom as xml
import functools
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json

class BlenderTreeView(QTreeView):
	""" A TreeView QWidget used on the animated title window """ 

	def currentChanged(self, selected, deselected):
		# Get selected item
		self.selected = selected
		self.deselected = deselected
		
		# Get translation object
		_ = self.app._tr
		
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
			widget = None
			label = QLabel()
			label.setText(_(param["title"]))
			label.setToolTip(_(param["title"]))
			#self.win.settingsContainer.layout().addWidget(label)

			if param["type"] == "spinner":
				# add value to dictionary
				self.params[param["name"]] = float(param["default"])
				
				# create spinner
				widget = QDoubleSpinBox()
				widget.setMinimum(float(param["min"]))
				widget.setMaximum(float(param["max"]))
				widget.setValue(float(param["default"]))
				widget.setSingleStep(0.01)
				widget.setToolTip(param["title"])
				widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))
				
			elif param["type"] == "text":
				# add value to dictionary
				self.params[param["name"]] = _(param["default"])
				
				# create spinner
				widget = QLineEdit()
				widget.setText(_(param["default"]))
				widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

			elif param["type"] == "multiline":
				# add value to dictionary
				self.params[param["name"]] = _(param["default"])
				
				# create spinner
				widget = QTextEdit()
				widget.setText(_(param["default"]))
				widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))
				
			elif param["type"] == "dropdown":
				# add value to dictionary
				self.params[param["name"]] = param["default"]
				
				# create spinner
				widget = QComboBox()
				widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

				# Add values to dropdown
				if "project_files" in param["name"]:
					# override files dropdown
					param["values"] = {}
					for file in File.filter():
						if file.data["media_type"] in ("image", "video"):
							(dirName, fileName) = os.path.split(file.data["path"])
							(fileBaseName, fileExtension)=os.path.splitext(fileName)
							
							if fileExtension.lower() not in (".svg"):
								param["values"][fileName] = "|".join((file.data["path"], str(file.data["height"]), str(file.data["width"]), file.data["media_type"], str(file.data["fps"]["num"]/file.data["fps"]["den"])))

				# Add normal values
				box_index = 0
				for k,v in sorted(param["values"].items()):
					# add dropdown item
					widget.addItem(_(k), v)
					
					# select dropdown (if default)
					if v == param["default"]:
						widget.setCurrentIndex(box_index)
					box_index = box_index + 1
					
				if not param["values"]:
					widget.addItem(_("No Files Found"), "")
					widget.setEnabled(False)
					
			elif param["type"] == "color":
				# add value to dictionary
				self.params[param["name"]] = param["default"]
				
				widget = QPushButton()
				widget.setText("")
				widget.setStyleSheet("background-color: %s" % param["default"])
				widget.clicked.connect(functools.partial(self.color_button_clicked, widget, param))
				
			# Add Label and Widget to the form
			if (widget and label):
				self.win.settingsContainer.layout().addRow(label, widget)
			elif (label):
				self.win.settingsContainer.layout().addRow(label)
		
	def spinner_value_changed(self, param, value ):
		self.params[param["name"]] = value
		log.info(value)
		
	def text_value_changed(self, widget, param, value=None ):
		try:
			# Attempt to load value from QTextEdit (i.e. multi-line)
			if not value:
				value = widget.toPlainText()
		except:
			pass
		self.params[param["name"]] = value
		log.info(value)
		
	def dropdown_index_changed(self, widget, param, index ):
		value = widget.itemData(index)
		self.params[param["name"]] = value
		log.info(value)
		
	def color_button_clicked(self, widget, param, index ):
		# Show color dialog
		currentColor = QColor(self.params[param["name"]])
		newColor = QColorDialog.getColor(currentColor)
		widget.setStyleSheet("background-color: %s" % newColor.name())
		self.params[param["name"]] = newColor.name()
		log.info(newColor.name())
		
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
		self.app = get_app()
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

