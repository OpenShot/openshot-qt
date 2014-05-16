""" 
 @file
 @brief This file contains a timeline object, which listens for updates and syncs a libopenshot timeline object
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
from classes.updates import UpdateInterface
from classes import info, settings
from classes.logger import log
from classes.app import get_app
import openshot # Python module for libopenshot (required video editing module installed separately)

class TimelineSync(UpdateInterface):
	""" This class syncs changes from the timeline to libopenshot """
	
	def __init__(self):
		self.app = get_app()
		project = self.app.project
		
		# Append on some project settings
		fps = project.get(["fps"])
		width = project.get(["width"])
		height = project.get(["height"])
		
		# Create an instance of a libopenshot Timeline object
		self.timeline = openshot.Timeline(width, height, openshot.Fraction(fps,1), 44100, 2)
		
		# Add self as listener to project data updates
		self.app.updates.add_listener(self)
		
	def changed(self, action):
		""" This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """
		
		# Pass the change to the libopenshot timeline
		try:
			if action.type == "load":
				# This JSON is initially loaded to libopenshot to update the timeline
				self.timeline.ApplyJsonDiff(action.json())
			
			else:
				# This JSON DIFF is passed to libopenshot to update the timeline
				self.timeline.ApplyJsonDiff(action.json(is_array=True))
				#print(self.timeline.Json())
				#print(action.json(is_array=True))
				
				#if len(self.timeline.Clips()) > 0:
				#	self.timeline.GetFrame(1).Display()
		except:
			log.info("Error applying JSON to timeline object in libopenshot")
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		