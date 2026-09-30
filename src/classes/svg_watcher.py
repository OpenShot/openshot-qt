"""Watch a title's contents, including saves which replace the file atomically."""
from xml.dom import minidom
from xml.parsers.expat import ExpatError

from qt_api import QObject, QTimer, Signal


class SvgWatcher(QObject):
    changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None
        self.contents = None
        self.pending = None
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.check)

    def watch(self, path):
        self.stop()
        self.path = path
        try:
            with open(path, 'rb') as stream:
                self.remember(stream.read())
        except OSError:
            # A file may temporarily disappear during an atomic save.
            self.remember(None)
        self.timer.start()

    def remember(self, contents):
        """Ignore our own writes and already loaded content."""
        self.contents = contents
        self.pending = None

    def stop(self):
        self.timer.stop()
        self.path = None
        self.pending = None

    def check(self, force=False):
        if not self.path:
            return
        try:
            with open(self.path, 'rb') as stream:
                contents = stream.read()
        except OSError:
            self.pending = None
            return
        if contents == self.contents:
            self.pending = None
            return
        # Require two equal reads so a save can finish before rebuilding controls.
        if not force and contents != self.pending:
            self.pending = contents
            return
        try:
            document = minidom.parseString(contents)
        except (ExpatError, LookupError, ValueError):
            return
        if document.documentElement.localName != 'svg':
            return
        self.remember(contents)
        self.changed.emit(document)
