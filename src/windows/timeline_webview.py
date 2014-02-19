""" 
 @file
 @brief This file loads the interactive HTML timeline
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
from PyQt5.QtCore import QFileInfo, pyqtSlot, QUrl, Qt, QCoreApplication
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QAbstractSlider, QMenu
from PyQt5.QtWebKitWidgets import QWebView
from classes.logger import log
from classes.app import get_app
from classes import info, updates
import uuid

try:
    import json
except ImportError:
    import simplejson as json
    
JS_SCOPE_SELECTOR = "$('body').scope()"

class TimelineWebView(QWebView, updates.UpdateInterface):
	""" A WebView QWidget used to load the Timeline """
	
	# Path to html file
	html_path = os.path.join(info.PATH, 'timeline','index.html')

	def eval_js(self, code):
		self.page().mainFrame().evaluateJavaScript(code)
	
	# This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
	def changed(self, action):
		
		# Send a JSON version of the UpdateAction to the timeline webview method: ApplyJsonDiff()
		code = JS_SCOPE_SELECTOR + ".ApplyJsonDiff([" + action.json() + "]);"
		self.eval_js(code)


	#Prevent default context menu, and ignore, so that javascript can intercept
	def contextMenuEvent(self, event):
		event.ignore()
		
	#Javascript callable function to show clip or transition content menus, passing in type to show
	@pyqtSlot()
	def show_context_menu(self, type):
		menu = QMenu(self)
		menu.addAction(self.window.actionNew)
		if type == "clip":
			menu.addAction(self.window.actionRemoveClip)
		elif type == "transition":
			menu.addAction(self.window.actionRemoveTransition)
		menu.exec_(QCursor.pos())
	
	#Handle changes to zoom level, update js
	def update_zoom(self, newValue):
		_ = get_app()._tr
		self.window.zoomScaleLabel.setText(_("{} seconds").format(newValue))
		#Get access to timeline scope and set scale to zoom slider value (passed in)
		cmd = JS_SCOPE_SELECTOR + ".setScale(" + str(newValue) + ");"
		self.page().mainFrame().evaluateJavaScript(cmd)
	
	#Capture wheel event to alter zoom slider control
	def wheelEvent(self, event):
		if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
			#For each 120 (standard scroll unit) adjust the zoom slider
			tick_scale = 120
			steps = int(event.angleDelta().y() / tick_scale)
			self.window.sliderZoom.setValue(self.window.sliderZoom.value() - self.window.sliderZoom.pageStep() * steps)
		#Otherwise pass on to implement default functionality (scroll in QWebView)
		else:
			#self.show_context_menu('clip') #Test of spontaneous context menu creation
			super(type(self), self).wheelEvent(event)
	
	def setup_js_data(self):
		#Export self as a javascript object in webview
		self.page().mainFrame().addToJavaScriptWindowObject('timeline', self)
		self.page().mainFrame().addToJavaScriptWindowObject('mainWindow', self.window)
		
	def dragEnterEvent(self, event):
		#If a plain text drag accept
		if not event.mimeData().hasUrls() and event.mimeData().hasText():
			file_id = event.mimeData().text()
			event.accept()
			pos = event.posF()
			
			# Find file object in project data
			app = get_app()
			proj = app.project
			files = proj.get(["files"])
			
			# Loop until correct file is found
			file = None
			for f in files:
				if f["id"] == file_id:
					file = f
					break
				
			# Bail if no file found
			if not file:
				event.ignore()
				return
			
			if (file["media_type"] == "video" or file["media_type"] == "image"):
				# Determine thumb path
				thumb_path = os.path.join(proj.current_filepath, "%s.png" % file["id"])
			else:
				# Audio file
				thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")
				
			# Get file name
			path, filename = os.path.split(file["path"])

			#build data to pass to timeline js
			new_clip = {
	                 "id" : file["id"],
	                 "title" : filename,
	                 "layer" : 0, 
	                 "image" : thumb_path,
	                 "locked" : False,
	                 "duration" : file["duration"],
	                 "start" : 0,
	                 "end" : file["duration"],
	                 "position" : 0.0,
	                 "effects" : [],
	                 "images" : { "start": 0, "end": file["duration"]},
	                 "show_audio" : False,
	               }
			
			# Add clip to timeline
			code = JS_SCOPE_SELECTOR + ".AddClip(" + str(pos.x()) + ", " + str(pos.y()) + ", " + json.dumps(new_clip) + ");"
			self.eval_js(code)
			
			log.info('Dragging {} in timeline.'.format(event.mimeData().text()))
			event.accept()


	#Without defining this method, the 'copy' action doesn't show with cursor
	def dragMoveEvent(self, event):
		
		# Get cursor position
		pos = event.posF()
		
		# Move clip on timeline
		code = JS_SCOPE_SELECTOR + ".MoveClip(" + str(pos.x()) + ", " + str(pos.y()) + ");"
		self.eval_js(code)
		
		#log.info('Moving {} in timeline.'.format(event.mimeData().text()))
		event.accept()
	
	def dropEvent(self, event):
		log.info('Dropping {} in timeline.'.format(event.mimeData().text()))
		event.accept()
	
	def __init__(self, window):
		QWebView.__init__(self)
		self.window = window
		self.setAcceptDrops(True)

		#Add self as listener to project data updates (used to update the timeline)
		get_app().updates.add_listener(self)
		
		#set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
		self.setUrl(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))
		
		#Connect signal of javascript initialization to our javascript reference init function
		self.page().mainFrame().javaScriptWindowObjectCleared.connect(self.setup_js_data)
		
		#Connect zoom functionality
		window.sliderZoom.valueChanged.connect(self.update_zoom)

		
