"""
 @file
 @brief This file converts a float time value (i.e. seconds) to parts of time
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

import math


def padNumber(value, pad_length):
    format_mask = '%%0%sd' % pad_length
    return format_mask % value


def secondsToTime(secs, fps_num, fps_den):
    # calculate time of playhead
    milliseconds = secs * 1000
    sec = math.floor(milliseconds / 1000)
    milli = milliseconds % 1000
    min = math.floor(sec / 60)
    sec = sec % 60
    hour = math.floor(min / 60)
    min = min % 60
    day = math.floor(hour / 24)
    hour = hour % 24
    week = math.floor(day / 7)
    day = day % 7

    frame = round((milli / 1000.0) * (fps_num / fps_den)) + 1
    return {"week": padNumber(week, 2), "day": padNumber(day, 2), "hour": padNumber(hour, 2),
            "min": padNumber(min, 2), "sec": padNumber(sec, 2), "milli": padNumber(milli, 2),
            "frame": padNumber(frame, 2)}
