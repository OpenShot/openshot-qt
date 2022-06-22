"""
 @file
 @brief A non-modal Qt color picker dialog launcher
 @author FeRD (Frank Dana) <ferdnyc@gmail.com>

 @section LICENSE

 Copyright (c) 2008-2020 OpenShot Studios, LLC
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

from classes.logger import log

from PyQt5.QtCore import Qt, QTimer, QRect, QPoint
from PyQt5.QtGui import QColor, QBrush, QPen, QPalette, QPainter, QPixmap
from PyQt5.QtWidgets import QColorDialog, QWidget, QLabel


class ColorPicker(QWidget):
    """Show a non-modal color picker.
    QColorDialog.colorSelected(QColor) is emitted when the user picks a color"""

    def __init__(self, initial_color: QColor, callback, extra_options=0,
                 parent=None, title=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)
        self.setObjectName("ColorPicker")
        # Merge any additional user-supplied options with our own
        options = QColorDialog.ColorDialogOption.DontUseNativeDialog
        if extra_options > 0:
            options = options | extra_options
        # Set up non-modal color dialog (to avoid blocking the eyedropper)
        log.debug(
            "Loading QColorDialog with start value %s",
            initial_color.getRgb())
        self.dialog = CPDialog(initial_color, parent)
        self.dialog.setObjectName("CPDialog")
        if title:
            self.dialog.setWindowTitle(title)
        self.dialog.setWindowFlags(Qt.WindowType.Tool)
        self.dialog.setOptions(options)
        # Avoid signal loops
        self.dialog.blockSignals(True)
        self.dialog.colorSelected.connect(callback)
        self.dialog.finished.connect(self.dialog.deleteLater)
        self.dialog.finished.connect(self.deleteLater)
        self.dialog.setCurrentColor(initial_color)
        self.dialog.blockSignals(False)
        self.dialog.open()
        # Seems to help if this is done AFTER init() returns
        QTimer.singleShot(0, self.add_alpha)
    def add_alpha(self):
        self.dialog.replace_label()


class CPDialog(QColorDialog):
    """Show a modified QColorDialog which supports checkerboard alpha"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.debug("CPDialog initialized")
        self.alpha_label = CPAlphaShowLabel(self)
        self.alpha_label.setObjectName("alpha_label")
        self.currentColorChanged.connect(self.alpha_label.updateColor)
    def replace_label(self):
        log.debug("Beginning discovery for QColorShowLabel widget")
        # Find the dialog widget used to display the current
        # color, so we can replace it with our implementation
        try:
            qcs = [
                a for a in self.children()
                if hasattr(a, "metaObject")
                and a.metaObject().className() == 'QColorShower'
                ][0]
            log.debug("Found QColorShower: %s", qcs)
            qcsl = [
                b for b in qcs.children()
                if hasattr(b, "metaObject")
                and b.metaObject().className() == 'QColorShowLabel'
                ][0]
            log.debug("Found QColorShowLabel: %s", qcsl)
        except IndexError as ex:
            child_list = [
                a.metaObject().className()
                for a in self.children()
                if hasattr(a, "metaObject")
                ]
            log.debug("%d children of CPDialog %s", len(child_list), child_list)
            raise RuntimeError("Could not find label to replace!") from ex
        qcslay = qcs.layout()
        log.debug(
            "QColorShowLabel found at layout index %d", qcslay.indexOf(qcsl))
        qcs.layout().replaceWidget(qcsl, self.alpha_label)
        log.debug("Replaced QColorShowLabel widget, hiding original")
        # Make sure it doesn't receive signals while hidden
        qcsl.blockSignals(True)
        qcsl.hide()
        self.alpha_label.show()


class CPAlphaShowLabel(QLabel):
    """A replacement for QColorDialog's QColorShowLabel which
    displays the currently-active color using checkerboard alpha"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Length in pixels of a side of the checkerboard squares
        # (Pattern is made up of 2x2 squares, total size 2n x 2n)
        self.checkerboard_size = 8
        # Start out transparent by default
        self.color = super().parent().currentColor()
        self.build_pattern()
        log.debug("CPAlphaShowLabel initialized, creating brush")
    def updateColor(self, color: QColor):
        self.color = color
        log.debug("Label color set to %s", str(color.getRgb()))
        self.repaint()
    def build_pattern(self) -> QPixmap:
        """Construct tileable checkerboard pattern for paint events"""
        # Brush will be an nxn checkerboard pattern
        n = self.checkerboard_size
        pat = QPixmap(2 * n, 2 * n)
        p = QPainter(pat)
        p.setPen(Qt.PenStyle.NoPen)
        # Paint a checkerboard pattern for the color to be overlaid on
        self.bg0 = QColor("#aaa")
        self.bg1 = QColor("#ccc")
        p.fillRect(pat.rect(), self.bg0)
        p.fillRect(QRect(0, 0, n, n), self.bg1)
        p.fillRect(QRect(n, n, 2 * n, 2 * n), self.bg1)
        p.end()
        log.debug("Constructed %s checkerboard brush", pat.size())
        self.pattern = pat
    def paintEvent(self, event):
        """Show the current color, with checkerboard alpha"""
        event.accept()
        p = QPainter(self)
        p.setPen(Qt.PenStyle.NoPen)
        if self.color.alphaF() < 1.0:
            # Draw a checkerboard pattern under the color
            p.drawTiledPixmap(event.rect(), self.pattern, QPoint(4,4))
        p.fillRect(event.rect(), self.color)
        p.end()
