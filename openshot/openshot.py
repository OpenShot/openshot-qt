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

import sys, os
from classes import info
from classes.logger import log
from PyQt5.QtWidgets import QApplication
from windows.MainWindow import MainWindow

# This method starts OpenShot
def main():
	""""Initialise settings (not implemented) and create main window/application."""
	
	# Display version and exit (if requested)
	if "--version" in sys.argv:
		print ("OpenShot version %s" % info.VERSION)
		exit()

	print ("--------------------------------")
	print ("   OpenShot (version %s)" % info.SETUP['version'])
	print ("--------------------------------")
	
	log.info('OpenShot version ' + info.VERSION)

	# Create application
	app = QApplication(sys.argv)
	app.setApplicationName('openshot')
	app.setApplicationVersion(info.VERSION)
	#app.setOrganizationName('OpenShot LLC')
	
	# Create main window and start event loop
	win = MainWindow()
	win.show()
	sys.exit(app.exec_())

if __name__ == '__main__':
	main()
