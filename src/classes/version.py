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

import threading
from classes.app import get_app
from classes import http_client, info, release_details
from classes.logger import log


def get_current_Version():
    """Get the current version """
    t = threading.Thread(target=get_version_from_http, daemon=True)
    t.start()

def get_version_from_http():
    """Get the current version # from openshot.org"""

    url = "https://www.openshot.org/version/json/"
    info.ERROR_REPORT_IS_RELEASE = False

    try:
        version_info = http_client.get_json(
            http_client.urls_with_http_fallback(url),
            "OpenShot version info",
            headers={"user-agent": "openshot-qt-%s" % info.VERSION},
        )
        log.info("Found current version: %s" % version_info)

        # Parse version
        openshot_version = version_info.get("openshot_version")
        info.ERROR_REPORT_STABLE_VERSION = version_info.get("openshot_version")
        info.ERROR_REPORT_RATE_STABLE = version_info.get("error_rate_stable")
        info.ERROR_REPORT_RATE_UNSTABLE = version_info.get("error_rate_unstable")
        info.TRANS_REPORT_RATE_STABLE = version_info.get("trans_rate_stable")
        info.TRANS_REPORT_RATE_UNSTABLE = version_info.get("trans_rate_unstable")

        # Use the same commit check as About, even when daily and release
        # builds share a version. Complete this before initializing Sentry.
        info.ERROR_REPORT_IS_RELEASE = release_details.is_release_build(
            release_details.get_build_details(),
            release_details.get_release_details(info.VERSION),
        )

        # Emit signal for the UI
        get_app().window.FoundVersionSignal.emit(openshot_version)

    except Exception:
        log.warning("Failed to get OpenShot version info", exc_info=True)
