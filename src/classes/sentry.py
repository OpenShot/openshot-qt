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

from classes import info

try:
    import distro
except ModuleNotFoundError:
    distro = None

try:
    import sentry_sdk as sdk
except ModuleNotFoundError:
    sdk = None

error_history = []
min_error_delay = 0.2 * 10**6 # 0.2 sec in microseconds
recent_error_length = 5 # compare new errors to this many previous errors.
def init_tracing():
    """Init all Sentry tracing"""
    if not sdk:
        return

    # Determine sample rate for exceptions
    default_sample_rate = 0.0
    if info.VERSION == info.ERROR_REPORT_STABLE_VERSION:
        default_sample_rate = info.ERROR_REPORT_RATE_STABLE
        environment = "production"
    else:
        default_sample_rate = info.ERROR_REPORT_RATE_UNSTABLE
        environment = "unstable"

    if info.ERROR_REPORT_STABLE_VERSION:
        print("Sentry initialized with %s error reporting rate (%s)" % (default_sample_rate, environment))

    def error_filtering(sampling_context):
        print('Filter method running!')
        name = sampling_context.get("transaction_context").get("name")
        current_time = datetime.datetime.now()
        if len(error_history) != 1:
            # Time since last error
            delta = current_time - self.last_error_time
            deltaMicroSec = (delta.seconds * 10**6) + delta.microseconds
            if deltaMicroSec < min_error_delay:
                print("Reject: too soon")
                # Too soon after last error. Don't send
                return 0.0
            if name == self.last_error_name:
                print("Reject: same name")
                # This error was just reported. don't report.
                return 0.0
        self.last_error_name = name
        self.last_error_time = current_time
        # return a chance of sending error
        return 1.0 # REMOVE BEFORE MERGE. Decrease to something reasonable.

    # Initialize sentry exception tracing
    sdk.init(
        "https://21496af56ab24e94af8ff9771fbc1600@o772439.ingest.sentry.io/5795985",
        traces_sampler=error_filtering,
        release=f"openshot@{info.VERSION}",
        environment=environment
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
