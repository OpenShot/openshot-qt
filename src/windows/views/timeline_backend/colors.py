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

from qt_api import QColor

# Mapping of effect class names (the "type" field in serialised effect JSON)
# to their representative colours.  Keys must match the value of the "type"
# field returned by libopenshot's Effect.Json() — which is always the
# CamelCase class name with no spaces (e.g. "ColorShift", not "Color Shift").
_EFFECT_COLORS: Dict[str, str] = {
    "AnalogTape":         "#907600",
    "Bars":               "#4d7bff",
    "Blur":               "#0095bf",
    "Brightness":         "#5500ff",
    "Caption":            "#5e7911",
    "ChromaKey":          "#00ad2d",
    "ColorGrade":         "#d4830a",
    "ColorMap":           "#4d945d",
    "ColorShift":         "#b39373",
    "Compressor":         "#A52A2A",
    "Crop":               "#7b3f00",
    "Deinterlace":        "#006001",
    "Delay":              "#ff4dd4",
    "Displace":           "#2a8090",
    "Distort":            "#537bb5",
    "Distortion":         "#7393B3",
    "Echo":               "#5C4033",
    "Expander":           "#C4A484",
    "FilmGrain":          "#c49a4a",
    "Glow":               "#e8b84b",
    "Hue":                "#2d7b6b",
    "LensFlare":          "#7c29d1",
    "Mask":               "#cb0091",
    "Negate":             "#ff9700",
    "Noise":              "#a9a9a9",
    "Normalize":          "#607d3b",
    "ObjectDetection":    "#636363",
    "Outline":            "#be6d33",
    "ParametricEQ":       "#708090",
    "PitchShift":         "#7561ad",
    "Pixelate":           "#9fa131",
    "Robotization":       "#CC5500",
    "Saturation":         "#ff3d00",
    "Shadow":             "#4a4a6b",
    "Sharpen":            "#49759c",
    "Shift":              "#8d7960",
    "SphericalProjection":"#b886ea",
    "Stabilizer":         "#9F2B68",
    "Tracker":            "#DE3163",
    "Wave":               "#FF00FF",
    "Whisperization":     "#93914a",
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
