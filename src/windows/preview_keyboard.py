"""Preview-local versions of the configured timeline keyboard commands."""
from functools import partial
from qt_api import QObject, QWidget, QLineEdit, QEvent, QKeySequence, Qt
from classes.app import get_app


class PreviewKeyboard(QObject):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.bindings = []
        commands = (
            ('nudgeLeft', ',', partial(self.nudge, -1)),
            ('nudgeRight', '.', partial(self.nudge, 1)),
            ('nudgeLeftBig', 'Shift+,', partial(self.nudge, -5)),
            ('nudgeRightBig', 'Shift+.', partial(self.nudge, 5)),
            ('timelineSelectLeftEdge', '[', partial(self.edge, 'in')),
            ('timelineSelectRightEdge', ']', partial(self.edge, 'out')),
            ('seekPreviousFrame', 'Left', partial(self.seek, -1)),
            ('seekNextFrame', 'Right', partial(self.seek, 1)),
            ('timelinePreviousFiveFrames', 'Shift+Left', partial(self.seek, -5)),
            ('timelineNextFiveFrames', 'Shift+Right', partial(self.seek, 5)),
            ('playToggle', 'Space', dialog.btnPlay.click),
            ('playbackStop', 'K', partial(dialog.btnPlay_clicked, force='pause')),
            ('actionRewind', 'J', partial(self.shuttle, -1)),
            ('actionFastForward', 'L', partial(self.shuttle, 1)),
        )
        lookup = getattr(get_app().window, 'getShortcutByName', None)
        for name, default, callback in commands:
            keys = lookup(name) if callable(lookup) else [QKeySequence(default)]
            self.bindings.extend((key, callback) for key in keys)
        for widget in [dialog] + dialog.findChildren(QWidget):
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.ShortcutOverride, QEvent.KeyPress):
            return False
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and self.dialog.range_mode != 'preview' and not event.modifiers()):
            from windows.source_range import SourceTimecodeEdit
            if isinstance(self.dialog.focusWidget(), SourceTimecodeEdit):
                if event.type() == QEvent.ShortcutOverride:
                    event.accept()
                    return True
                return False
            event.accept()
            if event.type() == QEvent.KeyPress and not event.isAutoRepeat():
                self.dialog.accept_source_changes()
            return True
        if isinstance(self.dialog.focusWidget(), QLineEdit):
            return False
        ruler = self.dialog.sliderVideo
        callback = None
        if event.key() == Qt.Key_Escape and ruler.active_edge:
            callback = partial(self.edge, None)
        else:
            modifiers = event.modifiers()
            modifiers = modifiers.value if hasattr(modifiers, 'value') else int(modifiers)
            sequence = QKeySequence(modifiers | event.key())
            callback = next((fn for key, fn in self.bindings if sequence == key), None)
        if callback is None:
            return False
        event.accept()
        if event.type() == QEvent.KeyPress:
            callback()
        return True

    def edge(self, edge):
        ruler = self.dialog.sliderVideo
        if not ruler.range_enabled:
            return
        ruler.active_edge = edge
        if edge:
            self.dialog._seek_range_edge(edge)
        ruler.update()

    def seek(self, frames):
        ruler = self.dialog.sliderVideo
        ruler.setValue(ruler.value()+frames)

    def nudge(self, frames):
        ruler = self.dialog.sliderVideo
        if not ruler.range_enabled:
            self.seek(frames)
            return
        self.dialog.btnPlay_clicked(force='pause')
        if ruler.active_edge:
            frame = ruler.in_frame if ruler.active_edge == 'in' else ruler.out_frame
            ruler.move_edge(ruler.active_edge, frame+frames)
        else:
            delta = max(1-ruler.in_frame, min(frames, ruler.maximum()-ruler.out_frame))
            if delta:
                ruler.set_region(ruler.in_frame+delta, ruler.out_frame+delta)
                ruler.rangeEdited.emit(ruler.in_frame, ruler.out_frame)
                ruler.setValue(max(ruler.in_frame, min(ruler.out_frame, ruler.value()+delta)))

    def shuttle(self, direction):
        d = self.dialog
        speed = d.preview_thread.player.Speed() if d.btnPlay.isChecked() else 0
        speed += direction
        if speed == 0:
            speed = direction
        d.btnPlay_clicked(force='play')
        d.SpeedSignal.emit(speed)
