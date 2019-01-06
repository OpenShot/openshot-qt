""" 
 @file
 @brief This file sets the default logging settings
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

import logging
import os, sys
from logging.handlers import RotatingFileHandler
from classes import info


class StreamToLogger(object):
    """Custom class to log all stdout and stderr streams (from libopenshot / and other libraries)"""
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

    def errors(self):
        pass

# Initialize logging module, give basic formats and level we want to report
logging.basicConfig(format="%(module)12s:%(levelname)s %(message)s",
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

# Create a formatter
formatter = logging.Formatter('%(module)12s:%(levelname)s %(message)s')

# Get logger instance & set level
log = logging.getLogger('OpenShot')
log.setLevel(logging.INFO)

# Add rotation file handler
fh = RotatingFileHandler(
    os.path.join(info.USER_PATH, 'openshot-qt.log'), encoding="utf-8", maxBytes=25*1024*1024, backupCount=3)
fh.setFormatter(formatter)
log.addHandler(fh)

def reroute_output():
    """Route stdout and stderr to logger (custom handler)"""
    if not getattr(sys, 'frozen', False):
        so = StreamToLogger(log, logging.INFO)
        sys.stdout = so

        se = StreamToLogger(log, logging.ERROR)
        sys.stderr = se

