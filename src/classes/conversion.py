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

zoomSeconds = [1,
               7,
               14,
               24,
               54,
               94,
               118,
               174,
               205,
               276,
               356,
               445,
               542,
               648,
               761,
               881,
               1075,
               1212,
               1428,
               1578,
               1813,
               2141,
               2396,
               2745,
               3192,
               3645,
               4187,
               4890,
               5988,
               7200
               ]

def zoomToSeconds(zoomValue):
    """ Convert zoom factor (slider position) into scale-seconds """
    return zoomSeconds[zoomValue] or 1


def secondsToZoom(scaleValue):
    """ Convert a number of seconds to a timeline zoom factor """
    if scaleValue in zoomSeconds:
        return zoomSeconds[scaleValue]
    else:
        # Find closest zoom
        closestValue = zoomSeconds[0]
        for zoomValue in zoomSeconds:
            if zoomValue < scaleValue:
                closestValue = zoomValue
        return zoomSeconds.index(closestValue)

