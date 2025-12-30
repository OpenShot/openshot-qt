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
import copy
import logging
import logging.handlers

from classes import info


class StreamToLogger(object):
    """Custom class to log all stdout and stderr streams (from libopenshot / and other libraries)"""
    def __init__(self, parent_stream, log_level=logging.INFO):
        self.parent = parent_stream or sys.__stderr__
        self.logger = logging.LoggerAdapter(
            logging.getLogger('OpenShot.stderr'), {'source': 'stream'})
        self.log_level = log_level
        self.logbuf = ''

    def write(self, text):
        self.logbuf += str(text) or ""
        self.parent.write(text)

    def flush(self):
        if self.logbuf.rstrip():
            self.logger.log(self.log_level, self.logbuf.rstrip())
        self.logbuf = ''

    def errors(self):
        pass


class StreamFilter(logging.Filter):
    """Filter out lines that originated on the output"""
    def filter(self, record):
        source = getattr(record, "source", "")
        return source != "stream"

# Clamp log messages to a reasonable size to avoid giant lines
MAX_LOG_MESSAGE_LENGTH = 2048


class TruncatingFormatter(logging.Formatter):
    """Formatter that trims overly long log messages."""
    def format(self, record):
        message = record.getMessage()
        if len(message) > MAX_LOG_MESSAGE_LENGTH:
            record = copy.copy(record)
            record.msg = message[:MAX_LOG_MESSAGE_LENGTH] + "... [truncated]"
            record.args = None
        return super().format(record)


# Set up log formatters
template = '%(levelname)s %(module)s: %(message)s'
console_formatter = TruncatingFormatter(template)
file_formatter = TruncatingFormatter('%(asctime)s ' + template, datefmt='%H:%M:%S')

# Configure root logger for minimal logging
logging.basicConfig(level=logging.ERROR)
root_log = logging.getLogger()

# Set up our top-level logging context
log = root_log.getChild('OpenShot')
log.setLevel(info.LOG_LEVEL_FILE)
# Don't pass messages on to root logger
log.propagate = False

#
# Create rotating file handler
#
fh = None
if os.path.exists(info.USER_PATH):
    log_path = os.path.join(info.USER_PATH, 'openshot-qt.log')
    try:
        fh = logging.handlers.RotatingFileHandler(
            log_path, encoding="utf-8", maxBytes=25*1024*1024, backupCount=3
        )
    except OSError:
        # Fall back silently if the log file cannot be created (e.g. during tests
        # in read-only environments)
        fh = logging.NullHandler()

if fh:
    fh.setLevel(info.LOG_LEVEL_FILE)
    fh.setFormatter(file_formatter)
    # Only add the handler when it's a real logger (NullHandler is harmless)
    log.addHandler(fh)
else:
    fh = logging.NullHandler()

#
# Create typical stream handler which logs to stderr
#
sh = logging.StreamHandler(sys.stderr)
sh.setLevel(info.LOG_LEVEL_CONSOLE)
sh.setFormatter(console_formatter)

# Filter out redirected output on console, to avoid duplicates
filt = StreamFilter()
sh.addFilter(filt)

log.addHandler(sh)


def reroute_output():
    """Route stdout and stderr to logger (custom handler)"""
    if (getattr(sys, 'frozen', False)
       or sys.stdout != sys.__stdout__):
        return
    sys.stdout = StreamToLogger(sys.stdout, logging.INFO)
    sys.stderr = StreamToLogger(sys.stderr, logging.WARNING)


def set_level_file(level=logging.INFO):
    """Adjust the minimum log level written to our logfile"""
    fh.setLevel(level)


def set_level_console(level=logging.INFO):
    """Adjust the minimum log level for output to the terminal"""
    sh.setLevel(level)
