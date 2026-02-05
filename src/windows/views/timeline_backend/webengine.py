"""
 @file
 @brief WebEngine backend for TimelineView
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

import os
import logging
from functools import partial

from classes import info
from classes.logger import log

from PyQt5.QtCore import QFileInfo, QUrl, Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel


class LoggingWebEnginePage(QWebEnginePage):
    """Override console.log message to display messages"""
    def javaScriptConsoleMessage(self, level, msg, line, source):
        log.log(
            self.levels[level],
            '%s@L%d: %s', os.path.basename(source), line, msg)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("LoggingWebEnginePage")
        self.levels = [logging.INFO, logging.WARNING, logging.ERROR]


class TimelineWebEngineView(QWebEngineView):
    """QtWebEngine Timeline Widget"""

    def __init__(self):
        """Initialization code required for widget"""
        super().__init__()
        self.setObjectName("TimelineWebEngineView")

        self.document_is_ready = False
        self.html_path = os.path.join(info.PATH, 'timeline', 'index.html')

        # Connect logging web page (for console.log)
        self.new_page = LoggingWebEnginePage(self)
        self.setPage(self.new_page)

        # Set background color of timeline
        self.page().setBackgroundColor(QColor("#363636"))

        # Delete the webview when closed
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Enable smooth scrolling on timeline
        self.settings().setAttribute(self.settings().ScrollAnimatorEnabled, True)

        # Set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
        self.webchannel = QWebChannel(self.page())
        self.setHtml(self.get_html(), QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))
        self.page().setWebChannel(self.webchannel)

        # Connect signal of javascript initialization to our javascript reference init function
        log.info("WebEngine backend initializing")
        self.page().loadStarted.connect(self.setup_js_data)

    def run_js(self, code, callback=None, retries=0):
        """Run JS code async and optionally have a callback for response"""
        # Check if document.Ready has fired in JS
        if not self.document_is_ready:
            # Not ready, try again in a few moments
            if retries == 0:
                # Log the script contents, the first time
                log.debug(
                    "run_js() called before document ready event. Script queued: %s",
                    code)
            elif retries == 5:
                # Warn once at 5 retries (~1s), then only debug to avoid log spam
                log.warning(
                    "WebEngine backend still not ready after %d retries; further retries logged at debug.",
                    retries)
            elif retries % 10 == 0:
                log.debug("WebEngine backend still not ready after %d retries.", retries)
            else:
                log.debug("Script queued, %d retries so far", retries)
            QTimer.singleShot(200, partial(self.run_js, code, callback, retries + 1))
            return None
        # Execute JS code
        if callback:
            return self.page().runJavaScript(code, callback)
        # else
        return self.page().runJavaScript(code)

    def apply_theme(self, css):
        """Apply additional theme to web-view"""
        single_line_css = css.replace("\n", "")
        self.run_js(f"$('body').scope().setTheme('{single_line_css}');")

    def setup_js_data(self):
        # Export self as a javascript object in webview
        log.info("Registering WebChannel connection with WebEngine")
        self.webchannel.registerObject('timeline', self)

    def get_html(self):
        """Get HTML for Timeline, adjusted for mixin"""
        with open(self.html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return html.replace(
            '<!--MIXIN_JS_INCLUDE-->',
            """
                <script type="text/javascript" src="js/mixin_webengine.js"></script>
            """)

    def keyPressEvent(self, event):
        """ Keypress callback for timeline """
        key_value = event.key()
        if key_value in [Qt.Key_Shift, Qt.Key_Control]:
            # Only pass a few keystrokes to the webview (CTRL and SHIFT)
            return QWebEngineView.keyPressEvent(self, event)
        # Ignore most keypresses
        event.ignore()
