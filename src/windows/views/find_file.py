"""
 @file
 @brief This file is used to find missing files when opening or importing a project
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

import html
import os
from classes import info
from classes.app import get_app
from classes.path_utils import native_display_path, wrapped_path_html
from qt_api import Qt
from qt_api import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, get_existing_directory

# Keep track of all previously checked paths, and keep checking them
known_paths = [info.HOME_PATH]


def _display_directory_html(file_path):
    directory_path = os.path.dirname(file_path)
    if not directory_path:
        directory_path = "."
    return wrapped_path_html(directory_path)


def _deepest_existing_parent(path_value):
    """Return the deepest existing directory in a missing file path."""
    candidate = os.path.abspath(path_value or "")
    if not candidate:
        return ""

    if os.path.isdir(candidate):
        return candidate

    candidate = os.path.dirname(candidate)
    while candidate and not os.path.exists(candidate):
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent

    if candidate and os.path.isdir(candidate):
        return candidate
    return ""


def _show_missing_file_dialog(file_name, file_path, starting_dir):
    _ = get_app()._tr
    browse_dir = starting_dir if os.path.isdir(starting_dir) else _deepest_existing_parent(starting_dir)
    if not browse_dir:
        browse_dir = info.HOME_PATH
    dialog = QDialog(get_app().window)
    dialog.setWindowTitle(_("Locate Missing Files"))
    dialog.setModal(True)
    dialog.setMinimumSize(420, 130)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(0)

    intro_label = QLabel(_("This file is missing. You can locate it or remove it from the project."))
    intro_label.setObjectName("lblMissingFileHint")
    intro_label.setWordWrap(True)
    layout.addWidget(intro_label)
    layout.addSpacing(12)

    name_label = QLabel(f"<b>{html.escape(file_name)}</b>")
    name_label.setTextFormat(Qt.RichText)
    name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    name_label.setContentsMargins(8, 0, 0, 0)
    layout.addWidget(name_label)

    dir_label = QLabel(_display_directory_html(file_path))
    dir_label.setObjectName("lblMissingFilePath")
    dir_label.setWordWrap(True)
    dir_label.setTextFormat(Qt.RichText)
    dir_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    dir_label.setContentsMargins(8, 0, 0, 0)
    dir_label.setToolTip(native_display_path(os.path.dirname(file_path) or "."))
    layout.addWidget(dir_label)
    layout.addStretch(1)

    button_row = QHBoxLayout()
    button_row.setContentsMargins(0, 0, 0, 0)
    button_row.setSpacing(6)
    skip_all_button = QPushButton(_("Remove All Missing"))
    skip_file_button = QPushButton(_("Remove"))
    browse_button = QPushButton(_("Browse..."))
    browse_button.setObjectName("acceptButton")
    button_row.addWidget(skip_all_button)
    button_row.addStretch(1)
    button_row.addWidget(skip_file_button)
    button_row.addWidget(browse_button)
    layout.addLayout(button_row)

    result = {"action": "file", "path": file_path}

    def pick_browse():
        if not browse_button.isEnabled():
            return
        browse_button.setEnabled(False)
        try:
            selected_dir = get_existing_directory(
                dialog,
                _("Locate folder containing: %s") % file_name,
                browse_dir,
            )
        finally:
            browse_button.setEnabled(True)
        if selected_dir:
            result["action"] = "locate"
            result["path"] = os.path.join(selected_dir, file_name)
            dialog.accept()

    def pick_skip_all():
        result["action"] = "all"
        dialog.reject()

    browse_button.clicked.connect(pick_browse)
    skip_file_button.clicked.connect(dialog.reject)
    skip_all_button.clicked.connect(pick_skip_all)
    browse_button.setDefault(True)
    browse_button.setAutoDefault(True)
    browse_button.setFocus()

    try:
        dialog.exec_()
    finally:
        dialog.deleteLater()
    return result["action"], result["path"]


def find_missing_file(file_path, prompt_state=None):
    """Find a missing file name or file path, and return valid path."""
    _ = get_app()._tr
    modified = False
    skipped = False
    if prompt_state is not None:
        prompt_state["last_skip"] = None

    # If user cancelled prompts, skip searching
    if prompt_state and prompt_state.get("cancelled"):
        if prompt_state is not None:
            prompt_state["last_skip"] = "all"
        return ("", modified, True)

    # Bail if path is already valid
    if os.path.exists(file_path):
        return (file_path, modified, skipped)

    # Original filename
    file_name = os.path.split(file_path)[-1]

    # Loop through all known paths, and check for this file
    for known_path in known_paths:
        possible_path = os.path.join(known_path, file_name)
        if os.path.exists(possible_path):
            modified = True
            return (possible_path, modified, skipped)

    # Check if path exists
    while not os.path.exists(file_path):
        recommended_path = _deepest_existing_parent(file_path)
        if not recommended_path:
            recommended_path = get_app().project.current_filepath or ""
            if not recommended_path:
                recommended_path = info.HOME_PATH
            else:
                recommended_path = os.path.dirname(recommended_path)
        action, selected_path = _show_missing_file_dialog(file_name, file_path, recommended_path)
        modified = True

        if action == "all":
            # User skipped all missing file prompts
            skipped = True
            if prompt_state is not None:
                prompt_state["cancelled"] = True
                prompt_state["last_skip"] = "all"
            return ("", modified, skipped)

        if action == "file":
            # User skipped this missing file only
            skipped = True
            if prompt_state is not None:
                prompt_state["last_skip"] = "file"
            return ("", modified, skipped)

        file_path = selected_path
        folder_to_check = os.path.dirname(file_path)
        if folder_to_check and folder_to_check not in known_paths:
            known_paths.append(folder_to_check)

    # Return found file_path
    return (file_path, modified, skipped)
