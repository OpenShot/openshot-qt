"""
 @file
 @brief Painter classes for the QWidget timeline backend.
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

from .background import BackgroundPainter
from .cache import PlaybackCachePainter
from .clip import ClipPainter
from .keyframe import KeyframePainter
from .keyframepanel import KeyframePanelPainter
from .marker import MarkerPainter
from .playhead import PlayheadPainter
from .ruler import RulerPainter
from .scrollbar import ScrollbarPainter
from .selection import SelectionPainter
from .track import TrackPainter
from .transition import TransitionPainter

__all__ = [
    "BackgroundPainter",
    "PlaybackCachePainter",
    "ClipPainter",
    "KeyframePainter",
    "KeyframePanelPainter",
    "MarkerPainter",
    "PlayheadPainter",
    "RulerPainter",
    "ScrollbarPainter",
    "SelectionPainter",
    "TrackPainter",
    "TransitionPainter",
]
