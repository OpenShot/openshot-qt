""" 
 @file
 @brief This file contains the project file tree, used by the main window
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
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeWidget, QApplication, QMessageBox, QTreeWidgetItem

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
			data.setText(self.dragItem.text(2) + self.dragItem.text(0))
			#Start drag operation
			drag = QDrag(self)
			drag.setMimeData(data)
			drag.setPixmap(QIcon.fromTheme('document-new').pixmap(QSize(self.drag_item_size,self.drag_item_size)))
			drag.setHotSpot(QPoint(self.drag_item_size/2,self.drag_item_size/2))
			drag.exec_()
	
	def dragEnterEvent(self, event):
		#If dragging urls onto widget, accept
		if event.mimeData().hasUrls():
			event.setDropAction(Qt.CopyAction)
			event.accept()

	#Without defining this method, the 'copy' action doesn't show with cursor
	def dragMoveEvent(self, event):
		pass
	
	def get_filetype(self, file):
		path = file["path"]
		
		if path.endswith((".mp4", ".avi", ".mov")):
			return "video"
		if path.endswith((".mp3", ".wav", ".ogg")):
			return "audio"
		if path.endswith((".jpg", ".jpeg", ".png", ".bmp")):
			return "image"
			
		#Otherwise, unknown
		return "unknown"
			
	def update_model(self):
		log.info("updating files model.")
		files = get_app().project.get(["files"])
		
		#Get window to check filters
		win = get_app().window
		
		self.clear() #Clear items in tree
		#add item for each file
		for file in files:
			path, filename = os.path.split(file["path"])
			
			if not win.actionFilesShowAll.isChecked():
				if win.actionFilesShowVideo.isChecked():
					if not file["type"] == "video":
						continue #to next file, didn't match filter
				elif win.actionFilesShowAudio.isChecked():
					if not file["type"] == "audio":
						continue #to next file, didn't match filter
				elif win.actionFilesShowImage.isChecked():
					if not file["type"] == "image":
						continue #to next file, didn't match filter
						
			if win.filesFilter.text() != "":
				if not win.filesFilter.text() in filename:
					continue
			
			item = QTreeWidgetItem(self)
			item.setIcon(0, QIcon("/home/jonathan/apps/openshot/openshot/images/AudioThumbnail.png"));
			item.setText(1, filename)
			item.setText(2, file["type"])
			item.setText(3, path)
			item.setText(4, file["id"])
			#item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
			self.addTopLevelItem(item)
		
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
			msg.setText(app._tr("Error generating file id."))
			msg.exec_()
			return False
			
		if found:
			msg = QMessageBox()
			msg.setText(app._tr("File already added to project."))
			msg.exec_()
			return False

		#Create file info
		file = {"id": new_id, "path": filepath, "tags": [], "chunk_completion": 0.0, "chunk_path": "", "info": {}}
		file['type'] = self.get_filetype(file)
		
		#Add file to files list via update manager
		app.updates.insert(["files", ""], file)
		return True
	
	#Handle a drag and drop being dropped on widget
	def dropEvent(self, event):
		#log.info('Dropping file(s) on files tree.')
		for uri in event.mimeData().urls():
			#log.info('Uri: ' + uri.toString())
			file_url = urlparse(uri.toString())
			if file_url.scheme == "file":
				filepath = file_url.path
				if filepath[0] == "/" and ":" in filepath:
					filepath = filepath[1:]
				#log.info('Path: %s', filepath)
				#log.info("Exists: %s, IsFile: %s", os.path.exists(filepath), os.path.isfile(filepath))
				if os.path.exists(filepath) and os.path.isfile(filepath):
					log.info('Adding file: %s', filepath)
					if self.add_file(filepath):
						event.accept()
		
	def mousePressEvent(self, event):
		#Save position of mouse press to check for drag
		self.startDragPos = event.pos()
		#Save item clicked on to use if drag starts
		self.dragItem = self.itemAt(event.pos())
			
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
		#self.setSelectionBehavior(QTreeWidget.SelectRows)

		#Example manipulation of tree widget
		"""items = []
		item = QTreeWidgetItem(self)
		item.setText(0, "a name.avi")
		item.setText(1, "Video")
		item.setText(2, "a/b/c/d_e_v_/")
		item.setText(3, app.project.generate_id())
		items.append(item)
		item = QTreeWidgetItem(self)
		item.setText(0, "askjdf.avi")
		item.setText(1, "Video")
		item.setText(2, "a/b/c/d_e_v_/")
		item.setText(3, app.project.generate_id())
		items.append(item)
		item = QTreeWidgetItem(self)
		item.setText(0, "daft_punk.mp3")
		item.setText(1, "Audio")
		item.setText(2, "a/b/c/d_e_v_/")
		item.setText(3, app.project.generate_id())
		items.append(item)
		self.insertTopLevelItems(0, items)"""
		
		#Update model based on loaded project
		self.update_model()

		#setup filter events
		app.window.filesFilter.textChanged.connect(self.filter_changed)
		app.window.actionFilesClear.triggered.connect(self.clear_filter)
		

	
	