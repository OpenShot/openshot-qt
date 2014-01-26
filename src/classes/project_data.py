""" 
 @file
 @brief This file listens to changes, and updates the primary project data
 @author Noah Figg <eggmunkee@hotmail.com>
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

import os, random, copy
from classes.json_data import JsonDataStore
from classes.updates import UpdateInterface
from classes import info
from classes.logger import log

class ProjectDataStore(JsonDataStore, UpdateInterface):
	""" This class allows advanced searching of data structure, implements changes interface """
	
	def __init__(self):
		JsonDataStore.__init__(self)
		self.data_type = "project data" #Used in error messages
		self.current_filepath = "" #What is currently loaded or last saved
		self.default_project_filepath = os.path.join(info.PATH, 'settings', '_default.project')
		
		#Load default project data on creation
		self.new()

	def get(self, key):
		""" Get copied value of a given key in data store """
		
		if not isinstance(key, list):
			log.warning("get() key must be a list. key: %s", key)
			return None
		if not key:
			log.warning("Cannot get empty key.")
			return None
		obj = self._data
		#Iterate through key list finding subobjects either by name or by an object match criteria such as {"id":"ADB34"}.
		for i in range(len(key)):
			key_part = key[i]
			
			#Key_part must be a string or dictionary
			if not isinstance(key_part, dict) and not isinstance(key_part, str) and not isinstance(key_part, int):
				log.error("Unexpected key part type: %s", type(key_part).__name__)
				return None
			#Object must be a dictionary or list (in order to sub-navigate)
			if not isinstance(obj, dict) and not isinstance(obj, list):
				log.error("Unexpected project data store object type: %s", type(obj).__name__)
				return None
			
			#If key_part is a dictionary and obj is a list or dict, each key is tested as a property of the items in the current object
			# in the project data structure, and the first match is returned.
			if isinstance(key_part, dict) and (isinstance(obj, list) or isinstance(obj, dict)):
				#Overall status of finding a matching subobject
				found = False
				#Loop through each item in object to find match
				for obj_key in obj:
					item = obj[obj_key]
					#True until something disqualifies this as a match
					match = True
					#Check each key in key_part dictionary and if not found to be equal as a property in item, move on to next item in list
					for subkey in key_part:
						subkey = subkey.lower()
						#If object is missing the key or the values differ, then it doesn't match.
						if (not subkey in item) or item[subkey] == key_part[subkey]:
							match = False
							break #exit subkey for loop, this item didn't qualify
					#If matched, set key_part to index of list or dict and stop loop
					if match:
						found = True
						key_part = obj_key
						break
				#No match found, return None
				if not found:
					return None
			
			#If key_part is a string, homogenize to lower case for comparisons
			if isinstance(key_part, str):
				key_part = key_part.lower()
				#If object is a list, key_part must be an int index.
				if isinstance(obj, list):
					try:
						key_part = int(key_part) #May throw error on non-int index to list
					except:
						return None
			
			#If next part of path isn't in current object map, return failure
			if not key_part in obj:
				log.warn("Key not found in project. Mismatch on key part %s (\"%s\").\nKey: %s", (i+1), key_part, key)
				return None
			#Get sub-object based on part key as new object, continue to next part
			obj = obj[key_part]
		
		#After processing each key, we've found object, return copy of it
		return copy.deepcopy(obj)

	def set(self, key, value):
		"""Prevent calling JsonDataStore set() method. It is not allowed in ProjectDataStore, as changes come from UpdateManager."""
		
		raise Exception("ProjectDataStore.set() is not allowed. Changes must route through UpdateManager.")
		
	def _set(self, key, values=None, add=False, partial_update=False, remove=False):
		""" Store setting, but adding isn't allowed. All possible settings must be in default settings file. """
		
		log.info("_set key: %s values: %s add: %s partial: %s remove: %s", key, values, add, partial_update, remove)
		if not isinstance(key, list):
			log.warning("set() key must be a list. key: %s", key)
			return None
		if not key:
			log.warning("Cannot set empty key.")
			return None
			
		parent, my_key = None, ""
		obj = self._data
		
		#Iterate through key list finding subobjects either by name or by an object match criteria such as {"id":"ADB34"}.
		for i in range(len(key)):
			key_part = key[i]
			#log.info("index: %s key_part: %s", i, key_part)
						
			#Key_part must be a string or dictionary
			if not isinstance(key_part, dict) and not isinstance(key_part, str):
				log.error("Unexpected key part type: %s", type(key_part).__name__)
				return None
			#Object must be a dictionary or list (in order to sub-navigate)
			if not isinstance(obj, dict) and not isinstance(obj, list):
				log.error("Unexpected project data store object type: %s", type(obj).__name__)
				return None
				
			#Final key_part on add is the element being added. It does not match anything, but it can indicate the key for a parent dictionary.
			if add and i == len(key) - 1:
				#log.info("breaking loop for add")
				parent, my_key = obj, key_part
				
				#Break loop and go straight to add operation
				break
				
			#A blank final key_part on a remove indicates to remove the last item of a list
			# This type of remove is generated as the reverse of an add ending in ""
			if remove and i == len(key) - 1 and key_part == "":
				if isinstance(obj, list):
					key_part = len(obj) - 1 #Save key_part as last index, which will be deleted from parent
				else:
					log.error("Remove ending in blank must be a list. Key: %s", key)
					return None
			
			#If key_part is a dictionary and obj is a list, each key is tested as a property of the current object
			# in the project data structure, and the first match index is saved.
			if isinstance(key_part, dict) and (isinstance(obj, list) or isinstance(obj, dict)):
				#Overall status of finding a matching subobject
				found = False
				for obj_key in obj:
					item = obj[obj_key]
					#True until something disqualifies this as a match
					match = True
					#Check each key in key_part dictionary and if not found to be equal as a property in item, move on to next item in list
					for subkey in key_part:
						subkey = subkey.lower()
						#If object is missing the key or the values differ, then it doesn't match.
						if (not subkey in item) or item[subkey] == key_part[subkey]:
							match = False
							break #exit subkey for loop, this item didn't qualify
					#If matched, set key_part to index of list or dict and stop loop
					if match:
						found = True
						key_part = obj_key
						break
				#No match found, return None
				if not found:
					return None			
			
			#If key_part is a string, homogenize to lower case for comparisons
			if isinstance(key_part, str) and key_part != "":
				key_part = key_part.lower()
				#If object is a list and key_part a str, convert to an int index.
				if isinstance(obj, list):
					try:
						key_part = int(key_part) #May throw error on non-int index to list
					except:
						log.error("Invalid index to list: %s", key_part)
						return None
			
			#If next part of path isn't in current object dict or list, return failure
			#log.info("path check key_part: %s in object: %s, contained: %s", key_part, obj, (key_part in obj))
			#Check if index is valid for list or dict
			if not (isinstance(obj, list) and key_part >= 0 and key_part < len(obj)) and not (isinstance(obj, dict) and key_part in obj):
				log.error("Key not found in project. Mismatch on key part %s (%s).\nKey: %s", (i+1), key_part, key)
				return None
			
			#Get sub-object based on part key as new object
			parent, my_key = obj, key_part
			obj = obj[key_part]
			
		#After processing each key, we've found object and parent, return former value/s on update
		ret = None
		#If partial update and both object and values are dictionaries, only copy over the keys in 'values'
		if isinstance(obj, dict) and isinstance(values, dict) and partial_update:
			ret = dict()
			for k in values:
				ret[k] = obj[k] #Save each old value
				obj[k] = values[k] #Set new value
		elif remove:
			ret = obj #Save old value of removed object
			del parent[my_key]
		else: #Add or Full Update
			ret = obj
			#For adds to list perform an insert to index or the end if not specified
			if add and isinstance(parent, list):
				#log.info("adding to list")
				if my_key == "":
					parent.append(values)
				elif isinstance(my_key, int):
					parent.insert(my_key, values)
			#Otherwise, set the given index
			else:
				#log.info("setting key on dict")
				parent[my_key] = values
		return ret
		
				
	#Load default project data
	def new(self):
		""" Try to load default project settings file, will raise error on failure """
		self._data = self.read_from_file(self.default_project_filepath)
		
	def load(self, file_path):
		""" Load project from file """
		
		self.new()
		#Default project data
		default_project = self._data
		
		#Try to load project data, will raise error on failure
		project_data = self.read_from_file(file_path)
		
		#Merge default and project settings, excluding settings not in default.
		self._data = self.merge_settings(default_project, project_data)
		#On success, save current filepath
		self.current_filepath = file_path

	def save(self, file_path):
		""" Save project file to disk """ 
		
		#Try to save project settings file, will raise error on failure
		self.write_to_file(file_path, self._data)
		#On success, save current filepath
		self.current_filepath = file_path

	def changed(self, action):
		""" This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """
		if action.type == "insert":
			# Insert new item
			self._set(action.key, action.values, add=True)
			
		elif action.type == "update":
			# Update existing item
			old_vals = self._set(action.key, action.values, partial_update=action.partial_update)
			action.set_old_values(old_vals) #Save previous values to reverse this action
			
		elif action.type == "delete":
			# Delete existing item
			old_vals = self._set(action.key, remove=True)
			action.set_old_values(old_vals)

	#Utility methods
	def generate_id(self, digits=10):
		""" Generate random alphanumeric ids """
		
		chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
		id = ""
		for i in range(digits):
			c_index = random.randint(0, len(chars)-1)
			id += (chars[c_index])
		return id
