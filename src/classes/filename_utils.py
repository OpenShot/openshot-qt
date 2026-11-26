"""
 @file
 @brief Helpers for validating a user-supplied file name before it reaches the filesystem
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

import sys

# Windows forbids these characters in a file name; POSIX only forbids "/" (and NUL,
# which is handled separately - no filesystem accepts it in a name).
WINDOWS_INVALID_CHARS = '<>:"/\\|?*'
POSIX_INVALID_CHARS = "/"


def _platform(platform=None):
    return sys.platform if platform is None else platform


def invalid_characters(file_name, platform=None):
    """Return the sorted, de-duplicated characters in ``file_name`` that the
    operating system ``platform`` refuses in a file name (never in a path - just
    the name itself). An empty list means the name is writable everywhere."""
    if not file_name:
        return []

    platform = _platform(platform)
    # No filesystem accepts a null byte in a file name - it would truncate the path.
    invalid = {"\x00"}
    if platform.startswith("win"):
        # Windows also drops a trailing dot or space, so treat those as invalid instead
        # of letting the name silently change under the user's feet.
        invalid.update(WINDOWS_INVALID_CHARS)
        if file_name[-1] in ". ":
            invalid.add(file_name[-1])
    else:
        invalid.update(POSIX_INVALID_CHARS)

    found = {char for char in file_name if char in invalid}
    return sorted(found)


def is_valid_file_name(file_name, platform=None):
    """True when ``file_name`` can be written as-is by the operating system
    ``platform`` (defaults to the current one)."""
    if file_name is None or not file_name.strip():
        return False

    return not invalid_characters(file_name, platform)
