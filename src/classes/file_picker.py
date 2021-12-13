"""
 @file file_picker.py
 @brief A widget for selecting a file or folder
 @details
 The goal of this widget is improved keyboard-based file/folder selection
 by suggesting files or folders in the path currently provided
 @author Jackson Godwin <jackson@openshot.org>

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
from PyQt5.QtWidgets import QPushButton, QFileDialog, QCompleter, QLineEdit, QLabel
from PyQt5.QtWidgets import QWidget, QHBoxLayout
from PyQt5 import QtCore
import os
from classes.app import get_app


_ = get_app()._tr
# TODO: test on windows

class customLineEdit(QLineEdit):
    """A QLineEdit which doesn't highlight
    the entire text when reached with the tab key"""
    def __init__(self, *args, **kwargs):
        super(customLineEdit, self).__init__()

    def focusInEvent(self, *args, **kwargs):
        # Deselect text in this lineEdit
        super(customLineEdit, self).focusInEvent(*args, **kwargs)
        self.deselect()

class filePicker(QWidget):
    folder_only = False
    DEFAULT_STARTING_DIRECTORY = os.path.expanduser("~") # or os.environ["HOME"]
    PROMPT = _("File Path: ")

    def __init__(self, *args, **kwargs):
        self.folder_only = kwargs.get("folder_only", False)
        if "folder_only" in kwargs:
            kwargs.pop("folder_only")
        super().__init__(*args, **kwargs)

        self._createWidgets()
        self.path_line.setText( kwargs.get("path", self.DEFAULT_STARTING_DIRECTORY))

    def _createWidgets(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6,0,6,0) #least vertical height by default
        self.path_lbl = QLabel(self.PROMPT)
        # Browse Button
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browseButtonPushed)
        self.file_dialog = QFileDialog()
        # LineEdit input
        self.path_line = customLineEdit()
        if (self.folder_only):
            self.file_dialog.setOption(QFileDialog.ShowDirsOnly)
        self.layout.addWidget(self.path_lbl)
        self.layout.addWidget(self.path_line)
        self.layout.addWidget(self.browse_button)

    def _browseButtonPushed(self):
        self.path_line.setText(self.file_dialog.getExistingDirectory())

    def _addCompletion(self, line: QLineEdit):
        #TODO case insensitive DONE
        dirs = self._childDirs(line.text())
        com = QCompleter(dirs)
        com.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        com.setFilterMode(QtCore.Qt.MatchContains)
        line.setCompleter(com)

    def _childDirs(self, path: str):
        parent_dir = lambda x: os.path.abspath( os.path.join(x, ".."))
        while not os.path.exists(path) and path != os.path.expanduser("/"):
            path = parent_dir(path)
        dirs = os.listdir(path)
        dirs = [os.path.join(path, x) for x in dirs]
        if (self.folder_only):
            dirs = list(filter(os.path.isdir, dirs))
        return(dirs)

    _UPDATE_LOCK = False
    def _updateCompleterModel(self, line: QLineEdit):
        if (self._UPDATE_LOCK):
            return
        self._UPDATE_LOCK = True
        dirs = self._childDirs(line.text())
        line.completer().model().setStringList(dirs)
        self._UPDATE_LOCK = False

    def getPath(self) -> str:
        return self.path_line.text()

    def setPath(self, p: str):
        self.path_line.setText(p)

    def setPrompt(self, p: str):
        self.PROMPT = p
