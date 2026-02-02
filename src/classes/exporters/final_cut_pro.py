"""
 @file
 @brief This file is used to generate a Final Cut Pro export
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

import os
import pathlib
import shutil
import subprocess
from operator import itemgetter
from uuid import uuid1
from xml.dom import minidom

import openshot
from PyQt5.QtWidgets import QFileDialog

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.path_utils import absolute_media_path, relative_export_path, normalize_path
from classes.query import Clip, Track, File

INTERPOLATION_EXPORT_MAP = {
    openshot.LINEAR: "linear",
    openshot.BEZIER: "bezier",
    openshot.CONSTANT: "constant"
}


def _set_text(node, value):
    """Safely set the text content of a DOM node."""
    if not node:
        return
    if node.firstChild:
        node.firstChild.nodeValue = str(value)
    else:
        node.appendChild(node.ownerDocument.createTextNode(str(value)))


def _is_ntsc_rate(fps_num, fps_den):
    return fps_den == 1001 and fps_num in (24000, 30000, 60000)


def _seconds_to_frames(value, fps_num, fps_den):
    if value is None:
        value = 0.0
    return int(round(float(value) * fps_num / fps_den))


def _format_timebase(fps_num, fps_den):
    fps_value = float(fps_num) / float(fps_den)
    text = ("{0:.3f}".format(fps_value)).rstrip('0').rstrip('.')
    return text or "0"


def _format_ratio(num, den):
    """Format a numeric ratio as a compact string."""
    try:
        num = float(num)
        den = float(den)
        if den == 0:
            raise ZeroDivisionError()
        value = num / den
        text = ("{0:.10f}".format(value)).rstrip('0').rstrip('.')
        return text or "1"
    except Exception:
        return "1"


def _displayformat(ntsc_value):
    """Choose drop-frame vs non-drop timecode string."""
    ntsc_upper = (ntsc_value or "").upper()
    return "DF" if ntsc_upper == "TRUE" else "NDF"


def _timecode_string(ntsc_value):
    """Return a default timecode string respecting drop/non-drop separators."""
    separator = ";" if (ntsc_value or "").upper() == "TRUE" else ":"
    return f"00{separator}00{separator}00{separator}00"


def _file_url(path_string):
    """Return a file:// URL for an absolute path if possible."""
    if not path_string:
        return ""
    try:
        return pathlib.Path(path_string).absolute().as_uri()
    except Exception:
        return normalize_path(path_string)


def _unique_file_id(path_string, existing_id, id_map):
    """Ensure a unique file id per absolute path."""
    normalized = os.path.abspath(path_string or "")
    if normalized in id_map:
        return id_map[normalized]
    candidate = existing_id or "file-%s" % uuid1()
    if candidate in id_map.values():
        candidate = "file-%s" % uuid1()
    id_map[normalized] = candidate
    return candidate


def _clip_file_info(clip):
    """Return (File object, merged metadata dict, absolute file path)."""
    file_obj = None
    file_data = {}
    file_id = clip.data.get("file_id")
    if file_id:
        file_obj = File.get(id=file_id)
        if file_obj and file_obj.data:
            file_data = dict(file_obj.data)

    reader_data = clip.data.get("reader", {}) or {}
    merged_data = dict(reader_data)
    merged_data.update(file_data)

    file_path = ""
    if file_obj:
        file_path = file_obj.absolute_path()
    if not file_path:
        file_path = absolute_media_path(reader_data.get("path"))
    if not file_path:
        file_path = reader_data.get("path", "")

    return file_obj, merged_data, file_path


def _apply_rate_settings(rate_nodes, timebase_value, ntsc_value):
    for rate_node in rate_nodes:
        timebase_nodes = rate_node.getElementsByTagName("timebase")
        if timebase_nodes:
            _set_text(timebase_nodes[0], timebase_value)
        ntsc_nodes = rate_node.getElementsByTagName("ntsc")
        if ntsc_nodes:
            _set_text(ntsc_nodes[0], ntsc_value)


def _apply_timecode_settings(timecode_nodes, timebase_value, ntsc_value):
    for timecode_node in timecode_nodes:
        _apply_rate_settings(timecode_node.getElementsByTagName("rate"), timebase_value, ntsc_value)
        displayformat_nodes = timecode_node.getElementsByTagName("displayformat")
        if displayformat_nodes:
            _set_text(displayformat_nodes[0], _displayformat(ntsc_value))
        string_nodes = timecode_node.getElementsByTagName("string")
        if string_nodes:
            _set_text(string_nodes[0], _timecode_string(ntsc_value))


def _validate_export(xml_path):
    """Validate the exported XML against the bundled Final Cut Pro DTDs."""
    xmllint_path = shutil.which("xmllint")
    if not xmllint_path:
        log.info("Skipping FCP XML validation; xmllint not available")
        return

    for dtd_file in ("fcp-xml-v4.dtd", "fcp-xml-v5.dtd"):
        dtd_path = os.path.join(info.RESOURCES_PATH, dtd_file)
        if not os.path.exists(dtd_path):
            continue

        result = subprocess.run(
            [xmllint_path, "--noout", "--dtdvalid", dtd_path, xml_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log.info("Validated Final Cut Pro XML against %s", dtd_file)
        else:
            error_text = (result.stderr or result.stdout or "").strip()
            log.warning("Final Cut Pro XML did not validate against %s: %s", dtd_file, error_text)


def _append_link(link_parent, mediatype_value, track_index, clip_index, group_index, ref_id):
    """Append a <link> node for A/V grouping compatibility."""
    if not link_parent:
        return
    link_node = link_parent.ownerDocument.createElement("link")
    link_parent.appendChild(link_node)
    for tag, value in (
        ("linkclipref", ref_id),
        ("mediatype", mediatype_value),
        ("trackindex", track_index),
        ("clipindex", clip_index),
        ("groupindex", group_index),
    ):
        child = link_parent.ownerDocument.createElement(tag)
        child.appendChild(link_parent.ownerDocument.createTextNode(str(value)))
        link_node.appendChild(child)


def _normalized_to_center_pixels(x_norm, y_norm, frame_width, frame_height):
    """Map normalized OpenShot coords (-1..1, origin center) to pixel center values."""
    try:
        w = float(frame_width)
        h = float(frame_height)
    except (TypeError, ValueError):
        return x_norm, y_norm
    if w <= 0 or h <= 0:
        return x_norm, y_norm
    return (w / 2.0) + (x_norm * w / 2.0), (h / 2.0) + (y_norm * h / 2.0)


def _export_interp_name(value):
    """Return an interpolation name for export from int/str values."""
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ("linear", "0"):
            return "linear"
        if val in ("bezier", "ease", "easein", "easeout", "1"):
            return "bezier"
        if val in ("hold", "constant", "2"):
            return "constant"
    try:
        return INTERPOLATION_EXPORT_MAP.get(int(value), "linear")
    except Exception:
        return "linear"


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
    # SCALE_NONE or unknown
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


def _merge_uniform_scale(scale_x_points, scale_y_points):
    """Combine X/Y scale into a single uniform curve (average when both exist)."""
    merged = {}

    def _add(points):
        for point in points:
            t = point.get("co", {}).get("X", 1)
            v = point.get("co", {}).get("Y", 1.0)
            interp = point.get("interpolation", openshot.LINEAR)
            if t in merged:
                merged[t]["val"] = (merged[t]["val"] + v) / 2.0
                if merged[t].get("interp") is None:
                    merged[t]["interp"] = interp
            else:
                merged[t] = {"val": v, "interp": interp}

    _add(scale_x_points or [])
    _add(scale_y_points or [])

    merged_points = []
    for t in sorted(merged.keys()):
        merged_points.append(
            {
                "co": {"X": t, "Y": merged[t]["val"]},
                "interpolation": merged[t].get("interp", openshot.LINEAR),
            }
        )
    return merged_points


def _find_effect_node(node, effect_name):
    """Find the first effect node with a matching name."""
    for effectNode in node.getElementsByTagName("effect"):
        effectName = effectNode.getElementsByTagName("name")[0].childNodes[0].nodeValue
        if effectName == effect_name:
            return effectNode
    return None


def _find_parameter_node(effect_node, parameter_id):
    """Find the first parameter node with a matching id."""
    for param in effect_node.getElementsByTagName("parameter"):
        paramIdNode = param.getElementsByTagName("parameterid")
        if paramIdNode and paramIdNode[0].childNodes and paramIdNode[0].childNodes[0].nodeValue == parameter_id:
            return param
    return None


def createEffect(xmldoc, name, node, points, scale, max_frames=None, param_name=None):
    """Create the XML filter with keyframes"""
    effectNode = _find_effect_node(node, name)
    if not effectNode:
        return
    if param_name:
        parameterNode = _find_parameter_node(effectNode, param_name)
    else:
        parameterNode = effectNode.getElementsByTagName("parameter")[0]

    if not parameterNode:
        return

    # Loop through Points (remove duplicates)
    keyframes = {}
    for point in points:
        keyframeTime = point.get('co', {}).get('X', 1)
        keyframeValue = point.get('co', {}).get('Y', 1) * scale
        interpolation = point.get('interpolation', openshot.LINEAR)
        if max_frames is not None:
            keyframeTime = max(0, min(keyframeTime, max_frames))
        keyframes[keyframeTime] = (keyframeValue, interpolation)

    # Loop through Points
    for keyframeTime in sorted(keyframes.keys()):
        keyframeValue, interpolation = keyframes.get(keyframeTime)

        # Create keyframe element for each point
        keyframeNode = xmldoc.createElement("keyframe")
        parameterNode.appendChild(keyframeNode)
        whenNode = xmldoc.createElement("when")
        whenNode.appendChild(xmldoc.createTextNode(str(int(round(keyframeTime)))))
        keyframeNode.appendChild(whenNode)
        valueNode = xmldoc.createElement("value")
        valueNode.appendChild(xmldoc.createTextNode(str(keyframeValue)))
        keyframeNode.appendChild(valueNode)
        interpNode = xmldoc.createElement("interpolation")
        interpName = xmldoc.createElement("name")
        interpName.appendChild(xmldoc.createTextNode(_export_interp_name(interpolation)))
        interpNode.appendChild(interpName)
        keyframeNode.appendChild(interpNode)


def createCenterEffect(
    xmldoc,
    node,
    x_points,
    y_points,
    frame_width,
    frame_height,
    src_width,
    src_height,
    scale_mode,
    gravity,
    scale_x_points,
    scale_y_points,
    max_frames=None,
):
    """Create the Basic Motion center keyframes using project/frame units."""
    effectNode = _find_effect_node(node, "Basic Motion")
    if not effectNode:
        return

    parameterNode = _find_parameter_node(effectNode, "center")
    if not parameterNode:
        return

    keyframes = {}

    def _add_points(points, axis_key):
        for point in points:
            keyframeTime = point.get("co", {}).get("X", 1)
            interpolation = point.get("interpolation", openshot.LINEAR)
            if max_frames is not None:
                keyframeTime = max(0, min(keyframeTime, max_frames))
            entry = keyframes.setdefault(keyframeTime, {})
            entry[axis_key] = point.get("co", {}).get("Y", 0.0)
            entry["interp_%s" % axis_key] = interpolation

    _add_points(x_points, "x")
    _add_points(y_points, "y")

    def _value_at_time(points, t, fallback=1.0):
        if not points:
            return fallback
        sorted_points = sorted(points, key=lambda p: p.get("co", {}).get("X", 0))
        last_val = sorted_points[0].get("co", {}).get("Y", fallback)
        for p in sorted_points:
            pt_time = p.get("co", {}).get("X", 0)
            if max_frames is not None:
                pt_time = max(0, min(pt_time, max_frames))
            if pt_time <= t:
                last_val = p.get("co", {}).get("Y", fallback)
            else:
                break
        return last_val

    last_x = 0.0
    last_y = 0.0

    for keyframeTime in sorted(keyframes.keys()):
        entry = keyframes[keyframeTime]
        x_val = entry.get("x", last_x)
        y_val = entry.get("y", last_y)
        last_x = x_val
        last_y = y_val
        if "interp_x" in entry:
            interpolation = entry.get("interp_x")
        elif "interp_y" in entry:
            interpolation = entry.get("interp_y")
        else:
            interpolation = openshot.LINEAR

        base_w, base_h = _scale_mode_size(src_width, src_height, frame_width, frame_height, scale_mode)
        sx = _value_at_time(scale_x_points, keyframeTime, 1.0)
        sy = _value_at_time(scale_y_points, keyframeTime, 1.0)
        scaled_w = base_w * sx
        scaled_h = base_h * sy
        origin_x, origin_y = _gravity_offset(gravity, frame_width, frame_height, scaled_w, scaled_h)
        center_x, center_y = origin_x + (scaled_w / 2.0), origin_y + (scaled_h / 2.0)
        center_x += frame_width * x_val
        center_y += frame_height * y_val

        keyframeNode = xmldoc.createElement("keyframe")
        parameterNode.appendChild(keyframeNode)
        whenNode = xmldoc.createElement("when")
        whenNode.appendChild(xmldoc.createTextNode(str(int(round(keyframeTime)))))
        keyframeNode.appendChild(whenNode)

        valueNode = xmldoc.createElement("value")
        horizNode = xmldoc.createElement("horiz")
        horizNode.appendChild(xmldoc.createTextNode(str(center_x)))
        valueNode.appendChild(horizNode)
        vertNode = xmldoc.createElement("vert")
        vertNode.appendChild(xmldoc.createTextNode(str(center_y)))
        valueNode.appendChild(vertNode)
        keyframeNode.appendChild(valueNode)

        interpNode = xmldoc.createElement("interpolation")
        interpName = xmldoc.createElement("name")
        interpName.appendChild(xmldoc.createTextNode(_export_interp_name(interpolation)))
        interpNode.appendChild(interpName)
        keyframeNode.appendChild(interpNode)


def export_xml():
    """Export final cut pro XML file"""
    app = get_app()
    _ = app._tr

    # Get FPS info
    fps_num = get_app().project.get("fps").get("num", 24)
    fps_den = get_app().project.get("fps").get("den", 1)
    timebase_value = _format_timebase(fps_num, fps_den)
    ntsc_value = "TRUE" if _is_ntsc_rate(fps_num, fps_den) else "FALSE"
    project_data = getattr(app.project, "_data", {}) or {}
    project_interlaced = False
    try:
        project_interlaced = bool(project_data.get("interlaced_frame"))
    except Exception:
        project_interlaced = False
    project_pixel_ratio = project_data.get("pixel_ratio") or {}
    project_pixel_ratio_value = _format_ratio(project_pixel_ratio.get("num", 1), project_pixel_ratio.get("den", 1))
    try:
        project_pixel_ratio_float = float(project_pixel_ratio.get("num", 1)) / float(project_pixel_ratio.get("den", 1))
    except Exception:
        project_pixel_ratio_float = 1.0
    project_anamorphic_value = "TRUE" if abs(project_pixel_ratio_float - 1.0) > 0.0005 else "FALSE"
    project_field_dominance = "lower" if project_interlaced else "none"

    # Get path
    recommended_path = get_app().project.current_filepath or ""
    if not recommended_path:
        recommended_path = os.path.join(info.HOME_PATH, "%s.xml" % _("Untitled Project"))
    else:
        for ext in (info.PROJECT_EXT, info.LEGACY_PROJECT_EXT):
            recommended_path = recommended_path.replace(ext, ".xml")
    file_path = QFileDialog.getSaveFileName(app.window, _("Export XML..."), recommended_path,
                                            _("Final Cut Pro (*.xml)"))[0]
    if not file_path:
        # User canceled dialog
        return

    # Append .xml if needed
    if not file_path.endswith(".xml"):
        file_path = "%s.xml" % file_path

    export_folder = os.path.dirname(os.path.abspath(file_path))

    # Get filename with no path
    file_name = os.path.basename(file_path)

    # Determine max frame (based on clips)
    duration = 0.0
    all_clips = Clip.filter()
    for clip in all_clips:
        clip_last_frame = (clip.data.get("position") or 0.0) + ((clip.data.get("end") or 0.0) - (clip.data.get("start") or 0.0))
        if clip_last_frame > duration:
            # Set max length of timeline
            duration = clip_last_frame
    duration_frames = _seconds_to_frames(duration, fps_num, fps_den)

    # XML template path
    xmldoc = minidom.parse(os.path.join(info.RESOURCES_PATH, 'export-project-template.xml'))

    # Set Project Details
    _set_text(xmldoc.getElementsByTagName("name")[0], file_name)
    _set_text(xmldoc.getElementsByTagName("uuid")[0], str(uuid1()))
    _set_text(xmldoc.getElementsByTagName("duration")[0], duration_frames)
    _set_text(xmldoc.getElementsByTagName("width")[0], app.project.get("width"))
    _set_text(xmldoc.getElementsByTagName("height")[0], app.project.get("height"))
    for par_node in xmldoc.getElementsByTagName("pixelaspectratio"):
        _set_text(par_node, project_pixel_ratio_value)
    for anamorphic_node in xmldoc.getElementsByTagName("anamorphic"):
        _set_text(anamorphic_node, project_anamorphic_value)
    _set_text(xmldoc.getElementsByTagName("samplerate")[0], app.project.get("sample_rate"))
    for field_node in xmldoc.getElementsByTagName("fielddominance"):
        _set_text(field_node, project_field_dominance)
    _apply_timecode_settings(xmldoc.getElementsByTagName("timecode"), timebase_value, ntsc_value)
    sequence_node = xmldoc.getElementsByTagName("sequence")[0]
    if app.project.get("id"):
        sequence_node.setAttribute("id", app.project.get("id"))
    for childNode in xmldoc.getElementsByTagName("timebase"):
        _set_text(childNode, timebase_value)
    for ntsc_node in xmldoc.getElementsByTagName("ntsc"):
        _set_text(ntsc_node, ntsc_value)

    # Get parent nodes
    parentAudioNode = xmldoc.getElementsByTagName("audio")[0]
    parentVideoNode = xmldoc.getElementsByTagName("video")[0]
    num_output_channels = parentAudioNode.getElementsByTagName("channelcount")
    if num_output_channels:
        project_channels = app.project.get("channels")
        if project_channels is None:
            project_channels = 2
        _set_text(num_output_channels[0], project_channels)

    # Loop through tracks
    all_tracks = get_app().project.get("layers")
    video_track_index = 1
    audio_track_index = 1
    clip_link_info = {}
    file_id_map = {}
    for track in sorted(all_tracks, key=itemgetter('number')):
        existing_track = Track.get(number=track.get("number"))
        if not existing_track:
            # Log error and fail silently, and continue
            log.error('No track object found with number: %s' % track.get("number"))
            continue

        # Track details
        track_locked = track.get("lock", False)
        clips_on_track = sorted(Clip.filter(layer=track.get("number")), key=lambda c: c.data.get('position', 0.0))
        if not clips_on_track:
            continue

        has_video = any(c.data.get("reader", {}).get("has_video") for c in clips_on_track)
        has_audio = any(c.data.get("reader", {}).get("has_audio") for c in clips_on_track)

        videoTrackNode = None
        audioTrackNode = None
        audioTrackNumber = None
        videoTrackNumber = None

        if has_video:
            trackTemplateDoc = minidom.parse(os.path.join(info.RESOURCES_PATH, 'export-track-video-template.xml'))
            videoTrackNode = trackTemplateDoc.getElementsByTagName('track')[0]
            parentVideoNode.appendChild(videoTrackNode)
            videoTrackNumber = video_track_index
            video_track_index += 1
            if track_locked:
                _set_text(videoTrackNode.getElementsByTagName("locked")[0], "TRUE")

        if has_audio:
            trackTemplateDoc = minidom.parse(os.path.join(info.RESOURCES_PATH, 'export-track-audio-template.xml'))
            audioTrackNode = trackTemplateDoc.getElementsByTagName('track')[0]
            parentAudioNode.appendChild(audioTrackNode)
            audioTrackNumber = audio_track_index
            audio_track_index += 1
            output_nodes = audioTrackNode.getElementsByTagName("outputchannelindex")
            if output_nodes:
                _set_text(output_nodes[0], audioTrackNumber)
            if track_locked:
                _set_text(audioTrackNode.getElementsByTagName("locked")[0], "TRUE")

        video_clip_index = 1
        audio_clip_index = 1

        # Loop through clips on this track
        for clip in clips_on_track:
            clip_reader = clip.data.get("reader", {}) or {}
            clip_duration_frames = _seconds_to_frames((clip.data.get('end') or 0.0) - (clip.data.get('start') or 0.0), fps_num, fps_den)
            if clip_duration_frames <= 0:
                continue

            clip_in_frames = _seconds_to_frames(clip.data.get('start') or 0.0, fps_num, fps_den)
            clip_out_frames = clip_in_frames + clip_duration_frames
            timeline_in_frames = _seconds_to_frames(clip.data.get('position') or 0.0, fps_num, fps_den)
            timeline_out_frames = timeline_in_frames + clip_duration_frames

            file_obj, merged_data, abs_media_path = _clip_file_info(clip)
            display_name = merged_data.get("name") or os.path.basename(merged_data.get("path", "") or clip.data.get('title') or "")
            clip_title = clip.data.get('title') or display_name or os.path.basename(abs_media_path or "") or "Clip"
            sample_rate = merged_data.get("sample_rate") or merged_data.get("audio_sample_rate") or app.project.get("sample_rate") or 48000
            channel_count = merged_data.get("channels") or merged_data.get("channel_count") or 2
            merged_pixel_ratio = merged_data.get("pixel_ratio") or project_pixel_ratio
            clip_pixel_ratio_value = _format_ratio(merged_pixel_ratio.get("num", 1), merged_pixel_ratio.get("den", 1))
            try:
                clip_pixel_ratio_float = float(merged_pixel_ratio.get("num", 1)) / float(merged_pixel_ratio.get("den", 1))
            except Exception:
                clip_pixel_ratio_float = 1.0
            clip_anamorphic_value = "TRUE" if abs(clip_pixel_ratio_float - 1.0) > 0.0005 else "FALSE"
            clip_field_dominance = project_field_dominance
            if merged_data.get("interlaced_frame"):
                clip_field_dominance = "lower"
            try:
                sample_rate = int(sample_rate)
            except (TypeError, ValueError):
                sample_rate = 48000
            try:
                channel_count = int(channel_count)
            except (TypeError, ValueError):
                channel_count = 2
            relative_media_path = relative_export_path(abs_media_path, export_folder)
            file_id_value = _unique_file_id(abs_media_path or merged_data.get("path"), clip.data.get('file_id'), file_id_map)

            # Use the single authoritative duration from the File object (if available)
            file_duration_frames = None
            if file_obj and isinstance(file_obj.data.get("duration"), (int, float)):
                file_duration_frames = _seconds_to_frames(file_obj.data.get("duration"), fps_num, fps_den)

            if file_duration_frames is not None:
                clip_in_frames = min(clip_in_frames, file_duration_frames)
                max_available = max(0, file_duration_frames - clip_in_frames)
                clip_duration_frames = min(clip_duration_frames, max_available)
                clip_out_frames = clip_in_frames + clip_duration_frames
                timeline_out_frames = timeline_in_frames + clip_duration_frames
            if clip_duration_frames <= 0:
                continue

            if clip_reader.get("has_video") and videoTrackNode:
                clipTemplateDoc = minidom.parse(os.path.join(info.RESOURCES_PATH, 'export-clip-video-template.xml'))
                clipNode = clipTemplateDoc.getElementsByTagName('clipitem')[0]
                videoTrackNode.appendChild(clipNode)

                clipNode.setAttribute('id', clip.data.get('id'))
                clip_file_node = clipNode.getElementsByTagName("file")[0]
                clip_file_node.setAttribute('id', file_id_value)
                clip_names = clipNode.getElementsByTagName("name")
                if clip_names:
                    _set_text(clip_names[0], clip_title)
                if len(clip_names) > 1:
                    _set_text(clip_names[1], clip_title)
                _set_text(clipNode.getElementsByTagName("start")[0], timeline_in_frames)
                _set_text(clipNode.getElementsByTagName("end")[0], timeline_out_frames)
                _set_text(clipNode.getElementsByTagName("in")[0], clip_in_frames)
                _set_text(clipNode.getElementsByTagName("out")[0], clip_out_frames)
                _set_text(clipNode.getElementsByTagName("duration")[0], clip_duration_frames)
                for par_node in clipNode.getElementsByTagName("pixelaspectratio"):
                    _set_text(par_node, clip_pixel_ratio_value)
                for anamorphic_node in clipNode.getElementsByTagName("anamorphic"):
                    _set_text(anamorphic_node, clip_anamorphic_value)
                _apply_rate_settings(clipNode.getElementsByTagName("rate"), timebase_value, ntsc_value)

                file_path_nodes = clip_file_node.getElementsByTagName("pathurl")
                if file_path_nodes:
                    preferred_path = abs_media_path or relative_media_path or clip_title
                    _set_text(file_path_nodes[0], _file_url(preferred_path))
                file_name_nodes = clip_file_node.getElementsByTagName("name")
                if file_name_nodes:
                    _set_text(file_name_nodes[0], display_name)
                file_duration_nodes = clip_file_node.getElementsByTagName("duration")
                if file_duration_nodes:
                    if file_duration_frames is not None:
                        _set_text(file_duration_nodes[0], file_duration_frames)
                    else:
                        _set_text(file_duration_nodes[0], clip_duration_frames)
                width_nodes = clip_file_node.getElementsByTagName("width")
                if width_nodes:
                    _set_text(width_nodes[0], merged_data.get("width") or app.project.get("width"))
                height_nodes = clip_file_node.getElementsByTagName("height")
                if height_nodes:
                    _set_text(height_nodes[0], merged_data.get("height") or app.project.get("height"))
                field_dom_nodes = clip_file_node.getElementsByTagName("fielddominance")
                for field_node in field_dom_nodes:
                    _set_text(field_node, clip_field_dominance)
                for par_node in clip_file_node.getElementsByTagName("pixelaspectratio"):
                    _set_text(par_node, clip_pixel_ratio_value)
                for anamorphic_node in clip_file_node.getElementsByTagName("anamorphic"):
                    _set_text(anamorphic_node, clip_anamorphic_value)
                _apply_timecode_settings(clip_file_node.getElementsByTagName("timecode"), timebase_value, ntsc_value)
                samplerate_nodes = clip_file_node.getElementsByTagName("samplerate")
                if samplerate_nodes:
                    _set_text(samplerate_nodes[0], sample_rate)
                channel_nodes = clip_file_node.getElementsByTagName("channelcount")
                if channel_nodes:
                    _set_text(channel_nodes[0], channel_count)
                media_nodes = clip_file_node.getElementsByTagName("media")
                if media_nodes:
                    video_nodes = media_nodes[0].getElementsByTagName("video")
                    audio_nodes = media_nodes[0].getElementsByTagName("audio")
                    if not clip_reader.get("has_audio"):
                        for n in list(audio_nodes):
                            media_nodes[0].removeChild(n)
                    if not clip_reader.get("has_video"):
                        for n in list(video_nodes):
                            media_nodes[0].removeChild(n)

                if clip_reader.get("has_video"):
                    frame_width = app.project.get("width") or merged_data.get("width")
                    frame_height = app.project.get("height") or merged_data.get("height")
                    src_width = merged_data.get("width") or frame_width
                    src_height = merged_data.get("height") or frame_height
                    scale_mode = clip.data.get("scale", openshot.SCALE_FIT)
                    gravity = clip.data.get("gravity", openshot.GRAVITY_CENTER)
                    createEffect(
                        xmldoc,
                        "Opacity",
                        clipNode,
                        clip.data.get("alpha", {}).get("Points", []),
                        100.0,
                        clip_duration_frames,
                        "opacity",
                    )
                    createCenterEffect(
                        xmldoc,
                        clipNode,
                        clip.data.get("location_x", {}).get("Points", []),
                        clip.data.get("location_y", {}).get("Points", []),
                        frame_width,
                        frame_height,
                        src_width,
                        src_height,
                        scale_mode,
                        gravity,
                        clip.data.get("scale_x", {}).get("Points", []),
                        clip.data.get("scale_y", {}).get("Points", []),
                        clip_duration_frames,
                    )
                    scale_points = _merge_uniform_scale(
                        clip.data.get("scale_x", {}).get("Points", []),
                        clip.data.get("scale_y", {}).get("Points", []),
                    )
                    createEffect(
                        xmldoc,
                        "Basic Motion",
                        clipNode,
                        scale_points,
                        100.0,
                        clip_duration_frames,
                        "scale",
                    )
                    createEffect(
                        xmldoc,
                        "Basic Motion",
                        clipNode,
                        clip.data.get("rotation", {}).get("Points", []),
                        1.0,
                        clip_duration_frames,
                        "rotation",
                    )
                logging_nodes = clipNode.getElementsByTagName("good")
                if logging_nodes:
                    _set_text(logging_nodes[0], "FALSE")
                base_id = clip.data.get('id')
                if base_id:
                    clip_link_info.setdefault(base_id, {})
                    clip_link_info[base_id]["video"] = {
                        "node": clipNode,
                        "trackindex": videoTrackNumber or 1,
                        "clipindex": video_clip_index,
                        "id": clip.data.get('id')
                    }
                    video_clip_index += 1
                    link_parts = clip_link_info[base_id]
                    if "audio" in link_parts:
                        audio_info = link_parts["audio"]
                        _append_link(clipNode, "video", videoTrackNumber or 1, link_parts["video"]["clipindex"], 1, clip.data.get('id'))
                        _append_link(clipNode, "audio", audio_info["trackindex"], audio_info["clipindex"], 1, audio_info["id"])
                        _append_link(audio_info["node"], "audio", audio_info["trackindex"], audio_info["clipindex"], 1, audio_info["id"])
                        _append_link(audio_info["node"], "video", videoTrackNumber or 1, link_parts["video"]["clipindex"], 1, clip.data.get('id'))

            if clip_reader.get("has_audio") and audioTrackNode:
                clipTemplateDoc = minidom.parse(os.path.join(info.RESOURCES_PATH, 'export-clip-audio-template.xml'))
                clipAudioNode = clipTemplateDoc.getElementsByTagName('clipitem')[0]
                audioTrackNode.appendChild(clipAudioNode)

                clipAudioNode.setAttribute('id', "%s-audio" % clip.data.get('id'))

                audio_file_node = clipAudioNode.getElementsByTagName("file")[0]
                audio_file_node.setAttribute('id', file_id_value)
                audio_name_nodes = clipAudioNode.getElementsByTagName("name")
                if audio_name_nodes:
                    _set_text(audio_name_nodes[0], clip_title)
                if len(audio_name_nodes) > 1:
                    _set_text(audio_name_nodes[1], clip_title)
                _set_text(clipAudioNode.getElementsByTagName("start")[0], timeline_in_frames)
                _set_text(clipAudioNode.getElementsByTagName("end")[0], timeline_out_frames)
                _set_text(clipAudioNode.getElementsByTagName("in")[0], clip_in_frames)
                _set_text(clipAudioNode.getElementsByTagName("out")[0], clip_out_frames)
                _set_text(clipAudioNode.getElementsByTagName("duration")[0], clip_duration_frames)
                _apply_rate_settings(clipAudioNode.getElementsByTagName("rate"), timebase_value, ntsc_value)

                audio_path_nodes = audio_file_node.getElementsByTagName("pathurl")
                if audio_path_nodes:
                    preferred_audio_path = abs_media_path or relative_media_path or clip_title
                    _set_text(audio_path_nodes[0], _file_url(preferred_audio_path))
                audio_file_names = audio_file_node.getElementsByTagName("name")
                if audio_file_names:
                    _set_text(audio_file_names[0], display_name)
                audio_file_duration_nodes = audio_file_node.getElementsByTagName("duration")
                if audio_file_duration_nodes:
                    _set_text(
                        audio_file_duration_nodes[0],
                        file_duration_frames if file_duration_frames is not None else clip_duration_frames
                    )
                samplerate_nodes = audio_file_node.getElementsByTagName("samplerate")
                if samplerate_nodes:
                    _set_text(samplerate_nodes[0], sample_rate)
                channel_nodes = audio_file_node.getElementsByTagName("channelcount")
                if channel_nodes:
                    _set_text(channel_nodes[0], channel_count)
                _apply_timecode_settings(audio_file_node.getElementsByTagName("timecode"), timebase_value, ntsc_value)

                sourcetrack_nodes = clipAudioNode.getElementsByTagName("sourcetrack")
                if sourcetrack_nodes and audioTrackNumber is not None:
                    track_index_nodes = sourcetrack_nodes[0].getElementsByTagName("trackindex")
                    if track_index_nodes:
                        _set_text(track_index_nodes[0], audioTrackNumber)

                track_index_nodes = clipAudioNode.getElementsByTagName("trackindex")
                if track_index_nodes and audioTrackNumber is not None:
                    _set_text(track_index_nodes[0], audioTrackNumber)

                createEffect(xmldoc, "Audio Levels", clipAudioNode, clip.data.get('volume', {}).get('Points', []), 1.0, clip_duration_frames)
                logging_nodes = clipAudioNode.getElementsByTagName("good")
                if logging_nodes:
                    _set_text(logging_nodes[0], "FALSE")
                base_id = clip.data.get('id')
                if base_id:
                    clip_link_info.setdefault(base_id, {})
                    audio_id = "%s-audio" % base_id
                    clip_link_info[base_id]["audio"] = {
                        "node": clipAudioNode,
                        "trackindex": audioTrackNumber or 1,
                        "clipindex": audio_clip_index,
                        "id": audio_id
                    }
                    audio_clip_index += 1
                    link_parts = clip_link_info[base_id]
                    if "video" in link_parts:
                        video_info = link_parts["video"]
                        _append_link(clipAudioNode, "audio", audioTrackNumber or 1, link_parts["audio"]["clipindex"], 1, audio_id)
                        _append_link(clipAudioNode, "video", video_info["trackindex"], video_info["clipindex"], 1, video_info["id"])
                        _append_link(video_info["node"], "video", video_info["trackindex"], video_info["clipindex"], 1, video_info["id"])
                        _append_link(video_info["node"], "audio", audioTrackNumber or 1, link_parts["audio"]["clipindex"], 1, audio_id)

    try:
        with open(os.fsencode(file_path), "wb") as file:
            file.write(bytes(xmldoc.toxml(), 'UTF-8'))
        _validate_export(file_path)
    except IOError as inst:
        log.error("Error writing XML export: {}".format(str(inst)))
    finally:
        # Free up DOM memory
        xmldoc.unlink()
