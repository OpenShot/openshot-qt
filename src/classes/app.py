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

import os
import sys
import platform
import traceback
from uuid import uuid4
from PyQt5.QtWidgets import QApplication, QStyleFactory, QMessageBox
from PyQt5.QtGui import QPalette, QColor, QFontDatabase, QFont
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QT_VERSION_STR
from PyQt5.QtCore import PYQT_VERSION_STR

try:
    # Enable High-DPI resolutions
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
except AttributeError:
    pass # Quietly fail for older Qt5 versions


def get_app():
    """ Returns the current QApplication instance of OpenShot """
    return QApplication.instance()


class OpenShotApp(QApplication):
    """ This class is the primary QApplication for OpenShot.
            mode=None (normal), mode=unittest (testing)"""

    def __init__(self, *args, mode=None):
        QApplication.__init__(self, *args)

        try:
            # Import modules
            from classes import info
            from classes.logger import log, reroute_output
            from classes import settings, project_data, updates, language, ui_util, logger_libopenshot
            import openshot

            # Re-route stdout and stderr to logger
            reroute_output()
        except (ImportError, ModuleNotFoundError) as ex:
            tb = traceback.format_exc()
            QMessageBox.warning(None, "Import Error",
                                "Module: %(name)s\n\n%(tb)s" % {"name": ex.name, "tb": tb})
            # Stop launching and exit
            raise
            sys.exit()
        except Exception:
            raise
            sys.exit()

        # Log some basic system info
        try:
            log.info("------------------------------------------------")
            log.info("   OpenShot (version %s)" % info.SETUP['version'])
            log.info("------------------------------------------------")

            v = openshot.GetVersion()
            log.info("openshot-qt version: %s" % info.VERSION)
            log.info("libopenshot version: %s" % v.ToString())
            log.info("platform: %s" % platform.platform())
            log.info("processor: %s" % platform.processor())
            log.info("machine: %s" % platform.machine())
            log.info("python version: %s" % platform.python_version())
            log.info("qt5 version: %s" % QT_VERSION_STR)
            log.info("pyqt5 version: %s" % PYQT_VERSION_STR)
        except:
            pass

        # Setup application
        self.setApplicationName('openshot')
        self.setApplicationVersion(info.SETUP['version'])

        # Init settings
        self.settings = settings.SettingStore()
        self.settings.load()

        # Init and attach exception handler
        from classes import exceptions
        sys.excepthook = exceptions.ExceptionHandler

        # Init translation system
        language.init_language()

        # Detect minimum libopenshot version
        _ = self._tr
        libopenshot_version = openshot.GetVersion().ToString()
        if mode != "unittest" and libopenshot_version < info.MINIMUM_LIBOPENSHOT_VERSION:
            QMessageBox.warning(None, _("Wrong Version of libopenshot Detected"),
                                      _("<b>Version %(minimum_version)s is required</b>, but %(current_version)s was detected. Please update libopenshot or download our latest installer.") %
                                {"minimum_version": info.MINIMUM_LIBOPENSHOT_VERSION, "current_version": libopenshot_version})
            # Stop launching and exit
            sys.exit()

        # Tests of project data loading/saving
        self.project = project_data.ProjectDataStore()

        # Init Update Manager
        self.updates = updates.UpdateManager()

        # It is important that the project is the first listener if the key gets update
        self.updates.add_listener(self.project)

        # Load ui theme if not set by OS
        ui_util.load_theme()

        # Test for permission issues (and display message if needed)
        try:
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
            log.error('Failed to create PERMISSION/test.osp file (likely permissions error): %s' % TEST_PATH_FILE)
            QMessageBox.warning(None, _("Permission Error"),
                                      _("%(error)s. Please delete <b>%(path)s</b> and launch OpenShot again." % {"error": str(ex), "path": info.USER_PATH}))
            # Stop launching and exit
            raise
            sys.exit()

        # Start libopenshot logging thread
        self.logger_libopenshot = logger_libopenshot.LoggerLibOpenShot()
        self.logger_libopenshot.start()

        # Track which dockable window received a context menu
        self.context_menu_object = None

        # Set Font for any theme
        if self.settings.get("theme") != "No Theme":
            # Load embedded font
            try:
                log.info("Setting font to %s" % os.path.join(info.IMAGES_PATH, "fonts", "Ubuntu-R.ttf"))
                font_id = QFontDatabase.addApplicationFont(os.path.join(info.IMAGES_PATH, "fonts", "Ubuntu-R.ttf"))
                font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
                font = QFont(font_family)
                font.setPointSizeF(10.5)
                QApplication.setFont(font)
            except Exception as ex:
                log.error("Error setting Ubuntu-R.ttf QFont: %s" % str(ex))

        # Set Experimental Dark Theme
        if self.settings.get("theme") == "Humanity: Dark":
            # Only set if dark theme selected
            log.info("Setting custom dark theme")
            self.setStyle(QStyleFactory.create("Fusion"))

            darkPalette = self.palette()
            darkPalette.setColor(QPalette.Window, QColor(53, 53, 53))
            darkPalette.setColor(QPalette.WindowText, Qt.white)
            darkPalette.setColor(QPalette.Base, QColor(25, 25, 25))
            darkPalette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            darkPalette.setColor(QPalette.ToolTipBase, Qt.white)
            darkPalette.setColor(QPalette.ToolTipText, Qt.white)
            darkPalette.setColor(QPalette.Text, Qt.white)
            darkPalette.setColor(QPalette.Button, QColor(53, 53, 53))
            darkPalette.setColor(QPalette.ButtonText, Qt.white)
            darkPalette.setColor(QPalette.BrightText, Qt.red)
            darkPalette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            darkPalette.setColor(QPalette.HighlightedText, Qt.black)
            darkPalette.setColor(QPalette.Disabled, QPalette.Text, QColor(104, 104, 104))
            self.setPalette(darkPalette)
            self.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 0px solid white; }")

        # Create main window
        from windows.main_window import MainWindow
        self.window = MainWindow(mode)

        # Reset undo/redo history
        self.updates.reset()
        self.window.updateStatusChanged(False, False)

        log.info('Process command-line arguments: %s' % args)
        if len(args[0]) == 2:
            path = args[0][1]
            if ".osp" in path:
                # Auto load project passed as argument
                self.window.OpenProjectSignal.emit(path)
            else:
                # Auto import media file
                self.window.filesTreeView.add_file(path)
        else:
            # Recover backup file (this can't happen until after the Main Window has completely loaded)
            self.window.RecoverBackup.emit()

    def _tr(self, message):
        return self.translate("", message)

    # Start event loop
    def run(self):
        """ Start the primary Qt event loop for the interface """

        res = self.exec_()

        try:
            from classes.logger import log
            self.settings.save()
        except Exception as ex:
            log.error("Couldn't save user settings on exit.\n{}".format(ex))

        # return exit result
        return res
