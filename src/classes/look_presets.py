"""
 @file
 @brief Look menu effect presets for timeline clips (Look clip menu and CLI)

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
import json

from classes.color_presets import (
    COLOR_GRADE_CLASS_NAME,
    COLOR_PRESET_AUTO_CONTRAST,
    COLOR_PRESET_BOOST_COLOR,
    COLOR_PRESET_LIFT_SHADOWS,
    COLOR_PRESET_RESET,
    COLOR_PRESET_WARM_UP,
    apply_color_grade_preset,
    is_color_grade_effect,
)
from classes.film_grain_presets import (
    FILM_GRAIN_CLASS_NAME,
    FILM_GRAIN_PRESET_16MM_CLASSIC,
    FILM_GRAIN_PRESET_35MM_CLASSIC,
    FILM_GRAIN_PRESET_35MM_FINE,
    FILM_GRAIN_PRESET_35MM_GRITTY,
    FILM_GRAIN_PRESET_HIGH_ISO,
    FILM_GRAIN_PRESET_NONE,
    FILM_GRAIN_PRESET_SUPER_8,
    apply_film_grain_preset,
    is_film_grain_effect,
)

LOOK_EFFECT_UI_MENU = "look"

LOOK_RESET_EFFECT_CLASSES = {
    COLOR_GRADE_CLASS_NAME,
    FILM_GRAIN_CLASS_NAME,
}

LOOK_EFFECT_PRESETS = {
    "AnalogTape": {
        "none": {},
        "subtle": {
            "bleed": 0.25,
            "noise": 0.18,
            "softness": 0.15,
            "static_bands": 0.05,
            "stripe": 0.06,
            "tracking": 0.20,
        },
        "vhs": {
            "bleed": 0.55,
            "noise": 0.35,
            "softness": 0.35,
            "static_bands": 0.18,
            "stripe": 0.20,
            "tracking": 0.45,
        },
        "heavy": {
            "bleed": 0.85,
            "noise": 0.60,
            "softness": 0.55,
            "static_bands": 0.35,
            "stripe": 0.40,
            "tracking": 0.75,
        },
    },
    "Blur": {
        "none": {},
        "soft_focus": {"horizontal_radius": 3.0, "vertical_radius": 3.0, "sigma": 1.5, "iterations": 2.0},
        "medium": {"horizontal_radius": 8.0, "vertical_radius": 8.0, "sigma": 4.0, "iterations": 3.0},
        "heavy": {"horizontal_radius": 20.0, "vertical_radius": 20.0, "sigma": 8.0, "iterations": 4.0},
    },
    "Glow": {
        "none": {},
        "soft_white": {"mode": 0, "opacity": 0.35, "blur_radius": 18.0, "spread": 0.15, "color": "#ffffffff"},
        "warm": {"mode": 0, "opacity": 0.45, "blur_radius": 24.0, "spread": 0.20, "color": "#ffd28cff"},
        "neon": {"mode": 0, "opacity": 0.65, "blur_radius": 16.0, "spread": 0.35, "color": "#35d7ffff"},
        "inner": {"mode": 1, "opacity": 0.45, "blur_radius": 12.0, "spread": 0.25, "color": "#ffffffff"},
    },
    "Shadow": {
        "none": {},
        "subtle": {"opacity": 0.30, "blur_radius": 12.0, "spread": 0.05, "distance": 8.0, "angle": 135.0, "color": "#000000ff"},
        "soft": {"opacity": 0.45, "blur_radius": 28.0, "spread": 0.10, "distance": 14.0, "angle": 135.0, "color": "#000000ff"},
        "strong": {"opacity": 0.70, "blur_radius": 18.0, "spread": 0.25, "distance": 16.0, "angle": 135.0, "color": "#000000ff"},
        "long": {"opacity": 0.45, "blur_radius": 24.0, "spread": 0.12, "distance": 44.0, "angle": 135.0, "color": "#000000ff"},
    },
    "Sharpen": {
        "none": {},
        "subtle": {"amount": 4.0, "radius": 1.5, "threshold": 0.0},
        "medium": {"amount": 9.0, "radius": 2.5, "threshold": 0.0},
        "strong": {"amount": 16.0, "radius": 3.5, "threshold": 0.0},
    },
}

# Preset names offered for each Look effect ("none" removes that effect)
LOOK_PRESETS = {
    COLOR_GRADE_CLASS_NAME: ("none", COLOR_PRESET_AUTO_CONTRAST, COLOR_PRESET_LIFT_SHADOWS,
                             COLOR_PRESET_WARM_UP, COLOR_PRESET_BOOST_COLOR),
    FILM_GRAIN_CLASS_NAME: (FILM_GRAIN_PRESET_NONE, FILM_GRAIN_PRESET_35MM_FINE, FILM_GRAIN_PRESET_35MM_CLASSIC,
                            FILM_GRAIN_PRESET_35MM_GRITTY, FILM_GRAIN_PRESET_16MM_CLASSIC,
                            FILM_GRAIN_PRESET_SUPER_8, FILM_GRAIN_PRESET_HIGH_ISO),
}
LOOK_PRESETS.update({class_name: tuple(presets) for class_name, presets in LOOK_EFFECT_PRESETS.items()})


def is_look_managed_effect(effect_json, class_name=None):
    if not isinstance(effect_json, dict):
        return False
    if effect_json.get("ui-menu") != LOOK_EFFECT_UI_MENU:
        return False
    return class_name is None or effect_json.get("class_name") == class_name


def parse_effect_color(value):
    if not isinstance(value, str):
        return None
    color = value.strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) not in (6, 8):
        return None
    try:
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
        alpha = int(color[6:8], 16) if len(color) == 8 else 255
    except ValueError:
        return None
    return {
        "red": red,
        "green": green,
        "blue": blue,
        "alpha": alpha,
    }


def _constant_point(value):
    import openshot
    return json.loads(openshot.Point(1, float(value), openshot.BEZIER).Json())


def set_effect_property_value(effect_json, property_name, value):
    property_data = effect_json.get(property_name)
    color_channels = parse_effect_color(value)
    if color_channels and isinstance(property_data, dict):
        for channel, channel_value in color_channels.items():
            channel_data = property_data.get(channel)
            if isinstance(channel_data, dict) and isinstance(channel_data.get("Points"), list):
                channel_data["Points"] = [_constant_point(channel_value)]
    elif isinstance(property_data, dict) and isinstance(property_data.get("Points"), list):
        property_data["Points"] = [_constant_point(value)]
    elif property_name in effect_json:
        effect_json[property_name] = value


def reset_look(data):
    """Remove all effects managed by the Look menu. Return True if anything changed."""
    effects = data.get("effects")
    if not isinstance(effects, list):
        return False
    filtered_effects = [
        effect_json for effect_json in effects
        if not isinstance(effect_json, dict)
        or (
            effect_json.get("class_name") not in LOOK_RESET_EFFECT_CLASSES
            and not is_look_managed_effect(effect_json)
        )
    ]
    if len(filtered_effects) == len(effects):
        return False
    data["effects"] = filtered_effects
    return True


def apply_look_preset(data, class_name, preset_name, create_effect):
    """Apply (or remove, for "none") one Look effect preset on clip JSON, in place.

    The preset replaces the first matching effect (keeping its id and order)
    and collapses duplicates. create_effect(class_name) returns new effect JSON
    with an id. Return True if the clip changed.
    """
    effects = data.get("effects")
    if not isinstance(effects, list):
        effects = list(effects) if effects else []
        data["effects"] = effects

    if class_name == COLOR_GRADE_CLASS_NAME:
        matches = is_color_grade_effect
        remove = preset_name in (COLOR_PRESET_RESET, "none")
    elif class_name == FILM_GRAIN_CLASS_NAME:
        matches = is_film_grain_effect
        remove = preset_name == FILM_GRAIN_PRESET_NONE
    else:
        if preset_name not in LOOK_EFFECT_PRESETS.get(class_name, {}):
            return False
        matches = lambda effect_json: is_look_managed_effect(effect_json, class_name)
        remove = preset_name == "none"
    matching_indexes = [index for index, effect_json in enumerate(effects) if matches(effect_json)]

    if remove:
        if not matching_indexes:
            return False
        data["effects"] = [effect_json for effect_json in effects if not matches(effect_json)]
        return True

    if class_name == COLOR_GRADE_CLASS_NAME:
        preset_effect = apply_color_grade_preset(create_effect(class_name), preset_name)
    elif class_name == FILM_GRAIN_CLASS_NAME:
        source_effect = effects[matching_indexes[0]] if matching_indexes else create_effect(class_name)
        preset_effect = apply_film_grain_preset(source_effect, preset_name)
    else:
        preset_effect = create_effect(class_name)
        preset_effect["ui-menu"] = LOOK_EFFECT_UI_MENU
        for property_name, value in LOOK_EFFECT_PRESETS[class_name][preset_name].items():
            set_effect_property_value(preset_effect, property_name, value)

    if matching_indexes:
        existing_effect = effects[matching_indexes[0]]
        if existing_effect.get("id"):
            preset_effect["id"] = existing_effect["id"]
        if "order" in existing_effect:
            preset_effect["order"] = existing_effect["order"]
        effects[matching_indexes[0]] = preset_effect
        for index in reversed(matching_indexes[1:]):
            del effects[index]
    else:
        effects.append(preset_effect)
    return True
