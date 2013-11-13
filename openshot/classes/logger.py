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

import logging

#Initialize logging module, give basic formats and level we want to report
logging.basicConfig(format="%(asctime)s %(module)s:%(levelname)s %(message)s", datefmt='%H:%M:%S', level=logging.INFO)

#Get OpenShot logger and set log level
#Alternative spaced out format: "%(asctime)s %(levelname)-7s %(module)-12s %(message)s"
log = logging.getLogger('OpenShot')
log.setLevel(logging.DEBUG)
