"""
 @file
 @brief This file loads the UI for selecting a region of a video (rectangle used for effect processing)
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
import sys
import functools
import math

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QPainter, QColor, QPen, QBrush, QKeySequence
from PyQt5.QtWidgets import *
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, time_parts, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.metrics import *
from windows.preview_thread import PreviewParent
from windows.video_widget import VideoWidget

import json


def normalized_quarter_turn_rotation(rotation):
    """Return clip rotation normalized to 0/90/180/270 when it's a quarter-turn."""
    try:
        rotation_value = float(rotation)
    except (TypeError, ValueError):
        return 0
    normalized = int(round(rotation_value / 90.0)) * 90
    normalized = normalized % 360
    if normalized in (0, 90, 180, 270):
        return normalized
    return 0


def rotated_content_rect(source_width, source_height, rotation):
    """Return the displayed content rect inside the rendered frame for quarter-turn rotations."""
    quarter_turn = normalized_quarter_turn_rotation(rotation)
    if quarter_turn in (90, 270):
        rotated_width = float(source_height)
        rotated_height = float(source_width)
    else:
        rotated_width = float(source_width)
        rotated_height = float(source_height)

    frame_width = float(source_width)
    frame_height = float(source_height)
    if rotated_width <= 0.0 or rotated_height <= 0.0 or frame_width <= 0.0 or frame_height <= 0.0:
        return None

    scale = min(frame_width / rotated_width, frame_height / rotated_height)
    display_width = rotated_width * scale
    display_height = rotated_height * scale
    return QRectF(
        (frame_width - display_width) / 2.0,
        (frame_height - display_height) / 2.0,
        display_width,
        display_height,
    )


def map_display_rect_to_source_rect(rect, source_width, source_height, rotation):
    """Map a selection from the rendered frame back into raw source coordinates."""
    if not isinstance(rect, dict):
        return None

    quarter_turn = normalized_quarter_turn_rotation(rotation)
    if quarter_turn == 0:
        return dict(rect)

    content_rect = rotated_content_rect(source_width, source_height, quarter_turn)
    if not content_rect or content_rect.width() <= 0.0 or content_rect.height() <= 0.0:
        return dict(rect)

    frame_width = float(source_width)
    frame_height = float(source_height)
    left = float(rect.get("normalized_x", 0.0)) * frame_width
    top = float(rect.get("normalized_y", 0.0)) * frame_height
    right = left + float(rect.get("normalized_width", 0.0)) * frame_width
    bottom = top + float(rect.get("normalized_height", 0.0)) * frame_height

    disp_left = (left - content_rect.left()) / content_rect.width()
    disp_top = (top - content_rect.top()) / content_rect.height()
    disp_right = (right - content_rect.left()) / content_rect.width()
    disp_bottom = (bottom - content_rect.top()) / content_rect.height()

    def inverse_rotate_point(x_pos, y_pos):
        if quarter_turn == 90:
            return y_pos, 1.0 - x_pos
        if quarter_turn == 180:
            return 1.0 - x_pos, 1.0 - y_pos
        if quarter_turn == 270:
            return 1.0 - y_pos, x_pos
        return x_pos, y_pos

    mapped_points = [
        inverse_rotate_point(disp_left, disp_top),
        inverse_rotate_point(disp_right, disp_top),
        inverse_rotate_point(disp_left, disp_bottom),
        inverse_rotate_point(disp_right, disp_bottom),
    ]
    xs = [min(1.0, max(0.0, point[0])) for point in mapped_points]
    ys = [min(1.0, max(0.0, point[1])) for point in mapped_points]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return {
        "normalized_x": min_x,
        "normalized_y": min_y,
        "normalized_width": max(0.0, max_x - min_x),
        "normalized_height": max(0.0, max_y - min_y),
    }


class RegionAnnotatedSlider(QSlider):
    frameClicked = pyqtSignal(int)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self._total_frames = 1
        self._current_frame = 1
        self._markers = []  # list of (frame, kind)
        self._marker_positions = []  # list of (x, y, frame)

    def set_frames(self, total_frames, current_frame, markers):
        self._total_frames = int(max(1, total_frames or 1))
        self._current_frame = int(max(1, current_frame or 1))
        self._markers = sorted(list(markers or []), key=lambda item: int(item[0]))
        self.update()

    def _groove_rect(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)

    def _handle_rect(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

    def _x_for_frame(self, frame):
        groove = self._groove_rect()
        left = float(groove.left())
        right = float(groove.right())
        span = max(1.0, right - left)
        if self._total_frames <= 1:
            return int(round(left))
        ratio = float(max(1, min(self._total_frames, int(frame))) - 1) / float(max(1, self._total_frames - 1))
        return int(round(left + ratio * span))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        handle = self._handle_rect().adjusted(-4, -4, 4, 4)
        if handle.contains(event.pos()):
            return super().mousePressEvent(event)
        if not self._marker_positions:
            return super().mousePressEvent(event)
        click_x = int(event.pos().x())
        click_y = int(event.pos().y())
        nearest = min(
            self._marker_positions,
            key=lambda item: (int(item[0]) - click_x) * (int(item[0]) - click_x) + (int(item[1]) - click_y) * (int(item[1]) - click_y),
        )
        dx = abs(int(nearest[0]) - click_x)
        dy = abs(int(nearest[1]) - click_y)
        if dx <= 8 and dy <= 8:
            self.setValue(int(nearest[2]))
            self.frameClicked.emit(int(nearest[2]))
            event.accept()
            return
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        handle = self._handle_rect().adjusted(-4, -4, 4, 4)
        if handle.contains(event.pos()):
            self.unsetCursor()
            return super().mouseMoveEvent(event)
        if self._marker_positions:
            x = int(event.pos().x())
            y = int(event.pos().y())
            nearest = min(
                self._marker_positions,
                key=lambda item: (int(item[0]) - x) * (int(item[0]) - x) + (int(item[1]) - y) * (int(item[1]) - y),
            )
            if abs(int(nearest[0]) - x) <= 8 and abs(int(nearest[1]) - y) <= 8:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.unsetCursor()
        else:
            self.unsetCursor()
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        return super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        groove = self._groove_rect()
        # Center markers on the slider groove line.
        mid_y = int(groove.center().y())

        self._marker_positions = []
        for frame, kind in self._markers:
            x = self._x_for_frame(frame)
            self._marker_positions.append((x, mid_y, int(frame)))
            if kind == "both":
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor("#53A0ED")))
                painter.drawEllipse(x - 4, mid_y - 4, 8, 8)
                painter.setBrush(QBrush(QColor("#E05757")))
                painter.drawEllipse(x, mid_y, 8, 8)
            elif kind == "negative":
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor("#E05757")))
                painter.drawEllipse(x - 4, mid_y - 4, 8, 8)
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor("#53A0ED")))
                painter.drawEllipse(x - 4, mid_y - 4, 8, 8)

        # Current-frame indicator
        cx = self._x_for_frame(self._current_frame)
        cur_pen = QPen(QColor("#EAF5FF"), 1)
        painter.setPen(cur_pen)
        painter.drawLine(cx, max(0, groove.top() - 5), cx, min(self.height() - 1, groove.bottom() + 5))
        painter.end()

class SelectRegion(QDialog):
    """ SelectRegion Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'region.ui')

    # Signals for preview thread
    previewFrameSignal = pyqtSignal(int)
    refreshFrameSignal = pyqtSignal()
    LoadFileSignal = pyqtSignal(str)
    PlaySignal = pyqtSignal()
    PauseSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int)
    LoadTimelineAndSeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    StopSignal = pyqtSignal()

    def __init__(self, file=None, clip=None, selection_mode="rect", parent=None):
        _ = get_app()._tr

        # Create dialog class
        QDialog.__init__(self, parent)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)
        self._esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._esc_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._esc_shortcut.activated.connect(self.reject)
        if parent is None:
            self.setWindowFlags(
                (self.windowFlags() & ~Qt.Dialog)
                | Qt.Window
                | Qt.WindowMinMaxButtonsHint
                | Qt.WindowMaximizeButtonHint
            )
        else:
            self.setWindowModality(Qt.WindowModal)
        self.setSizeGripEnabled(True)

        # Track metrics
        track_metric_screen("cutting-screen")

        self.selection_mode = str(selection_mode or "rect").strip().lower()
        if self.selection_mode not in ("rect", "point", "annotate"):
            self.selection_mode = "rect"
        if self.selection_mode == "annotate":
            # Replace stock UI slider with custom-painted annotation slider
            # so marker dots are perfectly aligned to the slider groove.
            original_slider = self.sliderVideo
            custom_slider = RegionAnnotatedSlider(Qt.Horizontal, original_slider.parent())
            custom_slider.setObjectName(original_slider.objectName())
            custom_slider.setTracking(original_slider.hasTracking())
            if hasattr(self, "horizontalLayout_3"):
                self.horizontalLayout_3.replaceWidget(original_slider, custom_slider)
            original_slider.hide()
            original_slider.deleteLater()
            self.sliderVideo = custom_slider
            self.sliderVideo.frameClicked.connect(self._on_marker_frame_clicked)
        self._selected_points = []
        self._selected_points_negative = []
        self._selected_payload = {}
        self._selected_rect_normalized = None
        self._selected_region_qimage = None
        self.loop_playback = False
        self.frame_annotations = {}
        self._last_annotation_frame = 1
        self._frame_has_local_keyframe = False
        self._frame_edited = False

        self.start_frame = 1
        self.start_image = None
        self.end_frame = 1
        self.end_image = None
        self.current_frame = 1

        # Create region clip with Reader
        if clip:
            self.clip = openshot.Clip(clip.Reader())
            self.clip.Open()
            # Set region clip start and end
            self.clip.Start(clip.Start())
            self.clip.End(clip.End())
        else:
            source_path = ""
            if file:
                if hasattr(file, "absolute_path"):
                    source_path = file.absolute_path()
                else:
                    source_path = str(getattr(file, "data", {}).get("path", ""))
            self.clip = openshot.Clip(source_path)
            self.clip.Open()
        self.clip.Id(get_app().project.generate_id())

        # Keep track of file object
        self.file = file
        if file and hasattr(file, "absolute_path"):
            self.file_path = file.absolute_path()
        else:
            self.file_path = str(getattr(file, "data", {}).get("path", ""))

        c_info = self.clip.Reader().info
        self.fps = c_info.fps.ToInt()
        self.fps_num = c_info.fps.num
        self.fps_den = c_info.fps.den
        self.width = c_info.width
        self.height = c_info.height
        self.sample_rate = int(c_info.sample_rate)
        self.channels = int(c_info.channels)
        self.channel_layout = int(c_info.channel_layout)
        self.video_length = int(self.clip.Duration() * self.fps) + 1
        self.source_rotation = 0

        # Apply effects to region frames
        if clip:
            for effect in clip.Effects():
                self.clip.AddEffect(effect)

        self.source_rotation = self._detect_source_rotation(clip)
        try:
            preview_props = json.loads(self.clip.PropertiesJSON(1))
        except Exception:
            preview_props = {}
        try:
            source_props = json.loads(clip.PropertiesJSON(1)) if clip else {}
        except Exception:
            source_props = {}

        # Open video file with Reader
        log.info(self.clip.Reader())

        # Set instruction text first so it remains above the preview widget.
        if self.selection_mode == "point":
            self.lblInstructions.setText(
                _("Click to add tracking point (SHIFT+Click for additional points, CTRL+Click for negative point)")
            )
        elif self.selection_mode == "annotate":
            self.lblInstructions.setText(
                _("Choose a tool and mark positive/negative points or rectangles. Scrub to edit selections by frame.")
            )
        else:
            self.lblInstructions.setText(_("Draw a rectangle to select a region of the video frame."))

        # Add Video Widget
        self.videoPreview = VideoWidget()
        self.videoPreview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.videoPreview.region_selection_mode = self.selection_mode
        self.videoPreview.regionAnnotationChanged.connect(self._on_video_annotation_changed)
        self.verticalLayout.insertWidget(1, self.videoPreview)
        if self.selection_mode == "annotate":
            self._build_annotation_toolbar()

        # Set aspect ratio to match source content
        aspect_ratio = openshot.Fraction(self.width, self.height)
        aspect_ratio.Reduce()
        self.videoPreview.aspect_ratio = aspect_ratio

        # Set max size of video preview (for speed)
        self.viewport_rect = self.videoPreview.centeredViewport(self.width, self.height)
        log.info(
            "SelectRegion init: source=%sx%s current_rotation=%s display_aspect=%s viewport=%sx%s",
            self.width,
            self.height,
            self.source_rotation,
            self.videoPreview.aspect_ratio.ToFloat() if hasattr(self.videoPreview, "aspect_ratio") else "unknown",
            self.viewport_rect.width(),
            self.viewport_rect.height(),
        )
        log.info(
            "SelectRegion props: preview_clip rotation=%s scale=(%s,%s) location=(%s,%s) gravity=%s; "
            "source_clip rotation=%s scale=(%s,%s) location=(%s,%s) gravity=%s",
            (preview_props.get("rotation") or {}).get("value"),
            (preview_props.get("scale_x") or {}).get("value"),
            (preview_props.get("scale_y") or {}).get("value"),
            (preview_props.get("location_x") or {}).get("value"),
            (preview_props.get("location_y") or {}).get("value"),
            getattr(self.clip, "gravity", None),
            (source_props.get("rotation") or {}).get("value"),
            (source_props.get("scale_x") or {}).get("value"),
            (source_props.get("scale_y") or {}).get("value"),
            (source_props.get("location_x") or {}).get("value"),
            (source_props.get("location_y") or {}).get("value"),
            getattr(clip, "gravity", None) if clip else None,
        )

        # Create an instance of a libopenshot Timeline object
        self.r = openshot.Timeline(self.viewport_rect.width(), self.viewport_rect.height(),
                                   openshot.Fraction(self.fps_num, self.fps_den),
                                   self.sample_rate, self.channels, self.channel_layout)
        self.r.info.channel_layout = self.channel_layout
        self.r.SetMaxSize(self.viewport_rect.width(), self.viewport_rect.height())

        try:
            # Show waveform for audio files
            if not self.clip.Reader().info.has_video and self.clip.Reader().info.has_audio:
                self.clip.Waveform(True)

            # Set has_audio property
            self.r.info.has_audio = self.clip.Reader().info.has_audio

            # Update video_length property of the Timeline object
            self.r.info.video_length = self.video_length

            self.r.AddClip(self.clip)

        except:
            log.error('Failed to load media file into region select player: %s' % self.file_path)
            return

        # Open reader
        self.r.Open()

        # Start the preview thread
        self.initialized = False
        self.transforming_clip = False
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.r, self.videoPreview, self.video_length)
        self.preview_thread = self.preview_parent.worker

        # Set slider constraints
        self.sliderIgnoreSignal = False
        self.sliderVideo.setMinimum(1)
        self.sliderVideo.setMaximum(self.video_length)
        self.sliderVideo.setSingleStep(1)
        self.sliderVideo.setPageStep(24)

        # Display start frame (and then the previous frame)
        QTimer.singleShot(500, functools.partial(self.sliderVideo.setValue, 2))
        QTimer.singleShot(600, functools.partial(self.sliderVideo.setValue, 1))

        # Add buttons
        self.cancel_button = QPushButton(_('Cancel'))
        if self.selection_mode == "rect":
            process_label = _('Select Region')
        elif self.selection_mode == "annotate":
            process_label = _('Apply Selections')
        else:
            process_label = _('Select Point(s)')
        self.process_button = QPushButton(process_label)
        self.buttonBox.addButton(self.process_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.RejectRole)

        # Connect signals
        self.actionPlay.triggered.connect(self.actionPlay_Triggered)
        self.btnPlay.clicked.connect(self.btnPlay_clicked)
        self.sliderVideo.valueChanged.connect(self.sliderVideo_valueChanged)
        self.initialized = True
        if self.selection_mode == "annotate":
            self._load_frame_annotations(1)
            self._update_defined_frames_label()
            self._refresh_marker_bar()

        get_app().window.SelectRegionSignal.emit(self.clip.Id())

    def _detect_source_rotation(self, clip):
        """Detect quarter-turn rotation applied to the displayed source."""
        rotation = 0.0

        if clip:
            try:
                clip_props = json.loads(clip.PropertiesJSON(1))
                rotation = float((clip_props.get("rotation") or {}).get("value", 0.0))
            except Exception:
                log.debug("Unable to read clip rotation for region selection", exc_info=1)

        if normalized_quarter_turn_rotation(rotation):
            return normalized_quarter_turn_rotation(rotation)

        try:
            metadata = self.clip.Reader().info.metadata
            if metadata.count("rotate"):
                rotation = float(metadata["rotate"])
                log.info("SelectRegion reader rotate metadata: %s", rotation)
        except Exception:
            log.debug("Unable to read reader rotate metadata for region selection", exc_info=1)

        return normalized_quarter_turn_rotation(rotation)

    def _log_selected_rect_debug(self, top_left, bottom_right, selected_rect):
        curr_frame_size = getattr(self.videoPreview, "curr_frame_size", None)
        current_image = getattr(self.videoPreview, "current_image", None)
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())
        region_transform = getattr(self.videoPreview, "region_transform", None)
        log.info(
            "SelectRegion rect debug: "
            "top_left=(%s,%s) bottom_right=(%s,%s) "
            "curr_frame_size=%sx%s current_image=%sx%s viewport=%s "
            "zoom=%s source=%sx%s source_rotation=%s "
            "selected_rect=%s transform=%s",
            getattr(top_left, "x", lambda: None)(),
            getattr(top_left, "y", lambda: None)(),
            getattr(bottom_right, "x", lambda: None)(),
            getattr(bottom_right, "y", lambda: None)(),
            curr_frame_size.width() if curr_frame_size else None,
            curr_frame_size.height() if curr_frame_size else None,
            current_image.width() if current_image else None,
            current_image.height() if current_image else None,
            viewport_rect,
            getattr(self.videoPreview, "zoom", None),
            self.width,
            self.height,
            self.source_rotation,
            selected_rect,
            region_transform,
        )

    def actionPlay_Triggered(self):
        # Trigger play button (This action is invoked from the preview thread, so it must exist here)
        self.btnPlay.click()

    def keyPressEvent(self, event):
        if event and event.key() == Qt.Key_Escape:
            self.reject()
            event.accept()
            return
        return super(SelectRegion, self).keyPressEvent(event)

    def _icon_path(self, name):
        icon_name = str(name or "").strip()
        path = os.path.join(info.PATH, "themes", "humanity", "images", icon_name)
        if os.path.exists(path):
            return path
        return ""

    def _build_annotation_toolbar(self):
        _ = get_app()._tr
        self.annotation_toolbar = QHBoxLayout()
        self.annotation_toolbar.setContentsMargins(0, 0, 0, 0)
        self.annotation_toolbar.setSpacing(6)

        self.annotation_tool_group = QButtonGroup(self)
        self.annotation_tool_group.setExclusive(True)
        checked_style = (
            "QToolButton:checked {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "  border: 1px solid palette(highlight);"
            "}"
        )

        tool_defs = [
            ("positive_point", _("Positive Point"), "ai-track-point-positive.svg"),
            ("negative_point", _("Negative Point"), "ai-track-point-negative.svg"),
            ("positive_rect", _("Positive Rectangle"), "ai-track-rect-positive.svg"),
            ("negative_rect", _("Negative Rectangle"), "ai-track-rect-negative.svg"),
        ]
        self.annotation_tool_buttons = {}
        for tool_id, tooltip, icon_name in tool_defs:
            btn = QToolButton(self)
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setIconSize(QSize(18, 18))
            btn.setMinimumSize(QSize(28, 28))
            icon_path = self._icon_path(icon_name)
            if icon_path:
                btn.setIcon(QIcon(icon_path))
            else:
                btn.setText(tooltip)
            btn.setStyleSheet(checked_style)
            btn.clicked.connect(lambda checked=False, t=tool_id: self._on_annotation_tool_changed(t))
            self.annotation_tool_group.addButton(btn)
            self.annotation_tool_buttons[tool_id] = btn
            self.annotation_toolbar.addWidget(btn)

        self.btnClearAnnotation = QToolButton(self)
        self.btnClearAnnotation.setToolTip(_("Clear All Selections"))
        self.btnClearAnnotation.setIconSize(QSize(18, 18))
        self.btnClearAnnotation.setMinimumSize(QSize(28, 28))
        trash_icon = self._icon_path("track-delete-enabled.svg")
        if trash_icon:
            self.btnClearAnnotation.setIcon(QIcon(trash_icon))
        else:
            self.btnClearAnnotation.setText(_("Reset"))
        self.btnClearAnnotation.clicked.connect(self._clear_current_frame_annotations)
        self.annotation_toolbar.addSpacing(8)
        self.annotation_toolbar.addWidget(self.btnClearAnnotation)
        self.annotation_toolbar.addStretch(1)

        self.lblDefinedFrames = QLabel("")
        self.annotation_toolbar.addWidget(self.lblDefinedFrames)
        self.verticalLayout.insertLayout(1, self.annotation_toolbar)

        # Default tool
        default_btn = self.annotation_tool_buttons.get("positive_point")
        if default_btn:
            default_btn.setChecked(True)
        self._on_annotation_tool_changed("positive_point")

    def _on_annotation_tool_changed(self, tool_id):
        if hasattr(self, "videoPreview") and self.videoPreview is not None:
            self.videoPreview.region_annotation_tool = str(tool_id or "positive_point")

    def _capture_current_annotation(self):
        def _points_to_payload(items):
            payload = []
            for p in items or []:
                try:
                    payload.append({"x": float(p.x()), "y": float(p.y())})
                except Exception:
                    continue
            return payload

        def _rects_to_payload(items):
            payload = []
            for r in items or []:
                if not isinstance(r, QRectF):
                    continue
                n = r.normalized()
                payload.append({
                    "x1": float(n.left()),
                    "y1": float(n.top()),
                    "x2": float(n.right()),
                    "y2": float(n.bottom()),
                })
            return payload

        return {
            "positive_points": _points_to_payload(self.videoPreview.region_points_positive),
            "negative_points": _points_to_payload(self.videoPreview.region_points_negative),
            "positive_rects": _rects_to_payload(self.videoPreview.region_rects_positive),
            "negative_rects": _rects_to_payload(self.videoPreview.region_rects_negative),
        }

    def _has_any_annotation(self, payload):
        return bool(
            (payload.get("positive_points") or [])
            or (payload.get("negative_points") or [])
            or (payload.get("positive_rects") or [])
            or (payload.get("negative_rects") or [])
        )

    def _save_current_frame_annotations(self, force=False):
        if self.selection_mode != "annotate":
            return
        frame = int(max(1, self.current_frame))
        if (not force) and (not self._frame_has_local_keyframe) and (not self._frame_edited):
            return
        payload = self._capture_current_annotation()
        if self._has_any_annotation(payload):
            self.frame_annotations[frame] = payload
        elif frame in self.frame_annotations:
            self.frame_annotations.pop(frame, None)
        self._frame_has_local_keyframe = frame in self.frame_annotations
        self._frame_edited = False
        self._update_defined_frames_label()

    def _load_frame_annotations(self, frame):
        if self.selection_mode != "annotate":
            return
        frame = int(max(1, frame))
        payload = {}
        inherited = False
        if frame in self.frame_annotations:
            payload = dict(self.frame_annotations.get(frame, {}))
        else:
            prior_frames = [f for f in self.frame_annotations.keys() if int(f) <= frame]
            if prior_frames:
                nearest = int(sorted(prior_frames)[-1])
                payload = dict(self.frame_annotations.get(nearest, {}))
                inherited = True
        self.videoPreview.region_points_positive = [
            QPointF(float(p.get("x", 0.0)), float(p.get("y", 0.0)))
            for p in (payload.get("positive_points") or [])
            if isinstance(p, dict)
        ]
        self.videoPreview.region_points_negative = [
            QPointF(float(p.get("x", 0.0)), float(p.get("y", 0.0)))
            for p in (payload.get("negative_points") or [])
            if isinstance(p, dict)
        ]
        self.videoPreview.region_rects_positive = [
            QRectF(
                QPointF(float(r.get("x1", 0.0)), float(r.get("y1", 0.0))),
                QPointF(float(r.get("x2", 0.0)), float(r.get("y2", 0.0))),
            ).normalized()
            for r in (payload.get("positive_rects") or [])
            if isinstance(r, dict)
        ]
        self.videoPreview.region_rects_negative = [
            QRectF(
                QPointF(float(r.get("x1", 0.0)), float(r.get("y1", 0.0))),
                QPointF(float(r.get("x2", 0.0)), float(r.get("y2", 0.0))),
            ).normalized()
            for r in (payload.get("negative_rects") or [])
            if isinstance(r, dict)
        ]
        self.videoPreview.region_rect_drag_start = None
        self.videoPreview.region_rect_drag_current = None
        self.videoPreview.region_annotation_inherited = bool(inherited)
        self.videoPreview.update()
        self._frame_has_local_keyframe = frame in self.frame_annotations
        self._frame_edited = False

    def _clear_current_frame_annotations(self):
        if self.selection_mode != "annotate":
            return
        self.frame_annotations = {}
        self._frame_has_local_keyframe = False
        self._frame_edited = False
        self.videoPreview.region_points_positive = []
        self.videoPreview.region_points_negative = []
        self.videoPreview.region_rects_positive = []
        self.videoPreview.region_rects_negative = []
        self.videoPreview.region_rect_drag_start = None
        self.videoPreview.region_rect_drag_current = None
        self.videoPreview.region_annotation_inherited = False
        self.videoPreview.update()
        self._update_defined_frames_label()
        self._refresh_marker_bar()

    def _on_video_annotation_changed(self):
        if self.selection_mode != "annotate":
            return
        self._frame_edited = True
        self._save_current_frame_annotations(force=True)
        self._refresh_marker_bar()

    def _update_defined_frames_label(self):
        if self.selection_mode != "annotate" or not hasattr(self, "lblDefinedFrames"):
            return
        frames = sorted(self.frame_annotations.keys())
        if not frames:
            self.lblDefinedFrames.setText("")
            return
        preview = ", ".join(str(f) for f in frames[:10])
        if len(frames) > 10:
            preview = "{} ...".format(preview)
        self.lblDefinedFrames.setText(get_app()._tr("Frames: {}").format(preview))
        self._refresh_marker_bar()

    def _refresh_marker_bar(self):
        if self.selection_mode != "annotate" or not hasattr(self, "sliderVideo"):
            return
        if not hasattr(self.sliderVideo, "set_frames"):
            return
        markers = []
        for frame in sorted(self.frame_annotations.keys()):
            payload = self.frame_annotations.get(frame, {}) or {}
            has_pos = bool((payload.get("positive_points") or []) or (payload.get("positive_rects") or []))
            has_neg = bool((payload.get("negative_points") or []) or (payload.get("negative_rects") or []))
            kind = "both" if (has_pos and has_neg) else ("negative" if has_neg else "positive")
            markers.append((int(frame), kind))
        self.sliderVideo.set_frames(self.video_length, self.current_frame, markers)

    def _on_marker_frame_clicked(self, frame_number):
        frame_number = int(max(1, min(int(frame_number), int(self.video_length))))
        self.sliderVideo.setValue(frame_number)

    def selection_payload(self):
        return dict(self._selected_payload or {})

    def selected_rect_normalized(self):
        if isinstance(self._selected_rect_normalized, dict):
            return dict(self._selected_rect_normalized)
        return None

    def selected_region_qimage(self):
        return self._selected_region_qimage

    def movePlayhead(self, frame_number):
        """Update the playhead position"""

        if self.selection_mode == "annotate" and int(frame_number) != int(self.current_frame):
            self._save_current_frame_annotations()
        self.current_frame = frame_number
        # Move slider to correct frame position
        self.sliderIgnoreSignal = True
        self.sliderVideo.setValue(frame_number)
        self.sliderIgnoreSignal = False

        # Convert frame to seconds
        seconds = (frame_number-1) / self.fps

        # Convert seconds to time stamp
        time_text = time_parts.secondsToTime(seconds, self.fps_num, self.fps_den)
        timestamp = "%s:%s:%s:%s" % (time_text["hour"], time_text["min"], time_text["sec"], time_text["frame"])

        # Update label
        self.lblVideoTime.setText(timestamp)
        if self.selection_mode == "annotate":
            self._load_frame_annotations(frame_number)
            self._refresh_marker_bar()

    def btnPlay_clicked(self, force=None):
        log.info("btnPlay_clicked")

        if force == "pause":
            self.btnPlay.setChecked(False)
        elif force == "play":
            self.btnPlay.setChecked(True)

        if self.btnPlay.isChecked():
            log.info('play (icon to pause)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-pause")
            self.preview_thread.Play()
        else:
            log.info('pause (icon to play)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-start")  # to default
            self.preview_thread.Pause()

        # Send focus back to toolbar
        self.sliderVideo.setFocus()

    def sliderVideo_valueChanged(self, new_frame):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_valueChanged: %s' % new_frame)
            if self.selection_mode == "annotate":
                self._save_current_frame_annotations()
                self.current_frame = int(new_frame)
                self._load_frame_annotations(new_frame)
                self._refresh_marker_bar()

            # Pause video
            self.btnPlay_clicked(force="pause")

            # Seek to new frame
            self.preview_thread.previewFrame(new_frame)

    def accept(self):
        """ Ok button clicked """
        # get translations
        app = get_app()
        _ = app._tr

        # Legacy behavior for rect/point modes: require frame 1 selection.
        if self.selection_mode in ("rect", "point") and self.sliderVideo.value() != self.sliderVideo.minimum():
            # Show a warning message box to the user
            QMessageBox.warning(self, _("Invalid Region"),
                                _("Please choose a region at the beginning of the clip"))

            # Reset the slider to its minimum value
            self.sliderVideo.setValue(self.sliderVideo.minimum())
            return

        if self.selection_mode == "point" and not self.videoPreview.region_points_positive:
            QMessageBox.warning(self, _("Invalid Selection"), _("Please select at least one point."))
            return
        if self.selection_mode == "rect":
            top_left = getattr(self.videoPreview, "regionTopLeftHandle", None)
            bottom_right = getattr(self.videoPreview, "regionBottomRightHandle", None)
            if top_left is None or bottom_right is None:
                QMessageBox.warning(self, _("Invalid Selection"), _("Please draw a rectangle region."))
                return
            curr_frame_size = getattr(self.videoPreview, "curr_frame_size", None)
            if curr_frame_size and curr_frame_size.width() > 0 and curr_frame_size.height() > 0:
                x1 = float(top_left.x()) / float(curr_frame_size.width())
                y1 = float(top_left.y()) / float(curr_frame_size.height())
                x2 = float(bottom_right.x()) / float(curr_frame_size.width())
                y2 = float(bottom_right.y()) / float(curr_frame_size.height())
                left = min(x1, x2)
                top = min(y1, y2)
                right = max(x1, x2)
                bottom = max(y1, y2)
                self._selected_rect_normalized = {
                    "normalized_x": left,
                    "normalized_y": top,
                    "normalized_width": max(0.0, right - left),
                    "normalized_height": max(0.0, bottom - top),
                }
                self._log_selected_rect_debug(top_left, bottom_right, self._selected_rect_normalized)
                self._selected_rect_normalized = map_display_rect_to_source_rect(
                    self._selected_rect_normalized,
                    self.width,
                    self.height,
                    self.source_rotation,
                )
                log.info("SelectRegion final rect passed to tracker: %s", self._selected_rect_normalized)
            region_qimage = getattr(self.videoPreview, "region_qimage", None)
            if region_qimage:
                self._selected_region_qimage = region_qimage.copy()
        if self.selection_mode == "annotate":
            self._save_current_frame_annotations()
            if not self.frame_annotations:
                QMessageBox.warning(self, _("Invalid Selection"), _("Please select at least one point or rectangle."))
                return
            sorted_frames = sorted(self.frame_annotations.keys())
            seed_frame = int(sorted_frames[0]) if sorted_frames else int(self.current_frame)
            self._selected_payload = {
                "version": 1,
                "seed_frame": seed_frame,
                "frames": {
                    str(frame): dict(self.frame_annotations.get(frame, {}))
                    for frame in sorted_frames
                },
            }
        else:
            self._selected_payload = {}

        # Continue with the rest of the accept method
        self._selected_points = self.selected_points()
        self._selected_points_negative = self.selected_points_negative()
        self.shutdownPlayer()
        get_app().window.SelectRegionSignal.emit("")
        super(SelectRegion, self).accept()

    def shutdownPlayer(self):

        log.info('shutdownPlayer')

        # Stop playback
        self.preview_parent.Stop()

        # Close readers
        self.clip.Close()
        # self.r.RemoveClip(self.clip)
        self.r.Close()
        # self.clip.Close()
        self.r.ClearAllCache()

    def reject(self):

        # Cancel dialog
        self.shutdownPlayer()
        get_app().window.SelectRegionSignal.emit("")
        super(SelectRegion, self).reject()

    def selected_points(self):
        if self._selected_points:
            return list(self._selected_points)
        points = []
        for point in getattr(self.videoPreview, "region_points_positive", []) or []:
            points.append({"x": float(point.x()), "y": float(point.y())})
        return points

    def selected_points_negative(self):
        if self._selected_points_negative:
            return list(self._selected_points_negative)
        points = []
        for point in getattr(self.videoPreview, "region_points_negative", []) or []:
            points.append({"x": float(point.x()), "y": float(point.y())})
        return points
