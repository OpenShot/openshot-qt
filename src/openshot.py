#!/usr/bin/env python

# @file
# @brief Primary Python file to launch OpenShot 2.0
# @author Jonathan Thomas <jonathan@openshot.org>
#
# @section LICENSE
#
# Copyright (c) 2008-2014 OpenShot Studios, LLC
# (http://www.openshotstudios.com). This file is part of
# OpenShot Video Editor (http://www.openshot.org), an open-source project
# dedicated to delivering high quality video editing and animation solutions
# to the world.
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.

import sys, os
from classes import info
from classes.OpenShotApp import OpenShotApp
from classes.logger import log

# This method launches OpenShot 2.0
def main():
	""""Initialize settings (not implemented) and create main window/application."""
	
	# Display version and exit (if requested)
	if "--version" in sys.argv:
		print ("OpenShot version %s" % info.SETUP['version'])
		exit()

	log.info("--------------------------------")
	log.info("   OpenShot (version %s)" % info.SETUP['version'])
	log.info("--------------------------------")
	
	# Create application
	app = OpenShotApp(sys.argv)
	
	# Run and return result
	sys.exit(app.run())


if __name__ == '__main__':
	main()
