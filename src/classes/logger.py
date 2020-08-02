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

import os, sys
import logging
import logging.handlers

from classes import info

# Dictionary of logging handlers we create, keyed by type
handlers = {}


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


# Create logger instance
log = logging.Logger('OpenShot')

# Set up log formatters
template = '%(levelname)s %(module)s: %(message)s'
console_formatter = logging.Formatter(template)
file_formatter = logging.Formatter('%(asctime)s ' + template, datefmt='%H:%M:%S')

# Add normal stderr stream handler
sh = logging.StreamHandler()
sh.setFormatter(console_formatter)
sh.setLevel(info.LOG_LEVEL_CONSOLE)
log.addHandler(sh)
handlers['stream'] = sh

# Add rotating file handler
fh = logging.handlers.RotatingFileHandler(
    os.path.join(info.USER_PATH, 'openshot-qt.log'), encoding="utf-8", maxBytes=25*1024*1024, backupCount=3)
fh.setFormatter(file_formatter)
fh.setLevel(info.LOG_LEVEL_FILE)
log.addHandler(fh)
handlers['file'] = fh


def reroute_output():
    """Route stdout and stderr to logger (custom handler)"""
    if not getattr(sys, 'frozen', False):
        handlers['stdout'] = StreamToLogger(log, logging.INFO)
        sys.stdout = handlers['stdout']

        handlers['stderr'] = StreamToLogger(log, logging.ERROR)
        sys.stderr = handlers['stderr']


def set_level_file(level=logging.INFO):
    handlers['file'].setLevel(level)


def set_level_console(level=logging.INFO):
    handlers['stream'].setLevel(level)
