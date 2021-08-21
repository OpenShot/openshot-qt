"""
 @file
 @brief This file creates the QApplication, and displays the main window
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author olivier Girard <eolinwen@gmail.com>

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

import atexit
import sys
import os
import platform
import traceback
import json

from PyQt5.QtCore import PYQT_VERSION_STR
from PyQt5.QtCore import QT_VERSION_STR
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QApplication, QStyleFactory, QMessageBox


def get_app():
    """ Get the current QApplication instance of OpenShot """
    return QApplication.instance()


def get_settings():
    """Get a reference to the app's settings object"""
    return get_app().get_settings()


class StartupError:
    """ Store and later display an error encountered during setup"""
    levels = {
        "warning": QMessageBox.warning,
        "error": QMessageBox.critical,
    }

    def __init__(self, title="", message="", level="warning"):
        """Create an error message object, populated with details"""
        self.title = title
        self.message = message
        self.level = level

    def show(self):
        """Display the stored error message"""
        box_call = self.levels[self.level]
        box_call(None, self.title, self.message)
        if self.level == "error":
            sys.exit()


class OpenShotApp(QApplication):
    """ This class is the primary QApplication for OpenShot.
            mode=None (normal), mode=unittest (testing)"""

    def __init__(self, *args, mode=None):
        QApplication.__init__(self, *args)
        self.mode = mode or "normal"
        self.args = super().arguments()
        self.errors = []

        try:
            # Import modules
            from classes import info, sentry
            from classes.logger import log, reroute_output

            # Log the session's start
            if mode != "unittest":
                import time
                log.info("-" * 48)
                log.info(time.asctime().center(48))
                log.info('Starting new session'.center(48))

            log.debug("Starting up in {} mode".format(self.mode))
            log.debug("Command line: {}".format(self.args))

            from classes import settings, project_data, updates
            import openshot

            # Re-route stdout and stderr to logger
            if mode != "unittest":
                reroute_output()

        except ImportError as ex:
            tb = traceback.format_exc()
            log.error('OpenShotApp::Import Error', exc_info=1)
            self.errors.append(StartupError(
                "Import Error",
                "Module: %(name)s\n\n%(tb)s" % {"name": ex.name, "tb": tb},
                level="error"))
            # Stop launching
            raise
        except Exception:
            log.error('OpenShotApp::Init Error', exc_info=1)
            sys.exit()

        self.info = info

        # Log some basic system info
        self.log = log
        self.show_environment(info, openshot)
        if self.mode != "unittest":
            self.check_libopenshot_version(info, openshot)

        # Init data objects
        self.settings = settings.SettingStore(parent=self)
        self.settings.load()
        self.project = project_data.ProjectDataStore()
        self.updates = updates.UpdateManager()
        # It is important that the project is the first listener if the key gets update
        self.updates.add_listener(self.project)
        self.updates.reset()

        # Set location of OpenShot program (for libopenshot)
        openshot.Settings.Instance().PATH_OPENSHOT_INSTALL = info.PATH

        # Check to disable sentry
        if not self.settings.get('send_metrics'):
            sentry.disable_tracing()

    def show_environment(self, info, openshot):
        log = self.log
        try:
            log.info("-" * 48)
            log.info(("OpenShot (version %s)" % info.SETUP['version']).center(48))
            log.info("-" * 48)

            log.info("openshot-qt version: %s" % info.VERSION)
            log.info("libopenshot version: %s" % openshot.OPENSHOT_VERSION_FULL)
            log.info("platform: %s" % platform.platform())
            log.info("processor: %s" % platform.processor())
            log.info("machine: %s" % platform.machine())
            log.info("python version: %s" % platform.python_version())
            log.info("qt5 version: %s" % QT_VERSION_STR)
            log.info("pyqt5 version: %s" % PYQT_VERSION_STR)

            # Look for frozen version info
            version_path = os.path.join(info.PATH, "settings", "version.json")
            if os.path.exists(version_path):
                with open(version_path, "r", encoding="UTF-8") as f:
                    version_info = json.loads(f.read())
                    log.info("Frozen version info from build server:\n%s" %
                             json.dumps(version_info, indent=4, sort_keys=True))

        except Exception:
            log.debug("Error displaying dependency/system details", exc_info=1)

    def check_libopenshot_version(self, info, openshot):
        """Detect minimum libopenshot version"""
        _ = self._tr
        ver = openshot.OPENSHOT_VERSION_FULL
        min_ver = info.MINIMUM_LIBOPENSHOT_VERSION
        if ver >= min_ver:
            return True

        self.errors.append(StartupError(
            _("Wrong Version of libopenshot Detected"),
            _("<b>Version %(minimum_version)s is required</b>, "
              "but %(current_version)s was detected. "
              "Please update libopenshot or download our latest installer.") % {
                "minimum_version": min_ver,
                "current_version": ver,
                },
            level="error",
        ))

    def gui(self):
        from classes import language, sentry, ui_util, logger_libopenshot
        from PyQt5.QtGui import QFont, QFontDatabase as QFD

        _ = self._tr
        info = self.info
        log = self.log

        # Init translation system
        language.init_language()
        sentry.set_tag("locale", info.CURRENT_LANGUAGE)

        # Load ui theme if not set by OS
        ui_util.load_theme()

        # Test for permission issues (and display message if needed)
        try:
            log.debug("Testing write access to user directory")
            # Create test paths
            TEST_PATH_DIR = os.path.join(info.USER_PATH, 'PERMISSION')
            TEST_PATH_FILE = os.path.join(TEST_PATH_DIR, 'test.osp')
            os.makedirs(TEST_PATH_DIR, exist_ok=True)
            with open(TEST_PATH_FILE, 'w') as f:
                f.write('{}')
                f.flush()
            # Delete test paths
            os.unlink(TEST_PATH_FILE)
            os.rmdir(TEST_PATH_DIR)
        except PermissionError as ex:
            log.error('Failed to create file %s', TEST_PATH_FILE, exc_info=1)
            self.errors.append(StartupError(
                _("Permission Error"),
                _("%(error)s. Please delete <b>%(path)s</b> and launch OpenShot again.") % {
                    "error": str(ex),
                    "path": info.USER_PATH,
                    },
                level="error",
            ))

        # Display any outstanding startup messages
        self.show_errors()

        # Start libopenshot logging thread
        self.logger_libopenshot = logger_libopenshot.LoggerLibOpenShot()
        self.logger_libopenshot.start()

        # Track which dockable window received a context menu
        self.context_menu_object = None

        # Set Font for any theme
        log.debug("Loading UI theme")
        if self.settings.get("theme") != "No Theme":
            # Load embedded font
            font_path = os.path.join(info.IMAGES_PATH, "fonts", "Ubuntu-R.ttf")
            if os.path.exists(font_path):
                log.info("Setting font to %s", font_path)
                try:
                    font_id = QFD.addApplicationFont(font_path)
                    font_family = QFD.applicationFontFamilies(font_id)[0]
                    font = QFont(font_family)
                    font.setPointSizeF(10.5)
                    QApplication.setFont(font)
                except Exception:
                    log.warning("Error setting Ubuntu-R.ttf QFont", exc_info=1)

        # Set Dark Theme, if selected
        if self.settings.get("theme") == "Humanity: Dark":
            log.info("Setting custom dark theme")
            self.setStyle(QStyleFactory.create("Fusion"))
            darkPalette = ui_util.make_dark_palette(self.palette())
            self.setPalette(darkPalette)
            self.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 0px solid white; }")

        # Create main window
        from windows.main_window import MainWindow
        log.debug("Creating main interface window")
        self.window = MainWindow(mode=self.mode)

        # Clear undo/redo history
        self.window.updateStatusChanged(False, False)

        # Connect our exit signals
        self.aboutToQuit.connect(self.cleanup)

        args = self.args
        if len(args) < 2:
            # Recover backup file (this can't happen until after the Main Window has completely loaded)
            self.window.RecoverBackup.emit()
            return

        log.info('Process command-line arguments: %s' % args)

        # Auto load project if passed as argument
        if args[1].endswith(".osp"):
            self.window.OpenProjectSignal.emit(args[1])
            return

        # Start a new project and auto import any media files
        self.project.load("")
        for arg in args[1:]:
            self.window.filesView.add_file(arg)

    def settings_load_error(self, filepath=None):
        """Use QMessageBox to warn the user of a settings load issue"""
        _ = self._tr
        self.errors.append(StartupError(
            _("Settings Error"),
            _("Error loading settings file: %(file_path)s. Settings will be reset.") % {
                "file_path": filepath
                },
            level="warning",
        ))

    def get_settings(self):
        if not hasattr(self, "settings"):
            return None
        return self.settings

    def show_errors(self):
        count = len(self.errors)
        if count > 0:
            self.log.warning("Displaying %d startup messages", count)
        while self.errors:
            error = self.errors.pop(0)
            error.show()

    def _tr(self, message):
        return self.translate("", message)

    @pyqtSlot()
    def cleanup(self):
        """aboutToQuit signal handler for application exit"""
        self.log.debug("Saving settings in app.cleanup")
        try:
            self.settings.save()
        except Exception:
            self.log.error("Couldn't save user settings on exit.", exc_info=1)


@atexit.register
def onLogTheEnd():
    """ Log when the primary Qt event loop ends """
    try:
        from classes.logger import log
        import time
        log.info("OpenShot's session ended".center(48))
        log.info(time.asctime().center(48))
        log.info("=" * 48)
    except Exception:
        import logging
        log = logging.getLogger(".")
        log.debug('Failed to write session ended log', exc_info=1)
