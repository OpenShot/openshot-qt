""" 
 @file
 @brief This file creates the QApplication, and displays the main window
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author olivier Girard <eolinwen@gmail.com>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtGui import QPalette, QColor, QFontDatabase, QFont
from PyQt5.QtCore import Qt

from classes.logger import log
from classes import info, settings, project_data, updates, language, ui_util


def get_app():
    """ Returns the current QApplication instance of OpenShot """
    return QApplication.instance()


class OpenShotApp(QApplication):
    """ This class is the primary QApplication for OpenShot """

    def __init__(self, *args):
        QApplication.__init__(self, *args)

        # Setup appication
        self.setApplicationName('openshot')
        self.setApplicationVersion(info.SETUP['version'])

        # Init settings
        self.settings = settings.SettingStore()
        try:
            self.settings.load()
        except Exception as ex:
            log.error("Couldn't load user settings. Exiting.\n{}".format(ex))
            exit()

        # Init translation system
        language.init_language()

        # Tests of project data loading/saving
        self.project = project_data.ProjectDataStore()

        # Init Update Manager
        self.updates = updates.UpdateManager()

        # It is important that the project is the first listener if the key gets update
        self.updates.add_listener(self.project)

        # Load ui theme if not set by OS
        ui_util.load_theme()

        # Track which dockable window received a context menu
        self.context_menu_object = None

        # Set Font for any theme
        if self.settings.get("theme") != "No Theme":
            # Load embedded font
            log.info("Setting font to %s" % os.path.join(info.IMAGES_PATH, "fonts", "Ubuntu-R.ttf"))
            font_id = QFontDatabase.addApplicationFont(os.path.join(info.IMAGES_PATH, "fonts", "Ubuntu-R.ttf"))
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            font = QFont(font_family)
            font.setPointSizeF(10.5)
            QApplication.setFont(font)

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
            self.setPalette(darkPalette)
            self.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 0px solid white; }")

        # Create main window
        from windows.main_window import MainWindow
        self.window = MainWindow()
        self.window.show()

        # Load new/blank project (which sets default profile)
        self.project.load("")

        log.info('Process command-line arguments: %s' % args)
        if len(args[0]) == 2:
            path = args[0][1]
            if ".osp" in path:
                # Auto load project passed as argument
                self.window.open_project(path)
            else:
                # Auto import media file
                self.window.filesTreeView.add_file(path)

        # Reset undo/redo history
        self.updates.reset()
        self.window.updateStatusChanged(False, False)

    def _tr(self, message):
        return self.translate("", message)

    # Start event loop
    def run(self):
        """ Start the primary Qt event loop for the interface """

        res = self.exec_()

        try:
            self.settings.save()
        except Exception as ex:
            log.error("Couldn't save user settings on exit.\n{}".format(ex))

        # return exit result
        return res
