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

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = ('windows','ui','main.ui')
	translation_path = ('qt_locale',)
	
	def timelineWheelEvent(self, event):
		#For each 120 (standard tick) adjust the zoom slider
		y = event.angleDelta().y()
		up = y > 0
		while (y != 0):
			if up and y > 120:
				y -= 120
			elif not up and y < -120:
				y += 120
			else:
				y = 0
			if (up):
				self.sliderZoom.triggerAction(QAbstractSlider.SliderPageStepAdd)
			else:
				self.sliderZoom.triggerAction(QAbstractSlider.SliderPageStepSub)
		
	@pyqtSlot()
	def fun(self):
		new_setting = not self.timeline.isVisible()
		self.timeline.setVisible(new_setting)
		self.findChild(QAction, 'actionShow_Browser').setVisible(not new_setting)
	
	def exec_(self):
		self.app.exec_()
	
	def __init__(self):
		#Create application and save reference before creating main window
		self.app = QApplication(sys.argv)
		
		#Get system locale
		print( QLocale.languageToString(QLocale.system().language()))
		print (QLibraryInfo.location(QLibraryInfo.TranslationsPath))
		#print (QLocale.languageToString(locale.language()))
		#print (QLocale.countryToString(locale.country()))
		#locale.name()
		#locale.language()
		
		#Create translator and load current locale's file
		trans = QTranslator()
		if not trans.load('qt_' + QLocale().system().name(),QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
			print ("QT Translations failed to load")
		self.app.installTranslator(trans)
		
		#Create translator and load current locale's file
		trans = QTranslator()
		if not trans.load('openshot.en_US.qm', os.path.join(*self.translation_path)): #QLocale(),
			print ("Translation failed to load (" + os.path.join(*self.translation_path) + ")")
		self.app.installTranslator(trans)
		
		#Create main window base class
		QMainWindow.__init__(self)
		
		#Load ui from configured path
		uic.loadUi(os.path.join(*self.ui_path), self)
		self.setWindowTitle(self.tr('Open Shot'))
		
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
		
		#May give window more aggressive focus, such as when nothing else is focused. Not sure. -nfigg
		self.setFocusPolicy(Qt.StrongFocus)
		
		#setup timeline
		self.timeline = TimelineWebView(self)
		
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)
		
		#Do some drawing on the graphics view
		#self.graphicsView.