"""
 @file
 @brief Dummy backend for TimelineWebView
 @author Jonathan Thomas <jonathan@openshot.org>
 @author FeRD (Frank Dana) <ferdnyc@gmail.com>

 @section LICENSE

 Copyright (c) 2008-2020 OpenShot Studios, LLC
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

from classes.logger import log

from PyQt5.QtWidgets import QWidget


class DummyWebView(QWidget):
    """A QWidget-derived class which provides the methods necessary for
    TimelineWebView to function, but does not display anything. Intended
    primarily for unit test runs and other simulated environments."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run_js(self, code, callback=None):
        log.debug("run_js request received: %s", code)
        if callback:
            callback("{}")
        else:
            return None
