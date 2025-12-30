"""
 @file
 @brief Geometry helpers split into focused mixins.
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

from .base import GeometryBase
from .clip import ClipGeometryMixin
from .marker import MarkerGeometryMixin
from .track import TrackGeometryMixin
from .transition import TransitionGeometryMixin


class Geometry(
    MarkerGeometryMixin,
    TransitionGeometryMixin,
    ClipGeometryMixin,
    TrackGeometryMixin,
    GeometryBase,
):
    """Concrete geometry helper combining all mixins."""


__all__ = ["Geometry"]
