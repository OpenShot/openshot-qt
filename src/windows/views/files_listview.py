""" 
 @file
 @brief This file contains the project file listview, used by the main window
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
from classes import info
from classes.logger import log
from classes.query import File
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QListView, QApplication, QMessageBox, QAbstractItemView, QMenu
from windows.models.files_model import FilesModel
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json

class FilesListView(QListView):
	""" A ListView QWidget used on the main window """ 
	drag_item_size = 32
	
	def currentChanged(self, selected, deselected):
		# get selected item
		self.selected = selected
		self.deselected = deselected
		
	def contextMenuEvent(self, event):
		menu = QMenu(self)
		menu.addAction(self.win.actionDetailsView)
		menu.addAction(self.win.actionThumbnailView)
		menu.exec_(QCursor.pos())

	def mouseMoveEvent(self, event):
		#If mouse drag detected, set the proper data and icon and start dragging
		if self.selected and event.buttons() & Qt.LeftButton == Qt.LeftButton and (event.pos() - self.startDragPos).manhattanLength() >= QApplication.startDragDistance():
			# Get selected item
			dragItemRow = self.files_model.model.itemFromIndex(self.selected).row()
			
			# Get all selected rows items
			dragItem = []
			for col in range(5):
				dragItem.append(self.files_model.model.item(dragItemRow, col))
			
			# Setup data based on item being dragged
			data = QMimeData()
			data.setText(dragItem[4].text()) # Add file ID to mimedata
			# Start drag operation
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
		# If dragging urls onto widget, accept
		if event.mimeData().hasUrls():
			event.setDropAction(Qt.CopyAction)
			event.accept()

	# Without defining this method, the 'copy' action doesn't show with cursor
	def dragMoveEvent(self, event):
		pass
		
	def mousePressEvent(self, event):
		# Save position of mouse press to check for drag
		self.startDragPos = event.pos()
		
		# Ignore event, propagate to parent 
		event.ignore()
		super().mousePressEvent(event)
		
	def is_image(self, file):
		path = file["path"].lower()
		
		if path.endswith((".jpg", ".jpeg", ".png", ".bmp", ".svg", ".thm", ".gif", ".bmp", ".pgm", ".tif", ".tiff")):
			return True
		else:
			return False

	def add_file(self, filepath):
		path, filename = os.path.split(filepath)
		
		# Add file into project
		app = get_app()

		# Check for this path in our existing project data
		file = File.get(path=filepath)
		
		# If this file is already found, exit
		if file:
			return

		# Load filepath in libopenshot clip object (which will try multiple readers to open it)
		clip = openshot.Clip(filepath)

		# Get the JSON for the clip's internal reader
		try:
			reader = clip.Reader()
			file_data = json.loads(reader.Json())

			# Determine media type
			if file_data["has_video"] and not self.is_image(file_data):
				file_data["media_type"] = "video"
			elif file_data["has_video"] and self.is_image(file_data):
				file_data["media_type"] = "image"
			elif file_data["has_audio"] and not file_data["has_video"]:
				file_data["media_type"] = "audio"	
			
			# Save new file to the project data
			file = File()
			file.data = file_data
			file.save()
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
		self.files_model.update_model()
		if self.win.filesFilter.text() == "":
			self.win.actionFilesClear.setEnabled(False)
		else:
			self.win.actionFilesClear.setEnabled(True)
			
	def __init__(self, *args):
		# Invoke parent init
		QListView.__init__(self, *args)
		
		# Get a reference to the window object
		self.win = get_app().window
		
		# Get Model data
		self.files_model = FilesModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.startDragPos = None
		self.setAcceptDrops(True)
		self.selected = None
		self.deselected = None

		# Setup header columns
		self.setModel(self.files_model.model)
		self.setIconSize(QSize(131, 108))
		self.setViewMode(QListView.IconMode)
		self.setResizeMode(QListView.Adjust)
		
		# setup filter events
		app = get_app()
		app.window.filesFilter.textChanged.connect(self.filter_changed)
		app.window.actionFilesClear.triggered.connect(self.clear_filter)
		

	
	
