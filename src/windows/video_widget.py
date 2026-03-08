"""
 @file
 @brief This file contains the video preview QWidget (based on a QLabel) and transform controls.
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
import math
import time
import uuid

from PyQt5.QtCore import (
    Qt, QCoreApplication, QMutex, QTimer,
    QPoint, QPointF, QSize, QSizeF, QRect, QRectF,
)
from PyQt5.QtGui import (
    QTransform, QPainter, QIcon, QColor, QPen, QBrush, QCursor, QImage, QRegion
)
from PyQt5.QtWidgets import QSizePolicy, QWidget, QPushButton

import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import updates
from classes import openshot_rc  # noqa
from classes.logger import log
from classes.app import get_app
from classes.query import Clip, Effect


class VideoWidget(QWidget, updates.UpdateInterface):
    """ A QWidget used on the video display widget """

    def _compute_handles_opacity(self, fps_float):
        """
        Opacity based on playhead vs. selected clip(s).
        Intersects => 1.0
        Otherwise => 0.60 fading to 0.25 over 90 seconds.
        """
        import math

        fps = max(float(fps_float), 0.0001)

        # Playhead frame is 1-indexed in UI; snap to grid by rounding
        try:
            cur_f_raw = float(get_app().window.preview_thread.current_frame)
        except Exception:
            cur_f_raw = 1.0
        # Ensure integer frame on the project grid
        cur_f = int(round(cur_f_raw))  # already 1-indexed from preview thread
        if cur_f < 1:
            cur_f = 1

        # Build selected set (clips or single transforming_clip for effects)
        selected = []
        if getattr(self, "transforming_clips", None):
            selected.extend(self.transforming_clips)
        if getattr(self, "transforming_clip", None) and self.transforming_clip not in selected:
            selected.append(self.transforming_clip)

        if not selected:
            return 1.0

        def clip_bounds_frames(c):
            """
            Return (start_frame, end_frame) inclusive, 1-indexed, snapped to project grid:
              start_frame = round(position*fps) + 1
              end_frame   = round((position + (end-start|duration))*fps)
            """
            position = float(c.data.get("position", 0.0))
            start = float(c.data.get("start", 0.0))

            if "end" in c.data and c.data["end"] is not None:
                src_end = float(c.data["end"])
            elif "duration" in c.data and c.data["duration"] is not None:
                src_end = start + float(c.data["duration"])
            else:
                reader = c.data.get("reader", {}) or {}
                dur = reader.get("duration")
                if dur is None:
                    vf = reader.get("video_length")
                    fps_num = (reader.get("fps") or {}).get("num", 0)
                    fps_den = (reader.get("fps") or {}).get("den", 1)
                    r_fps = (float(fps_num) / float(fps_den)) if fps_num and fps_den else 0.0
                    dur = (float(vf) / r_fps) if vf and r_fps else 0.0
                src_end = start + float(dur or 0.0)

            clip_len = max(src_end - start, 0.0)
            cs_sec = position
            ce_sec = position + clip_len
            if ce_sec < cs_sec:
                cs_sec, ce_sec = ce_sec, cs_sec

            # Snap both edges to the project frame grid (round) using your conventions
            sf = int(round(cs_sec * fps)) + 1
            ef = int(round(ce_sec * fps))
            if ef < sf:
                ef = sf
            return sf, ef

        min_dist_frames = None

        for c in selected:
            try:
                sf, ef = clip_bounds_frames(c)
            except Exception as exc:
                log.warning("Failed to compute frame bounds for %s: %s",
                            getattr(c, "id", c), exc, exc_info=True)
                continue

            # Exact inclusive test on snapped frame bounds
            if sf <= cur_f <= ef:
                return 1.0

            # Outside distance in frames to the nearest boundary
            if cur_f < sf:
                d = sf - cur_f
            else:
                d = cur_f - ef
            d = max(int(d), 0)
            if min_dist_frames is None or d < min_dist_frames:
                min_dist_frames = d

        if min_dist_frames is None:
            return 1.0

        # Convert distance to seconds for the fade (0.60 -> 0.25 over 90s)
        BASE, FAR, WINDOW = 0.60, 0.25, 90.0
        min_dist_sec = float(min_dist_frames) / fps
        t = min(min_dist_sec / WINDOW, 1.0)
        return BASE - (BASE - FAR) * t

    def _build_clip_transform(self, x, y, sw, sh, props):
        """Return (QTransform, unpacked props, originScreenPt) for a clip/effect box.
           Order: translate(x,y) → translate(origin) → rotate → shear → untranslate(origin) → scale,
           matching libopenshot's Clip::get_transform so shear/scale share the same pivot and basis.
        """
        sx = max(float(props["scale_x"]["value"]), 0.001)
        sy = max(float(props["scale_y"]["value"]), 0.001)
        rot = float(props["rotation"]["value"])
        shx = float(props["shear_x"]["value"])
        shy = float(props["shear_y"]["value"])
        ox = float(props["origin_x"]["value"])
        oy = float(props["origin_y"]["value"])

        # Clip-local pivot (pre-scale) and its translated amount once clip scale is applied.
        local_origin_x = sw * ox
        local_origin_y = sh * oy
        pivot_tx = local_origin_x * sx
        pivot_ty = local_origin_y * sy

        t = QTransform()
        if x or y:
            t.translate(x, y)
        if pivot_tx or pivot_ty:
            t.translate(pivot_tx, pivot_ty)
        if rot:
            t.rotate(rot)
        if shx or shy:
            t.shear(shx, shy)
        if pivot_tx or pivot_ty:
            t.translate(-pivot_tx, -pivot_ty)
        if sx or sy:
            t.scale(sx, sy)

        origin_screen = t.map(QPointF(local_origin_x, local_origin_y))
        return t, (sx, sy, rot, shx, shy, ox, oy), origin_screen

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        # Handle change
        if action and (len(action.key) >= 1 and action.key[0] in [
                "display_ratio", "pixel_ratio"
                ] or action.type in ["load"]):
            # Update display ratio (if found)
            if action.type == "load" and action.values.get("display_ratio"):
                self.aspect_ratio = openshot.Fraction(
                    action.values.get("display_ratio", {}).get("num", 16),
                    action.values.get("display_ratio", {}).get("den", 9))
                log.info(
                    "Load: Set video widget display aspect ratio to: %s",
                    self.aspect_ratio.ToFloat())
            elif action.key and action.key[0] == "display_ratio":
                self.aspect_ratio = openshot.Fraction(
                    action.values.get("num", 16),
                    action.values.get("den", 9))
                log.info(
                    "Update: Set video widget display aspect ratio to: %s",
                    self.aspect_ratio.ToFloat())

            # Update pixel ratio (if found)
            if action.type == "load" and action.values.get("pixel_ratio"):
                self.pixel_ratio = openshot.Fraction(
                    action.values.get("pixel_ratio").get("num", 1),
                    action.values.get("pixel_ratio").get("den", 1))
                log.info(
                    "Set video widget pixel aspect ratio to: %s",
                    self.pixel_ratio.ToFloat())
            elif action.key and action.key[0] == "pixel_ratio":
                self.pixel_ratio = openshot.Fraction(
                    action.values.get("num", 1),
                    action.values.get("den", 1))
                log.info(
                    "Update: Set video widget pixel aspect ratio to: %s",
                    self.pixel_ratio.ToFloat())

    def clearTransformState(self):
        """Clear all transform-related state to avoid using invalid clip/effect objects"""
        self.transforming_clip = None
        self.transforming_clips.clear()
        self.transforming_clip_objects.clear()
        self.transforming_effect = None
        self.transforming_clip_object = None
        self.transforming_effect_object = None
        self.transaction_id = None
        self.transform_mode = None
        self.transform = None
        self.clipBounds = None
        self.originHandle = None
        self.original_effect_data = None
        self.hover_transform_mode = None
        self.hover_cursor = Qt.ArrowCursor
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def drawTransformHandler(
        self, painter, sx, sy, source_width, source_height,
        origin_x, origin_y,
        x1=None, y1=None, x2=None, y2=None, rotation=None,
        skip_origin=False
    ):
        # Corner and origin glyph on-screen sizes
        cs = self.cs
        os = 12.0

        csx = cs / sx
        csy = cs / sy

        # Accept 0.0 values; only treat None as missing
        has_crop_box = (x1 is not None and y1 is not None and x2 is not None and y2 is not None)

        # Build bounds in local (clip) coords
        if has_crop_box:
            self.clipBounds = QRectF(
                QPointF(x1 * source_width, y1 * source_height),
                QPointF(x2 * source_width, y2 * source_height)
            )
            # Corner handles
            self.topLeftHandle = QRectF(
                x1 * source_width - (csx / 2.0),
                y1 * source_height - (csy / 2.0),
                csx, csy)
            self.topRightHandle = QRectF(
                x2 * source_width - (csx / 2.0),
                y1 * source_height - (csy / 2.0),
                csx, csy)
            self.bottomLeftHandle = QRectF(
                x1 * source_width - (csx / 2.0),
                y2 * source_height - (csy / 2.0),
                csx, csy)
            self.bottomRightHandle = QRectF(
                x2 * source_width - (csx / 2.0),
                y2 * source_height - (csy / 2.0),
                csx, csy)
        else:
            self.clipBounds = QRectF(QPointF(0.0, 0.0), QPointF(source_width, source_height))
            self.topLeftHandle = QRectF(-csx / 2.0, -csy / 2.0, csx, csy)
            self.topRightHandle = QRectF(source_width - csx / 2.0, -csy / 2.0, csx, csy)
            self.bottomLeftHandle = QRectF(-csx / 2.0, source_height - csy / 2.0, csx, csy)
            self.bottomRightHandle = QRectF(source_width - csx / 2.0, source_height - csy / 2.0, csx, csy)

        # Side handles
        if has_crop_box:
            self.topHandle = QRectF(
                ((x1 + x2) * source_width - csx) / 2.0,
                (y1 * source_height) - csy / 2.0,
                csx, csy)
            self.bottomHandle = QRectF(
                ((x1 + x2) * source_width - csx) / 2.0,
                (y2 * source_height) - csy / 2.0,
                csx, csy)
            self.leftHandle = QRectF(
                (x1 * source_width) - csx / 2.0,
                ((y1 + y2) * source_height - csy) / 2.0,
                csx, csy)
            self.rightHandle = QRectF(
                (x2 * source_width) - csx / 2.0,
                ((y1 + y2) * source_height - csy) / 2.0,
                csx, csy)
        else:
            self.topHandle = QRectF((source_width - csx) / 2.0, -csy / 2.0, csx, csy)
            self.bottomHandle = QRectF((source_width - csx) / 2.0, source_height - (csy / 2.0), csx, csy)
            self.leftHandle = QRectF(-csx / 2.0, (source_height - csy) / 2.0, csx, csy)
            self.rightHandle = QRectF(source_width - (csx / 2.0), (source_height - csy) / 2.0, csx, csy)

        # Shear regions span the visible bounds
        self.topShearHandle = QRectF(self.topLeftHandle.x(), self.topLeftHandle.y(), self.clipBounds.width(),
                                     self.topLeftHandle.height())
        self.leftShearHandle = QRectF(self.topLeftHandle.x(), self.topLeftHandle.y(), self.topLeftHandle.width(),
                                      self.clipBounds.height())
        self.rightShearHandle = QRectF(self.topRightHandle.x(), self.topRightHandle.y(), self.topRightHandle.width(),
                                       self.clipBounds.height())
        self.bottomShearHandle = QRectF(self.bottomLeftHandle.x(), self.bottomLeftHandle.y(), self.clipBounds.width(),
                                        self.topLeftHandle.height())

        # Pen color with global opacity applied
        color_hex = "#d3d3d3" if skip_origin else "#53a0ed"
        pen_color = QColor(color_hex)
        pen_color.setAlphaF(getattr(self, "handle_opacity", 1.0))
        pen = QPen(QBrush(pen_color), 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)

        # Draw outline + handles
        painter.drawRects([
            self.topLeftHandle, self.topRightHandle,
            self.bottomLeftHandle, self.bottomRightHandle,
            self.topHandle, self.bottomHandle,
            self.leftHandle, self.rightHandle,
            self.clipBounds,
        ])

        # Origin glyph (hidden in crop mode; crop draws its own)
        if not skip_origin:
            origin_rect = QRectF(
                source_width * origin_x - (os / sx),
                source_height * origin_y - (os / sy),
                (os / sx) * 2.0, (os / sy) * 2.0
            )
            self.centerHandle = origin_rect
            painter.drawEllipse(origin_rect)

            center = origin_rect.center()
            halfW = QPointF(origin_rect.width() * 0.75, 0)
            halfH = QPointF(0, origin_rect.height() * 0.75)
            painter.drawLines(center - halfW, center + halfW, center - halfH, center + halfH)

        painter.resetTransform()

    def update_title(self):
        """Update the widget title"""
        # Translate object
        _ = get_app()._tr
        rect = self.centeredViewport(self.width(), self.height())
        scale = self.devicePixelRatioF()

        # Display the playback speed in widget title
        speed = 0.0
        mode = self.win.preview_thread.player.Mode()
        if mode != openshot.PLAYBACK_PAUSED:
            speed = self.win.preview_thread.player.Speed()

        # Find parent dockWidget (if any)
        dock = None
        if self.parent() and self.parent().parent():
            # TODO: Find a better way to find the QDockWidget parent (if any)
            dock = self.parent().parent()
        else:
            # Not a dock widget, ignore title
            return

        transform_label = ""
        if (self.transforming_effect and self.transforming_effect_object and
                getattr(self.transforming_effect_object.info, 'class_name', '') == 'Crop'):
            transform_label = _("Crop")
        elif self.transforming_effect or self.transforming_clips:
            transform_label = _("Transform")
        elif self.region_enabled:
            transform_label = _("Selection")

        base_title = _("Video Preview")
        if transform_label:
            base_title += f" ({transform_label})"

        if self.settings.get("preview-fps"):
            dock.setWindowTitle(base_title + _(" (Speed: %(speed)sx, Paint: %(pfps)s FPS, Render: %(rfps)s FPS, %(width)sx%(height)s)")
                                % {"speed": speed,
                                   "pfps": self.paint_fps,
                                   "rfps": self.present_fps,
                                   "width": rect.width() * scale,
                                   "height": rect.height() * scale})
        else:
            # Restore window title
            if not speed in [1, 0, -1]:
                dock.setWindowTitle(base_title + f" ({speed}x)")
            else:
                dock.setWindowTitle(base_title)

    def paintEvent(self, event, *args):
        """ Custom paint event """
        event.accept()
        self.mutex.lock()

        # Ensure screen-space handle attribute exists and reset each paint
        if not hasattr(self, "cropOriginHandleScreen"):
            self.cropOriginHandleScreen = None
        else:
            self.cropOriginHandleScreen = None

        # Calculate "paint" FPS (and update widget title)
        current_sec = time.localtime(time.time()).tm_sec
        if current_sec != self.paint_fps_sec:
            self.paint_fps = self.paint_fps_counter
            self.update_title()
            self.paint_fps_sec = current_sec
            self.paint_fps_counter = 1
        else:
            self.paint_fps_counter += 1

        # Paint custom frame image on QWidget
        painter = QPainter(self)
        try:
            painter.setRenderHints(
                QPainter.Antialiasing
                | QPainter.SmoothPixmapTransform
                | QPainter.TextAntialiasing,
                True)

            # Background
            bg_color = self.palette().color(self.backgroundRole())
            painter.fillRect(event.rect(), bg_color)

            # Viewport and frame
            viewport = self.centeredViewport(self.width(), self.height())
            if self.current_image:
                pix_size = self.current_image.size()
                pix_size.scale(event.rect().size(), Qt.KeepAspectRatio)
                self.curr_frame_size = pix_size

                scale = self.devicePixelRatioF()
                scaled_img = self.current_image.scaled(
                    pix_size * scale,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                painter.drawImage(viewport, scaled_img)

            # Prep for transform UI
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Compute opacity for all transform UI this frame
            self.handle_opacity = self._compute_handles_opacity(fps_float)

            default_props = {
                "scale_x": {"value": 1.0},
                "scale_y": {"value": 1.0},
                "rotation": {"value": 0.0},
                "shear_x": {"value": 0.0},
                "shear_y": {"value": 0.0},
                "origin_x": {"value": 0.5},
                "origin_y": {"value": 0.5},
            }

            # Collect selected clips and build union rect
            clip_pairs = []
            if self.transforming_clips and self.transforming_clip_objects:
                clip_pairs = list(zip(self.transforming_clips, self.transforming_clip_objects))

            union_rect = None
            first_props = None
            for clip, obj in clip_pairs:
                frame = self._get_clip_frame_number(clip, fps_float)
                rect, props = self._clip_rect(clip, obj, viewport, frame)
                if union_rect is None:
                    union_rect = rect
                    first_props = props
                else:
                    union_rect = union_rect.united(rect)

            crop_params = None
            crop_norm = None

            # Effect overlays
            if (self.transforming_effect
                and self.transforming_effect_object
                and self.transforming_clip
                and self.transforming_clip_object):
                clip = self.transforming_clip
                obj = self.transforming_clip_object
                frame = self._get_clip_frame_number(clip, fps_float)
                clip_rect, clip_props = self._clip_rect(clip, obj, viewport, frame)

                eff_info = self.transforming_effect_object.info
                raw_eff = json.loads(self.transforming_effect_object.PropertiesJSON(frame))

                if getattr(eff_info, 'has_tracked_object', False):
                    objs = raw_eff.get("objects", {}) or {}
                    if objs:
                        oid = next(iter(objs))
                        eprops = objs[oid]
                        if eprops.get("visible", {}).get("value") == 1:
                            x1_abs = clip_rect.x() + eprops["x1"]["value"] * clip_rect.width()
                            y1_abs = clip_rect.y() + eprops["y1"]["value"] * clip_rect.height()
                            x2_abs = clip_rect.x() + eprops["x2"]["value"] * clip_rect.width()
                            y2_abs = clip_rect.y() + eprops["y2"]["value"] * clip_rect.height()
                            effect_rect = QRectF(QPointF(x1_abs, y1_abs), QPointF(x2_abs, y2_abs))
                            union_rect = effect_rect if union_rect is None else union_rect.united(effect_rect)
                            first_props = first_props or default_props

                elif getattr(eff_info, 'class_name', '') == 'Crop':
                    effect_id = None
                    if hasattr(self.transforming_effect_object, 'Id'):
                        effect_id = self.transforming_effect_object.Id()

                    left = raw_eff.get('left', {}).get('value', 0.0)
                    top = raw_eff.get('top', {}).get('value', 0.0)
                    right = raw_eff.get('right', {}).get('value', 0.0)
                    bottom = raw_eff.get('bottom', {}).get('value', 0.0)
                    resize = raw_eff.get('resize', {}).get('value', 0.0)
                    x_off = raw_eff.get('x', {}).get('value', 0.0)
                    y_off = raw_eff.get('y', {}).get('value', 0.0)

                    base_w, base_h = self._clip_source_dimensions(
                        clip, obj, frame, skip_effect_id=effect_id)

                    width = clip_rect.width()
                    height = clip_rect.height()
                    cw = max(1.0 - left - right, 0.0)
                    ch = max(1.0 - top - bottom, 0.0)

                    if resize:
                        crop_rect_local = self._crop_resize_rect(
                            base_w, base_h, left, top, right, bottom, x_off, y_off)
                        frame_w = max(crop_rect_local.width(), 0.0001)
                        frame_h = max(crop_rect_local.height(), 0.0001)
                        union_rect = self._clip_display_rect(
                            frame_w, frame_h, clip, clip_props, viewport)
                        crop_norm = (0.0, 0.0, 1.0, 1.0)
                    else:
                        crop_w = width * cw
                        crop_h = height * ch
                        x1_abs = clip_rect.x() + left * width
                        y1_abs = clip_rect.y() + top * height
                        dim_w = max(width, 0.0001)
                        dim_h = max(height, 0.0001)
                        x1 = (x1_abs - clip_rect.x()) / dim_w
                        y1 = (y1_abs - clip_rect.y()) / dim_h
                        x2 = x1 + (crop_w / dim_w)
                        y2 = y1 + (crop_h / dim_h)
                        crop_norm = (x1, y1, x2, y2)
                        union_rect = clip_rect
                        frame_w = max(base_w, 0.0001)
                        frame_h = max(base_h, 0.0001)

                    first_props = clip_props
                    crop_params = (left, top, right, bottom, resize, x_off, y_off, frame_w, frame_h)

            # Draw handler(s)
            if union_rect and first_props:
                x = union_rect.x()
                y = union_rect.y()
                sw = union_rect.width()
                sh = union_rect.height()

                # Transform: translate → translate(origin) → rotate → shear → scale → untranslate(origin)
                self.transform, unpacked, origin_screen = self._build_clip_transform(
                    x, y, sw, sh, first_props
                )
                sx, sy, _, _, _, ox, oy = unpacked

                # On-screen pivot
                self.originHandle = origin_screen

                # Draw the local-space handlers (blue or gray) with global opacity
                painter.setTransform(self.transform)
                is_crop = crop_params is not None
                if is_crop and crop_norm:
                    x1, y1, x2, y2 = crop_norm
                else:
                    x1 = y1 = x2 = y2 = None
                self.drawTransformHandler(
                    painter, sx, sy, sw, sh, ox, oy,
                    x1, y1, x2, y2, skip_origin=is_crop
                )

                # Crop origin glyph (screen space; constant size; with opacity)
                if is_crop:
                    left, top, right, bottom, resize, crop_x, crop_y, frame_w, frame_h = crop_params

                    base_w = max(frame_w, 0.0001)
                    base_h = max(frame_h, 0.0001)

                    # Map clip-space to screen-space
                    sx_factor = sw / base_w
                    sy_factor = sh / base_h

                    # For origin (x,y) we want full-frame units in both modes
                    origin_w = base_w * sx_factor
                    origin_h = base_h * sy_factor

                    # The crop origin represents an offset from the center of the clip's image
                    local_center = QPointF(sw / 2.0, sh / 2.0)
                    local_origin = QPointF(
                        local_center.x() - (crop_x * origin_w),
                        local_center.y() - (crop_y * origin_h)
                    )

                    screen_pt = self.transform.map(local_origin)
                    painter.resetTransform()

                    os = 12.0  # fixed on-screen radius
                    color = QColor("#d3d3d3")
                    color.setAlphaF(self.handle_opacity)
                    pen = QPen(QBrush(color), 1.5)
                    pen.setCosmetic(True)
                    painter.setPen(pen)

                    self.cropOriginHandleScreen = QRectF(
                        screen_pt.x() - os, screen_pt.y() - os, os * 2.0, os * 2.0
                    )
                    painter.drawEllipse(self.cropOriginHandleScreen)

                    c = self.cropOriginHandleScreen.center()
                    cross_w = self.cropOriginHandleScreen.width() * 0.75
                    cross_h = self.cropOriginHandleScreen.height() * 0.75
                    halfW = QPointF(cross_w / 2.0, 0)
                    halfH = QPointF(0, cross_h / 2.0)
                    painter.drawLines(c - halfW, c + halfW, c - halfH, c + halfH)

            # Region selection UI (also uses global opacity)
            if self.region_enabled:
                self.region_transform = QTransform()
                rx = viewport.x()
                ry = viewport.y()
                if rx or ry:
                    self.region_transform.translate(rx, ry)
                if self.zoom:
                    self.region_transform.scale(self.zoom, self.zoom)

                self.region_transform_inverted = self.region_transform.inverted()[0]
                painter.setTransform(self.region_transform)

                cs = self.cs
                if self.regionTopLeftHandle and self.regionBottomRightHandle:
                    color = QColor("#53a0ed")
                    color.setAlphaF(self.handle_opacity)
                    pen = QPen(QBrush(color), 1.5)
                    pen.setCosmetic(True)
                    painter.setPen(pen)
                    painter.drawRect(QRectF(
                        self.regionTopLeftHandle.x() - (cs / 2.0 / self.zoom),
                        self.regionTopLeftHandle.y() - (cs / 2.0 / self.zoom),
                        self.regionTopLeftHandle.width() / self.zoom,
                        self.regionTopLeftHandle.height() / self.zoom))
                    painter.drawRect(QRectF(
                        self.regionBottomRightHandle.x() - (cs / 2.0 / self.zoom),
                        self.regionBottomRightHandle.y() - (cs / 2.0 / self.zoom),
                        self.regionBottomRightHandle.width() / self.zoom,
                        self.regionBottomRightHandle.height() / self.zoom))
                    region_rect = QRectF(
                        self.regionTopLeftHandle.x(),
                        self.regionTopLeftHandle.y(),
                        self.regionBottomRightHandle.x() - self.regionTopLeftHandle.x(),
                        self.regionBottomRightHandle.y() - self.regionTopLeftHandle.y())
                    painter.drawRect(region_rect)

                painter.resetTransform()

        finally:
            if painter.isActive():
                painter.end()
            self.mutex.unlock()

    def centeredViewport(self, width, height):
        """ Calculate size of viewport to maintain aspect ratio """

        window_size = QSizeF(width, height)
        window_rect = QRectF(QPointF(0, 0), window_size)

        aspectRatio = self.aspect_ratio.ToFloat() * self.pixel_ratio.ToFloat()
        viewport_size = QSizeF(aspectRatio, 1).scaled(
                            window_size, Qt.KeepAspectRatio
                        ) * self.zoom
        viewport_rect = QRectF(QPointF(0, 0), viewport_size)
        viewport_rect.moveCenter(window_rect.center())
        # Always round up to next whole integer value
        return viewport_rect.toAlignedRect()

    def present(self, image, *args):
        """ Present the current frame """

        # Calculate "render" / "present" FPS
        current_sec = time.localtime(time.time()).tm_sec
        if current_sec != self.present_fps_sec:
            self.present_fps = self.present_fps_counter
            self.present_fps_sec = current_sec
            self.present_fps_counter = 1
        else:
            self.present_fps_counter += 1

        # Get frame's QImage from libopenshot
        self.current_image = image

        # Force repaint on this widget
        self.repaint()

    def connectSignals(self, renderer):
        """ Connect signals to renderer """
        renderer.present.connect(self.present)

    def mousePressEvent(self, event):
        """Capture mouse press event on video preview window"""
        event.accept()
        self.mouse_pressed = True
        self.mouse_dragging = False
        self.mouse_position = event.pos()
        self.transform_mode = self.hover_transform_mode
        self.setCursor(self.hover_cursor)

        # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
        get_app().updates.ignore_history = True

        if self.transforming_clips or self.transforming_effect:
            self.transaction_id = str(uuid.uuid4())
            self.original_clip_data_map = {c.id: json.loads(json.dumps(c.data)) for c in self.transforming_clips} if self.transforming_clips else {}
            self.original_effect_data = json.loads(json.dumps(self.transforming_effect.data)) if self.transforming_effect else None
            get_app().updates.transaction_id = self.transaction_id
        else:
            self.transaction_id = None
            self.original_clip_data_map = {}
            self.original_effect_data = None

        # Disable video caching during drag operation (for performance reasons)
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
        log.debug('mousePressEvent: Stop caching frames on timeline')

    def mouseReleaseEvent(self, event):
        event.accept()
        """Capture mouse release event on video preview window"""
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.transform_mode = None
        self.region_mode = None

        # Save region image data (as QImage)
        # This can be used other widgets to display the selected region
        if self.region_enabled:
            # Get region coordinates
            region_rect = QRectF(
                self.regionTopLeftHandle.x(),
                self.regionTopLeftHandle.y(),
                self.regionBottomRightHandle.x() - self.regionTopLeftHandle.x(),
                self.regionBottomRightHandle.y() - self.regionTopLeftHandle.y()
            ).normalized()

            # Map region (due to zooming)
            mapped_region_rect = self.region_transform.mapToPolygon(
                region_rect.toRect()).boundingRect()

            # Render a scaled version of the region (as a QImage)
            # TODO: Grab higher quality pixmap from the QWidget, as this method seems to be 1/2 resolution
            # of the original QWidget video element.
            scale = 3.0

            # Map rect to transform (for scaling video elements)
            mapped_region_rect = QRect(
                mapped_region_rect.x(),
                mapped_region_rect.y(),
                int(mapped_region_rect.width() * scale),
                int(mapped_region_rect.height() * scale))

            # Render QWidget onto scaled QImage
            self.region_qimage = QImage(
                mapped_region_rect.size(), QImage.Format_RGBA8888)
            region_painter = QPainter(self.region_qimage)
            region_painter.setRenderHints(
                QPainter.Antialiasing
                | QPainter.SmoothPixmapTransform
                | QPainter.TextAntialiasing,
                True)
            region_painter.scale(scale, scale)
            self.render(
                region_painter, QPoint(0, 0),
                QRegion(mapped_region_rect, QRegion.Rectangle))
            region_painter.end()

        # Inform UpdateManager to accept updates, and only store our final update
        get_app().updates.ignore_history = False

        # Enable video caching again
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True
        log.debug('mouseReleaseEvent: Start caching frames on timeline')

        # Record history for all transformed clips
        for clip in self.transforming_clips:
            original = self.original_clip_data_map.get(clip.id)
            if original:
                get_app().updates.ignore_history = True
                get_app().updates.transaction_id = self.transaction_id
                clip.save()
                get_app().updates.apply_last_action_to_history(original)
                get_app().updates.ignore_history = False

        if self.transforming_effect and self.original_effect_data:
            get_app().updates.ignore_history = True
            get_app().updates.transaction_id = self.transaction_id
            self.transforming_effect.save()
            get_app().updates.apply_last_action_to_history(self.original_effect_data)
            get_app().updates.ignore_history = False

        # Clear transaction and data
        get_app().updates.transaction_id = None
        get_app().updates.ignore_history = False
        self.original_clip_data = None
        self.original_clip_data_map = {}
        self.original_effect_data = None

    def rotateCursor(self, pixmap, rotation, shear_x, shear_y):
        """Rotate cursor based on the current transform"""
        rotated_pixmap = pixmap.transformed(
            QTransform().rotate(rotation).shear(shear_x, shear_y).scale(0.8, 0.8),
            Qt.SmoothTransformation)
        return QCursor(rotated_pixmap)

    def checkTransformMode(self, rotation, shear_x, shear_y, event):
        # Make sure attr exists even if old sessions
        if not hasattr(self, "cropOriginHandleScreen"):
            self.cropOriginHandleScreen = None

        if not self.transform:
            self.hover_cursor = Qt.ArrowCursor
            self.hover_transform_mode = None
            self.setCursor(self.hover_cursor)
            if self.mouse_dragging:
                self.transform_mode = None
            return

        # Special-case: Crop effect origin is in SCREEN SPACE
        if (self.transforming_effect and self.transforming_effect_object and
            getattr(self.transforming_effect_object.info, 'class_name', '') == 'Crop'):
            # Test the screen-space rect first
            if self.cropOriginHandleScreen and self.cropOriginHandleScreen.contains(event.pos()):
                cursor = self.rotateCursor(self.cursors.get('hand'), rotation, shear_x, shear_y)
                self.hover_cursor = cursor
                self.hover_transform_mode = 'origin'
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'origin'
                self.setCursor(cursor)
                return

        handle_uis = [
            {"handle": self.centerHandle, "mode": 'origin', "cursor": 'hand'},
            {"handle": self.topRightHandle, "mode": 'scale_top_right', "cursor": 'resize_bdiag'},
            {"handle": self.topHandle, "mode": 'scale_top', "cursor": 'resize_y'},
            {"handle": self.topLeftHandle, "mode": 'scale_top_left', "cursor": 'resize_fdiag'},
            {"handle": self.leftHandle, "mode": 'scale_left', "cursor": 'resize_x'},
            {"handle": self.rightHandle, "mode": 'scale_right', "cursor": 'resize_x'},
            {"handle": self.bottomLeftHandle, "mode": 'scale_bottom_left', "cursor": 'resize_bdiag'},
            {"handle": self.bottomHandle, "mode": 'scale_bottom', "cursor": 'resize_y'},
            {"handle": self.bottomRightHandle, "mode": 'scale_bottom_right', "cursor": 'resize_fdiag'},
            {"handle": self.topShearHandle, "mode": 'shear_top', "cursor": 'shear_x'},
            {"handle": self.leftShearHandle, "mode": 'shear_left', "cursor": 'shear_y'},
            {"handle": self.rightShearHandle, "mode": 'shear_right', "cursor": 'shear_y'},
            {"handle": self.bottomShearHandle, "mode": 'shear_bottom', "cursor": 'shear_x'},
        ]
        non_handle_uis = {
            "region": self.clipBounds,
            "inside": {"mode": 'location', "cursor": 'move'},
            "outside": {"mode": 'rotation', "cursor": "rotate"},
        }

        if (self.transforming_effect and self.transforming_effect_object and
            getattr(self.transforming_effect_object.info, 'class_name', '') == 'Crop'):
            handle_uis = [h for h in handle_uis if not h["mode"].startswith('shear_') and h["mode"] != 'origin']
            non_handle_uis["outside"] = {"mode": None, "cursor": None}

        # Ignore any handles that were not drawn
        handle_uis = [h for h in handle_uis if h["handle"]]

        # Mouse over resize button (and not currently dragging)
        if (not self.mouse_dragging
            and self.resize_button.isVisible()
            and self.resize_button.rect().contains(event.pos())
        ):
            self.hover_cursor = Qt.ArrowCursor
            self.hover_transform_mode = None
            self.setCursor(self.hover_cursor)
            if self.mouse_dragging:
                self.transform_mode = None
            return

        # If mouse is over a LOCAL handle, set corresponding pointer/mode
        for h in handle_uis:
            # Note: the crop-origin case was handled in screen space above
            if self.transform.mapToPolygon(h["handle"].toRect()).containsPoint(event.pos(), Qt.OddEvenFill):
                if self.transform_mode and self.transform_mode != h["mode"]:
                    continue
                cursor = self.rotateCursor(self.cursors.get(h["cursor"]), rotation, shear_x, shear_y)
                self.hover_cursor = cursor
                self.hover_transform_mode = h["mode"]
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = h["mode"]
                self.setCursor(cursor)
                return

        # If not over any handles, determine inside/outside clip rectangle
        r = non_handle_uis.get("region")
        if self.transform.mapToPolygon(r.toRect()).containsPoint(event.pos(), Qt.OddEvenFill):
            nh = non_handle_uis.get("inside", {})
        else:
            nh = non_handle_uis.get("outside", {})
        cursor_name = nh.get("cursor")
        if cursor_name:
            cursor = self.rotateCursor(self.cursors.get(cursor_name), rotation, shear_x, shear_y)
        else:
            cursor = Qt.ArrowCursor
        self.hover_cursor = cursor
        self.hover_transform_mode = nh.get("mode")
        if self.mouse_dragging and not self.transform_mode:
            self.transform_mode = self.hover_transform_mode
        if not self.transform_mode or self.transform_mode == self.hover_transform_mode:
            self.setCursor(cursor)

    def mouseMoveEvent(self, event):
        """Capture mouse events on video preview window """
        self.mutex.lock()
        event.accept()

        if self.mouse_pressed:
            self.mouse_dragging = True

        if self.transforming_clip and (not self.transforming_effect):
            # Modify clip transform properties (x, y, height, width, rotation, shear)
            # Get framerate
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Determine frame # of clip (absolute frame, accounting for clip start trim)
            clip_frame_number = self._get_clip_frame_number(
                self.transforming_clip, fps_float)

            # Get properties of clip at current frame
            raw_properties = json.loads(self.transforming_clip_object.PropertiesJSON(clip_frame_number))

            # Get current rotation and skew (used for cursor rotation)
            rotation = raw_properties.get('rotation').get('value')
            shear_x = raw_properties.get('shear_x').get('value')
            shear_y = raw_properties.get('shear_y').get('value')

            # Get the rect where the video is actually drawn (without the black borders, etc...)
            viewport_rect = self.centeredViewport(self.width(), self.height())

            # Make back-up of clip data
            if self.mouse_dragging and not self.transform_mode and self.transforming_clip:
                if self.transforming_clip.id not in self.original_clip_data_map:
                    self.original_clip_data_map[self.transforming_clip.id] = json.loads(json.dumps(self.transforming_clip.data))

            self.checkTransformMode(rotation, shear_x, shear_y, event)

            # Transform clip object
            if self.transform_mode:

                x_motion = event.pos().x() - self.mouse_position.x()
                y_motion = event.pos().y() - self.mouse_position.y()

                # For all interactions except rotation and location, adjust the motion vector
                # to account for the clip's current rotation.
                if self.transform_mode not in ['rotation', 'location']:
                    import math
                    current_rotation = raw_properties.get('rotation').get('value')
                    if abs(current_rotation) > 0.001:
                        rad = math.radians(current_rotation)
                        x_motion_unrotated = math.cos(rad) * x_motion + math.sin(rad) * y_motion
                        y_motion_unrotated = -math.sin(rad) * x_motion + math.cos(rad) * y_motion
                        x_motion, y_motion = x_motion_unrotated, y_motion_unrotated

                if self.transform_mode == 'origin':
                    # Get current keyframe value
                    origin_x = raw_properties.get('origin_x').get('value')
                    origin_y = raw_properties.get('origin_y').get('value')
                    scale_x = raw_properties.get('scale_x').get('value')
                    scale_y = raw_properties.get('scale_y').get('value')

                    # Calculate new location coordinates
                    origin_x += x_motion / (self.clipBounds.width() * scale_x)
                    origin_y += y_motion / (self.clipBounds.height() * scale_y)

                    # Constrain to clip
                    if origin_x < 0.0:
                        origin_x = 0.0
                    if origin_x > 1.0:
                        origin_x = 1.0
                    if origin_y < 0.0:
                        origin_y = 0.0
                    if origin_y > 1.0:
                        origin_y = 1.0
                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'origin_x', origin_x,
                        refresh=False)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'origin_y', origin_y)
                    self._apply_delta_to_clips('origin_x', origin_x - raw_properties.get('origin_x').get('value'), fps_float)
                    self._apply_delta_to_clips('origin_y', origin_y - raw_properties.get('origin_y').get('value'), fps_float)

                elif self.transform_mode == 'location':
                    # Get current keyframe value
                    location_x = raw_properties.get('location_x').get('value')
                    location_y = raw_properties.get('location_y').get('value')

                    # Calculate new location coordinates
                    location_x += x_motion / viewport_rect.width()
                    location_y += y_motion / viewport_rect.height()

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'location_x', location_x,
                        refresh=False)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'location_y', location_y)
                    self._apply_delta_to_clips('location_x', location_x - raw_properties.get('location_x').get('value'), fps_float)
                    self._apply_delta_to_clips('location_y', location_y - raw_properties.get('location_y').get('value'), fps_float)

                elif self.transform_mode == 'shear_top':
                    # Get current keyframe shear value
                    shear_x = raw_properties.get('shear_x').get('value')
                    scale_x = raw_properties.get('scale_x').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (self.clipBounds.width() / self.clipBounds.height()) * 2.0
                    shear_x -= x_motion / ((self.clipBounds.width() * scale_x) / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'shear_x', shear_x)
                    self._apply_delta_to_clips('shear_x', shear_x - raw_properties.get('shear_x').get('value'), fps_float)

                elif self.transform_mode == 'shear_bottom':
                    # Get current keyframe shear value
                    scale_x = raw_properties.get('scale_x').get('value')
                    shear_x = raw_properties.get('shear_x').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (self.clipBounds.width() / self.clipBounds.height()) * 2.0
                    shear_x += x_motion / ((self.clipBounds.width() * scale_x) / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'shear_x', shear_x)
                    self._apply_delta_to_clips('shear_x', shear_x - raw_properties.get('shear_x').get('value'), fps_float)

                elif self.transform_mode == 'shear_left':
                    # Get current keyframe shear value
                    shear_y = raw_properties.get('shear_y').get('value')
                    scale_y = raw_properties.get('scale_y').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (self.clipBounds.height() / self.clipBounds.width()) * 2.0
                    shear_y -= y_motion / (self.clipBounds.height() * scale_y / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'shear_y', shear_y)
                    self._apply_delta_to_clips('shear_y', shear_y - raw_properties.get('shear_y').get('value'), fps_float)

                elif self.transform_mode == 'shear_right':
                    # Get current keyframe shear value
                    scale_y = raw_properties.get('scale_y').get('value')
                    shear_y = raw_properties.get('shear_y').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (self.clipBounds.height() / self.clipBounds.width()) * 2.0
                    shear_y += y_motion / (self.clipBounds.height() * scale_y / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'shear_y', shear_y)
                    self._apply_delta_to_clips('shear_y', shear_y - raw_properties.get('shear_y').get('value'), fps_float)

                elif self.transform_mode == 'rotation':
                    # Get current rotation keyframe value
                    rotation = raw_properties.get('rotation').get('value')
                    scale_x = max(float(raw_properties.get('scale_x').get('value')), 0.001)
                    scale_y = max(float(raw_properties.get('scale_y').get('value')), 0.001)

                    # Calculate new location coordinates
                    is_on_right = event.pos().x() > self.originHandle.x()
                    is_on_top = event.pos().y() < self.originHandle.y()

                    x_adjust = x_motion / ((self.clipBounds.width() * scale_x) / 90)
                    rotation += (x_adjust if is_on_top else -x_adjust)

                    y_adjust = y_motion / ((self.clipBounds.height() * scale_y) / 90)
                    rotation += (y_adjust if is_on_right else -y_adjust)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id,
                        clip_frame_number,
                        'rotation', rotation)
                    self._apply_delta_to_clips('rotation', rotation - raw_properties.get('rotation').get('value'), fps_float)

                elif self.transform_mode.startswith('scale_'):
                    # Get current scale keyframe value
                    scale_x = max(float(raw_properties.get('scale_x').get('value')), 0.001)
                    scale_y = max(float(raw_properties.get('scale_y').get('value')), 0.001)

                    half_w = self.clipBounds.width() / 2.0
                    half_h = self.clipBounds.height() / 2.0

                    if self.transform_mode == 'scale_top_right':
                        scale_x += x_motion / half_w
                        scale_y -= y_motion / half_h
                    elif self.transform_mode == 'scale_bottom_right':
                        scale_x += x_motion / half_w
                        scale_y += y_motion / half_h
                    elif self.transform_mode == 'scale_top_left':
                        scale_x -= x_motion / half_w
                        scale_y -= y_motion / half_h
                    elif self.transform_mode == 'scale_bottom_left':
                        scale_x -= x_motion / half_w
                        scale_y += y_motion / half_h
                    elif self.transform_mode == 'scale_top':
                        scale_y -= y_motion / half_h
                    elif self.transform_mode == 'scale_bottom':
                        scale_y += y_motion / half_h
                    elif self.transform_mode == 'scale_left':
                        scale_x -= x_motion / half_w
                    elif self.transform_mode == 'scale_right':
                        scale_x += x_motion / half_w

                    if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
                        # If CTRL key is pressed, fix the scale_y to the correct aspect ratio
                        if scale_x:
                            scale_y = scale_x
                        elif scale_y:
                            scale_x = scale_y

                    # Update keyframe value (or create new one)
                    both_scaled = scale_x != 0.001 and scale_y != 0.001
                    if scale_x != 0.001:
                        self.updateClipProperty(
                            self.transforming_clips[0].id, clip_frame_number,
                            'scale_x', scale_x,
                            refresh=(not both_scaled))
                        self._apply_delta_to_clips('scale_x', scale_x - raw_properties.get('scale_x').get('value'), fps_float)
                    if scale_y != 0.001:
                        self.updateClipProperty(
                            self.transforming_clips[0].id, clip_frame_number,
                            'scale_y', scale_y)
                        self._apply_delta_to_clips('scale_y', scale_y - raw_properties.get('scale_y').get('value'), fps_float)

            # Force re-paint
            self.update()

        if self.region_enabled:
            # Modify region selection (x, y, width, height)
            # Corner size
            cs = self.cs

            # Adjust existing region coordinates (if any)
            if (not self.mouse_dragging
                and self.resize_button.isVisible()
                and self.resize_button.rect().contains(event.pos())
            ):
                # Mouse over resize button (and not currently dragging)
                self.setCursor(Qt.ArrowCursor)
            elif (
                    self.region_transform
                    and self.regionTopLeftHandle
                    and self.region_transform.mapToPolygon(
                        self.regionTopLeftHandle.toRect()).containsPoint(event.pos(), Qt.OddEvenFill)
                    ):
                if not self.region_mode or self.region_mode == 'scale_top_left':
                    self.setCursor(self.rotateCursor(self.cursors.get('resize_fdiag'), 0, 0, 0))
                # Set the region mode
                if self.mouse_dragging and not self.region_mode:
                    self.region_mode = 'scale_top_left'
            elif (
                    self.region_transform
                    and self.regionBottomRightHandle
                    and self.region_transform.mapToPolygon(
                        self.regionBottomRightHandle.toRect()).containsPoint(event.pos(), Qt.OddEvenFill)
                    ):
                if not self.region_mode or self.region_mode == 'scale_bottom_right':
                    self.setCursor(self.rotateCursor(self.cursors.get('resize_fdiag'), 0, 0, 0))
                # Set the region mode
                if self.mouse_dragging and not self.region_mode:
                    self.region_mode = 'scale_bottom_right'
            else:
                self.setCursor(Qt.ArrowCursor)

            # Initialize new region coordinates at current event.pos()
            if self.mouse_dragging and not self.region_mode:
                self.region_mode = 'scale_bottom_right'
                self.regionTopLeftHandle = QRectF(
                    self.region_transform_inverted.map(event.pos()).x(),
                    self.region_transform_inverted.map(event.pos()).y(),
                    cs, cs)
                self.regionBottomRightHandle = QRectF(
                    self.region_transform_inverted.map(event.pos()).x(),
                    self.region_transform_inverted.map(event.pos()).y(),
                    cs, cs)

            # Move existing region coordinates
            if self.mouse_dragging:
                diff_x = int(
                    self.region_transform_inverted.map(event.pos()).x()
                    - self.region_transform_inverted.map(self.mouse_position).x()
                )
                diff_y = int(
                    self.region_transform_inverted.map(event.pos()).y()
                    - self.region_transform_inverted.map(self.mouse_position).y()
                )
                if self.region_mode == 'scale_top_left':
                    self.regionTopLeftHandle.adjust(diff_x, diff_y, diff_x, diff_y)
                elif self.region_mode == 'scale_bottom_right':
                    self.regionBottomRightHandle.adjust(diff_x, diff_y, diff_x, diff_y)

            # Repaint widget on zoom
            self.update()

        if self.transforming_effect and self.transforming_clip and self.transforming_effect_object:
            # Adjust effect keyframes if mouse is on top of the transform handlers

            # Get framerate
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Determine frame # of clip (absolute frame, accounting for clip trim)
            clip_frame_number = self._get_clip_frame_number(
                self.transforming_clip, fps_float)

            # Get the rect where the video is actually drawn (without the black borders, etc...)
            viewport_rect = self.centeredViewport(self.width(), self.height())

            # Make back-up of clip data
            if self.mouse_dragging and not self.transform_mode and self.transforming_clip:
                if self.transforming_clip.id not in self.original_clip_data_map:
                    self.original_clip_data_map[self.transforming_clip.id] = json.loads(json.dumps(self.transforming_clip.data))

            if self.transforming_effect_object.info.has_tracked_object:
                # Get properties of effect at current frame
                raw_properties = json.loads(self.transforming_effect_object.PropertiesJSON(clip_frame_number))
                objects = raw_properties.get('objects', {})
                if not objects:
                    return

                selected_idx = self.transforming_effect.data.get('selected_object_index')
                obj_id = str(selected_idx) if selected_idx is not None else list(objects.keys())[0]
                raw_properties = objects.get(obj_id) or next(iter(objects.values()))

                if not raw_properties.get('visible'):
                    self.mouse_position = event.pos()
                    self.mutex.unlock()
                    return

                self.checkTransformMode(0, 0, 0, event)

                # Transform effect object
                if self.transform_mode:

                    x_motion = event.pos().x() - self.mouse_position.x()
                    y_motion = event.pos().y() - self.mouse_position.y()

                    if self.transform_mode == 'location':
                        # Get current keyframe value
                        location_x = raw_properties.get('delta_x').get('value')
                        location_y = raw_properties.get('delta_y').get('value')

                        # Calculate new location coordinates
                        location_x += x_motion / viewport_rect.width()
                        location_y += y_motion / viewport_rect.height()

                        # Update keyframe value (or create new one)
                        self.updateEffectProperty(
                            self.transforming_effect.id, clip_frame_number,
                            obj_id,
                            'delta_x', location_x,
                            refresh=False)
                        self.updateEffectProperty(
                            self.transforming_effect.id, clip_frame_number,
                            obj_id,
                            'delta_y', location_y)

                    elif self.transform_mode == 'rotation':
                        # Get current rotation keyframe value
                        rotation = raw_properties.get('rotation').get('value')
                        scale_x = max(float(raw_properties.get('scale_x').get('value')), 0.001)
                        scale_y = max(float(raw_properties.get('scale_y').get('value')), 0.001)

                        # Calculate new location coordinates
                        is_on_right = event.pos().x() > self.originHandle.x()
                        is_on_top = event.pos().y() < self.originHandle.y()

                        x_adjust = x_motion / (self.clipBounds.width() * scale_x / 90)
                        rotation += (x_adjust if is_on_top else -x_adjust)

                        y_adjust = y_motion / (self.clipBounds.height() * scale_y / 90)
                        rotation += (y_adjust if is_on_right else -y_adjust)

                        # Update keyframe value (or create new one)
                        self.updateEffectProperty(
                            self.transforming_effect.id,
                            clip_frame_number, obj_id,
                            'rotation', rotation)

                    elif self.transform_mode.startswith('scale_'):
                        # Get current scale keyframe value
                        scale_x = max(float(raw_properties.get('scale_x').get('value')), 0.001)
                        scale_y = max(float(raw_properties.get('scale_y').get('value')), 0.001)

                        half_w = self.clipBounds.width() / 2.0
                        half_h = self.clipBounds.height() / 2.0

                        if self.transform_mode == 'scale_top_right':
                            scale_x += x_motion / half_w
                            scale_y -= y_motion / half_h
                        elif self.transform_mode == 'scale_bottom_right':
                            scale_x += x_motion / half_w
                            scale_y += y_motion / half_h
                        elif self.transform_mode == 'scale_top_left':
                            scale_x -= x_motion / half_w
                            scale_y -= y_motion / half_h
                        elif self.transform_mode == 'scale_bottom_left':
                            scale_x -= x_motion / half_w
                            scale_y += y_motion / half_h
                        elif self.transform_mode == 'scale_top':
                            scale_y -= y_motion / half_h
                        elif self.transform_mode == 'scale_bottom':
                            scale_y += y_motion / half_h
                        elif self.transform_mode == 'scale_left':
                            scale_x -= x_motion / half_w
                        elif self.transform_mode == 'scale_right':
                            scale_x += x_motion / half_w

                        if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
                            # If CTRL key is pressed, fix the scale_y to the correct aspect ratio
                            if scale_x:
                                scale_y = scale_x
                            elif scale_y:
                                scale_x = scale_y

                        # Update keyframe value (or create new one)
                        both_scaled = scale_x != 0.001 and scale_y != 0.001
                        if scale_x != 0.001:
                            self.updateEffectProperty(
                                self.transforming_effect.id,
                                clip_frame_number, obj_id,
                                'scale_x', scale_x,
                                refresh=(not both_scaled))
                        if scale_y != 0.001:
                            self.updateEffectProperty(
                                self.transforming_effect.id,
                                clip_frame_number, obj_id,
                                'scale_y', scale_y)

            elif getattr(self.transforming_effect_object.info, 'class_name', '') == 'Crop':
                raw_properties = json.loads(
                    self.transforming_effect_object.PropertiesJSON(clip_frame_number))

                # Use the clip's transform for cursor orientation
                clip_props_for_cursors = json.loads(self.transforming_clip_object.PropertiesJSON(clip_frame_number))
                clip_rot = clip_props_for_cursors.get('rotation', {}).get('value', 0.0)
                clip_sx  = clip_props_for_cursors.get('shear_x', {}).get('value', 0.0)
                clip_sy  = clip_props_for_cursors.get('shear_y', {}).get('value', 0.0)

                crop_left   = raw_properties.get('left',   {}).get('value', 0.0)
                crop_top    = raw_properties.get('top',    {}).get('value', 0.0)
                crop_right  = raw_properties.get('right',  {}).get('value', 0.0)
                crop_bottom = raw_properties.get('bottom', {}).get('value', 0.0)
                resize = raw_properties.get('resize', {}).get('value', 0.0)
                crop_x = raw_properties.get('x', {}).get('value', 0.0)
                crop_y = raw_properties.get('y', {}).get('value', 0.0)

                cw = max(1.0 - crop_left - crop_right, 0.0001)
                ch = max(1.0 - crop_top - crop_bottom, 0.0001)

                # Use the clip's rotation/shear so the resize/rotate cursors match the tilted overlay
                self.checkTransformMode(clip_rot, clip_sx, clip_sy, event)

                if self.transform_mode:
                    x_motion = event.pos().x() - self.mouse_position.x()
                    y_motion = event.pos().y() - self.mouse_position.y()
                    base_w = max(self.clipBounds.width(), 0.0001)
                    base_h = max(self.clipBounds.height(), 0.0001)

                    # Determine how clip space maps to screen space (accounts for zoom)
                    mapped = self.transform.mapRect(self.clipBounds) if self.transform else self.clipBounds
                    sx_factor = mapped.width() / base_w
                    sy_factor = mapped.height() / base_h

                    width = (base_w / max(cw, 0.0001)) * sx_factor
                    height = (base_h / max(ch, 0.0001)) * sy_factor
                    if resize:
                        origin_w = base_w * sx_factor
                        origin_h = base_h * sy_factor
                    else:
                        origin_w = width
                        origin_h = height
                    if width <= 0.0001 or height <= 0.0001:
                        self.mutex.unlock()
                        return

                    eff_id = self.transforming_effect.id

                    new_left, new_top = crop_left, crop_top
                    new_right, new_bottom = crop_right, crop_bottom
                    new_x, new_y = crop_x, crop_y

                    if self.transform_mode == 'origin':
                        new_x -= x_motion / origin_w
                        new_y -= y_motion / origin_h
                        new_x = min(max(new_x, -1.0), 1.0)
                        new_y = min(max(new_y, -1.0), 1.0)
                    else:
                        if self.transform_mode == 'location':
                            dx = x_motion / width
                            dy = y_motion / height
                            dx = max(-crop_left, min(dx, crop_right))
                            dy = max(-crop_top, min(dy, crop_bottom))
                            new_left += dx
                            new_top += dy
                            new_right -= dx
                            new_bottom -= dy
                        elif self.transform_mode == 'scale_left':
                            new_left += x_motion / width
                        elif self.transform_mode == 'scale_right':
                            new_right -= x_motion / width
                        elif self.transform_mode == 'scale_top':
                            new_top += y_motion / height
                        elif self.transform_mode == 'scale_bottom':
                            new_bottom -= y_motion / height
                        elif self.transform_mode == 'scale_top_left':
                            new_left += x_motion / width
                            new_top += y_motion / height
                        elif self.transform_mode == 'scale_top_right':
                            new_top += y_motion / height
                            new_right -= x_motion / width
                        elif self.transform_mode == 'scale_bottom_left':
                            new_left += x_motion / width
                            new_bottom -= y_motion / height
                        elif self.transform_mode == 'scale_bottom_right':
                            new_right -= x_motion / width
                            new_bottom -= y_motion / height

                        new_left = min(max(new_left, 0.0), 1.0)
                        new_top = min(max(new_top, 0.0), 1.0)
                        new_right = min(max(new_right, 0.0), 1.0)
                        new_bottom = min(max(new_bottom, 0.0), 1.0)
                        if new_left + new_right > 1.0:
                            if 'left' in self.transform_mode or self.transform_mode == 'location':
                                new_left = 1.0 - new_right
                            else:
                                new_right = 1.0 - new_left
                        if new_top + new_bottom > 1.0:
                            if 'top' in self.transform_mode or self.transform_mode == 'location':
                                new_top = 1.0 - new_bottom
                            else:
                                new_bottom = 1.0 - new_top

                    updates = {}
                    if abs(new_left - crop_left) > 0.0001:
                        updates['left'] = new_left
                    if abs(new_top - crop_top) > 0.0001:
                        updates['top'] = new_top
                    if abs(new_right - crop_right) > 0.0001:
                        updates['right'] = new_right
                    if abs(new_bottom - crop_bottom) > 0.0001:
                        updates['bottom'] = new_bottom
                    if abs(new_x - crop_x) > 0.0001:
                        updates['x'] = new_x
                    if abs(new_y - crop_y) > 0.0001:
                        updates['y'] = new_y

                    for i, (prop, val) in enumerate(updates.items()):
                        self.updateEffectProperty(
                            eff_id,
                            clip_frame_number,
                            None,
                            prop,
                            val,
                            refresh=(i == len(updates) - 1),
                        )

            # Force re-paint
            self.update()
            # ==================================================================================

        # Update mouse position
        self.mouse_position = event.pos()

        self.mutex.unlock()

    def updateClipProperty(self, clip_id, frame_number, property_key, new_value, refresh=True):
        """Update a keyframe property to a new value, adding or updating keyframes as needed"""
        found_point = False
        clip_updated = False

        c = Clip.get(id=clip_id)
        if not c:
            # No clip found
            return

        # Property missing? Create it!
        if property_key not in c.data:
            c.data[property_key] = {"Points": []}
            log.warning("%s: Added missing '%s' to property data", clip_id, property_key)

        points = c.data.get(property_key, {}).get("Points", [])
        for point in points:
            co = point.get("co", {})
            log.info("looping points: co.X = %s" % co.get("X"))

            if co.get("X") == frame_number:
                found_point = True
                clip_updated = True
                point.update({
                    "co": {"X": frame_number, "Y": float(new_value)},
                    "interpolation": openshot.BEZIER,
                })

        if not found_point and new_value is not None:
            clip_updated = True
            log.info("Creating new point at X=%s", frame_number)
            c.data[property_key]["Points"].append({
                'co': {'X': frame_number, 'Y': float(new_value)},
                'interpolation': openshot.BEZIER
            })

        if clip_updated:
            # Reduce # of clip properties we are saving (performance boost)
            c.data = {property_key: c.data.get(property_key)}
            if self.transaction_id:
                get_app().updates.transaction_id = self.transaction_id
            c.save()
            # Update the preview
            if refresh:
                get_app().window.refreshFrameSignal.emit()

    def updateEffectProperty(self, effect_id, frame_number, obj_id, property_key, new_value, refresh=True):
        """Update a keyframe property to a new value, adding or updating keyframes as needed"""
        found_point = False
        effect_updated = False

        c = Effect.get(id=effect_id)

        if not c:
            # No clip found
            return

        # Clamp frame number to a sane range (effects share clip timing, so keep >= 1)
        frame_number = max(1, int(round(frame_number)))

        try:
            if obj_id is not None:
                props = c.data['objects'][obj_id]
            else:
                props = c.data
            points_list = props[property_key]["Points"]
        except (TypeError, KeyError):
            log.error("Corrupted project data!", exc_info=1)
            return

        if property_key in {'left', 'top', 'right', 'bottom'} and new_value is not None:
            new_value = min(max(float(new_value), 0.0), 1.0)

        for point in points_list:
            co = point.get("co", {})
            log.info("looping points: co.X = %s" % co.get("X"))

            if co.get("X") == frame_number:
                found_point = True
                effect_updated = True
                point.update({
                    "co": {"X": frame_number, "Y": float(new_value)},
                    "interpolation": openshot.BEZIER,
                })

        if not found_point and new_value is not None:
            effect_updated = True
            log.info("Creating new point at X=%s", frame_number)
            points_list.append({
                'co': {'X': frame_number, 'Y': float(new_value)},
                'interpolation': openshot.BEZIER,
                })

        if effect_updated:
            # Reduce # of clip properties we are saving (performance boost)
            if obj_id is not None:
                c.data = {'objects': {obj_id: c.data.get('objects', {}).get(obj_id)}}
            else:
                c.data = {property_key: c.data.get(property_key)}
            if self.transaction_id:
                get_app().updates.transaction_id = self.transaction_id
            c.save()
            # Update the preview
            if refresh:
                get_app().window.refreshFrameSignal.emit()

    def _get_clip_frame_number(self, clip, fps_float):
        """Return clip-relative frame clamped between trimmed start/end."""
        data = clip.data

        # Seconds
        start_sec = float(data.get("start", 0.0))
        end_val = data.get("end", None)
        end_sec = float(end_val) if end_val is not None else None

        # Frames
        start_frame = round(start_sec * fps_float) + 1
        end_frame = None
        if end_sec is not None and end_sec > start_sec:
            end_frame = round(end_sec * fps_float)

        # Timeline position (in frames, 1-based)
        position = (float(data.get("position", 0.0)) * fps_float) + 1

        # Current playhead frame
        try:
            playhead = float(get_app().window.preview_thread.current_frame)
        except Exception:
            playhead = 1.0

        # Original clip-relative math
        frame = round(playhead - position) + start_frame

        # Clamp to [start_frame, end_frame] if end is valid, otherwise just clamp to start
        if frame < start_frame:
            return start_frame
        if end_frame is not None and frame > end_frame:
            return end_frame

        return frame

    def _apply_delta_to_clips(self, property_key, delta, fps_float):
        for clip, obj in zip(self.transforming_clips[1:], self.transforming_clip_objects[1:]):
            frame = self._get_clip_frame_number(clip, fps_float)
            props = json.loads(obj.PropertiesJSON(frame))
            value = props.get(property_key).get('value')
            if self.transaction_id:
                get_app().updates.transaction_id = self.transaction_id
            self.updateClipProperty(clip.id, frame, property_key, value + delta, refresh=False)

    def _crop_resize_rect(self, width, height, left, top, right, bottom, x_off, y_off):
        width = float(max(width, 0.0))
        height = float(max(height, 0.0))
        dest_left = left * width
        dest_top = top * height
        dest_width = max(0.0, 1.0 - left - right) * width
        dest_height = max(0.0, 1.0 - top - bottom) * height

        src_left = dest_left + (x_off * width)
        src_top = dest_top + (y_off * height)

        if src_left < 0.0:
            overflow = -src_left
            dest_left -= src_left
            dest_width -= overflow
            src_left = 0.0
        if src_top < 0.0:
            overflow = -src_top
            dest_top -= src_top
            dest_height -= overflow
            src_top = 0.0

        src_right = src_left + dest_width
        if src_right > width:
            overflow = src_right - width
            dest_width -= overflow
            src_right = width

        src_bottom = src_top + dest_height
        if src_bottom > height:
            overflow = src_bottom - height
            dest_height -= overflow
            src_bottom = height

        dest_width = max(dest_width, 0.0)
        dest_height = max(dest_height, 0.0)

        return QRectF(dest_left, dest_top, dest_width, dest_height)

    def _clip_source_dimensions(self, clip, clip_object, frame_number, skip_effect_id=None):
        pixel_adjust = self.pixel_ratio.Reciprocal().ToDouble()
        width = float(clip.data['reader']['width'])
        height = float(clip.data['reader']['height']) * pixel_adjust

        for eff in clip_object.Effects():
            if getattr(getattr(eff, 'info', None), 'class_name', '') != 'Crop':
                continue
            if skip_effect_id is not None and hasattr(eff, 'Id') and eff.Id() == skip_effect_id:
                continue
            eff_props = json.loads(eff.PropertiesJSON(frame_number))
            if not eff_props.get('resize', {}).get('value', 0.0):
                continue
            left = eff_props.get('left', {}).get('value', 0.0)
            top = eff_props.get('top', {}).get('value', 0.0)
            right = eff_props.get('right', {}).get('value', 0.0)
            bottom = eff_props.get('bottom', {}).get('value', 0.0)
            x_off = eff_props.get('x', {}).get('value', 0.0)
            y_off = eff_props.get('y', {}).get('value', 0.0)

            crop_rect = self._crop_resize_rect(width, height, left, top, right, bottom, x_off, y_off)
            width = max(crop_rect.width(), 0.0001)
            height = max(crop_rect.height(), 0.0001)

        return width, height

    def _clip_display_rect(self, base_width, base_height, clip, raw_properties, viewport_rect):
        player_width = viewport_rect.width()
        player_height = viewport_rect.height()

        source_size = QSizeF(base_width, base_height)
        scale_mode = clip.data['scale']
        parent_memo = raw_properties.get('parentObjectId', {}).get('memo', '')
        if parent_memo:
            scale_mode = openshot.SCALE_STRETCH

        if scale_mode == openshot.SCALE_FIT:
            source_size.scale(player_width, player_height, Qt.KeepAspectRatio)
        elif scale_mode == openshot.SCALE_STRETCH:
            source_size.scale(player_width, player_height, Qt.IgnoreAspectRatio)
        elif scale_mode == openshot.SCALE_CROP:
            source_size.scale(player_width, player_height, Qt.KeepAspectRatioByExpanding)

        source_width = max(source_size.width(), 0.0001)
        source_height = max(source_size.height(), 0.0001)

        # Get per-frame scale factors
        sx = max(float(raw_properties.get('scale_x').get('value')), 0.001)
        sy = max(float(raw_properties.get('scale_y').get('value')), 0.001)

        # Scaled dimensions used for gravity and location offsets
        scaled_width = source_width * sx
        scaled_height = source_height * sy

        x = viewport_rect.x()
        y = viewport_rect.y()

        gravity = clip.data['gravity']
        if gravity == openshot.GRAVITY_TOP:
            x += (player_width - scaled_width) / 2.0
        elif gravity == openshot.GRAVITY_TOP_RIGHT:
            x += player_width - scaled_width
        elif gravity == openshot.GRAVITY_LEFT:
            y += (player_height - scaled_height) / 2.0
        elif gravity == openshot.GRAVITY_CENTER:
            x += (player_width - scaled_width) / 2.0
            y += (player_height - scaled_height) / 2.0
        elif gravity == openshot.GRAVITY_RIGHT:
            x += player_width - scaled_width
            y += (player_height - scaled_height) / 2.0
        elif gravity == openshot.GRAVITY_BOTTOM_LEFT:
            y += player_height - scaled_height
        elif gravity == openshot.GRAVITY_BOTTOM:
            x += (player_width - scaled_width) / 2.0
            y += player_height - scaled_height
        elif gravity == openshot.GRAVITY_BOTTOM_RIGHT:
            x += player_width - scaled_width
            y += player_height - scaled_height

        location_x = float(raw_properties.get('location_x', {}).get('value', 0.0))
        location_y = float(raw_properties.get('location_y', {}).get('value', 0.0))
        x += player_width * location_x
        y += player_height * location_y

        return QRectF(x, y, source_width, source_height)

    def _clip_rect(self, clip, clip_object, viewport_rect, frame_number):
        raw_properties = json.loads(clip_object.PropertiesJSON(frame_number))

        skip_id = None
        if self.transforming_effect_object and hasattr(self.transforming_effect_object, 'Id'):
            skip_id = self.transforming_effect_object.Id()

        base_width, base_height = self._clip_source_dimensions(clip, clip_object, frame_number, skip_id)
        rect = self._clip_display_rect(base_width, base_height, clip, raw_properties, viewport_rect)

        return rect, raw_properties

    def refreshTriggered(self):
        """Signal to refresh viewport (i.e. a property might have changed that effects the preview)"""

        # Update reference to clip(s)
        if self.transforming_clips:
            self.transforming_clips = [Clip.get(id=c.id) for c in self.transforming_clips if Clip.get(id=c.id)]
            if self.transforming_clips:
                self.transforming_clip = self.transforming_clips[0]
            else:
                self.transforming_clip = None

        if self.transforming_effect:
            self.transforming_effect = Effect.get(id=self.transforming_effect.id)

    def transformTriggered(self, clip_ids):
        """Handle the transform signal when it's emitted. Supports multiple clip IDs."""
        win = get_app().window
        need_refresh = False

        if not isinstance(clip_ids, list):
            clip_ids = [clip_ids] if clip_ids else []

        if not clip_ids:
            if self.transforming_clips:
                self.transforming_clips = []
                self.transforming_clip_objects = []
                self.transforming_clip = None
                self.transforming_clip_object = None
                need_refresh = True
            # Reset cursor when no clips are selected
            self.setCursor(Qt.ArrowCursor)
        else:
            self.transforming_clips = []
            self.transforming_clip_objects = []
            for cid in clip_ids:
                c = Clip.get(id=cid)
                co = win.timeline_sync.timeline.GetClip(cid)
                if c and co:
                    self.transforming_clips.append(c)
                    self.transforming_clip_objects.append(co)

            if self.transforming_clips:
                self.transforming_clip = self.transforming_clips[0]
                self.transforming_clip_object = self.transforming_clip_objects[0]
                self.transforming_effect = None
                self.transforming_effect_object = None
                need_refresh = True

        # Update the preview and reselect current frame in properties
        if need_refresh:
            win.refreshFrameSignal.emit()
        self.update_title()

    def keyFrameTransformTriggered(self, effect_id, clip_id):
        """Handle the key frame transform signal when it's emitted"""
        win = get_app().window
        need_refresh = False

        # Disable Transform UI
        # Is this the same clip_id already being transformed?
        if self.transforming_effect and not effect_id:
            # Clear transform
            self.transforming_effect = None
            self.transforming_effect_object = None
            self.transforming_clip = None
            self.transforming_clip_object = None
            need_refresh = True

        # Get new clip for transform
        if effect_id and clip_id:
            clip = Clip.get(id=clip_id)
            clip_obj = win.timeline_sync.timeline.GetClip(clip_id)
            eff = Effect.get(id=effect_id)
            eff_obj = win.timeline_sync.timeline.GetClipEffect(effect_id)

            if clip and clip_obj and eff and eff_obj:
                self.transforming_clip = clip
                self.transforming_clip_object = clip_obj
                self.transforming_effect = eff
                self.transforming_effect_object = eff_obj
            else:
                self.transforming_clip = None
                self.transforming_clip_object = None
                self.transforming_effect = None
                self.transforming_effect_object = None

            need_refresh = True

        # Update the preview and reselct current frame in properties
        if need_refresh:
            win.refreshFrameSignal.emit()
            win.propertyTableView.select_frame(win.preview_thread.player.Position())
        self.update_title()

    def regionTriggered(self, clip_id):
        """Handle the 'select region' signal when it's emitted"""
        # Clear transform
        self.region_enabled = bool(clip_id)
        get_app().window.refreshFrameSignal.emit()
        self.update_title()

    def resizeEvent(self, event):
        """Widget resize event"""
        event.accept()
        self.delayed_size = self.size()
        self.delayed_resize_timer.start()

        # Pause playback (to prevent crash since we are fixing to change the timeline's max size)
        self.win.PauseSignal.emit()

    def delayed_resize_callback(self):
        """Callback for resize event timer (to delay the resize event, and prevent lots of similar resize events)"""
        # Ensure width & height are divisible by 2 (round decimals).
        # Trying to find the closest even number to the requested aspect ratio
        # so that both width and height are divisible by 2. This is to prevent some
        # strange phantom scaling lines on the edges of the preview window.

        # Scale project size (with aspect ratio) to the delayed widget size
        project_size = QSize(get_app().project.get("width"), get_app().project.get("height"))
        project_size.scale(self.delayed_size, Qt.KeepAspectRatio)

        if project_size.height() > 0:
            # Ensure width and height are divisible by 2
            ratio = float(project_size.width()) / float(project_size.height())
            even_width = round(project_size.width() / 2.0) * 2
            even_height = round(round(even_width / ratio) / 2.0) * 2
            project_size = QSize(int(even_width), int(even_height))

        # Emit signal that video widget changed size
        self.win.MaxSizeChanged.emit(project_size)

    # Capture wheel event to alter zoom/scale of widget
    def wheelEvent(self, event):
        event.accept()
        # For each 120 (standard scroll unit) adjust the zoom slider
        tick_scale = 1024
        self.zoom += event.angleDelta().y() / tick_scale
        if self.zoom <= 0.0:
            # Don't allow zoom to go all the way to zero (or negative)
            self.zoom = 0.05

        # Add resize button (if not 100% zoom)
        if self.zoom != 1.0:
            self.resize_button.show()
        else:
            self.resize_button.hide()

        # Repaint widget on zoom
        self.repaint()

    def resize_button_clicked(self):
        """Resize zoom button clicked"""
        self.zoom = 1.0
        self.resize_button.hide()

        # Repaint widget on zoom
        self.repaint()

    def __init__(self, watch_project=True, *args):
        """watch_project: watch for changes in project size / widget size, and
        continue to match the current project's aspect ratio."""
        # Invoke parent init
        QWidget.__init__(self, *args)

        # Translate object
        _ = get_app()._tr

        # Settings object
        self.settings = get_app().get_settings()

        # Init aspect ratio settings (default values)
        self.aspect_ratio = openshot.Fraction(16, 9)
        self.pixel_ratio = openshot.Fraction(1, 1)
        self.transforming_clip = None
        self.transforming_clips = []
        self.transforming_clip_objects = []
        self.transforming_effect = None
        self.transforming_clip_object = None
        self.transforming_effect_object = None
        self.transaction_id = None
        self.transform = None
        self.topLeftHandle = None
        self.topRightHandle = None
        self.bottomLeftHandle = None
        self.bottomRightHandle = None
        self.topHandle = None
        self.bottomHandle = None
        self.leftHandle = None
        self.rightHandle = None
        self.centerHandle = None
        self.topShearHandle = None
        self.leftShearHandle = None
        self.rightShearHandle = None
        self.bottomShearHandle = None
        self.clipBounds = None
        self.originHandle = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.transform_mode = None
        self.hover_transform_mode = None
        self.hover_cursor = Qt.ArrowCursor
        self.original_clip_data = None
        self.original_clip_data_map = {}
        self.original_effect_data = None
        self.region_qimage = None
        self.region_transform = None
        self.region_enabled = False
        self.region_mode = None
        self.regionTopLeftHandle = None
        self.regionBottomRightHandle = None
        self.curr_frame_size = None # Frame size
        self.zoom = 1.0  # Zoom of widget (does not affect video, only workspace)
        self.cs = 14.0  # Corner size of Transform Handler rectangles
        self.resize_button = QPushButton(_('Reset Zoom'), self)
        self.resize_button.hide()
        self.resize_button.setStyleSheet('QPushButton { margin: 10px; padding: 2px; }')
        self.resize_button.clicked.connect(self.resize_button_clicked)
        self.resize_button.setMouseTracking(True)

        # FPS calculations
        self.paint_fps = 0.0
        self.paint_fps_counter = 1
        self.paint_fps_sec = None
        self.present_fps = 0.0
        self.present_fps_counter = 1
        self.present_fps_sec = None

        # Load icon (using display DPI)
        self.cursors = {}
        for cursor_name in ["move",
                            "resize_x",
                            "resize_y",
                            "resize_bdiag",
                            "resize_fdiag",
                            "rotate",
                            "shear_x",
                            "shear_y",
                            "hand"]:
            icon = QIcon(":/cursors/cursor_%s.png" % cursor_name)
            self.cursors[cursor_name] = icon.pixmap(32, 32)

        # Mutex lock
        self.mutex = QMutex()

        # Init Qt widget's properties (background repainting, etc...)
        super().setAttribute(Qt.WA_OpaquePaintEvent)
        super().setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)

        # Set mouse tracking
        self.setMouseTracking(True)

        # Init current frame's QImage
        self.current_image = None

        # Get a reference to the window object
        self.win = get_app().window

        # Update title whenever playback speed changes.
        self.win.PlaySignal.connect(self.update_title, Qt.QueuedConnection)
        self.win.PlaySignal.connect(self.update_title, Qt.QueuedConnection)
        self.win.PauseSignal.connect(self.update_title, Qt.QueuedConnection)
        self.win.SpeedSignal.connect(self.update_title, Qt.QueuedConnection)
        self.win.StopSignal.connect(self.update_title, Qt.QueuedConnection)

        # Show Property timer
        # Timer to use a delay before sending MaxSizeChanged signals (so we don't spam libopenshot)
        self.delayed_resize_timer = QTimer(self)
        self.delayed_resize_timer.setInterval(200)
        self.delayed_resize_timer.setSingleShot(True)
        if watch_project:
            self.delayed_resize_timer.timeout.connect(self.delayed_resize_callback)

        # Connect to signals
        self.win.TransformSignal.connect(self.transformTriggered)
        self.win.KeyFrameTransformSignal.connect(self.keyFrameTransformTriggered)
        self.win.SelectRegionSignal.connect(self.regionTriggered)
        self.win.refreshFrameSignal.connect(self.refreshTriggered)
