""" 
 @file
 @brief This file contains the video preview QWidget (based on a QLabel)
 @author Jonathan Thomas <jonathan@openshot.org>
 
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
from classes import updates
from classes import info
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo, QRect
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QLabel, QApplication, QMessageBox, QAbstractItemView, QMenu, QSizePolicy
from windows.models.effects_model import EffectsModel
import openshot # Python module for libopenshot (required video editing module installed separately)


class VideoWidget(QLabel):
	""" A QWidget used on the video display widget """ 
	
#	def contextMenuEvent(self, event):
#		# Set context menu mode
#		app = get_app()
#		app.context_menu_object = "effects"
#		
#		menu = QMenu(self)
#		menu.addAction(self.win.actionDetailsView)
#		menu.addAction(self.win.actionThumbnailView)
#		menu.exec_(QCursor.pos())

	def paintEvent(self, event, *args):
		""" Custom paint event """

		if self.current_image:
			# Paint custom frame image on QWidget
			painter = QPainter(self)
			painter.fillRect(event.rect(), self.palette().window());
			painter.drawImage(QRect(0, 0, self.width(), self.height()), self.current_image);
		
	def present(self, image, *args):
		""" Present the current frame """

		# Get frame's QImage from libopenshot
		self.current_image = image
		
		# Force repaint on this widget
		self.repaint()
		
	def connectSignals(self, renderer):
		""" Connect signals to renderer """
		renderer.present.connect(self.present)

	def __init__(self, *args):
		# Invoke parent init
		QLabel.__init__(self, *args)
		
		# Set background-color
		self.setStyleSheet("background-color: #000000;")
		self.setAlignment(Qt.AlignCenter)
		self.setMinimumWidth(400)
		
		# Init current frame's QImage
		self.current_image = None
		
		# Get a reference to the window object
		self.win = get_app().window
		
		

	
	
