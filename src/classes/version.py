"""
 @file
 @brief This file get the current version of openshot from the openshot.org website
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

import requests
import threading
from classes.app import get_app
from classes import info
from classes.logger import log
import json

def get_current_Version():
    """Get the current version """
    t = threading.Thread(target=get_version_from_http)
    t.start()

def get_version_from_http():
    """Get the current version # from openshot.org"""

    url = "http://www.openshot.org/version/json/"

    # Send metric HTTP data
    try:
        r = requests.get(url, headers={"user-agent": "openshot-qt-%s" % info.VERSION}, verify=False)
        log.info("Found current version: %s" % r.text)

        # Parse version
        openshot_version = r.json()["openshot_version"]

        # Emit signal for the UI
        get_app().window.FoundVersionSignal.emit(openshot_version)

    except Exception as Ex:
        log.error("Failed to get version from: %s" % url)
