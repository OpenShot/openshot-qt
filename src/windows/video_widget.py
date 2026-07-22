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

from qt_api import (
    Qt, QApplication, QCoreApplication, QMutex, QTimer,
    pyqtSignal, pyqtSlot, QPoint, QPointF, QSize, QSizeF, QRect, QRectF, QLineF,
)
from qt_api import modifiers_has
from qt_api import (
    QTransform, QPainter, QIcon, QColor, QPen, QBrush, QCursor, QImage, QRegion
)
from qt_api import QSizePolicy, QWidget, QPushButton

import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import updates
from classes import openshot_rc  # noqa
from classes.logger import log
from classes.app import get_app
from classes.query import Clip, Effect

MARGIN_BOX_EFFECTS = {"Bars", "Blur", "Caption", "Crop", "Pixelate"}
OBJECT_MASK_PREVIEW_COLOR = QColor(83, 160, 237, 120)
OBJECT_MASK_PREVIEW_STROKE_COLOR = QColor(255, 255, 255, 255)
OBJECT_MASK_PREVIEW_STROKE_WIDTH = 3


class VideoWidget(QWidget, updates.UpdateInterface):
    """ A QWidget used on the video display widget """
    regionAnnotationChanged = pyqtSignal()
    regionAnnotationLimitReached = pyqtSignal()
    regionRectChanged = pyqtSignal()
    scopeRegionCancelled = pyqtSignal()

    def _is_playing(self):
        try:
            return get_app().window.preview_thread.player.Mode() == openshot.PLAYBACK_PLAY
        except Exception:
            return False

    def _snap_angle(self, angle_degrees, step_degrees=15.0):
        """Snap an angle to the nearest increment (degrees)."""
        step = float(step_degrees) if step_degrees else 0.0
        if step <= 0.0:
            return angle_degrees
        return math.floor((angle_degrees + (step / 2.0)) / step) * step

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

    def _clip_screen_rect(self, rect, props):
        """Return the on-screen bounds of a clip rect after its clip transform."""
        transform, _, _ = self._build_clip_transform(
            rect.x(), rect.y(), rect.width(), rect.height(), props
        )
        return transform.mapRect(QRectF(0.0, 0.0, rect.width(), rect.height()))

    def _effect_has_margin_box(self, raw_properties=None):
        """Return True when an effect exposes a left/top/right/bottom margin rectangle."""
        if raw_properties is not None:
            return all(prop in raw_properties for prop in ("left", "top", "right", "bottom"))
        if self.transforming_effect_object:
            class_name = getattr(self.transforming_effect_object.info, 'class_name', '')
            if class_name in MARGIN_BOX_EFFECTS:
                return True
        if self.transforming_effect:
            if self.transforming_effect.data.get("class_name") in MARGIN_BOX_EFFECTS:
                return True
            return all(prop in self.transforming_effect.data for prop in ("left", "top", "right", "bottom"))
        return False

    def _draw_object_mask_preview(self, painter, mask_image, target_rect):
        if mask_image is None or mask_image.isNull():
            return

        overlay = QImage(mask_image.size(), QImage.Format_ARGB32_Premultiplied)
        overlay.fill(Qt.transparent)
        overlay_painter = QPainter(overlay)
        overlay_painter.setCompositionMode(QPainter.CompositionMode_Source)
        overlay_painter.fillRect(overlay.rect(), OBJECT_MASK_PREVIEW_COLOR)
        overlay_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        overlay_painter.drawImage(0, 0, mask_image)
        overlay_painter.end()
        painter.drawImage(target_rect, overlay)

        stroke = QImage(mask_image.size(), QImage.Format_ARGB32_Premultiplied)
        stroke.fill(Qt.transparent)
        stroke_painter = QPainter(stroke)
        stroke_painter.setCompositionMode(QPainter.CompositionMode_Source)
        stroke_painter.fillRect(stroke.rect(), OBJECT_MASK_PREVIEW_STROKE_COLOR)
        stroke_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        radius = max(1, int(OBJECT_MASK_PREVIEW_STROKE_WIDTH))
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                if x == 0 and y == 0:
                    continue
                if (x * x + y * y) <= (radius * radius):
                    stroke_painter.drawImage(x, y, mask_image)
        stroke_painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        stroke_painter.drawImage(0, 0, mask_image)
        stroke_painter.end()
        painter.drawImage(target_rect, stroke)

    @staticmethod
    def _margin_box_norm(raw_properties):
        """Return normalized x1/y1/x2/y2 from left/top/right/bottom margin properties."""
        left = float(raw_properties.get('left', {}).get('value', 0.0))
        top = float(raw_properties.get('top', {}).get('value', 0.0))
        right = float(raw_properties.get('right', {}).get('value', 0.0))
        bottom = float(raw_properties.get('bottom', {}).get('value', 0.0))
        left = min(max(left, 0.0), 1.0)
        top = min(max(top, 0.0), 1.0)
        right = min(max(right, 0.0), 1.0)
        bottom = min(max(bottom, 0.0), 1.0)
        if left + right > 1.0:
            right = 1.0 - left
        if top + bottom > 1.0:
            bottom = 1.0 - top
        return left, top, 1.0 - right, 1.0 - bottom

    @staticmethod
    def _clamp_margin_values(left, top, right, bottom, prefer_left=False, prefer_top=False):
        """Clamp margin values while preserving the dragged edge when opposing margins collide."""
        left = min(max(float(left), 0.0), 1.0)
        top = min(max(float(top), 0.0), 1.0)
        right = min(max(float(right), 0.0), 1.0)
        bottom = min(max(float(bottom), 0.0), 1.0)
        if left + right > 1.0:
            if prefer_left:
                left = 1.0 - right
            else:
                right = 1.0 - left
        if top + bottom > 1.0:
            if prefer_top:
                top = 1.0 - bottom
            else:
                bottom = 1.0 - top
        return left, top, right, bottom

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
        self.marginBoxFullBounds = None
        self.originHandle = None
        self.original_effect_data = None
        self.hover_transform_mode = None
        self.rotation_drag_value = None
        self.margin_box_drag_anchor = None
        self.hover_cursor = Qt.ArrowCursor
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def drawTransformHandler(
        self, painter, sx, sy, source_width, source_height,
        origin_x, origin_y,
        x1=None, y1=None, x2=None, y2=None, rotation=None,
        skip_origin=False,
        muted_handles=False
    ):
        # Corner and origin glyph on-screen sizes
        cs = self.cs
        os = 12.0

        csx = cs / sx
        csy = cs / sy

        # Accept 0.0 values; only treat None as missing
        has_crop_box = (x1 is not None and y1 is not None and x2 is not None and y2 is not None)
        self.marginBoxFullBounds = QRectF(0.0, 0.0, source_width, source_height)

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
        color_hex = "#d3d3d3" if muted_handles else "#53a0ed"
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
            painter.drawLines([
                QLineF(center - halfW, center + halfW),
                QLineF(center - halfH, center + halfH),
            ])
        else:
            self.centerHandle = None

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
        if self.region_enabled:
            transform_label = _("Selection")
        elif (self.transforming_effect and self.transforming_effect_object and
                getattr(self.transforming_effect_object.info, 'class_name', '') == 'Crop'):
            transform_label = _("Crop")
        elif self.transforming_effect and self._effect_has_margin_box():
            transform_label = _("Region")
        elif self.transforming_effect or self.transforming_clips:
            transform_label = _("Transform")

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

    @staticmethod
    def _scaled_frame_size(image_size, widget_size):
        """Return the logical displayed frame size inside the widget."""
        pix_size = QSize(image_size)
        pix_size.scale(widget_size, Qt.KeepAspectRatio)
        return pix_size

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
                pix_size = self._scaled_frame_size(self.current_image.size(), self.size())
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
            use_group_bounds = len(clip_pairs) > 1
            for clip, obj in clip_pairs:
                frame = self._get_clip_frame_number(clip, fps_float)
                rect, props = self._clip_rect(clip, obj, viewport, frame)
                if use_group_bounds:
                    rect = self._clip_screen_rect(rect, props)
                    props = default_props
                if union_rect is None:
                    union_rect = rect
                    first_props = props
                else:
                    union_rect = union_rect.united(rect)

            crop_params = None
            crop_norm = None
            margin_box_norm = None
            tracked_object_overlay = False

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
                    tracked_object_overlay = True
                    objs = raw_eff.get("objects", {}) or {}
                    if objs:
                        oid, eprops = self._resolve_tracked_object(objs, raw_eff)
                        if oid and eprops and self._tracked_object_visible(eprops):
                            x1_abs = clip_rect.x() + eprops.get("x1", {}).get("value", 0.0) * clip_rect.width()
                            y1_abs = clip_rect.y() + eprops.get("y1", {}).get("value", 0.0) * clip_rect.height()
                            x2_abs = clip_rect.x() + eprops.get("x2", {}).get("value", 0.0) * clip_rect.width()
                            y2_abs = clip_rect.y() + eprops.get("y2", {}).get("value", 0.0) * clip_rect.height()
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
                    margin_box_norm = crop_norm

                elif self._effect_has_margin_box(raw_eff):
                    margin_box_norm = self._margin_box_norm(raw_eff)
                    union_rect = clip_rect
                    first_props = clip_props

            # Draw handler(s)
            if union_rect and first_props and not self.region_enabled:
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
                elif margin_box_norm:
                    x1, y1, x2, y2 = margin_box_norm
                else:
                    x1 = y1 = x2 = y2 = None
                self.drawTransformHandler(
                    painter, sx, sy, sw, sh, ox, oy,
                    x1, y1, x2, y2,
                    skip_origin=(
                        is_crop
                        or margin_box_norm is not None
                        or tracked_object_overlay
                    ),
                    muted_handles=(is_crop or margin_box_norm is not None)
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
                    painter.drawLines([
                        QLineF(c - halfW, c + halfW),
                        QLineF(c - halfH, c + halfH),
                    ])

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
                if self.region_selection_mode in ("point", "annotate"):
                    if (
                        self.region_selection_mode == "annotate"
                        and self.region_mask_preview_image is not None
                        and self.curr_frame_size is not None
                    ):
                        mask_image = self.region_mask_preview_image
                        mask_rect = QRectF(0.0, 0.0, float(self.curr_frame_size.width()), float(self.curr_frame_size.height()))
                        self._draw_object_mask_preview(painter, mask_image, mask_rect)

                    point_radius = max(2.0, (cs * 0.4) / max(self.zoom, 0.001))
                    if self.region_points_positive:
                        pos_color = QColor("#53a0ed")
                        pos_color.setAlphaF(self.handle_opacity)
                        pos_pen = QPen(QBrush(pos_color), 1.5)
                        pos_pen.setCosmetic(True)
                        painter.setPen(pos_pen)
                        painter.setBrush(QBrush(pos_color))
                        for pt in self.region_points_positive:
                            painter.drawEllipse(pt, point_radius, point_radius)
                    if self.region_points_negative:
                        neg_color = QColor("#e05757")
                        neg_color.setAlphaF(self.handle_opacity)
                        neg_pen = QPen(QBrush(neg_color), 1.5)
                        neg_pen.setCosmetic(True)
                        painter.setPen(neg_pen)
                        painter.setBrush(QBrush(neg_color))
                        for pt in self.region_points_negative:
                            painter.drawEllipse(pt, point_radius, point_radius)
                    # Draw positive rectangles
                    if self.region_rects_positive:
                        rect_pos_color = QColor("#53a0ed")
                        rect_pos_color.setAlphaF(self.handle_opacity)
                        rect_pos_pen = QPen(QBrush(rect_pos_color), 1.5)
                        rect_pos_pen.setCosmetic(True)
                        painter.setPen(rect_pos_pen)
                        painter.setBrush(Qt.NoBrush)
                        for rect in self.region_rects_positive:
                            if isinstance(rect, QRectF):
                                painter.drawRect(rect.normalized())

                    # Draw negative rectangles
                    if self.region_rects_negative:
                        rect_neg_color = QColor("#e05757")
                        rect_neg_color.setAlphaF(self.handle_opacity)
                        rect_neg_pen = QPen(QBrush(rect_neg_color), 1.5)
                        rect_neg_pen.setCosmetic(True)
                        painter.setPen(rect_neg_pen)
                        painter.setBrush(Qt.NoBrush)
                        for rect in self.region_rects_negative:
                            if isinstance(rect, QRectF):
                                painter.drawRect(rect.normalized())

                    # Draw current dragging rectangle preview
                    if self.region_rect_drag_start is not None and self.region_rect_drag_current is not None:
                        drag_color = QColor("#53a0ed")
                        if str(self.region_annotation_tool or "").endswith("negative_rect"):
                            drag_color = QColor("#e05757")
                        drag_color.setAlphaF(self.handle_opacity)
                        drag_pen = QPen(QBrush(drag_color), 1.5, Qt.DashLine)
                        drag_pen.setCosmetic(True)
                        painter.setPen(drag_pen)
                        painter.setBrush(Qt.NoBrush)
                        painter.drawRect(QRectF(self.region_rect_drag_start, self.region_rect_drag_current).normalized())

                elif self.regionTopLeftHandle and self.regionBottomRightHandle:
                    color = QColor("#53a0ed")
                    color.setAlphaF(self.handle_opacity)
                    pen = QPen(QBrush(color), 1.25, Qt.DotLine)
                    pen.setCosmetic(True)
                    painter.setPen(pen)
                    region_rect = self._scope_region_rect()
                    painter.drawRect(region_rect)
                    painter.setBrush(Qt.NoBrush)
                    solid_pen = QPen(QBrush(color), 1.5)
                    solid_pen.setCosmetic(True)
                    painter.setPen(solid_pen)
                    for handle_rect in self._scope_region_corner_rects().values():
                        painter.drawRect(handle_rect)

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
        pan_x, pan_y = self._clamp_pan(width=width, height=height)
        viewport_rect.moveCenter(window_rect.center() + QPointF(pan_x, pan_y))
        # Always round up to next whole integer value
        return viewport_rect.toAlignedRect()

    @pyqtSlot(QImage)
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

        # Request an async paint to avoid recursive QWidget repaint on Windows.
        self.update()

    def connectSignals(self, renderer):
        """ Connect signals to renderer """
        renderer.present.connect(self.present)

    def mousePressEvent(self, event):
        """Capture mouse press event on video preview window"""
        event.accept()
        if event.button() == Qt.MiddleButton and self.zoom > 1.0:
            self.mouse_pressed = True
            self.mouse_dragging = False
            self.mouse_position = event.pos()
            self.middle_pan_active = True
            self.setCursor(Qt.ClosedHandCursor)
            if not self._is_playing():
                openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
            return
        self.mouse_pressed = True
        self.mouse_dragging = False
        self.mouse_position = event.pos()
        self.transform_mode = None if self.region_enabled else self.hover_transform_mode
        self.rotation_drag_value = None
        self.margin_box_drag_anchor = None
        self.setCursor(Qt.CrossCursor if self.region_enabled else self.hover_cursor)

        if self.region_enabled and self.region_selection_mode not in ("point", "annotate") and event.button() == Qt.LeftButton:
            self._ensure_region_transform()
            point = self._clamp_region_point(
                self.region_transform_inverted.map(event.pos()),
                include_edges=True)
            region_rect = self._scope_region_rect()
            self.region_mode = None
            self.region_press_outside = False
            for mode, handle_rect in self._scope_region_corner_rects().items():
                if handle_rect.contains(point):
                    self.region_mode = mode
                    break
            if self.region_mode is None and region_rect and region_rect.contains(point):
                self.region_mode = "move"
            if self.region_mode is None:
                self.region_mode = "draw"
                self.region_press_outside = True
                self.scope_region_drag_anchor = QPointF(point)
                self._apply_scope_region_rect(QRectF(point, point), emit_signal=True, enforce_min=False)
            if not self._is_playing():
                openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
            log.debug('mousePressEvent: Stop caching frames on timeline')
            return

        if self.region_enabled and self.region_selection_mode == "point" and event.button() == Qt.LeftButton:
            self._ensure_region_transform()
            point = self.region_transform_inverted.map(event.pos())
            point = self._clamp_region_point(point)
            mods = QCoreApplication.instance().keyboardModifiers()
            if modifiers_has(mods, Qt.ControlModifier):
                self.region_points_negative.append(point)
            elif modifiers_has(mods, Qt.ShiftModifier):
                self.region_points_positive.append(point)
            else:
                # Default click resets to a single positive point.
                self.region_points_positive = [point]
                self.region_points_negative = []
            self.update()
        elif self.region_enabled and self.region_selection_mode == "annotate" and event.button() == Qt.LeftButton:
            self._ensure_region_transform()
            tool = str(self.region_annotation_tool or "positive_point")
            point = self.region_transform_inverted.map(event.pos())
            point = self._clamp_region_point(point, include_edges=tool.endswith("_rect"))
            if bool(self.region_annotation_inherited):
                # First edit on a carried frame should replace inherited selections.
                self.region_points_positive = []
                self.region_points_negative = []
                self.region_rects_positive = []
                self.region_rects_negative = []
                self.region_rect_drag_start = None
                self.region_rect_drag_current = None
                self.region_annotation_inherited = False
            if tool == "positive_point":
                if not self._can_add_region_annotation(tool):
                    self.regionAnnotationLimitReached.emit()
                    self.update()
                    return
                self.region_points_positive.append(point)
                self.update()
                self.regionAnnotationChanged.emit()
            elif tool == "negative_point":
                if not self._can_add_region_annotation(tool):
                    self.regionAnnotationLimitReached.emit()
                    self.update()
                    return
                self.region_points_negative.append(point)
                self.update()
                self.regionAnnotationChanged.emit()
            elif tool in ("positive_rect", "negative_rect"):
                if not self._can_add_region_annotation(tool):
                    self.regionAnnotationLimitReached.emit()
                    self.update()
                    return
                self.region_rect_drag_start = QPointF(point)
                self.region_rect_drag_current = QPointF(point)
                self.update()

        # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
        get_app().updates.ignore_history = True

        if self.transforming_clips or self.transforming_effect:
            self.transaction_id = str(uuid.uuid4())
            self.original_clip_data_map = {c.id: json.loads(json.dumps(c.data)) for c in self.transforming_clips} if self.transforming_clips else {}
            self.original_effect_data = json.loads(json.dumps(self.transforming_effect.data)) if self.transforming_effect else None
            get_app().updates.transaction_id = self.transaction_id
            if self.transform_mode == 'draw_margin_box' and self.transform:
                self.margin_box_drag_anchor = self.transform.inverted()[0].map(event.pos())
        else:
            self.transaction_id = None
            self.original_clip_data_map = {}
            self.original_effect_data = None

        # Disable video caching during drag operation (for performance reasons)
        if not self._is_playing():
            openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
        log.debug('mousePressEvent: Stop caching frames on timeline')

    def mouseReleaseEvent(self, event):
        event.accept()
        """Capture mouse release event on video preview window"""
        if event.button() == Qt.MiddleButton and getattr(self, "middle_pan_active", False):
            self.mouse_pressed = False
            self.mouse_dragging = False
            self.middle_pan_active = False
            self.setCursor(Qt.OpenHandCursor if self.zoom > 1.0 else Qt.ArrowCursor)
            return
        was_dragging = self.mouse_dragging
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.transform_mode = None
        self.hover_transform_mode = None
        self.rotation_drag_value = None
        self.margin_box_drag_anchor = None

        if self.region_enabled and self.region_selection_mode == "annotate":
            if self.region_rect_drag_start is not None and self.region_rect_drag_current is not None:
                rect = QRectF(self.region_rect_drag_start, self.region_rect_drag_current).normalized()
                if rect.width() >= 2.0 and rect.height() >= 2.0:
                    tool = str(self.region_annotation_tool or "positive_rect")
                    if self._can_add_region_annotation(tool):
                        if tool == "negative_rect":
                            self.region_rects_negative.append(rect)
                        else:
                            self.region_rects_positive.append(rect)
                    else:
                        self.regionAnnotationLimitReached.emit()
            self.region_rect_drag_start = None
            self.region_rect_drag_current = None
            self.region_mode = None
            self.scope_region_drag_anchor = None
            self.update()
            self.regionAnnotationChanged.emit()

        # Save region image data (as QImage)
        # This can be used other widgets to display the selected region
        if (
            self.region_enabled
            and self.region_selection_mode not in ("point", "annotate")
            and self.regionTopLeftHandle is not None
            and self.regionBottomRightHandle is not None
        ):
            if self.region_mode == "draw" and self.region_press_outside and not was_dragging:
                self.region_mode = None
                self.region_press_outside = False
                self.scope_region_drag_anchor = None
                self.scopeRegionCancelled.emit()
                return
            region_rect = self._scope_region_rect()
            if region_rect:
                self._apply_scope_region_rect(region_rect, emit_signal=True, enforce_min=True)
                region_rect = self._scope_region_rect()

            # Get region coordinates
            mapped_region_rect = self.region_transform.mapToPolygon(region_rect.toRect()).boundingRect()

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
            self.regionRectChanged.emit()
            self.region_mode = None
            self.region_press_outside = False
            self.scope_region_drag_anchor = None
            return

        self.region_mode = None
        self.region_press_outside = False
        self.scope_region_drag_anchor = None

        # Inform UpdateManager to accept updates, and only store our final update
        get_app().updates.ignore_history = False

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
            get_app().updates.transaction_id = self.transaction_id
            get_app().updates.apply_last_action_to_history(self.original_effect_data)

        # Clear transaction and data
        get_app().updates.transaction_id = None
        get_app().updates.ignore_history = False
        self.original_clip_data = None
        self.original_clip_data_map = {}
        self.original_effect_data = None
        self.setCursor(Qt.ArrowCursor)

    def rotateCursor(self, pixmap, rotation, shear_x, shear_y):
        """Rotate cursor based on the current transform"""
        fallback = None
        if isinstance(pixmap, tuple):
            pixmap, fallback = pixmap
        if pixmap is None or pixmap.isNull():
            if fallback is None:
                fallback = Qt.ArrowCursor
            return QCursor(fallback)
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

        effect_class_name = (
            getattr(self.transforming_effect_object.info, 'class_name', '')
            if self.transforming_effect_object else ''
        )
        is_margin_box_effect = (
            self.transforming_effect and self.transforming_effect_object
            and self._effect_has_margin_box()
        )
        is_tracked_object_effect = (
            self.transforming_effect and self.transforming_effect_object
            and getattr(self.transforming_effect_object.info, 'has_tracked_object', False)
        )
        is_crop_effect = effect_class_name == 'Crop'
        if is_margin_box_effect:
            handle_uis = [h for h in handle_uis if not h["mode"].startswith('shear_') and h["mode"] != 'origin']
            non_handle_uis["outside"] = (
                {"mode": None, "cursor": None}
                if is_crop_effect else {"mode": 'draw_margin_box', "cursor": "cross"}
            )
        elif is_tracked_object_effect:
            handle_uis = [
                h for h in handle_uis
                if not h["mode"].startswith('shear_') and h["mode"] != 'origin'
            ]
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

        # If not over any handles, determine inside/outside active rectangle
        r = non_handle_uis.get("region")
        if self.transform.mapToPolygon(r.toRect()).containsPoint(event.pos(), Qt.OddEvenFill):
            nh = non_handle_uis.get("inside", {})
        else:
            nh = non_handle_uis.get("outside", {})
            if is_margin_box_effect and not is_crop_effect:
                try:
                    local_point = self.transform.inverted()[0].map(event.pos())
                    full_bounds = getattr(self, "marginBoxFullBounds", None)
                    if not full_bounds or not full_bounds.contains(local_point):
                        nh = {"mode": None, "cursor": None}
                except Exception:
                    nh = {"mode": None, "cursor": None}
        cursor_name = nh.get("cursor")
        if cursor_name == "cross":
            cursor = Qt.CrossCursor
        elif cursor_name:
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

        if getattr(self, "middle_pan_active", False):
            diff = event.pos() - self.mouse_position
            self.pan_x += diff.x()
            self.pan_y += diff.y()
            self.pan_x, self.pan_y = self._clamp_pan()
            self.mouse_position = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            self.update()
            self.mutex.unlock()
            return

        if self.region_enabled:
            if self.region_selection_mode == "annotate":
                self.setCursor(Qt.CrossCursor)
                self._ensure_region_transform()
                if self.region_rect_drag_start is not None and self.mouse_pressed:
                    current = self.region_transform_inverted.map(event.pos())
                    self.region_rect_drag_current = self._clamp_region_point(current, include_edges=True)
                    self.update()
                self.mouse_position = event.pos()
                self.mutex.unlock()
                return

            if self.region_selection_mode == "point":
                self.setCursor(Qt.CrossCursor)
                self.mouse_position = event.pos()
                self.mutex.unlock()
                return

            self._ensure_region_transform()
            point = self._clamp_region_point(
                self.region_transform_inverted.map(event.pos()),
                include_edges=True)
            region_rect = self._scope_region_rect()
            corner_rects = self._scope_region_corner_rects()
            hover_mode = None
            for mode, handle_rect in corner_rects.items():
                if handle_rect.contains(point):
                    hover_mode = mode
                    break

            if hover_mode in ("scale_top_left", "scale_bottom_right"):
                self.setCursor(self.rotateCursor(self.cursors.get('resize_fdiag'), 0, 0, 0))
            elif hover_mode in ("scale_top_right", "scale_bottom_left"):
                self.setCursor(self.rotateCursor(self.cursors.get('resize_bdiag'), 0, 0, 0))
            elif region_rect and region_rect.contains(point):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.CrossCursor)

            if self.mouse_dragging:
                last_point = self._clamp_region_point(
                    self.region_transform_inverted.map(self.mouse_position),
                    include_edges=True)
                diff_x = point.x() - last_point.x()
                diff_y = point.y() - last_point.y()

                if self.region_mode == "draw":
                    anchor = self.scope_region_drag_anchor or QPointF(point)
                    self._apply_scope_region_rect(QRectF(anchor, point), emit_signal=True, enforce_min=False)
                elif self.region_mode == "move" and region_rect:
                    moved = QRectF(region_rect)
                    moved.translate(diff_x, diff_y)
                    bounds_w, bounds_h = self._scope_region_bounds()
                    if moved.left() < 0.0:
                        moved.translate(-moved.left(), 0.0)
                    if moved.top() < 0.0:
                        moved.translate(0.0, -moved.top())
                    if moved.right() > bounds_w:
                        moved.translate(bounds_w - moved.right(), 0.0)
                    if moved.bottom() > bounds_h:
                        moved.translate(0.0, bounds_h - moved.bottom())
                    self._apply_scope_region_rect(moved, emit_signal=True, enforce_min=False)
                elif region_rect and self.region_mode in corner_rects:
                    left = region_rect.left()
                    top = region_rect.top()
                    right = region_rect.right()
                    bottom = region_rect.bottom()
                    if self.region_mode == "scale_top_left":
                        left = point.x()
                        top = point.y()
                    elif self.region_mode == "scale_top_right":
                        right = point.x()
                        top = point.y()
                    elif self.region_mode == "scale_bottom_left":
                        left = point.x()
                        bottom = point.y()
                    elif self.region_mode == "scale_bottom_right":
                        right = point.x()
                        bottom = point.y()
                    self._apply_scope_region_rect(QRectF(QPointF(left, top), QPointF(right, bottom)), emit_signal=True, enforce_min=False)

                self.mouse_position = event.pos()
            else:
                self.mouse_position = event.pos()

            self.update()
            self.mutex.unlock()
            return

        if self.zoom > 1.0 and not self.mouse_pressed:
            self.setCursor(Qt.OpenHandCursor)

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
                    self._apply_delta_to_clips(
                        'origin_x', origin_x - raw_properties.get('origin_x').get('value'),
                        fps_float, frame_number=clip_frame_number)
                    self._apply_delta_to_clips(
                        'origin_y', origin_y - raw_properties.get('origin_y').get('value'),
                        fps_float, frame_number=clip_frame_number)

                elif self.transform_mode == 'location':
                    # Get current keyframe value
                    location_x = raw_properties.get('location_x').get('value')
                    location_y = raw_properties.get('location_y').get('value')

                    base_w, base_h = self._clip_source_dimensions(
                        self.transforming_clip, self.transforming_clip_object, clip_frame_number)
                    (
                        _source_w,
                        _source_h,
                        scaled_w,
                        scaled_h,
                        anchored_x,
                        anchored_y,
                        layout_x,
                        layout_y,
                        layout_width,
                        layout_height) = self._clip_location_geometry(
                            base_w, base_h, self.transforming_clip, raw_properties, viewport_rect)

                    # Convert from screen-pixel motion to libopenshot's normalized
                    # location coordinates, which are relative to the gravity anchor
                    # and the distance to the offscreen edge.
                    current_x_offset = self._location_offset(
                        location_x, anchored_x - layout_x, layout_width, scaled_w)
                    current_y_offset = self._location_offset(
                        location_y, anchored_y - layout_y, layout_height, scaled_h)
                    location_x = self._location_value_from_offset(
                        current_x_offset + x_motion, anchored_x - layout_x, layout_width, scaled_w)
                    location_y = self._location_value_from_offset(
                        current_y_offset + y_motion, anchored_y - layout_y, layout_height, scaled_h)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'location_x', location_x,
                        refresh=False)
                    self.updateClipProperty(
                        self.transforming_clips[0].id, clip_frame_number,
                        'location_y', location_y)
                    self._apply_delta_to_clips(
                        'location_x', location_x - raw_properties.get('location_x').get('value'),
                        fps_float, frame_number=clip_frame_number)
                    self._apply_delta_to_clips(
                        'location_y', location_y - raw_properties.get('location_y').get('value'),
                        fps_float, frame_number=clip_frame_number)

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
                    self._apply_delta_to_clips(
                        'shear_x', shear_x - raw_properties.get('shear_x').get('value'),
                        fps_float, frame_number=clip_frame_number)

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
                    self._apply_delta_to_clips(
                        'shear_x', shear_x - raw_properties.get('shear_x').get('value'),
                        fps_float, frame_number=clip_frame_number)

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
                    self._apply_delta_to_clips(
                        'shear_y', shear_y - raw_properties.get('shear_y').get('value'),
                        fps_float, frame_number=clip_frame_number)

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
                    self._apply_delta_to_clips(
                        'shear_y', shear_y - raw_properties.get('shear_y').get('value'),
                        fps_float, frame_number=clip_frame_number)

                elif self.transform_mode == 'rotation':
                    # Get current rotation keyframe value
                    if self.rotation_drag_value is None:
                        self.rotation_drag_value = raw_properties.get('rotation').get('value')
                    rotation = self.rotation_drag_value
                    scale_x = max(float(raw_properties.get('scale_x').get('value')), 0.001)
                    scale_y = max(float(raw_properties.get('scale_y').get('value')), 0.001)

                    # Calculate new location coordinates
                    is_on_right = event.pos().x() > self.originHandle.x()
                    is_on_top = event.pos().y() < self.originHandle.y()

                    x_adjust = x_motion / ((self.clipBounds.width() * scale_x) / 90)
                    rotation += (x_adjust if is_on_top else -x_adjust)

                    y_adjust = y_motion / ((self.clipBounds.height() * scale_y) / 90)
                    rotation += (y_adjust if is_on_right else -y_adjust)

                    self.rotation_drag_value = rotation
                    mods = QCoreApplication.instance().keyboardModifiers()
                    if modifiers_has(mods, Qt.ControlModifier) or modifiers_has(mods, Qt.ShiftModifier):
                        rotation = self._snap_angle(rotation, 15.0)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clips[0].id,
                        clip_frame_number,
                        'rotation', rotation)
                    self._apply_delta_to_clips(
                        'rotation', rotation - raw_properties.get('rotation').get('value'),
                        fps_float, frame_number=clip_frame_number)

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

                    if modifiers_has(QCoreApplication.instance().keyboardModifiers(), Qt.ControlModifier):
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
                        self._apply_delta_to_clips(
                            'scale_x', scale_x - raw_properties.get('scale_x').get('value'),
                            fps_float, frame_number=clip_frame_number)
                    if scale_y != 0.001:
                        self.updateClipProperty(
                            self.transforming_clips[0].id, clip_frame_number,
                            'scale_y', scale_y)
                        self._apply_delta_to_clips(
                            'scale_y', scale_y - raw_properties.get('scale_y').get('value'),
                            fps_float, frame_number=clip_frame_number)

            # Force re-paint
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
                    self.hover_transform_mode = None
                    self.transform_mode = None
                    self.hover_cursor = Qt.ArrowCursor
                    self.setCursor(self.hover_cursor)
                    self.mouse_position = event.pos()
                    self.mutex.unlock()
                    return

                obj_id, raw_properties = self._resolve_tracked_object(objects, raw_properties)
                if not obj_id or not raw_properties:
                    self.hover_transform_mode = None
                    self.transform_mode = None
                    self.hover_cursor = Qt.ArrowCursor
                    self.setCursor(self.hover_cursor)
                    self.mouse_position = event.pos()
                    self.mutex.unlock()
                    return

                if not self._tracked_object_visible(raw_properties):
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

                        # Update keyframe values (or create new ones)
                        self.updateEffectProperties(
                            self.transforming_effect.id,
                            clip_frame_number,
                            obj_id,
                            {
                                'delta_x': location_x,
                                'delta_y': location_y,
                            })

                    elif self.transform_mode == 'rotation':
                        # Get current rotation keyframe value
                        if self.rotation_drag_value is None:
                            self.rotation_drag_value = raw_properties.get('rotation').get('value')
                        rotation = self.rotation_drag_value
                        scale_x = max(float(raw_properties.get('scale_x').get('value')), 0.001)
                        scale_y = max(float(raw_properties.get('scale_y').get('value')), 0.001)

                        # Calculate new location coordinates
                        is_on_right = event.pos().x() > self.originHandle.x()
                        is_on_top = event.pos().y() < self.originHandle.y()

                        x_adjust = x_motion / (self.clipBounds.width() * scale_x / 90)
                        rotation += (x_adjust if is_on_top else -x_adjust)

                        y_adjust = y_motion / (self.clipBounds.height() * scale_y / 90)
                        rotation += (y_adjust if is_on_right else -y_adjust)

                        self.rotation_drag_value = rotation
                        mods = QCoreApplication.instance().keyboardModifiers()
                        if modifiers_has(mods, Qt.ControlModifier) or modifiers_has(mods, Qt.ShiftModifier):
                            rotation = self._snap_angle(rotation, 15.0)

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

                        if modifiers_has(QCoreApplication.instance().keyboardModifiers(), Qt.ControlModifier):
                            # If CTRL key is pressed, fix the scale_y to the correct aspect ratio
                            if scale_x:
                                scale_y = scale_x
                            elif scale_y:
                                scale_x = scale_y

                        # Update keyframe values (or create new ones)
                        updates = {}
                        if scale_x != 0.001:
                            updates['scale_x'] = scale_x
                        if scale_y != 0.001:
                            updates['scale_y'] = scale_y
                        if updates:
                            self.updateEffectProperties(
                                self.transforming_effect.id,
                                clip_frame_number,
                                obj_id,
                                updates)

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

                    self.updateEffectProperties(
                        eff_id,
                        clip_frame_number,
                        None,
                        updates,
                    )

            elif self._effect_has_margin_box():
                raw_properties = json.loads(
                    self.transforming_effect_object.PropertiesJSON(clip_frame_number))
                if not self._effect_has_margin_box(raw_properties):
                    self.mouse_position = event.pos()
                    self.mutex.unlock()
                    return

                clip_props_for_cursors = json.loads(self.transforming_clip_object.PropertiesJSON(clip_frame_number))
                clip_rot = clip_props_for_cursors.get('rotation', {}).get('value', 0.0)
                clip_sx = clip_props_for_cursors.get('shear_x', {}).get('value', 0.0)
                clip_sy = clip_props_for_cursors.get('shear_y', {}).get('value', 0.0)

                margin_left = raw_properties.get('left', {}).get('value', 0.0)
                margin_top = raw_properties.get('top', {}).get('value', 0.0)
                margin_right = raw_properties.get('right', {}).get('value', 0.0)
                margin_bottom = raw_properties.get('bottom', {}).get('value', 0.0)

                self.checkTransformMode(clip_rot, clip_sx, clip_sy, event)

                if self.transform_mode:
                    full_bounds = getattr(self, "marginBoxFullBounds", None)
                    if not full_bounds:
                        self.mouse_position = event.pos()
                        self.mutex.unlock()
                        return
                    inverted_transform = self.transform.inverted()[0]
                    current = inverted_transform.map(event.pos())
                    previous = inverted_transform.map(self.mouse_position)
                    x_motion = current.x() - previous.x()
                    y_motion = current.y() - previous.y()
                    width = max(full_bounds.width(), 0.0001)
                    height = max(full_bounds.height(), 0.0001)

                    eff_id = self.transforming_effect.id

                    new_left = margin_left
                    new_top = margin_top
                    new_right = margin_right
                    new_bottom = margin_bottom

                    if self.transform_mode == 'draw_margin_box':
                        if self.margin_box_drag_anchor is None:
                            self.margin_box_drag_anchor = previous
                        anchor = self.margin_box_drag_anchor
                        left_px = min(max(min(anchor.x(), current.x()), 0.0), width)
                        top_px = min(max(min(anchor.y(), current.y()), 0.0), height)
                        right_px = min(max(max(anchor.x(), current.x()), 0.0), width)
                        bottom_px = min(max(max(anchor.y(), current.y()), 0.0), height)
                        new_left = left_px / width
                        new_top = top_px / height
                        new_right = 1.0 - (right_px / width)
                        new_bottom = 1.0 - (bottom_px / height)
                    elif self.transform_mode == 'location':
                        dx = x_motion / width
                        dy = y_motion / height
                        dx = max(-margin_left, min(dx, margin_right))
                        dy = max(-margin_top, min(dy, margin_bottom))
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

                    new_left, new_top, new_right, new_bottom = self._clamp_margin_values(
                        new_left,
                        new_top,
                        new_right,
                        new_bottom,
                        prefer_left=('left' in self.transform_mode or self.transform_mode == 'location'),
                        prefer_top=('top' in self.transform_mode or self.transform_mode == 'location'),
                    )

                    updates = {}
                    if abs(new_left - margin_left) > 0.0001:
                        updates['left'] = new_left
                    if abs(new_top - margin_top) > 0.0001:
                        updates['top'] = new_top
                    if abs(new_right - margin_right) > 0.0001:
                        updates['right'] = new_right
                    if abs(new_bottom - margin_bottom) > 0.0001:
                        updates['bottom'] = new_bottom

                    self.updateEffectProperties(
                        eff_id,
                        clip_frame_number,
                        None,
                        updates,
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

    def _ensure_region_transform(self):
        viewport = self.centeredViewport(self.width(), self.height())
        self.region_transform = QTransform()
        rx = viewport.x()
        ry = viewport.y()
        if rx or ry:
            self.region_transform.translate(rx, ry)
        if self.zoom:
            self.region_transform.scale(self.zoom, self.zoom)
        self.region_transform_inverted = self.region_transform.inverted()[0]

    def _clamp_region_point(self, point, include_edges=False):
        max_w = float(self.curr_frame_size.width()) if self.curr_frame_size else 0.0
        max_h = float(self.curr_frame_size.height()) if self.curr_frame_size else 0.0
        if max_w <= 0.0 or max_h <= 0.0:
            viewport = self.centeredViewport(self.width(), self.height())
            max_w = float(viewport.width()) / max(self.zoom, 0.001)
            max_h = float(viewport.height()) / max(self.zoom, 0.001)
        max_x = max_w if include_edges else max(max_w - 1.0, 0.0)
        max_y = max_h if include_edges else max(max_h - 1.0, 0.0)
        x = min(max(float(point.x()), 0.0), max(max_x, 0.0))
        y = min(max(float(point.y()), 0.0), max(max_y, 0.0))
        return QPointF(x, y)

    def _region_annotation_limit(self, name, default):
        limits = getattr(self, "region_annotation_limits", {}) or {}
        try:
            return int(limits.get(name, default))
        except Exception:
            return int(default)

    def _negative_annotation_count(self):
        return len(self.region_points_negative or []) + len(self.region_rects_negative or [])

    def _positive_prompt_slots_used(self):
        return len(self.region_points_positive or []) + (2 * len(self.region_rects_positive or []))

    def _can_add_region_annotation(self, tool):
        tool = str(tool or "")
        prompt_slots = self._region_annotation_limit("prompt_slots", 6)
        max_positive_rects = self._region_annotation_limit("positive_rects", 3)
        max_negative_filters = self._region_annotation_limit("negative_filters", 8)

        if tool == "positive_point":
            return self._positive_prompt_slots_used() < prompt_slots
        if tool == "positive_rect":
            if len(self.region_rects_positive or []) >= max_positive_rects:
                return False
            return self._positive_prompt_slots_used() + 2 <= prompt_slots
        if tool in ("negative_point", "negative_rect"):
            return self._negative_annotation_count() < max_negative_filters
        return True

    def updateEffectProperty(self, effect_id, frame_number, obj_id, property_key, new_value, refresh=True):
        """Update a keyframe property to a new value, adding or updating keyframes as needed"""
        self.updateEffectProperties(
            effect_id,
            frame_number,
            obj_id,
            {property_key: new_value},
            refresh=refresh)

    def updateEffectProperties(self, effect_id, frame_number, obj_id, property_updates, refresh=True):
        """Update one or more effect keyframe properties in a single project update."""
        if not property_updates:
            return

        c = Effect.get(id=effect_id)

        if not c:
            # No clip found
            return

        # Clamp frame number to a sane range (effects share clip timing, so keep >= 1)
        frame_number = max(1, int(round(frame_number)))
        updated_properties = {}

        try:
            if obj_id is not None:
                objects = c.data.setdefault('objects', {})
                props = objects.setdefault(obj_id, {})
            else:
                props = c.data
        except (TypeError, KeyError):
            log.error("Corrupted project data!", exc_info=1)
            return

        for property_key, new_value in property_updates.items():
            found_point = False
            if property_key not in props:
                props[property_key] = {"Points": []}
            if not isinstance(props[property_key], dict) or "Points" not in props[property_key]:
                props[property_key] = {"Points": []}
            points_list = props[property_key].setdefault("Points", [])

            if property_key in {'left', 'top', 'right', 'bottom'} and new_value is not None:
                new_value = min(max(float(new_value), 0.0), 1.0)

            for point in points_list:
                co = point.get("co", {})

                if co.get("X") == frame_number:
                    found_point = True
                    point.update({
                        "co": {"X": frame_number, "Y": float(new_value)},
                        "interpolation": openshot.BEZIER,
                    })

            if not found_point and new_value is not None:
                log.info("Creating new point at X=%s", frame_number)
                points_list.append({
                    'co': {'X': frame_number, 'Y': float(new_value)},
                    'interpolation': openshot.BEZIER
                    })

            if new_value is not None:
                updated_properties[property_key] = props.get(property_key, {"Points": []})

        if updated_properties:
            # Reduce # of clip properties we are saving (performance boost)
            if obj_id is not None:
                c.data = {
                    'objects': {
                        obj_id: updated_properties
                    }
                }
            else:
                c.data = updated_properties
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

    def _apply_delta_to_clips(self, property_key, delta, fps_float, frame_number=None):
        for clip, obj in zip(self.transforming_clips[1:], self.transforming_clip_objects[1:]):
            if frame_number is None:
                frame = self._get_clip_frame_number(clip, fps_float)
            else:
                frame = max(1, int(round(frame_number)))
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
        reader = clip.data.get('reader', {})
        width = float(reader.get('width', self.width()))
        height = float(reader.get('height', self.height())) * pixel_adjust

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

    @staticmethod
    def _location_offset(location, anchored_position, canvas_size, clip_size):
        """Match libopenshot normalized location semantics for one axis."""
        location = float(location)
        anchored_position = float(anchored_position)
        canvas_size = float(canvas_size)
        clip_size = float(clip_size)
        if location < 0.0:
            return location * (anchored_position + clip_size)
        return location * (canvas_size - anchored_position)

    @staticmethod
    def _location_value_from_offset(offset, anchored_position, canvas_size, clip_size):
        """Inverse of _location_offset(), used when dragging transform handles."""
        offset = float(offset)
        anchored_position = float(anchored_position)
        canvas_size = float(canvas_size)
        clip_size = float(clip_size)
        if offset < 0.0:
            basis = anchored_position + clip_size
        else:
            basis = canvas_size - anchored_position
        if abs(basis) < 0.0001:
            return 0.0
        return offset / basis

    def _clip_location_geometry(self, base_width, base_height, clip, raw_properties, viewport_rect):
        player_width = viewport_rect.width()
        player_height = viewport_rect.height()
        margin = max(float(raw_properties.get('margin', {}).get('value', 0.0)), 0.0)
        margin = min(margin, 0.5)
        margin_pixels = margin * min(player_width, player_height)
        layout_x = margin_pixels
        layout_y = margin_pixels
        layout_width = max(player_width - (margin_pixels * 2.0), 1.0)
        layout_height = max(player_height - (margin_pixels * 2.0), 1.0)

        source_size = QSizeF(base_width, base_height)
        scale_mode = clip.data['scale']
        parent_memo = raw_properties.get('parentObjectId', {}).get('memo', '')
        if parent_memo:
            scale_mode = openshot.SCALE_STRETCH

        if scale_mode == openshot.SCALE_FIT:
            source_size.scale(layout_width, layout_height, Qt.KeepAspectRatio)
        elif scale_mode == openshot.SCALE_STRETCH:
            source_size.scale(layout_width, layout_height, Qt.IgnoreAspectRatio)
        elif scale_mode == openshot.SCALE_CROP:
            source_size.scale(layout_width, layout_height, Qt.KeepAspectRatioByExpanding)
        elif scale_mode == openshot.SCALE_NONE:
            try:
                project_width = float(get_app().project.get("width") or player_width)
                project_height = float(get_app().project.get("height") or player_height)
            except Exception:
                project_width = float(player_width)
                project_height = float(player_height)
            if project_width > 0.0 and project_height > 0.0:
                source_size = QSizeF(
                    source_size.width() * (player_width / project_width),
                    source_size.height() * (player_height / project_height))

        source_width = max(source_size.width(), 0.0001)
        source_height = max(source_size.height(), 0.0001)

        sx = max(float(raw_properties.get('scale_x').get('value')), 0.001)
        sy = max(float(raw_properties.get('scale_y').get('value')), 0.001)
        scaled_width = source_width * sx
        scaled_height = source_height * sy

        gravity = clip.data['gravity']
        anchored_x = 0.0
        anchored_y = 0.0
        if gravity == openshot.GRAVITY_TOP_LEFT:
            anchored_x = layout_x
            anchored_y = layout_y
        elif gravity == openshot.GRAVITY_TOP:
            anchored_x = layout_x + ((layout_width - scaled_width) / 2.0)
            anchored_y = layout_y
        elif gravity == openshot.GRAVITY_TOP_RIGHT:
            anchored_x = layout_x + layout_width - scaled_width
            anchored_y = layout_y
        elif gravity == openshot.GRAVITY_LEFT:
            anchored_x = layout_x
            anchored_y = layout_y + ((layout_height - scaled_height) / 2.0)
        elif gravity == openshot.GRAVITY_CENTER:
            anchored_x = layout_x + ((layout_width - scaled_width) / 2.0)
            anchored_y = layout_y + ((layout_height - scaled_height) / 2.0)
        elif gravity == openshot.GRAVITY_RIGHT:
            anchored_x = layout_x + layout_width - scaled_width
            anchored_y = layout_y + ((layout_height - scaled_height) / 2.0)
        elif gravity == openshot.GRAVITY_BOTTOM_LEFT:
            anchored_x = layout_x
            anchored_y = layout_y + layout_height - scaled_height
        elif gravity == openshot.GRAVITY_BOTTOM:
            anchored_x = layout_x + ((layout_width - scaled_width) / 2.0)
            anchored_y = layout_y + layout_height - scaled_height
        elif gravity == openshot.GRAVITY_BOTTOM_RIGHT:
            anchored_x = layout_x + layout_width - scaled_width
            anchored_y = layout_y + layout_height - scaled_height

        return (
            source_width,
            source_height,
            scaled_width,
            scaled_height,
            anchored_x,
            anchored_y,
            layout_x,
            layout_y,
            layout_width,
            layout_height)

    def _clip_display_rect(self, base_width, base_height, clip, raw_properties, viewport_rect):
        player_width = viewport_rect.width()
        player_height = viewport_rect.height()

        (
            source_width,
            source_height,
            scaled_width,
            scaled_height,
            anchored_x,
            anchored_y,
            layout_x,
            layout_y,
            layout_width,
            layout_height) = (
            self._clip_location_geometry(base_width, base_height, clip, raw_properties, viewport_rect))

        x = viewport_rect.x() + anchored_x
        y = viewport_rect.y() + anchored_y

        location_x = float(raw_properties.get('location_x', {}).get('value', 0.0))
        location_y = float(raw_properties.get('location_y', {}).get('value', 0.0))
        x += self._location_offset(location_x, anchored_x - layout_x, layout_width, scaled_width)
        y += self._location_offset(location_y, anchored_y - layout_y, layout_height, scaled_height)

        return QRectF(x, y, source_width, source_height)

    def _clip_rect(self, clip, clip_object, viewport_rect, frame_number):
        raw_properties = json.loads(clip_object.PropertiesJSON(frame_number))

        skip_id = None
        if self.transforming_effect_object and hasattr(self.transforming_effect_object, 'Id'):
            skip_id = self.transforming_effect_object.Id()

        base_width, base_height = self._clip_source_dimensions(clip, clip_object, frame_number, skip_id)
        rect = self._clip_display_rect(base_width, base_height, clip, raw_properties, viewport_rect)

        return rect, raw_properties

    def _tracked_object_visible(self, object_props):
        visible_prop = object_props.get("visible")
        if isinstance(visible_prop, dict):
            return int(visible_prop.get("value", 1)) == 1
        if visible_prop is None:
            return True
        return bool(visible_prop)

    def _resolve_tracked_object(self, objects, raw_properties=None):
        """Resolve selected tracked-object key from effect data."""
        if not objects:
            return None, None

        selected_idx = None
        if raw_properties:
            selected_prop = raw_properties.get("selected_object_index")
            if isinstance(selected_prop, dict):
                selected_idx = selected_prop.get("value")
            else:
                selected_idx = selected_prop
        if selected_idx in (None, "", "None") and self.transforming_effect:
            selected_idx = self.transforming_effect.data.get("selected_object_index")
            if isinstance(selected_idx, dict):
                points = selected_idx.get("Points") or []
                if points:
                    selected_idx = points[0].get("co", {}).get("Y")

        if selected_idx not in (None, "", "None"):
            try:
                selected_idx = str(int(float(selected_idx)))
            except (TypeError, ValueError):
                selected_idx = str(selected_idx)
            if selected_idx == "-1":
                return None, None
            if selected_idx in objects:
                return selected_idx, objects[selected_idx]

            # Newer object IDs are "<effect-uuid>-<index>".
            suffix = f"-{selected_idx}"
            for object_id, object_props in objects.items():
                if object_id.endswith(suffix):
                    return object_id, object_props

        for object_id, object_props in objects.items():
            if str(object_id).lower() == "all":
                continue
            if self._tracked_object_visible(object_props):
                return object_id, object_props

        for object_id, object_props in objects.items():
            if str(object_id).lower() != "all":
                return object_id, object_props
        return None, None

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

        # Selection/transform changes affect overlay UI, not timeline frame.
        if need_refresh:
            self.update()
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

        # Transform target changes affect overlay UI, not timeline frame.
        if need_refresh:
            self.update()
            win.propertyTableView.select_frame(win.preview_thread.player.Position())
        self.update_title()

    def regionTriggered(self, clip_id):
        """Handle the 'select region' signal when it's emitted"""
        # Clear transform
        self.region_enabled = bool(clip_id)
        if not self.region_enabled:
            self.region_points = []
            self.region_points_positive = []
            self.region_points_negative = []
            self.region_rects_positive = []
            self.region_rects_negative = []
            self.region_rect_drag_start = None
            self.region_rect_drag_current = None
            self.region_mask_preview_image = None
            self.region_mask_preview_frame = None
            self.regionTopLeftHandle = None
            self.regionBottomRightHandle = None
        self.update()
        self.update_title()

    def _scope_region_bounds(self):
        width = float(self.curr_frame_size.width()) if self.curr_frame_size else 0.0
        height = float(self.curr_frame_size.height()) if self.curr_frame_size else 0.0
        if width <= 0.0 or height <= 0.0:
            viewport = self.centeredViewport(self.width(), self.height())
            width = float(viewport.width()) / max(self.zoom, 0.001)
            height = float(viewport.height()) / max(self.zoom, 0.001)
        return max(width, 1.0), max(height, 1.0)

    def _scope_region_min_size(self):
        return 1.0, 1.0

    def _max_pan_offsets(self, width=None, height=None, zoom=None):
        if width is None:
            width = self.width()
        if height is None:
            height = self.height()
        if zoom is None:
            zoom = self.zoom
        window_size = QSizeF(width, height)
        aspectRatio = self.aspect_ratio.ToFloat() * self.pixel_ratio.ToFloat()
        viewport_size = QSizeF(aspectRatio, 1).scaled(window_size, Qt.KeepAspectRatio) * zoom
        return (
            max(0.0, (viewport_size.width() - window_size.width()) * 0.5),
            max(0.0, (viewport_size.height() - window_size.height()) * 0.5),
        )

    def _clamp_pan(self, pan_x=None, pan_y=None, width=None, height=None, zoom=None):
        if pan_x is None:
            pan_x = self.pan_x
        if pan_y is None:
            pan_y = self.pan_y
        max_x, max_y = self._max_pan_offsets(width=width, height=height, zoom=zoom)
        return (
            min(max(float(pan_x), -max_x), max_x),
            min(max(float(pan_y), -max_y), max_y),
        )

    def _scope_region_rect(self):
        if not self.hasScopeRegionRect():
            return None
        return QRectF(
            self.regionTopLeftHandle.x(),
            self.regionTopLeftHandle.y(),
            self.regionBottomRightHandle.x() - self.regionTopLeftHandle.x(),
            self.regionBottomRightHandle.y() - self.regionTopLeftHandle.y()
        ).normalized()

    def _visible_scope_region_rect(self):
        bounds_w, bounds_h = self._scope_region_bounds()
        if bounds_w <= 0.0 or bounds_h <= 0.0:
            return QRectF(0.0, 0.0, 1.0, 1.0)
        self._ensure_region_transform()
        widget_rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))
        visible = self.region_transform_inverted.mapRect(widget_rect).intersected(QRectF(0.0, 0.0, bounds_w, bounds_h))
        if visible.isEmpty():
            return QRectF(0.0, 0.0, bounds_w, bounds_h)
        return visible.normalized()

    def _normalized_scope_region_rect(self, rect, enforce_min=False):
        if not isinstance(rect, QRectF):
            return None
        bounds_w, bounds_h = self._scope_region_bounds()
        rect = rect.normalized()
        left = max(0.0, min(bounds_w, rect.left()))
        top = max(0.0, min(bounds_h, rect.top()))
        right = max(0.0, min(bounds_w, rect.right()))
        bottom = max(0.0, min(bounds_h, rect.bottom()))
        if enforce_min:
            min_w, min_h = self._scope_region_min_size()
            if (right - left) < min_w:
                right = min(bounds_w, left + min_w)
                left = max(0.0, right - min_w)
            if (bottom - top) < min_h:
                bottom = min(bounds_h, top + min_h)
                top = max(0.0, bottom - min_h)
        return QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()

    def _apply_scope_region_rect(self, rect, emit_signal=True, enforce_min=False):
        rect = self._normalized_scope_region_rect(rect, enforce_min=enforce_min)
        if not rect:
            return
        self.regionTopLeftHandle = QRectF(rect.left(), rect.top(), self.cs, self.cs)
        self.regionBottomRightHandle = QRectF(rect.right(), rect.bottom(), self.cs, self.cs)
        self.update()
        self.update_title()
        if emit_signal:
            self.regionRectChanged.emit()

    def _scope_region_corner_rects(self):
        rect = self._scope_region_rect()
        if not rect:
            return {}
        size = self.cs / max(self.zoom, 0.001)
        half = size * 0.5
        corners = {
            "scale_top_left": QPointF(rect.left(), rect.top()),
            "scale_top_right": QPointF(rect.right(), rect.top()),
            "scale_bottom_left": QPointF(rect.left(), rect.bottom()),
            "scale_bottom_right": QPointF(rect.right(), rect.bottom()),
        }
        return {
            mode: QRectF(point.x() - half, point.y() - half, size, size)
            for mode, point in corners.items()
        }

    def hasScopeRegionRect(self):
        return self.regionTopLeftHandle is not None and self.regionBottomRightHandle is not None

    def resetScopeRegionToDefault(self):
        visible = self._visible_scope_region_rect()
        rect_w = max(24.0, visible.width() * 0.4)
        rect_h = max(24.0, visible.height() * 0.4)
        left = visible.center().x() - (rect_w * 0.5)
        top = visible.center().y() - (rect_h * 0.5)
        self._apply_scope_region_rect(
            QRectF(QPointF(left, top), QPointF(left + rect_w, top + rect_h)),
            emit_signal=True,
            enforce_min=True,
        )

    def setScopeRegionNormalizedRect(self, x, y, width, height):
        bounds_w, bounds_h = self._scope_region_bounds()
        x = max(0.0, min(1.0, float(x)))
        y = max(0.0, min(1.0, float(y)))
        width = max(0.0, min(1.0 - x, float(width)))
        height = max(0.0, min(1.0 - y, float(height)))
        if width <= 0.0 or height <= 0.0:
            self.regionTopLeftHandle = None
            self.regionBottomRightHandle = None
            self.update()
            self.update_title()
            self.regionRectChanged.emit()
            return
        left = x * bounds_w
        top = y * bounds_h
        right = min(bounds_w, left + (width * bounds_w))
        bottom = min(bounds_h, top + (height * bounds_h))
        self._apply_scope_region_rect(QRectF(QPointF(left, top), QPointF(right, bottom)), emit_signal=True, enforce_min=True)

    def scopeRegionNormalizedRect(self):
        rect = self._scope_region_rect()
        if not rect:
            return None
        bounds_w, bounds_h = self._scope_region_bounds()
        if rect.width() <= 0.0 or rect.height() <= 0.0:
            return None
        return {
            "x": max(0.0, min(1.0, rect.x() / bounds_w)),
            "y": max(0.0, min(1.0, rect.y() / bounds_h)),
            "width": max(0.0, min(1.0, rect.width() / bounds_w)),
            "height": max(0.0, min(1.0, rect.height() / bounds_h)),
        }

    def setScopeRegionEnabled(self, enabled):
        self.region_selection_mode = "rect"
        self.region_enabled = bool(enabled)
        if self.region_enabled and not self.hasScopeRegionRect():
            self.resetScopeRegionToDefault()
            return
        self.update()
        self.update_title()
        self.regionRectChanged.emit()

    def resizeEvent(self, event):
        """Widget resize event"""
        event.accept()
        if hasattr(self, "pan_x") and hasattr(self, "pan_y"):
            self.pan_x, self.pan_y = VideoWidget._clamp_pan(
                self,
                width=event.size().width(),
                height=event.size().height(),
            )
        self.delayed_size = self.size()
        self.delayed_resize_timer.start()

        # Only the main project preview uses VideoWidget's internal delayed resize
        # pipeline. Dialog previews manage their own resize/max-size flow and
        # should not be forcibly paused here during startup.
        if getattr(self, "watch_project", True) and not getattr(self.win, "_dock_interaction_active", False):
            self.win.PauseSignal.emit()

    def delayed_resize_callback(self):
        """Callback for resize event timer (to delay the resize event, and prevent lots of similar resize events)"""
        # While the mouse button is still held down (e.g. dragging docks/splitters),
        # keep deferring preview resize work so we don't thrash SetMaxSize/ClearAllCache.
        if QApplication.mouseButtons() & Qt.LeftButton:
            self.delayed_resize_timer.start()
            return

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
        old_zoom = float(self.zoom)
        old_viewport = QRectF(self.centeredViewport(self.width(), self.height()))
        self.zoom += event.angleDelta().y() / tick_scale
        if self.zoom <= 0.0:
            # Don't allow zoom to go all the way to zero (or negative)
            self.zoom = 0.05

        mods = QCoreApplication.instance().keyboardModifiers()
        keep_centered = modifiers_has(mods, Qt.ShiftModifier) or modifiers_has(mods, Qt.ControlModifier)
        if self.zoom <= 1.0:
            self.zoom = max(0.05, self.zoom)
            self.pan_x = 0.0
            self.pan_y = 0.0
        elif not keep_centered and old_zoom > 0.0:
            scale = self.zoom / old_zoom
            anchor = QPointF(event.pos())
            old_center = old_viewport.center()
            new_center = anchor + ((old_center - anchor) * scale)
            window_center = QRectF(QPointF(0, 0), QSizeF(self.width(), self.height())).center()
            self.pan_x = new_center.x() - window_center.x()
            self.pan_y = new_center.y() - window_center.y()
            self.pan_x, self.pan_y = self._clamp_pan()
        else:
            self.pan_x = 0.0
            self.pan_y = 0.0

        # Add resize button (if not 100% zoom)
        if self.zoom != 1.0:
            self.resize_button.show()
        else:
            self.resize_button.hide()

        # Request repaint asynchronously to avoid recursive paint calls.
        self.update()

    def resize_button_clicked(self):
        """Resize zoom button clicked"""
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.resize_button.hide()

        # Request repaint asynchronously to avoid recursive paint calls.
        self.update()

    def __init__(self, watch_project=True, *args):
        """watch_project: watch for changes in project size / widget size, and
        continue to match the current project's aspect ratio."""
        # Invoke parent init
        super().__init__(*args)
        self.watch_project = bool(watch_project)

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
        self.marginBoxFullBounds = None
        self.originHandle = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.transform_mode = None
        self.hover_transform_mode = None
        self.rotation_drag_value = None
        self.margin_box_drag_anchor = None
        self.hover_cursor = Qt.ArrowCursor
        self.original_clip_data = None
        self.original_clip_data_map = {}
        self.original_effect_data = None
        self.region_qimage = None
        self.region_transform = None
        self.region_transform_inverted = None
        self.region_enabled = False
        self.region_selection_mode = "rect"
        self.region_annotation_tool = "positive_point"
        self.region_annotation_limits = {}
        self.region_points = []
        self.region_points_positive = []
        self.region_points_negative = []
        self.region_rects_positive = []
        self.region_rects_negative = []
        self.region_rect_drag_start = None
        self.region_rect_drag_current = None
        self.region_annotation_inherited = False
        self.region_mask_preview_image = None
        self.region_mask_preview_frame = None
        self.region_mode = None
        self.region_press_outside = False
        self.scope_region_drag_anchor = None
        self.regionTopLeftHandle = None
        self.regionBottomRightHandle = None
        self.curr_frame_size = None # Frame size
        self.zoom = 1.0  # Zoom of widget (does not affect video, only workspace)
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.middle_pan_active = False
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
        cursor_fallbacks = {
            "move": Qt.SizeAllCursor,
            "resize_x": Qt.SizeHorCursor,
            "resize_y": Qt.SizeVerCursor,
            "resize_bdiag": Qt.SizeBDiagCursor,
            "resize_fdiag": Qt.SizeFDiagCursor,
            "rotate": Qt.CrossCursor,
            "shear_x": Qt.SizeHorCursor,
            "shear_y": Qt.SizeVerCursor,
            "hand": Qt.OpenHandCursor,
        }
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
            pixmap = icon.pixmap(32, 32)
            if pixmap.isNull() or pixmap.size().isEmpty():
                pixmap = None
            self.cursors[cursor_name] = (pixmap, cursor_fallbacks[cursor_name])

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
