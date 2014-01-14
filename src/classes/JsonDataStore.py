""" 
 @file
 @brief This file loads and saves settings (as JSON)
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

import simplejson as json
import sys, os, copy
from PyQt5.QtCore import QStandardPaths, QCoreApplication
from classes.logger import log
from classes import info

class JsonDataStore:
	"""JsonDataStore - class which allows getting/storing of settings, loading and saving to json"""
	
	def __init__(self):
		self._data = {} #Private data store, accessible through the get and set methods
		self.data_type = "json data"

	#Get key from settings
	def get(self, key):
		key = key.lower()
		return copy.deepcopy(self._data.get(key, None))
		
	#Store value in key.
	def set(self, key, value):
		key = key.lower()
		self._data[key] = value
		
	#Make all keys in dictionary lower cased
	def homogenize_keys(self, data):
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
			#log.info("Removing non-lowercased user setting key '%s'", key)
			del data[key]
		#Add lowercased data back in
		for key in add_set:
			#log.info("Relacing with lowercased user setting key '%s'", key)
			data[key] = add_set[key]
		
	#Merge settings files, removing invalid settings based on default settings
	def merge_settings(self, default, user):
		#Make sure all keys are lowercase
		self.homogenize_keys(default)
		self.homogenize_keys(user)
	
		for key in default:
			if key in user:
				default[key] = user[key]
		
		return default
		
	def read_from_file(self, file_path):
		#log.debug("loading", file_path)
		try:
			with open(file_path, 'r') as f:
				contents = f.read()
				if contents:
					#log.debug("loaded", contents)
					return json.loads(contents)
		except Exception as ex:
			msg = "Couldn't load %s file: %s" % (self.data_type, ex)
			log.error(msg)
			raise Exception(msg)
		msg = "Couldn't load %s file, no data." % self.data_type
		log.warning(msg)
		raise Exception(msg)
		
	def write_to_file(self, file_path, data):
		#Save data to file
		#log.debug("saving", file_path, data)
		try:
			with open(file_path, 'w') as f:
				f.write(json.dumps(data))
		except Exception as ex:
			msg = "Couldn't save %s file:\n%s\n%s" % (self.data_type, file_path, ex)
			log.error(msg)
			raise Exception(msg)
		