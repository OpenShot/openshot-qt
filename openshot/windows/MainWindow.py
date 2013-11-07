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
from PyQt5.Qt import *
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = ('windows','ui','main.ui')
	translation_path = ('qt_locale',)
	
	def wheelEvent(self, event):
		if (event.angleDelta().y() != 0):
			print (event.angleDelta().y())
		
	def keyPressEvent(self, event):
		if int(event.modifiers() & Qt.ControlModifier) > 0:
			print ('Control pressed!')
	
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
		locale = QLocale()
		#print (QLocale.languageToString(locale.language()))
		#print (QLocale.countryToString(locale.country()))
		#locale.name()
		#locale.language()
		
		#Create translator and load current locale's file
		trans = QTranslator()
		if not trans.load(QLocale.system(), os.path.join(*self.translation_path)): #QLocale(),
			print ("Translation failed to load (" + os.path.join(*self.translation_path) + ")")
		self.app.installTranslator(trans)
		
		#Create main window base class
		QMainWindow.__init__(self)
		
		#Load ui from configured path
		uic.loadUi(os.path.join(*self.ui_path), self)
		self.setWindowTitle(self.tr('Open Shot'))
		
		#May give window more aggressive focus, such as when nothing else is focused. Not sure. -nfigg
		self.setFocusPolicy(Qt.StrongFocus)
		
		#setup timeline
		self.timeline = TimelineWebView(self)
		
		#connect button to timeline slot
		self.btnGo.clicked.connect(self.timeline.navigate)
		self.findChild(QAction, 'actionShow_Browser').triggered.connect(self.fun)
		
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)
		
		