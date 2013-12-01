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
from classes import info

class ProjectDataStore(JsonDataStore):
	"""ProjectDataStore - JsonDataStore sub-class which allows more advanced searching of data structure, implements changes inteface."""
	
	def __init__(self):
		JsonDataStore.__init__(self)
		self.data_type = "project data" #Used in error messages
		self.current_filepath = "" #What is currently loaded or last saved
		self.default_project_filepath = os.path.join(info.PATH, 'settings', '_default.project')
		
		#Load default project data on creation
		self.new()

	#Load default project data
	def new(self):
		#Try to load default project settings file, will raise error on failure
		self._data = self.read_from_file(self.default_project_filepath)
		
	#Load project from file
	def load(self, file_path):
		#Try to load project settings file, will raise error on failure
		self._data = self.read_from_file(file_path)
		#On success, save current filepath
		self.current_filepath = file_path

	#Save project file to disk
	def save(self, file_path):
		#Try to save project settings file, will raise error on failure
		self.write_to_file(file_path, self._data)
		#On success, save current filepath
		self.current_filepath = file_path
