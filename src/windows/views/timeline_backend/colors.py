"""
 @file
 @brief Shared helpers for timeline color mappings.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
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

from typing import Any, Dict

from PyQt5.QtGui import QColor

# Mapping of known effect names to their representative colors. These values
# mirror the existing web timeline so both backends stay consistent.
_EFFECT_COLORS: Dict[str, str] = {
    "AnalogTape": "#907600",
    "Bars": "#4d7bff",
    "Blur": "#0095bf",
    "Brightness": "#5500ff",
    "Caption": "#5e7911",
    "ChromaKey": "#00ad2d",
    "Color Shift": "#b39373",
    "Compressor": "#A52A2A",
    "Crop": "#7b3f00",
    "Deinterlace": "#006001",
    "Delay": "#ff4dd4",
    "Distortion": "#7393B3",
    "Echo": "#5C4033",
    "Expander": "#C4A484",
    "Hue": "#2d7b6b",
    "Mask": "#cb0091",
    "Negate": "#ff9700",
    "Noise": "#a9a9a9",
    "ObjectDetection": "#636363",
    "Parametric EQ": "#708090",
    "Pixelate": "#9fa131",
    "Robotization": "#CC5500",
    "Saturation": "#ff3d00",
    "Sharpen": "#49759c",
    "ColorMap": "#4d945d",
    "LensFlare": "#7c29d1",
    "Normalize": "#607d3b",
    "Outline": "#be6d33",
    "SphericalProjection": "#b886ea",
    "Shift": "#8d7960",
    "Stabilizer": "#9F2B68",
    "Tracker": "#DE3163",
    "Wave": "#FF00Ff",
    "Whisperization": "#93914a",
}

_DEFAULT_COLOR = "#4d7bff"


def _effect_type_name(effect: Any) -> str:
    if isinstance(effect, dict):
        for key in ("type", "effect", "name", "class_name"):
            value = effect.get(key)
            if value:
                return str(value)
    elif effect:
        return str(effect)
    return ""


def effect_color_hex(effect: Any) -> str:
    """Return the preferred hex color string for *effect*."""
    if isinstance(effect, dict):
        color = effect.get("color")
        if isinstance(color, str) and color:
            return color
    type_name = _effect_type_name(effect)
    return _EFFECT_COLORS.get(type_name, _DEFAULT_COLOR)


def effect_color_qcolor(effect: Any) -> QColor:
    """Return a QColor matching the preferred color for *effect*."""
    return QColor(effect_color_hex(effect))
