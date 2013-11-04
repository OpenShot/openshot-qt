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
from PyQt5.Qt import QMainWindow, QApplication, pyqtSlot, QAction, QTranslator, QMessageBox
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView

#This class combines the main window widget with initializing the application and providing a pass-thru exec_ function
class MainWindow(QMainWindow):
	ui_path = ('windows','ui','main.ui')
	
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
		
		#translate = QTranslator()
		#print ('Loading translation: ', translate.load('OpenShot',
		#	os.path.join('locale','es','LC_Messages'),
		#	) )
		#self.app.installTranslator(translate)
		
		#Create main window base class
		QMainWindow.__init__(self)
		
		#Load ui from configured path
		uic.loadUi(os.path.join(*self.ui_path), self)
		
		#setup timeline
		self.timeline = TimelineWebView(self)
		
		#add timeline to web frame layout
		self.frameWeb.layout().addWidget(self.timeline)
		
		#Do some drawing on the graphics view
		#self.graphicsView.