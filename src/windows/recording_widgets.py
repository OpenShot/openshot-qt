"""
 @file
 @brief Reusable widgets for the Recording dock.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 SPDX-License-Identifier: GPL-3.0-or-later
 """

import ctypes
import ctypes.util
import os
import re
import shutil
import subprocess  # nosec B404 -- fixed argv only; shell execution is never used
import sys

from qt_api import (
    Qt, pyqtSignal, QRect, QPoint,
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QApplication, QDialog, QPainter, QColor, QPen,
)

from classes.app import get_app
from classes.logger import log


_WIN32_USER32 = None
_WIN32_DWMAPI = None
_WIN32_ENUMPROC = None
_WIN32_MONITOR_ENUMPROC = None
_WIN32_TYPES = None
_MAC_COREGRAPHICS = None
_MAC_COREFOUNDATION = None
_MAC_KEYS = None


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

        icon = QLabel(symbol, self)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedHeight(30)
        icon.setStyleSheet("color: #7db7ff; font-size: 22px;")
        layout.addWidget(icon, 0, Qt.AlignCenter)

        title_label = QLabel(title, self)
        title_label.setObjectName("recordingCardTitle")
        title_label.setAlignment(Qt.AlignCenter)
        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setObjectName("recordingCardSubtitle")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        checked = bool(checked) and self._available
        if self._checked == checked:
            return
        self._checked = checked
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
    def __init__(self, parent=None, screen_geometry=None, x11_geometry=True):
        super().__init__(parent)
        self.origin = QPoint()
        self.selection = QRect()
        self.global_origin = QPoint()
        self.global_selection = QRect()
        self.screen_geometry = screen_geometry
        self.x11_geometry = bool(x11_geometry)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setWindowOpacity(0.35)

    def select(self):
        screen_geometry = self.screen_geometry
        if screen_geometry is None:
            screen = QApplication.primaryScreen()
            screen_geometry = screen.geometry() if screen else None
        if screen_geometry:
            self.setGeometry(screen_geometry)
        accepted = getattr(QDialog, "Accepted", None)
        if accepted is None and hasattr(QDialog, "DialogCode"):
            accepted = QDialog.DialogCode.Accepted
        if self.exec_() == accepted and self.selection.isValid():
            rect = self.selection.normalized()
            if self.x11_geometry:
                return self._to_x11_geometry(rect, screen_geometry)
            return self._to_global_geometry(rect)
        return None

    def _to_global_geometry(self, rect):
        top_left = self.mapToGlobal(rect.topLeft())
        bottom_right = self.mapToGlobal(rect.bottomRight())
        x = int(min(top_left.x(), bottom_right.x()))
        y = int(min(top_left.y(), bottom_right.y()))
        width = int(abs(bottom_right.x() - top_left.x()) + 1)
        height = int(abs(bottom_right.y() - top_left.y()) + 1)
        return x, y, max(1, width), max(1, height)

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


def pick_screen_region(parent=None):
    if sys.platform.startswith("win"):
        return pick_windows_region(parent)
    if sys.platform == "darwin":
        return pick_mac_region(parent)
    return pick_x11_region(parent)


def x11_root_size():
    try:
        result = subprocess.run(  # nosec B603 -- fixed argv list, no shell
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


def screen_root_size():
    if sys.platform.startswith("win"):
        _, _, width, height = windows_virtual_screen_geometry()
        return width, height
    if sys.platform == "darwin":
        _, _, width, height = mac_primary_screen_geometry()
        return width, height
    return x11_root_size()


def screen_root_geometry():
    if sys.platform.startswith("win"):
        return windows_virtual_screen_geometry()
    if sys.platform == "darwin":
        return mac_primary_screen_geometry()
    width, height = x11_root_size()
    return 0, 0, width, height


def screen_capture_sources():
    if sys.platform.startswith("win"):
        sources = windows_monitor_geometries()
        all_x, all_y, all_width, all_height = windows_virtual_screen_geometry()
        if all_width and all_height and len(sources) > 1:
            sources.append({
                "id": "all",
                "label": get_app()._tr("All Screens"),
                "display": "desktop",
                "x": int(all_x or 0),
                "y": int(all_y or 0),
                "width": int(all_width),
                "height": int(all_height),
                "all": True,
                "primary": False,
            })
        return sources

    screens = list(QApplication.screens() or [])
    if sys.platform == "darwin":
        sources = []
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(screens):
            geometry = screen.geometry()
            scale = float(screen.devicePixelRatio() or 1.0)
            label = screen.name() or get_app()._tr("Screen %s") % (index + 1)
            sources.append({
                "id": "screen-%s" % index,
                "label": "%s (%sx%s)" % (
                    label,
                    int(round(geometry.width() * scale)),
                    int(round(geometry.height() * scale)),
                ),
                "display": "Capture screen %s:none" % index,
                "x": 0,
                "y": 0,
                "width": max(1, int(round(geometry.width() * scale))),
                "height": max(1, int(round(geometry.height() * scale))),
                "all": False,
                "primary": screen is primary,
            })
        if sources:
            return sources
        x, y, width, height = mac_primary_screen_geometry()
        return [{
            "id": "screen-0",
            "label": get_app()._tr("Screen 1"),
            "display": "Capture screen 0:none",
            "x": int(x or 0),
            "y": int(y or 0),
            "width": int(width or 1280),
            "height": int(height or 720),
            "all": False,
            "primary": True,
        }]

    display = os.environ.get("DISPLAY", ":0.0")
    root_width, root_height = x11_root_size()
    virtual = None
    try:
        primary = QApplication.primaryScreen()
        virtual = primary.virtualGeometry() if primary else None
    except Exception:
        virtual = None
    scale_x = 1.0
    scale_y = 1.0
    if virtual and virtual.width() > 0 and virtual.height() > 0 and root_width and root_height:
        scale_x = float(root_width) / float(virtual.width())
        scale_y = float(root_height) / float(virtual.height())
    sources = []
    primary = QApplication.primaryScreen()
    for index, screen in enumerate(screens):
        geometry = screen.geometry()
        origin_x = virtual.x() if virtual else 0
        origin_y = virtual.y() if virtual else 0
        x = int(round((geometry.x() - origin_x) * scale_x))
        y = int(round((geometry.y() - origin_y) * scale_y))
        width = max(1, int(round(geometry.width() * scale_x)))
        height = max(1, int(round(geometry.height() * scale_y)))
        label = screen.name() or get_app()._tr("Screen %s") % (index + 1)
        sources.append({
            "id": "screen-%s" % index,
            "label": "%s (%sx%s)" % (label, width, height),
            "display": display,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "all": False,
            "primary": screen is primary,
        })
    if root_width and root_height and len(sources) > 1:
        sources.append({
            "id": "all",
            "label": get_app()._tr("All Screens"),
            "display": display,
            "x": 0,
            "y": 0,
            "width": int(root_width),
            "height": int(root_height),
            "all": True,
            "primary": False,
        })
    if sources:
        return sources
    return [{
        "id": "screen-0",
        "label": get_app()._tr("Screen 1"),
        "display": display,
        "x": 0,
        "y": 0,
        "width": int(root_width or 1280),
        "height": int(root_height or 720),
        "all": False,
        "primary": True,
    }]


def pick_x11_window():
    result = pick_x11_window_with_xdotool()
    if result:
        return result
    return pick_x11_window_with_xwininfo()


def pick_screen_window():
    if sys.platform.startswith("win"):
        return pick_windows_window()
    if sys.platform == "darwin":
        return pick_mac_window()
    return pick_x11_window()


def mac_primary_screen_geometry():
    if sys.platform != "darwin":
        return 0, 0, None, None
    try:
        screen = QApplication.primaryScreen()
        geometry = screen.geometry() if screen else None
        if not geometry:
            return 0, 0, None, None
        scale = float(screen.devicePixelRatio() or 1.0)
        return (
            0,
            0,
            max(1, int(round(geometry.width() * scale))),
            max(1, int(round(geometry.height() * scale))),
        )
    except Exception:
        log.debug("Unable to query macOS primary screen geometry", exc_info=True)
        return 0, 0, None, None


def _mac_point_to_capture_pixels(x, y, width, height):
    screen = QApplication.screenAt(QPoint(int(x), int(y))) or QApplication.primaryScreen()
    geometry = screen.geometry() if screen else None
    scale = float(screen.devicePixelRatio() or 1.0) if screen else 1.0
    origin_x = geometry.x() if geometry else 0
    origin_y = geometry.y() if geometry else 0
    return (
        max(0, int(round((int(x) - origin_x) * scale))),
        max(0, int(round((int(y) - origin_y) * scale))),
        max(1, int(round(int(width) * scale))),
        max(1, int(round(int(height) * scale))),
    )


def pick_mac_region(parent=None):
    screen = QApplication.primaryScreen()
    geometry = screen.geometry() if screen else None
    result = RegionSelectorOverlay(parent, geometry, x11_geometry=False).select()
    if not result:
        return None
    return _mac_point_to_capture_pixels(*result)


def _mac_frameworks():
    global _MAC_COREGRAPHICS, _MAC_COREFOUNDATION
    if _MAC_COREGRAPHICS is None:
        path = ctypes.util.find_library("CoreGraphics")
        _MAC_COREGRAPHICS = ctypes.cdll.LoadLibrary(path) if path else False
    if _MAC_COREFOUNDATION is None:
        path = ctypes.util.find_library("CoreFoundation")
        _MAC_COREFOUNDATION = ctypes.cdll.LoadLibrary(path) if path else False
    if not _MAC_COREGRAPHICS or not _MAC_COREFOUNDATION:
        return None, None
    return _MAC_COREGRAPHICS, _MAC_COREFOUNDATION


def _mac_define_signatures():
    CG, CF = _mac_frameworks()
    if not CG or not CF:
        return None, None

    CFArrayRef = ctypes.c_void_p
    CFTypeRef = ctypes.c_void_p
    CFStringRef = ctypes.c_void_p
    CFNumberRef = ctypes.c_void_p
    CFIndex = ctypes.c_long

    CG.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    CG.CGWindowListCopyWindowInfo.restype = CFArrayRef

    CF.CFRelease.argtypes = [CFTypeRef]
    CF.CFRelease.restype = None
    CF.CFArrayGetCount.argtypes = [CFArrayRef]
    CF.CFArrayGetCount.restype = CFIndex
    CF.CFArrayGetValueAtIndex.argtypes = [CFArrayRef, CFIndex]
    CF.CFArrayGetValueAtIndex.restype = CFTypeRef
    CF.CFDictionaryGetValueIfPresent.argtypes = [ctypes.c_void_p, CFTypeRef, ctypes.POINTER(CFTypeRef)]
    CF.CFDictionaryGetValueIfPresent.restype = ctypes.c_bool
    CF.CFStringCreateWithCString.argtypes = [CFTypeRef, ctypes.c_char_p, ctypes.c_uint32]
    CF.CFStringCreateWithCString.restype = CFStringRef
    CF.CFStringGetCString.argtypes = [CFStringRef, ctypes.c_char_p, CFIndex, ctypes.c_uint32]
    CF.CFStringGetCString.restype = ctypes.c_bool
    CF.CFNumberGetValue.argtypes = [CFNumberRef, ctypes.c_int, ctypes.c_void_p]
    CF.CFNumberGetValue.restype = ctypes.c_bool
    return CG, CF


def _mac_keys():
    global _MAC_KEYS
    if _MAC_KEYS is not None:
        return _MAC_KEYS
    _CG, CF = _mac_define_signatures()
    if not CF:
        return {}
    encoding = 0x08000100
    names = (
        "kCGWindowNumber",
        "kCGWindowOwnerName",
        "kCGWindowOwnerPID",
        "kCGWindowName",
        "kCGWindowLayer",
        "kCGWindowAlpha",
        "kCGWindowBounds",
        "X",
        "Y",
        "Width",
        "Height",
    )
    _MAC_KEYS = {
        name: CF.CFStringCreateWithCString(None, name.encode("utf-8"), encoding)
        for name in names
    }
    return _MAC_KEYS


def _mac_dict_value(dictionary, key):
    _CG, CF = _mac_define_signatures()
    keys = _mac_keys()
    if not CF or key not in keys:
        return None
    value = ctypes.c_void_p()
    if CF.CFDictionaryGetValueIfPresent(dictionary, keys[key], ctypes.byref(value)):
        return value.value
    return None


def _mac_number(value, as_int=False):
    if not value:
        return None
    _CG, CF = _mac_define_signatures()
    if not CF:
        return None
    if as_int:
        out = ctypes.c_int()
        return int(out.value) if CF.CFNumberGetValue(value, 3, ctypes.byref(out)) else None
    out = ctypes.c_double()
    return float(out.value) if CF.CFNumberGetValue(value, 13, ctypes.byref(out)) else None


def _mac_string(value):
    if not value:
        return ""
    _CG, CF = _mac_define_signatures()
    if not CF:
        return ""
    buffer = ctypes.create_string_buffer(4096)
    if CF.CFStringGetCString(value, buffer, len(buffer), 0x08000100):
        return buffer.value.decode("utf-8", "replace")
    return ""


def _mac_window_bounds(bounds):
    if not bounds:
        return None
    x = _mac_number(_mac_dict_value(bounds, "X"))
    y = _mac_number(_mac_dict_value(bounds, "Y"))
    width = _mac_number(_mac_dict_value(bounds, "Width"))
    height = _mac_number(_mac_dict_value(bounds, "Height"))
    if x is None or y is None or width is None or height is None:
        return None
    return int(round(x)), int(round(y)), int(round(width)), int(round(height))


def _mac_visible_windows():
    CG, CF = _mac_define_signatures()
    if not CG or not CF:
        return []
    options = (1 << 0) | (1 << 4)  # On-screen only, excluding desktop elements.
    window_array = CG.CGWindowListCopyWindowInfo(options, 0)
    if not window_array:
        return []
    windows = []
    try:
        count = int(CF.CFArrayGetCount(window_array))
        current_pid = os.getpid()
        for index in range(count):
            window = CF.CFArrayGetValueAtIndex(window_array, index)
            layer = _mac_number(_mac_dict_value(window, "kCGWindowLayer"), as_int=True)
            alpha = _mac_number(_mac_dict_value(window, "kCGWindowAlpha"))
            if layer != 0 or alpha == 0:
                continue
            owner = _mac_string(_mac_dict_value(window, "kCGWindowOwnerName"))
            owner_pid = _mac_number(_mac_dict_value(window, "kCGWindowOwnerPID"), as_int=True)
            title = _mac_string(_mac_dict_value(window, "kCGWindowName"))
            bounds = _mac_window_bounds(_mac_dict_value(window, "kCGWindowBounds"))
            number = _mac_number(_mac_dict_value(window, "kCGWindowNumber"), as_int=True)
            if not bounds:
                continue
            x, y, width, height = bounds
            if width <= 8 or height <= 8:
                continue
            if owner_pid == current_pid:
                continue
            windows.append({
                "id": number or 0,
                "owner": owner,
                "title": title,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            })
    finally:
        CF.CFRelease(window_array)
    return windows


def _mac_pick_window_at(x, y):
    for window in _mac_visible_windows():
        left = window["x"]
        top = window["y"]
        right = left + window["width"]
        bottom = top + window["height"]
        if left <= x <= right and top <= y <= bottom:
            return window
    return None


class MacWindowSelectorOverlay(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        screen = QApplication.primaryScreen()
        self.screen_geometry = screen.geometry() if screen else QRect(0, 0, 1, 1)
        self.hover_rect = QRect()
        self.selected_result = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setWindowOpacity(0.22)
        self.setGeometry(self.screen_geometry)

    def select(self):
        accepted = getattr(QDialog, "Accepted", None)
        if accepted is None and hasattr(QDialog, "DialogCode"):
            accepted = QDialog.DialogCode.Accepted
        return self.selected_result if self.exec_() == accepted else None

    def _event_global_pos(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    def _update_hover(self, point):
        picked = _mac_pick_window_at(int(point.x()), int(point.y()))
        if not picked:
            self.hover_rect = QRect()
            self.update()
            return None
        self.hover_rect = QRect(
            self.mapFromGlobal(QPoint(picked["x"], picked["y"])),
            self.mapFromGlobal(QPoint(picked["x"] + picked["width"], picked["y"] + picked["height"])),
        ).normalized()
        self.update()
        return picked

    def mouseMoveEvent(self, event):
        self._update_hover(self._event_global_pos(event))

    def mouseReleaseEvent(self, event):
        picked = self._update_hover(self._event_global_pos(event))
        if not picked:
            self.reject()
            return
        x, y, width, height = _mac_point_to_capture_pixels(
            picked["x"], picked["y"], picked["width"], picked["height"])
        if width > 8 and height > 8:
            log.info(
                "Selected macOS window: id=%s owner=%s title=%s x=%s y=%s width=%s height=%s",
                picked["id"], picked["owner"], picked["title"], x, y, width, height,
            )
            self.selected_result = x, y, width, height, str(picked["id"])
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 95))
        if self.hover_rect.isValid():
            painter.setPen(QPen(QColor(64, 145, 255), 3))
            painter.fillRect(self.hover_rect, QColor(64, 145, 255, 45))
            painter.drawRect(self.hover_rect)


def pick_mac_window(parent=None):
    try:
        return MacWindowSelectorOverlay(parent).select()
    except Exception as ex:
        log.warning("Unable to select macOS window: %s", ex, exc_info=True)
        return None


def _windows_enum_proc_type():
    global _WIN32_ENUMPROC
    if _WIN32_ENUMPROC is None:
        wintypes = _windows_types()
        _WIN32_ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    return _WIN32_ENUMPROC


def _windows_monitor_enum_proc_type():
    global _WIN32_MONITOR_ENUMPROC
    if _WIN32_MONITOR_ENUMPROC is None:
        wintypes = _windows_types()
        _WIN32_MONITOR_ENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )
    return _WIN32_MONITOR_ENUMPROC


def _windows_types():
    global _WIN32_TYPES
    if _WIN32_TYPES is None:
        from ctypes import wintypes
        _WIN32_TYPES = wintypes
    return _WIN32_TYPES


def _windows_user32():
    global _WIN32_USER32
    if _WIN32_USER32 is None:
        wintypes = _windows_types()
        user32 = ctypes.windll.user32
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.EnumWindows.argtypes = [_windows_enum_proc_type(), wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.EnumDisplayMonitors.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            _windows_monitor_enum_proc_type(),
            wintypes.LPARAM,
        ]
        user32.EnumDisplayMonitors.restype = wintypes.BOOL
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        _WIN32_USER32 = user32
    return _WIN32_USER32


def _windows_dwmapi():
    global _WIN32_DWMAPI
    if _WIN32_DWMAPI is None:
        wintypes = _windows_types()
        try:
            dwmapi = ctypes.windll.dwmapi
            dwmapi.DwmGetWindowAttribute.argtypes = [
                wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
            ]
            dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
            _WIN32_DWMAPI = dwmapi
        except Exception:
            _WIN32_DWMAPI = False
    return _WIN32_DWMAPI or None


def windows_virtual_screen_geometry():
    if not sys.platform.startswith("win"):
        return 0, 0, None, None
    user32 = _windows_user32()
    x = int(user32.GetSystemMetrics(76))      # SM_XVIRTUALSCREEN
    y = int(user32.GetSystemMetrics(77))      # SM_YVIRTUALSCREEN
    width = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
    height = int(user32.GetSystemMetrics(79)) # SM_CYVIRTUALSCREEN
    return x, y, width, height


def windows_monitor_geometries():
    if not sys.platform.startswith("win"):
        return []
    user32 = _windows_user32()
    sources = []

    def enum_proc(_hmonitor, _hdc, rect, _lparam):
        geometry = rect.contents
        width = int(geometry.right - geometry.left)
        height = int(geometry.bottom - geometry.top)
        if width > 0 and height > 0:
            index = len(sources) + 1
            sources.append({
                "id": "screen-%s" % index,
                "label": "%s (%sx%s)" % (get_app()._tr("Screen %s") % index, width, height),
                "display": "desktop",
                "x": int(geometry.left),
                "y": int(geometry.top),
                "width": width,
                "height": height,
                "all": False,
                "primary": int(geometry.left) <= 0 < int(geometry.right)
                    and int(geometry.top) <= 0 < int(geometry.bottom),
            })
        return True

    try:
        user32.EnumDisplayMonitors(None, None, _windows_monitor_enum_proc_type()(enum_proc), 0)
    except Exception:
        log.debug("Unable to enumerate Windows monitors", exc_info=True)
        return []
    return sources


def pick_windows_region(parent=None):
    x, y, width, height = windows_virtual_screen_geometry()
    if not width or not height:
        return None
    return RegionSelectorOverlay(
        parent,
        QRect(int(x), int(y), int(width), int(height)),
        x11_geometry=False,
    ).select()


def _windows_window_title(hwnd):
    user32 = _windows_user32()
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _windows_hwnd_value(hwnd):
    value = getattr(hwnd, "value", hwnd)
    return int(value or 0)


def _windows_window_rect(hwnd):
    wintypes = _windows_types()
    user32 = _windows_user32()
    rect = wintypes.RECT()
    dwmapi = _windows_dwmapi()
    if dwmapi is not None:
        # DWMWA_EXTENDED_FRAME_BOUNDS gives visual bounds without the invisible
        # resize border on modern Windows.
        if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) == 0:
            return rect
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect
    return None


def _windows_cursor_pos():
    wintypes = _windows_types()
    point = wintypes.POINT()
    if _windows_user32().GetCursorPos(ctypes.byref(point)):
        return int(point.x), int(point.y)
    return None


def _windows_pick_window_at(x, y):
    wintypes = _windows_types()
    user32 = _windows_user32()
    current_pid = os.getpid()
    point = wintypes.POINT(int(x), int(y))
    candidates = []

    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) == current_pid:
            return True
        title = _windows_window_title(hwnd)
        if not title:
            return True
        rect = _windows_window_rect(hwnd)
        if not rect:
            return True
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 8 or height <= 8:
            return True
        if rect.left <= point.x <= rect.right and rect.top <= point.y <= rect.bottom:
            candidates.append((hwnd, rect, title))
            return False
        return True

    user32.EnumWindows(_windows_enum_proc_type()(enum_proc), 0)
    return candidates[0] if candidates else None


class WindowsWindowSelectorOverlay(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        x, y, width, height = windows_virtual_screen_geometry()
        self.screen_geometry = QRect(int(x), int(y), int(width or 1), int(height or 1))
        self.hover_rect = QRect()
        self.hover_title = ""
        self.selected_result = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setWindowOpacity(0.22)
        self.setGeometry(self.screen_geometry)

    def select(self):
        accepted = getattr(QDialog, "Accepted", None)
        if accepted is None and hasattr(QDialog, "DialogCode"):
            accepted = QDialog.DialogCode.Accepted
        return self.selected_result if self.exec_() == accepted else None

    def _physical_to_overlay_point(self, x, y):
        screen = self.screen_geometry
        scale_x = float(self.width() or 1) / float(screen.width() or 1)
        scale_y = float(self.height() or 1) / float(screen.height() or 1)
        return QPoint(
            int(round((int(x) - screen.x()) * scale_x)),
            int(round((int(y) - screen.y()) * scale_y)),
        )

    def _update_hover(self):
        cursor_pos = _windows_cursor_pos()
        if cursor_pos is None:
            return None
        picked = _windows_pick_window_at(cursor_pos[0], cursor_pos[1])
        if not picked:
            self.hover_rect = QRect()
            self.hover_title = ""
            self.update()
            return None
        _hwnd, rect, title = picked
        self.hover_rect = QRect(
            self._physical_to_overlay_point(rect.left, rect.top),
            self._physical_to_overlay_point(rect.right, rect.bottom),
        ).normalized()
        self.hover_title = title
        self.update()
        return picked

    def mouseMoveEvent(self, event):
        self._update_hover()

    def mouseReleaseEvent(self, event):
        picked = self._update_hover()
        if not picked:
            self.reject()
            return
        hwnd, rect, title = picked
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width > 8 and height > 8:
            hwnd_value = _windows_hwnd_value(hwnd)
            log.info(
                "Selected Windows window: hwnd=%s title=%s x=%s y=%s width=%s height=%s",
                hwnd_value, title, int(rect.left), int(rect.top), width, height,
            )
            self.selected_result = int(rect.left), int(rect.top), width, height, str(hwnd_value)
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 95))
        if self.hover_rect.isValid():
            painter.setPen(QPen(QColor(64, 145, 255), 3))
            painter.fillRect(self.hover_rect, QColor(64, 145, 255, 45))
            painter.drawRect(self.hover_rect)


def pick_windows_window(parent=None):
    overlay = WindowsWindowSelectorOverlay(parent)
    return overlay.select()


def pick_x11_window_with_xdotool():
    if not shutil.which("xdotool"):
        return None
    try:
        selected = subprocess.run(  # nosec B603 -- fixed argv list, no shell
            ["xdotool", "selectwindow"],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
        window_id = selected.stdout.strip()
        if not re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)", window_id):
            return None
        geometry = subprocess.run(  # nosec B603 -- validated ID, argv list, no shell
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
        result = subprocess.run(  # nosec B603 -- fixed argv list, no shell
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
