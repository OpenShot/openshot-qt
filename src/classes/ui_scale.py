"""
 @file
 @brief UI scale limits shared by startup and preferences
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


def minimum_ui_scale(qt_version):
    """Avoid Qt's pre-6.7 QPainter clamp of device pixel ratios below one.

    A global scale below one can work on a high-DPI display, then break
    painting when the window moves to a display using 100% system scaling.
    Use a display-independent limit so moving windows remains safe.
    """
    version = tuple(int(part) for part in qt_version.split(".")[:2])
    return 0.5 if version >= (6, 7) else 1.0
