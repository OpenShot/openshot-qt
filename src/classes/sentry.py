"""
 @file
 @brief This file manages the optional Sentry SDK
 @author Jonathan Thomas <jonathan@openshot.org>
 @author FeRD (Frank Dana) <ferdnyc@gmail.com>

 @section LICENSE

 Copyright (c) 2008-2021 OpenShot Studios, LLC
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

import platform
import datetime
from classes.logger import log

from classes import info
from classes.logger import log

try:
    import distro
except ModuleNotFoundError:
    distro = None

try:
    import sentry_sdk as sdk
except ModuleNotFoundError:
    sdk = None

# seconds required between errors
min_error_freq = 1
last_send_time = None
last_event_message = None

def init_tracing():
    """Init all Sentry tracing"""
    if not sdk:
        log.info('No sentry_sdk module detected (error reporting is disabled)')
        return

    # Determine sample rate for errors & transactions
    sample_rate = 0.0
    traces_sample_rate = 0.0
    if info.VERSION == info.ERROR_REPORT_STABLE_VERSION:
        sample_rate = info.ERROR_REPORT_RATE_STABLE
        traces_sample_rate = info.TRANS_REPORT_RATE_STABLE
        environment = "production"
    else:
        sample_rate = info.ERROR_REPORT_RATE_UNSTABLE
        traces_sample_rate = info.TRANS_REPORT_RATE_UNSTABLE
        environment = "unstable"

    if info.ERROR_REPORT_STABLE_VERSION:
        log.info("Sentry initialized for '%s': %s sample rate, %s transaction rate" % (environment,
                                                                                       sample_rate,
                                                                                       traces_sample_rate))

    def before_send(event,hint):
        """
        Function to filter out repetitive Sentry.io errors before sending them
        """
        global last_send_time
        global last_event_message

        # Prevent rapid errors
        current_time = datetime.datetime.now()
        if last_send_time:
            time_since_send = (current_time - last_send_time).total_seconds()
            if time_since_send < min_error_freq:
                log.debug("Report prevented: Recent error reported")
                return None

        # Prevent repeated errors
        event_message = event.\
            get("logentry", {"message": None}).\
            get("message", None)
        if last_event_message and last_event_message == event_message:
            log.debug("Report prevented: Same as last Error")
            return None

        # This error will send. Update the last time and last message
        log.debug("Sending Error")
        last_send_time = current_time
        last_event_message = event_message
        return event

    # Initialize sentry exception tracing
    sdk.init(
        "https://21496af56ab24e94af8ff9771fbc1600@o772439.ingest.sentry.io/5795985",
        sample_rate=sample_rate,
        traces_sample_rate=traces_sample_rate,
        release=f"openshot@{info.VERSION}",
        environment=environment,
        debug=False,
        before_send=before_send
    )
    if _supports_tagging():
        configure_platform_tags(sdk)
    else:
        sdk.configure_scope(platform_scope)


def platform_scope(scope):
    configure_platform_tags(scope)


def configure_platform_tags(sdk_or_scope):
    sdk_or_scope.set_tag("system", platform.system())
    sdk_or_scope.set_tag("machine", platform.machine())
    sdk_or_scope.set_tag("processor", platform.processor())
    sdk_or_scope.set_tag("platform", platform.platform())
    if distro and platform.system() == "linux":
        sdk_or_scope.set_tag("distro", " ".join(distro.linux_distribution()))
    sdk_or_scope.set_tag("locale", info.CURRENT_LANGUAGE)


def disable_tracing():
    """Disable all Sentry tracing requests"""
    if sdk:
        sdk.init()


def set_tag(*args):
    if sdk and _supports_tagging():
        sdk.set_tag(*args)


def set_user(*args):
    if sdk and _supports_tagging():
        sdk.set_user(*args)


def set_context(*args):
    if sdk and _supports_tagging():
        sdk.set_context(*args)


def _supports_tagging():
    """Returns whether the imported sentry-sdk has tag-related
    methods such as set_tag, set_user, set_context.

    Those methods were introduce on 0.13.1 version. Checking this
    before calling those methods on the sentry-sdk avoids crashing
    Openshot in case an old sdk is installed.
    """
    return all([hasattr(sdk, method) for method in ["set_tag", "set_user", "set_context"]])
