"""
 @file
 @brief This file sends anonymous application metrics and errors over HTTP
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

# idna encoding import required to prevent bug (unknown encoding: idna)
import encodings.idna
import requests
import platform
import threading
import time
import urllib.parse
import json

from classes import info
from classes import language
from classes.app import get_app
from classes.logger import log

import openshot

from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

try:
    import distro
except ModuleNotFoundError:
    distro = None

# Get settings
s = get_app().get_settings()

# Determine OS version
os_version = "X11; Linux %s" % platform.machine()
os_distro = "None"
try:
    if platform.system() == "Darwin":
        v = platform.mac_ver()
        os_version = "Macintosh; Intel Mac OS X %s" % v[0].replace(".", "_")
        os_distro = "OS X %s" % v[0]

    elif platform.system() == "Windows":
        v = platform.win32_ver()
        os_version = "Windows NT %s; %s" % (v[0], v[1])
        os_distro = "Windows %s" % "-".join(v)

    elif platform.system() == "Linux":
        # Get the distro name and version (if any)
        if distro:
            os_distro = "-".join(distro.linux_distribution()[0:2])
        else:
            os_distro = "Linux"

except Exception:
    log.debug("Error determining OS version", exc_info=1)

# Build user-agent
user_agent = "Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36" % os_version

params = {
    "cid": s.get("unique_install_id"),      # Unique install ID
    "v": 1,                                 # Google Measurement API version
    "tid": "UA-4381101-5",                  # Google Analytic Tracking ID
    "an": info.PRODUCT_NAME,                # App Name
    "aip": 1,                               # Anonymize IP
    "aid": "org.openshot.%s" % info.NAME,   # App ID
    "av": info.VERSION,                     # App Version
    "ul": language.get_current_locale().replace('_', '-').lower(),   # Current Locale
    "ua": user_agent,                       # Custom User Agent (for OS, Processor, and OS version)
    "cd1": openshot.OPENSHOT_VERSION_FULL,  # Dimension 1: libopenshot version
    "cd2": platform.python_version(),       # Dimension 2: python version (i.e. 3.4.3)
    "cd3": QT_VERSION_STR,                  # Dimension 3: qt5 version (i.e. 5.2.1)
    "cd4": PYQT_VERSION_STR,                # Dimension 4: pyqt5 version (i.e. 5.2.1)
    "cd5": os_distro
}

# Queue for metrics (incase things are disabled... just queue it up
# incase the user enables metrics later
metric_queue = []


def track_metric_screen(screen_name):
    """Track a GUI screen being shown"""
    metric_params = json.loads(json.dumps(params))
    metric_params["t"] = "screenview"
    metric_params["cd"] = screen_name
    metric_params["cid"] = s.get("unique_install_id")

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.daemon = True
    t.start()


def track_metric_event(event_action, event_label, event_category="General", event_value=0):
    """Track a GUI screen being shown"""
    metric_params = json.loads(json.dumps(params))
    metric_params["t"] = "event"
    metric_params["ec"] = event_category
    metric_params["ea"] = event_action
    metric_params["el"] = event_label
    metric_params["ev"] = event_value
    metric_params["cid"] = s.get("unique_install_id")

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.daemon = True
    t.start()


def track_metric_error(error_name, is_fatal=False):
    """Track an error has occurred"""
    metric_params = json.loads(json.dumps(params))
    metric_params["t"] = "exception"
    metric_params["exd"] = error_name
    metric_params["exf"] = 0
    if is_fatal:
        metric_params["exf"] = 1

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.daemon = True
    t.start()


def track_metric_session(is_start=True):
    """Track a GUI screen being shown"""
    metric_params = json.loads(json.dumps(params))
    metric_params["t"] = "screenview"
    metric_params["sc"] = "start"
    metric_params["cd"] = "launch-app"
    metric_params["cid"] = s.get("unique_install_id")
    if not is_start:
        metric_params["sc"] = "end"
        metric_params["cd"] = "close-app"

    t = threading.Thread(target=send_metric, args=[metric_params])
    t.daemon = True
    t.start()


def send_metric(params):
    """Send anonymous metric over HTTP for tracking"""

    # Add to queue and *maybe* send if the user allows it
    metric_queue.append(params)

    # Check if the user wants to send metrics and errors
    if s.get("send_metrics"):

        for metric_params in metric_queue:
            url_params = urllib.parse.urlencode(metric_params)
            url = "https://www.google-analytics.com/collect?%s" % url_params

            # Send metric HTTP data
            try:
                r = requests.get(url, headers={"user-agent": user_agent})
            except Exception:
                log.warning("Failed to track metric", exc_info=1)

            # Wait a moment, so we don't spam the requests
            time.sleep(0.25)

        # All metrics have been sent (or attempted to send)
        # Clear the queue
        metric_queue.clear()
