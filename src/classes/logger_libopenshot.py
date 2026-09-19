"""
 @file
 @brief Configure independent Python and libopenshot log files
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
import openshot
from classes import info, log_config
from classes.logger import log, set_level_file, set_level_console


def configure(debug=False, initialize=False, ui_debug=False):
    """Configure independent Python/native sinks. No forwarding thread is needed."""
    logger_type = getattr(openshot, "Logger", None)
    native = logger_type.Instance() if logger_type is not None else None
    if initialize and native is None:
        log.warning("Installed libopenshot lacks the Logger API; native logging controls "
                    "are unavailable. Update libopenshot and its Python bindings.")
    if initialize and native is not None:
        # The GUI owns the destination; standalone users can use LIBOPENSHOT_LOG_FILE.
        native.Path(os.path.join(info.USER_PATH, "libopenshot.log"))
    for component in ("python", "native"):
        if component == "native" and native is None:
            continue
        for destination in ("file", "console"):
            value, source = log_config.resolve(
                component, destination, ui_debug if component == "python" else debug)
            if component == "python":
                setter = set_level_file if destination == "file" else set_level_console
                setter(log_config.LEVELS[value])
            elif destination == "file":
                native.SetFileLevel(value)
            else:
                native.SetConsoleLevel(value)
            log.debug("Logging %s %s: %s (%s)", component, destination, value, source)


def close():
    logger_type = getattr(openshot, "Logger", None)
    if logger_type is not None:
        logger_type.Instance().Close()
