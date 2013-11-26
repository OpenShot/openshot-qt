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

import sys, os
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView
from classes import language, info, ui_util
from classes.logger import log
from images import openshot_rc
from windows.MediaTreeView import MediaTreeView
import xml.etree.ElementTree as ElementTree

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = os.path.join(info.PATH, 'windows','ui','main.ui')
	
	#def mouseMoveEvent(self, event):
		#print ('mouseMoveEvent', event.buttons() & Qt.LeftButton == Qt.LeftButton, event.buttons() & Qt.RightButton == Qt.RightButton, event.buttons() & Qt.NoButton == Qt.NoButton)
		#if event.button() == Qt.LeftButton:
		#	print ('mouseMoveEvent', event.pos())	
		
	def __init__(self):

		#Create main window base class
		QMainWindow.__init__(self)
		#self.setAcceptDrops(True)
		
		#Init translation system
		language.init_language()
		
		#Load theme if not set by OS
		ui_util.load_theme()
		
		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)

		#Init UI
		ui_util.init_ui(self)

		#setup timeline
		self.timeline = TimelineWebView(self)
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)
		
		#setup tree
		self.gridLayout_2.removeWidget(self.treeView)
		self.treeView.close()
		self.treeView = MediaTreeView(self.tabFiles)
		self.gridLayout_2.addWidget(self.treeView, 1, 0)

