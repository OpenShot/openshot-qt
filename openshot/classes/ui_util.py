
import os
import xml.etree.ElementTree
from classes.logger import log
from PyQt5.QtGui import QPixmap, QImageReader, QIcon
from PyQt5.QtWidgets import *
from PyQt5 import uic

def load(window, path):
	#Load ui from configured path
	uic.loadUi(os.path.join(*path), window)

	#Save xml tree for ui
	window.uiTree = xml.etree.ElementTree.parse(os.path.join(*path))

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
				if not QIcon.hasThemeIcon(theme_name):
					print ('Icon theme name', theme_name, 'not found. Will try backup icon. (soon)')
				elem.setIcon(QIcon.fromTheme(theme_name))

def init_ui(window):
	log.info('Initializing UI for %s', window.objectName())
	
	# Loop through all widgets
	for widget in window.findChildren(QWidget):
		init_element(window, widget)
	# Loop through all actions
	for action in window.findChildren(QAction):
		init_element(window, action)