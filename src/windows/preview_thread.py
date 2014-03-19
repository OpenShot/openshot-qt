""" 
 @file
 @brief This file contains the preview thread, used for displaying previews of the timeline
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
 
import os, time, uuid, shutil
import threading, subprocess, re
from _sre import MAXREPEAT
from urllib.parse import urlparse
from classes import updates
from classes import info
from classes.logger import log
from classes import settings
from classes.query import File
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo, QEvent
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import functools
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json
	
class QPreviewEvent(QEvent):
	""" A custom QEvent, which can safely be sent from the preview thread to the Qt thread (to communicate) """
	 
	def __init__(self, id, data=None, *args):
		# Invoke parent init
		QEvent.__init__(self, id)
		self.data = data
		self.id = id

class PreviewThread(threading.Thread):
	def __init__(self, parent, timeline):

		# base class constructor
		threading.Thread.__init__(self)
		
		# Flag to run thread
		self.is_running = True
		self.number = None
		self.parent = parent
		self.timeline = timeline
		
	def kill(self):
		""" Kill this thread """
		self.is_running = False
		
	def previewFrame(self, number):
		""" Preview a certain frame """
		
		# Mark frame number for processing
		self.number = number

	def run(self):

		# Main loop, waiting for frames to process
		while self.is_running:
			
			# Generate a preview (if needed)
			if self.number:
				# File path of preview
				file_path = os.path.join(info.THUMBNAIL_PATH, "preview.png")
				log.info("Generating thumbnail for frame %s: %s" % (self.number, file_path))
				
				# Generate timeline image
				#timeline.GetFrame(self.number).Save(file_path, 1.0)
		
				# Update preview in Qt
				#QCoreApplication.postEvent(self.parent, QPreviewEvent(1001, { "file_path" : file_path }))
			
			# wait for a small delay
			time.sleep(0.25)
