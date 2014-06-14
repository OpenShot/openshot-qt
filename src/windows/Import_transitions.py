"""
 @file
 @brief This file loads the import transition dialog (i.e add external transitions)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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

import os
import sys
import shutil
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from classes import info, ui_util, settings, qt_types, updates
from classes.logger import log
from classes.app import get_app
from windows.views.transitions_treeview import TransitionsTreeView
from windows.views.transitions_listview import TransitionsListView

class ImportTransition(QDialog):
	""" Import Transitions Dialog """

	# Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'import-transitions.ui')

	def __init__(self):

		# Create dialog class
		QDialog.__init__(self)

		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)

		#Init UI
		ui_util.init_ui(self)

		#get translations
		self.app = get_app()
		_ = self.app._tr

		#set events handlers
		self.btnImport.clicked.connect(self.choose_transition)
		self.btnImport.pressed.connect(self.import_transition)

		#Init some variables
		self.buttonBox.button(QDialogButtonBox.Ok).setVisible(False)
		self.transition_file = ""
		#self.project = project


	def choose_transition(self):
		""" choose the  transition file """

		#get translation
		self.app = get_app()
		_ = self.app._tr

		#Todo add extension files for import only thoses when the import dialog is called
		#file_extension = ("PNG Files (*.png), PPM Files (*.ppm), SVG Files (*.svg)")
		transition_file = QFileDialog.getOpenFileNames(self, _("Import Transition..."))[0]
		#return transition_file[0]
		if transition_file:
			#self.btnImport.clear()
			self.btnImport.setText(str(transition_file))

	def import_transition(self):
		""" Add the transition to the project and update the listview """
		#active the ok button
		self.buttonBox.button(QDialogButtonBox.Ok).setVisible(True)
		self.btnImport.setText(self.transition_file)

		#Create in user directory the transitions folder
		if not os.path.exists(info.TRANSITION_PATH):
			os.makedirs(info.TRANSITION_PATH)

		try:
			#Init file paths
			(dirName, filename) = os.path.split(self.transition_file)
			(simple_filename, file_extension) = os.path.splitext(filename)
			new_transition_path = os.path.join(info.TRANSITION_PATH, filename)

			#Copy transition & icon into Openshot folder
			shutil.copyfile(self.transition_file, new_transition_path)

			#Refresh the main screen to show the new transition in the listview
			self.refresh_view()

			#Show a QMessagebox for user to know if it is a success or a chess
			QMessageBox.information(self, "OpenShot", _("Transition Imported with successfully!"))

		except:
			#Show a QMessagebox for user to know that's a chess
			QMessageBox.information(self, "OpenShot", _("There was an error importing the Transition"))
