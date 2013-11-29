
# SettingStore - class which allows getting/storing of settings, loading and saving to json
import simplejson as json
import sys, os
from PyQt5.QtCore import QStandardPaths
from classes.logger import log

class SettingStore:
	config_filename = "openshot.settings"
	def __init__(self, init_data={}):
		self.data = dict(init_data)

	#Get key from settings
	def get(self, key):
		return self.data.get(key, None)
		
	#Store setting
	def set(self, key, value):
		self.data[key] = value
		
	def filter_settings(self, default, user):
		pass
		
	def load(self, data):
		#Try to find settings file
		file_path = QStandardPaths.locate(QStandardPaths.ConfigLocation, SettingStore.config_filename)
		
		#If file doesn't exist yet, try to create a default settings file
		if not file_path:
			writable_path = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
			
			#Create folder if not found
			if not os.path.exists(writable_path):
				try:
					os.mkdir(writable_path)
				except Exception as ex:
					log.error("Couldn't create config folder for openshot:\n%s\n%s", writable_path, ex)
					return False
					
			#Create blank settings file
			settings = {} #TODO: load default settings file
			settings['default_volume'] = 60
			file_path = os.path.join(writable_path, SettingStore.config_filename)
			try:
				with open(file_path, 'w') as f:
					f.write(json.dumps(settings))
			except Exception as ex:
				log.error("Couldn't create config file for openshot:\n%s\n%s", file_path, ex)
				return False
		#File was found, try to load settings
		else:
			print ('Located config file:',file_path)
			settings = {}
			try:
				with open(file_path, 'r') as f:
					settings = json.loads(f.read())
			except Exception as ex:
				log.error("Couldn't load config file: %s", ex)
				return False
				
		#Save settings and return success
		self.data = settings
		return True
				
			
			