"""
 @file
 @brief This file contains PyQt help functions, to translate the interface, load icons, and connect signals
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>

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
import time

# Try to get the security-patched XML functions from defusedxml
try:
    from defusedxml import ElementTree
except ImportError:
    from xml.etree import ElementTree

from PyQt5.QtCore import Qt, QDir, QLocale
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTabWidget, QAction)
from PyQt5 import uic

from classes.app import get_app
from classes.logger import log

from . import openshot_rc  # noqa

DEFAULT_THEME_NAME = "Humanity"


def load_icon_theme():
    """ Load the current OS theme, or fallback to a default one """

    s = get_app().get_settings()

    # If theme not reported by OS
    if QIcon.themeName() == '' and s.get("theme") != "No Theme":

        # Address known Ubuntu bug of not reporting configured theme name, use default ubuntu theme
        if os.getenv('DESKTOP_SESSION') == 'ubuntu':
            QIcon.setThemeName('unity-icon-theme')

        # Windows/Mac use packaged theme
        else:
            QIcon.setThemeName(DEFAULT_THEME_NAME)


def load_ui(window, path):
    """ Load a Qt *.ui file, and also load an XML parsed version """
    # Attempt to load the UI file 5 times
    # This is a hack, and I'm trying to avoid a really common error which might be a
    # race condition. [zipimport.ZipImportError: can't decompress data; zlib not available]
    # This error only happens when cx_Freeze is used, and the app is launched.
    error = None
    for attempt in range(1, 6):
        try:
            # Load ui from configured path
            uic.loadUi(path, window)

            # Successfully loaded UI file, so clear any previously encountered errors
            error = None
            break

        except Exception as ex:
            # Keep track of this error
            error = ex
            time.sleep(0.1)

    # Raise error (if any)
    if error:
        raise error

    # Save xml tree for ui
    window.uiTree = ElementTree.parse(path)


def get_default_icon(theme_name):
    """ Get a QIcon, and fallback to default theme if OS does not support themes. """

    # Default path to backup icons
    start_path = ":/icons/" + DEFAULT_THEME_NAME + "/"
    icon_path = search_dir(start_path, theme_name)
    return QIcon(icon_path), icon_path


def make_dark_palette(darkPalette: QPalette) -> QPalette:
    darkPalette.setColor(QPalette.Window, QColor(53, 53, 53))
    darkPalette.setColor(QPalette.WindowText, Qt.white)
    darkPalette.setColor(QPalette.Base, QColor(25, 25, 25))
    darkPalette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    darkPalette.setColor(QPalette.Light, QColor(68, 68, 68))
    darkPalette.setColor(QPalette.Text, Qt.white)
    darkPalette.setColor(QPalette.Button, QColor(53, 53, 53))
    darkPalette.setColor(QPalette.ButtonText, Qt.white)
    darkPalette.setColor(QPalette.Highlight, QColor(42, 130, 218, 192))
    darkPalette.setColor(QPalette.HighlightedText, Qt.black)
    #
    # Disabled palette
    #
    darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(255, 255, 255, 128))
    darkPalette.setColor(QPalette.Disabled, QPalette.Base, QColor(68, 68, 68))
    darkPalette.setColor(QPalette.Disabled, QPalette.Text, QColor(255, 255, 255, 128))
    darkPalette.setColor(QPalette.Disabled, QPalette.Button, QColor(53, 53, 53, 128))
    darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(255, 255, 255, 128))
    darkPalette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(151, 151, 151, 192))
    darkPalette.setColor(QPalette.Disabled, QPalette.HighlightedText, Qt.black)

    # Tooltips
    darkPalette.setColor(QPalette.ToolTipBase, QColor(42, 130, 218))
    darkPalette.setColor(QPalette.ToolTipText, Qt.white)
    # Links
    darkPalette.setColor(QPalette.Link, QColor(85, 170, 255))
    darkPalette.setColor(QPalette.LinkVisited, QColor(136, 85, 255))

    return darkPalette


def search_dir(base_path, theme_name):
    """ Search for theme name """

    # Search each entry in this directory
    base_dir = QDir(base_path)
    for e in base_dir.entryList():
        # Path to current item
        path = base_dir.path() + "/" + e
        base_filename = e.split('.')[0]

        # If file matches theme name, return
        if base_filename == theme_name:
            return path

        # If this is a directory, search within it
        dir = QDir(path)
        if dir.exists():
            # If found below, return it
            res = search_dir(path, theme_name)
            if res:
                return res

    # If no match found in dir, return None
    return None


def get_icon(theme_name):
    """Get either the current theme icon or fallback to default theme (for custom icons). Returns None if none
    found or empty name."""

    if theme_name:
        has_icon = QIcon.hasThemeIcon(theme_name)
        fallback_icon, fallback_path = get_default_icon(theme_name)
        if has_icon or fallback_icon:
            return QIcon.fromTheme(theme_name, fallback_icon)
    return None


def setup_icon(window, elem, name, theme_name=None):
    """Using the window xml, set the icon on the given element,
    or if theme_name passed load that icon."""

    type_filter = 'action'
    if isinstance(elem, QWidget):  # Search for widget with name instead
        type_filter = 'widget'
    # Find iconset in tree (if any)
    iconset = window.uiTree.find(
        './/' + type_filter + '[@name="' + name
        + '"]/property[@name="icon"]/iconset'
        )
    # For some reason "if iconset:" doesn't work the same
    if iconset is not None or theme_name:
        if not theme_name:
            theme_name = iconset.get('theme', '')
        # Get Icon (either current theme or fallback)
        icon = get_icon(theme_name)
        if icon:
            elem.setIcon(icon)


def init_element(window, elem):
    """ Initialize language and icons of the given element """

    _translate = QApplication.instance().translate

    name = ''
    if hasattr(elem, 'objectName'):
        name = elem.objectName()
        connect_auto_events(window, elem, name)

    # Handle generic translatable properties
    if (
            hasattr(elem, 'setText')
            and hasattr(elem, 'text')
            and elem.text() != ""
            ):
        elem.setText(_translate("", elem.text()))
    if hasattr(elem, 'setToolTip') and hasattr(elem, 'toolTip') and elem.toolTip() != "":
        elem.setToolTip(_translate("", elem.toolTip()))
    if (
            hasattr(elem, 'setWindowTitle')
            and hasattr(elem, 'windowTitle')
            and elem.windowTitle() != ""
            ):
        elem.setWindowTitle(_translate("", elem.windowTitle()))
    if (
            hasattr(elem, 'setTitle')
            and hasattr(elem, 'title')
            and elem.title() != ""
            ):
        elem.setTitle(_translate("", elem.title()))
    if (
            hasattr(elem, 'setPlaceholderText')
            and hasattr(elem, 'placeholderText')
            and elem.placeholderText() != ""
            ):
        elem.setPlaceholderText(_translate("", elem.placeholderText()))
    if hasattr(elem, 'setLocale'):
        elem.setLocale(QLocale().system())
    # Handle tabs differently
    if isinstance(elem, QTabWidget):
        for i in range(elem.count()):
            elem.setTabText(i, _translate("", elem.tabText(i)))
            elem.setTabToolTip(i, _translate("", elem.tabToolTip(i)))
    # Set icon if possible
    if hasattr(elem, 'setIcon') and name != '':  # Has ability to set its icon
        setup_icon(window, elem, name)


def connect_auto_events(window, elem, name):
    """ Connect any events in a *.ui file with matching Python method names """

    # If trigger slot available check it
    if hasattr(elem, 'trigger'):
        func_name = name + "_trigger"
        if hasattr(window, func_name) and callable(getattr(window, func_name)):
            # Disconnect existing connections safely
            try:
                while True:
                    elem.triggered.disconnect()
            except TypeError:
                pass  # No more connections to disconnect
            # Connect the signal to the slot
            elem.triggered.connect(getattr(window, func_name))

    # Similar approach for clicked signal
    if hasattr(elem, 'click'):
        func_name = name + "_click"
        if hasattr(window, func_name) and callable(getattr(window, func_name)):
            # Disconnect existing connections safely
            try:
                while True:
                    elem.clicked.disconnect()
            except TypeError:
                pass  # No more connections to disconnect
            # Connect the signal to the slot
            elem.clicked.connect(getattr(window, func_name))


def init_ui(window):
    """ Initialize all child widgets and action of a window or dialog """
    log.info('Initializing UI for {}'.format(window.objectName()))

    try:
        # Set locale & window title on the window object
        if hasattr(window, 'setWindowTitle') and window.windowTitle() != "":
            _translate = QApplication.instance().translate
            window.setWindowTitle(_translate("", window.windowTitle()))

            # Center window
            center(window)

        # Loop through all widgets
        for widget in window.findChildren(QWidget):
            init_element(window, widget)

        # Loop through all actions
        for action in window.findChildren(QAction):
            init_element(window, action)
            window.addAction(action)
    except Exception:
        log.info(
            'Failed to initialize an element on %s', window.objectName())


def center(window):
    """Center a window on the main window"""
    frameGm = window.frameGeometry()
    centerPoint = get_app().window.frameGeometry().center()
    frameGm.moveCenter(centerPoint)
    window.move(frameGm.topLeft())


def transfer_children(from_widget, to_widget):
    log.info(
        "Transferring children from '%s' to '%s'",
        from_widget.objectName(), to_widget.objectName())

