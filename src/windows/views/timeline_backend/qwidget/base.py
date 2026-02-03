"""
 @file
 @brief This file contains a custom QWidget-based timeline - to replace older, webview-based timelines
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

import json
from functools import partial

from PyQt5.QtCore import (
    Qt,
    QRectF,
    QSize,
    QTimer,
    QPointF,
    QSignalTransition,
    QByteArray,
    pyqtSignal,
    QObject,
    QMetaMethod,
    QVariantAnimation,
    QEasingCurve,
)
from PyQt5.QtGui import (
    QPainter,
    QCursor,
    QIcon,
    QColor,
)
from PyQt5.QtWidgets import QSizePolicy, QWidget

from ..geometry import Geometry
from ..paint import (
    BackgroundPainter,
    PlaybackCachePainter,
    ClipPainter,
    TransitionPainter,
    MarkerPainter,
    PlayheadPainter,
    RulerPainter,
    TrackPainter,
    KeyframePanelPainter,
    SelectionPainter,
    ScrollbarPainter,
    KeyframePainter,
)
from ..snap import SnapHelper
from ..theme import DEFAULT_THEME, apply_theme as parse_theme
from ..state import TimelineStateMachine
from windows.views.menu import StyledContextMenu
from classes.app import get_app
from classes.query import Clip, Transition, File
from classes.logger import log
from .thumbnails import TimelineThumbnailManager


class TimelineEvents(QObject):
    pressed = pyqtSignal(object)
    moved = pyqtSignal(object)
    released = pyqtSignal(object)


def _normalize_signal_bytes(signature):
    sig_bytes = bytes(signature)
    if sig_bytes[:1].isdigit():
        sig_bytes = sig_bytes[1:]
    return sig_bytes


def _collect_signal_signatures(qobject_type):
    """Return a mapping of signal name -> normalized signature bytes."""

    meta = qobject_type.staticMetaObject
    offset = meta.methodOffset()
    signatures = {}
    for i in range(offset, meta.methodCount()):
        method = meta.method(i)
        if method.methodType() == QMetaMethod.Signal:
            signature = _normalize_signal_bytes(method.methodSignature())
            name = signature.split(b"(", 1)[0].decode("latin-1")
            signatures[name] = signature
    return signatures


_TIMELINE_EVENT_SIGNATURES = _collect_signal_signatures(TimelineEvents)


class _ConditionalTransition(QSignalTransition):
    def __init__(self, sender, signal_bytes, source_state, target_state, condition):
        """Create a QSignalTransition that evaluates a condition before firing."""

        super().__init__(source_state)

        parent = source_state
        if parent is None and target_state is not None:
            parent = target_state.machine()
        if parent is not None:
            self.setParent(parent)

        normalized = _normalize_signal_bytes(signal_bytes)
        self._signal_signature = QByteArray(normalized)
        self._sender = sender
        self._signal_bytes = normalized
        self._condition = condition

        self.setSenderObject(sender)
        self.setSignal(self._signal_signature)
        self.setTargetState(target_state)

    def eventTest(self, event):
        return super().eventTest(event) and self._condition()


class TimelineWidgetBase(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Enable drag and drop
        self.new_item = None
        self.item_type = None
        self.setAcceptDrops(True)

        # Translate object
        _ = get_app()._tr

        # Init default values
        self.leftHandle = None
        self.rightHandle = None
        self.centerHandle = None
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.mouse_position = None
        self.zoom_factor = 15.0
        self.scrollbar_position = [0.0, 0.0, 0.0, 0.0]
        self.scrollbar_position_previous = [0.0, 0.0, 0.0, 0.0]
        self.v_scrollbar_position = [0.0, 0.0, 0.0, 0.0]
        self.v_scrollbar_position_previous = [0.0, 0.0, 0.0, 0.0]
        self.h_scroll_offset = 0.0
        self._external_zoom_span = None
        self.left_handle_rect = QRectF()
        self.left_handle_dragging = False
        self.right_handle_rect = QRectF()
        self.right_handle_dragging = False
        self.scroll_bar_rect = QRectF()
        self.scroll_bar_dragging = False
        self.v_scroll_bar_rect = QRectF()
        self.v_scroll_bar_dragging = False
        self.timeline_resize_handle_rect = QRectF()
        self.clip_rects = []
        self.clip_rects_selected = []
        self.marker_rects = []
        self.current_frame = 0
        self.is_auto_center = True
        self.min_distance = 0.02
        self.track_rects = []
        self.track_list = []
        self.pixels_per_second = 1.0
        self.vertical_factor = 1.0
        self.track_height = 48
        self.track_gap = 8
        self.track_margin_top = self.track_gap
        self._playback_cache_ranges = []
        self._track_panel_enabled = {}
        self._panel_properties = {}
        self._panel_heights = {}
        self._panel_refresh_signature = None
        self._panel_selected_keyframes = {}
        self._panel_box_track = None
        self._panel_box_bounds = QRectF()
        self._panel_press_info = None
        self._dragging_panel_keyframes = None
        self._panel_sparse_properties = set()
        self._panel_manual_properties = {}
        self.keyframe_panel_row_height = 24.0
        self.keyframe_panel_row_spacing = 4.0
        self.keyframe_panel_padding = 6.0

        # Wheel scrolling helpers
        self._pending_vscroll_delta = 0.0
        self._vscroll_timer = QTimer(self)
        self._vscroll_timer.setSingleShot(True)
        self._vscroll_timer.timeout.connect(self._flush_pending_vertical_scroll)

        # Wheel zoom helpers
        self._zoom_emit_timer = QTimer(self)
        self._zoom_emit_timer.setSingleShot(True)
        self._zoom_emit_timer.setInterval(50)
        self._zoom_emit_timer.timeout.connect(self._emit_pending_zoom)
        self._pending_zoom_emit = None

        # Smooth zoom animation (~150ms, Figma/After Effects–style)
        self._zoom_animation = QVariantAnimation(self)
        self._zoom_animation.setDuration(150)
        self._zoom_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._zoom_animation.valueChanged.connect(self._on_zoom_animation_value)
        self._zoom_animation.finished.connect(self._on_zoom_animation_finished)

        # Internal flag to defer repaint scheduling from changed()
        self._suspend_changed_update = 0

        # Guard against re-entrant paintEvent calls
        self._in_paint_event = False

        # Strong references to dynamically created state transitions
        self._transitions = []

        # Geometry constants
        self.ruler_height = 40
        self.track_name_width = 140
        self.scroll_bar_thickness = 12
        self._resize_handle_width = 6
        self.resizing_track_names = False
        self.resize_handle_rect = QRectF()
        self._project_handle_width = 10.0
        self._project_duration_override = None
        self._project_resize_initial_duration = 0.0
        self._project_resize_min_duration = 0.0
        self._project_resize_keep_right = False

        # Drag/selection helpers
        self.selection_rect = QRectF()
        self.box_selecting = False
        self.box_start = QPointF()
        self.dragging_item = None
        self.drag_clip_offset = 0.0
        self.drag_clip_start = 0.0
        self.dragging_playhead = False
        self.drag_bbox = QRectF()
        self._drag_transaction_id = None
        self._drag_moved = False
        self._drag_press_pos = None
        self._drag_threshold_met = False

        # Resize / timing helpers
        self.enable_timing = False
        self.enable_snapping = True
        self.enable_razor = False
        self._resizing_item = None
        self._resize_edge = None
        self._resize_initial_rect = QRectF()
        self._resize_initial = {}
        self._timing_original_start = 0.0
        self._fixed_cursor = None

        # Cached Qt text flags
        self._clip_text_flags = Qt.AlignLeft | Qt.AlignTop

        # Track toolbar interaction state
        self._toolbar_hover_key = None
        self._toolbar_pressed_key = None
        self._toolbar_pressed_inside = False

        # Frames per second float value
        fps_info = get_app().project.get("fps")
        self.fps_float = float(fps_info.get("num", 24)) / float(fps_info.get("den", 1) or 1)

        # Theme settings
        self.theme = DEFAULT_THEME

        # Thumbnail helpers
        self.thumbnail_style = self._load_thumbnail_style()
        self.thumbnail_generation = 0
        self.thumbnail_manager = TimelineThumbnailManager(self)
        self._viewport_thumbnail_reset_timer = QTimer(self)
        self._viewport_thumbnail_reset_timer.setSingleShot(True)
        self._viewport_thumbnail_reset_timer.setInterval(150)
        self._viewport_thumbnail_reset_timer.timeout.connect(self._apply_viewport_thumbnail_reset)

        # Helpers for geometry, snapping and painting
        self.geometry = Geometry(self)
        self.snap = SnapHelper(self, self.geometry)
        self.bg_painter = BackgroundPainter(self)
        self.ruler_painter = RulerPainter(self)
        self.track_painter = TrackPainter(self)
        self.playback_cache_painter = PlaybackCachePainter(self)
        self.clip_painter = ClipPainter(self)
        self.transition_painter = TransitionPainter(self)
        self.marker_painter = MarkerPainter(self)
        self.playhead_painter = PlayheadPainter(self)
        self.keyframe_painter = KeyframePainter(self)
        self.keyframe_panel_painter = KeyframePanelPainter(self)
        self.selection_painter = SelectionPainter(self)
        self.scrollbar_painter = ScrollbarPainter(self)
        self.thumbnail_manager.thumbnail_ready.connect(
            self.clip_painter.handle_thumbnail_ready
        )

        # Keyframe helpers
        self._keyframe_markers = []
        self._keyframe_marker_offsets = (None, None)
        self._keyframes_dirty = True
        self._dragging_keyframe = None
        self._press_keyframe = None
        self._press_keyframe_clear = True
        self._press_effect_icon = None
        self._pending_clip_overrides = {}
        self._pending_transition_overrides = {}
        self._preserve_overrides_once = False
        self._drag_payload = None
        self._drag_preview_items = []
        self._drag_preview_type = None
        self._snap_ignore_ids = set()
        self._snap_keyframe_seconds = []
        self._snap_active_targets = {}
        self._press_marker = None

        # Apply default theme
        self.apply_theme("")

        # Load icon (using display DPI)
        self.cursors = {}
        for cursor_name in ["move", "resize_x", "hand"]:
            icon = QIcon(":/cursors/cursor_%s.png" % cursor_name)
            self.cursors[cursor_name] = QCursor(icon.pixmap(24, 24))

        # Init Qt widget's properties (background repainting, etc...)
        super().setAttribute(Qt.WA_OpaquePaintEvent)
        super().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)

        # Set mouse tracking
        self.setMouseTracking(True)

        # Get a reference to the window object
        self.win = get_app().window
        self.win.ThemeChangedSignal.connect(self.apply_theme)

        # Connect zoom functionality
        self.win.TimelineScrolled.connect(self.update_scrollbars)
        self.win.TimelineScroll.connect(self.set_scroll_left)
        self.win.TimelineZoom.connect(self._apply_external_zoom)

        self.win.TimelineResize.connect(self.delayed_resize_callback)

        # Connect Selection signals
        self.win.SelectionChanged.connect(self.handle_selection)

        # Show Property timer
        # Timer to use a delay before sending MaxSizeChanged signals (so we don't spam libopenshot)
        self.delayed_size = None
        self.delayed_resize_timer = QTimer(self)
        self.delayed_resize_timer.setInterval(100)
        self.delayed_resize_timer.setSingleShot(True)
        self.delayed_resize_timer.timeout.connect(self.delayed_resize_callback)

        # Initial geometry setup
        self.changed(None)

        # State machine for mouse interactions
        self.events = TimelineEvents(self)
        self._last_event = None
        self._press_hit = None
        self._buildStateMachine()

        # Effect icon hit targets (populated by the clip painter)
        self._effect_icon_rects = []

        # Middle-mouse panning helpers
        self._middle_panning = False
        self._middle_pan_anchor = QPointF()
        self._middle_pan_scroll_start = [0.0, 0.0, 0.0, 0.0]
        self._middle_pan_vscroll_start = [0.0, 0.0, 0.0, 0.0]

    def _normalize_thumbnail_style(self, style):
        """Normalize and validate thumbnail style values."""
        style = str(style or "").strip().lower()
        valid = {"none", "start", "start-end", "entire"}
        return style if style in valid else "entire"

    def _load_thumbnail_style(self):
        """Return the preferred thumbnail rendering style."""
        style = get_app().get_settings().get("timeline-thumbnail-style")
        return self._normalize_thumbnail_style(style)

    def set_thumbnail_style(self, style):
        """Update the thumbnail rendering style and refresh the timeline."""
        normalized = self._normalize_thumbnail_style(style)
        if normalized == getattr(self, "thumbnail_style", None):
            return

        self.thumbnail_style = normalized
        self._reset_thumbnail_requests()
        self.clip_painter.clear_cache()
        self.update()

    def _reset_thumbnail_requests(self):
        """Cancel pending thumbnail work after a major viewport change."""
        self.thumbnail_generation += 1
        if self.thumbnail_manager:
            self.thumbnail_manager.clear_pending()
        if hasattr(self, "clip_painter"):
            self.clip_painter.expire_thumbnail_requests(self.thumbnail_generation)

    def _buildStateMachine(self):
        sm = TimelineStateMachine(self)

        idle = sm.idle
        drag = sm.drag
        resize = sm.resize
        playhead = sm.playhead
        boxsel = sm.box
        keydrag = sm.keyframe

        drag.entered.connect(self._startClipDrag)
        drag.exited.connect(self._finishClipDrag)
        resize.entered.connect(self._startResize)
        resize.exited.connect(self._finishResize)
        playhead.entered.connect(self._startPlayhead)
        playhead.exited.connect(self._finishPlayhead)
        boxsel.entered.connect(self._startBoxSelect)
        boxsel.exited.connect(self._finishBoxSelect)
        keydrag.entered.connect(self._startKeyframeDrag)
        keydrag.exited.connect(self._finishKeyframeDrag)

        sender, pressed_signal = self._event_signal("pressed")

        t = _ConditionalTransition(sender, pressed_signal, idle, drag, lambda: self._press_hit == "clip")
        idle.addTransition(t)
        self._transitions.append(t)

        t = _ConditionalTransition(sender, pressed_signal, idle, resize, lambda: self._press_hit in ("handle", "timeline-handle", "clip-edge"))
        idle.addTransition(t)
        self._transitions.append(t)

        t = _ConditionalTransition(sender, pressed_signal, idle, playhead, lambda: self._press_hit == "ruler")
        idle.addTransition(t)
        self._transitions.append(t)

        t = _ConditionalTransition(sender, pressed_signal, idle, boxsel, lambda: self._press_hit in ("background", "panel"))
        idle.addTransition(t)
        self._transitions.append(t)

        t = _ConditionalTransition(sender, pressed_signal, idle, keydrag, lambda: self._press_hit in ("keyframe", "panel-keyframe"))
        idle.addTransition(t)
        self._transitions.append(t)

        drag.entered.connect(lambda: self.events.moved.connect(self._dragMove))
        drag.exited.connect(lambda: self._safe_disconnect(self.events.moved, self._dragMove))
        self._add_simple_transition(drag, self.events, self._event_signal_bytes("released"), idle)

        resize.entered.connect(lambda: self.events.moved.connect(self._resizeMove))
        resize.exited.connect(lambda: self._safe_disconnect(self.events.moved, self._resizeMove))
        self._add_simple_transition(resize, self.events, self._event_signal_bytes("released"), idle)

        playhead.entered.connect(lambda: self.events.moved.connect(self._playheadMove))
        playhead.exited.connect(lambda: self._safe_disconnect(self.events.moved, self._playheadMove))
        self._add_simple_transition(playhead, self.events, self._event_signal_bytes("released"), idle)

        boxsel.entered.connect(lambda: self.events.moved.connect(self._boxMove))
        boxsel.exited.connect(lambda: self._safe_disconnect(self.events.moved, self._boxMove))
        self._add_simple_transition(boxsel, self.events, self._event_signal_bytes("released"), idle)

        keydrag.entered.connect(lambda: self.events.moved.connect(self._keyframeMove))
        keydrag.exited.connect(lambda: self._safe_disconnect(self.events.moved, self._keyframeMove))
        self._add_simple_transition(keydrag, self.events, self._event_signal_bytes("released"), idle)

        # repaint exactly once when any interactive state exits
        for s in (drag, resize, playhead, boxsel, keydrag):
            s.exited.connect(self.update)

        sm.setInitialState(idle)
        sm.start()
        self._sm = sm

    def _event_signal(self, name):
        return self.events, self._event_signal_bytes(name)

    def _add_simple_transition(self, source_state, sender, sig_bytes, target_state):
        t = QSignalTransition(source_state)
        normalized = _normalize_signal_bytes(sig_bytes)
        t.setSenderObject(sender)
        t.setSignal(QByteArray(normalized))
        t.setTargetState(target_state)
        source_state.addTransition(t)
        self._transitions.append(t)
        return t

    def _event_signal_bytes(self, name):
        signature = _TIMELINE_EVENT_SIGNATURES.get(name)
        if signature is None:
            raise ValueError(f"Unknown TimelineEvents signal '{name}'")
        return signature

    def _safe_disconnect(self, signal, slot):
        try:
            signal.disconnect(slot)
        except TypeError:
            pass

    def _current_project_duration(self):
        override = getattr(self, "_project_duration_override", None)
        if override is not None:
            try:
                return max(0.0, float(override))
            except (TypeError, ValueError):
                pass
        project = get_app().project
        return max(0.0, float(project.get("duration") or 0.0))

    def _furthest_timeline_edge(self):
        furthest = 0.0
        for clip in Clip.filter():
            data = clip.data if isinstance(clip.data, dict) else {}
            position = float(data.get("position", 0.0) or 0.0)
            start = float(data.get("start", 0.0) or 0.0)
            end = float(data.get("end", start) or start)
            duration = max(0.0, end - start)
            finish = position + duration
            if finish > furthest:
                furthest = finish
        for tran in Transition.filter():
            data = tran.data if isinstance(tran.data, dict) else {}
            position = float(data.get("position", 0.0) or 0.0)
            start = float(data.get("start", 0.0) or 0.0)
            end = float(data.get("end", start) or start)
            duration = max(0.0, end - start)
            finish = position + duration
            if finish > furthest:
                furthest = finish
        return furthest

    def _is_view_right_aligned(self):
        timeline_w = self.scrollbar_position[2] or 0.0
        view_w = self.scrollbar_position[3] or 0.0
        if timeline_w <= view_w + 1e-6:
            return True
        right = self.scrollbar_position[1]
        return right >= 1.0 - 1e-4

    def _set_project_duration_override(self, duration):
        if duration is None:
            self._project_duration_override = None
        else:
            try:
                self._project_duration_override = max(0.0, float(duration))
            except (TypeError, ValueError):
                self._project_duration_override = None
        self.geometry.mark_dirty()
        self.update()

    def _content_height_hint(self):
        """Estimate content height for size hint calculations."""
        self.geometry.ensure()
        ctx = getattr(self.geometry, "_view_context", {}) or {}
        content = ctx.get("content_h")
        if content is None:
            tracks = getattr(self.geometry, "track_list", []) or []
            count = len(tracks) or 1
            base_height = float(self.track_height or self.vertical_factor or 0.0)
            gap = float(self.track_gap or 0.0)
            margin = float(self.track_margin_top or 0.0)
            content = margin + count * base_height
            if count > 1:
                content += (count - 1) * gap
        try:
            return max(0.0, float(content))
        except (TypeError, ValueError):
            return 0.0

    def _size_hint_height(self):
        ruler = max(0.0, float(self.ruler_height or 0.0))
        bar = max(0.0, float(self.scroll_bar_thickness or 0.0))
        return int(round(self._content_height_hint() + ruler + bar))

    def sizeHint(self):
        self.geometry.ensure()
        ctx = getattr(self.geometry, "_view_context", {}) or {}
        timeline_w = max(
            float(ctx.get("timeline_w") or 0.0),
            float(ctx.get("view_w") or 0.0),
        )
        width = max(
            float(self.width() or 0.0),
            timeline_w + float(self.track_name_width or 0.0) + float(self.scroll_bar_thickness or 0.0),
        )
        return QSize(int(round(width)), self._size_hint_height())

    def minimumSizeHint(self):
        min_w = float(self.track_name_width or 0.0) + float(self.scroll_bar_thickness or 0.0)
        base_h = float(self.ruler_height or 0.0) + float(self.scroll_bar_thickness or 0.0)
        track_h = max(0.0, float(self.track_height or 0.0))
        min_h = max(100.0, base_h + track_h)
        return QSize(int(round(max(min_w, 1.0))), int(round(min_h)))

    def _on_zoom_animation_value(self, value):
        """Apply an intermediate zoom value during animation (no emit)."""
        try:
            zoom_factor = float(value)
        except (TypeError, ValueError):
            return
        self.setZoomFactor(zoom_factor, emit=False)
        project_duration = self._current_project_duration()
        tick_pixels = 100.0
        self.scrollbar_position[2] = (
            project_duration * tick_pixels / zoom_factor if zoom_factor else 0.0
        )

    def _on_zoom_animation_finished(self):
        """Persist final zoom and sync slider after animation."""
        self._emit_zoom_signals(list(self.scrollbar_position))

    def _apply_external_zoom(self, zoom_factor):
        """Apply zoom requests from the ZoomSlider with smooth animation (~150ms)."""
        zoom_factor = self._clamp_zoom_factor(float(zoom_factor))
        if abs(zoom_factor - self.zoom_factor) <= 1e-6:
            return

        slider = getattr(self.win, "sliderZoomWidget", None)
        syncing_slider = bool(slider and getattr(slider, "_syncing_backend", False))
        if slider:
            span = tuple(slider.scrollbar_position[:2])
            if span[1] > span[0]:
                left = max(0.0, min(span[0], 1.0))
                right = max(left, min(span[1], 1.0))
                self._external_zoom_span = (left, right)
                if syncing_slider:
                    self.is_auto_center = False
            else:
                self._external_zoom_span = None
        else:
            self._external_zoom_span = None

        # Animate from current to target over 150ms (don't emit until finished)
        self._zoom_animation.stop()
        self._zoom_animation.setStartValue(self.zoom_factor)
        self._zoom_animation.setEndValue(zoom_factor)
        self._zoom_animation.start()

    def setSnappingMode(self, enable):
        """Enable or disable snapping mode."""
        self.enable_snapping = bool(enable)

    def setRazorMode(self, enable):
        """Enable or disable razor tool mode."""
        self.enable_razor = bool(enable)

    def setTimingMode(self, enable):
        """Enable or disable timing (retime) mode."""
        self.enable_timing = bool(enable)
        if self.enable_timing:
            self._snap_keyframe_seconds = []

    def _fix_cursor(self, cursor):
        self._fixed_cursor = cursor
        self.setCursor(cursor)

    def _release_cursor(self):
        self._fixed_cursor = None

    def _snap_time(self, seconds):
        """Snap a time in seconds to the nearest frame boundary."""
        return round(seconds * self.fps_float) / self.fps_float

    def _seconds_from_x(self, x_pos):
        """Convert an x position in widget coordinates to timeline seconds."""
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return 0.0
        offset_px = getattr(self, "h_scroll_offset", 0.0)
        seconds = (x_pos - self.track_name_width + offset_px) / pps
        return max(0.0, seconds)

    def run_js(self, code, callback=None, retries=0):
        """Placeholder due to webview compatibility"""

    def apply_theme(self, css=None):
        """Apply CSS theme to this widget."""
        if not isinstance(css, str):
            # Signal from ThemeChangedSignal passes the theme instance.
            # The theme has already been applied directly, so simply
            # refresh painters.
            self._theme_changed()
            return

        if parse_theme(self, css):
            self.changed(None)
        self._theme_changed()

    def _theme_changed(self):
        for p in (
            self.bg_painter,
            self.ruler_painter,
            self.track_painter,
            self.playback_cache_painter,
            self.clip_painter,
            self.transition_painter,
            self.marker_painter,
            self.playhead_painter,
            self.keyframe_painter,
            self.keyframe_panel_painter,
            self.selection_painter,
            self.scrollbar_painter,
        ):
            p.update_theme()
        self.geometry.mark_dirty()
        self._keyframes_dirty = True
        self.update()

    def setup_js_data(self):
        """Placeholder due to webview compatibility"""

    def get_html(self):
        """Placeholder due to webview compatibility"""

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        # Ignore changes that don't affect this
        if action and len(action.key) >= 1 and action.key[0].lower() in ["files", "history", "profile"]:
            return

        fps_info = get_app().project.get("fps")
        self.fps_float = float(fps_info.get("num", 24)) / float(fps_info.get("den", 1) or 1)

        # Invalidate caches and geometry
        self.clip_painter.clear_cache()
        self.transition_painter.clear_cache()
        self.geometry.mark_dirty()

        preserve_overrides = getattr(self, "_preserve_overrides_once", False)
        if preserve_overrides:
            self._preserve_overrides_once = False
        else:
            self._pending_clip_overrides.clear()
            self._pending_transition_overrides.clear()

        self._update_track_panel_properties()
        self.geometry.ensure()
        self._keyframes_dirty = True
        self._snap_keyframe_seconds = []

        # Mirror some attributes for compatibility
        self.track_list = self.geometry.track_list

        # Schedule repaint unless updates are currently suspended
        if self._suspend_changed_update <= 0:
            self.update()

    def paintEvent(self, event, *args):
        """Custom paint routine for the timeline widget."""
        if self._in_paint_event:
            log.warning("TimelineWidgetBase paintEvent skipped due to re-entrancy")
            event.accept()
            self.update()
            return

        self._in_paint_event = True
        painter = QPainter(self)
        try:
            event.accept()
            painter.setRenderHints(
                QPainter.Antialiasing |
                QPainter.SmoothPixmapTransform |
                QPainter.TextAntialiasing,
                True,
            )

            if not get_app().window.timeline:
                return

            signature = self._panel_current_signature()
            if signature != self._panel_refresh_signature:
                self._panel_refresh_signature = signature
                if self._update_track_panel_properties():
                    self.geometry.mark_dirty()

            self.geometry.ensure()
            self._ensure_keyframe_markers()

            self.bg_painter.paint(painter, event.rect())
            self.track_painter.paint_background(painter)
            self.keyframe_panel_painter.paint(painter, mode="underlay")
            self.clip_painter.paint(painter)
            self.transition_painter.paint(painter)
            self.playback_cache_painter.paint(painter)
            self.keyframe_painter.paint(painter)
            self.track_painter.paint_names(painter)
            self.keyframe_panel_painter.paint(painter, mode="overlay")
            self.selection_painter.paint(painter)
            self.ruler_painter.paint(painter)
            self.marker_painter.paint(painter)
            self.playhead_painter.paint(painter)
            self.ruler_painter.paint_overlay(painter)
            self.scrollbar_painter.paint(painter)
        finally:
            if painter.isActive():
                painter.end()
            self._in_paint_event = False

    def closeEvent(self, event):
        """Ensure background threads stop when the widget closes."""
        if self.thumbnail_manager:
            self.thumbnail_manager.shutdown()
        super().closeEvent(event)

    def update_playback_cache(self, cache_dict):
        """Update cached playback ranges used for rendering."""

        if not isinstance(cache_dict, dict):
            if self._playback_cache_ranges:
                self._playback_cache_ranges = []
                self.update()
            return

        ranges_data = cache_dict.get("ranges")
        if not isinstance(ranges_data, list):
            if self._playback_cache_ranges:
                self._playback_cache_ranges = []
                self.update()
            return

        def _to_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        fps_val = None
        fps_raw = cache_dict.get("fps")
        if isinstance(fps_raw, dict):
            num = _to_float(fps_raw.get("num"))
            den = _to_float(fps_raw.get("den"))
            if num and den:
                try:
                    fps_val = num / den
                except ZeroDivisionError:
                    fps_val = None
        else:
            fps_val = _to_float(fps_raw)
        if not fps_val or fps_val <= 0.0:
            local_fps = _to_float(getattr(self, "fps_float", None))
            fps_val = local_fps if local_fps and local_fps > 0.0 else None

        new_ranges = []
        for entry in ranges_data:
            start_sec = end_sec = None
            if isinstance(entry, dict):
                start_sec = _to_float(entry.get("start_seconds"))
                end_sec = _to_float(entry.get("end_seconds"))
                if start_sec is None or end_sec is None:
                    start_frames = _to_float(entry.get("start"))
                    end_frames = _to_float(entry.get("end"))
                    if (
                        fps_val
                        and start_frames is not None
                        and end_frames is not None
                    ):
                        start_sec = start_frames / fps_val
                        end_sec = end_frames / fps_val
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                start_sec = _to_float(entry[0])
                end_sec = _to_float(entry[1])

            if start_sec is None or end_sec is None:
                continue
            if end_sec <= start_sec:
                continue
            new_ranges.append((max(0.0, start_sec), max(0.0, end_sec)))

        if not new_ranges and not self._playback_cache_ranges:
            return

        new_ranges.sort(key=lambda item: item[0])
        old_ranges = self._playback_cache_ranges or []
        changed = len(new_ranges) != len(old_ranges)
        if not changed:
            for (new_start, new_end), (old_start, old_end) in zip(new_ranges, old_ranges):
                if (
                    abs(new_start - old_start) > 1e-3
                    or abs(new_end - old_end) > 1e-3
                ):
                    changed = True
                    break

        if changed:
            self._playback_cache_ranges = new_ranges
            self.update()

    def dragEnterEvent(self, event):
        self._drag_payload = None
        mime = event.mimeData()

        if mime.hasUrls():
            event.accept()
            self.new_item = True
            self.item_type = "os_drop"
            self._drag_payload = {"type": "os_drop", "urls": mime.urls()}
            return

        mime_html = mime.html()
        if mime_html:
            if mime_html in ("clip", "transition"):
                try:
                    ids = json.loads(mime.text())
                except Exception:
                    ids = []
                if not isinstance(ids, list):
                    ids = [ids]
                self._drag_payload = {"type": mime_html, "ids": ids}
                self.item_type = mime_html
                self.new_item = True
                event.accept()
            elif mime_html == "effect":
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.accept()
        payload = self._ensure_drag_payload_from_event(event)

        if payload and payload.get("type") in {"clip", "transition"}:
            coords = self._event_seconds_track(event)
            if coords is None:
                self._reset_drag_preview(delete_items=True)
                return
            pos_seconds, track_num, _ = coords
            if not self._ensure_drag_preview(pos_seconds, track_num):
                return
            self._update_drag_preview_position(pos_seconds, track_num)
        else:
            if payload and payload.get("type") == "effect":
                return
            if payload and payload.get("type") == "os_drop":
                return
            self._reset_drag_preview(delete_items=True)

    def dropEvent(self, event):
        event.accept()

        if self._drag_preview_items:
            self._finalize_drag_preview()
            return

        file_ids = []
        effect_names = []
        mime = event.mimeData()
        mime_html = mime.html()
        if mime.hasUrls():
            urls = mime.urls()
            self.win.files_model.process_urls(urls, import_quietly=True, prevent_image_seq=True)
            for uri in urls:
                for f in File.filter(path=uri.toLocalFile()):
                    file_ids.append(f.id)
        elif mime_html == "clip":
            try:
                ids = json.loads(mime.text())
            except Exception:
                ids = []
            if not isinstance(ids, list):
                ids = [ids]
            file_ids.extend(ids)
        elif mime_html == "transition":
            try:
                ids = json.loads(mime.text())
            except Exception:
                ids = []
            if not isinstance(ids, list):
                ids = [ids]
            file_ids.extend(ids)
        elif mime_html == "effect":
            try:
                names = json.loads(mime.text())
            except Exception:
                names = []
            if not isinstance(names, list):
                names = [names]
            effect_names.extend(names)

        if not file_ids and not effect_names:
            self._reset_drag_preview()
            return

        coords = self._event_seconds_track(event)
        if coords is None:
            coords = (0.0, self.track_list[0].data.get("number") if self.track_list else 0, 0)
        pos_seconds, track_num, _ = coords
        pos = QPointF(pos_seconds, 0)

        if effect_names:
            self._apply_effect_drop(effect_names, pos_seconds, track_num)
            self._reset_drag_preview()
            return

        for idx, fid in enumerate(file_ids):
            ignore_refresh = idx < len(file_ids) - 1
            if mime_html == "transition":
                item = self.addTransition(
                    fid,
                    pos,
                    track_num,
                    ignore_refresh=ignore_refresh,
                    call_manual_move=False,
                )
                if item:
                    pos.setX(pos.x() + (item.get("end", 0.0) - item.get("start", 0.0)))
            else:
                clip = self.addClip(
                    fid,
                    pos,
                    track_num,
                    ignore_refresh=ignore_refresh,
                    call_manual_move=False,
                )
                if clip:
                    pos.setX(pos.x() + (clip.get("end", 0.0) - clip.get("start", 0.0)))
        self._reset_drag_preview()

    def dragLeaveEvent(self, event):
        event.accept()
        self._reset_drag_preview(delete_items=True)

    def _ensure_drag_payload_from_event(self, event):
        if self._drag_payload:
            return self._drag_payload
        mime = event.mimeData()
        if mime.hasUrls():
            self._drag_payload = {"type": "os_drop", "urls": mime.urls()}
            return self._drag_payload
        mime_html = mime.html()
        if mime_html in {"clip", "transition"}:
            try:
                ids = json.loads(mime.text())
            except Exception:
                ids = []
            if not isinstance(ids, list):
                ids = [ids]
            self._drag_payload = {"type": mime_html, "ids": ids}
            self.item_type = mime_html
            self.new_item = True
        elif mime_html == "effect":
            self._drag_payload = {"type": "effect"}
        return self._drag_payload

    def _viewport_offsets(self):
        view_w = self.scrollbar_position[3] or 1.0
        timeline_w = self.scrollbar_position[2] or view_w
        left = self.scrollbar_position[0]
        h_offset = left * timeline_w
        max_scroll = max(0.0, timeline_w - view_w)
        if h_offset > max_scroll:
            h_offset = max_scroll

        view_h = self.v_scrollbar_position[3] or 1.0
        content_h = self.v_scrollbar_position[2] or view_h
        top = self.v_scrollbar_position[0]
        v_offset = top * content_h
        max_vscroll = max(0.0, content_h - view_h)
        if v_offset > max_vscroll:
            v_offset = max_vscroll
        return h_offset, v_offset

    def _event_seconds_track(self, event):
        pos = event.pos()
        if pos.x() < self.track_name_width or pos.y() < self.ruler_height:
            return None
        if not self.track_list:
            return None
        pixels_per_second = float(self.pixels_per_second or 0.0)
        if pixels_per_second <= 0.0:
            return None
        vertical_factor = float(self.vertical_factor or 0.0)
        if vertical_factor <= 0.0:
            return None
        h_offset, v_offset = self._viewport_offsets()
        pos_seconds = (pos.x() - self.track_name_width + h_offset) / pixels_per_second
        pos_seconds = max(0.0, pos_seconds)
        track_idx = int((pos.y() - self.ruler_height + v_offset) / vertical_factor)
        if track_idx < 0 or track_idx >= len(self.track_list):
            return None
        track_num = self.track_list[track_idx].data.get("number")
        return pos_seconds, track_num, track_idx

    def _snap_new_item_start(self, seconds, duration):
        seconds = max(0.0, seconds)
        if not self.enable_snapping:
            return seconds
        self.geometry.ensure()
        pixels_per_second = float(self.pixels_per_second or 0.0)
        if pixels_per_second <= 0.0:
            return seconds

        h_offset, _ = self._viewport_offsets()
        left_px = self.track_name_width + seconds * pixels_per_second - h_offset
        width_px = max(0.0, duration) * pixels_per_second

        ignore_ids = {
            getattr(entry.get("model"), "id", None)
            for entry in self._drag_preview_items
        }

        original_bbox = getattr(self, "drag_bbox", QRectF())
        original_ignore = getattr(self, "_snap_ignore_ids", set())
        preview_bbox = QRectF(left_px, original_bbox.y(), width_px, original_bbox.height())
        if preview_bbox.height() <= 0.0:
            preview_bbox.setHeight(self.vertical_factor or 1.0)
        try:
            self._snap_ignore_ids = {obj_id for obj_id in ignore_ids if obj_id is not None}
            self.drag_bbox = preview_bbox
            delta = self.snap.snap_dx(0.0)
        finally:
            self._snap_ignore_ids = original_ignore
            self.drag_bbox = original_bbox

        snapped = seconds + float(delta)
        snapped = max(0.0, snapped)
        return self._snap_time(snapped)

    def _ensure_drag_preview(self, pos_seconds, track_num):
        if self._drag_preview_items:
            return True
        payload = self._drag_payload or {}
        ids = payload.get("ids")
        if not ids:
            return False
        if not hasattr(self, "item_ids"):
            self.item_ids = []
        self.item_ids.clear()
        if track_num is None:
            return False
        preview_items = []
        current_start = pos_seconds
        for idx, source_id in enumerate(ids):
            ignore_refresh = idx < len(ids) - 1
            if payload.get("type") == "transition":
                item = self.addTransition(
                    source_id,
                    QPointF(current_start, 0),
                    track_num,
                    ignore_refresh=ignore_refresh,
                    call_manual_move=False,
                )
                if not item:
                    continue
                model = Transition.get(id=item.get("id"))
                duration = max(0.0, float(item.get("end", 0.0)) - float(item.get("start", 0.0)))
            else:
                item = self.addClip(
                    source_id,
                    QPointF(current_start, 0),
                    track_num,
                    ignore_refresh=ignore_refresh,
                    call_manual_move=False,
                )
                if not item:
                    continue
                model = Clip.get(id=item.get("id"))
                duration = max(0.0, float(item.get("end", 0.0)) - float(item.get("start", 0.0)))
            if not model:
                continue
            offset = current_start - pos_seconds
            preview_items.append({
                "model": model,
                "offset": offset,
                "duration": duration,
            })
            self.item_ids.append(model.id)
            current_start += duration

        if not preview_items:
            return False

        self._drag_preview_items = preview_items
        self._drag_preview_type = payload.get("type")
        self.geometry.mark_dirty()
        self.update()
        return True

    def _update_drag_preview_position(self, pos_seconds, track_num):
        if not self._drag_preview_items:
            return
        min_offset = min(entry.get("offset", 0.0) for entry in self._drag_preview_items)
        max_end = max(
            entry.get("offset", 0.0) + entry.get("duration", 0.0)
            for entry in self._drag_preview_items
        )
        group_duration = max(0.0, max_end - min_offset)
        snapped_start = self._snap_new_item_start(pos_seconds, group_duration)
        total = len(self._drag_preview_items)
        for idx, entry in enumerate(self._drag_preview_items):
            model = entry.get("model")
            if not model:
                continue
            new_pos = max(0.0, snapped_start + entry.get("offset", 0.0))
            model.data["position"] = new_pos
            model.data["layer"] = track_num
            rect = self.geometry.calc_item_rect(model)
            self.geometry.update_item_rect(model, rect)
        self.drag_bbox = self._compute_preview_bbox()
        self._keyframes_dirty = True
        self.update()

    def _compute_preview_bbox(self):
        if not self._drag_preview_items:
            return QRectF()
        rects = []
        for entry in self._drag_preview_items:
            model = entry.get("model")
            if not model:
                continue
            rect = self.geometry.calc_item_rect(model, viewport=True)
            if rect:
                rects.append(QRectF(rect))
        if not rects:
            return QRectF()
        bbox = QRectF(rects[0])
        for rect in rects[1:]:
            bbox = bbox.united(rect)
        return bbox

    def _reset_drag_preview(self, delete_items=False):
        deleted_any = False
        if delete_items and self._drag_preview_items:
            for entry in self._drag_preview_items:
                model = entry.get("model")
                if isinstance(model, Clip) or isinstance(model, Transition):
                    try:
                        model.delete()
                        deleted_any = True
                    except Exception:
                        pass
        self._drag_preview_items = []
        self._drag_preview_type = None
        self._drag_payload = None
        if hasattr(self, "item_ids"):
            self.item_ids = []
        self.new_item = False
        self.item_type = None
        self.drag_bbox = QRectF()
        if deleted_any:
            self._update_project_duration()
        self.geometry.mark_dirty()
        self.update()

    def _finalize_drag_preview(self):
        total = len(self._drag_preview_items)
        if not total:
            self._reset_drag_preview()
            return
        for idx, entry in enumerate(self._drag_preview_items):
            model = entry.get("model")
            if not model:
                continue
            ignore_refresh = idx < total - 1
            if isinstance(model, Transition):
                self.update_transition_data(
                    model.data,
                    only_basic_props=False,
                    ignore_refresh=ignore_refresh,
                )
            else:
                self.update_clip_data(
                    model.data,
                    only_basic_props=False,
                    ignore_reader=True,
                    ignore_refresh=ignore_refresh,
                )
        self._update_project_duration()
        self._drag_preview_items = []
        self._drag_preview_type = None
        self._drag_payload = None
        if hasattr(self, "item_ids"):
            self.item_ids = []
        self.new_item = False
        self.item_type = None
        self.changed(None)
        self.update()



    def resizeEvent(self, event):
        """Widget resize event"""
        event.accept()
        self.geometry.mark_dirty()
        self.delayed_size = self.size()
        view_w = max(
            0.0,
            self.width() - self.track_name_width - self.scroll_bar_thickness,
        )
        view_h = max(
            0.0,
            self.height() - self.ruler_height - self.scroll_bar_thickness,
        )
        self.geometry.ensure()
        timeline_w = self.scrollbar_position[2] or None
        self.geometry.refresh_viewport(
            view_w=view_w,
            view_h=view_h,
            timeline_w=timeline_w,
        )
        self.updateGeometry()
        self._schedule_viewport_thumbnail_reset()
        self.update()
        self.delayed_resize_timer.start()

    def delayed_resize_callback(self):
        """Callback for resize event timer (to delay the resize event, and prevent lots of similar resize events)"""
        project = get_app().project
        project_duration = self._current_project_duration()
        tick_pixels = float(project.get("tick_pixels") or 100.0)

        if self.delayed_size:
            view_w = max(
                0.0,
                self.delayed_size.width()
                - self.track_name_width
                - self.scroll_bar_thickness,
            )
            view_h = max(
                0.0,
                self.delayed_size.height()
                - self.ruler_height
                - self.scroll_bar_thickness,
            )
            self.scrollbar_position[3] = view_w
            self.v_scrollbar_position[3] = view_h
        else:
            view_w = float(self.scrollbar_position[3] or 0.0)
            view_h = float(self.v_scrollbar_position[3] or 0.0)

        # Preserve the existing zoom factor and update the visible range instead of
        # recomputing zoom from the viewport size. This keeps manual zoom choices
        # intact when the dock is resized.
        self.pixels_per_second = tick_pixels / float(self.zoom_factor or 1.0)
        timeline_w = project_duration * self.pixels_per_second
        self.scrollbar_position[2] = timeline_w

        if project_duration > 0.0 and view_w > 0.0:
            visible_secs = self.zoom_factor * (view_w / tick_pixels)
            width_norm = max(0.0, min(visible_secs / project_duration, 1.0))
        else:
            width_norm = 1.0 if timeline_w > 0.0 else 0.0

        left_norm = self.scrollbar_position[0]
        right_norm = left_norm + width_norm
        if right_norm > 1.0:
            right_norm = 1.0
            left_norm = max(0.0, right_norm - width_norm)

        self.scrollbar_position[0] = left_norm
        self.scrollbar_position[1] = right_norm
        self.h_scroll_offset = left_norm * (timeline_w or 0.0)

        self.geometry.refresh_viewport(
            view_w=view_w,
            view_h=view_h,
            timeline_w=timeline_w,
        )
        self.geometry.mark_dirty()
        self.geometry.ensure()
        self.updateGeometry()
        self._schedule_viewport_thumbnail_reset()
        self.update()
        get_app().window.TimelineScrolled.emit(list(self.scrollbar_position))

    # Capture wheel event to alter zoom/scale of widget
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.pixelDelta().y() if not event.pixelDelta().isNull() else event.angleDelta().y()
            if delta:
                steps = delta / 120.0
                self.is_auto_center = True
                if self._apply_zoom_steps(steps, emit=False):
                    self._pending_zoom_emit = self.zoom_factor
                    self._zoom_emit_timer.start()
            event.accept()
            return

        # Vertical scrolling
        if self.v_scrollbar_position[3] > 0 and self.v_scrollbar_position[2] > self.v_scrollbar_position[3]:
            delta = -event.angleDelta().y() / 120.0
            if delta:
                self._pending_vscroll_delta += delta
                if not self._vscroll_timer.isActive():
                    # Process accumulated wheel events once the event queue is flushed
                    self._vscroll_timer.start(0)
            event.accept()
        else:
            event.ignore()

    def _flush_pending_vertical_scroll(self):
        """Apply any pending vertical scroll updates triggered by the wheel."""
        delta = self._pending_vscroll_delta
        self._pending_vscroll_delta = 0.0

        if not delta:
            return

        if not (
            self.v_scrollbar_position[3] > 0
            and self.v_scrollbar_position[2] > self.v_scrollbar_position[3]
        ):
            return

        view_ratio = self.v_scrollbar_position[1] - self.v_scrollbar_position[0]
        if not view_ratio:
            return

        new_top = self.v_scrollbar_position[0] + delta * view_ratio * 0.1
        new_top = max(0.0, min(new_top, 1.0 - view_ratio))
        self.v_scrollbar_position[0] = new_top
        self.v_scrollbar_position[1] = new_top + view_ratio
        self.geometry.mark_dirty()
        self._update_scrollbar_handles()
        self.update()

    def _update_scrollbar_handles(self):
        """Recompute scrollbar handle rectangles from the current positions."""

        # Horizontal scrollbar handle
        view_w = float(self.scrollbar_position[3] or 0.0)
        if view_w <= 0.0:
            view_w = max(0.0, self.width() - self.track_name_width - self.scroll_bar_thickness)
        timeline_w = float(self.scrollbar_position[2] or 0.0)
        if timeline_w <= 0.0:
            timeline_w = max(view_w, 0.0)
        width_norm = max(0.0, min(self.scrollbar_position[1] - self.scrollbar_position[0], 1.0))
        if (
            view_w > 0.0
            and timeline_w > view_w
            and width_norm > 0.0
            and width_norm < 1.0
        ):
            handle_w = max(20.0, width_norm * view_w)
            avail = max(0.0, view_w - handle_w)
            handle_x = float(self.track_name_width)
            max_scroll = max(0.0, timeline_w - view_w)
            scroll_px = max(0.0, min(self.scrollbar_position[0] * timeline_w, max_scroll))
            if max_scroll > 0.0 and avail > 0.0:
                handle_x += (scroll_px / max_scroll) * avail
            self.scroll_bar_rect = QRectF(
                handle_x,
                self.height() - self.scroll_bar_thickness,
                handle_w,
                self.scroll_bar_thickness,
            )
        else:
            self.scroll_bar_rect = QRectF()

        # Vertical scrollbar handle
        view_h = float(self.v_scrollbar_position[3] or 0.0)
        if view_h <= 0.0:
            view_h = max(0.0, self.height() - self.ruler_height - self.scroll_bar_thickness)
        content_h = float(self.v_scrollbar_position[2] or 0.0)
        if content_h <= 0.0:
            content_h = max(view_h, 0.0)
        height_norm = max(0.0, min(self.v_scrollbar_position[1] - self.v_scrollbar_position[0], 1.0))
        if (
            view_h > 0.0
            and content_h > view_h
            and height_norm > 0.0
            and height_norm < 1.0
        ):
            handle_h = max(20.0, height_norm * view_h)
            avail = max(0.0, view_h - handle_h)
            handle_y = float(self.ruler_height)
            max_scroll = max(0.0, content_h - view_h)
            scroll_py = max(0.0, min(self.v_scrollbar_position[0] * content_h, max_scroll))
            if max_scroll > 0.0 and avail > 0.0:
                handle_y += (scroll_py / max_scroll) * avail
            self.v_scroll_bar_rect = QRectF(
                self.width() - self.scroll_bar_thickness,
                handle_y,
                self.scroll_bar_thickness,
                handle_h,
            )
        else:
            self.v_scroll_bar_rect = QRectF()

    def _emit_pending_zoom(self):
        """Emit a pending zoom factor change after gesture bursts settle."""
        if self._pending_zoom_emit is None:
            return

        self._pending_zoom_emit = None
        self._emit_zoom_signals(list(self.scrollbar_position))

    def _emit_zoom_signals(self, slider_positions):
        """Persist the current zoom factor and broadcast timeline signals."""
        current_scale = float(get_app().project.get("scale") or 15.0)
        if abs(self.zoom_factor - current_scale) > 1e-6:
            get_app().updates.ignore_history = True
            get_app().updates.update(["scale"], self.zoom_factor)
            get_app().updates.ignore_history = False

        get_app().window.TimelineZoom.emit(self.zoom_factor)
        get_app().window.TimelineScrolled.emit(slider_positions)

    def _clamp_zoom_factor(self, zoom_factor):
        return max(0.05, min(zoom_factor, 200.0))

    def _apply_zoom_steps(self, steps, emit):
        """Apply a relative zoom change expressed as wheel steps."""
        if not steps:
            return False

        base = 0.9
        scale = pow(base, steps)
        new_factor = self._clamp_zoom_factor(self.zoom_factor * scale)
        if abs(new_factor - self.zoom_factor) <= 1e-6:
            return False

        self.setZoomFactor(new_factor, emit=emit)
        return True

    def setZoomFactor(self, zoom_factor, emit=True):
        """Set the current zoom factor"""
        # Force recalculation of clips
        zoom_factor = self._clamp_zoom_factor(zoom_factor)
        self.zoom_factor = zoom_factor
        self._suspend_changed_update += 1
        try:
            self.changed(None)
        finally:
            self._suspend_changed_update = max(0, self._suspend_changed_update - 1)

        # Update normalized scroll width to match new zoom
        project_duration = self._current_project_duration()
        view_w = self.scrollbar_position[3]
        tick_pixels = float(get_app().project.get("tick_pixels") or 100.0)
        self.pixels_per_second = tick_pixels / float(self.zoom_factor or 1.0)
        timeline_w = project_duration * self.pixels_per_second
        self.scrollbar_position[2] = timeline_w
        if project_duration > 0.0 and view_w > 0.0 and timeline_w > 0.0:
            visible_secs = zoom_factor * (view_w / tick_pixels)
            width_norm = max(0.0, min(visible_secs / project_duration, 1.0))
        else:
            width_norm = 1.0 if timeline_w > 0.0 else 0.0

        span = self._external_zoom_span
        self._external_zoom_span = None

        if span and project_duration > 0.0:
            width_norm = max(0.0, min(span[1] - span[0], 1.0))
            center_norm = span[0] + (width_norm / 2.0)
            center_norm = max(0.0, min(center_norm, 1.0))
            center_seconds = center_norm * project_duration
            self._center_on_seconds(
                center_seconds,
                width_norm=width_norm,
                timeline_w=timeline_w,
                view_w=view_w,
            )
        else:
            if self.is_auto_center:
                anchor_seconds = 0.0
                if self.fps_float:
                    anchor_seconds = max(0.0, (self.current_frame - 1) / self.fps_float)
                self._center_on_seconds(
                    anchor_seconds,
                    width_norm=width_norm,
                    timeline_w=timeline_w,
                    view_w=view_w,
                )
            else:
                left_norm = max(0.0, min(self.scrollbar_position[0], 1.0 - width_norm))
                right_norm = left_norm + width_norm
                self.scrollbar_position[0] = left_norm
                self.scrollbar_position[1] = right_norm
                self.h_scroll_offset = left_norm * timeline_w

        self.update()

        slider_positions = list(self.scrollbar_position)
        slider = getattr(self.win, "sliderZoomWidget", None)
        if slider:
            if abs(slider.zoom_factor - zoom_factor) > 1e-6:
                slider.setZoomFactor(zoom_factor, emit=False)
            slider.update_scrollbars(slider_positions)

        if emit:
            self._emit_zoom_signals(slider_positions)

        self._schedule_viewport_thumbnail_reset()
        self.update()

    def _schedule_viewport_thumbnail_reset(self):
        timer = getattr(self, "_viewport_thumbnail_reset_timer", None)
        if timer:
            timer.stop()
            timer.start()

    def _apply_viewport_thumbnail_reset(self):
        timer = getattr(self, "_viewport_thumbnail_reset_timer", None)
        if timer:
            timer.stop()
        self._reset_thumbnail_requests()
        self.update()

    def zoomIn(self):
        """Zoom into timeline"""
        self._apply_zoom_steps(1.0, emit=True)

    def zoomOut(self):
        """Zoom out of timeline"""
        self._apply_zoom_steps(-1.0, emit=True)

    def update_scrollbars(self, new_positions):
        """Consume the current scroll bar positions from the webview timeline"""
        if self.mouse_dragging:
            return

        if list(new_positions) == self.scrollbar_position:
            return

        self.scrollbar_position = list(new_positions)
        timeline_w = self.scrollbar_position[2] or self.scrollbar_position[3] or 0.0
        self.h_scroll_offset = self.scrollbar_position[0] * timeline_w
        self.geometry.refresh_viewport(timeline_w=timeline_w)

        # Check for empty clip rectangles
        if not self.geometry.clip_entries:
            self.changed(None)

        # Disable auto center
        self.is_auto_center = False

        # Schedule repaint
        self._schedule_viewport_thumbnail_reset()
        self.update()

    def set_scroll_left(self, new_left):
        width_norm = self.scrollbar_position[1] - self.scrollbar_position[0]
        left = max(0.0, min(new_left, 1.0 - width_norm))
        if abs(left - self.scrollbar_position[0]) < 1e-9:
            return
        self.scrollbar_position[0] = left
        self.scrollbar_position[1] = left + width_norm
        timeline_w = self.scrollbar_position[2] or self.scrollbar_position[3] or 0.0
        self.h_scroll_offset = left * timeline_w
        self.is_auto_center = False
        self.geometry.refresh_viewport(timeline_w=timeline_w)
        self._schedule_viewport_thumbnail_reset()
        self.update()

    def _center_on_seconds(self, seconds, width_norm=None, timeline_w=None, view_w=None):
        timeline_w = float(timeline_w or 0.0)
        view_w = float(view_w or 0.0)
        if timeline_w <= 0.0 or view_w <= 0.0:
            self.scrollbar_position[0] = 0.0
            self.scrollbar_position[1] = 1.0 if timeline_w > 0.0 else 0.0
            self.h_scroll_offset = 0.0
            return False

        if width_norm is None:
            width_norm = self.scrollbar_position[1] - self.scrollbar_position[0]
        width_norm = max(0.0, min(width_norm, 1.0))

        view_px = width_norm * timeline_w
        if view_px <= 0.0:
            view_px = min(view_w, timeline_w)
            width_norm = view_px / timeline_w if timeline_w else 0.0

        if timeline_w <= view_px + 1e-9:
            left_px = 0.0
            width_norm = 1.0
        else:
            anchor_px = max(0.0, min(seconds * self.pixels_per_second, timeline_w))
            half = view_px / 2.0
            left_px = anchor_px - half
            max_left = max(0.0, timeline_w - view_px)
            if left_px < 0.0:
                left_px = 0.0
            elif left_px > max_left:
                left_px = max_left

        left_norm = left_px / timeline_w if timeline_w else 0.0
        right_norm = left_norm + width_norm
        if right_norm > 1.0:
            right_norm = 1.0
            left_norm = max(0.0, right_norm - width_norm)

        changed = (
            abs(left_norm - self.scrollbar_position[0]) > 1e-6
            or abs(right_norm - self.scrollbar_position[1]) > 1e-6
        )

        self.scrollbar_position[0] = left_norm
        self.scrollbar_position[1] = right_norm
        self.h_scroll_offset = left_norm * timeline_w
        return changed


    def handle_selection(self):
        # Force recalculation of clips and repaint
        self.changed(None)
        self._keyframes_dirty = True
        self.update()







    # ----- State machine helper methods -----

    def _hitTest(self, pos):
        return self.geometry.hit(pos)




    def _select_timeline_item(self, item_id, item_type, clear_existing):
        if item_id is None or not item_type:
            return
        item_id_str = str(item_id)
        if not item_id_str:
            return
        timeline = getattr(self.win, "timeline", None)
        if timeline:
            timeline.addSelection(item_id_str, item_type, clear_existing)
        self.win.addSelection(item_id_str, item_type, clear_existing)
        # Selection changes affect cached clip renders and keyframe visibility.
        self.clip_painter.clear_cache()
        self.geometry.mark_dirty()
        self._keyframes_dirty = True
        self.update()

    def select_all_items(self):
        """Select all clips and transitions currently laid out on the timeline."""
        self.geometry.ensure()
        self.win.clearSelections()
        for _rect, item, _selected, item_type in self.geometry.iter_items(viewport=False):
            item_id = getattr(item, "id", None)
            if item_id is None:
                continue
            self._select_timeline_item(item_id, item_type, False)

    def selectRipple(self, item_id, item_type):
        """Select the item and everything to its right on the same layer."""
        if not item_id or not item_type:
            return
        self.geometry.ensure()
        target = None
        target_layer = None
        target_pos = None
        for _rect, obj, _sel, typ in self.geometry.iter_items(viewport=False):
            if typ == item_type and str(getattr(obj, "id", "")) == str(item_id):
                data = getattr(obj, "data", {}) or {}
                target = obj
                target_layer = data.get("layer")
                try:
                    target_pos = float(data.get("position"))
                except (TypeError, ValueError):
                    target_pos = None
                break
        if target is None or target_layer is None or target_pos is None:
            return
        for _rect, obj, _sel, typ in self.geometry.iter_items(viewport=False):
            if typ not in ("clip", "transition"):
                continue
            data = getattr(obj, "data", {}) or {}
            if data.get("layer") != target_layer:
                continue
            try:
                obj_pos = float(data.get("position"))
            except (TypeError, ValueError):
                continue
            if obj_pos >= target_pos:
                self._select_timeline_item(getattr(obj, "id", None), typ, False)

    def clear_all_selections(self):
        """Clear all timeline selections and keyframe highlights."""
        self.win.clearSelections()
        if hasattr(self, "_clear_panel_selection"):
            self._clear_panel_selection(None)
        self.clip_painter.clear_cache()
        self.geometry.mark_dirty()
        self._keyframes_dirty = True
        self.update()

    def _update_project_duration(self):
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return

        furthest = self._furthest_timeline_edge()
        min_length = 300.0
        padding = 10.0
        desired = max(min_length, furthest + padding)
        current = float(get_app().project.get("duration") or 0.0)
        if desired > current + 1e-3:
            timeline.resizeTimeline(desired)

    def _clip_menu_rect(self, rect):
        if not self.clip_painter.menu_pix:
            return QRectF()
        bw = self.clip_painter.clip_pen.widthF()
        width, height = self.clip_painter.logical_size(self.clip_painter.menu_pix)
        return QRectF(
            rect.x() + bw + self.clip_painter.menu_margin,
            rect.y() + bw + self.clip_painter.menu_margin,
            width,
            height,
        )

    def _marker_identifier(self, entry):
        if not isinstance(entry, dict):
            return None
        marker_id = entry.get("id")
        if marker_id:
            return str(marker_id)
        marker_obj = entry.get("marker")
        if marker_obj is not None:
            return str(getattr(marker_obj, "id", "")) or None
        return None

    def _marker_at(self, pos):
        self.geometry.ensure()
        if self._playhead_hit(pos):
            return None
        for entry in self.geometry.iter_markers():
            if isinstance(entry, dict):
                hit_rect = entry.get("hit_rect") or entry.get("icon_rect") or entry.get("line_rect")
                if hit_rect and hit_rect.contains(pos):
                    return entry
            elif isinstance(entry, QRectF) and entry.contains(pos):
                return {"line_rect": entry}
        return None

    def _marker_same(self, entry_a, entry_b):
        if not entry_a or not entry_b:
            return False
        return self._marker_identifier(entry_a) == self._marker_identifier(entry_b)

    def _select_marker(self, entry):
        marker_id = self._marker_identifier(entry)
        if not marker_id:
            return
        if hasattr(self.win, "selected_markers"):
            self.win.selected_markers = [marker_id]

    def _handle_marker_click(self, entry):
        if not isinstance(entry, dict):
            return
        self._select_marker(entry)
        seconds = entry.get("seconds")
        marker_obj = entry.get("marker")
        if seconds is None and marker_obj is not None:
            seconds = marker_obj.data.get("position", 0.0)
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            seconds = 0.0
        timeline = getattr(self.win, "timeline", None)
        if not timeline or not hasattr(timeline, "SeekToKeyframe"):
            return
        frame = 1
        if self.fps_float:
            frame = max(1, int(round(seconds * self.fps_float)) + 1)
        timeline.SeekToKeyframe(frame)


























































































    def _updateCursor(self, pos):
        if self._fixed_cursor is not None:
            self.setCursor(self._fixed_cursor)
            return

        self.geometry.ensure()

        # Playhead icon
        handle_rect = self._playhead_handle_rect()
        if (self.playhead_painter.icon_pix and not handle_rect.isNull() and handle_rect.contains(pos)):
            self.setCursor(self.cursors["hand"])
            return

        icon_entry = self._effect_icon_at(pos)
        if icon_entry:
            self.setCursor(Qt.PointingHandCursor)
            return

        toolbar_button = self._track_toolbar_button_at(pos)
        if toolbar_button:
            self.setCursor(Qt.PointingHandCursor)
            return

        # Transition menu icons
        for rect, _tran, _selected in self.geometry.iter_transitions(reverse=True):
            if self._transition_menu_rect(rect).contains(pos):
                self.setCursor(Qt.PointingHandCursor)
                return

        marker_entry = self._marker_at(pos)
        if marker_entry and isinstance(marker_entry, dict):
            self.setCursor(Qt.PointingHandCursor)
            return

        marker = self._get_keyframe_at(pos)
        if marker:
            self.setCursor(self.cursors.get("resize_x", Qt.SizeHorCursor))
            return

        # Clip menu icons
        for rect, _clip, _selected in self.geometry.iter_clips(reverse=True):
            if self._clip_menu_rect(rect).contains(pos):
                self.setCursor(Qt.PointingHandCursor)
                return

        # Clip/transition edges and drags (transitions prioritized)
        edge = 5
        for rect, _item, _selected, _type in self.geometry.iter_items(reverse=True):
            if rect.contains(pos):
                if abs(pos.x() - rect.left()) <= edge or abs(pos.x() - rect.right()) <= edge:
                    self.setCursor(self.cursors["resize_x"])
                else:
                    self.setCursor(self.cursors["hand"])
                return

        # Track menu icons
        for _track_rect, _track, name_rect in self.geometry.iter_tracks():
            mrect = self._track_menu_rect(name_rect)
            if mrect.contains(pos):
                self.setCursor(Qt.PointingHandCursor)
                return

        timeline_handle = self.geometry.timeline_handle_rect()
        if timeline_handle.contains(pos):
            self.setCursor(self.cursors.get("resize_x", Qt.SizeHorCursor))
            return

        self.unsetCursor()

    def mousePressEvent(self, event):
        self._press_marker = None
        if event.button() == Qt.RightButton:
            self._last_event = event
            if self._panel_show_property_menu_at(event.pos()):
                event.accept()
                return
            icon_entry = self._effect_icon_at(event.pos())
            if icon_entry and self._trigger_effect_context_menu(
                icon_entry, event.modifiers() if hasattr(event, "modifiers") else None
            ):
                event.accept()
                return
            if self._showContextMenu(event.pos()):
                event.accept()
            else:
                event.ignore()
            return

        if event.button() == Qt.MiddleButton:
            if self._startMiddlePan(event.pos()):
                event.accept()
                return

        self.geometry.ensure()
        pos = event.pos()

        if event.button() == Qt.LeftButton:
            toolbar_button = self._track_toolbar_button_at(pos)
            if toolbar_button:
                self._last_event = event
                self._toolbar_pressed_key = (toolbar_button.get("track_id"), toolbar_button.get("key"))
                self._toolbar_pressed_inside = True
                self._toolbar_hover_key = self._toolbar_pressed_key
                self.update()
                event.accept()
                return

        if self._handle_menu_icon_clicks(pos):
            return

        if self.enable_razor and event.button() == Qt.LeftButton:
            if self._handle_razor_press(pos):
                event.accept()
                return

        self._assign_press_target(event)

        if self._start_scroll_drag_if_needed(pos):
            return

        if self._press_hit == "panel-add":
            event.accept()
            return

        if self._press_hit == "effect-icon":
            event.accept()
            return

        self._last_event = event
        self.events.pressed.emit(event)

    def leaveEvent(self, event):
        if self._toolbar_hover_key is not None or self._toolbar_pressed_inside:
            self._toolbar_hover_key = None
            if self._toolbar_pressed_key:
                self._toolbar_pressed_inside = False
            self.update()
        super().leaveEvent(event)

    def _handle_menu_icon_clicks(self, pos):
        return (
            self._trigger_track_menu_icon(pos)
            or self._trigger_transition_menu_icon(pos)
            or self._trigger_clip_menu_icon(pos)
        )

    def _trigger_track_menu_icon(self, pos):
        for _track_rect, track, name_rect in self.geometry.iter_tracks():
            if self._track_menu_rect(name_rect).contains(pos) and hasattr(self.win, "timeline"):
                self.win.timeline.ShowTrackMenu(track.id)
                return True
        return False


    def _trigger_clip_menu_icon(self, pos):
        for rect, clip, _selected in self.geometry.iter_clips(reverse=True):
            if self._clip_menu_rect(rect).contains(pos) and hasattr(self.win, "timeline"):
                self.win.timeline.ShowClipMenu(clip.id)
                return True
        return False

    def _handle_razor_press(self, pos):
        """Invoke razor slicing when the razor tool is enabled and an item is clicked."""
        for rect, obj, _sel, typ in self.geometry.iter_items(reverse=True):
            if not rect.contains(pos):
                continue
            seconds = self._seconds_from_x(pos.x())
            clip_id = str(getattr(obj, "id", "")) if typ == "clip" else ""
            tran_id = str(getattr(obj, "id", "")) if typ == "transition" else ""
            razor_cb = getattr(self, "RazorSliceAtCursor", None)
            if callable(razor_cb):
                razor_cb(clip_id, tran_id, seconds)
            return True
        return False

    def _assign_press_target(self, event):
        pos = event.pos()
        modifiers = event.modifiers() if hasattr(event, "modifiers") else Qt.NoModifier
        ctrl = bool(modifiers & Qt.ControlModifier)
        marker_entry = self._marker_at(pos)
        if marker_entry and isinstance(marker_entry, dict):
            self._press_hit = "marker"
            self._press_marker = marker_entry
            self._select_marker(marker_entry)
            return
        self._press_marker = None
        marker = self._get_keyframe_at(pos)
        if marker:
            self._press_hit = "keyframe"
            self._press_keyframe = marker
            self._press_keyframe_clear = not ctrl
            self._select_marker_owner(marker, clear_existing=self._press_keyframe_clear)
            return
        self._press_keyframe = None
        self._press_keyframe_clear = True
        add_button = self._panel_add_button_at(pos)
        if add_button:
            self._press_hit = "panel-add"
            self._panel_press_info = add_button
            return
        panel_marker = self._panel_marker_at(pos)
        if panel_marker and panel_marker.get("point"):
            self._press_hit = "panel-keyframe"
            panel_marker = dict(panel_marker)
            panel_marker["modifiers"] = modifiers
            self._panel_press_info = panel_marker
            return
        self._panel_press_info = None
        panel_lane = self._panel_lane_at(pos)
        if panel_lane:
            self._press_hit = "panel"
            self._panel_press_info = {"lane": panel_lane}
            return
        icon_entry = self._effect_icon_at(pos)
        if icon_entry:
            self._press_hit = "effect-icon"
            self._press_effect_icon = icon_entry
            return
        self._press_effect_icon = None
        edge = 5
        for rect, item, _selected, _type in self.geometry.iter_items(reverse=True):
            if not rect.contains(pos):
                continue
            if abs(pos.x() - rect.left()) <= edge:
                self._press_hit = "clip-edge"
                self._resizing_item = item
                self._resize_edge = "left"
                return
            if abs(pos.x() - rect.right()) <= edge:
                self._press_hit = "clip-edge"
                self._resizing_item = item
                self._resize_edge = "right"
                return
        self._resizing_item = None
        self._resize_edge = None
        self._press_hit = self._hitTest(pos)

    def _start_scroll_drag_if_needed(self, pos):
        if self._press_hit == "h-scroll":
            self.scroll_bar_dragging = True
            self.mouse_dragging = True
            self.mouse_position = pos.x()
            self.scrollbar_position_previous = list(self.scrollbar_position)
            return True
        if self._press_hit == "v-scroll":
            self.v_scroll_bar_dragging = True
            self.mouse_dragging = True
            self.mouse_position = pos.y()
            self.v_scrollbar_position_previous = list(self.v_scrollbar_position)
            return True
        return False

    def mouseMoveEvent(self, event):
        self._last_event = event

        if self.scroll_bar_dragging:
            view_w = self.scrollbar_position[3] or 1.0
            width_norm = self.scrollbar_position_previous[1] - self.scrollbar_position_previous[0]
            handle_w = width_norm * view_w
            avail = view_w - handle_w
            delta_px = self.mouse_position - event.pos().x()
            delta = 0.0
            if avail > 0:
                delta = (delta_px / avail) * (1.0 - width_norm)
            new_left = self.scrollbar_position_previous[0] - delta
            new_left = max(0.0, min(new_left, 1.0 - width_norm))
            self.scrollbar_position = [new_left, new_left + width_norm,
                                       self.scrollbar_position[2], self.scrollbar_position[3]]
            timeline_w = self.scrollbar_position[2] or self.scrollbar_position[3] or 0.0
            self.h_scroll_offset = new_left * timeline_w
            self._update_scrollbar_handles()
            get_app().window.TimelineScrolled.emit(list(self.scrollbar_position))
            self.update()
            return

        if self.v_scroll_bar_dragging:
            view_h = self.v_scrollbar_position[3] or 1.0
            height_norm = self.v_scrollbar_position_previous[1] - self.v_scrollbar_position_previous[0]
            handle_h = height_norm * view_h
            avail = view_h - handle_h
            delta_py = self.mouse_position - event.pos().y()
            delta = 0.0
            if avail > 0:
                delta = (delta_py / avail) * (1.0 - height_norm)
            new_top = self.v_scrollbar_position_previous[0] - delta
            new_top = max(0.0, min(new_top, 1.0 - height_norm))
            self.v_scrollbar_position[0] = new_top
            self.v_scrollbar_position[1] = new_top + height_norm
            self._update_scrollbar_handles()
            self.update()
            return

        if self._middle_panning:
            self._updateMiddlePan(event.pos())
            return

        pos = event.pos()
        if self._toolbar_pressed_key:
            self._update_toolbar_pressed_state(pos)
        self._update_toolbar_hover(pos)

        self._updateCursor(pos)
        self.events.moved.emit(event)

    def mouseReleaseEvent(self, event):
        self._last_event = event

        if event.button() == Qt.LeftButton and self._toolbar_pressed_key:
            button = self._get_toolbar_button(*self._toolbar_pressed_key)
            inside = bool(
                button
                and button.get("rect")
                and button["rect"].contains(event.pos())
                and self._toolbar_pressed_inside
            )
            self._toolbar_pressed_key = None
            self._toolbar_pressed_inside = False
            if inside and button:
                self._activate_track_toolbar_button(button)
            self._update_toolbar_hover(event.pos())
            self.update()
            event.accept()
            return

        if event.button() == Qt.MiddleButton and self._middle_panning:
            self._finishMiddlePan()
            return
        if self.scroll_bar_dragging or self.v_scroll_bar_dragging:
            self.scroll_bar_dragging = False
            self.v_scroll_bar_dragging = False
            self.mouse_dragging = False
            return
        press_hit = self._press_hit
        add_info_initial = self._panel_press_info if press_hit == "panel-add" else None
        effect_info = self._press_effect_icon if press_hit == "effect-icon" else None

        self.events.released.emit(event)

        if press_hit == "panel-add":
            info = self._panel_press_info or add_info_initial or {}
            self._panel_press_info = None
            self._press_hit = None
            self._handle_panel_add_click(info)
            event.accept()
            return

        if press_hit == "panel-keyframe":
            info = self._panel_press_info or {}
            self._panel_press_info = None
            if info.get("dragged"):
                self._press_hit = None
                event.accept()
                return
            point = info.get("point") if isinstance(info, dict) else None
            prop = info.get("property") if isinstance(info, dict) else None
            track_num = info.get("track") if isinstance(info, dict) else None
            frame_val = point.get("frame") if isinstance(point, dict) else None
            prop_key = prop.get("key") if isinstance(prop, dict) else None
            modifiers = event.modifiers() if hasattr(event, "modifiers") else Qt.NoModifier
            additive = bool(modifiers & Qt.ControlModifier)
            if frame_val is not None and prop_key and track_num is not None:
                try:
                    frame_int = int(frame_val)
                except (TypeError, ValueError):
                    frame_int = None
                if frame_int is not None:
                    if additive:
                        self._panel_toggle_frames(track_num, prop_key, {frame_int})
                    else:
                        self._panel_set_selection_map(track_num, {prop_key: {frame_int}})
            if point:
                self._panel_seek_to_point(info, point)
            self._press_hit = None
            event.accept()
            return

        if press_hit == "effect-icon":
            self._press_hit = None
            self._press_effect_icon = None
            event.accept()
            self._handle_effect_icon_click(effect_info)
            return

        if press_hit == "marker":
            marker_entry = self._press_marker
            self._press_marker = None
            if event.button() == Qt.LeftButton and isinstance(marker_entry, dict):
                current = self._marker_at(event.pos())
                if self._marker_same(marker_entry, current):
                    self._handle_marker_click(marker_entry)
                    self._press_hit = None
                    event.accept()
                    return
            self._press_hit = None
            return

        self._press_hit = None

    def contextMenuEvent(self, event):
        if self._panel_show_property_menu_at(event.pos()):
            event.accept()
            return
        icon_entry = self._effect_icon_at(event.pos())
        if icon_entry:
            if self._trigger_effect_context_menu(
                icon_entry, event.modifiers() if hasattr(event, "modifiers") else None
            ):
                event.accept()
                return
        if not self._showContextMenu(event.pos()):
            event.ignore()

    def _panel_show_property_menu_at(self, pos):
        lane = self._panel_lane_at(pos)
        if not lane:
            return False
        label_rect = lane.get("label_rect")
        if not isinstance(label_rect, QRectF) or not label_rect.contains(pos):
            return False
        track_num = lane.get("track")
        key = self.normalize_track_number(track_num) if track_num is not None else None
        if key is None:
            return False
        info = self._panel_properties.get(key)
        if not isinstance(info, dict):
            return False
        available = info.get("available_properties") or []
        if not available:
            return False

        item_id = info.get("item_id", "")
        item_type = info.get("item_type")
        manual_entry = self._panel_manual_properties.get(key)
        if (
            not manual_entry
            or manual_entry.get("item_id") != item_id
            or manual_entry.get("item_type") != item_type
        ):
            manual_entry = {"item_id": item_id, "item_type": item_type, "properties": set()}
        else:
            manual_entry = {
                "item_id": manual_entry.get("item_id", ""),
                "item_type": manual_entry.get("item_type"),
                "properties": set(manual_entry.get("properties") or []),
            }
        self._panel_manual_properties[key] = manual_entry

        available_sorted = sorted(
            (entry for entry in available if isinstance(entry, dict)),
            key=lambda entry: str(entry.get("display_name", "")).lower(),
        )
        visible_keys = {
            str(prop.get("key"))
            for prop in info.get("properties", [])
            if isinstance(prop, dict) and prop.get("key") is not None
        }
        title = get_app()._tr("Keyframe Properties")
        menu = StyledContextMenu(title=title, parent=self)
        handled = False
        for entry in available_sorted:
            key_name = entry.get("key")
            if key_name is None:
                continue
            key_str = str(key_name)
            label = entry.get("display_name") or key_str
            action = menu.addAction(label)
            if key_str in visible_keys:
                action.setEnabled(False)
                action.setCheckable(True)
                action.setChecked(True)
                continue
            action.triggered.connect(partial(self._panel_add_visible_property, key, key_str))
            handled = True

        if not menu.actions():
            placeholder = menu.addAction(get_app()._tr("No keyframe properties available"))
            placeholder.setEnabled(False)

        global_pos = self.mapToGlobal(pos)
        menu.exec_(global_pos)
        return handled or bool(menu.actions())

    def _panel_add_visible_property(self, track_num, prop_key):
        key = self.normalize_track_number(track_num) if track_num is not None else None
        if key is None:
            return False
        info = self._panel_properties.get(key)
        if not isinstance(info, dict):
            return False
        available = info.get("available_properties") or []
        available_map = {
            str(entry.get("key")): entry
            for entry in available
            if isinstance(entry, dict) and entry.get("key") is not None
        }
        prop_id = str(prop_key)
        if prop_id not in available_map:
            return False
        visible_keys = {
            str(prop.get("key"))
            for prop in info.get("properties", [])
            if isinstance(prop, dict) and prop.get("key") is not None
        }
        if prop_id in visible_keys:
            return False

        manual_entry = self._panel_manual_properties.get(key)
        item_id = info.get("item_id", "")
        item_type = info.get("item_type")
        if (
            not manual_entry
            or manual_entry.get("item_id") != item_id
            or manual_entry.get("item_type") != item_type
        ):
            manual_entry = {"item_id": item_id, "item_type": item_type, "properties": set()}
        else:
            manual_entry = {
                "item_id": manual_entry.get("item_id", ""),
                "item_type": manual_entry.get("item_type"),
                "properties": set(manual_entry.get("properties") or []),
            }

        manual_entry["properties"].add(prop_id)
        self._panel_manual_properties[key] = manual_entry
        self._update_track_panel_properties()
        self.geometry.mark_dirty()
        self.update()
        return True

    def _startMiddlePan(self, pos):
        view_w = self.scrollbar_position[3]
        timeline_w = self.scrollbar_position[2]
        view_h = self.v_scrollbar_position[3]
        content_h = self.v_scrollbar_position[2]
        if not any((view_w, timeline_w, view_h, content_h)):
            return False
        self._middle_panning = True
        self.mouse_dragging = True
        self._middle_pan_anchor = QPointF(pos)
        self._middle_pan_scroll_start = list(self.scrollbar_position)
        self._middle_pan_vscroll_start = list(self.v_scrollbar_position)
        self._fix_cursor(self.cursors.get("hand", self.cursor()))
        return True

    def _updateMiddlePan(self, pos):
        if not self._middle_panning:
            return
        posf = QPointF(pos)
        delta = posf - self._middle_pan_anchor
        new_positions = list(self._middle_pan_scroll_start)
        new_v_positions = list(self._middle_pan_vscroll_start)

        view_w = new_positions[3] or self.width()
        timeline_w = new_positions[2] or view_w
        width_norm = new_positions[1] - new_positions[0]
        if timeline_w > 0 and width_norm < 1.0:
            left = new_positions[0] - (delta.x() / timeline_w)
            left = max(0.0, min(left, 1.0 - width_norm))
            new_positions[0] = left
            new_positions[1] = left + width_norm

        view_h = new_v_positions[3] or self.height()
        content_h = new_v_positions[2] or view_h
        height_norm = new_v_positions[1] - new_v_positions[0]
        if content_h > 0 and height_norm < 1.0:
            top = new_v_positions[0] - (delta.y() / content_h)
            top = max(0.0, min(top, 1.0 - height_norm))
            new_v_positions[0] = top
            new_v_positions[1] = top + height_norm

        changed = new_positions[:2] != self.scrollbar_position[:2]
        v_changed = new_v_positions[:2] != self.v_scrollbar_position[:2]
        if changed:
            self.scrollbar_position = new_positions
            timeline_w = new_positions[2] or new_positions[3] or 0.0
            self.h_scroll_offset = new_positions[0] * timeline_w
            get_app().window.TimelineScrolled.emit(list(self.scrollbar_position))
        if v_changed:
            self.v_scrollbar_position = new_v_positions
        if changed or v_changed:
            self._update_scrollbar_handles()
            self.update()

    def _finishMiddlePan(self):
        if not self._middle_panning:
            return
        self._middle_panning = False
        self.mouse_dragging = False
        self._release_cursor()

    def _showContextMenu(self, pos):
        """Show appropriate context menu for the position. Returns True if handled."""
        self.geometry.ensure()

        # Playhead context menu
        if self._playhead_hit(pos) and hasattr(self.win, "timeline"):
            # Convert frame number to seconds for backend API
            seconds = 0.0
            if self.fps_float:
                seconds = max(0.0, (max(1, self.current_frame) - 1) / self.fps_float)
            self.win.timeline.ShowPlayheadMenu(seconds)
            return True

        marker_entry = self._marker_at(pos)
        if marker_entry and isinstance(marker_entry, dict) and hasattr(self.win, "timeline"):
            marker_id = self._marker_identifier(marker_entry)
            if marker_id:
                self._select_marker(marker_entry)
                self.win.timeline.ShowMarkerMenu(marker_id)
                return True

        # Transition context menu (prioritized over clips)
        for rect, tran, _selected in self.geometry.iter_transitions(reverse=True):
            if rect.contains(pos) and hasattr(self.win, "timeline"):
                if tran.id not in getattr(self.win, "selected_transitions", []):
                    self._select_timeline_item(tran.id, "transition", True)
                self.win.timeline.ShowTransitionMenu(tran.id)
                return True

        # Clip context menu
        for rect, clip, _selected in self.geometry.iter_clips(reverse=True):
            if rect.contains(pos) and hasattr(self.win, "timeline"):
                if clip.id not in getattr(self.win, "selected_clips", []):
                    self._select_timeline_item(clip.id, "clip", True)
                self.win.timeline.ShowClipMenu(clip.id)
                return True

        # Track context menu
        for track_rect, track, name_rect in self.geometry.iter_tracks():
            if name_rect.contains(pos) and hasattr(self.win, "timeline"):
                self.win.timeline.ShowTrackMenu(track.id)
                return True
            if track_rect.contains(pos) and hasattr(self.win, "timeline"):
                seconds = 0.0
                if hasattr(self.win.timeline, "_seconds_from_x"):
                    seconds = max(0.0, float(self.win.timeline._seconds_from_x(pos.x())))
                self.win.timeline.ShowTimelineMenu(seconds, track.data.get("number"))
                return True

        return False
