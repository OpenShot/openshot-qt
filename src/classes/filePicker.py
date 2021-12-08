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
    PROMPT = "File Path: "

    def __init__(self, *args, **kwargs):
        super(filePicker, self).__init__()
        self.folder_only = kwargs.get("folder_only", False)

        self._createWidgets()
        self.dir_line.setText( kwargs.get("path", self.DEFAULT_STARTING_DIRECTORY))
        self._addCompletion(self.dir_line)
        self.dir_line.textEdited.connect(lambda : self._updateCompleterModel(self.dir_line) )

    def _createWidgets(self):
        self.layout = QHBoxLayout(self)
        self.lbl = QLabel(_(self.PROMPT))
        # Browse Button
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browseButtonPushed)
        self.file_dialog = QFileDialog()
        # LineEdit input
        self.dir_line = customLineEdit()
        if (self.folder_only):
            self.file_dialog.setOption(QFileDialog.ShowDirsOnly)
        self.layout.addWidget(self.lbl)
        self.layout.addWidget(self.dir_line)
        self.layout.addWidget(self.browse_button)

    def _browseButtonPushed(self):
        self.dir_line.setText(self.file_dialog.getExistingDirectory())

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
        return self.dir_line.text()

    def setPath(self, p: str):
        self.dir_line.setText(p)

    def setPrompt(self, p: str):
        self.PROMPT = p
