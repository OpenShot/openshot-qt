"""
 @file
 @brief This file creates the Curve Editor dock window to view and edit animation keys for OpenShot
 @author SuslikV
"""

import os
from PyQt5.QtWidgets import QDockWidget
from classes import info, ui_util
from classes.app import get_app

class CurveEditor(QDockWidget):
    """ This class is the Curve Editor dock window for OpenShot animations edit
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.loadEditorUI()

    def closeEvent(self, event):
        get_app().window.curve_editor_enable = False

    def loadEditorUI(self):
        """ Load editor's UI from the xml file """
        # Path to ui file
        ui_path = os.path.join(info.PATH, 'windows', 'ui', 'curve-editor.ui')

        # Load UI from designer
        ui_util.load_ui(self, ui_path)

        # Init UI (now 'self' is QDockWidget with object's name "dockCurveEditor" from .ui file)
        ui_util.init_ui(self)
