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
		
# Get project data reference
project = get_app().project

class QueryObject:
	""" This class allows one or more project data objects to be queried """

	def __init__(self):
		""" Constructor """
		
		self.id = None		# Unique ID of object
		self.key = None		# Key path to object in project data
		self.data = None	# Data dictionary of object
		
	def save(self):
		""" Save the object back to the project data store """
		pass

	def delete(self):
		""" Delete the object from the project data store """
		pass
	
	def filter(OBJECT_TYPE, **kwargs):
		""" Take any arguments given as filters, and find a list of matching objects """
		
		# Get a list of all objects of this type
		parent = project.get(OBJECT_TYPE.object_key)
		matching_objects = []
		
		# Loop through all children objects
		for child in parent:
			
			# Loop through all kwargs (and look for matches)
			match = True
			for key, value in kwargs.items():
				if key in child and not child[key] == value:
					match = False
					break
				
			# Add matched record
			if match:
				object = OBJECT_TYPE()
				object.id = child["id"]
				object.key = [OBJECT_TYPE.object_name, { "id" : object.id}]
				object.data = child
				matching_objects.append(object)
				
		# Return matching objects
		return matching_objects
				
	
	def get(OBJECT_TYPE, **kwargs):
		""" Take any arguments given as filters, and find the first matching object """
		
		# Look for matching objects
		matching_objects = QueryObject.filter(OBJECT_TYPE, **kwargs)
		
		if matching_objects:
			return matching_objects[0]
		else:
			return None

class Clip(QueryObject):
	""" This class allows one or more project data objects to be queried """
	object_name = "clips"		# Derived classes should define this
	object_key = [object_name]	# Derived classes should define this also
		
	def save(self):
		""" Save the object back to the project data store """
		log.info("Clip save method")

	def delete(self):
		""" Delete the object from the project data store """
		log.info("Clip delete method")

	def filter(**kwargs):
		""" Take any arguments given as filters, and find a list of matching objects """
		return QueryObject.filter(Clip, **kwargs)
		
	def get(**kwargs):
		""" Take any arguments given as filters, and find the first matching object """
		return QueryObject.get(Clip, **kwargs)
	
				