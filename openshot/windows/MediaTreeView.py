#!/usr/bin/env python
#	OpenShot Video Editor is a program that creates, modifies, and edits video files.
#   Copyright (C) 2009  Jonathan Thomas, TJ
#
#	This file is part of OpenShot Video Editor (http://launchpad.net/openshot/).
#
#	OpenShot Video Editor is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	OpenShot Video Editor is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with OpenShot Video Editor.  If not, see <http://www.gnu.org/licenses/>.

import os
from urllib.parse import urlparse
from classes.logger import log
from classes.SettingStore import SettingStore
from classes.OpenShotApp import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeView, QApplication, QMessageBox

class MediaTreeView(QTreeView):
	drag_item_size = 32
	
	def mouseMoveEvent(self, event):
		#If mouse drag detected, set the proper data and icon and start dragging
		if event.buttons() & Qt.LeftButton == Qt.LeftButton and (event.pos() - self.startDragPos).manhattanLength() >= QApplication.startDragDistance():
			data = QMimeData()
			data.setText('Test value 1')
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
	
	def update_model(self):
		files = get_app().project.get("files")
		
		#Get model
		mod = self.model()
		mod.setRowCount(0) #Remove all but header
		#add item for each file
		for file in files:
			path, filename = os.path.split(file["path"])
			item = QStandardItem(filename)
			mod.invisibleRootItem().appendRow(item)
			row = mod.rowCount() - 1
			mod.setData( mod.index(row,1), "Unknown")
			mod.setData( mod.index(row,2), path)
			mod.setData( mod.index(row,3), file["id"])
		
	def add_file(self, filepath):
		path, filename = os.path.split(filepath)
		
		#Add file into project
		app = get_app()
		proj = app.project
		files = proj.get("files") #get files list
		found = False
		new_id = proj.generate_id()
		
		for f in files:
			if f["id"] == new_id:
				new_id = proj.generate_id()
			if f["path"] == filepath:
				found = True
				break
			
		if found:
			msg = QMessageBox()
			msg.setText(app._tr("File already added to project."))
			msg.exec_()
			return False

		#Create file info
		file = {"id": new_id, "path": filepath, "tags": [], "chunk_completion": 0.0, "chunk_path": "", "info": {}}
		files.append(file)
		
		#Update files
		app.update_manager.update("files", files)
			
		#Refresh tree model
		self.update_model()
		
	
	#Handle a drag and drop being dropped on widget
	def dropEvent(self, event):
		log.info('Dropping file(s) on files tree.')
		for uri in event.mimeData().urls():
			log.info('Uri: ' + uri.toString())
			file_url = urlparse(uri.toString())
			if file_url.scheme == "file":
				filepath = file_url.path
				if filepath[0] == "/" and ":" in filepath:
					filepath = filepath[1:]
				log.info('Path: %s', filepath)
				log.info("Exists: %s, IsFile: %s", os.path.exists(filepath), os.path.isfile(filepath))
				if os.path.exists(filepath) and os.path.isfile(filepath):
					self.add_file(filepath)
					event.accept()
		
	def mousePressEvent(self, event):
		self.startDragPos = event.pos()
			
	def __init__(self, *args):
		QTreeView.__init__(self, *args)
		
		#Keep track of mouse press start position to determine when to start drag
		self.startDragPos = None
		self.setAcceptDrops(True)
		
		
		#Load data model and add some items to it
		mod = QStandardItemModel(0, 4)
		parent_node = mod.invisibleRootItem()
		mod.setHeaderData(0, Qt.Horizontal, "Name")
		mod.setHeaderData(1, Qt.Horizontal, "Type")
		mod.setHeaderData(2, Qt.Horizontal, "Path")
		mod.setHeaderData(3, Qt.Horizontal, "ID")
		self.setModel(mod)
		self.update_model()
		#for i in range(4):
		#	item = QStandardItem("Clip" + str(i))
		#	parent_node.appendRow(item)
		#	index = mod.index(i,1)
		#	if i % 2 == 0:
		#		mod.setData(index, "Video")
		#	else:
		#		mod.setData(index, "Audio")
	
	
	