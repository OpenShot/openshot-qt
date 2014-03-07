""" 
 @file
 @brief This file contains the project file model, used by the project tree
 @author Noah Figg <eggmunkee@hotmail.com>
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

class FilesModel(updates.UpdateInterface):
	
	# This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
	def changed(self, action):

		# Something was changed in the 'files' list
		if len(action.key) >= 1 and action.key[0].lower() == "files":
			# Refresh project files model
			if action.type == "insert":
				# Don't clear the existing items if only inserting new things
				self.update_model(clear=False)
			else:
				# Clear existing items
				self.update_model(clear=False)
			
	def update_model(self, clear=True):
		log.info("updating files model.")
		app = get_app()
		proj = app.project
		files = proj.get(["files"])

		# Get window to check filters
		win = app.window
		
		# Clear all items
		if clear:
			self.model_ids = {}
			self.model.clear()
		
		# Add Headers
		self.model.setHorizontalHeaderLabels(["Thumb", "Name", "Type" ])
		
		# add item for each file
		for file in files:
			path, filename = os.path.split(file["path"])
			
			if not win.actionFilesShowAll.isChecked():
				if win.actionFilesShowVideo.isChecked():
					if not file["media_type"] == "video":
						continue #to next file, didn't match filter
				elif win.actionFilesShowAudio.isChecked():
					if not file["media_type"] == "audio":
						continue #to next file, didn't match filter
				elif win.actionFilesShowImage.isChecked():
					if not file["media_type"] == "image":
						continue #to next file, didn't match filter
						
			if win.filesFilter.text() != "":
				if not win.filesFilter.text().lower() in filename.lower():
					continue

			# Generate thumbnail for file (if needed)
			if (file["media_type"] == "video" or file["media_type"] == "image"):
				# Determine thumb path
				thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file["id"])
				
				# Check if thumb exists
				if not os.path.exists(thumb_path):

					try:
						# Convert path to the correct relative path (based on this folder)
						absolute_path_of_file = file["path"]
						if not os.path.isabs(absolute_path_of_file):
							absolute_path_of_file = os.path.abspath(os.path.join(info.PATH, file["path"]))
						relative_path = os.path.relpath(absolute_path_of_file, info.CWD)
						
						# Reload this reader
						clip = openshot.Clip(relative_path)
						reader = clip.Reader()

						# Open reader
						reader.Open()
						
						# Determine scale of thumbnail
						scale = 95.0 / file["width"]
						
						# Save thumbnail
						reader.GetFrame(0).Save(thumb_path, scale)
						reader.Close()
						
					except:
						# Handle exception
						msg = QMessageBox()
						msg.setText(app._tr("%s is not a valid video, audio, or image file." % filename))
						msg.exec_()
						continue


			else:
				# Audio file
				thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")
			

			row = []
			
			# Append thumbnail
			col = QStandardItem()
			col.setIcon(QIcon(thumb_path))
			#col.setData("Thumb", Qt.DisplayRole)
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)
			
			# Append Filename
			col = QStandardItem("Name")
			col.setData(filename, Qt.DisplayRole)
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)
			
			# Append Media Type
			col = QStandardItem("Type")
			col.setData(file["media_type"], Qt.DisplayRole)
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)
			
			# Append Path
			col = QStandardItem("Path")
			col.setData(path, Qt.DisplayRole)
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)
			
			# Append ID
			col = QStandardItem("ID")
			col.setData(file["id"], Qt.DisplayRole)
			col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			row.append(col)

			# Append ROW to MODEL (if does not already exist in model)
			if not file["id"] in self.model_ids:
				self.model.appendRow(row)
				self.model_ids[file["id"]] = file["id"]
			
			# Process events in QT (to keep the interface responsive)
			app.processEvents()

	def __init__(self, *args):

		# Add self as listener to project data updates (undo/redo, as well as normal actions handled within this class all update the tree model)
		app = get_app()
		app.updates.add_listener(self)

		# Create standard model 
		self.model = QStandardItemModel()
		self.model.setColumnCount(5)
		self.model_ids = {}

		# Update model based on loaded project
		self.update_model()

		