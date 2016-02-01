"""
 @file
 @brief This file sends anonymous application metrics and errors over HTTP
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

import httplib2
import platform
import threading
import urllib.parse
from copy import deepcopy
from classes import info
from classes import language
from classes.logger import log
from classes import settings
import openshot

from PyQt5.QtCore import QT_VERSION_STR
from PyQt5.Qt import PYQT_VERSION_STR


# Get libopenshot version
v = openshot.GetVersion()

# Get settings
s = settings.get_settings()

# Build user-agent
user_agent = "Mozilla/5.0 (%s %s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36" % \
             (platform.system(), platform.processor())

params = {
    "cid" : s.get("unique_install_id"),     # Unique install ID
    "v" : 1,                                # Google Measurement API version
    "tid" : "UA-4381101-5",                 # Google Analytic Tracking ID
    "an" : info.PRODUCT_NAME,               # App Name
    "aip" : 1,                              # Anonymize IP
    "aid" : "org.openshot.%s" % info.NAME,  # App ID
    "av" : info.VERSION,                    # App Version
    "ul" : language.get_current_locale().replace('_','-').lower(),   # Current Locale
    "ua" : user_agent,                      # Custom User Agent (for OS, Processor, and OS version)
    "cd1" : v.ToString(),                   # Dimension 1: libopenshot version
    "cd2" : platform.python_version(),      # Dimension 2: python version (i.e. 3.4.3)
    "cd3" : QT_VERSION_STR,                 # Dimension 3: qt5 version (i.e. 5.2.1)
    "cd4" : PYQT_VERSION_STR                # Dimension 4: pyqt5 version (i.e. 5.2.1)
}

def track_metric_session(is_start=True):
    """Track a GUI screen being shown"""
    metric_params = deepcopy(params)
    metric_params["t"] = "screenview"
    metric_params["sc"] = "start"
    metric_params["cd"] = "launch-app"
    if not is_start:
        metric_params["sc"] = "end"
        metric_params["cd"] = "close-app"

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.start()

def track_metric_screen(screen_name):
    """Track a GUI screen being shown"""
    metric_params = deepcopy(params)
    metric_params["t"] = "screenview"
    metric_params["cd"] = screen_name

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.start()

def track_metric_error(error_name, is_fatal=False):
    """Track an error has occurred"""
    metric_params = deepcopy(params)
    metric_params["t"] = "exception"
    metric_params["exd"] = error_name
    metric_params["exf"] = 0
    if is_fatal:
        metric_params["exf"] = 1

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.start()

def send_metric(params):
    """Send anonymous metric over HTTP for tracking"""
    # Check if the user wants to send metrics and errors
    if s.get("send_metrics"):

        url_params = urllib.parse.urlencode(params)
        url = "http://www.google-analytics.com/collect?%s" % url_params

        # Send metric HTTP data
        try:
            resp, content = httplib2.Http(timeout=3).request(url, headers={"user-agent": user_agent})
            log.info("Track metric: %s (%s)" % (resp, content))

        except Exception as Ex:
            log.error("Failed to Track metric: %s" % (Ex))
