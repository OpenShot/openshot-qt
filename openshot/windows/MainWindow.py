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
from classes import language, info, ui_util, SettingStore, qt_types
from classes.logger import log
from images import openshot_rc
from windows.MediaTreeView import MediaTreeView
import xml.etree.ElementTree as ElementTree

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = os.path.join(info.PATH, 'windows','ui','main.ui')
	
	def closeEvent(self, event):
		self.save_settings()
	
	def save_settings(self):
		settings = SettingStore.get_settings()

		#Save window state and geometry (saves toolbar and dock locations)
		settings.set('window_state', qt_types.bytes_to_str(self.saveState()))
		settings.set('window_geometry', qt_types.bytes_to_str(self.saveGeometry()))

		#Splitter sizes
		sizes = self.splitter_2.sizes()
		settings.set('window_splitter_2_pos', sizes)
		sizes = self.splitter.sizes()
		settings.set('window_splitter_pos', sizes)
		
		#TODO: Call save_settings on any sub-objects necessary
	
	def load_settings(self):
		settings = SettingStore.get_settings()
		
		#Window state and geometry (also toolbar and dock locations)
		if settings.get('window_geometry'): self.restoreGeometry(qt_types.str_to_bytes(settings.get('window_geometry')))
		if settings.get('window_state'): self.restoreState(qt_types.str_to_bytes(settings.get('window_state')))
		
		#Splitter sizes
		if settings.get('window_splitter_pos'): self.splitter.setSizes(settings.get('window_splitter_pos'))
		if settings.get('window_splitter_2_pos'): self.splitter_2.setSizes(settings.get('window_splitter_2_pos'))

		#TODO: Call load_settings on any sub-objects necessary
		
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
		
		#Load user settings for window
		self.load_settings()

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

