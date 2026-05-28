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
import math

from qt_api import Qt, QRectF, QPointF, QSize, QTimer, pyqtSignal, pyqtSlot, QObject, QThread
from qt_api import QIcon, QPainter, QColor, QPen, QBrush, QKeySequence, QImage
from qt_api import (
    QDialog, QSlider, QStyleOptionSlider, QStyle, QShortcut, QSizePolicy,
    QPushButton, QHBoxLayout, QLabel, QMessageBox, QDialogButtonBox,
    QButtonGroup, QToolButton, QCheckBox, QApplication,
)
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, time_parts, qt_types, updates
from classes.app import get_app
from classes.clip_utils import is_single_image_media
from classes.logger import log
from classes.metrics import *
from classes.proxy_service import dialog_preview_reader_data
from windows.preview_thread import PreviewParent
from windows.video_widget import VideoWidget

import json


OBJECT_MASK_PROMPT_SLOTS_MAX = 6
OBJECT_MASK_MAX_POSITIVE_RECTS = OBJECT_MASK_PROMPT_SLOTS_MAX // 2
OBJECT_MASK_MAX_NEGATIVE_FILTERS = 8


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


class ObjectMaskPreviewWorker(QObject):
    finished = pyqtSignal(int, int, object, str)

    def __init__(self, request_id, frame_number, config_json, frame, parent=None):
        super().__init__(parent)
        self.request_id = int(request_id)
        self.frame_number = int(frame_number)
        self.config_json = str(config_json or "")
        self.frame = frame

    @pyqtSlot()
    def run(self):
        try:
            mask_frame = openshot.ClipProcessingJobs.PreviewObjectMask(self.config_json, self.frame)
            if not mask_frame:
                self.finished.emit(self.request_id, self.frame_number, None, "")
                return

            width = int(mask_frame.GetWidth())
            height = int(mask_frame.GetHeight())
            bytes_per_line = int(mask_frame.GetBytesPerLine())
            pixels = mask_frame.GetPixelsBytes()
            if not pixels or width <= 0 or height <= 0 or bytes_per_line <= 0:
                self.finished.emit(self.request_id, self.frame_number, None, "")
                return

            image = QImage(
                pixels,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGBA8888_Premultiplied,
            ).copy()
            self.finished.emit(self.request_id, self.frame_number, image, "")
        except Exception as ex:
            self.finished.emit(self.request_id, self.frame_number, None, str(ex))


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

    def __init__(self, file=None, clip=None, selection_mode="rect", parent=None, object_mask_preview_context=None):
        _ = get_app()._tr

        # Create dialog class
        super().__init__(parent)

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
        self.object_mask_preview_context = dict(object_mask_preview_context or {})
        self._mask_preview_request_id = 0
        self._mask_preview_thread = None
        self._mask_preview_worker = None
        self._mask_preview_dirty = False
        self._mask_preview_wait_cursor = False
        self._mask_preview_timer = QTimer(self)
        self._mask_preview_timer.setSingleShot(True)
        self._mask_preview_timer.setInterval(350)
        self._mask_preview_timer.timeout.connect(self._start_mask_preview)
        self._preview_worker_ready = False
        self._initial_preview_requested = False

        self.start_frame = 1
        self.start_image = None
        self.end_frame = 1
        self.end_image = None
        self.current_frame = 1
        self.file = file
        self.reader_data = dialog_preview_reader_data(file) if file else {}
        self.file_path = str(self.reader_data.get("path") or "")
        is_single_image = bool(is_single_image_media(self.reader_data) or is_single_image_media(getattr(file, "data", {})))

        # Create region clip with Reader
        if clip:
            if self.file_path:
                self.clip = openshot.Clip(self.file_path)
                if not is_single_image:
                    self.clip.SetJson(json.dumps({
                        "reader_orientation_mode": "reader",
                        "reader": self.reader_data,
                    }))
            else:
                self.clip = openshot.Clip(clip.Reader())
            self.clip.Open()
            # Set region clip start and end
            self.clip.Start(clip.Start())
            self.clip.End(clip.End())
        else:
            source_path = self.file_path
            if not source_path and file:
                if hasattr(file, "absolute_path"):
                    source_path = file.absolute_path()
                else:
                    source_path = str(getattr(file, "data", {}).get("path", ""))
            self.clip = openshot.Clip(source_path)
            if self.reader_data and not is_single_image:
                self.clip.SetJson(json.dumps({
                    "reader_orientation_mode": "reader",
                    "reader": self.reader_data,
                }))
            self.clip.Open()
        self.clip.Id(get_app().project.generate_id())

        if not self.file_path:
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
        project = getattr(get_app(), "project", None)
        if project:
            self.sample_rate = int(project.get("sample_rate"))
            self.channels = int(project.get("channels"))
            self.channel_layout = int(project.get("channel_layout"))
        self.video_length = int(self.clip.Duration() * self.fps) + 1

        # Apply effects to region frames
        if clip:
            for effect in clip.Effects():
                self.clip.AddEffect(effect)

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
        self.videoPreview = VideoWidget(watch_project=False)
        self.videoPreview.win = self
        self.videoPreview.setObjectName("videoPreview")
        self.videoPreview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.videoPreview.region_selection_mode = self.selection_mode
        self.videoPreview.region_annotation_limits = self._object_mask_annotation_limits()
        self.videoPreview.regionAnnotationChanged.connect(self._on_video_annotation_changed)
        self.videoPreview.regionAnnotationLimitReached.connect(self._on_annotation_limit_reached)
        self.verticalLayout.insertWidget(1, self.videoPreview)
        if self.selection_mode == "annotate":
            self._build_annotation_toolbar()

        # Set aspect ratio to match source content
        aspect_ratio = openshot.Fraction(self.width, self.height)
        aspect_ratio.Reduce()
        self.videoPreview.aspect_ratio = aspect_ratio

        # Set max size of video preview (for speed)
        self.viewport_rect = self.videoPreview.centeredViewport(self.width, self.height)

        # Create an instance of a libopenshot Timeline object
        self.r = openshot.Timeline(max(2, int(self.width or self.viewport_rect.width() or 2)),
                                   max(2, int(self.height or self.viewport_rect.height() or 2)),
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
        self.videoPreview.delayed_resize_timer.timeout.connect(self._apply_dynamic_preview_max_size)

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
        self._request_initial_preview_frame()

        get_app().window.SelectRegionSignal.emit(self.clip.Id())

    def _preview_ready(self):
        self._preview_worker_ready = True
        self._request_initial_preview_frame()

    def _request_initial_preview_frame(self):
        if self._initial_preview_requested:
            return
        if not getattr(self, "initialized", False):
            return
        if not getattr(self, "_preview_worker_ready", False):
            return
        if not getattr(self, "preview_thread", None):
            return
        self._initial_preview_requested = True
        QTimer.singleShot(0, self._preview_initial_frame)

    def _preview_initial_frame(self):
        preview_thread = getattr(self, "preview_thread", None)
        if not preview_thread:
            return
        preview_thread.previewFrame(max(1, int(self.current_frame or 1)))

    def actionPlay_Triggered(self):
        # Trigger play button (This action is invoked from the preview thread, so it must exist here)
        self.btnPlay.click()

    def keyPressEvent(self, event):
        if event and event.key() == Qt.Key_Escape:
            self.reject()
            event.accept()
            return
        return super(SelectRegion, self).keyPressEvent(event)

    def _target_preview_max_size(self):
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())
        device_pixel_ratio = self.devicePixelRatioF()
        requested = QSize(
            max(2, int(round(viewport_rect.width() * device_pixel_ratio))),
            max(2, int(round(viewport_rect.height() * device_pixel_ratio))),
        )

        source_width = int(getattr(self, "width", 0) or 0)
        source_height = int(getattr(self, "height", 0) or 0)
        file_data = getattr(getattr(self, "file", None), "data", {})
        if is_single_image_media(getattr(self, "reader_data", {})) or is_single_image_media(file_data):
            project = getattr(get_app(), "project", None)
            if project:
                source_width = max(source_width, int(project.get("width") or 0))
                source_height = max(source_height, int(project.get("height") or 0))
        if source_width > 0 and source_height > 0:
            source_size = QSize(source_width, source_height)
            if requested.width() > source_width or requested.height() > source_height:
                capped = QSize(source_size)
            else:
                capped = QSize(requested)
        else:
            capped = requested

        if capped.height() > 0:
            ratio = float(capped.width()) / float(capped.height())
            even_width = max(2, int(round(capped.width() / 2.0) * 2))
            even_height = max(2, int(round(round(even_width / ratio) / 2.0) * 2))
            capped = QSize(even_width, even_height)

        return capped

    def _apply_dynamic_preview_max_size(self):
        if not getattr(self, "initialized", False) or not getattr(self, "r", None):
            return

        new_size = self._target_preview_max_size()
        previous_width = int(getattr(self.r, "preview_width", 0) or 0)
        previous_height = int(getattr(self.r, "preview_height", 0) or 0)

        if previous_width == new_size.width() and previous_height == new_size.height():
            return

        self.PauseSignal.emit()
        self.r.SetMaxSize(new_size.width(), new_size.height())
        self.r.ClearAllCache(True)
        self.viewport_rect = self.videoPreview.centeredViewport(self.width, self.height)
        self.refreshFrameSignal.emit()

    def _icon_path(self, name):
        icon_name = str(name or "").strip()
        for theme_name in ("cosmic", "humanity"):
            path = os.path.join(info.PATH, "themes", theme_name, "images", icon_name)
            if os.path.exists(path):
                return path
        return ""

    def _object_mask_annotation_limits(self):
        return {
            "prompt_slots": OBJECT_MASK_PROMPT_SLOTS_MAX,
            "positive_rects": OBJECT_MASK_MAX_POSITIVE_RECTS,
            "negative_filters": OBJECT_MASK_MAX_NEGATIVE_FILTERS,
        }

    def _sanitize_annotation_payload(self, payload):
        if not isinstance(payload, dict):
            payload = {}

        positive_rects = [r for r in (payload.get("positive_rects") or []) if isinstance(r, dict)]
        positive_rects = positive_rects[:OBJECT_MASK_MAX_POSITIVE_RECTS]

        remaining_positive_slots = max(0, OBJECT_MASK_PROMPT_SLOTS_MAX - (2 * len(positive_rects)))
        positive_points = [p for p in (payload.get("positive_points") or []) if isinstance(p, dict)]
        positive_points = positive_points[:remaining_positive_slots]

        negative_points = [p for p in (payload.get("negative_points") or []) if isinstance(p, dict)]
        negative_points = negative_points[:OBJECT_MASK_MAX_NEGATIVE_FILTERS]
        remaining_negative_slots = max(0, OBJECT_MASK_MAX_NEGATIVE_FILTERS - len(negative_points))
        negative_rects = [r for r in (payload.get("negative_rects") or []) if isinstance(r, dict)]
        negative_rects = negative_rects[:remaining_negative_slots]

        return {
            "positive_points": positive_points,
            "negative_points": negative_points,
            "positive_rects": positive_rects,
            "negative_rects": negative_rects,
        }

    def _on_annotation_limit_reached(self):
        self._refresh_annotation_tool_state()

    def _refresh_annotation_tool_state(self):
        if self.selection_mode != "annotate" or not hasattr(self, "annotation_tool_buttons"):
            return
        can_add = getattr(self.videoPreview, "_can_add_region_annotation", None)
        if not callable(can_add):
            return

        current_tool = str(getattr(self.videoPreview, "region_annotation_tool", "positive_point") or "positive_point")
        first_enabled_tool = None
        for tool_id, button in self.annotation_tool_buttons.items():
            enabled = bool(can_add(tool_id))
            button.setEnabled(enabled)
            if enabled and first_enabled_tool is None:
                first_enabled_tool = tool_id

        current_button = self.annotation_tool_buttons.get(current_tool)
        if current_button is not None and not current_button.isEnabled() and first_enabled_tool:
            next_button = self.annotation_tool_buttons.get(first_enabled_tool)
            if next_button is not None:
                next_button.setChecked(True)
            self._on_annotation_tool_changed(first_enabled_tool)

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

        self.chkMaskPreview = QCheckBox(_("Preview Mask"))
        self.chkMaskPreview.setToolTip(_("Preview the current seed-frame mask using the selected EfficientSAM model."))
        self.chkMaskPreview.setChecked(True)
        if not self._mask_preview_supported():
            self.chkMaskPreview.setChecked(False)
            self.chkMaskPreview.setEnabled(False)
            self.chkMaskPreview.setToolTip(_("Preview requires an updated libopenshot Python module."))
        elif not self._mask_preview_model_path():
            self.chkMaskPreview.setChecked(False)
            self.chkMaskPreview.setEnabled(False)
            self.chkMaskPreview.setToolTip(_("Preview requires a valid EfficientSAM model path."))
        self.chkMaskPreview.stateChanged.connect(self._on_mask_preview_toggle_changed)
        self.annotation_toolbar.addSpacing(8)
        self.annotation_toolbar.addWidget(self.chkMaskPreview)

        self.annotation_toolbar.addStretch(1)

        self.lblDefinedFrames = QLabel("")
        self.annotation_toolbar.addWidget(self.lblDefinedFrames)
        self.verticalLayout.insertLayout(1, self.annotation_toolbar)

        # Default tool
        default_btn = self.annotation_tool_buttons.get("positive_point")
        if default_btn:
            default_btn.setChecked(True)
        self._on_annotation_tool_changed("positive_point")
        self._refresh_annotation_tool_state()

    def _on_annotation_tool_changed(self, tool_id):
        if hasattr(self, "videoPreview") and self.videoPreview is not None:
            self.videoPreview.region_annotation_tool = str(tool_id or "positive_point")
        self._refresh_annotation_tool_state()

    def _mask_preview_model_path(self):
        context = getattr(self, "object_mask_preview_context", {}) or {}
        for key in ("efficient_sam_model", "efficient_sam_model_path", "sam_model", "sam_model_path", "encoder_model"):
            value = str(context.get(key) or "").strip()
            if value:
                return value
        return ""

    def _mask_preview_supported(self):
        try:
            return hasattr(openshot.ClipProcessingJobs, "PreviewObjectMask")
        except Exception:
            return False

    def _mask_preview_enabled(self):
        if self.selection_mode != "annotate":
            return False
        if not self._mask_preview_supported():
            return False
        checkbox = getattr(self, "chkMaskPreview", None)
        if checkbox is not None and not checkbox.isChecked():
            return False
        model_path = self._mask_preview_model_path()
        return bool(model_path and os.path.isfile(model_path))

    def _clear_mask_preview(self):
        if not hasattr(self, "videoPreview") or self.videoPreview is None:
            return
        self.videoPreview.region_mask_preview_image = None
        self.videoPreview.region_mask_preview_frame = None
        self.videoPreview.update()

    def _on_mask_preview_toggle_changed(self, state):
        if state == Qt.Checked:
            self._schedule_mask_preview()
        else:
            self._clear_mask_preview()

    def _has_positive_annotation(self, payload):
        return bool((payload.get("positive_points") or []) or (payload.get("positive_rects") or []))

    def _scale_payload_to_frame_pixels(self, payload, frame):
        if not isinstance(payload, dict) or not frame:
            return payload
        preview_size = getattr(self.videoPreview, "curr_frame_size", None)
        if not preview_size or preview_size.width() <= 0 or preview_size.height() <= 0:
            return payload
        try:
            frame_width = float(frame.GetWidth())
            frame_height = float(frame.GetHeight())
        except Exception:
            return payload
        if frame_width <= 0.0 or frame_height <= 0.0:
            return payload

        scale_x = frame_width / float(preview_size.width())
        scale_y = frame_height / float(preview_size.height())
        scaled = json.loads(json.dumps(payload))
        for key in ("positive_points", "negative_points"):
            for point in scaled.get(key) or []:
                if not isinstance(point, dict):
                    continue
                point["x"] = float(point.get("x", 0.0)) * scale_x
                point["y"] = float(point.get("y", 0.0)) * scale_y
        for key in ("positive_rects", "negative_rects"):
            for rect in scaled.get(key) or []:
                if not isinstance(rect, dict):
                    continue
                rect["x1"] = float(rect.get("x1", 0.0)) * scale_x
                rect["x2"] = float(rect.get("x2", 0.0)) * scale_x
                rect["y1"] = float(rect.get("y1", 0.0)) * scale_y
                rect["y2"] = float(rect.get("y2", 0.0)) * scale_y
        return scaled

    def _schedule_mask_preview(self):
        if not self._mask_preview_enabled():
            self._clear_mask_preview()
            return
        if self.btnPlay.isChecked():
            self._clear_mask_preview()
            return
        payload = self._capture_current_annotation()
        if not self._has_positive_annotation(payload):
            self._clear_mask_preview()
            return
        self._mask_preview_request_id += 1
        self._mask_preview_timer.start()

    def _start_mask_preview(self):
        if not self._mask_preview_enabled() or self.btnPlay.isChecked():
            self._clear_mask_preview()
            return
        if self._mask_preview_thread is not None and self._mask_preview_thread.isRunning():
            self._mask_preview_dirty = True
            return

        frame_number = int(max(1, self.current_frame))
        payload = self._capture_current_annotation()
        if not self._has_positive_annotation(payload):
            self._clear_mask_preview()
            return

        try:
            frame = self.r.GetFrame(frame_number)
        except Exception as ex:
            log.warning("Unable to load frame for Object Mask preview: %s", ex)
            self._clear_mask_preview()
            return
        payload = self._scale_payload_to_frame_pixels(payload, frame)

        context = dict(getattr(self, "object_mask_preview_context", {}) or {})
        context["object_mask_selection"] = {
            "seed_frame": frame_number,
            "frames": {str(frame_number): payload},
        }
        if "processing-device" not in context and "processing_device" not in context:
            context["processing-device"] = "CPU"
        positive_count = len(payload.get("positive_points") or []) + len(payload.get("positive_rects") or [])
        negative_count = len(payload.get("negative_points") or []) + len(payload.get("negative_rects") or [])
        log.debug(
            "Object Mask preview request: frame=%s efficient_sam_model=%s processing_device=%s "
            "positive_prompts=%s negative_prompts=%s",
            frame_number,
            context.get("efficient_sam_model") or context.get("efficient_sam_model_path") or context.get("sam_model"),
            context.get("processing-device") or context.get("processing_device"),
            positive_count,
            negative_count,
        )

        request_id = int(self._mask_preview_request_id)
        self._mask_preview_dirty = False
        thread = QThread(self)
        worker = ObjectMaskPreviewWorker(request_id, frame_number, json.dumps(context), frame)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_mask_preview_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._mask_preview_thread = thread
        self._mask_preview_worker = worker
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._mask_preview_wait_cursor = True
        thread.start()

    def _on_mask_preview_finished(self, request_id, frame_number, image, error):
        if getattr(self, "_mask_preview_wait_cursor", False):
            QApplication.restoreOverrideCursor()
            self._mask_preview_wait_cursor = False
        if error:
            log.warning("Object Mask preview failed: %s", error)
        is_current = (
            int(request_id) == int(self._mask_preview_request_id)
            and int(frame_number) == int(self.current_frame)
            and not self.btnPlay.isChecked()
        )
        if is_current and image is not None:
            log.debug(
                "Object Mask preview ready: request=%s frame=%s size=%sx%s",
                request_id,
                frame_number,
                image.width(),
                image.height(),
            )
            self.videoPreview.region_mask_preview_image = image
            self.videoPreview.region_mask_preview_frame = int(frame_number)
            self.videoPreview.update()
        elif is_current:
            log.debug("Object Mask preview returned no mask: request=%s frame=%s", request_id, frame_number)
            self._clear_mask_preview()

        self._mask_preview_thread = None
        self._mask_preview_worker = None
        if self._mask_preview_dirty:
            self._mask_preview_dirty = False
            self._schedule_mask_preview()

    def _stop_mask_preview_worker(self):
        self._mask_preview_timer.stop()
        self._mask_preview_request_id += 1
        thread = getattr(self, "_mask_preview_thread", None)
        if thread is not None and thread.isRunning():
            thread.quit()
            if not thread.wait(5000):
                log.warning("Waiting for Object Mask preview worker to finish before dialog shutdown.")
                thread.wait()
        if getattr(self, "_mask_preview_wait_cursor", False):
            QApplication.restoreOverrideCursor()
            self._mask_preview_wait_cursor = False
        self._mask_preview_thread = None
        self._mask_preview_worker = None

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

        return self._sanitize_annotation_payload({
            "positive_points": _points_to_payload(self.videoPreview.region_points_positive),
            "negative_points": _points_to_payload(self.videoPreview.region_points_negative),
            "positive_rects": _rects_to_payload(self.videoPreview.region_rects_positive),
            "negative_rects": _rects_to_payload(self.videoPreview.region_rects_negative),
        })

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
            payload = self._sanitize_annotation_payload(self.frame_annotations.get(frame, {}))
        else:
            prior_frames = [f for f in self.frame_annotations.keys() if int(f) <= frame]
            if prior_frames:
                nearest = int(sorted(prior_frames)[-1])
                payload = self._sanitize_annotation_payload(self.frame_annotations.get(nearest, {}))
                inherited = True
        if frame in self.frame_annotations:
            self.frame_annotations[frame] = payload
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
        self.videoPreview.region_mask_preview_image = None
        self.videoPreview.region_mask_preview_frame = None
        self.videoPreview.update()
        self._frame_has_local_keyframe = frame in self.frame_annotations
        self._frame_edited = False
        self._refresh_annotation_tool_state()
        if self._frame_has_local_keyframe and not inherited:
            self._schedule_mask_preview()

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
        self.videoPreview.region_mask_preview_image = None
        self.videoPreview.region_mask_preview_frame = None
        self.videoPreview.update()
        self._refresh_annotation_tool_state()
        self._update_defined_frames_label()
        self._refresh_marker_bar()

    def _on_video_annotation_changed(self):
        if self.selection_mode != "annotate":
            return
        self._frame_edited = True
        self._save_current_frame_annotations(force=True)
        self._refresh_annotation_tool_state()
        self._refresh_marker_bar()
        self._schedule_mask_preview()

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
            self._clear_mask_preview()
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
            if self.selection_mode == "annotate":
                self._clear_mask_preview()
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-pause")
            self.preview_thread.Play()
        else:
            log.info('pause (icon to play)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-start")  # to default
            self.preview_thread.Pause()
            if self.selection_mode == "annotate":
                self._schedule_mask_preview()

        # Send focus back to toolbar
        self.sliderVideo.setFocus()

    def sliderVideo_valueChanged(self, new_frame):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_valueChanged: %s' % new_frame)
            if self.selection_mode == "annotate":
                self._save_current_frame_annotations()
                self._clear_mask_preview()
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
            region_qimage = getattr(self.videoPreview, "region_qimage", None)
            if region_qimage:
                self._selected_region_qimage = region_qimage.copy()
        if self.selection_mode == "annotate":
            self._save_current_frame_annotations()
            self.frame_annotations = {
                int(frame): self._sanitize_annotation_payload(payload)
                for frame, payload in self.frame_annotations.items()
                if isinstance(payload, dict)
            }
            if not self.frame_annotations:
                QMessageBox.warning(self, _("Invalid Selection"), _("Please select at least one point or rectangle."))
                return
            frames_without_positive = [
                int(frame) for frame, payload in self.frame_annotations.items()
                if not self._has_positive_annotation(payload)
            ]
            if frames_without_positive:
                QMessageBox.warning(
                    self,
                    _("Invalid Selection"),
                    _("Each Object Mask frame must include at least one positive point or rectangle."),
                )
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

        self._stop_mask_preview_worker()

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
