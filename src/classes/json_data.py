""" 
 @file
 @brief This file loads and saves settings (as JSON)
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

try:
    import json
except ImportError:
    import simplejson as json
    
import sys, os, copy
from PyQt5.QtCore import QStandardPaths, QCoreApplication
from classes.logger import log
from classes import info

class JsonDataStore:
	""" This class which allows getting/setting of key/value settings, and loading and saving to json files.
	Internal storage of a dictionary. Uses json or simplejson packages to serialize and deserialize from json to dictionary.
	Keys are assumed to be strings, but subclasses which override get/set methods may use different key types.
	The write_to_file and read_from_file methods are key type agnostic."""
	
	#Create default data storage and default data type for logging messages
	def __init__(self):
		self._data = {} #Private data store, accessible through the get and set methods
		self.data_type = "json data"

	def get(self, key):
		""" Get copied value of a given key in data store """
		key = key.lower()
		return copy.deepcopy(self._data.get(key, None))
		
	def set(self, key, value):
		""" Store value in key """
		key = key.lower()
		self._data[key] = value
		
	def homogenize_keys(self, data):
		""" Make all keys in dictionary lower cased """
		rem_list = []
		add_set = {}
		#Find keys that need changing
		for key in data:
			key_lower = key.lower()
			if key != key_lower:
				rem_list.append(key)
				add_set[key_lower] = data[key]
		#Remove non-lowercase keys
		for key in rem_list:
			#log.info("Removing non-lowercased user setting key '{}'".format(key))
			del data[key]
		#Add lowercased data back in
		for key in add_set:
			#log.info("Relacing with lowercased user setting key '{}'".format(key))
			data[key] = add_set[key]
		
	def merge_settings(self, default, user):
		""" Merge settings files, removing invalid settings based on default settings
			This is only called by some sub-classes that use string keys """
		#Make sure all keys are lowercase
		self.homogenize_keys(default)
		self.homogenize_keys(user)
	
		for key in default:
			if key in user:
				default[key] = user[key]
		
		return default
		
	def read_from_file(self, file_path):
		""" Load JSON settings from a file """
		#log.debug("loading {}".format(file_path))
		try:
			with open(file_path, 'r') as f:
				contents = f.read()
				if contents:
					#log.debug("loaded", contents)
					return json.loads(contents)
		except Exception as ex:
			msg = ("Couldn't load {} file: {}".format(self.data_type, ex))
			log.error(msg)
			raise Exception(msg)
		msg = ("Couldn't load {} file, no data.".format(self.data_type))
		log.warning(msg)
		raise Exception(msg)
		
	def write_to_file(self, file_path, data):
		""" Save JSON settings to a file """
		#log.debug("saving", file_path, data)
		try:
			with open(file_path, 'w') as f:
				f.write(json.dumps(data))
		except Exception as ex:
			msg = ("Couldn't save {} file:\n{}\n{}".format(self.data_type, file_path, ex))
			log.error(msg)
			raise Exception(msg)
		
