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

from PyQt5.QtCore import QFile, QFileInfo, QIODevice, QUrl, Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineScript
from PyQt5.QtWebChannel import QWebChannel


class LoggingWebEnginePage(QWebEnginePage):
    """Override console.log message to display messages"""
    def javaScriptConsoleMessage(self, level, msg, line, source):
        try:
            log.log(
                self.levels[int(level)],
                '%s@L%d: %s', os.path.basename(source or ''), line, msg)
        except Exception:
            # Fallback: write directly so exceptions don't silently swallow console output
            log.warning("JS[%s]@L%d: %s", source, line, msg)

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

        # Inject qwebchannel.js via QWebEngineScript (runs at DocumentCreation, before page scripts).
        # This avoids relying on qrc:// URL loading, which can fail in cx_Freeze frozen builds.
        qwc_file = QFile(":/qtwebchannel/qwebchannel.js")
        if qwc_file.open(QIODevice.ReadOnly):
            qwc_content = bytes(qwc_file.readAll()).decode('utf-8')
            qwc_file.close()
            qwc_script = QWebEngineScript()
            qwc_script.setName("qwebchannel.js")
            qwc_script.setSourceCode(qwc_content)
            qwc_script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            qwc_script.setWorldId(QWebEngineScript.MainWorld)
            self.page().scripts().insert(qwc_script)
            log.info("Injected qwebchannel.js via QWebEngineScript")
        else:
            log.warning("Could not inject qwebchannel.js from Qt resources: QFile open failed")

        # Inject mixin_webengine.js via QWebEngineScript so that init_mixin() is defined before
        # app.js runs (which calls init_mixin() inside $(document).ready()).
        # This replaces the <!--MIXIN_JS_INCLUDE--> HTML substitution approach and allows us to
        # load the HTML directly from disk (avoiding setHtml() file:// security restrictions).
        mixin_path = os.path.join(info.PATH, 'timeline', 'js', 'mixin_webengine.js')
        try:
            with open(mixin_path, 'r', encoding='utf-8') as fh:
                mixin_content = fh.read()
            mixin_script = QWebEngineScript()
            mixin_script.setName("mixin_webengine.js")
            mixin_script.setSourceCode(mixin_content)
            mixin_script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            mixin_script.setWorldId(QWebEngineScript.MainWorld)
            self.page().scripts().insert(mixin_script)
            log.info("Injected mixin_webengine.js via QWebEngineScript")
        except Exception as exc:
            log.warning("Could not inject mixin_webengine.js: %s", exc)

        # Register WebChannel BEFORE loading the page so that qt.webChannelTransport is
        # available to JavaScript from the very first document-creation event.
        self.webchannel = QWebChannel(self.page())
        self.page().setWebChannel(self.webchannel)

        # Load the timeline HTML directly from disk (file:// URL).
        # Using load() instead of setHtml() avoids security restrictions that can block
        # external JS/CSS files when the page content is passed as an inline string.
        self.load(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))

        # Connect signals for page lifecycle
        log.info("WebEngine backend initializing")
        self.page().loadStarted.connect(self.setup_js_data)
        self.page().loadFinished.connect(self.on_load_finished)

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

    def on_load_finished(self, ok):
        """Called when the page finishes loading. Logs result and runs a JS diagnostic."""
        log.info("WebEngine loadFinished: ok=%s", ok)
        if ok:
            # Check that key JS globals are available (QWebChannel from injection, qt from webchannel)
            self.page().runJavaScript(
                "JSON.stringify({QWebChannel: typeof QWebChannel, qt: typeof qt, "
                "timeline_var: typeof timeline, jquery: typeof $})",
                lambda r: log.info("WebEngine JS globals: %s", r)
            )

    def keyPressEvent(self, event):
        """ Keypress callback for timeline """
        key_value = event.key()
        if key_value in [Qt.Key_Shift, Qt.Key_Control]:
            # Only pass a few keystrokes to the webview (CTRL and SHIFT)
            return QWebEngineView.keyPressEvent(self, event)
        # Ignore most keypresses
        event.ignore()
