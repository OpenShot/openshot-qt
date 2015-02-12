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
from PyQt5.QtWidgets import QLabel, QApplication, QMessageBox, QAbstractItemView, QMenu, QSizePolicy, QWidget
from windows.models.effects_model import EffectsModel
import openshot # Python module for libopenshot (required video editing module installed separately)


class VideoWidget(QWidget):
	""" A QWidget used on the video display widget """ 

	def paintEvent(self, event, *args):
		""" Custom paint event """

		# Paint custom frame image on QWidget
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing)
		
		# Fill background black
		painter.fillRect(event.rect(), self.palette().window())

		if self.current_image:
			# DRAW FRAME
			# Calculate new frame image size, maintaining aspect ratio
			pixSize = self.current_image.size()
			pixSize.scale(event.rect().size(), Qt.KeepAspectRatio)
		
			# Scale image
			scaledPix = self.current_image.scaled(pixSize, Qt.KeepAspectRatio, Qt.SmoothTransformation)
		
			# Calculate center of QWidget and Draw image
			center = self.centeredViewport(self.width(), self.height())
			painter.drawImage(center, scaledPix)
			
	def SetAspectRatio(self, new_aspect_ratio, new_pixel_ratio):
		""" Set a new aspect ratio """
		self.aspect_ratio = new_aspect_ratio
		self.pixel_ratio = new_pixel_ratio
			
	def centeredViewport(self, width, height):
		""" Calculate size of viewport to maintain apsect ratio """

		aspectRatio = self.aspect_ratio.ToFloat() * self.pixel_ratio.ToFloat()
		heightFromWidth = width / aspectRatio
		widthFromHeight = height * aspectRatio
	
		if heightFromWidth <= height:
			return QRect(0,(height - heightFromWidth) / 2, width, heightFromWidth)
		else:
			return QRect((width - widthFromHeight) / 2.0, 0, widthFromHeight, height)
		
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
		QWidget.__init__(self, *args)
		
		# Init aspect ratio settings (default values)
		self.aspect_ratio = openshot.Fraction()
		self.pixel_ratio = openshot.Fraction()
		self.aspect_ratio.num = 16
		self.aspect_ratio.den = 9
		self.pixel_ratio.num = 1
		self.pixel_ratio.den = 1
		
		# Init Qt style properties (black background, ect...)
		p = QPalette()
		p.setColor(QPalette.Window, Qt.black)
		super().setPalette(p)
		super().setAttribute(Qt.WA_OpaquePaintEvent)
		super().setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
		
		# Init current frame's QImage
		self.current_image = None
		
		# Get a reference to the window object
		self.win = get_app().window
		
		

	
	
