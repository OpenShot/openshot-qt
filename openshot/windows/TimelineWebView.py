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
from PyQt5.QtCore import QFileInfo, pyqtSlot, QUrl, Qt, QCoreApplication
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QAbstractSlider, QMenu
from PyQt5.QtWebKitWidgets import QWebView
from classes.logger import log
from classes import info

JS_SCOPE_SELECTOR = "$('body').scope()"

class TimelineWebView(QWebView):
	html_path = os.path.join(info.PATH, 'windows','html','timeline','index.html')

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
		#Get access to timeline scope and set scale to zoom slider value (passed in)
		cmd = JS_SCOPE_SELECTOR + ".setScale(" + str(newValue) + ");"
		self.page().mainFrame().evaluateJavaScript(cmd)
	
	#Capture wheel event to alter zoom slider control
	def wheelEvent(self, event):
		if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
			#For each 120 (standard scroll unit) adjust the zoom slider
			tick_scale = 120
			y = event.angleDelta().y()
			up = y > 0
			while (y != 0):
				if up and y > tick_scale:
					y -= tick_scale
				elif not up and y < -tick_scale:
					y += tick_scale
				else:
					y = 0
				if up:
					self.window.sliderZoom.triggerAction(QAbstractSlider.SliderPageStepSub)
				else:
					self.window.sliderZoom.triggerAction(QAbstractSlider.SliderPageStepAdd)		
		#Otherwise pass on to implement default functionality (scroll in QWebView)
		else:
			self.show_context_menu('clip') #Test of spontaneous context menu creation
			#super(type(self), self).wheelEvent(event)
	
	def setup_js_data(self):
		#Export self as a javascript object in webview
		self.page().mainFrame().addToJavaScriptWindowObject('timeline', self)
		self.page().mainFrame().addToJavaScriptWindowObject('mainWindow', self.window)
	
	def __init__(self, window):
		QWebView.__init__(self)
		self.window = window
		#self.installEventFilter(window)
		
		#set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
		self.setUrl(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))
		
		#Connect signal of javascript initialization to our javascript reference init function
		self.page().mainFrame().javaScriptWindowObjectCleared.connect(self.setup_js_data)
		
		#Connect zoom functionality
		window.sliderZoom.valueChanged.connect(self.update_zoom)

		
