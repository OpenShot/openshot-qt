""" 
 @file
 @brief This file contains the transitions model, used by the main window
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
from PyQt5.QtWidgets import QTreeWidget, QApplication, QMessageBox, QTreeWidgetItem, QAbstractItemView
import openshot # Python module for libopenshot (required video editing module installed separately)

class TransitionsModel():
			
	def update_model(self, clear=True):
		log.info("updating transitions model.")
		app = get_app()
		proj = app.project

		# Get window to check filters
		win = app.window
		
		# Clear all items
		if clear:
			self.model_paths = {}
			self.model.clear()
		
		# Add Headers
		self.model.setHorizontalHeaderLabels(["Thumb", "Name" ])
		
		# get a list of files in the OpenShot /transitions directory
		transitions_dir = os.path.join(info.PATH, "transitions")
		common_dir = os.path.join(transitions_dir, "common")
		extra_dir = os.path.join(transitions_dir, "extra")
		transition_groups = [ { "type" : "common", "dir" : common_dir, "files" : os.listdir(common_dir) },
							  { "type" : "extra", "dir" : extra_dir, "files" : os.listdir(extra_dir) } ]
		
		for group in transition_groups:
			type = group["type"]
			dir = group["dir"]
			files = group["files"]

			for filename in sorted(files):
				path = os.path.join(dir, filename)
				(fileBaseName, fileExtension)=os.path.splitext(filename)
				
				# get name of transition
				trans_name = fileBaseName.replace("_", " ").capitalize()
				
				if not win.actionTransitionsShowAll.isChecked():
					if win.actionTransitionsShowCommon.isChecked():
						if not type == "common":
							continue # to next file, didn't match filter
	
				if win.transitionsFilter.text() != "":
					if not win.transitionsFilter.text().lower() in self.app._tr(trans_name).lower():
						continue
	
				# Generate thumbnail for file (if needed)
				thumb_path = os.path.join(info.CACHE_PATH, "{}.png".format(fileBaseName))
				
				# Check if thumb exists
				if not os.path.exists(thumb_path):

					try:
						# Reload this reader
						clip = openshot.Clip(path)
						reader = clip.Reader()

						# Open reader
						reader.Open()

						# Save thumbnail
						reader.GetFrame(0).Thumbnail(thumb_path, 98, 64, os.path.join(info.IMAGES_PATH, "mask.png"), "", "#000", True)
						reader.Close()

					except:
						# Handle exception
						msg = QMessageBox()
						msg.setText(app._tr("{} is not a valid image file.".format(filename)))
						msg.exec_()
						continue
				
				row = []
				
				# Append thumbnail
				col = QStandardItem()
				col.setIcon(QIcon(thumb_path))
				col.setText(self.app._tr(trans_name))
				col.setToolTip(self.app._tr(trans_name))
				col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
				row.append(col)
				
				# Append Filename
				col = QStandardItem("Name")
				col.setData(self.app._tr(trans_name), Qt.DisplayRole)
				col.setText(self.app._tr(trans_name))
				col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
				row.append(col)
				
				# Append Media Type
				col = QStandardItem("Type")
				col.setData(type, Qt.DisplayRole)
				col.setText(type)
				col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
				row.append(col)
				
				# Append Path
				col = QStandardItem("Path")
				col.setData(path, Qt.DisplayRole)
				col.setText(path)
				col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
				row.append(col)
	
				# Append ROW to MODEL (if does not already exist in model)
				if not path in self.model_paths:
					self.model.appendRow(row)
					self.model_paths[path] = path
				
				# Process events in QT (to keep the interface responsive)
				app.processEvents()

	def __init__(self, *args):

		# Create standard model 
		self.app = get_app()
		self.model = QStandardItemModel()
		self.model.setColumnCount(4)
		self.model_paths = {}

		
