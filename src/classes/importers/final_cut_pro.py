"""
 @file
 @brief This file is used to import a Final Cut Pro XML file
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

import json
import os
from urllib.parse import unquote, urlparse
from xml.dom import minidom, Node

import openshot
from PyQt5.QtWidgets import QFileDialog

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.image_types import get_media_type
from classes.path_utils import absolute_path_from_export, absolute_media_path
from classes.query import Clip, Track, File
from windows.views.find_file import find_missing_file


def _pathurl_to_path(path_url, base_folder):
    """Convert a Final Cut pathurl value into a filesystem path."""
    if not path_url:
        return ""
    parsed = urlparse(path_url)
    if parsed.scheme and parsed.scheme.lower() == "file":
        netloc = parsed.netloc
        path = parsed.path or ""
        if netloc and netloc.lower() not in ("", "localhost"):
            path = "/%s%s" % (netloc, path)
        path = unquote(path)
        if len(path) > 2 and path[0] == "/" and path[2:3] == ":":
            # Windows drive letter encoded as /C:/
            path = path[1:]
        return os.path.normpath(path)

    if path_url.startswith("@"):
        return absolute_media_path(path_url)

    normalized = unquote(path_url)
    return absolute_path_from_export(normalized, base_folder)


def _extract_path_from_file_node(file_node, file_lookup, base_folder):
    """Extract pathurl information, supporting referenced file nodes."""
    if not file_node:
        return ""

    path_nodes = file_node.getElementsByTagName("pathurl")
    if path_nodes and path_nodes[0].childNodes:
        return _pathurl_to_path(path_nodes[0].childNodes[0].nodeValue, base_folder)

    # Follow references to shared file definitions
    file_id = file_node.getAttribute("id")
    referenced_node = file_lookup.get(file_id)
    if referenced_node is not None and referenced_node is not file_node:
        ref_paths = referenced_node.getElementsByTagName("pathurl")
        if ref_paths and ref_paths[0].childNodes:
            return _pathurl_to_path(ref_paths[0].childNodes[0].nodeValue, base_folder)
    return ""


def _node_text_content(node):
    """Return the concatenated text within a DOM node, descending into children."""
    if not node:
        return None
    parts = []
    for child in node.childNodes:
        if child.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
            if child.nodeValue:
                parts.append(child.nodeValue)
        elif child.nodeType == Node.ELEMENT_NODE:
            nested = _node_text_content(child)
            if nested:
                parts.append(nested)
    text = "".join(parts).strip()
    return text or None


def _float_value(node_list, default=0.0):
    """Extract a float from the first node in a list, with a default fallback."""
    if not node_list:
        return default
    text_value = _node_text_content(node_list[0])
    if text_value is None:
        return default
    try:
        return float(text_value)
    except (TypeError, ValueError):
        return default


def _center_pixels_to_normalized(x_px, y_px, frame_width, frame_height):
    """Map FCP center pixel coordinates back to normalized OpenShot space."""
    try:
        w = float(frame_width)
        h = float(frame_height)
    except (TypeError, ValueError):
        return x_px, y_px
    if w <= 0 or h <= 0:
        return x_px, y_px
    return ((x_px - (w / 2.0)) / (w / 2.0)), ((y_px - (h / 2.0)) / (h / 2.0))


def _scale_mode_size(src_w, src_h, frame_w, frame_h, scale_mode):
    """Return base scaled dimensions after applying scale mode (before per-axis scale)."""
    try:
        sw = float(src_w)
        sh = float(src_h)
        fw = float(frame_w)
        fh = float(frame_h)
    except (TypeError, ValueError):
        return src_w, src_h
    if sw <= 0 or sh <= 0 or fw <= 0 or fh <= 0:
        return src_w, src_h
    if scale_mode == openshot.SCALE_STRETCH:
        return fw, fh
    if scale_mode == openshot.SCALE_CROP:
        factor = max(fw / sw, fh / sh)
        return sw * factor, sh * factor
    if scale_mode == openshot.SCALE_FIT:
        factor = min(fw / sw, fh / sh)
        return sw * factor, sh * factor
    return sw, sh


def _gravity_offset(gravity, frame_w, frame_h, scaled_w, scaled_h):
    """Top-left origin based on gravity inside the frame."""
    try:
        frame_w = float(frame_w)
        frame_h = float(frame_h)
        scaled_w = float(scaled_w)
        scaled_h = float(scaled_h)
    except (TypeError, ValueError):
        return 0.0, 0.0
    x = 0.0
    y = 0.0
    if gravity == openshot.GRAVITY_TOP:
        x = (frame_w - scaled_w) / 2.0
    elif gravity == openshot.GRAVITY_TOP_RIGHT:
        x = frame_w - scaled_w
    elif gravity == openshot.GRAVITY_LEFT:
        y = (frame_h - scaled_h) / 2.0
    elif gravity == openshot.GRAVITY_CENTER:
        x = (frame_w - scaled_w) / 2.0
        y = (frame_h - scaled_h) / 2.0
    elif gravity == openshot.GRAVITY_RIGHT:
        x = frame_w - scaled_w
        y = (frame_h - scaled_h) / 2.0
    elif gravity == openshot.GRAVITY_BOTTOM_LEFT:
        y = frame_h - scaled_h
    elif gravity == openshot.GRAVITY_BOTTOM:
        x = (frame_w - scaled_w) / 2.0
        y = frame_h - scaled_h
    elif gravity == openshot.GRAVITY_BOTTOM_RIGHT:
        x = frame_w - scaled_w
        y = frame_h - scaled_h
    return x, y


def _value_at_time(points, t, fallback=1.0, max_frames=None):
    """Find last value at or before time t."""
    if not points:
        return fallback
    sorted_points = sorted(points, key=lambda p: p.get("co", {}).get("X", 0))
    last_val = fallback
    for p in sorted_points:
        pt_time = p.get("co", {}).get("X", 0)
        if max_frames is not None:
            pt_time = max(0, min(pt_time, max_frames))
        if pt_time <= t:
            last_val = p.get("co", {}).get("Y", fallback)
        else:
            break
    return last_val


def _clip_merge_key(path, start, end, position):
    """Return a hashable key for matching audio/video clip pairs."""
    if not path:
        return None
    normalized_path = os.path.normcase(os.path.abspath(path))
    return (
        normalized_path,
        round(float(start or 0.0), 4),
        round(float(end or 0.0), 4),
        round(float(position or 0.0), 4)
    )


def _xml_interp_to_point(value):
    """Map Final Cut interpolation data to OpenShot constants."""
    if value is None:
        return openshot.LINEAR

    text_value = str(value).strip()
    lower_value = text_value.lower()
    if lower_value == "linear":
        return openshot.LINEAR
    if lower_value in ("bezier", "ease", "easein", "easeout"):
        return openshot.BEZIER
    if lower_value in ("hold", "constant"):
        return openshot.CONSTANT

    try:
        numeric = int(float(text_value))
    except (ValueError, TypeError):
        numeric = None

    if numeric == 0:
        return openshot.LINEAR
    if numeric == 1:
        return openshot.BEZIER
    if numeric == 2:
        return openshot.CONSTANT

    text = text_value.lower()
    if text.startswith("lin"):
        return openshot.LINEAR
    if text.startswith("bez"):
        return openshot.BEZIER
    if text.startswith("const") or text.startswith("hold"):
        return openshot.CONSTANT

    return openshot.LINEAR


def import_xml():
    """Import final cut pro XML file"""
    app = get_app()
    _ = app._tr

    # Get FPS info
    fps_num = app.project.get("fps").get("num", 24)
    fps_den = app.project.get("fps").get("den", 1)
    fps_float = float(fps_num / fps_den)
    project_width = app.project.get("width") or 1920
    project_height = app.project.get("height") or 1080

    # Get XML path
    recommended_path = app.project.current_filepath or ""
    if not recommended_path:
        recommended_path = info.HOME_PATH
    else:
        recommended_path = os.path.dirname(recommended_path)
    file_path = QFileDialog.getOpenFileName(app.window, _("Import XML..."), recommended_path,
                                            _("Final Cut Pro (*.xml)"), _("Final Cut Pro (*.xml)"))[0]

    if not file_path or not os.path.exists(file_path):
        # User canceled dialog
        return

    # Parse XML file
    xmldoc = minidom.parse(file_path)
    xml_folder = os.path.dirname(os.path.abspath(file_path))

    # Build lookup for shared <file> nodes
    file_lookup = {}
    for file_element in xmldoc.getElementsByTagName("file"):
        file_id = file_element.getAttribute("id")
        if file_id:
            file_lookup[file_id] = file_element

    # Get video tracks
    video_tracks = []
    for video_element in xmldoc.getElementsByTagName("video"):
        for video_track in video_element.getElementsByTagName("track"):
            # Skip empty tracks up front so ordering math matches created tracks
            if video_track.getElementsByTagName("clipitem"):
                video_tracks.append(video_track)
    audio_tracks = []
    for audio_element in xmldoc.getElementsByTagName("audio"):
        for audio_track in audio_element.getElementsByTagName("track"):
            if audio_track.getElementsByTagName("clipitem"):
                audio_tracks.append(audio_track)

    # Pre-compute numbering so audio layers stay below video layers.
    # Tracks are displayed in reversed sorted order, so higher numbers are higher on screen.
    # We give all video tracks a higher range, then audio tracks a lower range.
    stride = 1000000
    all_tracks = app.project.get("layers")
    max_existing = 0
    try:
        max_existing = max(t.get("number", 0) or 0 for t in all_tracks) if all_tracks else 0
    except Exception:
        max_existing = 0
    audio_base = max_existing + stride
    video_base = audio_base + (len(audio_tracks) * stride)
    video_created = 0
    audio_created = 0

    # Loop through tracks
    track_index = 0
    imported_clip_map = {}

    for track_list, track_type in ((video_tracks, "video"), (audio_tracks, "audio")):
        is_audio_track_list = (track_type == "audio")
        for track_element in track_list:
            # Get clipitems on this track (if any)
            clips_on_track = track_element.getElementsByTagName("clipitem")
            if not clips_on_track:
                continue

            track_index += 1

            # Assign track numbers so video layers sit above audio layers after import.
            if is_audio_track_list:
                track_number = audio_base + (audio_created * stride)
                audio_created += 1
            else:
                track_number = video_base + (video_created * stride)
                video_created += 1

            # Prepare to create track lazily (only if clips remain after merging)
            track = None
            locked_nodes = track_element.getElementsByTagName("locked")
            locked_text = _node_text_content(locked_nodes[0]) if locked_nodes else ""
            is_locked = (locked_text or "").strip().upper() == "TRUE"

            def ensure_track():
                nonlocal track
                if track is None:
                    track = Track()
                    track.data = {"number": track_number, "y": 0, "label": "XML Import %s" % track_index, "lock": is_locked}
                    track.save()

            # Loop through clips
            for clip_element in clips_on_track:
                # Get clip path (handles shared file nodes)
                file_elements = clip_element.getElementsByTagName("file")
                if not file_elements:
                    continue
                clip_path = _extract_path_from_file_node(file_elements[0], file_lookup, xml_folder)
                if not clip_path:
                    continue

                clip_path, is_modified, is_skipped = find_missing_file(clip_path)
                if is_skipped:
                    continue

                # Check for this path in our existing project data
                file = File.get(path=clip_path)

                # Load filepath in libopenshot clip object (which will try multiple readers to open it)
                clip_obj = openshot.Clip(clip_path)

                if not file:
                    # Get the JSON for the clip's internal reader
                    try:
                        reader = clip_obj.Reader()
                        file_data = json.loads(reader.Json())

                        # Determine media type
                        file_data["media_type"] = get_media_type(file_data)

                        # Save new file to the project data
                        file = File()
                        file.data = file_data

                        # Save file
                        file.save()
                    except Exception:
                        log.warning('Error building File object for %s' % clip_path, exc_info=1)

                if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
                    # Determine thumb path
                    thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
                else:
                    # Audio file
                    thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

                # Create Clip object
                clip = Clip()
                clip_start_value = _float_value(clip_element.getElementsByTagName("in"), 0.0) / fps_float
                clip_end_value = _float_value(clip_element.getElementsByTagName("out"), 0.0) / fps_float
                clip_position_value = _float_value(clip_element.getElementsByTagName("start"), 0.0) / fps_float

                clip.data = json.loads(clip_obj.Json())
                clip.data["file_id"] = file.id
                clip_name_nodes = clip_element.getElementsByTagName("name")
                clip_title = _node_text_content(clip_name_nodes[0]) if clip_name_nodes else None
                if not clip_title:
                    clip_title = os.path.basename(clip_path)
                clip.data["title"] = clip_title
                clip.data["layer"] = track_number
                clip.data["image"] = thumb_path
                clip.data["position"] = clip_position_value
                clip.data["start"] = clip_start_value
                clip.data["end"] = clip_end_value
                clip.data.setdefault("scale", openshot.SCALE_FIT)
                clip.data.setdefault("gravity", openshot.GRAVITY_CENTER)

                alpha_points = []
                volume_points = []
                location_x_points = []
                location_y_points = []
                scale_points = []
                rotation_points = []
                # Loop through clip's effects
                for effect_element in clip_element.getElementsByTagName("effect"):
                    effectid_nodes = effect_element.getElementsByTagName("effectid")
                    effectid = _node_text_content(effectid_nodes[0]) if effectid_nodes else ""
                    keyframes = effect_element.getElementsByTagName("keyframe")
                    if effectid == "opacity":
                        for keyframe_element in keyframes:
                            keyframe_time = _float_value(keyframe_element.getElementsByTagName("when"), 0.0)
                            keyframe_value = _float_value(keyframe_element.getElementsByTagName("value"), 0.0) / 100.0
                            interp_nodes = keyframe_element.getElementsByTagName("interpolation")
                            interp_value = _node_text_content(interp_nodes[0]) if interp_nodes else None
                            alpha_points.append(
                                {
                                    "co": {
                                        "X": round(keyframe_time),
                                        "Y": keyframe_value
                                    },
                                    "interpolation": _xml_interp_to_point(interp_value)
                                }
                        )
                    elif effectid in ("basicmotion", "basic"):
                        for parameter_element in effect_element.getElementsByTagName("parameter"):
                            parameterid_nodes = parameter_element.getElementsByTagName("parameterid")
                            parameterid = _node_text_content(parameterid_nodes[0]) if parameterid_nodes else ""

                            if parameterid == "center":
                                keyframes = parameter_element.getElementsByTagName("keyframe")
                                for keyframe_element in keyframes:
                                    keyframe_time = _float_value(keyframe_element.getElementsByTagName("when"), 0.0)
                                    value_nodes = keyframe_element.getElementsByTagName("value")
                                    value_node = value_nodes[0] if value_nodes else None
                                    horiz_value = _float_value(value_node.getElementsByTagName("horiz"), 0.0) if value_node else 0.0
                                    vert_value = _float_value(value_node.getElementsByTagName("vert"), 0.0) if value_node else 0.0
                                    # Derive normalized location by removing gravity/scale offsets at this time
                                    scale_mode = clip.data.get("scale", openshot.SCALE_FIT)
                                    gravity = clip.data.get("gravity", openshot.GRAVITY_CENTER)
                                    src_w = (file.data or {}).get("width") if isinstance(file.data, dict) else None
                                    src_h = (file.data or {}).get("height") if isinstance(file.data, dict) else None
                                    base_w, base_h = _scale_mode_size(src_w or 0, src_h or 0, project_width, project_height, scale_mode)
                                    s_val = _value_at_time(scale_points, keyframe_time, 1.0)
                                    scaled_w = base_w * s_val
                                    scaled_h = base_h * s_val
                                    origin_x, origin_y = _gravity_offset(gravity, project_width, project_height, scaled_w, scaled_h)
                                    base_center_x = origin_x + (scaled_w / 2.0)
                                    base_center_y = origin_y + (scaled_h / 2.0)
                                    norm_x = (horiz_value - base_center_x) / project_width
                                    norm_y = (vert_value - base_center_y) / project_height
                                    interp_nodes = keyframe_element.getElementsByTagName("interpolation")
                                    interp_value = _node_text_content(interp_nodes[0]) if interp_nodes else None
                                    interp_point = _xml_interp_to_point(interp_value)
                                    handles = {}
                                    if interp_point == openshot.BEZIER:
                                        handles = {
                                            "handle_left": {"X": 0.5, "Y": 1.0},
                                            "handle_right": {"X": 0.5, "Y": 0.0},
                                            "handle_type": 0,
                                        }
                                    location_x_points.append(
                                            {
                                                "co": {
                                                    "X": round(keyframe_time),
                                                    "Y": norm_x
                                                },
                                                "interpolation": interp_point,
                                                **handles
                                            }
                                    )
                                    location_y_points.append(
                                        {
                                            "co": {
                                                "X": round(keyframe_time),
                                                "Y": norm_y
                                            },
                                            "interpolation": interp_point,
                                            **handles
                                        }
                                    )
                            elif parameterid in ("scale", "scale_x", "scale_y"):
                                keyframes = parameter_element.getElementsByTagName("keyframe")
                                for keyframe_element in keyframes:
                                    keyframe_time = _float_value(keyframe_element.getElementsByTagName("when"), 0.0)
                                    keyframe_value = _float_value(keyframe_element.getElementsByTagName("value"), 0.0) / 100.0
                                    interp_nodes = keyframe_element.getElementsByTagName("interpolation")
                                    interp_value = _node_text_content(interp_nodes[0]) if interp_nodes else None
                                    scale_points.append(
                                        {
                                            "co": {
                                                "X": round(keyframe_time),
                                                "Y": keyframe_value
                                            },
                                            "interpolation": _xml_interp_to_point(interp_value)
                                        }
                                    )
                            elif parameterid == "rotation":
                                keyframes = parameter_element.getElementsByTagName("keyframe")
                                for keyframe_element in keyframes:
                                    keyframe_time = _float_value(keyframe_element.getElementsByTagName("when"), 0.0)
                                    keyframe_value = _float_value(keyframe_element.getElementsByTagName("value"), 0.0)
                                    interp_nodes = keyframe_element.getElementsByTagName("interpolation")
                                    interp_value = _node_text_content(interp_nodes[0]) if interp_nodes else None
                                    rotation_points.append(
                                        {
                                            "co": {
                                                "X": round(keyframe_time),
                                                "Y": keyframe_value
                                            },
                                            "interpolation": _xml_interp_to_point(interp_value)
                                        }
                                    )
                    elif effectid == "audiolevels":
                        for keyframe_element in keyframes:
                            keyframe_time = _float_value(keyframe_element.getElementsByTagName("when"), 0.0)
                            keyframe_value = _float_value(keyframe_element.getElementsByTagName("value"), 0.0)
                            if keyframe_value > 5.0:
                                keyframe_value = keyframe_value / 100.0
                            keyframe_value = max(0.0, min(1.0, keyframe_value))
                            interp_nodes = keyframe_element.getElementsByTagName("interpolation")
                            interp_value = _node_text_content(interp_nodes[0]) if interp_nodes else None
                            volume_points.append(
                                {
                                    "co": {
                                        "X": round(keyframe_time),
                                        "Y": keyframe_value
                                    },
                                    "interpolation": _xml_interp_to_point(interp_value)
                                }
                            )

                merge_key = _clip_merge_key(clip_path, clip_start_value, clip_end_value, clip_position_value)

                if is_audio_track_list and merge_key in imported_clip_map:
                    existing_clip = imported_clip_map[merge_key]
                    if volume_points:
                        existing_clip.data["volume"] = {"Points": volume_points}
                    existing_clip.save()
                    continue

                ensure_track()

                if alpha_points:
                    clip.data["alpha"] = {"Points": alpha_points}
                if location_x_points:
                    clip.data["location_x"] = {"Points": location_x_points}
                if location_y_points:
                    clip.data["location_y"] = {"Points": location_y_points}
                if scale_points:
                    clip.data["scale_x"] = {"Points": scale_points}
                    clip.data["scale_y"] = {
                        "Points": [
                            {
                                "co": dict(point.get("co", {})),
                                "interpolation": point.get("interpolation")
                            }
                            for point in scale_points
                        ]
                    }
                if rotation_points:
                    clip.data["rotation"] = {"Points": rotation_points}
                if volume_points:
                    clip.data["volume"] = {"Points": volume_points}
                # Save clip
                clip.save()

                if not is_audio_track_list and merge_key:
                    imported_clip_map[merge_key] = clip

            # Update the preview and reselect current frame in properties
            app.window.refreshFrameSignal.emit()
            app.window.propertyTableView.select_frame(app.window.preview_thread.player.Position())

    # Free up DOM memory
    xmldoc.unlink()
