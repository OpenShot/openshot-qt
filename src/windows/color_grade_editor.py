"""
 @file
 @brief Rich popup editors for ColorGrade curve and wheel properties
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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

import copy
import math

from qt_api import Qt, QPointF, QRectF, QSize, pyqtSignal, QShortcut, QKeySequence
from qt_api import QColor, QPainter, QPen, QBrush, QPainterPath, QPixmap, QIcon
from qt_api import QWidget, QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QAction
from qt_api import QDialogButtonBox
from qt_api import QFontMetrics, QSizePolicy
from qt_api import QLineEdit, QEvent, QLinearGradient

from classes.app import get_app
from windows.views.menu import StyledContextMenu, populate_keyframe_context_menu
from windows.color_picker import ColorPicker
import openshot


BROADCAST_HUE_ANCHORS = [
    (51.65, 300.0),
    (108.65, 360.0),
    (170.76, 420.0),
    (231.65, 480.0),
    (288.65, 540.0),
    (350.76, 600.0),
]


def _wrap_angle(angle):
    return (angle + 360.0) % 360.0


def _display_hue_for_scope_angle(angle_deg):
    wrapped = _wrap_angle(angle_deg)
    if wrapped < BROADCAST_HUE_ANCHORS[0][0]:
        wrapped += 360.0
    extended = BROADCAST_HUE_ANCHORS + [(BROADCAST_HUE_ANCHORS[0][0] + 360.0, BROADCAST_HUE_ANCHORS[0][1] + 360.0)]
    for index in range(len(BROADCAST_HUE_ANCHORS)):
        a0, h0 = extended[index]
        a1, h1 = extended[index + 1]
        if a0 <= wrapped <= a1:
            span = max(1e-6, a1 - a0)
            t = (wrapped - a0) / span
            return (h0 + ((h1 - h0) * t)) % 360.0
    return BROADCAST_HUE_ANCHORS[0][1] % 360.0


def scope_angle_for_display_hue(hue_deg):
    display_hue = hue_deg % 360.0
    if display_hue < 300.0:
        display_hue += 360.0
    anchors = [(display, angle) for angle, display in BROADCAST_HUE_ANCHORS]
    extended = anchors + [(anchors[0][0] + 360.0, anchors[0][1] + 360.0)]
    for index in range(len(anchors)):
        h0, a0 = extended[index]
        h1, a1 = extended[index + 1]
        if h0 <= display_hue <= h1:
            span = max(1e-6, h1 - h0)
            t = (display_hue - h0) / span
            return _wrap_angle(a0 + ((a1 - a0) * t))
    return _wrap_angle(BROADCAST_HUE_ANCHORS[0][0])


def draw_broadcast_hue_ring(painter, center, radius, ring_width, alpha=255):
    painter.save()
    pen = QPen(QColor(255, 255, 255, alpha), ring_width)
    pen.setCapStyle(Qt.FlatCap)
    painter.setPen(pen)
    for step in range(720):
        scope_angle = step * 0.5
        color = QColor.fromHsv(int(_display_hue_for_scope_angle(scope_angle)) % 360, 255, 255, alpha)
        pen.setColor(color)
        painter.setPen(pen)
        angle0 = math.radians(scope_angle)
        angle1 = math.radians(scope_angle + 0.75)
        x0 = center.x() + (math.cos(angle0) * radius)
        y0 = center.y() - (math.sin(angle0) * radius)
        x1 = center.x() + (math.cos(angle1) * radius)
        y1 = center.y() - (math.sin(angle1) * radius)
        painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    painter.restore()


def _keyframe_value(frame_number=1.0, value=0.0, interpolation=openshot.CONSTANT):
    return {
        "Points": [{
            "co": {"X": float(frame_number), "Y": float(value)},
            "interpolation": int(interpolation),
        }]
    }


def _normalize_keyframe_data(data, default_value=0.0):
    if isinstance(data, dict) and isinstance(data.get("Points"), list):
        points = []
        for point in data["Points"]:
            try:
                normalized_point = {
                    "co": {
                        "X": float(point.get("co", {}).get("X", 1.0)),
                        "Y": float(point.get("co", {}).get("Y", default_value)),
                    },
                    "interpolation": int(point.get("interpolation", openshot.LINEAR)),
                }
                handle_left = point.get("handle_left")
                handle_right = point.get("handle_right")
                if isinstance(handle_left, dict):
                    normalized_point["handle_left"] = {
                        "X": float(handle_left.get("X", 0.5)),
                        "Y": float(handle_left.get("Y", 1.0)),
                    }
                if isinstance(handle_right, dict):
                    normalized_point["handle_right"] = {
                        "X": float(handle_right.get("X", 0.5)),
                        "Y": float(handle_right.get("Y", 0.0)),
                    }
                if "handle_type" in point:
                    normalized_point["handle_type"] = int(point.get("handle_type", openshot.AUTO))
                points.append(normalized_point)
            except (TypeError, ValueError, AttributeError):
                continue
        if points:
            points.sort(key=lambda point: point["co"]["X"])
            return {"Points": points}

    if isinstance(data, (int, float, bool)):
        return _keyframe_value(value=float(data))
    return _keyframe_value(value=float(default_value))


def _evaluate_keyframe(data, frame_number, default_value=0.0):
    normalized = _normalize_keyframe_data(data, default_value)
    points = normalized.get("Points", [])
    if not points:
        try:
            return float(default_value)
        except (TypeError, ValueError):
            return 0.0

    frame_value = float(frame_number)
    if frame_value <= points[0]["co"]["X"]:
        return float(points[0]["co"]["Y"])

    for index in range(1, len(points)):
        left = points[index - 1]
        right = points[index]
        right_x = float(right["co"]["X"])
        if frame_value > right_x:
            continue
        left_x = float(left["co"]["X"])
        left_y = float(left["co"]["Y"])
        right_y = float(right["co"]["Y"])
        if abs(frame_value - right_x) < 0.00001:
            return right_y
        interpolation = int(right.get("interpolation", openshot.BEZIER))
        if interpolation == openshot.CONSTANT or abs(right_x - left_x) < 0.00001:
            return left_y
        progress = (frame_value - left_x) / (right_x - left_x)
        progress = max(0.0, min(1.0, progress))
        return left_y + ((right_y - left_y) * progress)

    return float(points[-1]["co"]["Y"])


def _set_keyframe_value(data, frame_number, value, interpolation=openshot.BEZIER):
    normalized = _normalize_keyframe_data(data, value)
    # Normalization already creates independent points and handles.
    points = normalized["Points"]
    target_frame = int(frame_number)
    for point in points:
        if int(round(point["co"]["X"])) == target_frame:
            point["co"]["Y"] = float(value)
            return {"Points": points}

    points.append({
        "co": {"X": float(target_frame), "Y": float(value)},
        "interpolation": int(interpolation),
    })
    points.sort(key=lambda point: point["co"]["X"])
    return {"Points": points}


def _normalize_color_data(data, default_color="#ffffff"):
    color = QColor(default_color)
    if isinstance(data, dict):
        return {
            "red": _normalize_keyframe_data(data.get("red"), color.red()),
            "green": _normalize_keyframe_data(data.get("green"), color.green()),
            "blue": _normalize_keyframe_data(data.get("blue"), color.blue()),
            "alpha": _normalize_keyframe_data(data.get("alpha"), color.alpha()),
        }

    if isinstance(data, str):
        candidate = QColor(data)
        if candidate.isValid():
            color = candidate

    return {
        "red": _keyframe_value(value=color.red()),
        "green": _keyframe_value(value=color.green()),
        "blue": _keyframe_value(value=color.blue()),
        "alpha": _keyframe_value(value=color.alpha()),
    }


def _evaluate_color(data, frame_number, default_color="#ffffff"):
    normalized = _normalize_color_data(data, default_color)
    return QColor(
        int(round(_evaluate_keyframe(normalized["red"], frame_number, 255.0))),
        int(round(_evaluate_keyframe(normalized["green"], frame_number, 255.0))),
        int(round(_evaluate_keyframe(normalized["blue"], frame_number, 255.0))),
        int(round(_evaluate_keyframe(normalized["alpha"], frame_number, 255.0))),
    )


def _set_color_value(data, frame_number, color, interpolation=openshot.BEZIER):
    current = _normalize_color_data(data)
    return {
        "red": _set_keyframe_value(current["red"], frame_number, color.red(), interpolation),
        "green": _set_keyframe_value(current["green"], frame_number, color.green(), interpolation),
        "blue": _set_keyframe_value(current["blue"], frame_number, color.blue(), interpolation),
        "alpha": _set_keyframe_value(current["alpha"], frame_number, color.alpha(), interpolation),
    }


def _default_curve_node(node_id, x_value, y_value, frame_number=1):
    return {
        "id": int(node_id),
        "x": _keyframe_value(frame_number=frame_number, value=x_value, interpolation=openshot.LINEAR),
        "y": _keyframe_value(frame_number=frame_number, value=y_value, interpolation=openshot.LINEAR),
        "left_handle_x": _keyframe_value(frame_number=frame_number, value=0.5, interpolation=openshot.LINEAR),
        "left_handle_y": _keyframe_value(frame_number=frame_number, value=1.0, interpolation=openshot.LINEAR),
        "right_handle_x": _keyframe_value(frame_number=frame_number, value=0.5, interpolation=openshot.LINEAR),
        "right_handle_y": _keyframe_value(frame_number=frame_number, value=0.0, interpolation=openshot.LINEAR),
        "interpolation": int(openshot.LINEAR),
        "handle_type": int(openshot.AUTO),
    }


def default_curve_data():
    return {
        "enabled": _keyframe_value(value=1.0),
        "nodes": [
            _default_curve_node(0, 0.0, 0.0),
            _default_curve_node(1, 1.0, 1.0),
        ],
    }


def normalize_curve_data(data):
    data = data or {}
    nodes = []
    for index, node in enumerate(data.get("nodes") or []):
        try:
            node_id = int(node.get("id", index))
        except (TypeError, ValueError, AttributeError):
            node_id = index
        nodes.append({
            "id": node_id,
            "x": _normalize_keyframe_data(node.get("x"), 0.0),
            "y": _normalize_keyframe_data(node.get("y"), 0.0),
            "left_handle_x": _normalize_keyframe_data(node.get("left_handle_x"), 0.5),
            "left_handle_y": _normalize_keyframe_data(node.get("left_handle_y"), 1.0),
            "right_handle_x": _normalize_keyframe_data(node.get("right_handle_x"), 0.5),
            "right_handle_y": _normalize_keyframe_data(node.get("right_handle_y"), 0.0),
            "interpolation": int(node.get("interpolation", openshot.LINEAR)),
            "handle_type": int(node.get("handle_type", openshot.AUTO)),
        })
    if len(nodes) < 2:
        return default_curve_data()
    return {
        "enabled": _normalize_keyframe_data(data.get("enabled"), 1.0),
        "nodes": nodes,
    }


def curve_enabled_at_frame(data, frame_number):
    curve = normalize_curve_data(data)
    return _evaluate_keyframe(curve["enabled"], frame_number, 1.0) >= 0.5


def curve_nodes_at_frame(data, frame_number):
    curve = normalize_curve_data(data)
    evaluated = []
    for node in curve["nodes"]:
        evaluated.append({
            "id": node["id"],
            "x": max(0.0, min(1.0, _evaluate_keyframe(node["x"], frame_number, 0.0))),
            "y": max(0.0, min(1.0, _evaluate_keyframe(node["y"], frame_number, 0.0))),
            "left_handle_x": max(0.0, min(1.0, _evaluate_keyframe(node["left_handle_x"], frame_number, 0.5))),
            "left_handle_y": max(0.0, min(1.0, _evaluate_keyframe(node["left_handle_y"], frame_number, 1.0))),
            "right_handle_x": max(0.0, min(1.0, _evaluate_keyframe(node["right_handle_x"], frame_number, 0.5))),
            "right_handle_y": max(0.0, min(1.0, _evaluate_keyframe(node["right_handle_y"], frame_number, 0.0))),
            "interpolation": int(node.get("interpolation", openshot.LINEAR)),
            "handle_type": int(node.get("handle_type", openshot.AUTO)),
        })
    evaluated.sort(key=lambda node: (node["x"], node["id"]))
    return evaluated


def curve_summary(data, frame_number):
    curve = normalize_curve_data(data)
    summary = f"{len(curve['nodes'])} nodes"
    if not curve_enabled_at_frame(curve, frame_number):
        return f"Disabled, {summary}"
    return summary


def default_wheels_data():
    return {
        "enabled_keyframes": _keyframe_value(value=1.0),
        "global": {"color_keyframes": _normalize_color_data("#ffffff"), "amount_keyframes": _keyframe_value(value=0.0), "luma_keyframes": _keyframe_value(value=0.0)},
        "shadows": {"color_keyframes": _normalize_color_data("#ffffff"), "amount_keyframes": _keyframe_value(value=0.0), "luma_keyframes": _keyframe_value(value=0.0)},
        "midtones": {"color_keyframes": _normalize_color_data("#ffffff"), "amount_keyframes": _keyframe_value(value=0.0), "luma_keyframes": _keyframe_value(value=0.0)},
        "highlights": {"color_keyframes": _normalize_color_data("#ffffff"), "amount_keyframes": _keyframe_value(value=0.0), "luma_keyframes": _keyframe_value(value=0.0)},
    }


NEUTRAL_WHEEL_COLOR = "#ffffff"
NEUTRAL_PUCK_COLOR = "#ffffff"
ACHROMATIC_SATURATION_THRESHOLD = 0.02


def _mix_color(first, second, ratio):
    ratio = max(0.0, min(1.0, float(ratio)))
    return QColor(
        int(round(first.red() + ((second.red() - first.red()) * ratio))),
        int(round(first.green() + ((second.green() - first.green()) * ratio))),
        int(round(first.blue() + ((second.blue() - first.blue()) * ratio))),
        int(round(first.alpha() + ((second.alpha() - first.alpha()) * ratio))),
    )


def disabled_control_color(widget, text=False):
    palette = widget.palette()
    base = palette.base().color()
    mid = palette.mid().color()
    text_color = palette.text().color()
    if text:
        return _mix_color(mid, text_color, 0.32)
    return _mix_color(base, mid, 0.36)


def is_neutral_wheel(data):
    try:
        return float((data or {}).get("amount", 0.0)) <= 0.0001
    except (TypeError, ValueError, AttributeError):
        return True


def display_wheel_color(data):
    if is_neutral_wheel(data):
        return QColor(Qt.white)
    color = QColor((data or {}).get("color", NEUTRAL_WHEEL_COLOR))
    return color if color.isValid() else QColor(Qt.white)


def selected_wheel_color(data):
    color = QColor((data or {}).get("color", NEUTRAL_WHEEL_COLOR))
    return color if color.isValid() else QColor(Qt.white)


def is_achromatic_color(color):
    if not isinstance(color, QColor) or not color.isValid():
        return True
    saturation = color.hsvSaturationF()
    if saturation < 0.0:
        saturation = color.saturationF()
    return saturation < ACHROMATIC_SATURATION_THRESHOLD


def puck_display_color(data):
    amount = 0.0
    try:
        amount = max(0.0, min(1.0, float((data or {}).get("amount", 0.0))))
    except (TypeError, ValueError, AttributeError):
        pass

    base = QColor(NEUTRAL_PUCK_COLOR)
    if amount <= 0.0001:
        return base

    target = display_wheel_color(data)
    return QColor(
        int(round(base.red() + ((target.red() - base.red()) * amount))),
        int(round(base.green() + ((target.green() - base.green()) * amount))),
        int(round(base.blue() + ((target.blue() - base.blue()) * amount))),
    )


def normalize_single_wheel_data(data):
    normalized = normalize_wheels_data({"global": data})
    return wheel_snapshot(normalized["global"], 1)


def normalize_wheels_data(data):
    # Each channel normalizer builds fresh data; copying the input first would
    # duplicate the entire animation only to immediately rebuild it again.
    data = data or {}
    normalized = default_wheels_data()
    normalized["enabled_keyframes"] = _normalize_keyframe_data(
        data.get("enabled_keyframes", data.get("enabled")),
        1.0,
    )
    for name, wheel in normalized.items():
        if name == "enabled_keyframes":
            continue
        source = data.get(name) or {}
        wheel["color_keyframes"] = _normalize_color_data(source.get("color_keyframes", source.get("color")), "#ffffff")
        wheel["amount_keyframes"] = _normalize_keyframe_data(source.get("amount_keyframes", source.get("amount")), 0.0)
        wheel["luma_keyframes"] = _normalize_keyframe_data(source.get("luma_keyframes", source.get("luma")), 0.0)
    return normalized


def colorgrade_keyframe_frames(data, property_type):
    """Return the set of unique frame numbers that have keyframes for a colorgrade property."""
    frame_set = set()

    def _collect(kf_data):
        if isinstance(kf_data, dict):
            for pt in kf_data.get("Points", []):
                try:
                    frame_set.add(int(round(float(pt["co"]["X"]))))
                except (KeyError, TypeError, ValueError):
                    pass

    if property_type == "colorgrade_curve":
        curve = normalize_curve_data(data)
        _collect(curve.get("enabled"))
        for node in curve.get("nodes", []):
            for k in ("x", "y", "left_handle_x", "left_handle_y", "right_handle_x", "right_handle_y"):
                _collect(node.get(k))
    elif property_type == "colorgrade_wheels":
        wheels = normalize_wheels_data(data)
        _collect(wheels.get("enabled_keyframes"))
        for section in ("global", "shadows", "midtones", "highlights"):
            wheel = wheels.get(section, {})
            color_kf = wheel.get("color_keyframes") or {}
            for channel in ("red", "green", "blue", "alpha"):
                _collect(color_kf.get(channel))
            _collect(wheel.get("amount_keyframes"))
            _collect(wheel.get("luma_keyframes"))
    return frame_set


def wheels_enabled_at_frame(data, frame_number):
    wheels = data or {}
    return _evaluate_keyframe(wheels.get("enabled_keyframes", wheels.get("enabled")), frame_number, 1.0) >= 0.5


def wheel_snapshot(data, frame_number):
    wheel = data or {}
    color = _evaluate_color(wheel.get("color_keyframes", wheel.get("color")), frame_number, NEUTRAL_WHEEL_COLOR)
    return {
        "color": color.name(),
        "amount": max(0.0, min(1.0, _evaluate_keyframe(wheel.get("amount_keyframes", wheel.get("amount")), frame_number, 0.0))),
        "luma": max(-1.0, min(1.0, _evaluate_keyframe(wheel.get("luma_keyframes", wheel.get("luma")), frame_number, 0.0))),
    }


def wheels_snapshot(data, frame_number):
    # Snapshot helpers normalize only the channels they read.
    wheels = data or {}
    snapshot = {"enabled": wheels_enabled_at_frame(wheels, frame_number)}
    for name in ("global", "shadows", "midtones", "highlights"):
        snapshot[name] = wheel_snapshot(wheels.get(name), frame_number)
    return snapshot


def wheels_summary(data, frame_number):
    if wheels_enabled_at_frame(data, frame_number):
        return "Global / Shadows / Midtones / Highlights"
    return "Disabled"


def _draw_keyframe_marker(painter, center, interpolation, size, fill_color, border_color):
    half = size / 2.0
    rect = QRectF(center.x() - half, center.y() - half, size, size)
    painter.setPen(QPen(border_color, 1.2))
    painter.setBrush(QBrush(fill_color))
    if interpolation == openshot.LINEAR:
        painter.drawRect(rect)
    elif interpolation == openshot.CONSTANT:
        path = QPainterPath()
        path.moveTo(center.x(), rect.top())
        path.lineTo(rect.right(), center.y())
        path.lineTo(center.x(), rect.bottom())
        path.lineTo(rect.left(), center.y())
        path.closeSubpath()
        painter.drawPath(path)
    else:
        painter.drawEllipse(rect)


def _keyframe_marker_icon(interpolation, size=12, fill_color="#4d7bff", border_color="#ffffff"):
    pixmap = QPixmap(size + 4, size + 4)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    _draw_keyframe_marker(
        painter,
        QPointF(pixmap.width() / 2.0, pixmap.height() / 2.0),
        interpolation,
        float(size),
        QColor(fill_color),
        QColor(border_color),
    )
    painter.end()
    return QIcon(pixmap)


class ColorWheelControl(QWidget):
    changed = pyqtSignal()
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, wheel_data=None, parent=None, title=""):
        super().__init__(parent)
        self._data = normalize_single_wheel_data(wheel_data)
        self._dragging = False
        self._title = title
        self.setMinimumSize(QSize(120, 120))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return width

    def sizeHint(self):
        return QSize(120, 120)

    def wheel_data(self):
        return copy.deepcopy(self._data)

    def set_wheel_data(self, wheel_data):
        self._data = normalize_single_wheel_data(wheel_data)
        self.update()
        self.changed.emit()

    def _center_and_radius(self):
        radius = min(self.width(), self.height()) * 0.47
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        return center, radius

    def _inner_radius(self):
        _, radius = self._center_and_radius()
        ring_width = max(6.0, radius * 0.16)
        return max(1.0, radius - ring_width - 1.0)

    def _puck_position(self):
        center, _ = self._center_and_radius()
        radius = self._inner_radius()
        color = display_wheel_color(self._data)
        hue = color.hueF() if color.hueF() >= 0 else 0.0
        angle = math.radians(scope_angle_for_display_hue(hue * 360.0))
        amount = float(self._data["amount"]) * radius
        return QPointF(center.x() + math.cos(angle) * amount, center.y() - math.sin(angle) * amount)

    def _normalize_neutral_state(self):
        if float(self._data.get("amount", 0.0)) <= 0.0001:
            self._data["amount"] = 0.0
            self._data["color"] = NEUTRAL_WHEEL_COLOR

    def _update_from_position(self, pos):
        center, _ = self._center_and_radius()
        radius = self._inner_radius()
        dx = pos.x() - center.x()
        dy = center.y() - pos.y()
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += math.tau
        distance = min(radius, math.hypot(dx, dy))
        hue = _display_hue_for_scope_angle(math.degrees(angle)) / 360.0
        color = QColor.fromHsvF(hue, 1.0, 1.0)
        self._data["color"] = color.name()
        self._data["amount"] = 0.0 if radius <= 0 else (distance / radius)
        self._normalize_neutral_state()
        self.update()
        self.changed.emit()

    def mousePressEvent(self, event):
        if not self.isEnabled():
            super().mousePressEvent(event)
            return
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self._dragging = True
        self.dragStarted.emit()
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        self._update_from_position(pos)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._dragging or not self.isEnabled():
            return
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        self._update_from_position(pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.dragFinished.emit()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self.isEnabled():
            super().mouseDoubleClickEvent(event)
            return
        self._data["amount"] = 0.0
        self._data["color"] = NEUTRAL_WHEEL_COLOR
        self.update()
        self.changed.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center, radius = self._center_and_radius()
        enabled = self.isEnabled()
        disabled_color = disabled_control_color(self)
        disabled_text_color = disabled_control_color(self, text=True)

        ring_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)
        ring_width = max(6.0, radius * 0.16)
        ring_path = QPainterPath()
        ring_path.addEllipse(ring_rect)
        inner_path = QPainterPath()
        inner_radius = radius - ring_width
        inner_path.addEllipse(QRectF(center.x() - inner_radius, center.y() - inner_radius, inner_radius * 2.0, inner_radius * 2.0))
        ring_path = ring_path.subtracted(inner_path)
        if enabled:
            painter.save()
            painter.setClipPath(ring_path)
            draw_broadcast_hue_ring(painter, center, radius - (ring_width * 0.5), ring_width + 1.0)
            painter.restore()
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(disabled_color))
            painter.drawPath(ring_path)

        outline_color = disabled_color if not enabled else self.palette().mid().color()
        painter.setPen(QPen(outline_color, 1.0))
        painter.setBrush(QBrush(self.palette().base()))
        painter.drawEllipse(center, inner_radius - 1.0, inner_radius - 1.0)

        painter.setPen(QPen(outline_color, 1.0, Qt.DashLine))
        painter.drawLine(QPointF(center.x() - inner_radius, center.y()), QPointF(center.x() + inner_radius, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - inner_radius), QPointF(center.x(), center.y() + inner_radius))

        puck = self._puck_position()
        painter.setPen(QPen(Qt.white if enabled else disabled_text_color, 1.0))
        painter.setBrush(QBrush(puck_display_color(self._data) if enabled else disabled_color))
        painter.drawEllipse(puck, 5.0, 5.0)

        if self._title:
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(Qt.white if enabled else disabled_text_color))
            text_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2.0, ring_width)
            painter.drawText(text_rect, Qt.AlignCenter, self._title)

        painter.end()


class CurvePreviewWidget(QWidget):
    curveChanged = pyqtSignal(dict)
    editFrameRequested = pyqtSignal()
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, curve_data=None, frame_number=1, parent=None):
        super().__init__(parent)
        self.setMinimumSize(QSize(240, 240))
        self._curve_data = normalize_curve_data(curve_data)
        self._frame_number = int(frame_number)
        self._drag_target = None
        self._padding = 18.0
        self._selected_node_id = None
        self._curve_icons = {
            openshot.BEZIER: _keyframe_marker_icon(openshot.BEZIER),
            openshot.LINEAR: _keyframe_marker_icon(openshot.LINEAR),
            openshot.CONSTANT: _keyframe_marker_icon(openshot.CONSTANT),
        }

    def curve_data(self):
        return normalize_curve_data(self._curve_data)

    def set_curve_data(self, curve_data):
        self._curve_data = normalize_curve_data(curve_data)
        self.update()
        self.curveChanged.emit(self.curve_data())

    def set_frame_number(self, frame_number):
        self._frame_number = int(frame_number)
        self.update()

    def reset(self):
        self.set_curve_data(default_curve_data())

    def _graph_rect(self):
        return QRectF(
            self._padding,
            self._padding,
            max(10.0, self.width() - (self._padding * 2.0)),
            max(10.0, self.height() - (self._padding * 2.0)),
        )

    def _point_to_screen(self, point):
        rect = self._graph_rect()
        x = rect.left() + (point["x"] * rect.width())
        y = rect.bottom() - (point["y"] * rect.height())
        return QPointF(x, y)

    def _screen_to_point(self, pos):
        rect = self._graph_rect()
        x = max(0.0, min(1.0, (pos.x() - rect.left()) / rect.width()))
        y = max(0.0, min(1.0, (rect.bottom() - pos.y()) / rect.height()))
        return {"x": x, "y": y}

    def _evaluated_nodes(self):
        return curve_nodes_at_frame(self._curve_data, self._frame_number)

    def _node_sort_index(self, node_id):
        for idx, node in enumerate(self._evaluated_nodes()):
            if node["id"] == node_id:
                return idx
        return None

    def _get_node(self, node_id):
        for node in self._curve_data["nodes"]:
            if node["id"] == node_id:
                return node
        return None

    def _curve_icon(self, interpolation):
        return self._curve_icons.get(interpolation) or self._curve_icons[openshot.BEZIER]

    def _find_point_index(self, pos, radius=10.0):
        for idx, point in enumerate(self._evaluated_nodes()):
            if (self._point_to_screen(point) - pos).manhattanLength() <= radius:
                return idx
        return None

    def _segment_nodes(self, node_id, side):
        nodes = self._evaluated_nodes()
        sort_index = self._node_sort_index(node_id)
        if sort_index is None:
            return None, None
        if side == "left":
            if sort_index <= 0:
                return None, None
            return nodes[sort_index - 1], nodes[sort_index]
        if sort_index >= len(nodes) - 1:
            return None, None
        return nodes[sort_index], nodes[sort_index + 1]

    def _handle_point(self, node_id, side):
        left, right = self._segment_nodes(node_id, side)
        if not left or not right:
            return None

        if side == "left" and right["interpolation"] != openshot.BEZIER:
            return None
        if side == "right" and right["interpolation"] != openshot.BEZIER:
            return None

        delta_x = right["x"] - left["x"]
        delta_y = right["y"] - left["y"]
        if side == "left":
            return {
                "x": left["x"] + (right["left_handle_x"] * delta_x),
                "y": left["y"] + (right["left_handle_y"] * delta_y),
            }
        return {
            "x": left["x"] + (left["right_handle_x"] * delta_x),
            "y": left["y"] + (left["right_handle_y"] * delta_y),
        }

    def _find_handle_hit(self, pos, radius=8.0):
        for node in self._evaluated_nodes():
            for side in ("left", "right"):
                handle = self._handle_point(node["id"], side)
                if handle is None:
                    continue
                if (self._point_to_screen(handle) - pos).manhattanLength() <= radius:
                    return {"type": "handle", "node_id": node["id"], "side": side}
        return None

    def _set_handle_value(self, node, side, x_value, y_value):
        if side == "left":
            node["left_handle_x"] = _set_keyframe_value(node.get("left_handle_x"), self._frame_number, x_value)
            node["left_handle_y"] = _set_keyframe_value(node.get("left_handle_y"), self._frame_number, y_value)
        else:
            node["right_handle_x"] = _set_keyframe_value(node.get("right_handle_x"), self._frame_number, x_value)
            node["right_handle_y"] = _set_keyframe_value(node.get("right_handle_y"), self._frame_number, y_value)

    def _set_handle_from_position(self, node_id, side, pos, modifiers):
        left, right = self._segment_nodes(node_id, side)
        node = self._get_node(node_id)
        if not left or not right or not node:
            return

        point = self._screen_to_point(pos)
        delta_x = right["x"] - left["x"]
        delta_y = right["y"] - left["y"]
        base_x = left["x"]
        base_y = left["y"]

        if abs(delta_x) < 0.00001:
            handle_x = 0.5
        else:
            handle_x = (point["x"] - base_x) / delta_x
        if abs(delta_y) < 0.00001:
            handle_y = 0.0 if side == "right" else 1.0
        else:
            handle_y = (point["y"] - base_y) / delta_y

        handle_x = max(-2.0, min(2.0, handle_x))
        handle_y = max(-2.0, min(2.0, handle_y))
        self._set_handle_value(node, side, handle_x, handle_y)

        if modifiers & Qt.ShiftModifier:
            opposite_node = node
            if side == "left":
                opposite_left, opposite_right = self._segment_nodes(node_id, "right")
                if opposite_left and opposite_right:
                    self._set_handle_value(opposite_node, "right", 1.0 - handle_x, 1.0 - handle_y)
            else:
                opposite_left, opposite_right = self._segment_nodes(node_id, "left")
                if opposite_left and opposite_right:
                    self._set_handle_value(opposite_node, "left", 1.0 - handle_x, 1.0 - handle_y)
        elif modifiers & Qt.ControlModifier:
            opposite_node = node
            if side == "left":
                current_x = _evaluate_keyframe(node.get("right_handle_x"), self._frame_number, 0.5)
                current_y = _evaluate_keyframe(node.get("right_handle_y"), self._frame_number, 0.0)
                left_current_x = _evaluate_keyframe(node.get("left_handle_x"), self._frame_number, 0.5)
                left_current_y = _evaluate_keyframe(node.get("left_handle_y"), self._frame_number, 1.0)
                self._set_handle_value(opposite_node, "right", current_x + (handle_x - left_current_x), current_y + (handle_y - left_current_y))
            else:
                current_x = _evaluate_keyframe(node.get("left_handle_x"), self._frame_number, 0.5)
                current_y = _evaluate_keyframe(node.get("left_handle_y"), self._frame_number, 1.0)
                right_current_x = _evaluate_keyframe(node.get("right_handle_x"), self._frame_number, 0.5)
                right_current_y = _evaluate_keyframe(node.get("right_handle_y"), self._frame_number, 0.0)
                self._set_handle_value(opposite_node, "left", current_x + (handle_x - right_current_x), current_y + (handle_y - right_current_y))

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        if event.button() == Qt.RightButton:
            hit_index = self._find_point_index(pos)
            if hit_index is not None:
                self._selected_node_id = self._evaluated_nodes()[hit_index]["id"]
                self._show_node_menu(event.globalPos() if hasattr(event, "globalPos") else self.mapToGlobal(pos.toPoint()))
            return

        self.editFrameRequested.emit()
        handle_hit = self._find_handle_hit(pos)
        if handle_hit is not None:
            self._drag_target = handle_hit
            self._selected_node_id = handle_hit["node_id"]
            self.dragStarted.emit()
            return

        hit_index = self._find_point_index(pos)
        if hit_index is not None:
            self._drag_target = {"type": "node", "node_id": self._evaluated_nodes()[hit_index]["id"]}
            self._selected_node_id = self._drag_target["node_id"]
            self.dragStarted.emit()
            return

        new_point = self._screen_to_point(pos)
        next_id = max([node["id"] for node in self._curve_data["nodes"]] + [-1]) + 1
        new_node = _default_curve_node(next_id, new_point["x"], new_point["y"], self._frame_number)
        self._curve_data["nodes"].append(new_node)
        self._curve_data = normalize_curve_data(self._curve_data)
        self._drag_target = {"type": "node", "node_id": next_id}
        self._selected_node_id = next_id
        self.dragStarted.emit()
        self.update()
        self.curveChanged.emit(self.curve_data())

    def mouseMoveEvent(self, event):
        if self._drag_target is None:
            return
        self.editFrameRequested.emit()
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        if self._drag_target["type"] == "handle":
            self._set_handle_from_position(
                self._drag_target["node_id"],
                self._drag_target["side"],
                pos,
                event.modifiers() if hasattr(event, "modifiers") else Qt.NoModifier,
            )
        else:
            point = self._screen_to_point(pos)
            sort_index = self._node_sort_index(self._drag_target["node_id"])
            if sort_index == 0:
                point["x"] = 0.0
            elif sort_index == len(self._curve_data["nodes"]) - 1:
                point["x"] = 1.0
            node = self._get_node(self._drag_target["node_id"])
            if not node:
                return
            node["x"] = _set_keyframe_value(node["x"], self._frame_number, point["x"])
            node["y"] = _set_keyframe_value(node["y"], self._frame_number, point["y"])
        self._curve_data = normalize_curve_data(self._curve_data)
        self.update()
        self.curveChanged.emit(self.curve_data())

    def mouseReleaseEvent(self, event):
        if self._drag_target is not None:
            self._drag_target = None
            self.dragFinished.emit()
        super().mouseReleaseEvent(event)

    def _remove_selected_node(self):
        if self._selected_node_id is None or len(self._curve_data["nodes"]) <= 2:
            return
        sort_index = self._node_sort_index(self._selected_node_id)
        if sort_index in (0, len(self._curve_data["nodes"]) - 1):
            return
        self.dragStarted.emit()
        self._curve_data["nodes"] = [
            node for node in self._curve_data["nodes"] if node["id"] != self._selected_node_id
        ]
        self._curve_data = normalize_curve_data(self._curve_data)
        self.update()
        self.curveChanged.emit(self.curve_data())
        self.dragFinished.emit()

    def _set_selected_interpolation(self, interpolation):
        node = self._get_node(self._selected_node_id)
        if not node:
            return
        self.dragStarted.emit()
        node["interpolation"] = int(interpolation)
        self._curve_data = normalize_curve_data(self._curve_data)
        self.update()
        self.curveChanged.emit(self.curve_data())
        self.dragFinished.emit()

    def _apply_selected_bezier_preset(self, preset):
        node = self._get_node(self._selected_node_id)
        if not node:
            return

        self.dragStarted.emit()
        node["interpolation"] = int(openshot.BEZIER)

        sort_index = self._node_sort_index(self._selected_node_id)
        if sort_index is not None and sort_index > 0:
            previous_id = self._evaluated_nodes()[sort_index - 1]["id"]
            previous = self._get_node(previous_id)
            if previous:
                previous["right_handle_x"] = _set_keyframe_value(previous.get("right_handle_x"), self._frame_number, preset[0])
                previous["right_handle_y"] = _set_keyframe_value(previous.get("right_handle_y"), self._frame_number, preset[1])
            node["left_handle_x"] = _set_keyframe_value(node.get("left_handle_x"), self._frame_number, preset[2])
            node["left_handle_y"] = _set_keyframe_value(node.get("left_handle_y"), self._frame_number, preset[3])

        self._curve_data = normalize_curve_data(self._curve_data)
        self.update()
        self.curveChanged.emit(self.curve_data())
        self.dragFinished.emit()

    def _show_node_menu(self, global_pos):
        menu = StyledContextMenu(parent=self)
        sort_index = self._node_sort_index(self._selected_node_id)
        remove_enabled = sort_index not in (0, len(self._curve_data["nodes"]) - 1) and len(self._curve_data["nodes"]) > 2
        populate_keyframe_context_menu(
            menu,
            bezier_callback=self._apply_selected_bezier_preset,
            linear_callback=lambda: self._set_selected_interpolation(openshot.LINEAR),
            constant_callback=lambda: self._set_selected_interpolation(openshot.CONSTANT),
            remove_callback=self._remove_selected_node,
            remove_enabled=remove_enabled,
            bezier_icon=None,
            linear_icon=None,
            constant_icon=None,
            remove_text=get_app()._tr("Remove"),
        )
        menu.exec_(global_pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self._graph_rect()
        painter.fillRect(self.rect(), self.palette().window())
        painter.fillRect(rect, self.palette().base())

        grid_pen = QPen(self.palette().mid().color(), 1)
        painter.setPen(grid_pen)
        for tick in range(5):
            x = rect.left() + (tick * rect.width() / 4.0)
            y = rect.top() + (tick * rect.height() / 4.0)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        nodes = self._evaluated_nodes()
        is_enabled = curve_enabled_at_frame(self._curve_data, self._frame_number)
        painter.setPen(QPen(self.palette().text().color() if is_enabled else self.palette().mid().color(), 1.5))
        path = QPainterPath()
        if nodes:
            path.moveTo(self._point_to_screen(nodes[0]))
            for idx in range(1, len(nodes)):
                left = nodes[idx - 1]
                right = nodes[idx]
                if right["interpolation"] == openshot.CONSTANT:
                    step = QPointF(self._point_to_screen(right).x(), self._point_to_screen(left).y())
                    path.lineTo(step)
                    path.lineTo(self._point_to_screen(right))
                elif right["interpolation"] == openshot.LINEAR:
                    path.lineTo(self._point_to_screen(right))
                else:
                    delta_x = right["x"] - left["x"]
                    delta_y = right["y"] - left["y"]
                    c1 = {
                        "x": left["x"] + (left["right_handle_x"] * delta_x),
                        "y": left["y"] + (left["right_handle_y"] * delta_y),
                    }
                    c2 = {
                        "x": left["x"] + (right["left_handle_x"] * delta_x),
                        "y": left["y"] + (right["left_handle_y"] * delta_y),
                    }
                    path.cubicTo(self._point_to_screen(c1), self._point_to_screen(c2), self._point_to_screen(right))
            painter.drawPath(path)

        handle_pen = QPen(QColor("#ffffff") if is_enabled else self.palette().mid().color(), 1.0)
        painter.setPen(handle_pen)
        painter.setBrush(QBrush(QColor("#ffffff") if is_enabled else self.palette().mid().color()))
        for node in nodes:
            if node["interpolation"] == openshot.BEZIER:
                left_handle = self._handle_point(node["id"], "left")
                if left_handle is not None:
                    anchor = self._point_to_screen(node)
                    handle_point = self._point_to_screen(left_handle)
                    painter.drawLine(anchor, handle_point)
                    painter.drawRect(QRectF(handle_point.x() - 3.0, handle_point.y() - 3.0, 6.0, 6.0))
            right_handle = self._handle_point(node["id"], "right")
            if right_handle is not None:
                anchor = self._point_to_screen(node)
                handle_point = self._point_to_screen(right_handle)
                painter.drawLine(anchor, handle_point)
                painter.drawRect(QRectF(handle_point.x() - 3.0, handle_point.y() - 3.0, 6.0, 6.0))

        for node in nodes:
            screen_point = self._point_to_screen(node)
            _draw_keyframe_marker(
                painter,
                screen_point,
                node["interpolation"],
                9.0,
                QColor("#4d7bff") if is_enabled else self.palette().mid().color(),
                QColor("#ffffff") if is_enabled else self.palette().mid().color(),
            )

        painter.end()


class ElidedLabel(QLabel):
    """A QLabel that shows '...' when text is wider than the available width."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def paintEvent(self, event):
        painter = QPainter(self)
        elided = QFontMetrics(self.font()).elidedText(self.text(), Qt.ElideRight, self.width())
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, elided)
        painter.end()


class ColorGradeCurveDialog(QDialog):
    changeStarted = pyqtSignal()
    changeFinished = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, curve_data=None, channel="all", frame_number=1, parent=None, title=None):
        super().__init__(parent)
        _ = get_app()._tr
        self.setWindowTitle(title if title else _("Edit Color Curve"))
        self.setModal(False)
        self._frame_number = int(frame_number)
        self._widget = CurvePreviewWidget(curve_data, self._frame_number, self)

        layout = QVBoxLayout(self)
        layout.addWidget(ElidedLabel(_("Drag to reshape. Right-click points for options."), self))
        layout.addWidget(self._widget)

        button_row = QHBoxLayout()
        self.toggle_button = QPushButton(_("Disable"), self)
        self.toggle_button.clicked.connect(self._toggle_enabled)
        button_row.addWidget(self.toggle_button)

        button_row.addStretch(1)

        reset_button = QPushButton(_("Reset"), self)
        reset_button.clicked.connect(self._reset)
        button_row.addWidget(reset_button)
        layout.addLayout(button_row)
        self.channel = channel
        self._widget.dragStarted.connect(self.changeStarted)
        self._widget.dragFinished.connect(self.changeFinished)

        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(get_app().window.actionUndo_trigger)
        redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        redo_shortcut.activated.connect(get_app().window.actionRedo_trigger)
        self._shortcuts = [undo_shortcut, redo_shortcut]
        self._update_enabled_state()

    def curve_data(self):
        return self._widget.curve_data()

    def curve_widget(self):
        return self._widget

    def set_frame_number(self, frame_number):
        self._frame_number = int(frame_number)
        self._widget.set_frame_number(self._frame_number)
        self._update_enabled_state()

    def _apply_curve_change(self, curve_data):
        self.changeStarted.emit()
        self._widget.set_curve_data(curve_data)
        self.changeFinished.emit()

    def _reset(self):
        reset_curve = default_curve_data()
        reset_curve["enabled"] = copy.deepcopy(self.curve_data().get("enabled", _keyframe_value(value=1.0)))
        self._apply_curve_change(reset_curve)

    def _toggle_enabled(self):
        updated = copy.deepcopy(self.curve_data())
        next_enabled = not curve_enabled_at_frame(updated, self._frame_number)
        updated["enabled"] = _set_keyframe_value(updated.get("enabled"), self._frame_number, 1.0 if next_enabled else 0.0)
        self._apply_curve_change(updated)
        self._update_enabled_state()

    def _update_enabled_state(self):
        enabled = curve_enabled_at_frame(self.curve_data(), self._frame_number)
        _ = get_app()._tr
        self.toggle_button.setText(_("Disable") if enabled else _("Enable"))
        self._widget.setEnabled(enabled)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class WheelsPreviewWidget(QWidget):
    def __init__(self, wheels_data=None, parent=None):
        super().__init__(parent)
        self._frame_number = 1
        self._wheels_data = normalize_wheels_data(wheels_data)
        self.setMinimumHeight(72)

    def set_wheels_data(self, wheels_data):
        self._wheels_data = normalize_wheels_data(wheels_data)
        self.update()

    def set_frame_number(self, frame_number):
        self._frame_number = int(frame_number)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        wheels = wheels_snapshot(self._wheels_data, self._frame_number)
        names = ["global", "shadows", "midtones", "highlights"]
        labels = ["G", "S", "M", "H"]
        slot_width = self.width() / float(len(names))
        for idx, name in enumerate(names):
            wheel = wheels[name]
            center_x = (idx * slot_width) + (slot_width / 2.0)
            center = QPointF(center_x, 28.0)
            radius = 19.0
            painter.setPen(QPen(self.palette().mid().color(), 1))
            painter.setBrush(QBrush(self.palette().base()))
            painter.drawEllipse(center, radius, radius)
            tint = display_wheel_color(wheel)
            if is_neutral_wheel(wheel):
                tint = QColor(self.palette().base())
            else:
                tint.setAlpha(26)
            painter.setBrush(QBrush(tint))
            painter.drawEllipse(center, radius * 0.92, radius * 0.92)

            wheel_color = display_wheel_color(wheel)
            angle = math.radians(scope_angle_for_display_hue((wheel_color.hueF() if wheel_color.hueF() >= 0 else 0.0) * 360.0))
            amount = float(wheel["amount"]) * radius * 0.85
            puck = QPointF(center.x() + math.cos(angle) * amount, center.y() - math.sin(angle) * amount)
            painter.setPen(QPen(Qt.white, 1.0))
            painter.setBrush(QBrush(puck_display_color(wheel)))
            painter.drawEllipse(puck, 5.0, 5.0)

            luma_rect = QRectF(center_x - 20.0, 55.0, 40.0, 3.0)
            painter.setPen(QPen(self.palette().mid().color(), 1.0))
            painter.drawLine(QPointF(luma_rect.left(), luma_rect.center().y()), QPointF(luma_rect.right(), luma_rect.center().y()))
            value = (float(wheel["luma"]) + 1.0) / 2.0
            marker_x = luma_rect.left() + (luma_rect.width() * value)
            painter.setPen(QPen(self.palette().highlight().color(), 2.0))
            painter.drawLine(QPointF(marker_x, luma_rect.top() - 2.0), QPointF(marker_x, luma_rect.bottom() + 2.0))

            painter.setPen(QPen(self.palette().text().color(), 1))
            painter.drawText(QRectF(center_x - 16.0, 61.0, 32.0, 16.0), Qt.AlignCenter, labels[idx])

        painter.end()


class PropertySlider(QWidget):
    """Compact filled-bar slider with inline keyboard editing.

    Visually matches the properties-table slider style. Supports mouse drag to
    adjust the value and numeric key presses to enter a direct-type edit mode.
    """

    valueChanged = pyqtSignal(float)
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, min_val=0.0, max_val=1.0, value=0.0, decimals=2, parent=None):
        super().__init__(parent)
        self._min = float(min_val)
        self._max = float(max_val)
        self._value = max(self._min, min(self._max, float(value)))
        self._decimals = decimals
        self._drag_active = False
        self._editing = False
        self._keyframe_points = 1
        self._interpolation = openshot.LINEAR
        self._curve_pixmaps = {
            openshot.BEZIER: QIcon(":/curves/keyframe-%s.png" % openshot.BEZIER).pixmap(20, 20),
            openshot.LINEAR: QIcon(":/curves/keyframe-%s.png" % openshot.LINEAR).pixmap(20, 20),
            openshot.CONSTANT: QIcon(":/curves/keyframe-%s.png" % openshot.CONSTANT).pixmap(20, 20),
        }

        self.setFocusPolicy(Qt.ClickFocus)
        self.setFixedHeight(30)
        self.setCursor(Qt.SizeHorCursor)
        self.setMinimumWidth(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._edit = QLineEdit(self)
        self._edit.setAlignment(Qt.AlignCenter)
        self._edit.setFrame(False)
        self._edit.setStyleSheet("background: transparent; color: white; border: none; font-size: 11px;")
        self._edit.hide()
        self._edit.installEventFilter(self)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = max(self._min, min(self._max, float(value)))
        if not self._editing:
            self.update()

    def set_keyframe_status(self, points=1, interpolation=openshot.LINEAR):
        self._keyframe_points = max(1, int(points or 1))
        self._interpolation = int(interpolation)
        self.update()

    def _value_percent(self):
        span = self._max - self._min
        if abs(span) < 1e-12:
            return 0.0
        return (self._value - self._min) / span

    def _fmt(self, v):
        return f"{v:.{self._decimals}f}"

    def paintEvent(self, event):
        if self._editing:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())

        bg = QColor("#1e2433")
        fg = QColor("#4a6fa5")
        app = get_app()
        if app.theme_manager:
            theme = app.theme_manager.get_current_theme()
            if theme:
                bg = theme.get_color(".property_value", "background-color")
                fg = theme.get_color(".property_value", "foreground-color")
        if not self.isEnabled():
            bg = self.palette().base().color()
            fg = disabled_control_color(self)

        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, bg)

        pct = self._value_percent()
        if pct > 1e-6:
            fill_rect = QRectF(rect.x(), rect.y(), rect.width() * pct, rect.height())
            painter.setClipRect(fill_rect, Qt.IntersectClip)
            gradient = QLinearGradient(rect.topLeft(), rect.topRight())
            gradient.setColorAt(0, fg)
            gradient.setColorAt(1, fg)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(rect, 6, 6)
            painter.fillPath(fill_path, gradient)
            painter.setClipping(False)

        text_rect = QRectF(rect)
        if self._keyframe_points > 1:
            painter.drawPixmap(
                int(rect.x() + rect.width() - 26.0),
                int(rect.y() + 5.0),
                self._curve_pixmaps.get(self._interpolation, self._curve_pixmaps[openshot.LINEAR]))
            text_rect.adjust(0.0, 0.0, -24.0, 0.0)

        painter.setPen(QPen(Qt.white if self.isEnabled() else disabled_control_color(self, text=True)))
        painter.drawText(text_rect, Qt.AlignCenter, self._fmt(self._value))
        painter.end()

    def resizeEvent(self, event):
        self._edit.setGeometry(self.rect())
        super().resizeEvent(event)

    def _x_to_value(self, x):
        pct = max(0.0, min(1.0, x / max(self.width(), 1)))
        return self._min + pct * (self._max - self._min)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self.dragStarted.emit()
            self.setValue(self._x_to_value(event.x()))
            self.valueChanged.emit(self._value)
            self.update()

    def mouseMoveEvent(self, event):
        if not self._drag_active or not self.isEnabled():
            return
        self.setValue(self._x_to_value(event.x()))
        self.valueChanged.emit(self._value)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_active:
            self._drag_active = False
            self.dragFinished.emit()

    def mouseDoubleClickEvent(self, event):
        if not self.isEnabled():
            super().mouseDoubleClickEvent(event)
            return
        if event.button() == Qt.LeftButton:
            self._enter_edit_mode()

    def keyPressEvent(self, event):
        if not self.isEnabled():
            super().keyPressEvent(event)
            return
        text = event.text()
        if text and (text.isdigit() or text in ('.', ',', '-')):
            self._enter_edit_mode(text)
        else:
            super().keyPressEvent(event)

    def _enter_edit_mode(self, initial_char=""):
        self._editing = True
        self._edit.setGeometry(self.rect())
        if initial_char:
            self._edit.setText(initial_char)
        else:
            self._edit.setText(self._fmt(self._value))
            self._edit.selectAll()
        self._edit.show()
        self._edit.setFocus()
        self.update()

    def _accept_edit(self):
        text = self._edit.text().replace(',', '.')
        self._edit.hide()
        self._editing = False
        try:
            new_val = max(self._min, min(self._max, float(text)))
        except ValueError:
            self.update()
            return
        old = self._value
        self._value = new_val
        if new_val != old:
            self.dragStarted.emit()
            self.valueChanged.emit(self._value)
            self.dragFinished.emit()
        self.update()

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._accept_edit()
                return True
            if key == Qt.Key_Escape:
                self._edit.hide()
                self._editing = False
                self.update()
                return True
        return super().eventFilter(obj, event)


class WheelRow(QWidget):
    changed = pyqtSignal()
    editFrameRequested = pyqtSignal()
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, title, wheel_data, frame_number=1, parent=None):
        super().__init__(parent)
        self.title = title
        self._data = normalize_wheels_data({"global": wheel_data})["global"]
        self._frame_number = int(frame_number)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 12)

        self.wheel_control = ColorWheelControl(self._data, self, title=title)
        self.wheel_control.changed.connect(self._on_wheel_control_changed)
        self.wheel_control.dragStarted.connect(self.dragStarted)
        self.wheel_control.dragFinished.connect(self.dragFinished)
        self.wheel_control.customContextMenuRequested.connect(self._show_wheel_menu)
        layout.addWidget(self.wheel_control)

        self.amount_input = PropertySlider(0.0, 1.0, decimals=2, parent=self)
        self.luma_input = PropertySlider(-1.0, 1.0, decimals=2, parent=self)
        for key, control in (("amount", self.amount_input), ("luma", self.luma_input)):
            control.setContextMenuPolicy(Qt.CustomContextMenu)
            control.customContextMenuRequested.connect(
                lambda pos, slider_key=key, widget=control: self._show_slider_menu(slider_key, pos, widget))

        amount_row = QHBoxLayout()
        amount_label = QLabel("Amount", self)
        amount_label.setFixedWidth(50)
        amount_row.addWidget(amount_label)
        amount_row.addWidget(self.amount_input)
        layout.addLayout(amount_row)

        luma_row = QHBoxLayout()
        luma_label = QLabel("Luma", self)
        luma_label.setFixedWidth(50)
        luma_row.addWidget(luma_label)
        luma_row.addWidget(self.luma_input)
        layout.addLayout(luma_row)

        self.amount_input.valueChanged.connect(lambda v: self._on_input_changed("amount", v))
        self.luma_input.valueChanged.connect(lambda v: self._on_input_changed("luma", v))
        self.amount_input.dragStarted.connect(self.dragStarted)
        self.amount_input.dragFinished.connect(self.dragFinished)
        self.luma_input.dragStarted.connect(self.dragStarted)
        self.luma_input.dragFinished.connect(self.dragFinished)

        self._apply_data()

    def set_frame_number(self, frame_number, update_controls=True):
        self._frame_number = int(frame_number)
        if update_controls:
            self._apply_data()

    def _snapshot(self):
        return wheel_snapshot(self._data, self._frame_number)

    def _apply_data(self):
        data = self._snapshot()
        self.wheel_control.blockSignals(True)
        self.wheel_control.set_wheel_data(data)
        self.wheel_control.blockSignals(False)
        self.amount_input.blockSignals(True)
        self.luma_input.blockSignals(True)
        self.amount_input.setValue(float(data["amount"]))
        self.luma_input.setValue(float(data["luma"]))
        self.amount_input.set_keyframe_status(*self._keyframe_status(self._data.get("amount_keyframes")))
        self.luma_input.set_keyframe_status(*self._keyframe_status(self._data.get("luma_keyframes")))
        self.amount_input.blockSignals(False)
        self.luma_input.blockSignals(False)

    def _on_input_changed(self, key, value):
        self.editFrameRequested.emit()
        key_name = f"{key}_keyframes"
        self._data[key_name] = _set_keyframe_value(
            self._data.get(key_name), self._frame_number, value)
        if key == "amount":
            self.wheel_control.blockSignals(True)
            self.wheel_control.set_wheel_data(self._snapshot())
            self.wheel_control.blockSignals(False)
        self.changed.emit()

    def _on_wheel_control_changed(self):
        snapshot = self.wheel_control.wheel_data()
        self.editFrameRequested.emit()
        self._data["color_keyframes"] = _set_color_value(
            self._data.get("color_keyframes"), self._frame_number, QColor(snapshot["color"]))
        self._data["amount_keyframes"] = _set_keyframe_value(
            self._data.get("amount_keyframes"), self._frame_number, snapshot["amount"])
        self._apply_data()
        self.changed.emit()

    def pick_color(self):
        current = _evaluate_color(self._data.get("color_keyframes"), self._frame_number, NEUTRAL_WHEEL_COLOR)

        def callback(color):
            if is_achromatic_color(color):
                self._data["color_keyframes"] = _set_color_value(
                    self._data.get("color_keyframes"), self._frame_number, QColor(NEUTRAL_WHEEL_COLOR))
                self._data["amount_keyframes"] = _set_keyframe_value(
                    self._data.get("amount_keyframes"), self._frame_number, 0.0)
            else:
                self._data["color_keyframes"] = _set_color_value(
                    self._data.get("color_keyframes"), self._frame_number, color)
            self._apply_data()
            self.changed.emit()

        ColorPicker(current, parent=self, title=get_app()._tr("Select a Color"), callback=callback)

    def reset_to_neutral(self):
        self.dragStarted.emit()
        self._data["color_keyframes"] = _set_color_value(
            self._data.get("color_keyframes"), self._frame_number, QColor(NEUTRAL_WHEEL_COLOR))
        self._data["amount_keyframes"] = _set_keyframe_value(
            self._data.get("amount_keyframes"), self._frame_number, 0.0)
        self._data["luma_keyframes"] = _set_keyframe_value(
            self._data.get("luma_keyframes"), self._frame_number, 0.0)
        self._apply_data()
        self.changed.emit()
        self.dragFinished.emit()

    def _frame_set(self):
        frames = set()

        def _collect(kf_data):
            points = kf_data.get("Points") if isinstance(kf_data, dict) else None
            if not isinstance(points, list):
                return
            for point in points:
                try:
                    frames.add(int(round(float(point["co"]["X"]))))
                except (KeyError, TypeError, ValueError):
                    continue

        color_kf = self._data.get("color_keyframes") or {}
        for channel in ("red", "green", "blue", "alpha"):
            _collect(color_kf.get(channel))
        _collect(self._data.get("amount_keyframes"))
        _collect(self._data.get("luma_keyframes"))
        return frames

    def _keyframe_points(self, kf_data):
        points = kf_data.get("Points") if isinstance(kf_data, dict) else None
        return points if isinstance(points, list) else []

    def _keyframe_status(self, kf_data):
        points = self._keyframe_points(kf_data)
        target = self._interpolation_target_frame_for(kf_data)
        interpolation = openshot.LINEAR
        for point in points:
            try:
                if int(round(float(point["co"]["X"]))) == int(round(target)):
                    interpolation = int(point.get("interpolation", openshot.LINEAR))
                    break
            except (KeyError, TypeError, ValueError):
                continue
        return max(1, len(points)), interpolation

    def _interpolation_target_frame(self):
        frames = sorted(self._frame_set())
        if not frames:
            return int(round(self._frame_number))
        current = int(round(self._frame_number))
        return next((frame for frame in frames if frame >= current), frames[-1])

    def _interpolation_target_frame_for(self, kf_data):
        frames = []
        for point in self._keyframe_points(kf_data):
            try:
                frames.append(int(round(float(point["co"]["X"]))))
            except (KeyError, TypeError, ValueError):
                continue
        frames = sorted(set(frames))
        if not frames:
            return int(round(self._frame_number))
        current = int(round(self._frame_number))
        return next((frame for frame in frames if frame >= current), frames[-1])

    def _previous_interpolation_frame(self, target_frame):
        frames = sorted(self._frame_set())
        if not frames:
            return int(round(target_frame))
        try:
            target_index = frames.index(int(round(target_frame)))
        except ValueError:
            target_index = 0
        return frames[max(0, target_index - 1)]

    def _previous_interpolation_frame_for(self, kf_data, target_frame):
        frames = []
        for point in self._keyframe_points(kf_data):
            try:
                frames.append(int(round(float(point["co"]["X"]))))
            except (KeyError, TypeError, ValueError):
                continue
        frames = sorted(set(frames))
        if not frames:
            return int(round(target_frame))
        try:
            target_index = frames.index(int(round(target_frame)))
        except ValueError:
            target_index = 0
        return frames[max(0, target_index - 1)]

    def _apply_keyframe_interpolation(self, previous_frame, target_frame, interpolation, preset=None):
        changed = False
        preset = preset or []

        def _matches(point, frame):
            try:
                return int(round(float(point.get("co", {}).get("X")))) == int(round(frame))
            except (TypeError, ValueError):
                return False

        def _update(kf_data):
            nonlocal changed
            points = kf_data.get("Points") if isinstance(kf_data, dict) else None
            if not isinstance(points, list):
                return
            for point in points:
                if _matches(point, previous_frame):
                    changed = True
                    if int(point.get("interpolation", openshot.LINEAR)) == openshot.BEZIER and preset:
                        point["handle_right"] = point.get("handle_right") or {"Y": 0.0, "X": 0.0}
                        point["handle_right"]["X"] = preset[0]
                        point["handle_right"]["Y"] = preset[1]
                    else:
                        point.pop("handle_right", None)
                if _matches(point, target_frame):
                    changed = True
                    point["interpolation"] = int(interpolation)
                    if interpolation == openshot.BEZIER and preset:
                        point["handle_left"] = point.get("handle_left") or {"Y": 0.0, "X": 0.0}
                        point["handle_left"]["X"] = preset[2]
                        point["handle_left"]["Y"] = preset[3]
                    else:
                        point.pop("handle_left", None)

        color_kf = self._data.get("color_keyframes") or {}
        for channel in ("red", "green", "blue", "alpha"):
            _update(color_kf.get(channel))
        _update(self._data.get("amount_keyframes"))
        _update(self._data.get("luma_keyframes"))

        if changed:
            self.dragStarted.emit()
            self._data = normalize_wheels_data({"global": self._data})["global"]
            self._apply_data()
            self.changed.emit()
            self.dragFinished.emit()

    def _set_wheel_interpolation(self, interpolation, preset=None):
        target = self._interpolation_target_frame()
        previous = self._previous_interpolation_frame(target)
        self._apply_keyframe_interpolation(previous, target, interpolation, preset)

    def _set_slider_interpolation(self, key, interpolation, preset=None):
        key_name = f"{key}_keyframes"
        target = self._interpolation_target_frame_for(self._data.get(key_name))
        previous = self._previous_interpolation_frame_for(self._data.get(key_name), target)
        self._apply_keyframe_interpolation_to_key(key_name, previous, target, interpolation, preset)

    def _apply_keyframe_interpolation_to_key(self, key_name, previous_frame, target_frame, interpolation, preset=None):
        changed = False
        preset = preset or []
        kf_data = self._data.get(key_name)

        def _matches(point, frame):
            try:
                return int(round(float(point.get("co", {}).get("X")))) == int(round(frame))
            except (TypeError, ValueError):
                return False

        points = self._keyframe_points(kf_data)
        for point in points:
            if _matches(point, previous_frame):
                changed = True
                if int(point.get("interpolation", openshot.LINEAR)) == openshot.BEZIER and preset:
                    point["handle_right"] = point.get("handle_right") or {"Y": 0.0, "X": 0.0}
                    point["handle_right"]["X"] = preset[0]
                    point["handle_right"]["Y"] = preset[1]
                else:
                    point.pop("handle_right", None)
            if _matches(point, target_frame):
                changed = True
                point["interpolation"] = int(interpolation)
                if interpolation == openshot.BEZIER and preset:
                    point["handle_left"] = point.get("handle_left") or {"Y": 0.0, "X": 0.0}
                    point["handle_left"]["X"] = preset[2]
                    point["handle_left"]["Y"] = preset[3]
                else:
                    point.pop("handle_left", None)

        if changed:
            self.dragStarted.emit()
            self._data[key_name] = _normalize_keyframe_data(kf_data)
            self._apply_data()
            self.changed.emit()
            self.dragFinished.emit()

    def _insert_keyframe(self):
        snapshot = self._snapshot()
        self.dragStarted.emit()
        self._data["color_keyframes"] = _set_color_value(
            self._data.get("color_keyframes"), self._frame_number, QColor(snapshot["color"]))
        self._data["amount_keyframes"] = _set_keyframe_value(
            self._data.get("amount_keyframes"), self._frame_number, snapshot["amount"])
        self._data["luma_keyframes"] = _set_keyframe_value(
            self._data.get("luma_keyframes"), self._frame_number, snapshot["luma"])
        self._data = normalize_wheels_data({"global": self._data})["global"]
        self._apply_data()
        self.changed.emit()
        self.dragFinished.emit()

    def _remove_keyframe(self):
        target = self._interpolation_target_frame()
        changed = False

        def _remove(kf_data):
            nonlocal changed
            points = kf_data.get("Points") if isinstance(kf_data, dict) else None
            if not isinstance(points, list) or len(points) <= 1:
                return
            filtered = []
            for point in points:
                try:
                    keep = int(round(float(point["co"]["X"]))) != target
                except (KeyError, TypeError, ValueError):
                    keep = True
                if keep:
                    filtered.append(point)
            if len(filtered) != len(points):
                kf_data["Points"] = filtered
                changed = True

        color_kf = self._data.get("color_keyframes") or {}
        for channel in ("red", "green", "blue", "alpha"):
            _remove(color_kf.get(channel))
        _remove(self._data.get("amount_keyframes"))
        _remove(self._data.get("luma_keyframes"))

        if changed:
            self.dragStarted.emit()
            self._data = normalize_wheels_data({"global": self._data})["global"]
            self._apply_data()
            self.changed.emit()
            self.dragFinished.emit()

    def _insert_slider_keyframe(self, key):
        value = self._snapshot().get(key, 0.0)
        key_name = f"{key}_keyframes"
        self.dragStarted.emit()
        self._data[key_name] = _set_keyframe_value(
            self._data.get(key_name), self._frame_number, value)
        self._data = normalize_wheels_data({"global": self._data})["global"]
        self._apply_data()
        self.changed.emit()
        self.dragFinished.emit()

    def _remove_slider_keyframe(self, key):
        key_name = f"{key}_keyframes"
        target = self._interpolation_target_frame_for(self._data.get(key_name))
        points = self._keyframe_points(self._data.get(key_name))
        if len(points) <= 1:
            return
        filtered = []
        for point in points:
            try:
                keep = int(round(float(point["co"]["X"]))) != target
            except (KeyError, TypeError, ValueError):
                keep = True
            if keep:
                filtered.append(point)
        if len(filtered) == len(points):
            return
        self.dragStarted.emit()
        self._data[key_name]["Points"] = filtered
        self._data = normalize_wheels_data({"global": self._data})["global"]
        self._apply_data()
        self.changed.emit()
        self.dragFinished.emit()

    def _show_slider_menu(self, key, pos, source_widget):
        _ = get_app()._tr
        menu = StyledContextMenu(parent=self)
        populate_keyframe_context_menu(
            menu,
            bezier_callback=lambda preset: self._set_slider_interpolation(key, openshot.BEZIER, preset),
            linear_callback=lambda: self._set_slider_interpolation(key, openshot.LINEAR),
            constant_callback=lambda: self._set_slider_interpolation(key, openshot.CONSTANT),
            bezier_icon=None,
            linear_icon=None,
            constant_icon=None,
        )
        menu.addSeparator()
        insert_action = QAction(_("Insert Keyframe"), self)
        insert_action.triggered.connect(lambda: self._insert_slider_keyframe(key))
        menu.addAction(insert_action)
        remove_action = QAction(_("Remove Keyframe"), self)
        remove_action.setEnabled(len(self._keyframe_points(self._data.get(f"{key}_keyframes"))) > 1)
        remove_action.triggered.connect(lambda: self._remove_slider_keyframe(key))
        menu.addAction(remove_action)
        menu.exec_(source_widget.mapToGlobal(pos))

    def _show_wheel_menu(self, pos, source_widget=None):
        _ = get_app()._tr
        menu = StyledContextMenu(parent=self)
        color_action = QAction(_("Choose Color..."), self)
        color_action.triggered.connect(self.pick_color)
        menu.addAction(color_action)
        menu.addSeparator()
        populate_keyframe_context_menu(
            menu,
            bezier_callback=lambda preset: self._set_wheel_interpolation(openshot.BEZIER, preset),
            linear_callback=lambda: self._set_wheel_interpolation(openshot.LINEAR),
            constant_callback=lambda: self._set_wheel_interpolation(openshot.CONSTANT),
            bezier_icon=None,
            linear_icon=None,
            constant_icon=None,
        )
        menu.addSeparator()
        insert_action = QAction(_("Insert Keyframe"), self)
        insert_action.triggered.connect(self._insert_keyframe)
        menu.addAction(insert_action)
        remove_action = QAction(_("Remove Keyframe"), self)
        remove_action.setEnabled(len(self._frame_set()) > 1)
        remove_action.triggered.connect(self._remove_keyframe)
        menu.addAction(remove_action)
        menu.addSeparator()
        reset_action = QAction(_("Reset"), self)
        reset_action.triggered.connect(self.reset_to_neutral)
        menu.addAction(reset_action)
        source_widget = source_widget or self.wheel_control
        menu.exec_(source_widget.mapToGlobal(pos))

    def value(self):
        return copy.deepcopy(self._data)


class ColorGradeWheelsDialog(QDialog):
    def __init__(self, wheels_data=None, parent=None):
        super().__init__(parent)
        _ = get_app()._tr
        self.setWindowTitle(_("Edit Color Wheels"))
        self._data = normalize_wheels_data(wheels_data)

        layout = QVBoxLayout(self)
        self.preview = WheelsPreviewWidget(self._data, self)
        layout.addWidget(self.preview)

        self.rows = {}
        for name, title in (
            ("global", _("Global")),
            ("shadows", _("Shadows")),
            ("midtones", _("Midtones")),
            ("highlights", _("Highlights")),
        ):
            row = WheelRow(title, self._data[name], 1, self)
            row.changed.connect(self._refresh_preview)
            self.rows[name] = row
            layout.addWidget(row)

        reset_button = QPushButton(_("Reset"), self)
        reset_button.clicked.connect(self._reset)
        layout.addWidget(reset_button)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_preview(self):
        self.preview.set_wheels_data(self.wheels_data())

    def _reset(self):
        reset_data = default_wheels_data()
        for name, row in self.rows.items():
            row._data = copy.deepcopy(reset_data[name])
            row._apply_data()
        self._refresh_preview()

    def wheels_data(self):
        payload = {"enabled_keyframes": self._data.get("enabled_keyframes", _keyframe_value(value=1.0))}
        for name, row in self.rows.items():
            payload[name] = row._data
        return normalize_wheels_data(payload)


class ColorGradeWheelsPanel(QWidget):
    wheelsChanged = pyqtSignal(dict)
    editFrameRequested = pyqtSignal()
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, wheels_data=None, frame_number=1, parent=None):
        super().__init__(parent)
        _ = get_app()._tr
        self._data = normalize_wheels_data(wheels_data)
        self._frame_number = int(frame_number)

        layout = QVBoxLayout(self)

        self.rows = {}
        for name, title in (
            ("global", _("Global")),
            ("shadows", _("Shadows")),
            ("midtones", _("Midtones")),
            ("highlights", _("Highlights")),
        ):
            row = WheelRow(title, self._data[name], self._frame_number, self)
            row.changed.connect(self._refresh_preview)
            row.editFrameRequested.connect(self.editFrameRequested)
            row.dragStarted.connect(self.dragStarted)
            row.dragFinished.connect(self.dragFinished)
            self.rows[name] = row
            layout.addWidget(row)

        button_row = QHBoxLayout()
        self.toggle_button = QPushButton(_("Disable"), self)
        self.toggle_button.clicked.connect(self._toggle_enabled)
        button_row.addWidget(self.toggle_button)

        button_row.addStretch(1)

        reset_button = QPushButton(_("Reset"), self)
        reset_button.clicked.connect(self._reset)
        button_row.addWidget(reset_button)
        layout.addLayout(button_row)
        self._update_enabled_state()

    def set_wheels_data(self, wheels_data):
        self._data = normalize_wheels_data(wheels_data)
        for name, row in self.rows.items():
            row._data = copy.deepcopy(self._data[name])
            row._apply_data()
        self._update_enabled_state()

    def set_frame_number(self, frame_number, update_controls=True):
        self._frame_number = int(frame_number)
        for row in self.rows.values():
            row.set_frame_number(self._frame_number, update_controls=update_controls)
        if update_controls:
            self._update_enabled_state()

    def _refresh_preview(self):
        wheels = self.wheels_data()
        self.wheelsChanged.emit(wheels)

    def _reset(self):
        reset_data = default_wheels_data()
        reset_data["enabled_keyframes"] = copy.deepcopy(self.wheels_data().get("enabled_keyframes", _keyframe_value(value=1.0)))
        self.set_wheels_data(reset_data)
        self.wheelsChanged.emit(self.wheels_data())

    def _toggle_enabled(self):
        updated = self.wheels_data()
        next_enabled = not wheels_enabled_at_frame(updated, self._frame_number)
        updated["enabled_keyframes"] = _set_keyframe_value(updated.get("enabled_keyframes"), self._frame_number, 1.0 if next_enabled else 0.0)
        self.set_wheels_data(updated)
        self.wheelsChanged.emit(updated)
        self._update_enabled_state()

    def _update_enabled_state(self):
        enabled = wheels_enabled_at_frame(self.wheels_data(), self._frame_number)
        _ = get_app()._tr
        self.toggle_button.setText(_("Disable") if enabled else _("Enable"))
        for row in self.rows.values():
            row.setEnabled(enabled)

    def wheels_data(self):
        payload = {"enabled_keyframes": self._data.get("enabled_keyframes", _keyframe_value(value=1.0))}
        for name, row in self.rows.items():
            payload[name] = row._data
        return normalize_wheels_data(payload)
