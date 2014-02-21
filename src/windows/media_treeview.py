""" 
 @file
 @brief This file contains the project file tree, used by the main window
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>
 
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

try:
    import json
except ImportError:
    import simplejson as json

class MediaTreeView(QTreeWidget, updates.UpdateInterface):
	""" A TreeView QWidget used on the main window """ 
	drag_item_size = 32
	
	# This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
	def changed(self, action):

		# Something was changed in the 'files' list
		if len(action.key) >= 1 and action.key[0].lower() == "files":
			# Refresh project files model
			self.update_model()

	def mouseMoveEvent(self, event):
		#If mouse drag detected, set the proper data and icon and start dragging
		if event.buttons() & Qt.LeftButton == Qt.LeftButton and (event.pos() - self.startDragPos).manhattanLength() >= QApplication.startDragDistance():
			#Setup data based on item being dragged
			data = QMimeData()
			data.setText(self.dragItem.text(4)) # Add file ID to mimedata
			#Start drag operation
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
	
	def dragEnterEvent(self, event):
		#If dragging urls onto widget, accept
		if event.mimeData().hasUrls():
			event.setDropAction(Qt.CopyAction)
			event.accept()

	#Without defining this method, the 'copy' action doesn't show with cursor
	def dragMoveEvent(self, event):
		pass
		
	def mousePressEvent(self, event):
		# Select the current item
		self.setCurrentItem(self.itemAt(event.pos()))
		
		#Save position of mouse press to check for drag
		self.startDragPos = event.pos()
		#Save item clicked on to use if drag starts
		self.dragItem = self.itemAt(event.pos())
	
	def is_image(self, file):
		path = file["path"].lower()
		
		if path.endswith((".jpg", ".jpeg", ".png", ".bmp", ".svg")):
			return True
		else:
			return False
			
	def update_model(self):
		log.info("updating files model.")
		app = get_app()
		proj = app.project
		files = proj.get(["files"])

		#Get window to check filters
		win = app.window
		
		self.clear() #Clear items in tree
		#add item for each file
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
				if not win.filesFilter.text() in filename:
					continue

			# Generate thumbnail for file (if needed)
			if (file["media_type"] == "video" or file["media_type"] == "image"):
				# Determine thumb path
				thumb_path = os.path.join(proj.current_filepath, "%s.png" % file["id"])
				
				# Check if thumb exists
				if not os.path.exists(thumb_path):

					try:
						# Reload this reader
						clip = openshot.Clip(file["path"])
						reader = clip.Reader()

						# Open reader
						reader.Open()
						
						# Determine scale of thumbnail
						scale = 86.0 / file["width"]
						
						# Save thumbnail
						reader.GetFrame(0).Save(thumb_path, scale)
						reader.Close()

					except:
						# Handle exception
						msg = QMessageBox()
						msg.setText(app._tr("%s is not a valid video, audio, or image file." % filename))
						msg.exec_()
						return False

			else:
				# Audio file
				thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")
			
			item = QTreeWidgetItem(self)
			item.setIcon(0, QIcon(thumb_path));
			item.setText(1, filename)
			item.setText(2, file["media_type"])
			item.setText(3, path)
			item.setText(4, file["id"])
			item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
			self.addTopLevelItem(item)
			
			# Process events in QT (to keep the interface responsive)
			app.processEvents()
			
		# Resize columns to match contents
		for column in range(4):
			self.resizeColumnToContents(column)
		
	def add_file(self, filepath):
		path, filename = os.path.split(filepath)
		
		#Add file into project
		app = get_app()
		proj = app.project
		files = proj.get(["files"]) #get files list
		found = False
		new_id = proj.generate_id()
		
		#Check for new_id and filepath in current file list to prevent duplicates
		index = 0
		sanity_check, sanity_limit = 0, 10
		while index < len(files):
			if sanity_check > sanity_limit: #Stop checking if we can't get a unique id in 10 tries
				break;
			f = files[index]
			#Stop checking if we find this filepath already in the list, don't allow duplicate.
			if f["path"] == filepath:
				found = True
				break
			#Generate new id and start loop over again if duplicate id is found
			if f["id"] == new_id: #If this ID is found, generate a new one
				new_id = proj.generate_id()
				index = 0
				sanity_check += 1
				continue
			#Move to next item
			index += 1
		
		if sanity_check > sanity_limit:
			msg = QMessageBox()
			msg.setText(app._tr("Error generating unique file ID for %s." % filename))
			msg.exec_()
			return False
			
		if found:
			msg = QMessageBox()
			msg.setText(app._tr("%s already added to project." % filename))
			msg.exec_()
			return False
		
		# Inspect the file with libopenshot
		clip = None

		# Load filepath in libopenshot clip object (which will try multiple readers to open it)
		clip = openshot.Clip(filepath)

		# Get the JSON for the clip's internal reader
		try:
			reader = clip.Reader()
			file_json = json.loads(reader.Json())
			
			# Add unique ID to the JSON
			file_json["id"] = new_id

			# Determine media type
			if file_json["has_video"] and not self.is_image(file_json):
				file_json["media_type"] = "video"
			elif file_json["has_video"] and self.is_image(file_json):
				file_json["media_type"] = "image"
			elif file_json["has_audio"] and not file_json["has_video"]:
				file_json["media_type"] = "audio"	
			
			# Add file to files list via update manager
			app.updates.insert(["files", ""], file_json)
			return True
		
		except:
			# Handle exception
			msg = QMessageBox()
			msg.setText(app._tr("%s is not a valid video, audio, or image file." % filename))
			msg.exec_()
			return False
		
	
	# Handle a drag and drop being dropped on widget
	def dropEvent(self, event):
		#log.info('Dropping file(s) on files tree.')
		for uri in event.mimeData().urls():
			file_url = urlparse(uri.toString())
			if file_url.scheme == "file":
				filepath = file_url.path
				if filepath[0] == "/" and ":" in filepath:
					filepath = filepath[1:]
				if os.path.exists(filepath) and os.path.isfile(filepath):
					log.info('Adding file: {}'.format(filepath))
					if self.add_file(filepath):
						event.accept()
		
	def clear_filter(self):
		get_app().window.filesFilter.setText("")
		
	def filter_changed(self):
		self.update_model()
		win = get_app().window
		if win.filesFilter.text() == "":
			win.actionFilesClear.setEnabled(False)
		else:
			win.actionFilesClear.setEnabled(True)
			
	def __init__(self, *args):
		QTreeWidget.__init__(self, *args)
		#Keep track of mouse press start position to determine when to start drag
		self.startDragPos = None
		self.setAcceptDrops(True)
		
		#Add self as listener to project data updates (undo/redo, as well as normal actions handled within this class all update the tree model)
		app = get_app()
		app.updates.add_listener(self)

		#Setup header columns
		self.setColumnCount(5)
		self.setHeaderLabels(["Thumb","Name","Type","Path","ID"])
		self.setIconSize(QSize(75, 62))
		self.setIndentation(0)
		self.setSelectionBehavior(QTreeWidget.SelectRows)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)

		#Update model based on loaded project
		self.update_model()

		#setup filter events
		app.window.filesFilter.textChanged.connect(self.filter_changed)
		app.window.actionFilesClear.triggered.connect(self.clear_filter)
		

	
	
