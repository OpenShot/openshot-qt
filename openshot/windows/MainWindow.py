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
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView
from classes import language

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = ('windows','ui','main.ui')
	
	def exec_(self):
		#start application event loop (blocks until close)
		self.app.exec_()
	
	def __init__(self):
		#Create application and save reference before creating main window
		app = QApplication(sys.argv)
		self.app = app
		
		#Create main window base class
		QMainWindow.__init__(self)
		
		#Load ui from configured path
		uic.loadUi(os.path.join(*self.ui_path), self)
		
		#Add code here to save default translations in a dict, to use on retranslate events (prevent need for pyuic5 generated retranslateUi() function
		
		#Init translation system
		language.init_language(app)
		
		#Translate ui to current language
		# TODO: improve to generically translate text and tooltips of standard components, see if this is feasible
		self.retranslateUi()
		
		#Set icons on actions
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
		
		#setup timeline
		self.timeline = TimelineWebView(self)
		
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)
		
	
	#imported from pyuic5 output, but with the context "" instead of "MainWindow"
	def retranslateUi(self):
		_translate = self.app.translate
		self.setWindowTitle(_translate("", "OpenShot"))
		self.pushButton_2.setText(_translate("", "Show All"))
		self.pushButton_3.setText(_translate("", "Video"))
		self.pushButton_4.setText(_translate("", "Audio"))
		self.pushButton_5.setText(_translate("", "Image"))
		self.tabMain.setTabText(self.tabMain.indexOf(self.tab), _translate("", "Project Files"))
		self.tabMain.setTabText(self.tabMain.indexOf(self.tab_2), _translate("", "Transitions"))
		self.tabMain.setTabText(self.tabMain.indexOf(self.tab_3), _translate("", "Effects"))
		self.tabMain.setTabText(self.tabMain.indexOf(self.tab_4), _translate("", "History"))
		self.label_2.setText(_translate("", "OpenShot Error"))
		self.pushButton.setText(_translate("", "OpenShot"))
		self.label.setText(_translate("", "Zoom"))
		self.menuFile.setTitle(_translate("", "File"))
		self.toolBar.setWindowTitle(_translate("", "toolBar"))
		self.actionNew.setText(_translate("", "New Project..."))
		self.actionNew.setToolTip(_translate("", "New Project..."))
		self.actionShow_Browser.setText(_translate("", "Show Browser"))
		self.actionOpen.setText(_translate("", "Open Project..."))
		self.actionOpen.setToolTip(_translate("", "Open Project..."))
		self.actionSave.setText(_translate("", "Save Project"))
		self.actionSave.setToolTip(_translate("", "Save Project"))
		self.actionUndo.setText(_translate("", "Undo"))
		self.actionSaveAs.setText(_translate("", "Save Project As..."))
		self.actionSaveAs.setToolTip(_translate("", "Save Project As..."))
		self.actionRecent.setText(_translate("", "Recent Projects"))
		self.actionRecent.setToolTip(_translate("", "Recent Projects"))
		self.actionImportFiles.setText(_translate("", "Import Files..."))
		self.actionImportFiles.setToolTip(_translate("", "Import Files..."))
		self.actionImportImageSequence.setText(_translate("", "Import Image Sequence..."))
		self.actionImportImageSequence.setToolTip(_translate("", "Import Image Sequence..."))
		self.actionImportTransition.setText(_translate("", "Import New Transition..."))
		self.actionImportTransition.setToolTip(_translate("", "Import New Transition..."))
		self.actionRedo.setText(_translate("", "Redo"))
		self.actionRedo.setToolTip(_translate("", "Redo"))
		self.actionPlay.setText(_translate("", "Play"))
		self.actionPlay.setToolTip(_translate("", "Play"))