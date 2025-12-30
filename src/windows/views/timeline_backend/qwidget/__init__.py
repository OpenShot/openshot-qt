"""
 @file
 @brief QWidget-based timeline widget composed from focused mixins.
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

from .base import TimelineWidgetBase, TimelineEvents, _ConditionalTransition
from .clip import ClipInteractionMixin
from .effect import EffectInteractionMixin
from .keyframe import KeyframeMixin
from .keyframe_panel import KeyframePanelMixin
from .playhead import PlayheadMixin
from .track import TrackInteractionMixin
from .transition import TransitionInteractionMixin


class TimelineWidget(
    ClipInteractionMixin,
    TransitionInteractionMixin,
    EffectInteractionMixin,
    TrackInteractionMixin,
    KeyframePanelMixin,
    KeyframeMixin,
    PlayheadMixin,
    TimelineWidgetBase,
):
    """Concrete QWidget timeline implementation."""


__all__ = [
    "TimelineWidget",
    "TimelineWidgetBase",
    "TimelineEvents",
    "_ConditionalTransition",
]
