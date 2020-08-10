"""
 @file
 @brief This file allows for switching between QtWebEngine and QtWebKit
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

import os
from classes import info
from PyQt5.QtCore import QFileInfo, pyqtSlot, QUrl, Qt, QCoreApplication, QTimer
from PyQt5.QtGui import QCursor, QKeySequence, QColor
from PyQt5.QtWidgets import QMenu
from classes.logger import log
from functools import partial


try:
    # Attempt to import QtWebEngine
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    IS_WEBENGINE_VALID = True
except ImportError:
    QWebEngineView = object # Prevent inheritance errors
    IS_WEBENGINE_VALID = False

try:
    # Attempt to import QtWebKit
    from PyQt5.QtWebKitWidgets import QWebView
    IS_WEBKIT_VALID = True
except ImportError:
    QWebView = object # Prevent inheritance errors
    IS_WEBKIT_VALID = False


class TimelineBaseMixin(object):
    """OpenShot Timeline Base Mixin Class"""
    def __init__(self):
        """Initialization code required for parent widget"""
        self.document_is_ready = False
        self.html_path = html_path = os.path.join(info.PATH, 'timeline', 'index.html')

    def run_js(self, code, callback=None, retries=0):
        """Run javascript code snippet"""
        raise Exception("run_js not implemented")


class TimelineQtWebEngineMixin(TimelineBaseMixin, QWebEngineView):
    """QtWebEngine Timeline Widget"""

    def __init__(self):
        """Initialization code required for widget"""
        TimelineBaseMixin.__init__(self)
        QWebEngineView.__init__(self)

        # Set background color of timeline
        self.page().setBackgroundColor(QColor("#363636"))

        # Delete the webview when closed
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Enable smooth scrolling on timeline
        self.settings().setAttribute(self.settings().ScrollAnimatorEnabled, True)

        # Set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
        self.webchannel = QWebChannel(self.page())
        self.setUrl(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))
        self.page().setWebChannel(self.webchannel)

        # Connect signal of javascript initialization to our javascript reference init function
        self.page().loadStarted.connect(self.setup_js_data)

    def run_js(self, code, callback=None, retries=0):
        '''Run JS code async and optionally have a callback for response'''
        # Check if document.Ready has fired in JS
        if not self.document_is_ready:
            # Not ready, try again in a few moments
            if retries == 0:
                # Log the script contents, the first time
                log.debug("run_js() called before document ready event. Script queued: %s" % code)
            elif retries % 5 == 0:
                log.warning("WebEngine backend still not ready after {} retries.".format(retries))
            else:
                log.debug("Script queued, {} retries so far".format(retries))
            QTimer.singleShot(200, partial(self.run_js, code, callback, retries + 1))
            return None
        else:
            # Execute JS code
            if callback:
                return self.page().runJavaScript(code, callback)
            else:
                return self.page().runJavaScript(code)

    def setup_js_data(self):
        # Export self as a javascript object in webview
        self.webchannel.registerObject('timeline', self)


class TimelineQtWebKitMixin(TimelineBaseMixin, QWebView):
    """QtWebKit Timeline Widget"""

    def __init__(self):
        """Initialization code required for widget"""
        TimelineBaseMixin.__init__(self)
        QWebView.__init__(self)

        # Delete the webview when closed
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Disable image caching on timeline
        self.settings().setObjectCacheCapacities(0, 0, 0)

        # Set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
        self.setUrl(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))

        # Connect signal of javascript initialization to our javascript reference init function
        self.page().mainFrame().javaScriptWindowObjectCleared.connect(self.setup_js_data)

    def run_js(self, code, callback=None, retries=0):
        '''Run JS code async and optionally have a callback for response'''
        # Check if document.Ready has fired in JS
        if not self.document_is_ready:
            # Not ready, try again in a few moments
            if retries == 0:
                # Log the script contents, the first time
                log.debug("run_js() called before document ready event. Script queued: %s" % code)
            elif retries % 5 == 0:
                log.warning("WebKit backend still not ready after {} retries.".format(retries))
            else:
                log.debug("Script queued, {} retries so far".format(retries))
            QTimer.singleShot(200, partial(self.run_js, code, callback, retries + 1))
            return None
        else:
            # Execute JS code
            if callback:
                return self.page().mainFrame().evaluateJavaScript(code, callback)
            else:
                return self.page().mainFrame().evaluateJavaScript(code)

    def setup_js_data(self):
        # Export self as a javascript object in webview
        self.page().mainFrame().addToJavaScriptWindowObject('timeline', self)
        self.page().mainFrame().addToJavaScriptWindowObject('mainWindow', self.window)


# Set correct Mixin (with QtWebEngine preference)
if IS_WEBENGINE_VALID:
    TimelineMixin = TimelineQtWebEngineMixin
elif IS_WEBKIT_VALID:
    TimelineMixin = TimelineQtWebKitMixin
else:
    TimelineMixin = None
