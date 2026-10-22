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
    # ── In ───────────────────────────────────────────────────────────────────
    SLIDE_IN_LEFT = auto()
    SLIDE_IN_RIGHT = auto()
    SLIDE_IN_TOP = auto()
    SLIDE_IN_BOTTOM = auto()
    BLUR_IN = auto()
    WIPE_IN_CIRCLE_EXPAND = auto()
    WIPE_IN_CIRCLE_SHRINK = auto()
    WIPE_IN_FADE = auto()
    WIPE_IN_LEFT = auto()
    WIPE_IN_RIGHT = auto()
    WIPE_IN_TOP = auto()
    WIPE_IN_BOTTOM = auto()
    FOCUS_WIPE_IN_CIRCLE_EXPAND = auto()
    FOCUS_WIPE_IN_CIRCLE_SHRINK = auto()
    FOCUS_WIPE_IN_LEFT = auto()
    FOCUS_WIPE_IN_RIGHT = auto()
    FOCUS_WIPE_IN_TOP = auto()
    FOCUS_WIPE_IN_BOTTOM = auto()
    POP_IN = auto()
    SPIRAL_IN = auto()
    BACK_IN_DOWN = auto()
    BACK_IN_LEFT = auto()
    BACK_IN_RIGHT = auto()
    BACK_IN_UP = auto()
    BOUNCE_IN = auto()
    BOUNCE_IN_DOWN = auto()
    BOUNCE_IN_LEFT = auto()
    BOUNCE_IN_RIGHT = auto()
    BOUNCE_IN_UP = auto()
    # ── Out ──────────────────────────────────────────────────────────────────
    SLIDE_OUT_LEFT = auto()
    SLIDE_OUT_RIGHT = auto()
    SLIDE_OUT_TOP = auto()
    SLIDE_OUT_BOTTOM = auto()
    BLUR_OUT = auto()
    WIPE_OUT_CIRCLE_EXPAND = auto()
    WIPE_OUT_CIRCLE_SHRINK = auto()
    WIPE_OUT_FADE = auto()
    WIPE_OUT_LEFT = auto()
    WIPE_OUT_RIGHT = auto()
    WIPE_OUT_TOP = auto()
    WIPE_OUT_BOTTOM = auto()
    FOCUS_WIPE_OUT_CIRCLE_EXPAND = auto()
    FOCUS_WIPE_OUT_CIRCLE_SHRINK = auto()
    FOCUS_WIPE_OUT_LEFT = auto()
    FOCUS_WIPE_OUT_RIGHT = auto()
    FOCUS_WIPE_OUT_TOP = auto()
    FOCUS_WIPE_OUT_BOTTOM = auto()
    POP_OUT = auto()
    SPIRAL_OUT = auto()
    BACK_OUT_DOWN = auto()
    BACK_OUT_LEFT = auto()
    BACK_OUT_RIGHT = auto()
    BACK_OUT_UP = auto()
    BOUNCE_OUT = auto()
    BOUNCE_OUT_DOWN = auto()
    BOUNCE_OUT_LEFT = auto()
    BOUNCE_OUT_RIGHT = auto()
    BOUNCE_OUT_UP = auto()
    # ── Emphasis ─────────────────────────────────────────────────────────────
    BOUNCE = auto()
    FLASH = auto()
    PULSE = auto()
    RUBBER_BAND = auto()
    SHAKE_X = auto()
    SHAKE_Y = auto()
    SWING = auto()
    TADA = auto()
    WOBBLE = auto()
    JELLO = auto()
    HEART_BEAT = auto()
    # ── Camera ───────────────────────────────────────────────────────────────
    CAM_PUSH_IN = auto()
    CAM_PULL_OUT = auto()
    CAM_PAN_AUTO = auto()
    CAM_PAN_LEFT = auto()
    CAM_PAN_RIGHT = auto()
    CAM_PAN_UP = auto()
    CAM_PAN_DOWN = auto()
    KEN_BURNS_IN = auto()
    KEN_BURNS_OUT = auto()
    KEN_BURNS_IN_LEFT_TO_RIGHT = auto()
    KEN_BURNS_IN_RIGHT_TO_LEFT = auto()
    KEN_BURNS_IN_TOP_TO_BOTTOM = auto()
    KEN_BURNS_IN_BOTTOM_TO_TOP = auto()
    KEN_BURNS_OUT_LEFT_TO_RIGHT = auto()
    KEN_BURNS_OUT_RIGHT_TO_LEFT = auto()
    KEN_BURNS_OUT_TOP_TO_BOTTOM = auto()
    KEN_BURNS_OUT_BOTTOM_TO_TOP = auto()
    # ── Credits ──────────────────────────────────────────────────────────────
    CREDITS_UP = auto()
    CREDITS_DOWN = auto()


class MenuVolume(Enum):
    NONE = 1
    FADE_IN_FAST = auto()
    FADE_IN_SLOW = auto()
    FADE_OUT_FAST = auto()
    FADE_OUT_SLOW = auto()
    FADE_IN_OUT_FAST = auto()
    FADE_IN_OUT_SLOW = auto()
    LEVEL = auto()


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
    TEXT_STYLE = auto()


class MenuSlice(Enum):
    KEEP_BOTH = 0
    KEEP_LEFT = auto()
    KEEP_RIGHT = auto()


class MenuSplitAudio(Enum):
    SINGLE = 0
    MULTIPLE = auto()
