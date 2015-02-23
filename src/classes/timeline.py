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
		self.timeline = openshot.Timeline(width, height, openshot.Fraction(fps["num"],fps["den"]), 44100, 2)
		self.timeline.info.has_audio = True
		self.timeline.info.has_video = True
		self.timeline.info.video_length = 99999
		self.timeline.info.duration = 999.99
		self.timeline.debug = True

		# Add self as listener to project data updates (at the beginning of the list)
		# This listener will receive events before others.
		self.app.updates.add_listener(self, 0)
		
	def changed(self, action):
		""" This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """
		
		# Ignore changes that don't affect libopenshot
		if len(action.key) >= 1 and action.key[0].lower() in ["files", "profile", "markers", "layers"]:
			return
		
		# Pass the change to the libopenshot timeline
		try:
			if action.type == "load":
				# This JSON is initially loaded to libopenshot to update the timeline
				self.timeline.SetJson(action.json(only_value=True))

			else:
				# This JSON DIFF is passed to libopenshot to update the timeline
				self.timeline.ApplyJsonDiff(action.json(is_array=True))

		except:
			log.info("Error applying JSON to timeline object in libopenshot")
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		