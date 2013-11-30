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

# SettingStore - class which allows getting/storing of settings, loading and saving to json
import simplejson as json
import sys, os
from PyQt5.QtCore import QStandardPaths, QCoreApplication
from classes.logger import log
from classes import info

def get_settings():
	return QCoreApplication.instance().settings

class SettingStore:
	"""SettingStore - class which allows getting/storing of settings, loading and saving to json"""
	
	settings_filename = "openshot.settings"
	
	def __init__(self):
		self._data = {} #Private data store, accessible through the get and set methods

	#Get key from settings
	def get(self, key):
		key = key.lower()
		return self._data.get(key, None)
		
	#Store setting, but adding isn't allowed. All possible settings must be in default settings file.
	def set(self, key, value):
		key = key.lower()
		if key in self._data:
			self._data[key] = value
		else:
			log.warn("User setting '%s' is not valid. The following are valid: %s", key, list(self._data.keys()))
		
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
		
	#Load user settings file from disk, merging with allowed settings in default settings file. Creates user settings if missing.
	def load(self):
		#Default and user settings objects
		default_settings, user_settings = {}, {}
	
		#Get Default settings file
		default_path = os.path.join(info.PATH, 'settings', '_default.settings')
		#try to load default settings
		try:
			with open(default_path, 'r') as f:
				default_settings = json.loads(f.read())
		except Exception as ex:
			log.error("Couldn't load default settings file:\n%s\n%s", default_path, ex)
			return False
		
		#Try to find user settings file
		file_path = QStandardPaths.locate(QStandardPaths.ConfigLocation, SettingStore.settings_filename)
		
		#If user settings file doesn't exist yet, try to create a default settings file
		if not file_path:
			writable_path = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
			
			#Create folder if not found
			if not os.path.exists(writable_path):
				try:
					os.mkdir(writable_path)
				except Exception as ex:
					log.error("Couldn't create user settings folder for openshot:\n%s\n%s", writable_path, ex)
					return False
					
			#Set path to user settings file (will be created below)
			file_path = os.path.join(writable_path, SettingStore.settings_filename)

		#File was found, try to load settings
		else:
			#log.info('Located user settings file: %s',file_path)
			try:
				with open(file_path, 'r') as f:
					contents = f.read()
					if contents:
						user_settings = json.loads(contents)
			except Exception as ex:
				log.error("Couldn't load user settings file: %s", ex)
				return False
				
		#Merge default and user settings, excluding settings not in default, Save settings
		self._data = self.merge_settings(default_settings, user_settings)
		
		#Save user settings file back after merge
		try:
			with open(file_path, 'w') as f:
				f.write(json.dumps(self._data))
		except Exception as ex:
			log.error("Couldn't save user settings file for openshot:\n%s\n%s", file_path, ex)
			return False
				
		#Return success
		return True
		
	#Save user settings file to disk
	def save(self):
		#Try to find user settings file
		file_path = QStandardPaths.locate(QStandardPaths.ConfigLocation, SettingStore.settings_filename)
		
		#If user settings file doesn't exist yet, try to create a default settings file
		if not file_path:
			log.error("Couldn't fine settings file on save(). Load must create any missing settings file.")
			return False
			
		try:
			with open(file_path, 'w') as f:
				f.write(json.dumps(self._data))
		except Exception as ex:
			log.error("Couldn't save config file for openshot:\n%s\n%s", file_path, ex)
			return False

		#Return success
		return True
			
			