"""
 @file
 @brief This file is responsible for serializing copy/paste clipboard data for OpenShot
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

import json
import math
from qt_api import QMimeData
from classes.query import Clip, Transition, Effect


EFFECT_RANGES_MIME = "application/x-openshot-effect-ranges"
_MIME = "application/x-openshot-generic"
_TYPES = {"clip": Clip, "transition": Transition, "effect": Effect}


def _json_loads(text):
    # NaN/Infinity aren't JSON and cannot be used for timeline coordinates.
    def invalid_constant(value):
        raise ValueError("Invalid JSON constant: " + value)
    return json.loads(text, parse_constant=invalid_constant)


def _validate_data(data):
    if not isinstance(data, dict):
        raise ValueError("Clipboard item must be a JSON object")
    for key in ("position", "start", "end", "layer"):
        if key in data and (type(data[key]) not in (int, float) or not math.isfinite(data[key])):
            raise ValueError("Invalid clipboard coordinate")
    if "effects" in data and (not isinstance(data["effects"], list) or
                              any(not isinstance(item, dict) for item in data["effects"])):
        raise ValueError("Invalid clipboard effects")
    if "reader" in data and not isinstance(data["reader"], dict):
        raise ValueError("Invalid clipboard reader")


class ClipboardManager:
    """Copy timeline data once as JSON text, plus small type/identity metadata."""

    @staticmethod
    def to_mime(data):
        mime_data = QMimeData()
        # Preserve the established single-object versus multi-object text shape.
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        items = data if isinstance(data, list) else [data]
        try:
            metadata = []
            for item in items:
                kind = next((name for name, cls in _TYPES.items() if isinstance(item, cls)), None)
                if kind is None or (item.id is not None and not isinstance(item.id, str)):
                    raise ValueError("Unsupported clipboard object")
                _validate_data(item.data)
                metadata.append({"type": kind, "id": item.id})
            text = json.dumps([item.data for item in items] if isinstance(data, list) else data.data,
                              indent=4, allow_nan=False)
            # The custom format contains NO duplicate clip/effect JSON data.
            details = json.dumps({"version": 1, "items": metadata}).encode("utf-8")
            mime_data.setText(text)
            mime_data.setData(_MIME, details)
        except (TypeError, ValueError, AttributeError, OverflowError, RecursionError):
            return QMimeData()
        return mime_data

    @staticmethod
    def from_mime(mime_data):
        """Rebuild only known detached query objects; never load Python state."""
        try:
            if not mime_data.hasFormat(_MIME) or not mime_data.hasText():
                return None
            metadata = _json_loads(bytes(mime_data.data(_MIME)).decode("utf-8"))
            data = _json_loads(mime_data.text())
            if (not isinstance(metadata, dict) or not isinstance(metadata.get("version"), int)
                    or isinstance(metadata.get("version"), bool) or metadata["version"] != 1 or not isinstance(metadata.get("items"), list)):
                return None
            items = data if isinstance(data, list) else [data]
            if len(items) != len(metadata["items"]):
                return None
            objects = []
            for value, details in zip(items, metadata["items"]):
                if not isinstance(details, dict) or not isinstance(details.get("type"), str):
                    return None
                cls = _TYPES.get(details["type"])
                source_id = details.get("id")
                if cls is None or (source_id is not None and not isinstance(source_id, str)):
                    return None
                _validate_data(value)
                item = cls()
                item.id = source_id
                item.data = value
                objects.append(item)
            return objects if isinstance(data, list) else objects[0]
        except (TypeError, ValueError, AttributeError, OverflowError, RecursionError):
            # Old pickle clipboard payloads and malformed foreign MIME data are
            # ignored by Paste and context-menu availability checks alike.
            return None
