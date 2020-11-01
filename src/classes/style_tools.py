"""
 @file
 @brief Utility functions for manipulating SVG style attributes
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


def style_to_dict(style: str) -> dict:
    """Explode an SVG node style= attribute string into a dict representation"""
    styledict = {}
    try:
        # Fill the dict using key-value pairs produced by this comprehension
        styledict.update(
            # Make pairs of (property, value) by splitting on the first ':'
            (a.split(':', 1))
            # Using the list formed by splitting style on ';'
            for a in style.split(';')
            # Ignore any empty strings produced
            if a
            )
        return styledict
    except ValueError as ex:
        log.error(
            "style_to_dict failed to convert to dict: %s\n%s",
            ex, style)


def dict_to_style(styledict: dict) -> str:
    """Turn an exploded style dictionary back into a string"""
    # Glue the results of this comprehension together with ';' separators
    try:
        style = ";".join([
            # Produce a list of "key:value" strings
            ":".join([k, v])
            # For every {key: value} in styledict
            for k, v in styledict.items()
            ])
        # Don't forget the trailing semicolon!
        return style + ';'
    except ValueError as ex:
        import json
        log.error(
            "style_to_dict failed to generate string: %s\n%s",
            ex, json.dumps(styledict))


def set_if_existing(d: dict, existing_key, new_value):
    if existing_key in d:
        d.update({existing_key: new_value})
