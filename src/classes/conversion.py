"""
 @file
 @brief This file deals with value conversions
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Frank Dana <ferdnyc AT gmail com>

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

def zoomToSeconds(zoomValue):
    """ Convert zoom factor (slider position) into scale-seconds """

    if (zoomValue <= 5):
        # Under 1 minute, convert to seconds (exponential)
        return 2**zoomValue
    elif (zoomValue <= 11):
        # convert to N minutes (exponential), in seconds
        return 60 * (2**(zoomValue-6))
    else:
        # Over 1 hour, convert to N hours (exponential), in seconds
        return 3600 * (2**(zoomValue-12))


def secondsToZoom(scaleValue):
    """ Convert a number of seconds to a timeline zoom factor """

    return int(math.log(scaleValue,2))

