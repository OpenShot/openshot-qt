""" 
 @file
 @brief This file can easily query Clips, Files, and other project data
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

import os, sys, random, copy
from classes.json_data import JsonDataStore
from classes.updates import UpdateInterface
from classes import info, settings
from classes.logger import log
from classes.app import get_app

class Clip():
	""" This class allows one or more project data objects to be queried """
	
	def __init__(self, **kwargs):
		""" Constructor """
		
		self.app = get_app()
		self.project = app.project
		self.root_key = "clip"
	
	def filter(self, **kwargs):
		""" Take any arguments given as filters, and find a matching object """
		
		for key, value in kwargs.iteritems():
			log.info("%s = %s" % (key, value))

