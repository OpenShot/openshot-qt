"""
 @file
 @brief Painter for timeline clips.
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

from qt_api import QPointF, QRectF, Qt, QTimer
from qt_api import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from qt_api import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene
import copy
import json
import copy
import json
import math
import os
import time

import openshot

from classes.app import get_app
from classes.keyframe_scaler import KeyframeScaler
from classes.logger import log
from classes.thumbnail import RoundFrameToThumbnailGrid
from classes.time_parts import secondsToTime
from classes import info
from classes.clip_utils import is_single_image_media
from classes.qt_types import font_metrics_horizontal_advance

from .base import BasePainter


def _frame_for_seconds(seconds, fps):
    fps = float(fps or 0.0)
    if fps <= 0.0:
        fps = 24.0
    seconds = max(0.0, float(seconds or 0.0))
    frame_float = seconds * fps
    frame = int(math.floor(frame_float + 0.5)) + 1
    return max(1, frame)


def _clip_media_frame_count(clip, clip_fps):
    data = clip.data if isinstance(getattr(clip, "data", None), dict) else {}
    reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}

    try:
        video_length = int(round(float(reader.get("video_length", 0) or 0)))
    except (TypeError, ValueError):
        video_length = 0
    if video_length > 0:
        return video_length

    try:
        duration = float(reader.get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration > 0.0 and clip_fps > 0.0:
        return max(1, int(math.floor(duration * clip_fps)))

    return 0


def _scaled_time_keyframe_points(clip, clip_fps, project_fps):
    """Return time keyframe points scaled into clip-fps space."""
    data = clip.data if isinstance(getattr(clip, "data", None), dict) else {}
    time_data = data.get("time") if isinstance(data.get("time"), dict) else {}
    points = time_data.get("Points") if isinstance(time_data.get("Points"), list) else []
    if len(points) < 2:
        return []

    clip_fps = float(clip_fps or 0.0)
    project_fps = float(project_fps or 0.0)
    if clip_fps <= 0.0:
        clip_fps = 24.0
    if project_fps <= 0.0:
        project_fps = clip_fps

    scaled_time = copy.deepcopy(time_data)
    if project_fps > 0.0 and abs(project_fps - clip_fps) > 1e-6:
        payload = {"clips": [{"time": scaled_time}]}
        KeyframeScaler(clip_fps / project_fps)(payload)
        scaled_time = payload["clips"][0]["time"]
    return scaled_time.get("Points", []) if isinstance(scaled_time, dict) else []


def _has_time_curve(clip, clip_fps, project_fps=None):
    """Return True when a clip has a multi-point time mapping curve."""
    return len(_scaled_time_keyframe_points(clip, clip_fps, project_fps)) >= 2


def resolve_source_frame(clip, clip_time_seconds, clip_fps, project_fps=None, fallback_frame=None):
    """Resolve a source-media frame for a clip-local timestamp.

    Clips without a multi-point time curve fall back to linear trim mapping.
    Clips with time keyframes scale that curve into clip-fps space, then
    query the scaled curve directly to find the source reader frame.
    """
    frame = int(fallback_frame or _frame_for_seconds(clip_time_seconds, clip_fps))
    points = _scaled_time_keyframe_points(clip, clip_fps, project_fps)
    if len(points) < 2:
        return max(1, frame)

    clip_fps = float(clip_fps or 0.0)
    if clip_fps <= 0.0:
        clip_fps = 24.0

    project_fps = float(project_fps or 0.0)
    if project_fps <= 0.0:
        project_fps = clip_fps

    keyframe = openshot.Keyframe()
    point_count = 0
    for point in sorted(points, key=lambda value: float(value.get("co", {}).get("X", 0.0))):
        co = point.get("co") if isinstance(point, dict) else {}
        if not isinstance(co, dict):
            continue
        x_val = co.get("X")
        y_val = co.get("Y")
        if x_val is None or y_val is None:
            continue
        try:
            interpolation = int(point.get("interpolation", openshot.LINEAR))
        except (TypeError, ValueError):
            interpolation = openshot.LINEAR
        keyframe.AddPoint(float(x_val), float(y_val), interpolation)
        point_count += 1

    if point_count < 2:
        return max(1, frame)

    try:
        mapped_frame = int(keyframe.GetLong(frame))
    except Exception:
        return max(1, frame)

    max_frame = _clip_media_frame_count(clip, clip_fps)
    if max_frame > 0:
        mapped_frame = min(mapped_frame, max_frame)

    return max(1, mapped_frame or frame)


class ClipPainter(BasePainter):
    def __init__(self, widget):
        super().__init__(widget)
        self._thumbnail_repaint_timer = QTimer(self.w)
        self._thumbnail_repaint_timer.setSingleShot(True)
        self._thumbnail_repaint_timer.setInterval(250)
        self._thumbnail_repaint_timer.timeout.connect(self._flush_thumbnail_repaint)
        self._thumb_repaint_pending = False
        self._last_thumb_request_time = {}
        self._slot_fallback_cache = {}
        self._trim_request_cooldown = 0.12
        self._retime_preview_cache = {}

    MAX_THUMB_SLOTS = 150

    def _clip_media_type(self, clip):
        try:
            data = clip.data if isinstance(getattr(clip, "data", None), dict) else {}
            reader = data.get("reader") or {}
            mt = str(reader.get("media_type") or data.get("media_type") or "").strip().lower()
            if mt == "video" and self._clip_is_audio_media(clip):
                return "audio"
            return mt
        except Exception:
            return ""

    def _clip_timeline_position(self, clip):
        """Return the clip's left-edge position on the timeline in seconds.

        This reads the clip's data["position"] (if present), or falls back
        to a clip.position attribute. It is expected to be in *seconds*.
        """
        data = clip.data if isinstance(clip.data, dict) else {}
        pos = data.get("position", None)

        if self.w.clip_has_pending_override(clip):
            overrides = self.w._pending_clip_overrides.get(clip.id, {})
            pending_pos = overrides.get("position")
            if pending_pos is not None:
                pos = pending_pos

        if pos is None and hasattr(clip, "position"):
            try:
                pos = getattr(clip, "position")
            except Exception:
                pos = None

        return self._to_float(pos, 0.0)

    def update_theme(self):
        bw = float(self.w.theme.clip.border_width or 0.0)
        self.border_width = bw
        self.border_radius = float(self.w.theme.clip.border_radius or 0.0)
        self.clip_pen = QPen(QBrush(self.w.theme.clip.border_color), bw)
        self.clip_pen.setCosmetic(True)
        self.sel_pen = QPen(QBrush(self.w.theme.clip_selected), bw)
        self.sel_pen.setCosmetic(True)
        self.type_fills = {}
        self.type_pens = {}
        self.type_edges = {}
        for mt, st in (getattr(self.w.theme.clip, "type_styles", None) or {}).items():
            fill = st.get("fill")
            edge = st.get("edge")
            if fill is not None and fill.isValid():
                self.type_fills[mt] = QColor(fill)
            if edge is not None and edge.isValid():
                self.type_edges[mt] = QColor(edge)
                pen = QPen(QBrush(edge), bw)
                pen.setCosmetic(True)
                self.type_pens[mt] = pen
        self.top_overlay = QColor(self.w.theme.clip.top_overlay)
        self.top_overlay2 = QColor(self.w.theme.clip.top_overlay2)
        self.menu_pix = None  # menu icon removed; title container is now the click target
        from windows.views.timeline_backend.theme import _icon as _theme_icon
        _arrow = _theme_icon("themes/cosmic/images/dropdown-arrow.svg")
        self.dropdown_arrow_pix = _arrow if (_arrow and not _arrow.isNull()) else None
        self.thumb_cache = {}
        self._thumb_pending = {}
        self._thumb_regions = {}
        self._thumb_missing_logged = set()
        min_visible = float(getattr(self.w.theme.clip, "thumb_min_visible", 5.0) or 5.0)
        clip_min = float(getattr(self.w.theme.clip, "thumb_clip_min_width", 24.0) or 24.0)
        self._min_thumb_slot_width = max(6.0, min_visible)
        self._min_clip_thumb_width = max(min_visible * 2.0, clip_min)
        # Cache of fully rendered clip pixmaps keyed by clip id/size/pen color
        self.clip_cache = {}
        self.menu_margin = self.w.theme.menu_margin

    def clear_cache(self):
        """Clear cached rendered clip pixmaps."""
        self.clip_cache.clear()
        self.thumb_cache.clear()
        self._thumb_pending.clear()
        self._thumb_regions.clear()
        self._thumb_missing_logged.clear()
        self._last_thumb_request_time.clear()
        self._slot_fallback_cache.clear()
        self._retime_preview_cache.clear()

    def clear_render_cache(self, *, drop_preview=True):
        """Clear only cached clip renders while keeping loaded thumbnail pixmaps."""
        self.clip_cache.clear()
        if drop_preview:
            self._retime_preview_cache.clear()

    def invalidate_clip_thumbnails(
        self,
        clip_token,
        *,
        drop_cache=True,
        drop_pending=True,
        drop_fallback=True,
        drop_preview=True,
        invalidate_render_cache=True,
    ):
        """Invalidate thumbnail caches/requests for a single clip."""
        if not clip_token:
            return
        clip_id = str(clip_token).split(":", 1)[0]
        if drop_cache:
            cache_keys = [
                key for key in list(self.thumb_cache.keys())
                if isinstance(key, tuple) and key and str(key[0]).split(":", 1)[0] == clip_id
            ]
            for key in cache_keys:
                self.thumb_cache.pop(key, None)

        if drop_pending:
            pending_keys = [
                key for key in list(self._thumb_pending.keys())
                if isinstance(key, tuple) and key and str(key[0]).split(":", 1)[0] == clip_id
            ]
            for key in pending_keys:
                self._thumb_pending.pop(key, None)
                self._thumb_regions.pop(key, None)
                self._thumb_missing_logged.discard(key)

        if drop_fallback:
            fallback_keys = [
                key for key in list(self._slot_fallback_cache.keys())
                if isinstance(key, tuple) and key and str(key[0]).split(":", 1)[0] == clip_id
            ]
            for key in fallback_keys:
                self._slot_fallback_cache.pop(key, None)

        self._last_thumb_request_time.pop(clip_id, None)
        if drop_preview:
            self._retime_preview_cache.pop(clip_id, None)
        if invalidate_render_cache:
            self._invalidate_clip_cache_for_clip(clip_id)

    def clear_retime_preview(self, clip_token):
        if not clip_token:
            return
        clip_id = str(clip_token).split(":", 1)[0]
        self._retime_preview_cache.pop(clip_id, None)

    def _is_timing_preview_active(self, clip):
        if not clip or not isinstance(getattr(clip, "id", None), str):
            return False
        if not getattr(self.w, "clip_has_pending_override", None):
            return False
        if not self.w.clip_has_pending_override(clip):
            return False
        overrides = getattr(self.w, "_pending_clip_overrides", {}).get(clip.id, {})
        if not isinstance(overrides, dict) or not overrides.get("scale"):
            return False
        checker = getattr(self.w, "_is_active_resize_item", None)
        if callable(checker):
            return bool(checker(clip))
        return (
            getattr(self.w, "_resizing_item", None) is clip
            and getattr(self.w, "_press_hit", "") == "clip-edge"
        )

    def _is_trim_preview_active(self, clip):
        if not clip or not isinstance(getattr(clip, "id", None), str):
            return False
        if not getattr(self.w, "clip_has_pending_override", None):
            return False
        if not self.w.clip_has_pending_override(clip):
            return False
        overrides = getattr(self.w, "_pending_clip_overrides", {}).get(clip.id, {})
        if not isinstance(overrides, dict) or overrides.get("scale"):
            return False
        checker = getattr(self.w, "_is_active_resize_item", None)
        if callable(checker):
            return bool(checker(clip))
        return (
            getattr(self.w, "_resizing_item", None) is clip
            and getattr(self.w, "_press_hit", "") == "clip-edge"
        )

    def _trim_preview_offset_px(self, clip):
        overrides = getattr(self.w, "_pending_clip_overrides", {}).get(getattr(clip, "id", ""), {})
        if not isinstance(overrides, dict):
            return 0.0
        current_position = self._to_float(overrides.get("position"), self._clip_timeline_position(clip))
        initial_position = self._to_float(overrides.get("initial_position"), current_position)
        return (current_position - initial_position) * float(self.w.pixels_per_second or 0.0)

    def _retime_preview_result(self, clip, segment_rect):
        entry = self._retime_preview_cache.get(getattr(clip, "id", ""))
        if not entry:
            return None

        pix = entry.get("pix")
        blur = float(entry.get("blur", 0.0) or 0.0)
        if not isinstance(pix, QPixmap) or pix.isNull():
            return None

        ratio = 1.0
        try:
            ratio = float(pix.devicePixelRatioF())
        except AttributeError:
            try:
                ratio = float(pix.devicePixelRatio())
            except AttributeError:
                ratio = 1.0
        if not math.isfinite(ratio) or ratio <= 0.0:
            ratio = 1.0

        logical_w = max(1, int(round(float(segment_rect.width()) + (blur * 2.0))))
        logical_h = max(1, int(round(float(segment_rect.height()) + (blur * 2.0))))
        target_w = max(1, int(round(logical_w * ratio)))
        target_h = max(1, int(round(logical_h * ratio)))

        scaled = pix.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        if not scaled or scaled.isNull():
            return None
        if ratio != 1.0:
            scaled.setDevicePixelRatio(ratio)
        return (scaled, blur, [], False, None)

    def _segment_overdraw(self, view_width):
        """Return the horizontal overdraw (extra pixels) to render beyond the view."""

        blur = max(0.0, float(self.w.theme.clip.shadow_blur or 0.0))
        base = max(64.0, view_width * 0.25)
        return max(base, blur * 3.0)

    def paint(self, painter: QPainter):
        area = QRectF(
            self.w.track_name_width,
            self.w.ruler_height,
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        overdraw = self._segment_overdraw(area.width())
        expanded = QRectF(
            area.left() - overdraw,
            area.top(),
            area.width() + (overdraw * 2.0),
            area.height(),
        )

        self.w._effect_icon_rects = []
        self.w._clip_text_rects = []
        painter.save()
        painter.setClipRect(area)
        for rect, clip, selected in self.w.geometry.iter_clips():
            if not rect.intersects(expanded):
                continue

            segment_left = max(rect.left(), expanded.left())
            segment_right = min(rect.right(), expanded.right())
            if segment_right <= segment_left:
                continue

            segment_rect = QRectF(
                segment_left,
                rect.top(),
                segment_right - segment_left,
                rect.height(),
            )

            pen = self.sel_pen if selected else self.type_pens.get(self._clip_media_type(clip), self.clip_pen)
            locked = self.w._is_track_locked((clip.data if isinstance(clip.data, dict) else {}).get("layer"))
            if locked:
                pen = self.dimmed_pen(pen)
                painter.save()
                painter.setOpacity(0.8)
            self._draw_clip(painter, rect, segment_rect, clip, pen, selected)
            if locked:
                painter.restore()
        painter.restore()

    @staticmethod
    def _to_float(value, fallback=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _clip_key(self, clip):
        clip_id = getattr(clip, "id", None)
        return str(clip_id) if clip_id is not None else ""

    def _has_static_image(self, clip):
        """Return True if the clip reports a static image so all frames are identical."""
        if not clip:
            return False
        data = clip.data if isinstance(clip.data, dict) else {}
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}
        flags = (
            data.get("has_static_image"),
            reader.get("has_static_image"),
            data.get("has_single_image"),
            reader.get("has_single_image"),
        )
        for value in flags:
            if isinstance(value, bool) and value:
                return True
            if isinstance(value, (int, float)) and value:
                return True

        # Audio assets (e.g. mp3/m4a/ogg) should reuse one visual frame
        # across the timeline even if libopenshot reports dynamic frame counts.
        if self._clip_is_audio_media(clip):
            return True
        return False

    def _clip_is_audio_media(self, clip):
        """Best-effort audio media detection resilient to reader metadata quirks."""
        if not clip:
            return False
        data = clip.data if isinstance(clip.data, dict) else {}
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}

        media_type = str(reader.get("media_type") or data.get("media_type") or "").strip().lower()
        if media_type == "audio":
            return True

        source_path = str(
            reader.get("path")
            or data.get("path")
            or reader.get("file_path")
            or data.get("file_path")
            or ""
        ).strip().lower()
        audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav", ".wma")
        if source_path.endswith(audio_exts):
            return True

        return False

    def _clip_file_id(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        file_id = data.get("file_id")
        return str(file_id) if file_id else None

    def _clip_is_audio_only(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}

        has_video = reader.get("has_video")
        has_video = True if has_video is None else bool(has_video)

        has_audio = reader.get("has_audio")
        has_audio = True if has_audio is None else bool(has_audio)
        return has_audio and not has_video

    def _audio_thumbnail_pixmap(self):
        key = ("_fallback_", "audio")
        cached = self.thumb_cache.get(key)
        if cached and not cached.isNull():
            return cached

        path = os.path.join(info.PATH, "images", "AudioThumbnail.svg")
        pix = QPixmap(path) if os.path.exists(path) else QPixmap()
        self.thumb_cache[key] = pix
        return pix if not pix.isNull() else None

    def _clip_time_bounds(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        start = self._to_float(data.get("start"), 0.0)
        end = self._to_float(data.get("end"), start)
        if self.w.clip_has_pending_override(clip):
            overrides = self.w._pending_clip_overrides.get(clip.id, {})
            pending_start = overrides.get("start")
            pending_end = overrides.get("end")
            if pending_start is not None:
                start = self._to_float(pending_start, start)
            if pending_end is not None:
                end = self._to_float(pending_end, end)
        if end < start:
            end = start
        return start, max(0.0, end - start)

    def _existing_thumb_path(self, file_id, frame, fps=0.0):
        subdir = os.path.join(info.THUMBNAIL_PATH, file_id)
        candidates = [
            os.path.join(subdir, f"{frame}.png"),
        ]
        if frame == 1:
            candidates.append(os.path.join(info.THUMBNAIL_PATH, f"{file_id}.png"))
        else:
            candidates.append(os.path.join(info.THUMBNAIL_PATH, f"{file_id}-{frame}.png"))

        for path in candidates:
            if path and os.path.exists(path):
                return path

        fps = float(fps or 0.0)
        if fps > 0.0:
            rounded_frame = RoundFrameToThumbnailGrid(frame, fps)
            if rounded_frame != frame:
                rounded_path = os.path.join(subdir, f"{rounded_frame}.png")
                if os.path.exists(rounded_path):
                    return rounded_path
                if rounded_frame == 1:
                    legacy_path = os.path.join(info.THUMBNAIL_PATH, f"{file_id}.png")
                else:
                    legacy_path = os.path.join(info.THUMBNAIL_PATH, f"{file_id}-{rounded_frame}.png")
                if os.path.exists(legacy_path):
                    return legacy_path
        return ""

    def _frame_for_offset(self, offset, fps):
        return _frame_for_seconds(offset, fps)

    def _frame_rounding_increment(self, fps, interval_seconds, clip=None, project_fps=None):
        """Return frame rounding increment based on frames-per-slot at current zoom.

        Keep rounding local enough to reuse nearby thumbnails while avoiding
        visible multi-second jumps as the zoom level changes. Use a coarser
        half-second ceiling to reduce churn while zooming.
        """
        fps = float(fps or 0.0)
        if fps <= 0.0 or not interval_seconds or interval_seconds <= 0.0:
            return 1
        frames_per_slot = fps * float(interval_seconds)
        if frames_per_slot <= 1.25:
            return 1
        if clip is not None and _has_time_curve(clip, fps, project_fps):
            # Time-mapped clips are sensitive to project-frame rounding because
            # small changes in timeline time can map to large source-frame jumps.
            # Keep the earlier, tighter rounding so slot thumbnails stay anchored.
            max_increment = max(1, int(round(fps / 4.0)))
            return max(1, min(int(round(frames_per_slot)), max_increment))
        # Cap rounding at roughly a half-second so cache reuse stays local
        # without rolling through nearby frames on tiny zoom changes.
        max_increment = max(1, int(round(fps / 2.0)))
        increment = max(1, min(int(round(frames_per_slot)), max_increment))
        return max(1, min(increment * 2, max_increment))

    def _segment_timing(self, segment, clip_duration):
        segment = segment or {}
        offset = self._to_float(segment.get("offset_seconds"), 0.0)
        duration = self._to_float(segment.get("duration_seconds"), clip_duration)
        includes_start = segment.get("includes_start", True)
        includes_end = segment.get("includes_end", True)
        return {
            "offset": max(0.0, offset),
            "duration": max(0.0, duration),
            "includes_start": bool(includes_start),
            "includes_end": bool(includes_end),
        }

    def _clip_media_duration(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}
        candidate_durations = []

        duration = self._to_float(reader.get("duration"))
        if duration > 0.0:
            candidate_durations.append(duration)
        video_length = self._to_float(reader.get("video_length"))
        if video_length > 0.0:
            fps_meta = reader.get("fps") if isinstance(reader.get("fps"), dict) else {}
            fps_num = self._to_float(fps_meta.get("num"))
            fps_den = self._to_float(fps_meta.get("den"))
            if fps_num > 0.0 and fps_den > 0.0:
                fps_value = fps_num / fps_den
                if fps_value > 0.0:
                    candidate_durations.append(video_length / fps_value)
        project_fps = self._to_float(getattr(self.w, "fps_float", None))
        time_data = data.get("time") if isinstance(data.get("time"), dict) else {}
        time_points = time_data.get("Points") if isinstance(time_data.get("Points"), list) else []
        if project_fps > 0.0 and len(time_points) >= 2:
            x_values = []
            for point in time_points:
                if not isinstance(point, dict):
                    continue
                co = point.get("co")
                if not isinstance(co, dict):
                    continue
                x_val = self._to_float(co.get("X"))
                if x_val > 0.0:
                    x_values.append(x_val)
            if len(x_values) >= 2:
                time_duration = (max(x_values) - min(x_values)) / project_fps
                if time_duration > 0.0:
                    candidate_durations.append(time_duration)
        clip_duration = self._to_float(data.get("duration"))
        if clip_duration > 0.0:
            candidate_durations.append(clip_duration)
        start = self._to_float(data.get("start"))
        end = self._to_float(data.get("end"), start)
        span = end - start
        if span > 0.0:
            candidate_durations.append(span)
        return max(candidate_durations) if candidate_durations else 0.0

    def _clip_trim_start(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        start = self._to_float(data.get("start"), 0.0)

        if self.w.clip_has_pending_override(clip):
            overrides = self.w._pending_clip_overrides.get(clip.id, {})
            pending_start = overrides.get("start")
            if pending_start is not None:
                start = self._to_float(pending_start, start)

        return start

    def _clip_aspect_ratio(self, clip):
        """Return the source aspect ratio of a clip, falling back to 16:9."""
        data = clip.data if isinstance(clip.data, dict) else {}
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}
        w = self._to_float(reader.get("width"))
        h = self._to_float(reader.get("height"))
        if w > 0 and h > 0:
            return max(0.25, min(w / h, 4.0))  # clamp to sane range
        return 16.0 / 9.0

    def _clip_media_fps(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}
        fps_meta = reader.get("fps") if isinstance(reader.get("fps"), dict) else {}
        fps_num = self._to_float(fps_meta.get("num"))
        fps_den = self._to_float(fps_meta.get("den"), 1.0)
        if fps_num > 0.0 and fps_den > 0.0:
            return fps_num / fps_den
        fps_value = self._to_float(data.get("fps"))
        if fps_value > 0.0:
            return fps_value
        fps = self._to_float(reader.get("frame_rate"))
        if fps > 0.0:
            return fps
        return float(getattr(self.w, "fps_float", 24.0) or 24.0)

    def _clip_pixmap(self, full_rect, segment_rect, clip):
        """Return cached pixmap for the visible portion of a clip."""

        w = int(segment_rect.width())
        h = int(segment_rect.height())
        if w <= 0 or h <= 0:
            return None

        if self._is_timing_preview_active(clip):
            preview = self._retime_preview_result(clip, segment_rect)
            if preview:
                return preview

        ratio = 1.0
        try:
            ratio = float(self.w.devicePixelRatioF())
        except AttributeError:
            try:
                ratio = float(self.w.devicePixelRatio())
            except AttributeError:
                ratio = 1.0
        if not math.isfinite(ratio) or ratio <= 0.0:
            ratio = 1.0

        clip_width = max(float(full_rect.width()), 0.0)
        offset_px = max(0.0, float(segment_rect.left() - full_rect.left()))
        offset_seconds = 0.0
        duration_seconds = 0.0
        clip_duration_seconds = 0.0
        if self.w.pixels_per_second > 0.0:
            offset_seconds = offset_px / float(self.w.pixels_per_second)
            duration_seconds = segment_rect.width() / float(self.w.pixels_per_second)
            clip_duration_seconds = clip_width / float(self.w.pixels_per_second)

        includes_start = offset_px <= 0.5
        includes_end = (segment_rect.right() + 0.5) >= full_rect.right()

        segment_info = {
            "offset_px": offset_px,
            "segment_width": float(segment_rect.width()),
            "clip_width": clip_width,
            "includes_start": includes_start,
            "includes_end": includes_end,
            "offset_seconds": offset_seconds,
            "duration_seconds": duration_seconds,
            "clip_duration": clip_duration_seconds,
        }

        use_cache = not self.w.clip_has_pending_override(clip)
        waveform_token = self.w.clip_waveform_cache_token(clip) if use_cache else None
        key = (
            clip.id,
            w,
            h,
            waveform_token,
            round(ratio, 4),
            round(offset_seconds, 4),
            round(duration_seconds, 4),
            includes_start,
            includes_end,
        ) if use_cache else None
        if use_cache and key in self.clip_cache:
            cached = self.clip_cache[key]
            if isinstance(cached, tuple) and len(cached) == 3:
                pix, blur, icons = cached
                cached = (pix, blur, icons, False, None)
                self.clip_cache[key] = cached
            elif isinstance(cached, tuple) and len(cached) == 4:
                pix, blur, icons, pending = cached
                cached = (pix, blur, icons, pending, None)
                self.clip_cache[key] = cached
            return cached

        small = w < 10
        tiny = w < 2
        blur = self.w.theme.clip.shadow_blur if not small else 0
        if not includes_start or not includes_end:
            blur = 0
        radius = self.w.theme.clip.border_radius if not small else 0
        shadow_col = self.w.theme.clip.shadow_color if not small else QColor()

        img_w = max(1, int(math.ceil((w + (blur * 2.0)) * ratio)))
        img_h = max(1, int(math.ceil((h + (blur * 2.0)) * ratio)))
        img = QImage(img_w, img_h, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)

        if blur and shadow_col.isValid():
            self._draw_clip_shadow(img, w, h, blur, radius, shadow_col, ratio)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if ratio != 1.0:
            painter.scale(ratio, ratio)
        inner_rect = QRectF(blur, blur, w, h)

        icon_entries = []
        text_entry = None
        pending_thumbs = False
        if not tiny:
            self._fill_clip_background(painter, inner_rect, segment_info, clip=clip)
            icon_entries, pending_thumbs, text_entry = self._draw_clip_contents(
                painter, clip, inner_rect, segment_info
            )

        painter.end()

        pix = QPixmap.fromImage(img)
        if ratio != 1.0:
            pix.setDevicePixelRatio(ratio)
        result = (pix, blur, icon_entries, pending_thumbs, text_entry)
        if getattr(clip, "id", None):
            self._retime_preview_cache[str(clip.id)] = {
                "pix": pix,
                "blur": blur,
                "icons": icon_entries,
                "text_entry": text_entry,
            }
        if use_cache and key is not None and not pending_thumbs:
            self.clip_cache[key] = result
        return result

    def _draw_clip_shadow(self, img, w, h, blur, radius, shadow_col, ratio):
        if blur <= 0 or not shadow_col.isValid():
            return

        img_w = img.width()
        img_h = img.height()
        shadow = QImage(img_w, img_h, QImage.Format_ARGB32_Premultiplied)
        shadow.fill(0)

        fill_color = QColor(shadow_col)
        fill_color.setAlpha(int(fill_color.alpha() * 0.7))

        shadow_painter = QPainter(shadow)
        shadow_painter.setRenderHint(QPainter.Antialiasing, True)
        if ratio != 1.0:
            shadow_painter.scale(ratio, ratio)
        path = QPainterPath()
        path.addRoundedRect(QRectF(blur, blur, w, h), radius, radius)
        shadow_painter.fillPath(path, fill_color)
        shadow_painter.end()

        shadow_pix = QPixmap.fromImage(shadow)
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(max(0.1, float(blur) * ratio))

        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(shadow_pix)
        item.setGraphicsEffect(blur_effect)
        scene.addItem(item)

        blurred = QImage(img_w, img_h, QImage.Format_ARGB32_Premultiplied)
        blurred.fill(0)
        blur_painter = QPainter(blurred)
        scene.render(blur_painter, QRectF(), QRectF(0, 0, img_w, img_h))
        blur_painter.end()

        composite = QPainter(img)
        composite.drawImage(0, 0, blurred)
        composite.end()

    def _clip_fill_path(self, rect, includes_start=True, includes_end=True):
        if rect.width() <= 0.0 or rect.height() <= 0.0:
            return None
        radius = 0.0
        if rect.width() >= 10.0 and rect.height() > 0.0:
            radius = min(float(self.border_radius or 0.0), min(rect.width(), rect.height()) / 2.0)
        if radius <= 0.0:
            return None

        if includes_start and includes_end:
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)
            return path

        left = rect.left()
        right = rect.right()
        top = rect.top()
        bottom = rect.bottom()
        path = QPainterPath()

        if includes_start:
            path.moveTo(left, top + radius)
            path.quadTo(left, top, left + radius, top)
        else:
            path.moveTo(left, top)

        if includes_end:
            path.lineTo(right - radius, top)
            path.quadTo(right, top, right, top + radius)
            path.lineTo(right, bottom - radius)
            path.quadTo(right, bottom, right - radius, bottom)
        else:
            path.lineTo(right, top)
            path.lineTo(right, bottom)

        if includes_start:
            path.lineTo(left + radius, bottom)
            path.quadTo(left, bottom, left, bottom - radius)
            path.lineTo(left, top + radius)
        else:
            path.lineTo(left, bottom)
            path.lineTo(left, top)

        path.closeSubpath()
        return path

    def _fill_clip_background(self, painter, inner_rect, segment=None, clip=None):
        includes_start = True
        includes_end = True
        if isinstance(segment, dict):
            includes_start = bool(segment.get("includes_start", True))
            includes_end = bool(segment.get("includes_end", True))
        shape_path = self._clip_fill_path(inner_rect, includes_start, includes_end)

        mt = self._clip_media_type(clip) if clip is not None else ""
        type_fill = self.type_fills.get(mt) if mt else None

        bg = type_fill or self.w.theme.clip.background
        bg2 = self.w.theme.clip.background2
        if type_fill is not None:
            bg2 = QColor()

        if bg2.isValid() and bg2 != bg:
            grad = QLinearGradient(QPointF(inner_rect.topLeft()), QPointF(inner_rect.bottomLeft()))
            grad.setColorAt(0, bg)
            grad.setColorAt(1, bg2)
            if shape_path:
                painter.fillPath(shape_path, QBrush(grad))
            else:
                painter.fillRect(inner_rect, QBrush(grad))
        elif bg.isValid():
            if shape_path:
                painter.fillPath(shape_path, bg)
            else:
                painter.fillRect(inner_rect, bg)

        # Match JS .clip_top overlay (light-to-transparent).
        top_overlay = QColor(self.top_overlay)
        bottom_overlay = QColor(self.top_overlay2)
        if top_overlay.isValid() or bottom_overlay.isValid():
            if not top_overlay.isValid() and bottom_overlay.isValid():
                top_overlay = QColor(bottom_overlay)
            if not bottom_overlay.isValid() and top_overlay.isValid():
                bottom_overlay = QColor(top_overlay)
                bottom_overlay.setAlpha(0)
            overlay = QLinearGradient(QPointF(inner_rect.topLeft()), QPointF(inner_rect.bottomLeft()))
            overlay.setColorAt(0.0, top_overlay)
            overlay.setColorAt(1.0, bottom_overlay)
            if shape_path:
                painter.fillPath(shape_path, QBrush(overlay))
            else:
                painter.fillRect(inner_rect, QBrush(overlay))

        edge = self.type_edges.get(mt) if mt else None
        if edge is not None and includes_start:
            painter.save()
            if shape_path:
                painter.setClipPath(shape_path)
            painter.fillRect(QRectF(inner_rect.left(), inner_rect.top(), 3.0, inner_rect.height()), edge)
            painter.restore()

    def _draw_clip_contents(self, painter, clip, inner_rect, segment):
        bw = float(self.border_width or 0.0)
        inner = inner_rect.adjusted(bw, bw, -bw, -bw)
        painter.save()
        painter.setClipRect(inner)

        right = inner.right() - self.menu_margin
        text_right = inner.right()
        icon_entries = []
        text_entry = None
        pending_thumbs = False

        has_waveform = self._draw_waveform(painter, clip, inner, segment)

        includes_start = segment.get("includes_start", True) if isinstance(segment, dict) else True

        if not has_waveform:
            pending_thumbs = self._draw_thumbnails(painter, clip, inner, segment)

        if includes_start:
            # Title container anchored at top-left; effect badges drawn inside it
            text_entry = self._draw_clip_text(
                painter,
                clip,
                inner,
                inner.x(),
                text_right,
                visible_width=float(segment.get("segment_width") or inner_rect.width()) if isinstance(segment, dict) else float(inner_rect.width()),
                icon_entries=icon_entries,
            )

        painter.restore()
        return icon_entries, pending_thumbs, text_entry

    def _add_slot_if_valid(self, slots, seen, center_clip_time, half_interval, segment_start,
                           segment_end, trim_start, media_duration, inner_x, top,
                           thumb_w, thumb_h, pixels_per_second, view_left, view_right):
        """Helper to add a slot if it meets all criteria."""
        start_clip_time = center_clip_time - half_interval
        end_clip_time = center_clip_time + half_interval

        # Require overlap with visible segment
        if end_clip_time <= segment_start + 1e-6 or start_clip_time >= segment_end - 1e-6:
            return

        # X coordinate within the visible segment
        local_x = (start_clip_time - segment_start) * pixels_per_second
        if local_x >= view_right or (local_x + thumb_w) <= view_left:
            return

        # Media time check
        center_media_time = trim_start + center_clip_time
        if center_media_time < -1e-6 or center_media_time > media_duration + 1e-6:
            return
        center_media_time = max(0.0, min(center_media_time, media_duration))

        # Deduplicate by clip-local time
        key = round(center_clip_time, 4)
        if key in seen:
            return
        seen.add(key)

        rect = QRectF(inner_x + local_x, top, thumb_w, thumb_h)
        slots.append((center_clip_time, rect))

    def _finishItemResize(self):
        item = self._resizing_item
        if not item:
            return
        start = self._resize_new_start
        end = self._resize_new_end
        position = self._resize_new_position
        if isinstance(item, Clip):
            if self.enable_timing:
                duration = end - start
                item.data["start"] = self._timing_original_start
                item.data["end"] = self._snap_time(self._timing_original_start + duration)
                item.data["position"] = self._snap_time(position)
                self.RetimeClip(item.id, item.data["end"], item.data["position"])
            else:
                item.data["start"] = self._snap_time(start)
                item.data["end"] = self._snap_time(end)
                item.data["position"] = self._snap_time(position)
                self.update_clip_data(item.data, only_basic_props=True, ignore_reader=True)
            # Clear pending override after update to ensure consistency
            self._pending_clip_overrides.pop(item.id, None)
        else:
            reader = {}
            if isinstance(item.data, dict):
                for key in ("mask_reader", "reader"):
                    candidate = item.data.get(key)
                    if isinstance(candidate, dict):
                        reader = candidate
                        break
            static_mask = False
            if isinstance(reader, dict):
                static_mask = bool(reader.get("has_single_image")) if "has_single_image" in reader else bool(
                    is_single_image_media(reader)
                )
            item.data["position"] = self._snap_time(position)
            item.data["start"] = self._snap_time(start)
            item.data["end"] = self._snap_time(end)
            item.data["duration"] = self._snap_time(item.data["end"] - item.data["start"])
            item.data["_auto_direction"] = static_mask
            self.update_transition_data(item.data, only_basic_props=True)

        self._resizing_item = None
        self._snap_keyframe_seconds = []
        self.snap.reset()
        if hasattr(self, "_resize_snap_ignore_backup"):
            self._snap_ignore_ids = self._resize_snap_ignore_backup
            del self._resize_snap_ignore_backup
        self._update_project_duration()
        self.changed(None)
        self.geometry.mark_dirty()  # Ensure geometry rebuild
        self.update()
        self._release_cursor()
        if self._last_event:
            self._updateCursor(self._last_event.pos())
        if hasattr(self, "_resize_initial_world_rect"):
            del self._resize_initial_world_rect
        self._resize_clip_max_duration = None
        self._resize_allow_left_overflow = False
        self._resize_clip_is_single_image = False

    def _build_thumbnail_slots(self, clip, inner, segment, style, timing):
        """ Build thumbnail slots for a clip. """
        if style == "none":
            return [], None

        segment = segment or {}
        timing = timing or {}

        # Visible width of this segment (in pixels)
        visible_width = max(0.0, float(segment.get("segment_width") or inner.width()))
        if visible_width < self._min_clip_thumb_width:
            return [], None

        # Full clip width in pixels at the current zoom
        clip_width = float(segment.get("clip_width") or visible_width)
        if clip_width <= 0.0:
            return [], None

        # Slot dimensions — height fills the clip; width matches the clip's source AR.
        # thumb_w must be an integer pixel value so all slot positions share the same
        # fractional offset and round consistently in drawPixmap, preventing per-slot jitter.
        thumb_h = max(self._min_thumb_slot_width, inner.height())
        if self.w.theme.clip.thumb_width:
            thumb_w = float(max(self._min_thumb_slot_width, float(self.w.theme.clip.thumb_width)))
        else:
            thumb_w = float(max(self._min_thumb_slot_width, round(inner.height() * self._clip_aspect_ratio(clip))))
        top = inner.y()

        pixels_per_second = float(self.w.pixels_per_second or 0.0)
        if pixels_per_second <= 0.0:
            return [], None

        # Clip duration on the timeline (seconds)
        clip_duration = self._to_float(
            segment.get("clip_duration"),
            clip_width / pixels_per_second,
        )
        if clip_duration <= 0.0:
            return [], None

        # Segment window in clip-local seconds
        segment_offset = self._to_float(segment.get("offset_seconds"), 0.0)
        segment_duration = self._to_float(
            segment.get("duration_seconds"),
            clip_duration,
        )
        segment_duration = max(0.0, min(segment_duration, clip_duration))
        if segment_duration <= 0.0:
            return [], None

        segment_start = segment_offset
        segment_end = segment_start + segment_duration
        if segment_end <= segment_start:
            return [], None

        # Source media duration (seconds)
        media_duration = self._clip_media_duration(clip)
        if media_duration <= 0.0:
            media_duration = clip_duration
        media_duration = max(media_duration, clip_duration)
        time_data = clip.data.get("time") if isinstance(getattr(clip, "data", None), dict) and isinstance(clip.data.get("time"), dict) else {}
        time_points = time_data.get("Points") if isinstance(time_data.get("Points"), list) else []
        has_time_curve = len(time_points) >= 2

        # Slot spacing in time. Keep visual geometry tied to the nominal
        # thumbnail width in pixels. Frame sampling can still use a quantized
        # interval, but quantizing the drawn slot positions causes all slots to
        # jump by a pixel as smooth zoom crosses frame-rounding thresholds.
        interval_pixels = max(thumb_w, self._min_thumb_slot_width)
        geometry_interval_seconds = interval_pixels / pixels_per_second
        if geometry_interval_seconds <= 0.0:
            geometry_interval_seconds = 0.01
        interval_seconds = geometry_interval_seconds
        if style == "entire":
            clip_fps = self._clip_media_fps(clip)
            if clip_fps > 0.0:
                interval_frames = max(1, int(round(interval_seconds * clip_fps)))
                interval_seconds = interval_frames / clip_fps
        half_interval = interval_seconds * 0.5
        slot_duration_seconds = geometry_interval_seconds

        includes_start = bool(timing.get("includes_start", True))
        includes_end = bool(timing.get("includes_end", True))

        # --- World-anchor via (position - start) --------------------------

        trim_start = self._clip_trim_start(clip)  # media in-point
        clip_pos = self._clip_timeline_position(clip)  # world time of clip left
        anchor_world = clip_pos - trim_start  # world time of media 0.0

        # World-time range covered by this segment of the clip
        segment_start_world = clip_pos + segment_start
        segment_end_world = segment_start_world + segment_duration

        view_left = 0.0
        view_right = visible_width

        slots = []
        seen = set()

        epsilon = 1e-6

        def add_center_world(center_world, geometry_world=None):
            """
            Add a slot whose sampling left edge begins at `center_world` (timeline
            seconds), if it overlaps the visible segment and lies within clip & media.
            `geometry_world` can differ for pixel-stable visual placement during
            smooth zoom while keeping prior frame sampling.
            """
            if geometry_world is None:
                geometry_world = center_world

            # Media time (0 at media start), using the visual slot coverage.
            slot_start_media_time = geometry_world - anchor_world

            # Clip-local time (0 at clip's left edge), using the visual slot coverage.
            slot_start_clip_time = geometry_world - clip_pos
            slot_end_clip_time = slot_start_clip_time + slot_duration_seconds

            # Clip-local sampling time. This is what _draw_thumbnails uses for
            # frame selection.
            sample_start_clip_time = center_world - clip_pos

            # Require positive overlap with the visible segment. Boundary-only
            # slots can oscillate in/out during smooth zoom and fight with the
            # first real visible slot.
            overlap_start = max(slot_start_clip_time, segment_start)
            overlap_end = min(slot_end_clip_time, segment_end)
            if (overlap_end - overlap_start) <= epsilon:
                return

            # Slot coverage in media time
            slot_end_media_time = slot_start_media_time + slot_duration_seconds

            # Require overlap with media bounds [0, media_duration] (lenient)
            if not has_time_curve:
                if (
                    slot_end_media_time < -epsilon
                    or slot_start_media_time > media_duration + epsilon
                ):
                    return

            # Require positive visible width in the current segment.
            local_x = (slot_start_clip_time - segment_start) * pixels_per_second
            visible_left = max(local_x, view_left)
            visible_right = min(local_x + thumb_w, view_right)
            if (visible_right - visible_left) <= epsilon:
                return

            # Deduplicate by clip-local time to avoid overlapping slots
            key = round(sample_start_clip_time, 4)
            if key in seen:
                return
            seen.add(key)

            rect = QRectF(inner.x() + local_x, top, thumb_w, thumb_h)
            # Store slot start time; _draw_thumbnails samples near the center.
            slots.append((sample_start_clip_time, rect))

        # --- Style handling -----------------------------------------------

        if style == "start":
            if includes_start:
                add_center_world(segment_start_world)
        elif style == "start-end":
            if includes_start:
                add_center_world(segment_start_world)
            # If the visible segment cannot fit two full slots, prioritize the
            # start slot to avoid the end slot covering it on very short clips.
            allow_end_slot = True
            if includes_start and includes_end and segment_duration < (slot_duration_seconds * 2.0):
                allow_end_slot = False
            if includes_end and allow_end_slot:
                # Start slot so its right edge aligns with the clip end
                clip_end_world = clip_pos + max(0.0, clip_duration - slot_duration_seconds)
                add_center_world(clip_end_world)
        else:
            # Full-grid style ("entire", etc.)
            # Slot starts should cover any thumbnail overlapping the visible
            # segment, including partials at either edge.
            n_min = int(
                math.floor(
                    (segment_start_world - slot_duration_seconds - anchor_world) / geometry_interval_seconds
                )
            ) - 2
            n_max = int(
                math.ceil(
                    (segment_end_world - anchor_world) / geometry_interval_seconds
                )
            ) + 2

            for n in range(n_min, n_max + 1):
                center_world = anchor_world + n * interval_seconds
                geometry_world = anchor_world + n * geometry_interval_seconds
                add_center_world(center_world, geometry_world)

        if not slots:
            return [], interval_seconds

        return slots, interval_seconds

    def _draw_thumbnails(self, painter, clip, inner, segment):
        style = str(getattr(self.w, "thumbnail_style", "entire") or "").strip().lower()
        if style == "none":
            return False
        clip_key = self._clip_key(clip)
        file_id = self._clip_file_id(clip)
        if not (clip_key and file_id):
            return False

        _, clip_duration = self._clip_time_bounds(clip)
        timing = self._segment_timing(segment, clip_duration)
        slots, interval_seconds = self._build_thumbnail_slots(clip, inner, segment, style, timing)
        if not slots:
            return False

        clip_fps = self._clip_media_fps(clip)
        project_fps = float(getattr(self.w, "fps_float", clip_fps) or clip_fps or 24.0)
        trim_start = self._clip_trim_start(clip)
        slot_duration_seconds = float(interval_seconds or 0.0)
        half_slot_duration = slot_duration_seconds * 0.5
        segment_offset = float(timing.get("offset", 0.0) or 0.0)
        segment_duration = float(timing.get("duration", 0.0) or 0.0)
        segment_end = segment_offset + segment_duration
        edge_epsilon = 1e-6
        frame_duration = (1.0 / project_fps) if project_fps and project_fps > 0.0 else 0.0
        edge_time_epsilon = max(edge_epsilon, frame_duration * 0.5) if frame_duration > 0.0 else edge_epsilon
        segment_at_clip_start = segment_offset <= edge_time_epsilon
        segment_at_clip_end = abs(clip_duration - segment_end) <= edge_time_epsilon
        clip_start_frame = _frame_for_seconds(trim_start + segment_offset, clip_fps)
        if frame_duration > 0.0:
            clip_end_frame = _frame_for_seconds(max(trim_start + segment_offset, trim_start + segment_end - frame_duration), clip_fps)
        else:
            clip_end_frame = _frame_for_seconds(trim_start + segment_end, clip_fps)
        checker = getattr(self.w, "_is_active_resize_item", None)
        if callable(checker):
            is_resizing_clip = bool(checker(clip))
        else:
            is_resizing_clip = (
                getattr(self.w, "_resizing_item", None) is clip
                and getattr(self.w, "_press_hit", "") == "clip-edge"
            )
        throttle_requests = is_resizing_clip and style in ("start", "start-end")
        pending = False
        generation = getattr(self.w, "thumbnail_generation", 0)
        rounding = self._frame_rounding_increment(
            clip_fps,
            interval_seconds,
            clip=clip,
            project_fps=project_fps,
        )
        static_image = self._has_static_image(clip)
        static_frame = 1 if static_image else None

        for slot_index, (time_offset, rect) in enumerate(slots):
            if self._clip_is_audio_only(clip):
                pix = self._audio_thumbnail_pixmap()
                if pix:
                    self._paint_thumbnail_pixmap(painter, pix, rect, inner)
                else:
                    pending = True
                continue

            slot_start_time = float(time_offset)
            slot_end_time = slot_start_time + slot_duration_seconds
            slot_center_time = slot_start_time + half_slot_duration
            clamped_center_time = slot_center_time
            if clamped_center_time < segment_offset:
                clamped_center_time = segment_offset
            elif clamped_center_time > segment_end:
                clamped_center_time = segment_end
            visible_slot_start = max(slot_start_time, segment_offset)
            visible_slot_end = min(slot_end_time, segment_end)
            visible_center_time = clamped_center_time
            if visible_slot_end >= visible_slot_start:
                visible_center_time = visible_slot_start + ((visible_slot_end - visible_slot_start) * 0.5)

            touches_start = slot_start_time <= segment_offset + edge_epsilon
            touches_end = slot_end_time >= segment_end - edge_epsilon
            is_first_slot = slot_index == 0
            is_last_slot = slot_index == (len(slots) - 1)
            slot_role = "grid"
            is_edge = False
            if style != "entire":
                is_edge = (
                    (segment_at_clip_start and touches_start and is_first_slot)
                    or (segment_at_clip_end and touches_end and is_last_slot)
                )
                if segment_at_clip_start and touches_start and is_first_slot:
                    slot_role = "edge-start"
                elif segment_at_clip_end and touches_end and is_last_slot:
                    slot_role = "edge-end"

            # For "start" and "start-end", anchor edge thumbnails to exact trim edges.
            # Keep strip/entire behavior unchanged (centered sampling).
            if style in ("start", "start-end") and slot_role == "edge-start":
                sample_time = segment_offset
            elif style in ("start", "start-end") and slot_role == "edge-end":
                if frame_duration > 0.0:
                    sample_time = max(segment_offset, segment_end - frame_duration)
                else:
                    sample_time = segment_end
            elif style == "entire":
                sample_time = visible_center_time
            else:
                sample_time = clamped_center_time

            frame = None
            pix = None
            clip_time = trim_start + sample_time
            frame = self._frame_for_offset(clip_time, clip_fps)
            if rounding > 1 and (style == "entire" or not is_edge):
                frame = max(1, int(round((frame - 1) / rounding) * rounding) + 1)
            frame = min(max(frame, clip_start_frame), clip_end_frame)
            mapped_frame = resolve_source_frame(
                clip,
                clip_time,
                clip_fps,
                project_fps,
                fallback_frame=frame,
            )
            frame = mapped_frame
            if static_frame:
                frame = static_frame

            key = (clip_key, frame)
            cached = self.thumb_cache.get(key)
            if cached and not cached.isNull():
                pix = cached
            else:
                allow_request = True
                if throttle_requests:
                    allow_request = self._can_request_thumbnail(clip_key, throttle_requests)

                # Always queue/load for all slots in the clip (since clip is visible during paint)
                pix = self._get_thumbnail_pixmap(
                    clip,
                    clip_key,
                    file_id,
                    frame,
                    rect,
                    generation,
                    allow_request=allow_request,
                )
                if pix is None and slot_role != "grid":
                    fallback = self._slot_fallback_cache.get((clip_key, slot_role))
                    if fallback and not fallback.isNull():
                        pix = fallback

            if pix:
                self._paint_thumbnail_pixmap(painter, pix, rect, inner)
                if slot_role != "grid":
                    self._slot_fallback_cache[(clip_key, slot_role)] = pix
            else:
                pending = True

        return pending

    def _get_thumbnail_pixmap(self, clip, clip_key, file_id, frame, rect, generation, *, allow_request=True):
        key = (clip_key, frame)

        # 1. If we already have it cached → return it immediately
        if key in self.thumb_cache:
            cached = self.thumb_cache[key]
            if not cached.isNull():
                return cached
            # Null pixmap means "we tried and failed" — don't request again this generation
            if self._thumb_pending.get(key) == generation:
                return None

        # 2. If already requested this generation → don't request again
        if self._thumb_pending.get(key) == generation:
            return None

        # 3. Load existing on-disk thumbnail if available
        path = self._existing_thumb_path(file_id, frame, self._clip_media_fps(clip))
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                self.thumb_cache[key] = pix
                return pix

        if getattr(self.w, "_suspend_thumbnail_requests", False):
            return None

        if not allow_request:
            return None

        # Queue the request exactly once per generation (only for visible slots)
        self._thumb_pending[key] = generation
        self._thumb_regions[key] = QRectF(rect)
        if self.w.thumbnail_manager:
            self.w.thumbnail_manager.request_thumbnail(clip_key, file_id, frame, generation)
            if key not in self._thumb_missing_logged:
                self._thumb_missing_logged.add(key)

        return None

    def _paint_thumbnail_pixmap(self, painter, pixmap, rect, clip_bounds):
        if not pixmap or pixmap.isNull() or not isinstance(rect, QRectF) or not isinstance(clip_bounds, QRectF):
            return

        visible_rect = rect.intersected(clip_bounds)
        if visible_rect.isEmpty():
            return

        rect_width = rect.width()
        if rect_width <= 0.0:
            return

        scaled = self.scaled_pixmap(pixmap, rect_width, rect.height(), fill=True)
        if not scaled or scaled.isNull():
            return
        full_width, scaled_height = self.logical_size(scaled)
        if full_width <= 0.0 or scaled_height <= 0.0:
            return

        target_x = rect.x() + (rect.width() - full_width) / 2.0
        target_y = rect.y() + (rect.height() - scaled_height) / 2.0

        had_hint = bool(painter.renderHints() & QPainter.SmoothPixmapTransform)
        painter.save()
        painter.setClipRect(visible_rect, Qt.IntersectClip)
        if not had_hint:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(QPointF(target_x, target_y), scaled)
        if not had_hint:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.restore()

    def _slot_is_visible(self, rect):
        """Return True if a thumbnail slot rect intersects the current viewport."""
        if not isinstance(rect, QRectF):
            return False
        view = QRectF(
            self.w.track_name_width,
            self.w.ruler_height,
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        return view.isValid() and view.intersects(rect)

    def _can_request_thumbnail(self, clip_key, throttle_requests):
        """Throttle requests while trimming to avoid flooding the manager."""
        if not throttle_requests:
            return True
        now = time.monotonic()
        cooldown = max(0.01, float(self._trim_request_cooldown or 0.0))
        last = self._last_thumb_request_time.get(clip_key)
        if last is not None and (now - last) < cooldown:
            return False
        self._last_thumb_request_time[clip_key] = now
        return True

    def _flush_thumbnail_repaint(self):
        if not self._thumb_repaint_pending:
            return
        self._thumb_repaint_pending = False
        self.w.update()

    def _draw_menu_icon(self, painter, inner, x, used_width):
        if not self.menu_pix:
            return used_width
        painter.drawPixmap(
            QPointF(x, inner.y() + self.menu_margin),
            self.menu_pix,
        )
        return max(used_width, float(self.menu_pix.width()))

    def _draw_effect_icons(self, painter, clip, inner, x, right, entries):
        effects = clip.data.get("effects", []) if isinstance(clip.data, dict) else []
        if not isinstance(effects, list) or not effects:
            return x

        available_height = max(0.0, inner.height() - (self.menu_margin * 2))
        base_height = min(16.0, available_height or 0.0)
        badge_height = max(11.0, base_height if base_height > 0.0 else 11.0)
        top = inner.y() + self.menu_margin

        original_font = painter.font()
        badge_font = QFont(original_font)
        if badge_font.pointSizeF() > 0:
            badge_font.setPointSizeF(max(7.0, badge_font.pointSizeF() * 0.8))
        metrics = QFontMetrics(badge_font)

        selected_ids = set()
        if hasattr(self.w, "_selected_effect_ids"):
            selected_ids = self.w._selected_effect_ids()

        for eff in effects:
            available = right - x
            if available <= 4:
                break

            label = (
                eff.get("type")
                or eff.get("effect")
                or eff.get("name")
                or eff.get("class_name")
                or "?"
            )
            letter = label.strip()[0].upper() if isinstance(label, str) and label.strip() else "?"

            text_width = font_metrics_horizontal_advance(metrics, letter)
            badge_width = max(text_width + 6.0, badge_height)
            if badge_width > available:
                break

            rect = QRectF(x, top, badge_width, badge_height)
            color = self.w._effect_color(eff)
            if not isinstance(color, QColor) or not color.isValid():
                color = QColor("#4d7bff")

            effect_id = eff.get("id")
            effect_id_str = str(effect_id) if effect_id is not None else ""
            selected = bool(eff.get("selected")) or (
                effect_id_str and effect_id_str in selected_ids
            )

            fill = QColor(color)
            if selected and fill.isValid():
                fill = fill.lighter(120)
            opacity = 1.0 if selected else 0.7

            border = QColor(223, 223, 223) if selected else QColor(0, 0, 0, 200)
            pen = QPen(border, 1.0)
            pen.setCosmetic(True)

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setOpacity(opacity)
            painter.setBrush(fill)
            painter.setPen(pen)
            radius = min(badge_height / 2.0, 6.0)
            painter.drawRoundedRect(rect, radius, radius)

            painter.setOpacity(1.0)
            painter.setFont(badge_font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect, Qt.AlignCenter, letter)
            painter.restore()

            entries.append(
                {
                    "rect": QRectF(rect),
                    "effect": eff,
                    "selected": selected,
                    "effect_id": effect_id_str,
                }
            )
            x += rect.width() + self.menu_margin

        painter.setFont(original_font)
        return x

    def _draw_clip_text(self, painter, clip, inner, x, right, visible_width=None, icon_entries=None):
        text_width = right - x
        if text_width <= 0:
            return None
        title_raw = str((clip.data.get("title", "") if isinstance(clip.data, dict) else "") or "")
        if text_width <= 4:
            return {"rect": QRectF(x, inner.y(), max(1.0, text_width), max(1.0, inner.height())),
                    "title": title_raw}

        metrics = QFontMetrics(painter.font())
        font_h = float(metrics.height())

        pad_x = 6.0
        pad_y = 2.0
        container_h = font_h + pad_y * 2.0
        icon_size = max(8.0, font_h - 2.0)
        icon_gap = 4.0

        # --- Effect badge sizing ---
        effects = clip.data.get("effects", []) if isinstance(clip.data, dict) else []
        effects = [e for e in effects if isinstance(e, dict)] if isinstance(effects, list) else []

        badge_font = QFont(painter.font())
        if badge_font.pointSizeF() > 0:
            badge_font.setPointSizeF(max(7.0, badge_font.pointSizeF() * 0.8))
        badge_fm = QFontMetrics(badge_font)
        badge_h = max(10.0, min(container_h - pad_y * 2.0, font_h))

        raw_badge_infos = []
        for eff in effects:
            label = (eff.get("type") or eff.get("effect") or eff.get("name") or eff.get("class_name") or "?")
            letter = label.strip()[0].upper() if isinstance(label, str) and label.strip() else "?"
            tw = float(font_metrics_horizontal_advance(badge_fm, letter))
            bw = max(tw + 6.0, badge_h)
            raw_badge_infos.append((eff, letter, bw))

        compact_w = pad_x + icon_size + pad_x
        compact_lod_w = max(compact_w, float(getattr(self, "_min_clip_thumb_width", 0.0) or 0.0))
        visible_clip_w = float(visible_width if visible_width is not None else inner.width())

        # --- LOD: two phases as clip narrows ---
        #
        # Phase 1 (all badges fit + arrow): keep ALL badges, shrink text
        #   [b1 b2] [full title]  [arrow]
        #   [b1 b2] [elided...]   [arrow]
        #   [b1 b2] [T...]        [arrow]
        #   [b1 b2]               [arrow]   ← text gone, badges still there
        #
        # Phase 2 (all badges no longer fit): drop badges from the right, no text
        #   [b1]                  [arrow]
        #                         [arrow]   ← compact
        #                                   ← None (too narrow)

        if raw_badge_infos:
            all_used_w = (
                sum(bw for _, _, bw in raw_badge_infos)
                + self.menu_margin * (len(raw_badge_infos) - 1)
            )
        else:
            all_used_w = 0.0

        # "All badges fit" means all badges + arrow fit with zero text
        all_badges_fit = (
            not raw_badge_infos
            or pad_x + all_used_w + 2.0 * icon_gap + icon_size + pad_x <= text_width
        )

        badge_infos = []
        badges_prefix_w = 0.0
        title_elided = ""
        text_advance = 0.0
        container_w = compact_w
        mode = "compact"

        if all_badges_fit:
            # Phase 1: keep all badges; text fills whatever space remains
            badge_infos = list(raw_badge_infos)
            badges_prefix_w = (all_used_w + icon_gap) if badge_infos else 0.0
            avail_text_w = int(text_width - pad_x * 2.0 - badges_prefix_w - icon_gap - icon_size)
            if avail_text_w >= 4:
                title_elided = metrics.elidedText(title_raw, Qt.ElideRight, avail_text_w)
                if title_elided:
                    text_advance = float(font_metrics_horizontal_advance(metrics, title_elided))

            if badge_infos or text_advance > 0:
                container_w = min(
                    pad_x + badges_prefix_w + text_advance + icon_gap + icon_size + pad_x,
                    text_width,
                )
                container_w = max(container_h, container_w)
                mode = "full"
            elif compact_w <= text_width and compact_lod_w <= visible_clip_w:
                mode = "compact"
            else:
                return None

        else:
            # Phase 2: drop badges from the right until arrow fits, then compact/none
            for n in range(len(raw_badge_infos) - 1, 0, -1):
                used_w = (
                    sum(bw for _, _, bw in raw_badge_infos[:n])
                    + self.menu_margin * (n - 1)
                )
                if pad_x + used_w + 2.0 * icon_gap + icon_size + pad_x <= text_width:
                    badge_infos = list(raw_badge_infos[:n])
                    badges_prefix_w = used_w + icon_gap
                    break

            if badge_infos:
                container_w = min(
                    pad_x + badges_prefix_w + icon_gap + icon_size + pad_x,
                    text_width,
                )
                container_w = max(container_h, container_w)
                mode = "full"
            elif compact_w <= text_width and compact_lod_w <= visible_clip_w:
                mode = "compact"
            else:
                return None

        container_x = inner.x()
        container_y = inner.y()
        container_rect = QRectF(container_x, container_y, container_w, container_h)

        radius = min(4.0, container_rect.width() / 2.0, container_rect.height() / 2.0)
        path = QPainterPath()
        path.addRoundedRect(container_rect, radius, radius)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(path, QColor(0, 0, 0, 140))
        painter.restore()

        # Pre-scale the arrow once for both modes
        arrow_pix = self.dropdown_arrow_pix
        scaled_arrow = None
        arrow_w = arrow_h = 0.0
        if arrow_pix and not arrow_pix.isNull():
            scaled_arrow = self.scaled_pixmap(arrow_pix, icon_size, icon_size)
            if scaled_arrow and not scaled_arrow.isNull():
                arrow_w, arrow_h = self.logical_size(scaled_arrow)

        if mode == "full":
            # Draw effect badges left of the title text
            if badge_infos:
                selected_ids = set()
                if hasattr(self.w, "_selected_effect_ids"):
                    selected_ids = self.w._selected_effect_ids()
                original_font = painter.font()
                badge_x = container_x + pad_x
                badge_y = container_y + (container_h - badge_h) / 2.0
                for eff, letter, bw in badge_infos:
                    badge_rect = QRectF(badge_x, badge_y, bw, badge_h)
                    color = self.w._effect_color(eff)
                    if not isinstance(color, QColor) or not color.isValid():
                        color = QColor("#4d7bff")
                    effect_id = eff.get("id")
                    effect_id_str = str(effect_id) if effect_id is not None else ""
                    selected = bool(eff.get("selected")) or (effect_id_str and effect_id_str in selected_ids)
                    fill = QColor(color)
                    if selected and fill.isValid():
                        fill = fill.lighter(120)
                    opacity = 1.0 if selected else 0.7
                    border = QColor(223, 223, 223) if selected else QColor(0, 0, 0, 200)
                    badge_pen = QPen(border, 1.0)
                    badge_pen.setCosmetic(True)
                    painter.save()
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    painter.setOpacity(opacity)
                    painter.setBrush(fill)
                    painter.setPen(badge_pen)
                    badge_radius = min(badge_h / 2.0, 6.0)
                    painter.drawRoundedRect(badge_rect, badge_radius, badge_radius)
                    painter.setOpacity(1.0)
                    painter.setFont(badge_font)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(badge_rect, Qt.AlignCenter, letter)
                    painter.restore()
                    if icon_entries is not None:
                        icon_entries.append({
                            "rect": QRectF(badge_rect),
                            "effect": eff,
                            "selected": selected,
                            "effect_id": effect_id_str,
                        })
                    badge_x += bw + self.menu_margin
                painter.setFont(original_font)

            # Title text after badges
            flags = Qt.AlignLeft | Qt.AlignVCenter
            text_start_x = container_x + pad_x + badges_prefix_w
            text_draw_rect = QRectF(text_start_x, container_y + pad_y, text_advance, font_h)
            painter.setPen(QColor(0, 0, 0, 120))
            painter.drawText(text_draw_rect.translated(1, 1), flags, title_elided)
            painter.setPen(self.w.theme.clip.font_color)
            painter.drawText(text_draw_rect, flags, title_elided)

            # Arrow after text — only if it clears the container edge by ≥3px
            if scaled_arrow:
                arrow_x = text_start_x + text_advance + icon_gap
                if arrow_x + arrow_w <= container_x + container_w - 3.0:
                    arrow_y = container_y + (container_h - arrow_h) / 2.0
                    painter.drawPixmap(QPointF(arrow_x, arrow_y), scaled_arrow)
        else:
            # Compact: arrow left-aligned, same position as text would be
            if scaled_arrow:
                arrow_x = container_x + pad_x
                arrow_y = container_y + (container_h - arrow_h) / 2.0
                painter.drawPixmap(QPointF(arrow_x, arrow_y), scaled_arrow)

        return {"rect": container_rect, "title": title_raw, "open_menu": True}

    def _draw_waveform(self, painter, clip, inner, segment=None):
        data = clip.data if isinstance(clip.data, dict) else {}
        ui_data = data.get("ui", {}) if isinstance(data, dict) else {}
        audio_data = ui_data.get("audio_data") if isinstance(ui_data, dict) else None
        if not (isinstance(audio_data, list) and len(audio_data) > 1):
            return False

        width = int(inner.width())
        height = int(inner.height())
        if width <= 0 or height <= 0:
            return False

        samples = len(audio_data)
        display = self.w.clip_waveform_window(clip)
        scale_waveform = display.get("scale", False)
        if scale_waveform:
            start_ratio = display.get("source_start_ratio", display.get("start_ratio", 0.0))
            end_ratio = display.get("source_end_ratio", display.get("end_ratio", 1.0))
        else:
            start_ratio = display.get("start_ratio", 0.0)
            end_ratio = display.get("end_ratio", 1.0)

        source_start_ratio = display.get("source_start_ratio", start_ratio)
        source_end_ratio = display.get("source_end_ratio", end_ratio)

        start_float = max(0.0, min(float(samples), float(samples) * start_ratio))
        end_float = max(start_float, min(float(samples), float(samples) * end_ratio))

        span = end_float - start_float
        if span <= 0:
            return False

        if segment and isinstance(segment, dict):
            clip_duration = float(segment.get("clip_duration") or 0.0)
            offset_seconds = float(segment.get("offset_seconds") or 0.0)
            duration_seconds = float(segment.get("duration_seconds") or 0.0)
            total_span = max(float(end_ratio - start_ratio), 0.0)
            source_span = max(float(source_end_ratio - source_start_ratio), 0.0)
            if clip_duration > 0.0 and total_span > 0.0:
                start_frac = max(0.0, min(1.0, offset_seconds / clip_duration))
                end_frac = max(start_frac, min(1.0, (offset_seconds + duration_seconds) / clip_duration))

                adj_start_ratio = start_ratio + total_span * start_frac
                adj_end_ratio = start_ratio + total_span * end_frac
                start_ratio = max(0.0, min(1.0, adj_start_ratio))
                end_ratio = max(start_ratio, min(1.0, adj_end_ratio))

                if source_span > 0.0:
                    adj_source_start = source_start_ratio + source_span * start_frac
                    adj_source_end = source_start_ratio + source_span * end_frac
                    source_start_ratio = max(0.0, min(1.0, adj_source_start))
                    source_end_ratio = max(source_start_ratio, min(1.0, adj_source_end))

                start_float = max(0.0, min(float(samples), float(samples) * start_ratio))
                end_float = max(start_float, min(float(samples), float(samples) * end_ratio))
                span = end_float - start_float
                if span <= 0:
                    return False

        samples_per_pixel = span / float(width)
        if samples_per_pixel <= 0:
            return False

        clip_rect = painter.clipBoundingRect()
        visible_left = 0
        visible_right = width
        if clip_rect.isValid():
            left_offset = int(math.floor(clip_rect.left() - inner.left()))
            right_offset = int(math.ceil(clip_rect.right() - inner.left()))
            visible_left = min(width, max(0, left_offset))
            visible_right = min(width, max(visible_left, right_offset))
        if visible_right <= visible_left:
            return False

        center_y = inner.center().y()
        amplitude_scale = (height * 0.5) * 0.95
        peak_color = self.w.theme.waveform_peak_color
        fill_color = self.w.theme.waveform_color
        if not peak_color.isValid():
            peak_color = QColor(fill_color)
            peak_color.setAlpha(128)
        if not fill_color.isValid():
            fill_color = QColor("#2a82da")

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setClipRect(inner, Qt.IntersectClip)

        peak_heights = []
        avg_heights = []
        x_positions = []

        for column in range(visible_left, visible_right):
            px_start = start_float + column * samples_per_pixel
            px_end = min(end_float, px_start + samples_per_pixel)
            start_idx = max(0, int(math.floor(px_start)))
            end_idx = min(samples, int(math.ceil(px_end)))
            values = []

            if end_idx <= start_idx:
                idx = min(samples - 1, max(0, int(round(px_start)))) if samples else 0
                if samples:
                    sample = audio_data[idx]
                    values.append(abs(sample) if isinstance(sample, (int, float)) else 0.0)
            else:
                step = max(1, int(math.ceil((end_idx - start_idx) / 20.0)))
                idx = start_idx
                while idx < end_idx:
                    sample = audio_data[idx]
                    values.append(abs(sample) if isinstance(sample, (int, float)) else 0.0)
                    idx += step
                last_idx = end_idx - 1
                if values and (last_idx - start_idx) % step != 0:
                    sample = audio_data[last_idx]
                    values.append(abs(sample) if isinstance(sample, (int, float)) else 0.0)

            if not values:
                peak_heights.append(0.0)
                avg_heights.append(0.0)
                x_positions.append(inner.left() + column + 0.5)
                continue

            max_amp = max(values)
            avg_amp = sum(values) / len(values)
            peak_heights.append(max_amp * amplitude_scale)
            avg_heights.append(avg_amp * amplitude_scale)
            x_positions.append(inner.left() + column + 0.5)

        if x_positions:
            peak_path = QPainterPath()
            peak_path.moveTo(x_positions[0], center_y)
            for x_pos, height_px in zip(x_positions, peak_heights):
                peak_path.lineTo(x_pos, center_y - height_px)
            peak_path.lineTo(x_positions[-1], center_y)
            for x_pos, height_px in zip(reversed(x_positions), reversed(peak_heights)):
                peak_path.lineTo(x_pos, center_y + height_px)
            peak_path.closeSubpath()

            fill_path = QPainterPath()
            fill_path.moveTo(x_positions[0], center_y)
            for x_pos, height_px in zip(x_positions, avg_heights):
                fill_path.lineTo(x_pos, center_y - height_px)
            fill_path.lineTo(x_positions[-1], center_y)
            for x_pos, height_px in zip(reversed(x_positions), reversed(avg_heights)):
                fill_path.lineTo(x_pos, center_y + height_px)
            fill_path.closeSubpath()

            if any(height > 0.0 for height in peak_heights):
                painter.fillPath(peak_path, peak_color)
            if any(height > 0.0 for height in avg_heights):
                painter.fillPath(fill_path, fill_color)

        painter.restore()
        return True


    def _draw_clip(self, painter, full_rect, segment_rect, clip, pen, selected):
        style = str(getattr(self.w, "thumbnail_style", "entire") or "").strip().lower()
        pix = None
        shadow_spread = 0.0
        icons = []
        text_entry = None
        preview_drawn = False
        if style in ("entire", "start", "start-end") and self._is_trim_preview_active(clip):
            preview = self._retime_preview_cache.get(getattr(clip, "id", ""))
            pix = preview.get("pix") if isinstance(preview, dict) else None
            blur = float(preview.get("blur", 0.0) or 0.0) if isinstance(preview, dict) else 0.0
            if isinstance(pix, QPixmap) and not pix.isNull():
                shadow_spread = blur
                icons = preview.get("icons") if isinstance(preview.get("icons"), list) else []
                text_entry = preview.get("text_entry") if isinstance(preview.get("text_entry"), dict) else None
                offset_x = segment_rect.x() - blur - self._trim_preview_offset_px(clip)
                offset = QPointF(offset_x, segment_rect.y() - blur)
                painter.save()
                painter.setClipRect(segment_rect, Qt.IntersectClip)
                painter.drawPixmap(offset, pix)
                painter.restore()
                preview_drawn = True
        else:
            result = self._clip_pixmap(full_rect, segment_rect, clip)
            if not result:
                return
            pix, shadow_spread, icons, _, text_entry = result
        includes_start = (segment_rect.left() - full_rect.left()) <= 0.5
        if pix:
            offset = QPointF(segment_rect.x() - shadow_spread, segment_rect.y() - shadow_spread)
            if not preview_drawn:
                painter.drawPixmap(offset, pix)
            if icons:
                for entry in icons:
                    rect_local = entry.get("rect") if isinstance(entry, dict) else None
                    effect = entry.get("effect") if isinstance(entry, dict) else None
                    if not isinstance(rect_local, QRectF):
                        continue
                    global_rect = QRectF(rect_local)
                    global_rect.translate(offset.x(), offset.y())
                    self.w._effect_icon_rects.append(
                        {
                            "rect": global_rect,
                            "clip": clip,
                            "effect": effect,
                            "effect_id": entry.get("effect_id"),
                        }
                    )
            if isinstance(text_entry, dict):
                rect_local = text_entry.get("rect")
                if isinstance(rect_local, QRectF):
                    global_rect = QRectF(rect_local)
                    global_rect.translate(offset.x(), offset.y())
                    self.w._clip_text_rects.append(
                        {
                            "rect": global_rect,
                            "clip": clip,
                            "title": str(text_entry.get("title", "") or ""),
                            "open_menu": bool(text_entry.get("open_menu", False)),
                        }
                    )
        elif includes_start and segment_rect.width() <= 8.0:
            # Keep tiny clips hoverable even when no text is painted.
            bw = float(self.border_width or 0.0)
            self.w._clip_text_rects.append(
                {
                    "rect": QRectF(
                        segment_rect.x() + bw,
                        segment_rect.y() + bw,
                        max(1.0, segment_rect.width() - (bw * 2.0)),
                        max(1.0, segment_rect.height() - (bw * 2.0)),
                    ),
                    "clip": clip,
                    "title": str((clip.data.get("title", "") if isinstance(clip.data, dict) else "") or ""),
                }
            )

        includes_end = (full_rect.right() - segment_rect.right()) <= 0.5

        border_pen = pen if isinstance(pen, QPen) else (self.sel_pen if selected else self.type_pens.get(self._clip_media_type(clip), self.clip_pen))
        self._stroke_visible_border(
            painter,
            segment_rect,
            border_pen,
            includes_start=includes_start,
            includes_end=includes_end,
        )

    def _stroke_visible_border(
        self,
        painter,
        segment_rect,
        pen,
        *,
        includes_start=True,
        includes_end=True,
    ):
        if not isinstance(pen, QPen) or not pen.color().isValid():
            return
        if segment_rect.width() <= 0.0 or segment_rect.height() <= 0.0:
            return

        painter.save()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)

        rect = QRectF(segment_rect)
        width_offset = max(pen.widthF(), 1.0) / 2.0
        max_x = max(rect.width() / 2.0 - 0.1, 0.0)
        max_y = max(rect.height() / 2.0 - 0.1, 0.0)
        offset_x = min(width_offset, max_x)
        offset_y = min(width_offset, max_y)
        rect.adjust(offset_x, offset_y, -offset_x, -offset_y)
        if rect.width() <= 0.0 or rect.height() <= 0.0:
            painter.restore()
            return

        radius = 0.0
        if rect.width() >= 10.0 and rect.height() > 0.0:
            radius = min(self.border_radius, min(rect.width(), rect.height()) / 2.0)

        painter.setRenderHint(QPainter.Antialiasing, True)

        if radius > 0.0:
            if includes_start and includes_end:
                painter.drawRoundedRect(rect, radius, radius)
            elif includes_start or includes_end:
                left = rect.left()
                right = rect.right()
                top = rect.top()
                bottom = rect.bottom()
                path = QPainterPath()

                if includes_start:
                    path.moveTo(left, top + radius)
                    path.quadTo(left, top, left + radius, top)
                else:
                    path.moveTo(left, top)

                if includes_end:
                    path.lineTo(right - radius, top)
                    path.quadTo(right, top, right, top + radius)
                    path.lineTo(right, bottom - radius)
                    path.quadTo(right, bottom, right - radius, bottom)
                else:
                    path.lineTo(right, top)
                    path.lineTo(right, bottom)

                if includes_start:
                    path.lineTo(left + radius, bottom)
                    path.quadTo(left, bottom, left, bottom - radius)
                    path.lineTo(left, top + radius)
                else:
                    path.lineTo(left, bottom)
                    path.lineTo(left, top)

                path.closeSubpath()
                painter.drawPath(path)
            else:
                painter.drawRect(rect)
        else:
            painter.drawRect(rect)
        painter.restore()

    def expire_thumbnail_requests(self, generation):
        """Remove pending thumbnail entries when the viewport changes."""
        stale_keys = [
            key
            for key, pending_generation in self._thumb_pending.items()
            if pending_generation != generation
        ]
        for key in stale_keys:
            self._thumb_pending.pop(key, None)
            self._thumb_regions.pop(key, None)
            self._thumb_missing_logged.discard(key)
        # Edge-slot fallbacks are keyed only by clip/role, so a viewport change
        # can make them point at the wrong first/last visible frame.
        self._slot_fallback_cache.clear()

    def handle_thumbnail_ready(self, clip_id, frame, thumb_path, generation):
        clip_key = str(clip_id or "")
        key = (clip_key, int(frame or 0))
        pending_generation = self._thumb_pending.get(key)

        # Ignore if not from current generation
        if pending_generation != generation:
            return

        self._thumb_pending.pop(key, None)
        rect = self._thumb_regions.pop(key, None)

        pix = QPixmap()
        if thumb_path and os.path.exists(thumb_path):
            pix = QPixmap(thumb_path)

        # Store even empty pixmaps so we don't re-request failed ones
        self.thumb_cache[key] = pix
        self._invalidate_clip_cache_for_clip(clip_key)

        # Safe repaint — defer to avoid active painter issues
        QTimer.singleShot(0, self.w.update)

    def _invalidate_clip_cache_for_clip(self, clip_token):
        """Drop cached clip pixmaps when a thumbnail changes."""
        if not clip_token:
            return
        clip_id = str(clip_token).split(":", 1)[0]
        stale_keys = [
            key
            for key in self.clip_cache.keys()
            if isinstance(key, tuple) and key and str(key[0]) == clip_id
        ]
        for key in stale_keys:
            self.clip_cache.pop(key, None)
