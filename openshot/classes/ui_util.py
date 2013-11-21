
import os
import xml.etree.ElementTree
from classes.logger import log
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QPixmap, QImageReader, QIcon
from PyQt5.QtWidgets import *
from PyQt5 import uic

DEFAULT_THEME_NAME = "Compass"

def load_theme():
	#If theme not reported by OS
	if QIcon.themeName() == '':
		#Address known Ubuntu bug of not reporting configured theme name, use default ubuntu theme
		if os.getenv('DESKTOP_SESSION') == 'ubuntu':
			QIcon.setThemeName("ubuntu-mono-dark")
		#Windows/Mac use packaged theme
		else:
			QIcon.setThemeName(DEFAULT_THEME_NAME)
			
def load_ui(window, path):
	#Load ui from configured path
	uic.loadUi(path, window)

	#Save xml tree for ui
	window.uiTree = xml.etree.ElementTree.parse(path)

def get_default_icon(theme_name):
	#Default path to backup icons
	start_path = ":/icons/" + DEFAULT_THEME_NAME + "/"
	
	icon_path = search_dir(start_path, theme_name)
	return QIcon(icon_path), icon_path

def search_dir(base_path, theme_name):
	#Search each entry in this directory
	base_dir = QDir(base_path)
	for e in base_dir.entryList():
		#Path to current item
		path = base_dir.path() + "/" + e
		base_filename = e.split('.')[0]
		
		#If file matches theme name, return
		if base_filename == theme_name:
			return path
	
		#If this is a directory, search within it
		dir = QDir(path)
		if dir.exists():
			#If found below, return it
			res = search_dir(path, theme_name)
			if res:
				return res

	#If no match found in dir, return None
	return None
	
#Initialize language and icons of the given element
def init_element(window, elem):
	_translate = QApplication.instance().translate
	
	name = ''
	if hasattr(elem, 'objectName'):
		name = elem.objectName()
	
	#Handle generic translatable properties
	if hasattr(elem, 'setText') and elem.text() != "":
		elem.setText( _translate("", elem.text()) )
	if hasattr(elem, 'setTooltip') and elem.tooltip() != "":
		elem.setTooltip( _translate("", elem.tooltip()) )
	if hasattr(elem, 'setWindowTitle') and elem.windowTitle() != "":
		elem.setWindowTitle( _translate("", elem.windowTitle()) )
	if hasattr(elem, 'setTitle') and elem.title() != "":
		elem.setTitle( _translate("", elem.title()) )
	#Handle tabs differently
	if isinstance(elem, QTabWidget):
		for i in range(elem.count()):
			elem.setTabText(i, _translate("", elem.tabText(i)) )
			elem.setTabToolTip(i, _translate("", elem.tabToolTip(i)) )
	#Set icon if possible
	if hasattr(elem, 'setIcon') and name != '': #Has ability to set its icon
		type_filter = 'action'
		if isinstance(elem, QWidget): #Search for widget with name instead
			type_filter = 'widget'
		#Find iconset in tree (if any)
		iconset = window.uiTree.find('.//' + type_filter + '[@name="' + name + '"]/property[@name="icon"]/iconset')
		if iconset != None: #For some reason "if iconset:" doesn't work the same as "!= None"
			theme_name = iconset.get('theme', '')
			if theme_name:
				has_icon = QIcon.hasThemeIcon(theme_name)
				if not has_icon:
					log.warn('Icon theme %s not found. Will use backup icon.', theme_name)
				fallback_icon, fallback_path = get_default_icon(theme_name)
				#log.info('Fallback icon path for %s is %s', theme_name, fallback_path)
				if has_icon or fallback_icon:
					elem.setIcon(QIcon.fromTheme(theme_name, fallback_icon))

def init_ui(window):
	log.info('Initializing UI for %s', window.objectName())
	
	# Loop through all widgets
	for widget in window.findChildren(QWidget):
		init_element(window, widget)
	# Loop through all actions
	for action in window.findChildren(QAction):
		init_element(window, action)
