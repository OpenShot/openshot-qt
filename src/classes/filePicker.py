from PyQt5.QtWidgets import QApplication, QPushButton, QFileDialog, QCompleter, QLineEdit, QLabel
from PyQt5.QtWidgets import QGridLayout, QWidget, QHBoxLayout
from PyQt5 import QtCore
import os

from classes.app import get_app
_ = get_app()._tr
# TODO: test on windows

class customLineEdit(QLineEdit):
    """A QLineEdit which doens't highlight
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
    PROMPT = "File Path: "

    def __init__(self, *args, **kwargs):
        super(filePicker, self).__init__()
        self.folder_only = kwargs.get("folder_only", False)

        self._createWidgets()
        self.dirLine.setText( kwargs.get("path", self.DEFAULT_STARTING_DIRECTORY))
        self._addCompletion(self.dirLine)
        self.dirLine.textEdited.connect(lambda : self._updateCompleterModel(self.dirLine) )

    def _createWidgets(self):
        self.layout = QHBoxLayout(self)
        self.lbl = QLabel(_(self.PROMPT))
        # Browse Button
        self.browseButton = QPushButton("Browse...")
        self.browseButton.clicked.connect(self._browse_button_pushed)
        self.fileDialog = QFileDialog()
        # LineEdit input
        self.dirLine = customLineEdit()
        if (self.folder_only):
            self.fileDialog.setOption(QFileDialog.ShowDirsOnly)
        self.layout.addWidget(self.lbl)
        self.layout.addWidget(self.dirLine)
        self.layout.addWidget(self.browseButton)

    def _browse_button_pushed(self):
        self.dirLine.setText(self.fileDialog.getExistingDirectory())

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
            dirs = list(filter(lambda x: os.path.isdir(x), dirs))
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
        return self.dirLine.text()

    def setPath(self, p: str):
        self.dirLine.setText(p)

    def setPrompt(self, p: str):
        self.PROMPT = p
