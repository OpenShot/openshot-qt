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

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        # Handle change
        if (action.key and action.key[0] in [
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


    def drawTransformHandler(
        self, painter, sx, sy, source_width, source_height,
        origin_x, origin_y,
        x1=None, y1=None, x2=None, y2=None, rotation = None
    ):
        # Draw transform corners and center origin circle
        # Corner size
        cs = self.cs
        os = 12.0

        csx = cs / sx
        csy = cs / sy

        # Rotate the transform handler
        if rotation:
            bbox_center_x = ((x1*source_width + x2*source_width) / 2.0) - ((os / 2) / sx)
            bbox_center_y = ((y1*source_height + y2*source_height) / 2.0) - ((os / 2) / sy)
            painter.translate(bbox_center_x, bbox_center_y)
            painter.rotate(rotation)
            painter.translate(-bbox_center_x, -bbox_center_y)

        if all([x1, y1, x2, y2]):
            # Calculate bounds of clip
            self.clipBounds = QRectF(
                QPointF(x1 * source_width, y1 * source_height),
                QPointF(x2 * source_width, y2 * source_height)
            )
            # Calculate 4 corners coordinates
            self.topLeftHandle = QRectF(
                x1 * source_width - (csx / 2.0),
                y1 * source_height - (csy / 2.0),
                csx,
                csy)
            self.topRightHandle = QRectF(
                x2 * source_width - (csx / 2.0),
                y1 * source_height - (csy / 2.0),
                csx,
                csy)
            self.bottomLeftHandle = QRectF(
                x1 * source_width - (csx / 2.0),
                y2 * source_height - (csy / 2.0),
                csx,
                csy)
            self.bottomRightHandle = QRectF(
                x2 * source_width - (csx / 2.0),
                y2 * source_height - (csy / 2.0),
                csx,
                csy)
        else:
            # Calculate bounds of clip
            self.clipBounds = QRectF(
                QPointF(0.0, 0.0),
                QPointF(source_width, source_height))
            # Calculate 4 corners coordinates
            self.topLeftHandle = QRectF(
                -csx / 2.0, -csy / 2.0, csx, csy)
            self.topRightHandle = QRectF(
                source_width - csx / 2.0, -csy / 2.0, csx, csy)
            self.bottomLeftHandle = QRectF(
                -csx / 2.0, source_height - csy / 2.0, csx, csy)
            self.bottomRightHandle = QRectF(
                source_width - csx / 2.0, source_height - csy / 2.0, csx, csy)

        # Draw 4 corners
        pen = QPen(QBrush(QColor("#53a0ed")), 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(self.topLeftHandle)
        painter.drawRect(self.topRightHandle)
        painter.drawRect(self.bottomLeftHandle)
        painter.drawRect(self.bottomRightHandle)

        if all([x1, y1, x2, y2]):
            # Calculate 4 side coordinates
            self.topHandle = QRectF(
                ((x1 + x2) * source_width - csx) / 2.0,
                (y1 * source_height) - csy / 2.0,
                csx,
                csy)
            self.bottomHandle = QRectF(
                ((x1 + x2) * source_width - csx) / 2.0,
                (y2 * source_height) - csy / 2.0,
                csx,
                csy)
            self.leftHandle = QRectF(
                (x1 * source_width) - csx / 2.0,
                ((y1 + y2) * source_height - csy) / 2.0,
                csx,
                csy)
            self.rightHandle = QRectF(
                (x2 * source_width) - csx / 2.0,
                ((y1 + y2) * source_height - csy) / 2.0,
                csx, csy)

        else:
            # Calculate 4 side coordinates
            self.topHandle = QRectF(
                (source_width - csx) / 2.0,
                -csy / 2.0,
                csx,
                csy)
            self.bottomHandle = QRectF(
                (source_width - csx) / 2.0,
                source_height - (csy / 2.0),
                csx,
                csy)
            self.leftHandle = QRectF(
                -csx / 2.0,
                (source_height - csy) / 2.0,
                csx,
                csy)
            self.rightHandle = QRectF(
                source_width - (csx / 2.0),
                (source_height - csy) / 2.0,
                csx,
                csy)

        # Calculate shear handles
        self.topShearHandle = QRectF(
            self.topLeftHandle.x(),
            self.topLeftHandle.y(),
            self.clipBounds.width(),
            self.topLeftHandle.height())
        self.leftShearHandle = QRectF(
            self.topLeftHandle.x(),
            self.topLeftHandle.y(),
            self.topLeftHandle.width(),
            self.clipBounds.height())
        self.rightShearHandle = QRectF(
            self.topRightHandle.x(),
            self.topRightHandle.y(),
            self.topRightHandle.width(),
            self.clipBounds.height())
        self.bottomShearHandle = QRectF(
            self.bottomLeftHandle.x(),
            self.bottomLeftHandle.y(),
            self.clipBounds.width(),
            self.topLeftHandle.height())

        # Draw 4 sides (centered)
        painter.drawRects([
            self.topHandle,
            self.bottomHandle,
            self.leftHandle,
            self.rightHandle,
            self.clipBounds,
            ])

        # Calculate center coordinate
        if all([x1, y1, x2, y2]):
            cs = 5.0
            os = 7.0
            self.centerHandle = QRectF(
                ((x1 + x2) * source_width / 2.0) - (os / sx),
                ((y1 + y2) * source_height / 2.0) - (os / sy),
                os / sx * 2.0,
                os / sy * 2.0
            )
        else:
            self.centerHandle = QRectF(
                source_width * origin_x - (os / sx),
                source_height * origin_y - (os / sy),
                os / sx * 2.0,
                os / sy * 2.0)

        # Draw origin
        painter.drawEllipse(self.centerHandle)

        # Draw cross at origin center, extending beyond ellipse by 25%
        center = self.centerHandle.center()
        halfW = QPointF(self.centerHandle.width() * 0.75, 0)
        halfH = QPointF(0, self.centerHandle.height() * 0.75)
        painter.drawLines(
            center - halfW, center + halfW,
            center - halfH, center + halfH,
        )

        # Remove transform
        painter.resetTransform()

    def paintEvent(self, event, *args):
        """ Custom paint event """
        event.accept()
        self.mutex.lock()

        # Paint custom frame image on QWidget
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.SmoothPixmapTransform
            | QPainter.TextAntialiasing,
            True)

        # Fill the whole widget with the solid color
        painter.fillRect(event.rect(), QColor("#191919"))

        # Find centered viewport
        viewport_rect = self.centeredViewport(self.width(), self.height())

        if self.current_image:
            # DRAW FRAME
            # Calculate new frame image size, maintaining aspect ratio
            pixSize = self.current_image.size()
            pixSize.scale(event.rect().size(), Qt.KeepAspectRatio)
            self.curr_frame_size = pixSize

            # Scale image (take into account display scaling for High DPI monitors)
            scale = self.devicePixelRatioF()
            scaledPix = self.current_image.scaled(pixSize * scale, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Calculate center of QWidget and Draw image
            painter.drawImage(viewport_rect, scaledPix)

        if self.transforming_clip:
            # Draw transform handles on top of video preview
            # Get framerate
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Determine frame # of clip
            start_of_clip = round(float(self.transforming_clip.data["start"]) * fps_float)
            position_of_clip = (float(self.transforming_clip.data["position"]) * fps_float) + 1
            playhead_position = float(get_app().window.preview_thread.current_frame)
            clip_frame_number = round(playhead_position - position_of_clip) + start_of_clip + 1

            # Get properties of clip at current frame
            raw_properties = json.loads(self.transforming_clip_object.PropertiesJSON(clip_frame_number))

            # Get size of current video player
            player_width = viewport_rect.width()
            player_height = viewport_rect.height()

            # Determine original size of clip's reader
            source_width = self.transforming_clip.data['reader']['width']
            source_height = self.transforming_clip.data['reader']['height']
            pixel_adjust = self.pixel_ratio.Reciprocal().ToDouble()
            source_size = QSize(
                int(source_width),
                int(source_height * pixel_adjust))

            # Determine scale of clip
            scale = self.transforming_clip.data['scale']

            # Set scale as STRETCH if the clip is attached to an object
            if (
                    raw_properties.get('parentObjectId').get('memo') != 'None'
                    and len(raw_properties.get('parentObjectId').get('memo')) > 0
            ):
                scale = openshot.SCALE_STRETCH

            if scale == openshot.SCALE_FIT:
                source_size.scale(player_width, player_height, Qt.KeepAspectRatio)

            elif scale == openshot.SCALE_STRETCH:
                source_size.scale(player_width, player_height, Qt.IgnoreAspectRatio)

            elif scale == openshot.SCALE_CROP:
                source_size.scale(player_width, player_height, Qt.KeepAspectRatioByExpanding)

            # Get new source width / height (after scaling mode applied)
            source_width = source_size.width()
            source_height = source_size.height()

            # Init X/Y
            x = viewport_rect.x()
            y = viewport_rect.y()

            # Get scaled source image size (scale_x, scale_y)
            sx = max(float(raw_properties.get('scale_x').get('value')), 0.001)
            sy = max(float(raw_properties.get('scale_y').get('value')), 0.001)
            scaled_source_width = source_width * sx
            scaled_source_height = source_height * sy

            # Determine gravity of clip
            gravity = self.transforming_clip.data['gravity']
            if gravity == openshot.GRAVITY_TOP_LEFT:
                pass
            elif gravity == openshot.GRAVITY_TOP:
                x += (player_width - scaled_source_width) / 2.0  # center
            elif gravity == openshot.GRAVITY_TOP_RIGHT:
                x += player_width - scaled_source_width  # right
            elif gravity == openshot.GRAVITY_LEFT:
                y += (player_height - scaled_source_height) / 2.0  # center
            elif gravity == openshot.GRAVITY_CENTER:
                x += (player_width - scaled_source_width) / 2.0  # center
                y += (player_height - scaled_source_height) / 2.0  # center
            elif gravity == openshot.GRAVITY_RIGHT:
                x += player_width - scaled_source_width  # right
                y += (player_height - scaled_source_height) / 2.0  # center
            elif gravity == openshot.GRAVITY_BOTTOM_LEFT:
                y += (player_height - scaled_source_height)  # bottom
            elif gravity == openshot.GRAVITY_BOTTOM:
                x += (player_width - scaled_source_width) / 2.0  # center
                y += (player_height - scaled_source_height)  # bottom
            elif gravity == openshot.GRAVITY_BOTTOM_RIGHT:
                x += player_width - scaled_source_width  # right
                y += (player_height - scaled_source_height)  # bottom

            # Adjust x,y for location
            x_offset = raw_properties.get('location_x').get('value')
            y_offset = raw_properties.get('location_y').get('value')
            x += (player_width * x_offset)
            y += (player_height * y_offset)

            self.transform = QTransform()

            # Apply translate/move
            if x or y:
                self.transform.translate(x, y)

            # Apply rotation
            rotation = raw_properties.get('rotation').get('value')
            shear_x = raw_properties.get('shear_x').get('value')
            shear_y = raw_properties.get('shear_y').get('value')
            origin_x = raw_properties.get('origin_x').get('value')
            origin_y = raw_properties.get('origin_y').get('value')
            origin_x_value = scaled_source_width * origin_x
            origin_y_value = scaled_source_height * origin_y
            self.originHandle = QPointF(x + origin_x_value, y + origin_y_value)
            if rotation or shear_x or shear_y:
                self.transform.translate(origin_x_value, origin_y_value)
                self.transform.rotate(rotation)
                self.transform.shear(shear_x, shear_y)
                self.transform.translate(-origin_x_value, -origin_y_value)

            # Apply scale
            if sx or sy:
                self.transform.scale(sx, sy)

            # Apply transform
            painter.setTransform(self.transform)

            if self.transforming_effect:
                # Check if the effect has a tracked object
                if self.transforming_effect_object.info.has_tracked_object:
                    # Get properties of clip at current frame
                    raw_properties_effect = json.loads(self.transforming_effect_object.PropertiesJSON(clip_frame_number))
                    # Get properties for the first object in dict. PropertiesJSON should return one object at the time
                    tmp = raw_properties_effect.get('objects')
                    obj_id = list(tmp.keys())[0]
                    raw_properties_effect = raw_properties_effect.get('objects').get(obj_id)

                    # Check if the tracked object is visible in this frame
                    if raw_properties_effect.get('visible'):
                        if raw_properties_effect.get('visible').get('value') == 1:
                            # Get the selected bounding box values
                            rotation = raw_properties_effect['rotation']['value']
                            x1 = raw_properties_effect['x1']['value']
                            y1 = raw_properties_effect['y1']['value']
                            x2 = raw_properties_effect['x2']['value']
                            y2 = raw_properties_effect['y2']['value']
                            self.drawTransformHandler(
                                painter,
                                sx, sy,
                                source_width, source_height,
                                origin_x, origin_y,
                                x1, y1, x2, y2,
                                rotation)
            else:
                self.drawTransformHandler(
                    painter,
                    sx, sy,
                    source_width, source_height,
                    origin_x, origin_y)

        if self.region_enabled:
            # Paint region selector onto video preview
            self.region_transform = QTransform()

            # Init X/Y
            x = viewport_rect.x()
            y = viewport_rect.y()

            # Apply translate/move
            if x or y:
                self.region_transform.translate(x, y)

            # Apply scale (if any)
            if self.zoom:
                self.region_transform.scale(self.zoom, self.zoom)

            # Apply transform
            self.region_transform_inverted = self.region_transform.inverted()[0]
            painter.setTransform(self.region_transform)

            # Draw transform corners and center origin circle
            # Corner size
            cs = self.cs

            if self.regionTopLeftHandle and self.regionBottomRightHandle:
                # Draw 2 corners and bounding box
                pen = QPen(QBrush(QColor("#53a0ed")), 1.5)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawRect(
                    self.regionTopLeftHandle.x() - (cs / 2.0 / self.zoom),
                    self.regionTopLeftHandle.y() - (cs / 2.0 / self.zoom),
                    self.regionTopLeftHandle.width() / self.zoom,
                    self.regionTopLeftHandle.height() / self.zoom)
                painter.drawRect(
                    self.regionBottomRightHandle.x() - (cs / 2.0 / self.zoom),
                    self.regionBottomRightHandle.y() - (cs / 2.0 / self.zoom),
                    self.regionBottomRightHandle.width() / self.zoom,
                    self.regionBottomRightHandle.height() / self.zoom)
                region_rect = QRectF(
                    self.regionTopLeftHandle.x(),
                    self.regionTopLeftHandle.y(),
                    self.regionBottomRightHandle.x() - self.regionTopLeftHandle.x(),
                    self.regionBottomRightHandle.y() - self.regionTopLeftHandle.y())
                painter.drawRect(region_rect)

            # Remove transform
            painter.resetTransform()

        # End painter
        painter.end()

        self.mutex.unlock()

    def centeredViewport(self, width, height):
        """ Calculate size of viewport to maintain aspect ratio """

        window_size = QSizeF(width, height)
        window_rect = QRectF(QPointF(0, 0), window_size)

        aspectRatio = self.aspect_ratio.ToFloat() * self.pixel_ratio.ToFloat()
        viewport_size = QSizeF(aspectRatio, 1).scaled(window_size, Qt.KeepAspectRatio)
        viewport_rect = QRectF(QPointF(0, 0), viewport_size)
        viewport_rect.moveCenter(window_rect.center())

        return viewport_rect.toRect()

    def present(self, image, *args):
        """ Present the current frame """

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
        self.transform_mode = None

        # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
        get_app().updates.ignore_history = True

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

        # Add final update to undo/redo history
        if self.original_clip_data:
            get_app().updates.apply_last_action_to_history(self.original_clip_data)

        # Clear original data
        self.original_clip_data = None

    def rotateCursor(self, pixmap, rotation, shear_x, shear_y):
        """Rotate cursor based on the current transform"""
        rotated_pixmap = pixmap.transformed(
            QTransform().rotate(rotation).shear(shear_x, shear_y).scale(0.8, 0.8),
            Qt.SmoothTransformation)
        return QCursor(rotated_pixmap)

    def checkTransformMode(self, rotation, shear_x, shear_y, event):
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
            "outside": {"mode": 'rotation', "cursor": "rotate"}
            }

        # Mouse over resize button (and not currently dragging)
        if (not self.mouse_dragging
            and self.resize_button.isVisible()
            and self.resize_button.rect().contains(event.pos()
        ):
            self.setCursor(Qt.ArrowCursor)
            self.transform_mode = None
            return

        # If mouse is over a handle, set corresponding pointer/mode
        for h in handle_uis:
            if self.transform.mapToPolygon(
                    h["handle"].toRect()
                    ).containsPoint(event.pos(), Qt.OddEvenFill):
                # Handle contains cursor
                if self.transform_mode and self.transform_mode != h["mode"]:
                    # We're in different xform mode, skip
                    continue
                if self.mouse_dragging:
                    self.transform_mode = h["mode"]
                self.setCursor(self.rotateCursor(
                    self.cursors.get(h["cursor"]), rotation, shear_x, shear_y))
                return

        # If not over any handles, determne inside/outside clip rectangle
        r = non_handle_uis.get("region")
        if self.transform.mapToPolygon(r.toRect()).containsPoint(event.pos(), Qt.OddEvenFill):
            nh = non_handle_uis.get("inside", {})
        else:
            nh = non_handle_uis.get("outside", {})
        if self.mouse_dragging and not self.transform_mode:
            self.transform_mode = nh.get("mode")
        if not self.transform_mode or self.transform_mode == nh.get("mode"):
            self.setCursor(self.rotateCursor(
                self.cursors.get(nh.get("cursor")), rotation, shear_x, shear_y))


        # If we got this far and we don't have a transform mode, reset the cursor
        if not self.transform_mode:
            self.setCursor(QCursor(Qt.ArrowCursor))

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

            # Determine frame # of clip
            start_of_clip_frame = round(float(self.transforming_clip.data["start"]) * fps_float) + 1
            position_of_clip_frame = (float(self.transforming_clip.data["position"]) * fps_float) + 1
            playhead_position_frame = float(get_app().window.preview_thread.current_frame)
            clip_frame_number = round(playhead_position_frame - position_of_clip_frame) + start_of_clip_frame

            # Get properties of clip at current frame
            raw_properties = json.loads(self.transforming_clip_object.PropertiesJSON(clip_frame_number))

            # Get current rotation and skew (used for cursor rotation)
            rotation = raw_properties.get('rotation').get('value')
            shear_x = raw_properties.get('shear_x').get('value')
            shear_y = raw_properties.get('shear_y').get('value')

            # Get the rect where the video is actually drawn (without the black borders, etc...)
            viewport_rect = self.centeredViewport(self.width(), self.height())

            # Make back-up of clip data
            if self.mouse_dragging and not self.transform_mode:
                self.original_clip_data = self.transforming_clip.data

            self.checkTransformMode(rotation, shear_x, shear_y, event)

            # Transform clip object
            if self.transform_mode:

                x_motion = event.pos().x() - self.mouse_position.x()
                y_motion = event.pos().y() - self.mouse_position.y()

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
                        self.transforming_clip.id, clip_frame_number,
                        'origin_x', origin_x,
                        refresh=False)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'origin_y', origin_y)

                elif self.transform_mode == 'location':
                    # Get current keyframe value
                    location_x = raw_properties.get('location_x').get('value')
                    location_y = raw_properties.get('location_y').get('value')

                    # Calculate new location coordinates
                    location_x += x_motion / viewport_rect.width()
                    location_y += y_motion / viewport_rect.height()

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'location_x', location_x,
                        refresh=False)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'location_y', location_y)

                elif self.transform_mode == 'shear_top':
                    # Get current keyframe shear value
                    shear_x = raw_properties.get('shear_x').get('value')
                    scale_x = raw_properties.get('scale_x').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (self.clipBounds.width() / self.clipBounds.height()) * 2.0
                    shear_x -= (
                        x_motion) / (
                        (self.clipBounds.width() * scale_x) / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'shear_x', shear_x)

                elif self.transform_mode == 'shear_bottom':
                    # Get current keyframe shear value
                    scale_x = raw_properties.get('scale_x').get('value')
                    shear_x = raw_properties.get('shear_x').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (self.clipBounds.width() / self.clipBounds.height()) * 2.0
                    shear_x += (
                        x_motion) / (
                        (self.clipBounds.width() * scale_x) / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'shear_x', shear_x)

                elif self.transform_mode == 'shear_left':
                    # Get current keyframe shear value
                    shear_y = raw_properties.get('shear_y').get('value')
                    scale_y = raw_properties.get('scale_y').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (
                        self.clipBounds.height() / self.clipBounds.width()) * 2.0
                    shear_y -= (
                        y_motion) / (
                        self.clipBounds.height() * scale_y / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'shear_y', shear_y)

                elif self.transform_mode == 'shear_right':
                    # Get current keyframe shear value
                    scale_y = raw_properties.get('scale_y').get('value')
                    shear_y = raw_properties.get('shear_y').get('value')

                    # Calculate new location coordinates
                    aspect_ratio = (
                        self.clipBounds.height() / self.clipBounds.width()) * 2.0
                    shear_y += (
                        y_motion) / (
                        self.clipBounds.height() * scale_y / aspect_ratio)

                    # Update keyframe value (or create new one)
                    self.updateClipProperty(
                        self.transforming_clip.id, clip_frame_number,
                        'shear_y', shear_y)

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
                        self.transforming_clip.id,
                        clip_frame_number,
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
                        # If CTRL key is pressed, fix the scale_y to the correct aspect ration
                        if scale_x:
                            scale_y = scale_x
                        elif scale_y:
                            scale_x = scale_y

                    # Update keyframe value (or create new one)
                    both_scaled = scale_x != 0.001 and scale_y != 0.001
                    if scale_x != 0.001:
                        self.updateClipProperty(
                            self.transforming_clip.id, clip_frame_number,
                            'scale_x', scale_x,
                            refresh=(not both_scaled))
                    if scale_y != 0.001:
                        self.updateClipProperty(
                            self.transforming_clip.id, clip_frame_number,
                            'scale_y', scale_y)

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

        if self.transforming_effect and self.transforming_clip:
            # Adjust effect keyframes if mouse is on top of the transform handlers

            # Get framerate
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Determine frame # of clip
            start_of_clip_frame = round(float(self.transforming_clip.data["start"]) * fps_float) + 1
            position_of_clip_frame = (float(self.transforming_clip.data["position"]) * fps_float) + 1
            playhead_position_frame = float(get_app().window.preview_thread.current_frame)
            clip_frame_number = round(playhead_position_frame - position_of_clip_frame) + start_of_clip_frame

            # Get the rect where the video is actually drawn (without the black borders, etc...)
            viewport_rect = self.centeredViewport(self.width(), self.height())

            # Make back-up of clip data
            if self.mouse_dragging and not self.transform_mode:
                self.original_clip_data = self.transforming_clip.data

            if self.transforming_effect_object.info.has_tracked_object:
                # Get properties of effect at current frame
                raw_properties = json.loads(self.transforming_effect_object.PropertiesJSON(clip_frame_number))
                # Get properties for the first object in dict.
                # PropertiesJSON should return one object at the time
                obj_id = list(raw_properties.get('objects').keys())[0]
                raw_properties = raw_properties.get('objects').get(obj_id)

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

        for point in c.data[property_key]["Points"]:
            log.info("looping points: co.X = %s" % point["co"]["X"])

            if point["co"]["X"] == frame_number:
                found_point = True
                clip_updated = True
                point["interpolation"] = openshot.BEZIER
                point["co"]["Y"] = float(new_value)

        if not found_point and new_value is not None:
            clip_updated = True
            log.info("Created new point at X=%s", frame_number)
            c.data[property_key]["Points"].append({
                'co': {'X': frame_number, 'Y': new_value},
                'interpolation': openshot.BEZIER
                })

        # Reduce # of clip properties we are saving (performance boost)
        c.data = {property_key: c.data.get(property_key)}

        if clip_updated:
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

        try:
            props = c.data['objects'][obj_id]
            points_list = props[property_key]["Points"]
        except (TypeError, KeyError):
            log.error("Corrupted project data!", exc_info=1)
            return

        for point in points_list:
            log.info("looping points: co.X = %s", point["co"]["X"])

            if point["co"]["X"] == frame_number:
                found_point = True
                effect_updated = True
                point["interpolation"] = openshot.BEZIER
                point["co"]["Y"] = float(new_value)

        if not found_point and new_value != None:
            effect_updated = True
            log.info("Created new point at X=%s", frame_number)
            points_list.append({
                'co': { 'X': frame_number, 'Y': new_value },
                'interpolation': openshot.BEZIER,
                })

        # Reduce # of clip properties we are saving (performance boost)
        #TODO: This is too slow when draging transform handlers
        c.data = {'objects': {obj_id: c.data.get('objects', {}).get(obj_id)}}

        if effect_updated:
            c.save()
            # Update the preview
            if refresh:
                get_app().window.refreshFrameSignal.emit()

    def refreshTriggered(self):
        """Signal to refresh viewport (i.e. a property might have changed that effects the preview)"""

        # Update reference to clip
        if self.transforming_clip:
            self.transforming_clip = Clip.get(id=self.transforming_clip.id)

        if self.transforming_effect:
            self.transforming_effect = Effect.get(id=self.transforming_effect.id)

    def transformTriggered(self, clip_id):
        """Handle the transform signal when it's emitted"""
        win = get_app().window
        need_refresh = False

        # Disable Transform UI
        # Is this the same clip_id already being transformed?
        if self.transforming_clip and not clip_id:
            # Clear transform
            self.transforming_clip = None
            need_refresh = True

        # Get new clip for transform
        if clip_id:
            self.transforming_clip = Clip.get(id=clip_id)
            self.transforming_clip_object = win.timeline_sync.timeline.GetClip(clip_id)
            if self.transforming_clip and self.transforming_clip_object:
                self.transforming_effect = None
                need_refresh = True

        # Update the preview and reselct current frame in properties
        if need_refresh:
            win.refreshFrameSignal.emit()
            win.propertyTableView.select_frame(win.preview_thread.player.Position())

    def keyFrameTransformTriggered(self, effect_id, clip_id):
        """Handle the key frame transform signal when it's emitted"""
        win = get_app().window
        need_refresh = False

        # Disable Transform UI
        # Is this the same clip_id already being transformed?
        if self.transforming_effect and not effect_id:
            # Clear transform
            self.transforming_effect = None
            self.transforming_clip = None
            need_refresh = True

        # Get new clip for transform
        if effect_id and clip_id:
            self.transforming_clip = Clip.get(id=clip_id)
            self.transforming_clip_object = win.timeline_sync.timeline.GetClip(clip_id)
            self.transforming_effect = Effect.get(id=effect_id)
            self.transforming_effect_object = win.timeline_sync.timeline.GetClipEffect(effect_id)

            if (self.transforming_clip and self.transforming_clip_object and
                self.transforming_effect and self.transforming_effect_object):
                need_refresh = True

        # Update the preview and reselct current frame in properties
        if need_refresh:
            win.refreshFrameSignal.emit()
            win.propertyTableView.select_frame(win.preview_thread.player.Position())

    def regionTriggered(self, clip_id):
        """Handle the 'select region' signal when it's emitted"""
        # Clear transform
        self.region_enabled = bool(not clip_id)
        get_app().window.refreshFrameSignal.emit()

    def resizeEvent(self, event):
        """Widget resize event"""
        event.accept()
        self.delayed_size = self.size()
        self.delayed_resize_timer.start()

        # Pause playback (to prevent crash since we are fixing to change the timeline's max size)
        self.win.actionPlay_trigger(force="pause")

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

        # Init aspect ratio settings (default values)
        self.aspect_ratio = openshot.Fraction(16, 9)
        self.pixel_ratio = openshot.Fraction(1, 1)
        self.transforming_clip = None
        self.transforming_effect = None
        self.transforming_clip_object = None
        self.transforming_effect_object = None
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
        self.clipBounds = None
        self.originHandle = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.transform_mode = None
        self.original_clip_data = None
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
