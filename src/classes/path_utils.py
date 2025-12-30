"""
 @file
 @brief Helpers for resolving media paths to absolute/relative forms
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

import os

from classes import info
from classes.app import get_app
from classes.assets import get_assets_path


def _project_file_path(project_file=None):
    """Return the active project file path (if any)."""
    if project_file:
        return project_file
    app = get_app()
    if app and hasattr(app, "project"):
        return getattr(app.project, "current_filepath", None)
    return None


def _project_folder(project_file=None):
    project_file = _project_file_path(project_file)
    if project_file:
        return os.path.dirname(project_file)
    return info.HOME_PATH


def _token_suffix(path_value):
    parts = path_value.split("/", 1)
    if len(parts) == 2:
        return parts[1]
    return ""


def absolute_media_path(path_value, project_file=None):
    """Resolve OpenShot-specific tokens and relative paths into absolute paths."""
    if not path_value:
        return ""

    normalized = path_value.replace("\\", "/")

    if normalized.startswith("@emojis"):
        suffix = _token_suffix(normalized)
        return os.path.normpath(os.path.join(info.PATH, "emojis", "color", "svg", suffix))

    if normalized.startswith("@transitions"):
        suffix = _token_suffix(normalized)
        return os.path.normpath(os.path.join(info.PATH, "transitions", suffix))

    if normalized.startswith("@colors"):
        suffix = _token_suffix(normalized)
        return os.path.normpath(os.path.join(info.COLORS_PATH, suffix))

    if normalized.startswith("@assets"):
        project_file = _project_file_path(project_file)
        assets_root = get_assets_path(project_file, create_paths=False)
        suffix = _token_suffix(normalized)
        return os.path.normpath(os.path.join(assets_root, suffix))

    if normalized.startswith("thumbnail/"):
        project_file = _project_file_path(project_file)
        assets_root = get_assets_path(project_file, create_paths=False)
        return os.path.normpath(os.path.join(assets_root, normalized.replace("thumbnail/", "thumbnail" + os.sep)))

    if os.path.isabs(normalized):
        return os.path.normpath(normalized)

    base_folder = _project_folder(project_file)
    return os.path.normpath(os.path.join(base_folder, normalized))


def relative_export_path(abs_path, export_folder):
    """Return path relative to export folder when possible."""
    if not abs_path:
        return ""
    try:
        abs_norm = os.path.normpath(abs_path)
        if not export_folder:
            return abs_norm.replace("\\", "/")
        export_norm = os.path.normpath(export_folder)
        if os.name == "nt":
            src_drive = os.path.splitdrive(abs_norm)[0].lower()
            dst_drive = os.path.splitdrive(export_norm)[0].lower()
            if src_drive and dst_drive and src_drive != dst_drive:
                return abs_norm.replace("\\", "/")
        rel_path = os.path.relpath(abs_norm, export_norm)
        return rel_path.replace("\\", "/")
    except Exception:
        return abs_path.replace("\\", "/")


def absolute_path_from_export(path_value, base_folder, project_file=None):
    """Resolve a relative path stored in an export back into an absolute path."""
    if not path_value:
        return ""

    normalized = path_value.replace("\\", "/")

    if normalized.startswith("@"):
        return absolute_media_path(normalized, project_file)

    if os.path.isabs(normalized):
        return os.path.normpath(normalized)

    if not base_folder:
        base_folder = _project_folder(project_file)

    return os.path.normpath(os.path.join(base_folder, normalized))


def normalize_path(path_value):
    """Return a path string with POSIX separators (useful for XML)."""
    if not path_value:
        return ""
    return path_value.replace("\\", "/")
