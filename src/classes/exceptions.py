"""
 @file
 @brief This file deals with unhandled exceptions
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
import platform

from classes import info
from classes import sentry


def tail_file(f, n, offset=None):
    """Read the end of a file (n number of lines)"""
    avg_line_length = 90
    to_read = n + (offset or 0)

    while True:
        try:
            # Seek to byte position
            f.seek(-(avg_line_length * to_read), 2)
        except IOError:
            # Byte position not found
            f.seek(0)
        pos = f.tell()
        lines = f.read().splitlines()
        if len(lines) >= to_read or pos == 0:
            # Return the lines
            return lines[-to_read:offset and -offset or None]
        avg_line_length *= 2


def libopenshot_crash_recovery():
    """Walk libopenshot.log for the last line before this launch"""
    from classes.metrics import track_metric_error

    log_path = os.path.join(info.USER_PATH, "libopenshot.log")
    last_log_line = ""
    last_stack_trace = ""
    found_stack = False
    log_start_counter = 0
    if not os.path.exists(log_path):
        return
    with open(log_path, "rb") as f:
        # Read from bottom up
        for raw_line in reversed(tail_file(f, 500)):
            # Format and remove extra spaces from line
            line = " ".join(str(raw_line, 'utf-8').split()) + "\n"
            # Detect stack trace
            if "End of Stack Trace" in line:
                found_stack = True
                continue
            if "Unhandled Exception: Stack Trace" in line:
                found_stack = False
                continue
            if "libopenshot logging:" in line:
                log_start_counter += 1
                if log_start_counter > 1:
                    # Found the previous log start, too old now
                    break

            if found_stack:
                # Append line to beginning of stacktrace
                last_stack_trace = line + last_stack_trace

            # Ignore certain useless lines
            line.strip()
            if all(["---" not in line,
                    "libopenshot logging:" not in line,
                    not last_log_line,
                    ]):
                last_log_line = line

    # Split last stack trace (if any)
    if last_stack_trace:
        # Get top line of stack trace (for metrics)
        exception_lines = last_stack_trace.split("\n")
        last_log_line = exception_lines[0].strip()

        # Format and add exception log to Sentry context
        # Split list of lines into smaller lists (so we don't exceed Sentry limits)
        sentry.set_context("libopenshot", {"stack-trace": exception_lines})
        sentry.set_tag("component", "libopenshot")

    # Clear / normalize log line (so we can roll them up in the analytics)
    if last_log_line:
        # Format last log line based on OS (since each OS can be formatted differently)
        if platform.system() == "Darwin":
            last_log_line = "mac-%s" % last_log_line[58:].strip()
        elif platform.system() == "Windows":
            last_log_line = "windows-%s" % last_log_line
        elif platform.system() == "Linux":
            last_log_line = "linux-%s" % last_log_line.replace("/usr/local/lib/", "")

        # Remove '()' from line, and split. Trying to grab the beginning of the log line.
        last_log_line = last_log_line.replace("()", "")
        log_parts = last_log_line.split("(")
        if len(log_parts) == 2:
            last_log_line = "-%s" % log_parts[0].replace(
                "logger_libopenshot:INFO ", "").strip()[:64]
        elif len(log_parts) >= 3:
            last_log_line = "-%s (%s" % (log_parts[0].replace(
                "logger_libopenshot:INFO ", "").strip()[:64], log_parts[1])
    else:
        last_log_line = ""

    # Report exception (with last libopenshot line... if found)
    track_metric_error("unhandled-crash%s" % last_log_line, True)

    return last_log_line
