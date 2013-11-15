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
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap, QImageReader, QIcon
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView
from classes import language, info
from classes.logger import log
from images import openshot_rc

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = ('windows','ui','main.ui')
	theme_path = ('icons','Compass')
	
	def __init__(self, app):
		#save reference to application
		self.app = app
		
		#Create main window base class
		QMainWindow.__init__(self)
		
		themePath = os.path.join(*self.theme_path)
		themeSearchPaths = QIcon.themeSearchPaths()
		print (themeSearchPaths)
		#if not themePath in themeSearchPaths:
		#themeSearchPaths.append(":/images")
		#QIcon.setThemeSearchPaths(themeSearchPaths)
		print(QDir(':/icons/Compass').entryList())
		QIcon.setThemeName("Compass")
		
		print ('Has theme icon document-open:', QIcon.hasThemeIcon('document-open'))
		print (QIcon.themeName())
		
		#Load ui from configured path
		uic.loadUi(os.path.join(*self.ui_path), self)
		
		#Init translation system
		language.init_language(app)
		
		#Translate ui to current language
		self.translate_self()
		
		#Set icons on actions
		if False:
			self.actionNew.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
			self.actionOpen.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
			self.actionRecent.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
			self.actionSave.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
			self.actionSaveAs.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
			self.actionUndo.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
			self.actionRedo.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
			self.actionImportFiles.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
			self.actionImportImageSequence.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
			self.actionImportTransition.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))

		#Test loading icon
		#img = QPixmap(":/Compass/actions/navtoolbar/go-jump.svg").scaledToHeight(200)
		#.lblImage.setPixmap(img)
			
		#setup timeline
		self.timeline = TimelineWebView(self)
		
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)

	#Translate all text portions of the given element
	def translate_element(self, elem):
		_translate = self.app.translate
		
		#Handle generic translatable properties
		if hasattr(elem, 'setText') and elem.text() != "":
			elem.setText( _translate("", elem.text()) )
		if hasattr(elem, 'setTooltip') and elem.tooltip() != "":
			elem.setTooltip( _translate("", elem.tooltip()) )
		if hasattr(elem, 'setWindowTitle') and elem.windowTitle() != "":
			elem.setWindowTitle( _translate("", elem.windowTitle()) )
		if hasattr(elem, 'setTitle') and elem.title() != "":
			elem.setTitle( _translate("", elem.title()) )
		#Handle tabs differently
		if isinstance(elem, QTabWidget):
			for i in range(elem.count()):
				elem.setTabText(i, _translate("", elem.tabText(i)) )
	
	def translate_self(self):
		log.info('Translating UI')
		
		# Loop through all widgets
		for widget in self.findChildren(QWidget):
			self.translate_element(widget)
		# Loop through all actions
		for action in self.findChildren(QAction):
			self.translate_element(action)
