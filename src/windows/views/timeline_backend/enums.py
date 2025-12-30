"""
 @file
 @brief This file contains enums used in the timeline view (mostly for menu handling)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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

from enum import Enum, auto


class MenuFade(Enum):
    NONE = 0
    IN_FAST = auto()
    IN_SLOW = auto()
    OUT_FAST = auto()
    OUT_SLOW = auto()
    IN_OUT_FAST = auto()
    IN_OUT_SLOW = auto()


class MenuRotate(Enum):
    NONE = 0
    RIGHT_90 = auto()
    LEFT_90 = auto()
    FLIP_180 = auto()


class MenuLayout(Enum):
    NONE = 0
    CENTER = auto()
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()
    ALL_WITH_ASPECT = auto()
    ALL_WITHOUT_ASPECT = auto()


class MenuAlign(Enum):
    LEFT = 0
    RIGHT = auto()


class MenuAnimate(Enum):
    NONE = 0
    IN_50_100 = auto()
    IN_75_100 = auto()
    IN_100_150 = auto()
    OUT_100_75 = auto()
    OUT_100_50 = auto()
    OUT_150_100 = auto()
    CENTER_TOP = auto()
    CENTER_LEFT = auto()
    CENTER_RIGHT = auto()
    CENTER_BOTTOM = auto()
    TOP_CENTER = auto()
    LEFT_CENTER = auto()
    RIGHT_CENTER = auto()
    BOTTOM_CENTER = auto()
    TOP_BOTTOM = auto()
    LEFT_RIGHT = auto()
    RIGHT_LEFT = auto()
    BOTTOM_TOP = auto()
    RANDOM = auto()


class MenuVolume(Enum):
    NONE = 1
    FADE_IN_FAST = auto()
    FADE_IN_SLOW = auto()
    FADE_OUT_FAST = auto()
    FADE_OUT_SLOW = auto()
    FADE_IN_OUT_FAST = auto()
    FADE_IN_OUT_SLOW = auto()
    LEVEL = auto()


class MenuTransform(Enum):
    DEFAULT = 0


class MenuTime(Enum):
    NONE = 0
    FORWARD = auto()
    BACKWARD = auto()
    REVERSE = auto()
    FREEZE = auto()
    FREEZE_ZOOM = auto()


class MenuCopy(Enum):
    ALL = -1
    CLIP = 0
    KEYFRAMES_ALL = auto()
    KEYFRAMES_ALPHA = auto()
    KEYFRAMES_SCALE = auto()
    KEYFRAMES_SHEAR = auto()
    KEYFRAMES_ROTATE = auto()
    KEYFRAMES_LOCATION = auto()
    KEYFRAMES_TIME = auto()
    KEYFRAMES_VOLUME = auto()
    EFFECT = auto()
    ALL_EFFECTS = auto()
    PASTE = auto()
    TRANSITION = auto()
    KEYFRAMES_BRIGHTNESS = auto()
    KEYFRAMES_CONTRAST = auto()


class MenuSlice(Enum):
    KEEP_BOTH = 0
    KEEP_LEFT = auto()
    KEEP_RIGHT = auto()


class MenuSplitAudio(Enum):
    SINGLE = 0
    MULTIPLE = auto()
