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

import os
import html
from classes import info
from classes.app import get_app
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFileDialog, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel
)

# Keep track of all previously checked paths, and keep checking them
known_paths = [info.HOME_PATH]


def _relative_display_path(file_path, starting_dir):
    if starting_dir:
        try:
            return os.path.relpath(file_path, starting_dir)
        except Exception:
            pass
    return file_path


def _relative_display_path_html(file_path, starting_dir):
    rel_path = _relative_display_path(file_path, starting_dir)
    rel_dir, rel_name = os.path.split(rel_path)
    if rel_dir:
        return f"{html.escape(rel_dir)}/{'<b>' + html.escape(rel_name) + '</b>'}"
    return f"<b>{html.escape(rel_name)}</b>"


def _relative_display_dir(file_path, starting_dir):
    rel_path = _relative_display_path(file_path, starting_dir)
    rel_dir = os.path.dirname(rel_path)
    if rel_dir:
        return f"{rel_dir}/"
    return "./"


def _show_missing_file_dialog(file_name, file_path, starting_dir):
    _ = get_app()._tr
    dialog = QDialog(None)
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

    dir_label = QLabel(_relative_display_dir(file_path, starting_dir))
    dir_label.setObjectName("lblMissingFilePath")
    dir_label.setWordWrap(True)
    dir_label.setTextFormat(Qt.PlainText)
    dir_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    dir_label.setContentsMargins(8, 0, 0, 0)
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
        selected_path = QFileDialog.getExistingDirectory(
            None,
            _("Find directory that contains: %s") % file_name,
            starting_dir,
        )
        if selected_path:
            result["action"] = "locate"
            result["path"] = os.path.join(selected_path, file_name)
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

    dialog.exec_()
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
