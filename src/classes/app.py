""" 
 @file
 @brief This file creates the QApplication, and displays the main window
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

from classes.logger import log
from classes import info, settings, project_data, updates, language, ui_util
from PyQt5.QtWidgets import QApplication

def get_app():
	""" Returns the current QApplication instance of OpenShot """
	return QApplication.instance()

class OpenShotApp(QApplication):
	""" This class is the primary QApplication for OpenShot """
	
	def __init__(self, *args):
		QApplication.__init__(self, *args)
		
		#Setup appication
		self.setApplicationName('openshot')
		self.setApplicationVersion(info.SETUP['version'])
		
		# Init settings
		self.settings = settings.SettingStore()
		try:
			self.settings.load()
		except Exception as ex:
			log.error("Couldn't load user settings. Exiting.\n%s", ex)
			exit()
		
		#Init translation system
		language.init_language()
		
		#Tests of project data loading/saving
		self.project = project_data.ProjectDataStore()
		
		#Init Update Manager
		self.updates = updates.UpdateManager()
		#It is important that the project is the first listener if the key gets updat
		self.updates.add_listener(self.project)
			
		#Load ui theme if not set by OS
		ui_util.load_theme()
			
		# Create main window
		from windows.main_window import MainWindow
		self.window = MainWindow()
		self.window.show()
			
	def _tr(self, message):
		return self.translate("", message)
		
	#Start event loop
	def run(self):
		""" Start the primary Qt event loop for the interface """

		res = self.exec_()
		
		try:
			self.settings.save()
		except Exception as ex:
			log.error("Couldn't save user settings on exit.\n%s", ex)
			
		#return exit result
		return res
