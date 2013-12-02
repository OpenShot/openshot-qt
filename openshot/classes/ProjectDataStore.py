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

import os
from classes.JsonDataStore import JsonDataStore
from classes.UpdateManager import UpdateInterface
from classes import info

class ProjectDataStore(JsonDataStore, UpdateInterface):
	"""ProjectDataStore - JsonDataStore sub-class which allows more advanced searching of data structure, implements changes inteface."""
	
	def __init__(self):
		JsonDataStore.__init__(self)
		self.data_type = "project data" #Used in error messages
		self.current_filepath = "" #What is currently loaded or last saved
		self.default_project_filepath = os.path.join(info.PATH, 'settings', '_default.project')
		
		#Load default project data on creation
		self.new()

	def get(self, key):
		key = key.lower()
		if not key:
			log.warning("Cannot get empty key.")
			return None
		parts = key.split("/")
		obj = self._data
		#Walk object tree expecting the key path to be from root.
		while (True):
			key_part = parts.pop(0)
			#If object is a list, use int key instead of string
			if isinstance(obj, list):
				key_part = int(key_part) #May throw error on non-int index to list
			#If next part of path isn't in current object map, return failure
			if not key_part in obj:
				return None
			#Get sub-object based on part key as new object
			obj = obj[key_part]
			#If this was last part, we've found object, return it
			if len(parts) == 0:
				return obj

	#Store setting, but adding isn't allowed. All possible settings must be in default settings file.
	def _set(self, key, values=None, add=False, partial_update=False, remove=False):
		key = key.lower()
		
		if not key:
			log.warning("Cannot set empty key.")
			return None
		parts = key.split("/")
		parent, my_key = None, ""
		obj = self._data
		#Walk object tree expecting the key path to be from root.
		while (True):
			key_part = parts.pop(0)
			#If object is a list, use int key instead of string
			if isinstance(obj, list):
				key_part = int(key_part) #May throw error on non-int index to list
			#If this is an add and we are on last part, check and add it
			if add and len(parts) == 0:
				if key_part in obj:
					log.warning("Add attempted with existing key: %s", key)
					return None
				#Store new key,value
				obj[key_part] = values
				return None					
				
			#If next part of path isn't in current object map, return failure
			if not key_part in obj:
				return None
			#Get sub-object based on part key as new object
			parent, my_key = obj, key_part
			obj = obj[key_part]
			
			#If this was last part, we've found object, set/update it
			if len(parts) == 0:
				ret = None
				#If partial update and both object and values are dictionaries, only copy over the keys in 'values'
				if isinstance(obj, dict) and isinstance(values, dict) and partial_update:
					ret = dict()
					for k in values:
						ret[k] = obj[k] #Save each old value
						obj[k] = values[k] #Set new value
				elif remove:
					ret = obj #Save old value of 
					del parent[my_key]
				else:
					ret = parent[my_key]
					parent[my_key] = values
				return ret
		
		
				
	#Load default project data
	def new(self):
		#Try to load default project settings file, will raise error on failure
		self._data = self.read_from_file(self.default_project_filepath)
		
	#Load project from file
	def load(self, file_path):
		#Re-load default project
		self.new()
		#Default project data
		default_project = self._data
		
		#Try to load project data, will raise error on failure
		project_data = self.read_from_file(file_path)
		
		#Merge default and project settings, excluding settings not in default.
		self._data = self.merge_settings(default_project, project_data)
		#On success, save current filepath
		self.current_filepath = file_path

	#Save project file to disk
	def save(self, file_path):
		#Try to save project settings file, will raise error on failure
		self.write_to_file(file_path, self._data)
		#On success, save current filepath
		self.current_filepath = file_path

	#UpdateInterface methods
	def add(self, action):
		self._set(action.key, action.values, add=True)
	
	def update(self, action):
		old_vals = self._set(action.key, action.values, partial_update=action.partial_update)
		action.set_old_values(old_vals) #Save previous values to reverse this action
		
	def remove(self, action):
		old_vals = self._set(action.key, remove=True)
		action.set_old_values(old_vals)
