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
import os
from PyQt5.QtCore import QStandardPaths, QCoreApplication
from classes.logger import log
from classes import info
from classes.JsonDataStore import JsonDataStore

def get_settings():
	return QCoreApplication.instance().settings

class SettingStore(JsonDataStore):
	"""SettingStore - JsonDataStore sub-class which restricts settings to default settings file, merges user settings on load, assumes default OS dir."""
	
	def __init__(self):
		JsonDataStore.__init__(self)
		self.data_type = "user settings"
		self.settings_filename = "openshot.settings"
		self.default_settings_filename = os.path.join(info.PATH, 'settings', '_default.settings')
		
	#Load user settings file from disk, merging with allowed settings in default settings file. Creates user settings if missing.
	def load(self):
		#Default and user settings objects
		default_settings, user_settings = {}, {}
	
		#try to load default settings, on failure will raise exception to caller
		default_settings = self.read_from_file(self.default_settings_filename)
		
		#Try to find user settings file
		file_path = QStandardPaths.locate(QStandardPaths.ConfigLocation, self.settings_filename)
		
		#If user settings file doesn't exist yet, try to create a default settings file
		if not file_path:
			writable_path = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
			
			#Create folder if not found
			if not os.path.exists(writable_path):
				try:
					os.mkdir(writable_path)
				except Exception as ex:
					msg = "Couldn't create %s folder for openshot:\n%s\n%s" % (self.data_type, writable_path, ex)
					log.error(msg)
					raise Exception(msg)
					
			#Set path to user settings file (will be created below)
			file_path = os.path.join(writable_path, self.settings_filename)

		#File was found, try to load settings
		else:
			#Will raise exception to caller on failure to read
			user_settings = self.read_from_file(file_path)
				
		#Merge default and user settings, excluding settings not in default, Save settings
		self._data = self.merge_settings(default_settings, user_settings)
		
		#Return success of saving user settings file back after merge
		return self.write_to_file(file_path, self._data)
		
	#Save user settings file to disk
	def save(self):
		#Try to find user settings file
		file_path = QStandardPaths.locate(QStandardPaths.ConfigLocation, self.settings_filename)
		
		#If user settings file doesn't exist yet, try to create a default settings file
		if not file_path:
			msg = "Couldn't find %s file on save(). Load must create any missing %s file." % (self.data_type, self.data_type)
			log.error(msg)
			raise Exception(msg)
			
		#try to save data to file, will raise exception on failure
		self.write_to_file(file_path, self._data)

			
			