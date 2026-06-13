"""
 @file
 @brief Reusable widgets for the Recording dock.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 SPDX-License-Identifier: GPL-3.0-or-later
 """

import re
import shutil
import subprocess

from qt_api import (
    Qt, pyqtSignal, QRect, QPoint,
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QApplication, QDialog, QPainter, QColor, QPen,
)

from classes.app import get_app
from classes.logger import log


CARD_STYLE = """
QFrame#recordingCard {
    background-color: rgba(20, 31, 48, 190);
    border: 1px solid rgba(70, 134, 230, 110);
    border-radius: 8px;
}
QFrame#recordingCard[checked="true"] {
    border: 2px solid #2f8cff;
    background-color: rgba(26, 58, 105, 170);
}
QFrame#recordingCard[available="false"] {
    border: 1px solid rgba(80, 91, 110, 90);
    background-color: rgba(20, 25, 34, 120);
}
QLabel#recordingCardTitle {
    color: #f4f7ff;
    font-size: 14px;
    font-weight: 700;
}
QLabel#recordingCardSubtitle {
    color: #9aa8bd;
    font-size: 11px;
}
"""

SECTION_STYLE = """
QFrame#recordingSection {
    background-color: rgba(13, 24, 38, 165);
    border: 1px solid rgba(83, 105, 134, 95);
    border-radius: 8px;
}
QFrame#recordingSection[active="true"] {
    border: 1px solid rgba(70, 141, 255, 125);
}
QFrame#recordingSection[active="false"] {
    color: #6f7b8d;
    background-color: rgba(15, 20, 28, 95);
}
QLabel#recordingSectionTitle {
    color: #f4f7ff;
    font-weight: 700;
}
QPushButton#recordingAdvancedLink {
    color: #4f9aff;
    border: none;
    padding: 0;
    text-align: right;
}
QPushButton#recordingAdvancedLink:hover {
    color: #b8d7ff;
    text-decoration: underline;
}
QPushButton#recordingSegment {
    border: 1px solid rgba(83, 105, 134, 120);
    border-radius: 6px;
    padding: 7px 10px;
    color: #c4cedd;
    background-color: rgba(14, 25, 40, 170);
}
QPushButton#recordingSegment[position="left"] {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QPushButton#recordingSegment[position="right"] {
    border-left: none;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QPushButton#recordingSegment:checked {
    color: #9dccff;
    border: 1px solid #2f8cff;
    background-color: rgba(40, 94, 170, 135);
}
QPushButton#recordingPrimary {
    color: white;
    border: none;
    border-radius: 8px;
    padding: 11px;
    font-size: 15px;
    font-weight: 700;
    background-color: #087cff;
}
QPushButton#recordingPrimary:hover {
    background-color: #1688ff;
}
QPushButton#recordingPrimary:pressed {
    background-color: #0567d6;
}
"""


class RecordingSourceCard(QFrame):
    toggled = pyqtSignal(bool)

    def __init__(self, title, subtitle, symbol, parent=None):
        super().__init__(parent)
        self._checked = False
        self._available = True
        self.setObjectName("recordingCard")
        self.setProperty("checked", False)
        self.setProperty("available", True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(88)
        self.setStyleSheet(CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        top = QGridLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 0)
        top.setColumnStretch(2, 1)
        icon = QLabel(symbol, self)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("color: #7db7ff; font-size: 22px;")
        self.check_label = QLabel("", self)
        self.check_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.check_label.setStyleSheet("color: #7db7ff; font-size: 17px;")
        top.addWidget(icon, 0, 1)
        top.addWidget(self.check_label, 0, 2)
        layout.addLayout(top)

        title_label = QLabel(title, self)
        title_label.setObjectName("recordingCardTitle")
        title_label.setAlignment(Qt.AlignCenter)
        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setObjectName("recordingCardSubtitle")
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        checked = bool(checked) and self._available
        if self._checked == checked:
            return
        self._checked = checked
        self.check_label.setText("✓" if checked else "")
        self.setProperty("checked", checked)
        self.style().unpolish(self)
        self.style().polish(self)
        self.toggled.emit(checked)

    def setAvailable(self, available, tooltip=""):
        self._available = bool(available)
        self.setEnabled(self._available)
        self.setProperty("available", self._available)
        self.setToolTip(tooltip)
        if not self._available:
            self.setChecked(False)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._available:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)


class RecordingSection(QFrame):
    def __init__(self, title, symbol, parent=None):
        super().__init__(parent)
        self.setObjectName("recordingSection")
        self.setProperty("active", True)
        self.setStyleSheet(SECTION_STYLE)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(10, 8, 10, 10)
        self.outer_layout.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel(symbol, self)
        icon.setStyleSheet("color: #8fbfff; font-size: 16px;")
        title_label = QLabel(title, self)
        title_label.setObjectName("recordingSectionTitle")
        self.advanced_button = QPushButton(get_app()._tr("Advanced"), self)
        self.advanced_button.setObjectName("recordingAdvancedLink")
        self.advanced_button.setFlat(True)
        self.advanced_button.setCheckable(True)
        self.advanced_button.setCursor(Qt.PointingHandCursor)
        header.addWidget(icon)
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.advanced_button)
        self.outer_layout.addLayout(header)

        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)
        self.outer_layout.addWidget(self.body)

        self.advanced_body = QWidget(self)
        self.advanced_layout = QGridLayout(self.advanced_body)
        self.advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.advanced_layout.setHorizontalSpacing(8)
        self.advanced_layout.setVerticalSpacing(5)
        self.advanced_body.hide()
        self.outer_layout.addWidget(self.advanced_body)
        self.advanced_button.toggled.connect(self.advanced_body.setVisible)

    def setActive(self, active):
        active = bool(active)
        self.setProperty("active", active)
        self.body.setVisible(active)
        self.advanced_button.setEnabled(active)
        if not active:
            self.advanced_body.hide()
            self.advanced_button.setChecked(False)
        self.style().unpolish(self)
        self.style().polish(self)


class SegmentButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("recordingSegment")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)


class RegionSelectorOverlay(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.origin = QPoint()
        self.selection = QRect()
        self.global_origin = QPoint()
        self.global_selection = QRect()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setWindowOpacity(0.35)

    def select(self):
        screen = QApplication.primaryScreen()
        screen_geometry = None
        if screen:
            screen_geometry = screen.geometry()
            self.setGeometry(screen_geometry)
        exec_method = getattr(self, "exec", None) or getattr(self, "exec_", None)
        accepted = getattr(QDialog, "Accepted", None)
        if accepted is None and hasattr(QDialog, "DialogCode"):
            accepted = QDialog.DialogCode.Accepted
        if exec_method() == accepted and self.selection.isValid():
            rect = self.selection.normalized()
            return self._to_x11_geometry(rect, screen_geometry)
        return None

    def _to_x11_geometry(self, rect, screen_geometry):
        root_width, root_height = x11_root_size()
        top_left = self.mapToGlobal(rect.topLeft())
        bottom_right = self.mapToGlobal(rect.bottomRight())
        if screen_geometry and screen_geometry.width() > 0 and screen_geometry.height() > 0:
            scale_x = float(root_width or screen_geometry.width()) / float(screen_geometry.width())
            scale_y = float(root_height or screen_geometry.height()) / float(screen_geometry.height())
            origin_x = screen_geometry.x()
            origin_y = screen_geometry.y()
        else:
            scale_x = scale_y = 1.0
            origin_x = origin_y = 0

        x = int(round((top_left.x() - origin_x) * scale_x))
        y = int(round((top_left.y() - origin_y) * scale_y))
        width = int(round((bottom_right.x() - top_left.x() + 1) * scale_x))
        height = int(round((bottom_right.y() - top_left.y() + 1) * scale_y))

        if root_width and root_height:
            x = max(0, min(x, root_width - 1))
            y = max(0, min(y, root_height - 1))
            width = max(1, min(width, root_width - x))
            height = max(1, min(height, root_height - y))
        return x, y, width, height

    def _global_pos(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    def mousePressEvent(self, event):
        self.origin = event.pos()
        self.selection = QRect(self.origin, self.origin)
        self.global_origin = self._global_pos(event)
        self.global_selection = QRect(self.global_origin, self.global_origin)
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.selection = QRect(self.origin, event.pos())
            self.global_selection = QRect(self.global_origin, self._global_pos(event))
            self.update()

    def mouseReleaseEvent(self, event):
        self.selection = QRect(self.origin, event.pos()).normalized()
        self.global_selection = QRect(self.global_origin, self._global_pos(event)).normalized()
        if self.global_selection.width() > 8 and self.global_selection.height() > 8:
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if self.global_selection.isValid():
            global_rect = self.global_selection.normalized()
            rect = QRect(
                self.mapFromGlobal(global_rect.topLeft()),
                self.mapFromGlobal(global_rect.bottomRight()),
            ).normalized()
            painter.setPen(QPen(QColor(64, 145, 255), 2))
            painter.fillRect(rect, QColor(64, 145, 255, 45))
            painter.drawRect(rect)


def pick_x11_region(parent=None):
    return RegionSelectorOverlay(parent).select()


def x11_root_size():
    try:
        result = subprocess.run(
            ["xwininfo", "-root"],
            check=True,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        return None, None

    match = re.search(r"Width:\s+(\d+).*?Height:\s+(\d+)", result.stdout, re.S)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"Dimensions:\s+(\d+)x(\d+)", result.stdout)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def pick_x11_window():
    result = pick_x11_window_with_xdotool()
    if result:
        return result
    return pick_x11_window_with_xwininfo()


def pick_x11_window_with_xdotool():
    if not shutil.which("xdotool"):
        return None
    try:
        selected = subprocess.run(
            ["xdotool", "selectwindow"],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
        window_id = selected.stdout.strip()
        if not window_id:
            return None
        geometry = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            check=True,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception as ex:
        log.debug("Unable to select X11 window with xdotool: %s", ex, exc_info=True)
        return None

    parsed = {}
    for line in geometry.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ("X", "Y", "WIDTH", "HEIGHT"):
            try:
                parsed[key.lower()] = int(value)
            except ValueError:
                return None
    if not all(key in parsed for key in ("x", "y", "width", "height")):
        return None
    log.info(
        "Selected X11 window with xdotool: id=%s x=%s y=%s width=%s height=%s",
        window_id, parsed["x"], parsed["y"], parsed["width"], parsed["height"],
    )
    return parsed["x"], parsed["y"], parsed["width"], parsed["height"], window_id


def pick_x11_window_with_xwininfo():
    try:
        result = subprocess.run(
            ["xwininfo"],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except Exception as ex:
        log.warning("Unable to select X11 window with xwininfo: %s", ex)
        return None

    fields = {
        "x": r"Absolute upper-left X:\s+(-?\d+)",
        "y": r"Absolute upper-left Y:\s+(-?\d+)",
        "width": r"Width:\s+(\d+)",
        "height": r"Height:\s+(\d+)",
        "border": r"Border width:\s+(\d+)",
    }
    parsed = {}
    for key, pattern in fields.items():
        match = re.search(pattern, result.stdout)
        if not match and key != "border":
            return None
        parsed[key] = int(match.group(1)) if match else 0
    # xwininfo reports width/height for the window interior, but X11 border
    # pixels can be outside that rectangle. Capture the interior by offsetting
    # the origin inward while preserving the reported content size.
    parsed["x"] += parsed["border"]
    parsed["y"] += parsed["border"]
    log.info(
        "Selected X11 window with xwininfo: x=%s y=%s width=%s height=%s border=%s",
        parsed["x"], parsed["y"], parsed["width"], parsed["height"], parsed["border"],
    )
    return parsed["x"], parsed["y"], parsed["width"], parsed["height"], ""
