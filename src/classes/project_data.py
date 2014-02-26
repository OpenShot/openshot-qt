""" 
 @file
 @brief This file listens to changes, and updates the primary project data
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>
 
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
from classes import info
from classes.logger import log

class ProjectDataStore(JsonDataStore, UpdateInterface):
	""" This class allows advanced searching of data structure, implements changes interface """
	
	def __init__(self):
		JsonDataStore.__init__(self)
		self.data_type = "project data" # Used in error messages
		self.default_project_filepath = os.path.join(info.PATH, 'settings', '_default.project')
		
		# Set default filepath to user's home folder
		self.current_filepath = os.path.join(os.path.expanduser("~"), ".openshot_qt")

		if not os.path.exists(self.current_filepath):
			# Create folder if it does not exist
			os.makedirs(self.current_filepath)
		
		# Load default project data on creation
		self.new()

	def get(self, key):
		""" Get copied value of a given key in data store """
		
		# Verify key is valid type
		if not isinstance(key, list):
			log.warning("get() key must be a list. key: {}".format(key))
			return None
		if not key:
			log.warning("Cannot get empty key.")
			return None
		
		# Get reference to internal data structure
		obj = self._data
		
		# Iterate through key list finding sub-objects either by name or by an object match criteria such as {"id":"ADB34"}.
		for key_index in range(len(key)):
			key_part = key[key_index]
			
			# Key_part must be a string or dictionary
			if not isinstance(key_part, dict) and not isinstance(key_part, str):
				log.error("Unexpected key part type: {}".format(type(key_part).__name__))
				return None
			
			# If key_part is a dictionary and obj is a list or dict, each key is tested as a property of the items in the current object
			# in the project data structure, and the first match is returned.
			if isinstance(key_part, dict) and isinstance(obj, list):
				#Overall status of finding a matching sub-object
				found = False
				# Loop through each item in object to find match
				for item_index in range(len(obj)):
					item = obj[item_index]
					# True until something disqualifies this as a match
					match = True
					# Check each key in key_part dictionary and if not found to be equal as a property in item, move on to next item in list
					for subkey in key_part.keys():
						# Get each key in dictionary (i.e. "id", "layer", etc...)
						subkey = subkey.lower()
						# If object is missing the key or the values differ, then it doesn't match.
						if not (subkey in item and item[subkey] == key_part[subkey]):
							match = False
							break
					# If matched, set key_part to index of list or dict and stop loop
					if match:
						found = True
						obj = item
						break
				# No match found, return None
				if not found:
					return None
			
			# If key_part is a string, homogenize to lower case for comparisons
			if isinstance(key_part, str):
				key_part = key_part.lower()
			
				# Check current obj type (should be dictionary)
				if not isinstance(obj, dict):
					log.warn("Invalid project data structure. Trying to use a key on a non-dictionary object. Key part: {} (\"{}\").\nKey: {}".format((key_index), key_part, key))
					return None
				
				# If next part of path isn't in current dictionary, return failure
				if not key_part in obj:
					log.warn("Key not found in project. Mismatch on key part {} (\"{}\").\nKey: {}".format((key_index), key_part, key))
					return None
				
				# Get sub-object based on part key as new object, continue to next part
				obj = obj[key_part]
		
		# After processing each key, we've found object, return copy of it
		return copy.deepcopy(obj)

	def set(self, key, value):
		"""Prevent calling JsonDataStore set() method. It is not allowed in ProjectDataStore, as changes come from UpdateManager."""
		raise Exception("ProjectDataStore.set() is not allowed. Changes must route through UpdateManager.")
		
	def _set(self, key, values=None, add=False, partial_update=False, remove=False):
		""" Store setting, but adding isn't allowed. All possible settings must be in default settings file. """
		
		log.info("_set key: {} values: {} add: {} partial: {} remove: {}".format(key, values, add, partial_update, remove))
		parent, my_key = None, ""
		
		# Verify key is valid type
		if not isinstance(key, list):
			log.warning("_set() key must be a list. key: {}".format(key))
			return None
		if not key:
			log.warning("Cannot set empty key.")
			return None
		
		# Get reference to internal data structure
		obj = self._data
		
		# Iterate through key list finding sub-objects either by name or by an object match criteria such as {"id":"ADB34"}.
		for key_index in range(len(key)):
			key_part = key[key_index]
			
			# Set parent to the last set obj
			parent = obj
			
			# Key_part must be a string or dictionary
			if not isinstance(key_part, dict) and not isinstance(key_part, str):
				log.error("Unexpected key part type: {}".format(type(key_part).__name__))
				return None
			
			# Final key_part on add is the element being added. It does not match anything, but it can indicate the key for a parent dictionary.
			if add and key_index == len(key) - 1:
				# log.info("breaking loop for add")
				parent, my_key = obj, key_part
				break
			
			# A blank final key_part on a remove indicates to remove the last item of a list
			# This type of remove is generated as the reverse of an add ending in ""
			if remove and key_index == len(key) - 1 and key_part == "":
				if isinstance(obj, list):
					parent = obj
					key_part = len(obj) - 1 # Save key_part as last index, which will be deleted from parent
					my_key = key_part
					obj = parent[my_key]

			# If key_part is a dictionary and obj is a list or dict, each key is tested as a property of the items in the current object
			# in the project data structure, and the first match is returned.
			if isinstance(key_part, dict) and isinstance(obj, list):
				#Overall status of finding a matching sub-object
				found = False
				# Loop through each item in object to find match
				for item_index in range(len(obj)):
					item = obj[item_index]
					# True until something disqualifies this as a match
					match = True
					# Check each key in key_part dictionary and if not found to be equal as a property in item, move on to next item in list
					for subkey in key_part.keys():
						# Get each key in dictionary (i.e. "id", "layer", etc...)
						subkey = subkey.lower()
						# If object is missing the key or the values differ, then it doesn't match.
						if not (subkey in item and item[subkey] == key_part[subkey]):
							match = False
							break
					# If matched, set key_part to index of list or dict and stop loop
					if match:
						found = True
						obj = item
						my_key = item_index
						break
				# No match found, return None
				if not found:
					return None	
			
			# If key_part is a string, homogenize to lower case for comparisons
			if isinstance(key_part, str):
				key_part = key_part.lower()
			
				# Check current obj type (should be dictionary)
				if not isinstance(obj, dict):
					log.warn("Invalid project data structure. Trying to use a key on a non-dictionary object. Key part: {} (\"{}\").\nKey: {}".format((key_index), key_part, key))
					return None
				
				# If next part of path isn't in current dictionary, return failure
				if not key_part in obj:
					log.warn("Key not found in project. Mismatch on key part {} (\"{}\").\nKey: {}".format((key_index), key_part, key))
					return None
				
				# Get sub-object based on part key as new object, continue to next part
				obj = obj[key_part]
				my_key = key_part


		# After processing each key, we've found object and parent, return former value/s on update
		ret = copy.deepcopy(obj)
		
		# Apply the correct action to the found item
		if remove:
			del parent[my_key]
			
		else:
			# Add or Full Update
			# For adds to list perform an insert to index or the end if not specified
			if add and isinstance(parent, list):
				#log.info("adding to list")
				parent.append(values)
					
			# Otherwise, set the given index
			else:
				# Update existing dictionary value
				obj.update(values)
				
		# Return the previous value to the matching item (used for history tracking)
		return ret
		
				
	# Load default project data
	def new(self):
		""" Try to load default project settings file, will raise error on failure """
		self._data = self.read_from_file(self.default_project_filepath)
		
	def load(self, file_path):
		""" Load project from file """
		
		self.new()
		# Default project data
		default_project = self._data
		
		# Try to load project data, will raise error on failure
		project_data = self.read_from_file(file_path)
		
		# Merge default and project settings, excluding settings not in default.
		self._data = self.merge_settings(default_project, project_data)
		# On success, save current filepath
		self.current_filepath = os.path.dirname(file_path)

	def save(self, file_path):
		""" Save project file to disk """ 
		
		# Try to save project settings file, will raise error on failure
		self.write_to_file(file_path, self._data)
		# On success, save current filepath
		self.current_filepath = os.path.dirname(file_path)

	def changed(self, action):
		""" This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """
		if action.type == "insert":
			# Insert new item
			 old_vals = self._set(action.key, action.values, add=True)
			 action.set_old_values(old_vals) # Save previous values to reverse this action
			
		elif action.type == "update":
			# Update existing item
			old_vals = self._set(action.key, action.values, partial_update=action.partial_update)
			action.set_old_values(old_vals) # Save previous values to reverse this action
			
		elif action.type == "delete":
			# Delete existing item
			old_vals = self._set(action.key, remove=True)
			action.set_old_values(old_vals) # Save previous values to reverse this action

	# Utility methods
	def generate_id(self, digits=10):
		""" Generate random alphanumeric ids """
		
		chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
		id = ""
		for i in range(digits):
			c_index = random.randint(0, len(chars)-1)
			id += (chars[c_index])
		return id
