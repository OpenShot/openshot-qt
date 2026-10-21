"""
 @file
 @brief One-click Motion presets for timeline clips (Motion clip menu and CLI)

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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
from copy import deepcopy
import json
import os

import openshot
from classes import info
from classes.animation_presets import PRESETS as _ANIMATION_PRESETS, KEYFRAME_EASING as _KEYFRAME_EASING
from classes.camera_motion import (
    KEN_BURNS_AUTO,
    KEN_BURNS_BOTTOM_TO_TOP,
    KEN_BURNS_LEFT_TO_RIGHT,
    KEN_BURNS_RIGHT_TO_LEFT,
    KEN_BURNS_TOP_TO_BOTTOM,
    PAN_AUTO,
    PAN_DOWN,
    PAN_LEFT,
    PAN_RIGHT,
    PAN_UP,
    camera_pan_keyframes,
    ken_burns_keyframes,
    push_pull_keyframes,
    source_dimensions_from_reader,
)
from classes.keyframe_editing import add_point, remove_points_in_range
from classes.look_presets import LOOK_EFFECT_UI_MENU
from .timeline_backend.enums import MenuAnimate

MOTION_EFFECT_UI_MENU = "motion"

# JSON animation name for each MenuAnimate value
_JSON_ANIM = {
    MenuAnimate.BACK_IN_DOWN:    "backInDown",
    MenuAnimate.BACK_IN_LEFT:    "backInLeft",
    MenuAnimate.BACK_IN_RIGHT:   "backInRight",
    MenuAnimate.BACK_IN_UP:      "backInUp",
    MenuAnimate.BOUNCE_IN:       "bounceIn",
    MenuAnimate.BOUNCE_IN_DOWN:  "bounceInDown",
    MenuAnimate.BOUNCE_IN_LEFT:  "bounceInLeft",
    MenuAnimate.BOUNCE_IN_RIGHT: "bounceInRight",
    MenuAnimate.BOUNCE_IN_UP:    "bounceInUp",
    MenuAnimate.BACK_OUT_DOWN:   "backOutDown",
    MenuAnimate.BACK_OUT_LEFT:   "backOutLeft",
    MenuAnimate.BACK_OUT_RIGHT:  "backOutRight",
    MenuAnimate.BACK_OUT_UP:     "backOutUp",
    MenuAnimate.BOUNCE_OUT:      "bounceOut",
    MenuAnimate.BOUNCE_OUT_DOWN: "bounceOutDown",
    MenuAnimate.BOUNCE_OUT_LEFT: "bounceOutLeft",
    MenuAnimate.BOUNCE_OUT_RIGHT:"bounceOutRight",
    MenuAnimate.BOUNCE_OUT_UP:   "bounceOutUp",
    MenuAnimate.BOUNCE:          "bounce",
    MenuAnimate.FLASH:           "flash",
    MenuAnimate.PULSE:           "pulse",
    MenuAnimate.RUBBER_BAND:     "rubberBand",
    MenuAnimate.SHAKE_X:         "shakeX",
    MenuAnimate.SHAKE_Y:         "shakeY",
    MenuAnimate.SWING:           "swing",
    MenuAnimate.TADA:            "tada",
    MenuAnimate.WOBBLE:          "wobble",
    MenuAnimate.JELLO:           "jello",
    MenuAnimate.HEART_BEAT:      "heartBeat",
}

_EMPHASIS_ACTIONS = frozenset({
    MenuAnimate.BOUNCE, MenuAnimate.FLASH, MenuAnimate.PULSE,
    MenuAnimate.RUBBER_BAND, MenuAnimate.SHAKE_X, MenuAnimate.SHAKE_Y,
    MenuAnimate.SWING, MenuAnimate.TADA,
    MenuAnimate.WOBBLE, MenuAnimate.JELLO, MenuAnimate.HEART_BEAT,
})

_IN_ACTIONS = frozenset({
    MenuAnimate.BACK_IN_DOWN, MenuAnimate.BACK_IN_LEFT,
    MenuAnimate.BACK_IN_RIGHT, MenuAnimate.BACK_IN_UP,
    MenuAnimate.BOUNCE_IN, MenuAnimate.BOUNCE_IN_DOWN,
    MenuAnimate.BOUNCE_IN_LEFT, MenuAnimate.BOUNCE_IN_RIGHT,
    MenuAnimate.BOUNCE_IN_UP,
})


def apply_motion(data, action, fps_float, base_clip=None, playhead_frame=1,
                 project_size=(None, None), load_reader=None, new_id=None):
    """Apply one Motion menu preset to clip JSON, in place.

    Each MenuAnimate action encodes the animation type and its zone:
      In actions  → first 1 second of the clip
      Out actions → last 1 second of the clip
      Emphasis    → 1 second from playhead_frame (timeline frame), if inside the clip
      Continuous  → entire clip duration
      Pan actions → entire clip, also sets scale mode to SCALE_CROP

    base_clip is a native clip used to read current values (identity if None).
    load_reader(path) loads a wipe mask reader; new_id() generates effect IDs.

    Keyframe coordinates follow OpenShot conventions:
      location ±1.0 ≈ one full frame dimension (offscreen)
      scale    1.0  = 100%
      rotation degrees (positive = clockwise)
      shear    dimensionless skew factor
      origin   0.0–1.0 (0 = top/left edge, 0.5 = center, 1.0 = bottom/right)
    """
    # Clip frame boundaries (1-based, relative to clip content start)
    s = round(float(data["start"]) * fps_float) + 1   # first frame
    e = round(float(data["end"])   * fps_float) + 1   # last frame

    # 1-second enter / exit zones clamped to clip length
    zone = max(1, round(fps_float))
    in_end    = min(s + zone, e)   # end of "In" zone
    out_start = max(s, e - zone)   # start of "Out" zone

    # Emphasis: fixed 1-second window at playhead (if inside clip).
    # The playhead frame is timeline-global, while clip keyframes are
    # stored in the clip's local/source frame space.
    try:
        timeline_seconds = max(0.0, (int(playhead_frame or 1) - 1) / fps_float)
        clip_position = float(data.get("position", 0.0))
        clip_playhead = round(
            (float(data["start"]) + timeline_seconds - clip_position) * fps_float
        ) + 1
    except Exception:
        clip_playhead = s
    if s <= clip_playhead <= e:
        emph_start = clip_playhead
    else:
        emph_start = s
    emph_end = min(emph_start + zone, e)

    # ── helpers ───────────────────────────────────────────────────
    def kf(frame, val, interp=openshot.BEZIER):
        """Build a keyframe point dict."""
        return json.loads(openshot.Point(int(frame), val, interp).Json())

    def add(key, *pts):
        """Append keyframe points to a clip channel."""
        for p in pts:
            add_point(data[key], p)

    # Read current clip state BEFORE any edits
    c = base_clip

    _PROP_IDENTITY = {
        'scale_x': 1.0, 'scale_y': 1.0,
        'location_x': 0.0, 'location_y': 0.0,
        'alpha': 1.0, 'rotation': 0.0,
        'shear_x': 0.0, 'shear_y': 0.0,
    }

    def _base(prop, frame):
        """Return the clip's current value of prop at frame (identity fallback)."""
        if c is not None:
            obj = getattr(c, prop, None)
            if obj is not None:
                return obj.GetValue(int(round(frame)))
        return _PROP_IDENTITY.get(prop, 0.0)

    def _rel(prop, preset_val, base_val):
        """Adjust a preset value relative to the clip's current base value.
        Scale/alpha are multiplicative; location/rotation/shear are additive."""
        if prop in ('scale_x', 'scale_y', 'alpha'):
            return preset_val * base_val
        return preset_val + base_val

    data["gravity"] = openshot.GRAVITY_CENTER

    # ── RESET (always runs first for non-NONE actions) ─────────────
    # Clears all previous motion keyframes and removes Blur/Mask effects
    # added by prior motion presets so animations are never additive.
    def _reset_motion():
        data["scale"]      = openshot.SCALE_FIT
        data["scale_x"]    = {"Points": [kf(s, 1.0)]}
        data["scale_y"]    = {"Points": [kf(s, 1.0)]}
        data["location_x"] = {"Points": [kf(s, 0.0)]}
        data["location_y"] = {"Points": [kf(s, 0.0)]}
        data["rotation"]   = {"Points": [kf(s, 0.0)]}
        data["shear_x"]    = {"Points": [kf(s, 0.0)]}
        data["shear_y"]    = {"Points": [kf(s, 0.0)]}
        data["alpha"]      = {"Points": [kf(s, 1.0)]}
        data["origin_x"]   = {"Points": [kf(s, 0.5)]}
        data["origin_y"]   = {"Points": [kf(s, 0.5)]}
        effects = data.get("effects", [])
        data["effects"] = [
            eff for eff in (effects if isinstance(effects, list) else [])
            if not isinstance(eff, dict)
            or (
                eff.get("class_name") not in ("Blur", "Mask")
                or eff.get("ui-menu") == LOOK_EFFECT_UI_MENU
            )
        ]

    _WIPE_SVG_FILENAMES = {
        "circle_in_to_out.svg",
        "circle_out_to_in.svg",
        "fade.svg",
        "wipe_left_to_right.svg",
        "wipe_right_to_left.svg",
        "wipe_top_to_bottom.svg",
        "wipe_bottom_to_top.svg",
    }

    def _find_or_create_motion_effect(class_name):
        """Return a reusable motion effect and collapse duplicate preset effects."""
        effects = data.get("effects")
        if not isinstance(effects, list):
            effects = []
            data["effects"] = effects

        def _points(prop):
            data = prop if isinstance(prop, dict) else {}
            return data.get("Points") if isinstance(data.get("Points"), list) else []

        def _point_values(prop):
            return [point.get("co", {}).get("Y") for point in _points(prop)]

        def _is_legacy_motion_effect(eff):
            if eff.get("ui-menu") not in (None, ""):
                return False
            if class_name == "Blur":
                horizontal = _point_values(eff.get("horizontal_radius"))
                vertical = _point_values(eff.get("vertical_radius"))
                return (
                    horizontal == vertical
                    and horizontal in ([50.0, 0.0], [0.0, 50.0])
                )
            if class_name == "Mask":
                reader = eff.get("mask_reader") or eff.get("reader") or {}
                path = reader.get("path", "") if isinstance(reader, dict) else ""
                brightness = _point_values(eff.get("brightness"))
                return (
                    os.path.basename(path) in _WIPE_SVG_FILENAMES
                    and brightness in ([1.0, -1.0], [-1.0, 1.0])
                )
            return False

        matching_indexes = [
            idx for idx, eff in enumerate(effects)
            if isinstance(eff, dict)
            and eff.get("class_name") == class_name
            and (
                eff.get("ui-menu") == MOTION_EFFECT_UI_MENU
                or _is_legacy_motion_effect(eff)
            )
        ]
        if matching_indexes:
            keep_index = matching_indexes[0]
            fx = effects[keep_index]
            fx["ui-menu"] = MOTION_EFFECT_UI_MENU
            for idx in reversed(matching_indexes[1:]):
                del effects[idx]
            return fx, False

        effect = openshot.EffectInfo().CreateEffect(class_name)
        fx = json.loads(effect.Json())
        fx["id"] = new_id()
        fx["ui-menu"] = MOTION_EFFECT_UI_MENU
        effects.append(fx)
        return fx, True

    def _set_motion_effect_points(fx, prop, *pts, replace_all=False):
        if not isinstance(fx.get(prop), dict) or not isinstance(fx[prop].get("Points"), list):
            fx[prop] = {"Points": []}
        if replace_all:
            fx[prop]["Points"] = []
        else:
            remove_points_in_range(fx[prop], pts[0]["co"]["X"], pts[-1]["co"]["X"])
        for pt in pts:
            add_point(fx[prop], pt)

    def _make_wipe_fx(svg_filename, t_start, t_end, brightness_start, brightness_end,
                      contrast=20.0):
        """Reuse or attach a Mask effect (wipe) using the given SVG transition."""
        svg_path = os.path.join(info.PATH, "transitions", "common", svg_filename)
        reader_json = load_reader(svg_path)
        if not reader_json:
            return
        fx, created = _find_or_create_motion_effect("Mask")
        fx["mask_reader"] = deepcopy(reader_json)
        fx["reader"]      = deepcopy(reader_json)
        x1, y1, x2, y2 = _KEYFRAME_EASING['ease_in_out']
        p0 = kf(t_start, brightness_start)
        p0['handle_right'] = {'X': x1, 'Y': y1}
        p1 = kf(t_end, brightness_end)
        p1['handle_left'] = {'X': x2, 'Y': y2}
        _set_motion_effect_points(fx, "brightness", p0, p1, replace_all=created)
        _set_motion_effect_points(fx, "contrast", kf(t_start, contrast), replace_all=created)

    def _make_blur_fx(t_start, r_start, t_end, r_end):
        """Reuse or attach a Blur effect (horizontal + vertical radius)."""
        fx, created = _find_or_create_motion_effect("Blur")
        x1, y1, x2, y2 = _KEYFRAME_EASING['ease_in_out']

        def _eased_pts():
            q0 = kf(t_start, r_start)
            q0['handle_right'] = {'X': x1, 'Y': y1}
            q1 = kf(t_end, r_end)
            q1['handle_left'] = {'X': x2, 'Y': y2}
            return [q0, q1]

        _set_motion_effect_points(fx, "horizontal_radius", *_eased_pts(), replace_all=created)
        _set_motion_effect_points(fx, "vertical_radius", *_eased_pts(), replace_all=created)

    def _apply_preset(preset_name, t_start, t_end, resting_frame):
        """Apply an animation preset scaled to [t_start, t_end] frames.

        Values are applied relative to the clip's current state at resting_frame:
        scale/alpha are multiplied by the base value; location/rotation/shear
        are offset by it.  Easing handles from KEYFRAME_EASING are applied to
        consecutive point pairs.  The zone [t_start, t_end] is cleared of
        existing keyframes for each touched property before insertion.
        """
        preset = _ANIMATION_PRESETS.get(preset_name, {})
        if not preset:
            return
        src_dur = 30.0  # source frames span 1–31
        tgt_dur = max(1, t_end - t_start)

        for prop, points in preset.items():
            if prop not in data:
                continue

            base = _base(prop, resting_frame)

            # Clear previous keyframes in the animation zone
            remove_points_in_range(data[prop], t_start, t_end)

            # Anchor keyframes at both zone boundaries so no drift occurs
            # when the first/last preset frame doesn't map exactly to t_start/t_end.
            # Preset keyframes that land on t_start or t_end will overwrite these.
            add_point(data[prop], kf(t_start, base))
            add_point(data[prop], kf(t_end,   base))

            # Scale frame positions, adjust values, and record easing names
            scaled = []
            for pt in points:
                src_frame = pt[0]
                src_val   = pt[1]
                easing    = pt[2] if len(pt) > 2 else None
                norm      = (src_frame - 1) / src_dur
                tgt_frame = t_start + round(norm * tgt_dur)
                adj_val   = _rel(prop, src_val, base)
                scaled.append((tgt_frame, adj_val, easing))

            # Build point dicts and apply cubic-bezier handles
            for i, (tgt_frame, adj_val, easing) in enumerate(scaled):
                p = kf(tgt_frame, adj_val)
                # handle_right on current point (controls curve TO next point)
                if easing and easing in _KEYFRAME_EASING:
                    x1, y1, x2, y2 = _KEYFRAME_EASING[easing]
                    p['handle_right'] = {'X': x1, 'Y': y1}
                # handle_left on current point (controls curve FROM previous)
                if i > 0:
                    prev_easing = scaled[i - 1][2]
                    if prev_easing and prev_easing in _KEYFRAME_EASING:
                        _, _, x2, y2 = _KEYFRAME_EASING[prev_easing]
                        p['handle_left'] = {'X': x2, 'Y': y2}
                add_point(data[prop], p)

    # SVG filename → enum mappings for Wipe In (brightness 1 → -1)
    # and Wipe Out (brightness -1 → 1, same SVG file)
    _WIPE_SVG = {
        MenuAnimate.WIPE_IN_CIRCLE_EXPAND:  "circle_in_to_out.svg",
        MenuAnimate.WIPE_IN_CIRCLE_SHRINK:  "circle_out_to_in.svg",
        MenuAnimate.WIPE_IN_FADE:           "fade.svg",
        MenuAnimate.WIPE_IN_LEFT:           "wipe_left_to_right.svg",
        MenuAnimate.WIPE_IN_RIGHT:          "wipe_right_to_left.svg",
        MenuAnimate.WIPE_IN_TOP:            "wipe_top_to_bottom.svg",
        MenuAnimate.WIPE_IN_BOTTOM:         "wipe_bottom_to_top.svg",
        MenuAnimate.WIPE_OUT_CIRCLE_EXPAND: "circle_out_to_in.svg",
        MenuAnimate.WIPE_OUT_CIRCLE_SHRINK: "circle_in_to_out.svg",
        MenuAnimate.WIPE_OUT_FADE:          "fade.svg",
        MenuAnimate.WIPE_OUT_LEFT:          "wipe_left_to_right.svg",
        MenuAnimate.WIPE_OUT_RIGHT:         "wipe_right_to_left.svg",
        MenuAnimate.WIPE_OUT_TOP:           "wipe_top_to_bottom.svg",
        MenuAnimate.WIPE_OUT_BOTTOM:        "wipe_bottom_to_top.svg",
        MenuAnimate.FOCUS_WIPE_IN_CIRCLE_EXPAND:  "circle_in_to_out.svg",
        MenuAnimate.FOCUS_WIPE_IN_CIRCLE_SHRINK:  "circle_out_to_in.svg",
        MenuAnimate.FOCUS_WIPE_IN_LEFT:           "wipe_left_to_right.svg",
        MenuAnimate.FOCUS_WIPE_IN_RIGHT:          "wipe_right_to_left.svg",
        MenuAnimate.FOCUS_WIPE_IN_TOP:            "wipe_top_to_bottom.svg",
        MenuAnimate.FOCUS_WIPE_IN_BOTTOM:         "wipe_bottom_to_top.svg",
        MenuAnimate.FOCUS_WIPE_OUT_CIRCLE_EXPAND: "circle_out_to_in.svg",
        MenuAnimate.FOCUS_WIPE_OUT_CIRCLE_SHRINK: "circle_in_to_out.svg",
        MenuAnimate.FOCUS_WIPE_OUT_LEFT:          "wipe_left_to_right.svg",
        MenuAnimate.FOCUS_WIPE_OUT_RIGHT:         "wipe_right_to_left.svg",
        MenuAnimate.FOCUS_WIPE_OUT_TOP:           "wipe_top_to_bottom.svg",
        MenuAnimate.FOCUS_WIPE_OUT_BOTTOM:        "wipe_bottom_to_top.svg",
    }

    def _camera_context():
        reader = data.get("reader", {}) if isinstance(data, dict) else {}
        source_width, source_height = source_dimensions_from_reader(reader)
        project_width, project_height = project_size
        return project_width, project_height, source_width, source_height

    def _apply_camera_motion(values):
        data["scale"] = openshot.SCALE_CROP
        for prop in ("scale_x", "scale_y", "location_x", "location_y"):
            remove_points_in_range(data[prop], s, e)
        add("scale_x", kf(s, values.scale_x[0]), kf(e, values.scale_x[1]))
        add("scale_y", kf(s, values.scale_y[0]), kf(e, values.scale_y[1]))
        add("location_x", kf(s, values.location_x[0]), kf(e, values.location_x[1]))
        add("location_y", kf(s, values.location_y[0]), kf(e, values.location_y[1]))

    if action == MenuAnimate.NONE:
        _reset_motion()

    else:
        # Ensure effects list exists (reset not called here)
        if not isinstance(data.get("effects"), list):
            data["effects"] = []

        # ── SLIDE IN ──────────────────────────────────────────────
        if action == MenuAnimate.SLIDE_IN_LEFT:
            bx = _base('location_x', in_end)
            remove_points_in_range(data["location_x"], s, in_end)
            add("location_x", kf(s, bx - 1.0), kf(in_end, bx))
        elif action == MenuAnimate.SLIDE_IN_RIGHT:
            bx = _base('location_x', in_end)
            remove_points_in_range(data["location_x"], s, in_end)
            add("location_x", kf(s, bx + 1.0), kf(in_end, bx))
        elif action == MenuAnimate.SLIDE_IN_TOP:
            by = _base('location_y', in_end)
            remove_points_in_range(data["location_y"], s, in_end)
            add("location_y", kf(s, by - 1.0), kf(in_end, by))
        elif action == MenuAnimate.SLIDE_IN_BOTTOM:
            by = _base('location_y', in_end)
            remove_points_in_range(data["location_y"], s, in_end)
            add("location_y", kf(s, by + 1.0), kf(in_end, by))

        # ── SLIDE OUT ─────────────────────────────────────────────
        elif action == MenuAnimate.SLIDE_OUT_LEFT:
            bx = _base('location_x', out_start)
            remove_points_in_range(data["location_x"], out_start, e)
            add("location_x", kf(out_start, bx), kf(e, bx - 1.0))
        elif action == MenuAnimate.SLIDE_OUT_RIGHT:
            bx = _base('location_x', out_start)
            remove_points_in_range(data["location_x"], out_start, e)
            add("location_x", kf(out_start, bx), kf(e, bx + 1.0))
        elif action == MenuAnimate.SLIDE_OUT_TOP:
            by = _base('location_y', out_start)
            remove_points_in_range(data["location_y"], out_start, e)
            add("location_y", kf(out_start, by), kf(e, by - 1.0))
        elif action == MenuAnimate.SLIDE_OUT_BOTTOM:
            by = _base('location_y', out_start)
            remove_points_in_range(data["location_y"], out_start, e)
            add("location_y", kf(out_start, by), kf(e, by + 1.0))

        # ── BLUR IN — blur 50→0 + alpha fade ─────────────────────
        elif action == MenuAnimate.BLUR_IN:
            _make_blur_fx(s, 50.0, in_end, 0.0)
            ba = _base('alpha', in_end)
            remove_points_in_range(data["alpha"], s, in_end)
            add("alpha", kf(s, 0.0), kf(in_end, ba))

        # ── BLUR OUT — alpha fade + blur 0→50 ─────────────────────
        elif action == MenuAnimate.BLUR_OUT:
            _make_blur_fx(out_start, 0.0, e, 50.0)
            ba = _base('alpha', out_start)
            remove_points_in_range(data["alpha"], out_start, e)
            add("alpha", kf(out_start, ba), kf(e, 0.0))

        # ── WIPE IN — Mask effect, brightness 1 → -1 ──────────────
        elif action in (MenuAnimate.WIPE_IN_CIRCLE_EXPAND,
                        MenuAnimate.WIPE_IN_CIRCLE_SHRINK,
                        MenuAnimate.WIPE_IN_FADE,
                        MenuAnimate.WIPE_IN_LEFT, MenuAnimate.WIPE_IN_RIGHT,
                        MenuAnimate.WIPE_IN_TOP,  MenuAnimate.WIPE_IN_BOTTOM):
            _make_wipe_fx(_WIPE_SVG[action], s, in_end, 1.0, -1.0)

        # ── WIPE OUT — Mask effect, brightness -1 → 1 ─────────────
        elif action in (MenuAnimate.WIPE_OUT_CIRCLE_EXPAND,
                        MenuAnimate.WIPE_OUT_CIRCLE_SHRINK,
                        MenuAnimate.WIPE_OUT_FADE,
                        MenuAnimate.WIPE_OUT_LEFT, MenuAnimate.WIPE_OUT_RIGHT,
                        MenuAnimate.WIPE_OUT_TOP,  MenuAnimate.WIPE_OUT_BOTTOM):
            _make_wipe_fx(_WIPE_SVG[action], out_start, e, -1.0, 1.0)

        # ── FOCUS WIPE IN — blur 50→0, then wipe reveals ──────────
        elif action in (MenuAnimate.FOCUS_WIPE_IN_CIRCLE_EXPAND,
                        MenuAnimate.FOCUS_WIPE_IN_CIRCLE_SHRINK,
                        MenuAnimate.FOCUS_WIPE_IN_LEFT, MenuAnimate.FOCUS_WIPE_IN_RIGHT,
                        MenuAnimate.FOCUS_WIPE_IN_TOP,  MenuAnimate.FOCUS_WIPE_IN_BOTTOM):
            _make_blur_fx(s, 50.0, in_end, 0.0)
            _make_wipe_fx(_WIPE_SVG[action], s, in_end, 1.0, -1.0, contrast=10.0)

        # ── FOCUS WIPE OUT — wipe hides, blur 0→50 ───────────────
        elif action in (MenuAnimate.FOCUS_WIPE_OUT_CIRCLE_EXPAND,
                        MenuAnimate.FOCUS_WIPE_OUT_CIRCLE_SHRINK,
                        MenuAnimate.FOCUS_WIPE_OUT_LEFT, MenuAnimate.FOCUS_WIPE_OUT_RIGHT,
                        MenuAnimate.FOCUS_WIPE_OUT_TOP,  MenuAnimate.FOCUS_WIPE_OUT_BOTTOM):
            _make_blur_fx(out_start, 0.0, e, 50.0)
            _make_wipe_fx(_WIPE_SVG[action], out_start, e, -1.0, 1.0, contrast=10.0)

        # ── POP ───────────────────────────────────────────────────
        elif action == MenuAnimate.POP_IN:
            peak = in_end - max(1, round(0.2 * (in_end - s)))
            bsx = _base('scale_x', in_end)
            bsy = _base('scale_y', in_end)
            ba  = _base('alpha',   in_end)
            for prop in ("scale_x", "scale_y", "alpha"):
                remove_points_in_range(data[prop], s, in_end)
            add("scale_x", kf(s, 0.0), kf(peak, 1.1 * bsx), kf(in_end, bsx))
            add("scale_y", kf(s, 0.0), kf(peak, 1.1 * bsy), kf(in_end, bsy))
            add("alpha",   kf(s, 0.0), kf(in_end, ba))
        elif action == MenuAnimate.POP_OUT:
            peak = out_start + max(1, round(0.2 * (e - out_start)))
            bsx = _base('scale_x', out_start)
            bsy = _base('scale_y', out_start)
            ba  = _base('alpha',   out_start)
            for prop in ("scale_x", "scale_y", "alpha"):
                remove_points_in_range(data[prop], out_start, e)
            add("scale_x", kf(out_start, bsx), kf(peak, 1.1 * bsx), kf(e, 0.0))
            add("scale_y", kf(out_start, bsy), kf(peak, 1.1 * bsy), kf(e, 0.0))
            add("alpha",   kf(out_start, ba), kf(e, 0.0))

        # ── SPIRAL ────────────────────────────────────────────────
        elif action == MenuAnimate.SPIRAL_IN:
            br  = _base('rotation', in_end)
            bsx = _base('scale_x',  in_end)
            bsy = _base('scale_y',  in_end)
            ba  = _base('alpha',    in_end)
            for prop in ("rotation", "scale_x", "scale_y", "alpha"):
                remove_points_in_range(data[prop], s, in_end)
            add("rotation", kf(s, -360.0 + br), kf(in_end, br))
            add("scale_x",  kf(s, 0.0),         kf(in_end, bsx))
            add("scale_y",  kf(s, 0.0),         kf(in_end, bsy))
            add("alpha",    kf(s, 0.0),         kf(in_end, ba))
        elif action == MenuAnimate.SPIRAL_OUT:
            br  = _base('rotation', out_start)
            bsx = _base('scale_x',  out_start)
            bsy = _base('scale_y',  out_start)
            ba  = _base('alpha',    out_start)
            for prop in ("rotation", "scale_x", "scale_y", "alpha"):
                remove_points_in_range(data[prop], out_start, e)
            add("rotation", kf(out_start, br),  kf(e, 360.0 + br))
            add("scale_x",  kf(out_start, bsx), kf(e, 0.0))
            add("scale_y",  kf(out_start, bsy), kf(e, 0.0))
            add("alpha",    kf(out_start, ba),  kf(e, 0.0))

        # ── JSON PRESETS (Back/Bounce/Flip In/Out + all Emphasis) ──
        elif action in _JSON_ANIM:
            if action in _EMPHASIS_ACTIONS:
                _apply_preset(_JSON_ANIM[action], emph_start, emph_end, emph_start)
            elif action in _IN_ACTIONS:
                _apply_preset(_JSON_ANIM[action], s, in_end, in_end)
            else:
                _apply_preset(_JSON_ANIM[action], out_start, e, out_start)

        # ── CAMERA: PUSH IN / PULL OUT (zoom, SCALE_CROP) ──────────
        elif action == MenuAnimate.CAM_PUSH_IN:
            _apply_camera_motion(push_pull_keyframes(zoom_in=True))
        elif action == MenuAnimate.CAM_PULL_OUT:
            _apply_camera_motion(push_pull_keyframes(zoom_in=False))

        # ── CAMERA: PAN (axis-aware SCALE_CROP framing) ───────────
        elif action in (MenuAnimate.CAM_PAN_AUTO,
                        MenuAnimate.CAM_PAN_LEFT,  MenuAnimate.CAM_PAN_RIGHT,
                        MenuAnimate.CAM_PAN_UP,    MenuAnimate.CAM_PAN_DOWN):
            pan_direction = {
                MenuAnimate.CAM_PAN_AUTO: PAN_AUTO,
                MenuAnimate.CAM_PAN_LEFT: PAN_LEFT,
                MenuAnimate.CAM_PAN_RIGHT: PAN_RIGHT,
                MenuAnimate.CAM_PAN_UP: PAN_UP,
                MenuAnimate.CAM_PAN_DOWN: PAN_DOWN,
            }[action]
            _apply_camera_motion(camera_pan_keyframes(pan_direction, *_camera_context()))

        # ── CAMERA: KEN BURNS (axis-aware zoom + drift) ───────────
        elif action in (
                MenuAnimate.KEN_BURNS_IN, MenuAnimate.KEN_BURNS_OUT,
                MenuAnimate.KEN_BURNS_IN_LEFT_TO_RIGHT,
                MenuAnimate.KEN_BURNS_IN_RIGHT_TO_LEFT,
                MenuAnimate.KEN_BURNS_IN_TOP_TO_BOTTOM,
                MenuAnimate.KEN_BURNS_IN_BOTTOM_TO_TOP,
                MenuAnimate.KEN_BURNS_OUT_LEFT_TO_RIGHT,
                MenuAnimate.KEN_BURNS_OUT_RIGHT_TO_LEFT,
                MenuAnimate.KEN_BURNS_OUT_TOP_TO_BOTTOM,
                MenuAnimate.KEN_BURNS_OUT_BOTTOM_TO_TOP):
            direction = {
                MenuAnimate.KEN_BURNS_IN: KEN_BURNS_AUTO,
                MenuAnimate.KEN_BURNS_OUT: KEN_BURNS_AUTO,
                MenuAnimate.KEN_BURNS_IN_LEFT_TO_RIGHT: KEN_BURNS_LEFT_TO_RIGHT,
                MenuAnimate.KEN_BURNS_IN_RIGHT_TO_LEFT: KEN_BURNS_RIGHT_TO_LEFT,
                MenuAnimate.KEN_BURNS_IN_TOP_TO_BOTTOM: KEN_BURNS_TOP_TO_BOTTOM,
                MenuAnimate.KEN_BURNS_IN_BOTTOM_TO_TOP: KEN_BURNS_BOTTOM_TO_TOP,
                MenuAnimate.KEN_BURNS_OUT_LEFT_TO_RIGHT: KEN_BURNS_LEFT_TO_RIGHT,
                MenuAnimate.KEN_BURNS_OUT_RIGHT_TO_LEFT: KEN_BURNS_RIGHT_TO_LEFT,
                MenuAnimate.KEN_BURNS_OUT_TOP_TO_BOTTOM: KEN_BURNS_TOP_TO_BOTTOM,
                MenuAnimate.KEN_BURNS_OUT_BOTTOM_TO_TOP: KEN_BURNS_BOTTOM_TO_TOP,
            }[action]
            zoom_in = action in (
                MenuAnimate.KEN_BURNS_IN,
                MenuAnimate.KEN_BURNS_IN_LEFT_TO_RIGHT,
                MenuAnimate.KEN_BURNS_IN_RIGHT_TO_LEFT,
                MenuAnimate.KEN_BURNS_IN_TOP_TO_BOTTOM,
                MenuAnimate.KEN_BURNS_IN_BOTTOM_TO_TOP)
            _apply_camera_motion(ken_burns_keyframes(zoom_in, direction, *_camera_context()))

        # ── CREDITS (full scroll, SCALE_CROP) ─────────────────────
        elif action == MenuAnimate.CREDITS_UP:
            data["scale"] = openshot.SCALE_CROP
            add("location_y",
                kf(s,  1.0, openshot.LINEAR),
                kf(e, -1.0, openshot.LINEAR))
        elif action == MenuAnimate.CREDITS_DOWN:
            data["scale"] = openshot.SCALE_CROP
            add("location_y",
                kf(s, -1.0, openshot.LINEAR),
                kf(e,  1.0, openshot.LINEAR))
