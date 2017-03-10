""" 
 @file
 @brief This file contains the video preview QWidget (based on a QLabel)
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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

from PyQt5.QtCore import QSize, Qt, QCoreApplication, QPointF, QRect, QRectF, QMutex
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QSizePolicy, QWidget
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes.logger import log
from classes.app import get_app
from classes.query import Clip

try:
    import json
except ImportError:
    import simplejson as json


class VideoWidget(QWidget):
    """ A QWidget used on the video display widget """

    def paintEvent(self, event, *args):
        """ Custom paint event """
        self.mutex.lock()

        # Paint custom frame image on QWidget
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing, True)

        # Fill background black
        painter.fillRect(event.rect(), self.palette().window())

        if self.current_image:
            # DRAW FRAME
            # Calculate new frame image size, maintaining aspect ratio
            pixSize = self.current_image.size()
            pixSize.scale(event.rect().size(), Qt.KeepAspectRatio)

            # Scale image
            scaledPix = self.current_image.scaled(pixSize, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Calculate center of QWidget and Draw image
            center = self.centeredViewport(self.width(), self.height())
            painter.drawImage(center, scaledPix)

        if self.transforming_clip:
            # Draw transform handles on top of video preview
            # Get framerate
            fps = get_app().project.get(["fps"])
            fps_float = float(fps["num"]) / float(fps["den"])

            # Determine frame # of clip
            start_of_clip = round(float(self.transforming_clip.data["start"]) * fps_float)
            position_of_clip = (float(self.transforming_clip.data["position"]) * fps_float) + 1
            playhead_position = float(get_app().window.preview_thread.current_frame)
            clip_frame_number = round(playhead_position - position_of_clip) + start_of_clip + 1

            # Get properties of clip at current frame
            raw_properties = json.loads(self.transforming_clip_object.PropertiesJSON(clip_frame_number))

            # Get size of current video player
            player_width = self.rect().width()
            player_height = self.rect().height()

            # Determine original size of clip's reader
            source_width = self.transforming_clip.data['reader']['width']
            source_height = self.transforming_clip.data['reader']['height']
            source_size = QSize(source_width, source_height)

            # Determine scale of clip
            scale = self.transforming_clip.data['scale']
            if scale == openshot.SCALE_FIT:
                source_size.scale(player_width, player_height, Qt.KeepAspectRatio)

            elif scale == openshot.SCALE_STRETCH:
                source_size.scale(player_width, player_height, Qt.IgnoreAspectRatio)

            elif scale == openshot.SCALE_CROP:
                width_size = QSize(player_width, round(player_width / (float(source_width) / float(source_height))))
                height_size = QSize(round(player_height / (float(source_height) / float(source_width))), player_height)
                if width_size.width() >= player_width and width_size.height() >= player_height:
                    source_size.scale(width_size.width(), width_size.height(), Qt.KeepAspectRatio)
                else:
                    source_size.scale(height_size.width(), height_size.height(), Qt.KeepAspectRatio)

            # Get new source width / height (after scaling mode applied)
            source_width = source_size.width()
            source_height = source_size.height()

            # Init X/Y
            x = 0.0
            y = 0.0

            # Get scaled source image size (scale_x, scale_y)
            sx = float(raw_properties.get('scale_x').get('value'))
            sy = float(raw_properties.get('scale_y').get('value'))
            scaled_source_width = source_width * sx
            scaled_source_height = source_height * sy

            # Determine gravity of clip
            gravity = self.transforming_clip.data['gravity']
            if gravity == openshot.GRAVITY_TOP_LEFT:
                x += self.centeredViewport(self.width(), self.height()).x()  # nudge right
                y += self.centeredViewport(self.width(), self.height()).y()  # nudge down
            elif gravity == openshot.GRAVITY_TOP:
                x = (player_width - scaled_source_width) / 2.0 # center
                y += self.centeredViewport(self.width(), self.height()).y()  # nudge down
            elif gravity == openshot.GRAVITY_TOP_RIGHT:
                x = player_width - scaled_source_width # right
                x -= self.centeredViewport(self.width(), self.height()).x()  # nudge left
                y += self.centeredViewport(self.width(), self.height()).y()  # nudge down
            elif gravity == openshot.GRAVITY_LEFT:
                y = (player_height - scaled_source_height) / 2.0 # center
                x += self.centeredViewport(self.width(), self.height()).x()  # nudge right
            elif gravity == openshot.GRAVITY_CENTER:
                x = (player_width - scaled_source_width) / 2.0 # center
                y = (player_height - scaled_source_height) / 2.0 # center
            elif gravity == openshot.GRAVITY_RIGHT:
                x = player_width - scaled_source_width # right
                y = (player_height - scaled_source_height) / 2.0 # center
                x -= self.centeredViewport(self.width(), self.height()).x()  # nudge left
            elif gravity == openshot.GRAVITY_BOTTOM_LEFT:
                y = (player_height - scaled_source_height) # bottom
                x += self.centeredViewport(self.width(), self.height()).x()  # nudge right
                y -= self.centeredViewport(self.width(), self.height()).y()  # nudge up
            elif gravity == openshot.GRAVITY_BOTTOM:
                x = (player_width - scaled_source_width) / 2.0 # center
                y = (player_height - scaled_source_height) # bottom
                y -= self.centeredViewport(self.width(), self.height()).y()  # nudge up
            elif gravity == openshot.GRAVITY_BOTTOM_RIGHT:
                x = player_width - scaled_source_width # right
                y = (player_height - scaled_source_height) # bottom
                x -= self.centeredViewport(self.width(), self.height()).x()  # nudge left
                y -= self.centeredViewport(self.width(), self.height()).y()  # nudge up

            # Track gravity starting coordinate
            self.gravity_point = QPointF(x, y)

            # Scale to fit in widget
            final_size = QSize(source_width, source_height)

            # Adjust x,y for location
            x_offset = raw_properties.get('location_x').get('value')
            y_offset = raw_properties.get('location_y').get('value')
            x += (scaledPix.width() * x_offset)
            y += (scaledPix.height() * y_offset)

            self.transform = QTransform()

            # Apply translate/move
            if x or y:
                self.transform.translate(x, y)

            # Apply scale
            if sx or sy:
                self.transform.scale(sx, sy)

            # Apply shear
            shear_x = raw_properties.get('shear_x').get('value')
            shear_y = raw_properties.get('shear_y').get('value')
            if shear_x or shear_y:
                self.transform.shear(shear_x, shear_y)

            # Apply rotation
            rotation = raw_properties.get('rotation').get('value')
            if rotation:
                origin_x = x - self.centeredViewport(self.width(), self.height()).x() + (scaled_source_width / 2.0)
                origin_y = y - self.centeredViewport(self.width(), self.height()).y() + (scaled_source_height / 2.0)
                self.transform.translate(origin_x, origin_y)
                self.transform.rotate(rotation)
                self.transform.translate(-origin_x, -origin_y)

            # Apply transform
            painter.setTransform(self.transform)

            # Draw transform corners and cernter origin circle
            # Corner size
            cs = 6.0
            os = 12.0

            # Calculate 4 corners coordinates
            self.topLeftHandle = QRectF(0.0, 0.0, cs/sx, cs/sy)
            self.topRightHandle = QRectF(source_width - (cs/sx), 0, cs/sx, cs/sy)
            self.bottomLeftHandle = QRectF(0.0, source_height - (cs/sy), cs/sx, cs/sy)
            self.bottomRightHandle = QRectF(source_width - (cs/sx), source_height - (cs/sy), cs/sx, cs/sy)

            # Draw 4 corners
            painter.fillRect(self.topLeftHandle, QBrush(QColor("#53a0ed")))
            painter.fillRect(self.topRightHandle, QBrush(QColor("#53a0ed")))
            painter.fillRect(self.bottomLeftHandle, QBrush(QColor("#53a0ed")))
            painter.fillRect(self.bottomRightHandle, QBrush(QColor("#53a0ed")))

            # Calculate 4 side coordinates
            self.topHandle = QRectF(0.0 + (source_width / 2.0) - (cs/sx/2.0), 0, cs/sx, cs/sy)
            self.bottomHandle = QRectF(0.0 + (source_width / 2.0) - (cs/sx/2.0), source_height - (cs/sy), cs/sx, cs/sy)
            self.leftHandle = QRectF(0.0, (source_height / 2.0) - (cs/sy/2.0), cs/sx, cs/sy)
            self.rightHandle = QRectF(source_width - (cs/sx), (source_height / 2.0) - (cs/sy/2.0), cs/sx, cs/sy)

            # Draw 4 sides (centered)
            painter.fillRect(self.topHandle, QBrush(QColor("#53a0ed")))
            painter.fillRect(self.bottomHandle, QBrush(QColor("#53a0ed")))
            painter.fillRect(self.leftHandle, QBrush(QColor("#53a0ed")))
            painter.fillRect(self.rightHandle, QBrush(QColor("#53a0ed")))

            # Calculate center coordinate
            self.centerHandle = QRectF((source_width / 2.0) - (os/sx), (source_height / 2.0) - (os/sy), os/sx*2.0, os/sy*2.0)

            # Draw origin
            painter.setBrush(QColor(83, 160, 237, 122))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.centerHandle)

            # Draw translucent rectangle
            self.clipRect = QRectF(0, 0, final_size.width(), final_size.height())

            # Remove transform
            painter.resetTransform()

        # End painter
        painter.end()

        self.mutex.unlock()

    def SetAspectRatio(self, new_aspect_ratio, new_pixel_ratio):
        """ Set a new aspect ratio """
        self.aspect_ratio = new_aspect_ratio
        self.pixel_ratio = new_pixel_ratio

    def centeredViewport(self, width, height):
        """ Calculate size of viewport to maintain apsect ratio """

        aspectRatio = self.aspect_ratio.ToFloat() * self.pixel_ratio.ToFloat()
        heightFromWidth = width / aspectRatio
        widthFromHeight = height * aspectRatio

        if heightFromWidth <= height:
            return QRect(0, (height - heightFromWidth) / 2, width, heightFromWidth)
        else:
            return QRect((width - widthFromHeight) / 2.0, 0, widthFromHeight, height)

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
        self.mouse_pressed = True
        self.mouse_dragging = False
        self.mouse_position = event.pos()
        self.transform_mode = None

        # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
        get_app().updates.ignore_history = True

    def mouseReleaseEvent(self, event):
        """Capture mouse release event on video preview window"""
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.transform_mode = None

        # Inform UpdateManager to accept updates, and only store our final update
        get_app().updates.ignore_history = False

        # Add final update to undo/redo history
        if self.original_clip_data:
            get_app().updates.apply_last_action_to_history(self.original_clip_data)

        # Clear original data
        self.original_clip_data = None

    def mouseMoveEvent(self, event):
        """Capture mouse events on video preview window """
        self.mutex.lock()

        if self.mouse_pressed:
            self.mouse_dragging = True

        if self.transforming_clip:
            # Get framerate
            fps = get_app().project.get(["fps"])
            fps_float = float(fps["num"]) / float(fps["den"])

            # Get current clip's position
            start_of_clip = float(self.transforming_clip.data["start"])
            end_of_clip = float(self.transforming_clip.data["end"])
            position_of_clip = float(self.transforming_clip.data["position"])
            playhead_position = float(get_app().window.preview_thread.current_frame) / fps_float

            # Get the rect where the video is actually drawn (without the black borders, etc...)
            viewport_rect = self.centeredViewport(self.width(), self.height())

            # Make back-up of clip data
            if self.mouse_dragging and not self.transform_mode:
                self.original_clip_data = self.transforming_clip.data

            # Determine if cursor is over a handle
            if self.transform.mapRect(self.topRightHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeBDiagCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_top_right'

            elif self.transform.mapRect(self.topHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeVerCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_top'

            elif self.transform.mapRect(self.topLeftHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeFDiagCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_top_left'

            elif self.transform.mapRect(self.leftHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeHorCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_left'

            elif self.transform.mapRect(self.rightHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeHorCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_right'

            elif self.transform.mapRect(self.bottomLeftHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeBDiagCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_bottom_left'

            elif self.transform.mapRect(self.bottomHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeVerCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_bottom'

            elif self.transform.mapRect(self.bottomRightHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeFDiagCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'scale_bottom_right'

            elif self.transform.mapRect(self.centerHandle).contains(event.pos()):
                self.setCursor(QCursor(Qt.SizeAllCursor))
                # Set the transform mode
                if self.mouse_dragging and not self.transform_mode:
                    self.transform_mode = 'location'
                    # Determine x,y offsets for gravity
                    self.corner_offset_x = event.pos().x() - self.transform.mapRect(self.topLeftHandle).x()
                    self.corner_offset_y = event.pos().y() - self.transform.mapRect(self.topLeftHandle).y()


            elif not self.transform_mode:
                # Reset cursor when not over a handle
                self.setCursor(QCursor(Qt.ArrowCursor))

            # Determine frame # of clip
            start_of_clip_frame = round(float(self.transforming_clip.data["start"]) * fps_float)
            position_of_clip_frame = (float(self.transforming_clip.data["position"]) * fps_float) + 1
            playhead_position_frame = float(get_app().window.preview_thread.current_frame)
            clip_frame_number = round(playhead_position_frame - position_of_clip_frame) + start_of_clip_frame + 1

            # Transform clip object
            if self.transform_mode:
                if self.transform_mode == 'location':
                    # Calculate new location coordinates
                    location_x = (event.pos().x() - self.gravity_point.x() - self.corner_offset_x) / viewport_rect.width()
                    location_y = (event.pos().y() - self.gravity_point.y() - self.corner_offset_y) / viewport_rect.height()

                    # Save new location
                    self.updateProperty(self.transforming_clip.id, clip_frame_number, 'location_x', location_x)
                    self.updateProperty(self.transforming_clip.id, clip_frame_number, 'location_y', location_y)

                elif self.transform_mode.startswith('scale_'):
                    scale_x = None
                    scale_y = None

                    # Calculate new location coordinates
                    center_x = self.transform.mapRect(self.centerHandle).x() + (self.transform.mapRect(self.centerHandle).width() / 2.0)
                    center_y = self.transform.mapRect(self.centerHandle).y() + (self.transform.mapRect(self.centerHandle).height() / 2.0)

                    if self.transform_mode == 'scale_top_right':
                        scale_x = (event.pos().x() - center_x) / (viewport_rect.width() / 2.0)
                        scale_y = (center_y - event.pos().y()) / (viewport_rect.height() / 2.0)
                    elif self.transform_mode == 'scale_bottom_right':
                        scale_x = (event.pos().x() - center_x) / (viewport_rect.width() / 2.0)
                        scale_y = (event.pos().y() - center_y) / (viewport_rect.height() / 2.0)
                    elif self.transform_mode == 'scale_top_left':
                        scale_x = (center_x - event.pos().x()) / (viewport_rect.width() / 2.0)
                        scale_y = (center_y - event.pos().y()) / (viewport_rect.height() / 2.0)
                    elif self.transform_mode == 'scale_bottom_left':
                        scale_x = (center_x - event.pos().x()) / (viewport_rect.width() / 2.0)
                        scale_y = (event.pos().y() - center_y) / (viewport_rect.height() / 2.0)
                    elif self.transform_mode == 'scale_top':
                        scale_y = (center_y - event.pos().y()) / (viewport_rect.height() / 2.0)
                    elif self.transform_mode == 'scale_bottom':
                        scale_y = (event.pos().y() - center_y) / (viewport_rect.height() / 2.0)
                    elif self.transform_mode == 'scale_left':
                        scale_x = (center_x - event.pos().x()) / (viewport_rect.width() / 2.0)
                    elif self.transform_mode == 'scale_right':
                        scale_x = (event.pos().x() - center_x) / (viewport_rect.width() / 2.0)

                    if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
                        # If CTRL key is pressed, fix the scale_y to the correct aspect ration
                        if scale_x and scale_y:
                            scale_y = scale_x
                        elif scale_y:
                            scale_x = scale_y
                        elif scale_x:
                            scale_y = scale_x

                    # Save new location
                    if scale_x != None:
                        self.updateProperty(self.transforming_clip.id, clip_frame_number, 'scale_x', scale_x)
                    if scale_y != None:
                        self.updateProperty(self.transforming_clip.id, clip_frame_number, 'scale_y', scale_y)

            # Force re-paint
            self.update()

        # Update mouse position
        self.mouse_position = event.pos()

        self.mutex.unlock()

    def updateProperty(self, id, frame_number, property_key, new_value):
        """Update a keyframe property to a new value, adding or updating keyframes as needed"""
        found_point = False
        clip_updated = False

        c = Clip.get(id=id)

        for point in c.data[property_key]["Points"]:
            log.info("looping points: co.X = %s" % point["co"]["X"])

            if point["co"]["X"] == frame_number:
                found_point = True
                clip_updated = True
                point["interpolation"] = openshot.BEZIER
                point["co"]["Y"] = float(new_value)

        if not found_point and new_value != None:
            clip_updated = True
            log.info("Created new point at X=%s" % frame_number)
            c.data[property_key]["Points"].append({'co': {'X': frame_number, 'Y': new_value}, 'interpolation': openshot.BEZIER})

        # Reduce # of clip properties we are saving (performance boost)
        c.data = {property_key: c.data.get(property_key)}

        # Save changes
        if clip_updated:
            # Save
            c.save()

            # Update the preview
            get_app().window.refreshFrameSignal.emit()

    def refreshTriggered(self):
        """Signal to refresh viewport (i.e. a property might have changed that effects the preview)"""

        # Update reference to clip
        if self.transforming_clip:
            self.transforming_clip = Clip.get(id=self.transforming_clip.id)

    def transformTriggered(self, clip_id):
        """Handle the transform signal when it's emitted"""
        need_refresh = False
        # Disable Transform UI
        if self.transforming_clip:
            # Is this the same clip_id already being transformed?
            if not clip_id:
                # Clear transform
                self.transforming_clip = None
                need_refresh = True

        # Get new clip for transform
        if clip_id:
            self.transforming_clip = Clip.get(id=clip_id)

            if self.transforming_clip:
                self.transforming_clip_object = None
                clips = get_app().window.timeline_sync.timeline.Clips()
                for clip in clips:
                    if clip.Id() == self.transforming_clip.id:
                        self.transforming_clip_object = clip
                        need_refresh = True
                        break

        # Update the preview and reselct current frame in properties
        if need_refresh:
            get_app().window.refreshFrameSignal.emit()
            get_app().window.propertyTableView.select_frame(get_app().window.preview_thread.player.Position())

    def resizeEvent(self, event):
        """Widget resize event"""
        viewport_rect = self.centeredViewport(event.size().width(), event.size().height())

        # Emit signal that video widget changed size
        self.win.MaxSizeChanged.emit(viewport_rect.size())

    def __init__(self, *args):
        # Invoke parent init
        QWidget.__init__(self, *args)

        # Init aspect ratio settings (default values)
        self.aspect_ratio = openshot.Fraction()
        self.pixel_ratio = openshot.Fraction()
        self.aspect_ratio.num = 16
        self.aspect_ratio.den = 9
        self.pixel_ratio.num = 1
        self.pixel_ratio.den = 1
        self.transforming_clip = None
        self.transforming_clip_object = None
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
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.transform_mode = None
        self.corner_offset_x = None
        self.corner_offset_y = None
        self.clipRect = None
        self.gravity_point = None
        self.original_clip_data = None

        # Mutex lock
        self.mutex = QMutex()

        # Init Qt style properties (black background, ect...)
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#191919"))
        super().setPalette(p)
        super().setAttribute(Qt.WA_OpaquePaintEvent)
        super().setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Set mouse tracking
        self.setMouseTracking(True)

        # Init current frame's QImage
        self.current_image = None

        # Get a reference to the window object
        self.win = get_app().window

        # Connect to signals
        self.win.TransformSignal.connect(self.transformTriggered)
        self.win.refreshFrameSignal.connect(self.refreshTriggered)