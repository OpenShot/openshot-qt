"""
@file
@brief Trim & Edit panel with three-point and four-point editing and source monitor.
@author OpenShot Studios, LLC
@section LICENSE

Copyright (c) 2008-2026 OpenShot Studios, LLC
(http://www.openshotstudios.com). This file is part of
OpenShot Video Editor (http://www.openshot.org), an open-source project
dedicated to delivering high quality video editing and animation solutions
to the world.

OpenShot Video Editor is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import os
import uuid

from qt_api import (
    Qt, pyqtSlot, QObject, QWidget, QDockWidget, QLabel,
    QPushButton, QToolButton, QComboBox, QSlider, QLineEdit, QAction,
    QIcon, QTimer, QColor, QPainter, QBrush, QPen, QFont, QSizePolicy,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QScrollArea, QPixmap,
    QImage, QKeySequence, QMessageBox, QRect, QRectF, QSplitter, QSize
)

from classes import info, ui_util
from classes.app import get_app
from classes.logger import log
from classes.query import Clip, File
from classes.thumbnail import FindCachedThumbnail, ThumbnailCacheId


def format_tc(seconds, fps=30.0):
    """Format seconds into HH:MM:SS.FF timecode."""
    if seconds is None:
        return "--:--:--.--"
    seconds = max(0.0, float(seconds))
    fps = max(1.0, float(fps))
    total_frames = int(round(seconds * fps))
    fps_int = max(1, int(round(fps)))
    frames = total_frames % fps_int
    total_seconds = total_frames // fps_int
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{frames:02d}"


def parse_tc(tc_str, fps=30.0):
    """Parse HH:MM:SS.FF or HH:MM:SS:FF or raw seconds into float seconds."""
    if not tc_str or not isinstance(tc_str, str):
        return None
    tc_str = tc_str.strip()
    if not tc_str:
        return None
    fps = max(1.0, float(fps))
    # Direct float seconds support: e.g. "5.5", "10"
    if ":" not in tc_str and ";" not in tc_str:
        try:
            return max(0.0, float(tc_str))
        except ValueError:
            pass
    s = tc_str.replace(";", ":").replace(",", ".")
    parts = s.split(":")
    try:
        if len(parts) == 1:
            return max(0.0, float(parts[0]))
        if len(parts) == 2:
            return max(0.0, float(parts[0]) * 60.0 + float(parts[1]))
        if len(parts) == 3:
            if "." in parts[2]:
                sec_part, frame_part = parts[2].split(".", 1)
                return max(0.0, float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(sec_part) + (float(frame_part) / fps))
            return max(0.0, float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(parts[2]))
        if len(parts) >= 4:
            h, m, sec, f = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
            return max(0.0, h * 3600.0 + m * 60.0 + sec + (f / fps))
    except (ValueError, TypeError):
        return None
    return None


class SourcePreviewCanvas(QWidget):
    """Canvas widget showing the source clip frame with In/Out markers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _ = get_app()._tr
        self.pixmap = None
        self.source_in_ratio = None
        self.source_out_ratio = None
        self.current_ratio = 0.0
        self.timecode_text = ""
        self.placeholder_text = _("Trim & Edit Monitor\n(Select a project file)")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(180, 100)

    def set_frame(self, pixmap, current_ratio=0.0, in_ratio=None, out_ratio=None, timecode="", placeholder_text=None):
        self.pixmap = pixmap
        self.current_ratio = max(0.0, min(1.0, float(current_ratio or 0.0)))
        self.source_in_ratio = in_ratio
        self.source_out_ratio = out_ratio
        self.timecode_text = timecode
        if placeholder_text is not None:
            self.placeholder_text = placeholder_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        bar_h = 10
        video_h = max(20, h - bar_h)

        # Draw dark canvas background
        painter.fillRect(0, 0, w, h, QColor(18, 20, 24))

        # Draw Pixmap if present, maintaining aspect ratio
        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                w, video_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            px = (w - scaled.width()) // 2
            py = (video_h - scaled.height()) // 2
            painter.drawPixmap(px, py, scaled)
        else:
            # Draw placeholder canvas
            painter.setPen(QColor(110, 118, 130))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                QRect(0, 0, w, video_h),
                Qt.AlignCenter,
                self.placeholder_text
            )

        # Draw Timecode badge on bottom-left corner of video area
        if self.timecode_text:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 190))
            badge_rect = QRect(8, max(4, video_h - 26), 110, 20)
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QColor(230, 235, 245))
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            painter.drawText(badge_rect, Qt.AlignCenter, self.timecode_text)

        # Draw In/Out Range Bar at the bottom
        bar_y = h - bar_h
        painter.fillRect(0, bar_y, w, bar_h, QColor(32, 36, 44))

        # Draw In-Out Range highlight if marked
        in_r = self.source_in_ratio if self.source_in_ratio is not None else 0.0
        out_r = self.source_out_ratio if self.source_out_ratio is not None else 1.0
        if self.source_in_ratio is not None or self.source_out_ratio is not None:
            rx = int(in_r * w)
            rw = max(2, int((out_r - in_r) * w))
            painter.fillRect(rx, bar_y, rw, bar_h, QColor(41, 128, 185, 170))

        # Draw In Point Marker (Green)
        if self.source_in_ratio is not None:
            ix = int(self.source_in_ratio * w)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(46, 204, 113))
            painter.drawRect(max(0, ix - 2), bar_y, 4, bar_h)

        # Draw Out Point Marker (Red)
        if self.source_out_ratio is not None:
            ox = int(self.source_out_ratio * w)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(231, 76, 60))
            painter.drawRect(max(0, ox - 2), bar_y, 4, bar_h)

        # Draw Current Playhead tick (Yellow)
        cx = int(self.current_ratio * w)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(241, 196, 15))
        painter.drawRect(max(0, cx - 1), bar_y - 2, 3, bar_h + 2)


class ThreePointEditWidget(QWidget):
    """Trim & Edit dock controller and UI (three-point and four-point editing)."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.win = main_window

        # State tracking
        self.current_file = None
        self.source_in = None      # float seconds
        self.source_out = None     # float seconds
        self.timeline_in = None    # float seconds (None = use current playhead)
        self.timeline_out = None   # float seconds
        self.current_frame = 1
        self.total_frames = 1
        self.fps = 30.0
        self.duration = 0.0

        # Native frame reader for live frame decoding
        self.source_reader = None

        # Playback timer for preview
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._step_play_forward)

        self._init_ui()
        self.refresh_files()

        # Connect to main window selection/update signals if available
        if self.win:
            if hasattr(self.win, "refreshFilesSignal"):
                self.win.refreshFilesSignal.connect(self.refresh_files)
            if hasattr(self.win, "FileUpdated"):
                self.win.FileUpdated.connect(lambda fid: self.refresh_files())
            self._connect_project_files_selection()

    def _connect_project_files_selection(self):
        """Listen to selection changes in Project Files to auto-load clicked clips."""
        try:
            if hasattr(self.win, "filesView") and self.win.filesView:
                sel_model = self.win.filesView.selectionModel()
                if sel_model:
                    sel_model.selectionChanged.connect(self._on_project_files_selection_changed)
        except (AttributeError, RuntimeError) as ex:
            log.debug("Failed to connect project files selection: %s", ex)

    def _on_project_files_selection_changed(self, selected=None, deselected=None):
        """Handle selection changes in Project Files view."""
        try:
            if hasattr(self.win, "files_model") and self.win.files_model:
                f = self.win.files_model.current_file()
                if not f:
                    sel = self.win.files_model.selected_files()
                    if sel:
                        f = sel[0]
                if f and (not self.current_file or self.current_file.id != f.id):
                    self.select_file_by_id(f.id)
        except (AttributeError, RuntimeError, IndexError) as ex:
            log.debug("Project files selection change error: %s", ex)

    def select_file_by_id(self, file_id):
        """Switch source combo to the specified file ID."""
        for idx in range(self.cmb_files.count()):
            if self.cmb_files.itemData(idx) == file_id:
                if self.cmb_files.currentIndex() != idx:
                    self.cmb_files.setCurrentIndex(idx)
                break

    def _init_ui(self):
        """Construct the responsive layout matching OpenShot application styling."""
        _ = get_app()._tr
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ─── Vertical Splitter (Makes Monitor & Bottom Controls Resizable) ─────
        self.splitter = QSplitter(Qt.Vertical, self)
        self.splitter.setChildrenCollapsible(False)

        # ─── TOP PANE: Monitor View Area ──────────────────────────────────────
        self.top_container = QWidget()
        top_layout = QVBoxLayout(self.top_container)
        top_layout.setContentsMargins(6, 6, 6, 4)
        top_layout.setSpacing(4)

        # Source Selector Row
        sel_box = QHBoxLayout()
        sel_box.setSpacing(6)
        lbl_file = QLabel(_("Source:"))
        lbl_file.setStyleSheet("font-weight: bold;")
        self.cmb_files = QComboBox()
        self.cmb_files.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cmb_files.currentIndexChanged.connect(self._on_file_selected)

        btn_refresh = QToolButton()
        btn_refresh.setToolTip(_("Refresh project files list"))
        btn_refresh.setAutoRaise(True)
        refresh_icon = ui_util.get_icon("view-refresh")
        if refresh_icon:
            btn_refresh.setIcon(refresh_icon)
        else:
            btn_refresh.setText("⟳")
        btn_refresh.clicked.connect(self.refresh_files)

        sel_box.addWidget(lbl_file)
        sel_box.addWidget(self.cmb_files)
        sel_box.addWidget(btn_refresh)
        top_layout.addLayout(sel_box)

        # File metadata line
        self.lbl_info = QLabel(_("No file loaded"))
        self.lbl_info.setStyleSheet("color: #828b98; font-size: 11px;")
        top_layout.addWidget(self.lbl_info)

        # Source Preview Viewport Canvas
        self.preview_canvas = SourcePreviewCanvas(self.top_container)
        top_layout.addWidget(self.preview_canvas, 1)

        # Scrubber Slider
        scrub_layout = QVBoxLayout()
        scrub_layout.setSpacing(2)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(1)
        self.slider.valueChanged.connect(self._on_scrubber_moved)
        scrub_layout.addWidget(self.slider)

        # Transport & Timecode Bar (matching Video Preview QToolButton toolbar style)
        trans_layout = QHBoxLayout()
        trans_layout.setSpacing(4)

        icon_size = QSize(20, 20)

        self.btn_jump_start = QToolButton(self.top_container)
        self.btn_jump_start.setIcon(ui_util.get_icon("media-skip-backward") or QIcon())
        self.btn_jump_start.setIconSize(icon_size)
        self.btn_jump_start.setAutoRaise(True)
        self.btn_jump_start.setToolTip(_("Jump to Start (Home)"))
        if self.btn_jump_start.icon().isNull():
            self.btn_jump_start.setText("⏮")
        self.btn_jump_start.clicked.connect(lambda: self.seek_frame(1))

        self.btn_prev = QToolButton(self.top_container)
        self.btn_prev.setIcon(ui_util.get_icon("media-seek-backward") or QIcon())
        self.btn_prev.setIconSize(icon_size)
        self.btn_prev.setAutoRaise(True)
        self.btn_prev.setToolTip(_("Previous Frame (Left Arrow)"))
        if self.btn_prev.icon().isNull():
            self.btn_prev.setText("◀")
        self.btn_prev.clicked.connect(self.step_backward)

        self.btn_play = QToolButton(self.top_container)
        self.icon_play = ui_util.get_icon("media-playback-start")
        self.icon_pause = ui_util.get_icon("media-playback-pause")
        self.btn_play.setIcon(self.icon_play or QIcon())
        self.btn_play.setIconSize(icon_size)
        self.btn_play.setAutoRaise(True)
        self.btn_play.setToolTip(_("Play / Pause (Space)"))
        if self.btn_play.icon().isNull():
            self.btn_play.setText("▶")
        self.btn_play.clicked.connect(self.toggle_play)

        self.btn_next = QToolButton(self.top_container)
        self.btn_next.setIcon(ui_util.get_icon("media-seek-forward") or QIcon())
        self.btn_next.setIconSize(icon_size)
        self.btn_next.setAutoRaise(True)
        self.btn_next.setToolTip(_("Next Frame (Right Arrow)"))
        if self.btn_next.icon().isNull():
            self.btn_next.setText("▶")
        self.btn_next.clicked.connect(self.step_forward)

        self.btn_jump_end = QToolButton(self.top_container)
        self.btn_jump_end.setIcon(ui_util.get_icon("media-skip-forward") or QIcon())
        self.btn_jump_end.setIconSize(icon_size)
        self.btn_jump_end.setAutoRaise(True)
        self.btn_jump_end.setToolTip(_("Jump to End (End)"))
        if self.btn_jump_end.icon().isNull():
            self.btn_jump_end.setText("⏭")
        self.btn_jump_end.clicked.connect(lambda: self.seek_frame(self.total_frames))

        self.lbl_current_tc = QLabel("00:00:00.00 / 00:00:00.00")
        self.lbl_current_tc.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        self.lbl_current_tc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        trans_layout.addWidget(self.btn_jump_start)
        trans_layout.addWidget(self.btn_prev)
        trans_layout.addWidget(self.btn_play)
        trans_layout.addWidget(self.btn_next)
        trans_layout.addWidget(self.btn_jump_end)
        trans_layout.addStretch()
        trans_layout.addWidget(self.lbl_current_tc)

        scrub_layout.addLayout(trans_layout)
        top_layout.addLayout(scrub_layout)

        self.splitter.addWidget(self.top_container)

        # ─── BOTTOM PANE: Controls in Resizable Scroll Area ───────────────────
        self.bottom_scroll = QScrollArea()
        self.bottom_scroll.setWidgetResizable(True)
        self.bottom_scroll.setFrameShape(QFrame.NoFrame)
        self.bottom_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.bottom_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.bottom_container = QWidget()
        bottom_layout = QVBoxLayout(self.bottom_container)
        bottom_layout.setContentsMargins(6, 4, 6, 6)
        bottom_layout.setSpacing(6)

        # In/Out Points Editor Cards Row
        points_box = QHBoxLayout()
        points_box.setSpacing(6)

        # Card 1: Source Points Card
        card_src = QFrame()
        card_src.setFrameShape(QFrame.StyledPanel)
        l_src = QGridLayout(card_src)
        l_src.setContentsMargins(6, 6, 6, 6)
        l_src.setSpacing(4)

        lbl_src_hdr = QLabel(_("SOURCE CLIP"))
        lbl_src_hdr.setStyleSheet("color: #5dade2; font-weight: bold; font-size: 10px; letter-spacing: 1px;")
        l_src.addWidget(lbl_src_hdr, 0, 0, 1, 2)

        self.btn_src_in = QPushButton(_("Mark In (I)"))
        self.btn_src_in.clicked.connect(self.mark_source_in)
        self.txt_src_in = QLineEdit()
        self.txt_src_in.setPlaceholderText("00:00:00.00")
        self.txt_src_in.editingFinished.connect(self._on_txt_src_in_edited)

        self.btn_src_out = QPushButton(_("Mark Out (O)"))
        self.btn_src_out.clicked.connect(self.mark_source_out)
        self.txt_src_out = QLineEdit()
        self.txt_src_out.setPlaceholderText(_("End"))
        self.txt_src_out.editingFinished.connect(self._on_txt_src_out_edited)

        self.btn_src_clear = QPushButton(_("Clear"))
        self.btn_src_clear.clicked.connect(self.clear_source_points)

        self.lbl_src_dur = QLabel("Dur: --:--:--.--")
        self.lbl_src_dur.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #3498db;")

        l_src.addWidget(self.btn_src_in, 1, 0)
        l_src.addWidget(self.txt_src_in, 1, 1)
        l_src.addWidget(self.btn_src_out, 2, 0)
        l_src.addWidget(self.txt_src_out, 2, 1)
        l_src.addWidget(self.btn_src_clear, 3, 0)
        l_src.addWidget(self.lbl_src_dur, 3, 1)
        points_box.addWidget(card_src)

        # Card 2: Timeline Points Card
        card_tl = QFrame()
        card_tl.setFrameShape(QFrame.StyledPanel)
        l_tl = QGridLayout(card_tl)
        l_tl.setContentsMargins(6, 6, 6, 6)
        l_tl.setSpacing(4)

        lbl_tl_hdr = QLabel(_("TIMELINE DESTINATION"))
        lbl_tl_hdr.setStyleSheet("color: #58d68d; font-weight: bold; font-size: 10px; letter-spacing: 1px;")
        l_tl.addWidget(lbl_tl_hdr, 0, 0, 1, 2)

        self.btn_tl_in = QPushButton(_("Mark In (D)"))
        self.btn_tl_in.setToolTip(_("Set Timeline In point (defaults to Playhead if blank)"))
        self.btn_tl_in.clicked.connect(self.mark_timeline_in)
        self.txt_tl_in = QLineEdit()
        self.txt_tl_in.setPlaceholderText(_("Playhead"))
        self.txt_tl_in.editingFinished.connect(self._on_txt_tl_in_edited)

        self.btn_tl_out = QPushButton(_("Mark Out (F)"))
        self.btn_tl_out.clicked.connect(self.mark_timeline_out)
        self.txt_tl_out = QLineEdit()
        self.txt_tl_out.setPlaceholderText(_("Auto"))
        self.txt_tl_out.editingFinished.connect(self._on_txt_tl_out_edited)

        self.btn_tl_clear = QPushButton(_("Clear"))
        self.btn_tl_clear.clicked.connect(self.clear_timeline_points)

        self.lbl_tl_dur = QLabel("Dur: --:--:--.--")
        self.lbl_tl_dur.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #2ecc71;")

        l_tl.addWidget(self.btn_tl_in, 1, 0)
        l_tl.addWidget(self.txt_tl_in, 1, 1)
        l_tl.addWidget(self.btn_tl_out, 2, 0)
        l_tl.addWidget(self.txt_tl_out, 2, 1)
        l_tl.addWidget(self.btn_tl_clear, 3, 0)
        l_tl.addWidget(self.lbl_tl_dur, 3, 1)
        points_box.addWidget(card_tl)

        bottom_layout.addLayout(points_box)

        # Track & 4-Point Policy Options Row
        opt_layout = QHBoxLayout()
        opt_layout.setSpacing(6)

        lbl_track = QLabel(_("Target Track:"))
        lbl_track.setStyleSheet("font-weight: bold;")
        self.cmb_track = QComboBox()
        self.cmb_track.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._populate_tracks()

        lbl_policy = QLabel(_("4-Point Policy:"))
        lbl_policy.setStyleSheet("font-weight: bold;")
        self.cmb_policy = QComboBox()
        self.cmb_policy.addItem(_("Fit to Fill (Retime / Speed)"), "retime")
        self.cmb_policy.addItem(_("Trim Source (Fit Timeline)"), "trim_source")
        self.cmb_policy.addItem(_("Trim Timeline (Fit Source)"), "trim_timeline")
        self.cmb_policy.addItem(_("Ripple / Shift"), "ripple")
        self.cmb_policy.currentIndexChanged.connect(self._on_policy_changed)

        opt_layout.addWidget(lbl_track)
        opt_layout.addWidget(self.cmb_track)
        opt_layout.addWidget(lbl_policy)
        opt_layout.addWidget(self.cmb_policy)
        bottom_layout.addLayout(opt_layout)

        # Status / Calculation Banner
        self.lbl_status = QLabel(_("Select a source file and mark points for Trim & Edit."))
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setFrameShape(QFrame.StyledPanel)
        self.lbl_status.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_status)

        # Execution Action Buttons Row (using theme-native push button styles)
        act_box = QHBoxLayout()
        act_box.setSpacing(8)

        self.btn_overwrite = QPushButton(_("Overwrite (B)"))
        self.btn_overwrite.setToolTip(_("Overwrite into timeline track across calculated duration"))
        self.btn_overwrite.setFixedHeight(28)
        bold_font = self.btn_overwrite.font()
        bold_font.setBold(True)
        self.btn_overwrite.setFont(bold_font)
        self.btn_overwrite.clicked.connect(self.execute_overwrite)

        self.btn_insert = QPushButton(_("Insert (V)"))
        self.btn_insert.setToolTip(_("Insert into timeline track and ripple subsequent clips"))
        self.btn_insert.setFixedHeight(28)
        self.btn_insert.setFont(bold_font)
        self.btn_insert.clicked.connect(self.execute_insert)

        act_box.addWidget(self.btn_overwrite)
        act_box.addWidget(self.btn_insert)
        bottom_layout.addLayout(act_box)

        self.bottom_scroll.setWidget(self.bottom_container)
        self.splitter.addWidget(self.bottom_scroll)

        # Default size and proportions: Monitor 58%, Controls 42%
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([340, 260])

        root_layout.addWidget(self.splitter)

    # ─── File & Track Synchronization ────────────────────────────────────────

    def _format_track_name(self, layer_num):
        """Format a human-friendly track label from project layer number."""
        _ = get_app()._tr
        if layer_num is None:
            return _("Track 1")
        try:
            num = int(layer_num)
            if num >= 1000000:
                return _("Track %d") % (num // 1000000)
            return _("Track %d") % num
        except Exception:
            return f"Track {layer_num}"

    def _populate_tracks(self):
        """Populate the track combobox from project layers with human-friendly names."""
        _ = get_app()._tr
        self.cmb_track.clear()
        try:
            layers = get_app().project.get("layers") or []
            sorted_layers = sorted(layers, key=lambda l: l.get("number", 0), reverse=True)
            for l in sorted_layers:
                num = l.get("number", 0)
                name = l.get("name") or l.get("label") or ""
                if num >= 1000000:
                    display_num = num // 1000000
                else:
                    display_num = num

                if name and not name.startswith("Track ") and str(num) not in name:
                    display_text = f"{name} (" + (_("Track %d") % display_num) + ")"
                else:
                    display_text = _("Track %d") % display_num
                self.cmb_track.addItem(display_text, num)
        except Exception:
            for num in range(5, 0, -1):
                self.cmb_track.addItem(_("Track %d") % num, num * 1000000)

    def refresh_files(self):
        """Sync the source file combobox with all project files."""
        _ = get_app()._tr
        current_id = self.current_file.id if self.current_file else None
        self.cmb_files.blockSignals(True)
        self.cmb_files.clear()
        self.cmb_files.addItem(_("-- Select Source File --"), None)

        files = File.filter() or []
        target_idx = 0
        for idx, f in enumerate(files):
            name = f.data.get("name") or os.path.basename(f.data.get("path") or "") or f"File {f.id}"
            self.cmb_files.addItem(name, f.id)
            if current_id and f.id == current_id:
                target_idx = idx + 1

        self.cmb_files.setCurrentIndex(target_idx)
        self.cmb_files.blockSignals(False)
        self._populate_tracks()

        if target_idx > 0:
            self._on_file_selected(target_idx)
        elif files and not self.current_file:
            self.cmb_files.setCurrentIndex(1)

    def _on_file_selected(self, index):
        """Handle user picking a file from the dropdown."""
        _ = get_app()._tr
        file_id = self.cmb_files.currentData()
        if not file_id:
            self._close_reader()
            self.current_file = None
            self.lbl_info.setText(_("No file loaded"))
            self.preview_canvas.set_frame(None, placeholder_text=_("Trim & Edit Monitor\n(Select a project file)"))
            self._update_status_and_parameters()
            return

        f = File.get(id=file_id)
        if not f:
            return
        self.load_file(f)

    def _close_reader(self):
        """Safely close and clean up any native reader."""
        if self.source_reader:
            try:
                self.source_reader.Close()
            except Exception:
                pass
            self.source_reader = None

    def load_file(self, file_obj):
        """Load a file object into the source monitor and initialize its reader."""
        self._close_reader()
        self.current_file = file_obj
        data = file_obj.data or {}

        # Extract metadata
        self.fps = 30.0
        fps_dict = data.get("fps") or {}
        if isinstance(fps_dict, dict) and fps_dict.get("den"):
            self.fps = float(fps_dict.get("num", 30)) / float(fps_dict.get("den", 1))

        self.duration = float(data.get("duration") or 0.0)
        self.total_frames = max(1, int(data.get("video_length") or round(self.duration * self.fps)))
        if self.duration <= 0.0 and self.total_frames > 1:
            self.duration = self.total_frames / self.fps

        w = data.get("width", 0)
        h = data.get("height", 0)
        name = data.get("name") or os.path.basename(data.get("path") or "")
        self.lbl_info.setText(f"{name} | {w}x{h} @ {self.fps:.2f}fps | {format_tc(self.duration, self.fps)}")

        # Configure Scrubber
        self.slider.blockSignals(True)
        self.slider.setRange(1, self.total_frames)
        self.slider.setValue(1)
        self.slider.blockSignals(False)
        self.current_frame = 1

        # Clear existing source points on file switch
        self.source_in = None
        self.source_out = None
        self.txt_src_in.clear()
        self.txt_src_out.clear()

        # Attempt to open native libopenshot reader for real-time decoding
        try:
            import openshot
            abs_path = file_obj.absolute_path()
            if abs_path and os.path.isfile(abs_path):
                self.source_reader = openshot.Clip.CreateReader(abs_path, False)
                if hasattr(self.source_reader, "SetMaxDecodeSize"):
                    self.source_reader.SetMaxDecodeSize(960, 540)
                self.source_reader.Open()
        except Exception as e:
            log.debug("Source monitor: native reader open skipped: %s", e)
            self.source_reader = None

        self._refresh_frame_display()
        self._update_status_and_parameters()

    # ─── Frame Stepping and Playback ─────────────────────────────────────────

    def seek_frame(self, frame_num):
        """Seek source preview to a specific frame."""
        frame_num = max(1, min(self.total_frames, int(frame_num)))
        self.current_frame = frame_num
        self.slider.blockSignals(True)
        self.slider.setValue(frame_num)
        self.slider.blockSignals(False)
        self._refresh_frame_display()

    def step_forward(self):
        self.seek_frame(self.current_frame + 1)

    def step_backward(self):
        self.seek_frame(self.current_frame - 1)

    def toggle_play(self):
        """Toggle preview playback."""
        if self.play_timer.isActive():
            self.play_timer.stop()
            if self.icon_play and not self.icon_play.isNull():
                self.btn_play.setIcon(self.icon_play)
            else:
                self.btn_play.setText("▶")
        else:
            interval = max(10, int(round(1000.0 / self.fps)))
            self.play_timer.start(interval)
            if self.icon_pause and not self.icon_pause.isNull():
                self.btn_play.setIcon(self.icon_pause)
            else:
                self.btn_play.setText("⏸")

    def _step_play_forward(self):
        """Step playback forward, looping between In and Out points if set."""
        start_f = int(round(self.source_in * self.fps)) + 1 if self.source_in is not None else 1
        end_f = int(round(self.source_out * self.fps)) + 1 if self.source_out is not None else self.total_frames
        if self.current_frame >= end_f:
            self.seek_frame(start_f)
        else:
            self.seek_frame(self.current_frame + 1)

    def _on_scrubber_moved(self, value):
        self.current_frame = value
        self._refresh_frame_display()

    def _refresh_frame_display(self):
        """Fetch and paint the source preview frame via native reader or multi-tier fallbacks."""
        _ = get_app()._tr
        if not self.current_file:
            self.preview_canvas.set_frame(None, placeholder_text=_("Trim & Edit Monitor\n(Select a project file)"))
            return

        current_secs = (self.current_frame - 1) / self.fps
        cur_ratio = (self.current_frame - 1) / max(1, self.total_frames - 1)
        in_ratio = (self.source_in / self.duration) if (self.source_in is not None and self.duration > 0) else None
        out_ratio = (self.source_out / self.duration) if (self.source_out is not None and self.duration > 0) else None

        pix = None

        # Tier 1: Decode live frame from native libopenshot reader
        if self.source_reader:
            try:
                decoded = self.source_reader.GetFrame(self.current_frame)
                if decoded and decoded.GetWidth() > 0 and decoded.GetHeight() > 0:
                    img = QImage(
                        decoded.GetPixelsBytes(),
                        decoded.GetWidth(),
                        decoded.GetHeight(),
                        decoded.GetBytesPerLine(),
                        QImage.Format_RGBA8888_Premultiplied
                    ).copy()
                    if not img.isNull():
                        pix = QPixmap.fromImage(img)
            except Exception as e:
                log.debug("Frame decode error on frame %s: %s", self.current_frame, e)

        # Tier 2: Exact or rounded cached thumbnail
        if pix is None or pix.isNull():
            try:
                thumb_path = FindCachedThumbnail(self.current_file.id, self.current_frame, self.fps)
                if thumb_path and os.path.isfile(thumb_path):
                    pix = QPixmap(thumb_path)
            except Exception:
                pass

        # Tier 3: Closest frame thumbnail in cache directory
        if pix is None or pix.isNull():
            try:
                cache_dir = os.path.join(info.THUMBNAIL_PATH, ThumbnailCacheId(self.current_file.id))
                if os.path.isdir(cache_dir):
                    closest_path = None
                    min_diff = float("inf")
                    for fname in os.listdir(cache_dir):
                        if fname.endswith(".png"):
                            fnum_str = os.path.splitext(fname)[0]
                            if fnum_str.isdigit():
                                fnum = int(fnum_str)
                                diff = abs(fnum - self.current_frame)
                                if diff < min_diff:
                                    min_diff = diff
                                    closest_path = os.path.join(cache_dir, fname)
                    if closest_path and os.path.isfile(closest_path):
                        pix = QPixmap(closest_path)
            except Exception:
                pass

        # Tier 4: Fallback to frame 1 cached thumbnail
        if pix is None or pix.isNull():
            try:
                thumb_path = FindCachedThumbnail(self.current_file.id, 1, self.fps)
                if thumb_path and os.path.isfile(thumb_path):
                    pix = QPixmap(thumb_path)
            except Exception:
                pass

        # Tier 5: Direct image file preview fallback
        if pix is None or pix.isNull():
            try:
                abs_path = self.current_file.absolute_path()
                if abs_path and os.path.isfile(abs_path):
                    ext = os.path.splitext(abs_path)[1].lower()
                    if ext in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp"}:
                        pix = QPixmap(abs_path)
            except Exception:
                pass

        tc_display = f"{format_tc(current_secs, self.fps)} / {format_tc(self.duration, self.fps)}"
        self.lbl_current_tc.setText(tc_display)

        file_name = self.current_file.data.get("name") or os.path.basename(self.current_file.absolute_path() or "")
        self.preview_canvas.set_frame(
            pix,
            current_ratio=cur_ratio,
            in_ratio=in_ratio,
            out_ratio=out_ratio,
            timecode=format_tc(current_secs, self.fps),
            placeholder_text=f"{file_name}\n" + _("Loading frame...") if self.current_file else _("Trim & Edit Monitor\n(Select a project file)")
        )

    # ─── Mark In / Out Operations ────────────────────────────────────────────

    def mark_source_in(self):
        """Set source In point at the current scrubber frame."""
        if not self.current_file:
            return
        sec = max(0.0, (self.current_frame - 1) / self.fps)
        if self.source_out is not None and sec >= self.source_out:
            sec = max(0.0, self.source_out - (1.0 / self.fps))
        self.source_in = sec
        self.txt_src_in.setText(format_tc(self.source_in, self.fps))
        self._refresh_frame_display()
        self._update_status_and_parameters()

    def mark_source_out(self):
        """Set source Out point at the current scrubber frame."""
        if not self.current_file:
            return
        sec = min(self.duration, (self.current_frame - 1) / self.fps)
        if self.source_in is not None and sec <= self.source_in:
            sec = min(self.duration, self.source_in + (1.0 / self.fps))
        self.source_out = sec
        self.txt_src_out.setText(format_tc(self.source_out, self.fps))
        self._refresh_frame_display()
        self._update_status_and_parameters()

    def clear_source_points(self):
        """Clear source In and Out marks."""
        self.source_in = None
        self.source_out = None
        self.txt_src_in.clear()
        self.txt_src_out.clear()
        self._refresh_frame_display()
        self._update_status_and_parameters()

    def mark_timeline_in(self):
        """Mark Timeline In at the current timeline playhead position."""
        tl_sec = self._get_current_timeline_seconds()
        if self.timeline_out is not None and tl_sec >= self.timeline_out:
            tl_sec = max(0.0, self.timeline_out - 0.1)
        self.timeline_in = tl_sec
        self.txt_tl_in.setText(format_tc(self.timeline_in, self._project_fps()))
        self._update_status_and_parameters()

    def mark_timeline_out(self):
        """Mark Timeline Out at the current timeline playhead position."""
        tl_sec = self._get_current_timeline_seconds()
        if self.timeline_in is not None and tl_sec <= self.timeline_in:
            tl_sec = self.timeline_in + 1.0
        self.timeline_out = tl_sec
        self.txt_tl_out.setText(format_tc(self.timeline_out, self._project_fps()))
        self._update_status_and_parameters()

    def clear_timeline_points(self):
        """Clear timeline marks."""
        self.timeline_in = None
        self.timeline_out = None
        self.txt_tl_in.clear()
        self.txt_tl_out.clear()
        self._update_status_and_parameters()

    def _on_txt_src_in_edited(self):
        val = parse_tc(self.txt_src_in.text(), self.fps)
        if val is not None:
            self.source_in = max(0.0, min(self.duration, val))
            self.txt_src_in.setText(format_tc(self.source_in, self.fps))
        else:
            self.source_in = None
            self.txt_src_in.clear()
        self._refresh_frame_display()
        self._update_status_and_parameters()

    def _on_txt_src_out_edited(self):
        val = parse_tc(self.txt_src_out.text(), self.fps)
        if val is not None:
            self.source_out = max(0.0, min(self.duration, val))
            self.txt_src_out.setText(format_tc(self.source_out, self.fps))
        else:
            self.source_out = None
            self.txt_src_out.clear()
        self._refresh_frame_display()
        self._update_status_and_parameters()

    def _on_txt_tl_in_edited(self):
        val = parse_tc(self.txt_tl_in.text(), self._project_fps())
        self.timeline_in = val
        if val is not None:
            self.txt_tl_in.setText(format_tc(self.timeline_in, self._project_fps()))
        self._update_status_and_parameters()

    def _on_txt_tl_out_edited(self):
        val = parse_tc(self.txt_tl_out.text(), self._project_fps())
        self.timeline_out = val
        if val is not None:
            self.txt_tl_out.setText(format_tc(self.timeline_out, self._project_fps()))
        self._update_status_and_parameters()

    def _get_current_timeline_seconds(self):
        """Read the live playhead position from the main window."""
        if self.win and hasattr(self.win, "_current_timeline_seconds"):
            try:
                return float(self.win._current_timeline_seconds())
            except Exception:
                pass
        try:
            cur_f = get_app().window.preview_thread.current_frame
            fps = self._project_fps()
            return max(0.0, (float(cur_f) - 1.0) / fps)
        except Exception:
            return 0.0

    def _project_fps(self):
        """Read active project frames-per-second."""
        try:
            fps_d = get_app().project.get("fps") or {}
            if fps_d.get("den"):
                return float(fps_d.get("num", 30)) / float(fps_d.get("den", 1))
        except Exception:
            pass
        return 30.0

    # ─── 3-Point & 4-Point Core Parameter Calculator ─────────────────────────

    def calculate_edit_parameters(self):
        """
        Evaluate Source In/Out and Timeline In/Out marks.
        Returns a dictionary detailing edit parameters, resolved boundaries, and status.
        """
        _ = get_app()._tr
        if not self.current_file:
            return {"valid": False, "message": _("No source file selected.")}

        p_fps = self._project_fps()
        src_dur = self.duration
        s_in = self.source_in if self.source_in is not None else 0.0
        s_out = self.source_out if self.source_out is not None else src_dur

        if s_out <= s_in:
            return {"valid": False, "message": _("Source Out must be greater than Source In.")}

        source_span = s_out - s_in

        # Target layer
        layer = self.cmb_track.currentData()
        if layer is None:
            layer = 1000000
        track_label = self._format_track_name(layer)

        # Timeline playhead default if Timeline In is not marked
        effective_tl_in = self.timeline_in
        if effective_tl_in is None:
            effective_tl_in = self._get_current_timeline_seconds()

        tl_in = self.timeline_in
        tl_out = self.timeline_out

        # ─── Four-Point Editing (All 4 points explicitly provided) ─────────────
        if tl_in is not None and tl_out is not None and self.source_in is not None and self.source_out is not None:
            if tl_out <= tl_in:
                return {"valid": False, "message": _("Timeline Out must be greater than Timeline In.")}
            tl_span = tl_out - tl_in
            policy = self.cmb_policy.currentData() or "retime"

            # Case: Durations match exactly
            if abs(source_span - tl_span) < 0.001:
                return {
                    "valid": True,
                    "mode": "4-point",
                    "policy": "exact",
                    "src_in": s_in,
                    "src_out": s_out,
                    "timeline_in": tl_in,
                    "timeline_out": tl_out,
                    "duration": tl_span,
                    "speed_factor": 1.0,
                    "layer": layer,
                    "message": f"4-Point Exact Match: {format_tc(tl_span, p_fps)} on {track_label}."
                }

            # Four-Point Conflict Resolution Policies
            if policy == "retime":
                speed_factor = source_span / tl_span
                return {
                    "valid": True,
                    "mode": "4-point",
                    "policy": "retime",
                    "src_in": s_in,
                    "src_out": s_out,
                    "timeline_in": tl_in,
                    "timeline_out": tl_out,
                    "duration": tl_span,
                    "speed_factor": speed_factor,
                    "layer": layer,
                    "message": f"4-Point Fit to Fill (Speed: {speed_factor * 100:.1f}%) on {track_label}."
                }
            if policy == "trim_source":
                resolved_s_out = min(src_dur, s_in + tl_span)
                return {
                    "valid": True,
                    "mode": "4-point",
                    "policy": "trim_source",
                    "src_in": s_in,
                    "src_out": resolved_s_out,
                    "timeline_in": self.timeline_in,
                    "timeline_out": self.timeline_out,
                    "duration": tl_span,
                    "speed_factor": 1.0,
                    "layer": layer,
                    "message": f"4-Point Mismatch: Trim Source to {format_tc(tl_span, p_fps)} on {track_label}."
                }
            if policy == "trim_timeline":
                resolved_tl_out = self.timeline_in + source_span
                return {
                    "valid": True,
                    "mode": "4-point",
                    "policy": "trim_timeline",
                    "src_in": s_in,
                    "src_out": s_out,
                    "timeline_in": self.timeline_in,
                    "timeline_out": resolved_tl_out,
                    "duration": source_span,
                    "speed_factor": 1.0,
                    "layer": layer,
                    "message": f"4-Point Mismatch: Trim Timeline to {format_tc(source_span, p_fps)} on {track_label}."
                }
            if policy == "ripple":
                return {
                    "valid": True,
                    "mode": "4-point",
                    "policy": "ripple",
                    "src_in": s_in,
                    "src_out": s_out,
                    "timeline_in": self.timeline_in,
                    "timeline_out": self.timeline_in + source_span,
                    "duration": source_span,
                    "speed_factor": 1.0,
                    "layer": layer,
                    "message": f"4-Point Mismatch: Ripple Shift {format_tc(source_span, p_fps)} on {track_label}."
                }

        # ─── Three-Point Editing ─────────────────────────────────────────────
        # Case 1: Source In + Out set, Timeline In set (or playhead default)
        if tl_out is None:
            resolved_tl_in = effective_tl_in
            resolved_tl_out = resolved_tl_in + source_span
            return {
                "valid": True,
                "mode": "3-point",
                "policy": "standard",
                "src_in": s_in,
                "src_out": s_out,
                "timeline_in": resolved_tl_in,
                "timeline_out": resolved_tl_out,
                "duration": source_span,
                "speed_factor": 1.0,
                "layer": layer,
                "message": f"3-Point Ready: Source ({format_tc(source_span, p_fps)}) → Timeline [{format_tc(resolved_tl_in, p_fps)} - {format_tc(resolved_tl_out, p_fps)}] on {track_label}."
            }

        # Case 2: Source In + Out set, Timeline Out set, Timeline In unmarked
        if tl_in is None and tl_out is not None:
            resolved_tl_in = max(0.0, tl_out - source_span)
            return {
                "valid": True,
                "mode": "3-point",
                "policy": "standard",
                "src_in": s_in,
                "src_out": s_out,
                "timeline_in": resolved_tl_in,
                "timeline_out": tl_out,
                "duration": source_span,
                "speed_factor": 1.0,
                "layer": layer,
                "message": f"3-Point Back-Timed: Source ({format_tc(source_span, p_fps)}) → Timeline Out {format_tc(tl_out, p_fps)} on {track_label}."
            }

        # Case 3: Timeline In + Out set, Source Out unmarked
        if tl_in is not None and tl_out is not None:
            tl_span = max(0.01, tl_out - tl_in)
            resolved_s_out = min(src_dur, s_in + tl_span)
            return {
                "valid": True,
                "mode": "3-point",
                "policy": "standard",
                "src_in": s_in,
                "src_out": resolved_s_out,
                "timeline_in": tl_in,
                "timeline_out": tl_out,
                "duration": tl_span,
                "speed_factor": 1.0,
                "layer": layer,
                "message": f"3-Point Timeline-Fit: Source In {format_tc(s_in, self.fps)} fitted to {format_tc(tl_span, p_fps)} on {track_label}."
            }

        return {"valid": False, "message": _("Incomplete edit points.")}

    def _on_policy_changed(self, _index=0):
        """Handle 4-point policy combo selection changes."""
        self._update_status_and_parameters()

    def _update_status_and_parameters(self):
        """Recalculate and update the UI status label and action buttons."""
        res = self.calculate_edit_parameters()
        valid = res.get("valid", False)
        self.btn_overwrite.setEnabled(valid)
        self.btn_insert.setEnabled(valid)

        # Update Durations display
        s_in = self.source_in or 0.0
        s_out = self.source_out or self.duration
        self.lbl_src_dur.setText(f"Dur: {format_tc(max(0.0, s_out - s_in), self.fps)}")

        if self.timeline_in is not None and self.timeline_out is not None:
            self.lbl_tl_dur.setText(f"Dur: {format_tc(max(0.0, self.timeline_out - self.timeline_in), self._project_fps())}")
        elif self.timeline_in is not None:
            self.lbl_tl_dur.setText(f"In: {format_tc(self.timeline_in, self._project_fps())}")
        elif self.timeline_out is not None:
            self.lbl_tl_dur.setText(f"Out: {format_tc(self.timeline_out, self._project_fps())}")
        else:
            self.lbl_tl_dur.setText("Dur: Playhead")

        msg = res.get("message", "")
        self.lbl_status.setText(msg)

    # ─── Timeline Overwrite and Insert Execution ─────────────────────────────

    def execute_overwrite(self):
        """Execute an NLE overwrite edit into the timeline."""
        _ = get_app()._tr
        params = self.calculate_edit_parameters()
        if not params.get("valid"):
            QMessageBox.warning(self, _("Invalid Edit"), params.get("message", _("Cannot execute edit.")))
            return

        app = get_app()
        app.updates.transaction_id = str(uuid.uuid4())
        try:
            tl_in = params["timeline_in"]
            tl_out = params["timeline_out"]
            layer = params["layer"]
            src_in = params["src_in"]
            src_out = params["src_out"]

            # Overwrite overlapping clips on target layer
            existing_clips = Clip.filter(layer=layer) or []
            for clip in existing_clips:
                c_data = clip.data
                c_start = float(c_data.get("position", 0.0))
                c_dur = float(c_data.get("end", 0.0)) - float(c_data.get("start", 0.0))
                c_end = c_start + c_dur

                # Check intersection with [tl_in, tl_out]
                if c_end <= tl_in or c_start >= tl_out:
                    continue  # No overlap

                # Case 1: Existing clip completely engulfed by the new edit
                if c_start >= tl_in and c_end <= tl_out:
                    clip.delete()
                    continue

                # Case 2: New edit punches out the middle of an existing clip (split)
                if c_start < tl_in and c_end > tl_out:
                    right_data = copy.deepcopy(c_data)
                    right_data["id"] = str(uuid.uuid4())
                    right_offset = tl_out - c_start
                    right_data["start"] = float(c_data.get("start", 0.0)) + right_offset
                    right_data["position"] = tl_out
                    right_clip = Clip()
                    right_clip.data = right_data
                    right_clip.save()

                    c_data["end"] = float(c_data.get("start", 0.0)) + (tl_in - c_start)
                    clip.save()
                    continue

                # Case 3: Existing clip overlaps the beginning of [tl_in, tl_out]
                if c_start < tl_in and c_end > tl_in:
                    c_data["end"] = float(c_data.get("start", 0.0)) + (tl_in - c_start)
                    clip.save()
                    continue

                # Case 4: Existing clip overlaps the end of [tl_in, tl_out]
                if c_start < tl_out and c_end > tl_out:
                    trim_amt = tl_out - c_start
                    c_data["position"] = tl_out
                    c_data["start"] = float(c_data.get("start", 0.0)) + trim_amt
                    clip.save()
                    continue

            # Create and insert the new clip
            self._create_and_add_clip(
                position=tl_in,
                layer=layer,
                start=src_in,
                end=src_out,
                target_duration=params.get("duration"),
                retime=(params.get("policy") == "retime")
            )

        finally:
            app.updates.transaction_id = None

        self._finalize_edit(params["timeline_out"])

    def execute_insert(self):
        """Execute an NLE ripple insert edit into the timeline."""
        _ = get_app()._tr
        params = self.calculate_edit_parameters()
        if not params.get("valid"):
            QMessageBox.warning(self, _("Invalid Edit"), params.get("message", _("Cannot execute edit.")))
            return

        app = get_app()
        app.updates.transaction_id = str(uuid.uuid4())
        try:
            tl_in = params["timeline_in"]
            insert_dur = params["duration"]
            layer = params["layer"]
            src_in = params["src_in"]
            src_out = params["src_out"]

            # Ripple-shift clips on target layer
            existing_clips = Clip.filter(layer=layer) or []
            for clip in existing_clips:
                c_data = clip.data
                c_start = float(c_data.get("position", 0.0))
                c_dur = float(c_data.get("end", 0.0)) - float(c_data.get("start", 0.0))
                c_end = c_start + c_dur

                if c_start >= tl_in:
                    c_data["position"] = c_start + insert_dur
                    clip.save()
                elif c_start < tl_in and c_end > tl_in:
                    right_data = copy.deepcopy(c_data)
                    right_data["id"] = str(uuid.uuid4())
                    cut_offset = tl_in - c_start
                    right_data["start"] = float(c_data.get("start", 0.0)) + cut_offset
                    right_data["position"] = tl_in + insert_dur
                    right_clip = Clip()
                    right_clip.data = right_data
                    right_clip.save()

                    c_data["end"] = float(c_data.get("start", 0.0)) + cut_offset
                    clip.save()

            # Create and place new clip
            self._create_and_add_clip(
                position=tl_in,
                layer=layer,
                start=src_in,
                end=src_out,
                target_duration=insert_dur,
                retime=(params.get("policy") == "retime")
            )

        finally:
            app.updates.transaction_id = None

        self._finalize_edit(tl_in + insert_dur)

    def _create_and_add_clip(self, position, layer, start, end, target_duration=None, retime=False):
        """Construct clip dictionary and save to project data."""
        f_data = self.current_file.data
        filename = os.path.basename(f_data.get("path") or "")

        new_clip_data = {
            "id": str(uuid.uuid4()),
            "position": float(position),
            "layer": int(layer),
            "start": float(start),
            "end": float(end),
            "file_id": self.current_file.id,
            "title": f_data.get("name") or filename,
            "reader": copy.deepcopy(f_data),
            "scale": 1,
            "alpha": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 0}]},
            "effects": []
        }

        # If retime requested for fit-to-fill
        if retime and target_duration and target_duration > 0:
            from windows.views.retime import retime_clip
            clip_obj = Clip()
            clip_obj.data = new_clip_data
            clip_obj.save()
            retime_clip(clip_obj, new_end=start + target_duration)
            clip_obj.save()
            return clip_obj

        clip_obj = Clip()
        clip_obj.data = new_clip_data
        clip_obj.save()
        return clip_obj

    def _finalize_edit(self, new_playhead_sec):
        """Update main window, timeline view, and playhead position."""
        if self.win:
            p_fps = self._project_fps()
            target_frame = max(1, int(round(new_playhead_sec * p_fps)) + 1)
            if hasattr(self.win, "SeekSignal"):
                self.win.SeekSignal.emit(target_frame, True)
            if hasattr(self.win, "refreshFrameSignal"):
                self.win.refreshFrameSignal.emit()

            tl_view = getattr(self.win, "timeline", None)
            extend_fn = getattr(tl_view, "_extend_timeline_to_fit_items", None)
            if callable(extend_fn):
                try:
                    extend_fn()
                except Exception:
                    pass

        self._update_status_and_parameters()

    def on_show(self):
        """Callback when dock is displayed to update state."""
        self.refresh_files()
        self._populate_tracks()
        self._update_status_and_parameters()

    def showEvent(self, event):
        super().showEvent(event)
        self.on_show()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "play_timer") and self.play_timer.isActive():
            self.play_timer.stop()
            if hasattr(self, "btn_play"):
                if self.icon_play and not self.icon_play.isNull():
                    self.btn_play.setIcon(self.icon_play)
                else:
                    self.btn_play.setText("▶")

    def closeEvent(self, event):
        """Clean up timers and native reader upon close."""
        if hasattr(self, "play_timer") and self.play_timer.isActive():
            self.play_timer.stop()
        self._close_reader()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """Handle standard NLE keyboard shortcuts when dock has focus."""
        key = event.key()
        if key == Qt.Key_I:
            self.mark_source_in()
            event.accept()
        elif key == Qt.Key_O:
            self.mark_source_out()
            event.accept()
        elif key == Qt.Key_D:
            self.mark_timeline_in()
            event.accept()
        elif key == Qt.Key_F:
            self.mark_timeline_out()
            event.accept()
        elif key == Qt.Key_B:
            self.execute_overwrite()
            event.accept()
        elif key == Qt.Key_V:
            self.execute_insert()
            event.accept()
        elif key == Qt.Key_Space:
            self.toggle_play()
            event.accept()
        elif key == Qt.Key_Left:
            self.step_backward()
            event.accept()
        elif key == Qt.Key_Right:
            self.step_forward()
            event.accept()
        else:
            super().keyPressEvent(event)
