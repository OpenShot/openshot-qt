""" 
 @file
 @brief This file deals with unhandled exceptions
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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

import traceback
from classes.logger import log
from classes.metrics import track_exception_stacktrace


def ExceptionHandler(exeception_type, exeception_value, exeception_traceback):
    """Callback for any unhandled exceptions"""
    log.error('Unhandled Exception', exc_info=(exeception_type, exeception_value, exeception_traceback))

    # Build string of stack trace
    stacktrace = "Python %s" % "".join(traceback.format_exception(exeception_type, exeception_value, exeception_traceback))

    # Report traceback to webservice (if enabled)
    track_exception_stacktrace(stacktrace, "openshot-qt")
