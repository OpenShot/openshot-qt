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
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView
from classes import language, info, ui_util
from classes.logger import log
from images import openshot_rc
import xml.etree.ElementTree as ElementTree

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = ('windows','ui','main.ui')
	
	def __init__(self, app):
		#save reference to application
		self.app = app
		
		#Create main window base class
		QMainWindow.__init__(self)
		
		if QIcon.themeName() == '':
			QIcon.setThemeName("Compass")
		
		#Load ui from configured path
		uic.loadUi(os.path.join(*self.ui_path), self)

		#Get xml tree for ui
		self.uiTree = ElementTree.parse(os.path.join(*self.ui_path))
		
		#Init translation system
		language.init_language(app)
		
		#Init ui
		ui_util.init_ui(self)

		#setup timeline
		self.timeline = TimelineWebView(self)
		
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)

