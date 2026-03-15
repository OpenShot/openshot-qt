"""
 @file
 @brief AI Media Management panel for tags, collections, and analysis
 @author Zenvi Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import os
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTabWidget,
    QListWidget, QPushButton, QLabel, QFrame,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QLineEdit,
    QSizePolicy,
)
from PyQt5.QtGui import QFont

from classes.logger import log
from classes.app import get_app
from classes.ai_metadata_utils import get_scene_descriptions_formatted
from classes.api_client import get_backend_client


def _section_header(text: str) -> QLabel:
    """Return a flat section-header label that replaces QGroupBox titles."""
    lbl = QLabel(text.upper())
    lbl.setObjectName("sectionHeader")
    font = lbl.font()
    font.setPointSizeF(8.5)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
    lbl.setFont(font)
    lbl.setStyleSheet(
        "QLabel#sectionHeader {"
        "  color: #737373;"
        "  padding: 6px 0 2px 0;"
        "  border: none;"
        "}"
    )
    return lbl


class AIMediaPanel(QDockWidget):
    """Dock widget for AI media management features"""

    analysisComplete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Scene Descriptions", parent)
        self.setObjectName("AIMediaPanel")
        
        # Make it closable and movable
        self.setFeatures(
            QDockWidget.DockWidgetClosable |
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )
        
        # Main widget
        main = QWidget()
        layout = QVBoxLayout()
        main.setLayout(layout)
        self.setWidget(main)
        
        # Create tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tab pages (Tags only – Analysis/Collections are backend-internal)
        self._create_tags_tab()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_analysis_status)
        # Timer starts on-demand; only runs while analysis is active
        
        # Track selection changes for clip tag display
        self._wire_selection_signals()
        self.update_selected_clip_tags()

        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
    
    def _create_tags_tab(self):
        """Create the tags browser tab"""
        tags_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        tags_widget.setLayout(layout)

        # Search box
        self.tag_search = QLineEdit()
        self.tag_search.setPlaceholderText("Search scene descriptions...")
        self.tag_search.textChanged.connect(self.filter_tags)
        layout.addWidget(self.tag_search)

        # Scene list tree (takes most of the space)
        self.tags_tree = QTreeWidget()
        self.tags_tree.setHeaderLabels(["Time", "Description"])
        self.tags_tree.setColumnWidth(0, 52)
        self.tags_tree.setUniformRowHeights(True)
        self.tags_tree.setWordWrap(True)
        self.tags_tree.setRootIsDecorated(False)
        self.tags_tree.setAlternatingRowColors(False)
        layout.addWidget(self.tags_tree, stretch=3)

        # Subtle separator between the scene list and the selected-clip section
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setStyleSheet("background: rgba(255,255,255,0.07); max-height: 1px; border: none; margin: 4px 0;")
        layout.addWidget(sep)

        # Selected clip section
        layout.addWidget(_section_header("Selected Clip"))
        self.selected_clip_label = QLabel("Select a clip to view scene descriptions")
        self.selected_clip_label.setWordWrap(True)
        self.selected_clip_label.setStyleSheet("color: #8a8a8a; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self.selected_clip_label)
        self.selected_tags_list = QListWidget()
        self.selected_tags_list.setMaximumHeight(110)
        layout.addWidget(self.selected_tags_list, stretch=1)

        # Refresh button – minimal, full-width
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        refresh_btn.setObjectName("tagsRefreshBtn")
        refresh_btn.clicked.connect(self.refresh_tags)
        layout.addWidget(refresh_btn)

        # Keep a reference for backward-compatible code that accesses .selected_clip_group
        self.selected_clip_group = None

        # No tab bar needed when there is only one tab – hide it
        self.tabs.tabBar().setVisible(False)
        self.tabs.addTab(tags_widget, "Tags")

        # Load initial tags
        self.refresh_tags()
    
    def refresh_tags(self):
        """Refresh the scenes tree (based on current selection)."""
        self.update_selected_clip_tags()
    
    def filter_tags(self, text):
        """Filter scene descriptions by search text."""
        iterator = QTreeWidgetItemIterator(self.tags_tree)
        while iterator.value():
            item = iterator.value()
            # Only filter leaf rows (we disable decoration, so this is always a row)
            desc_text = (item.text(1) or "").lower()
            time_text = (item.text(0) or "").lower()
            haystack = f"{time_text} {desc_text}".strip()
            item.setHidden(text.lower() not in haystack if text else False)
            iterator += 1

    def _wire_selection_signals(self):
        """Listen for file selection changes to show per-clip tags."""
        try:
            window = get_app().window
            files_model = getattr(window, "files_model", None)
            if files_model and files_model.selection_model:
                files_model.selection_model.selectionChanged.connect(self.update_selected_clip_tags)
            window.FileUpdated.connect(lambda _fid: self.update_selected_clip_tags())
            # Timeline selection (clips/transitions/effects)
            window.SelectionChanged.connect(self.update_selected_clip_tags)
        except Exception as e:
            log.warning(f"Failed to connect selection signals for tags: {e}")

    def update_selected_clip_tags(self, *args, **kwargs):
        """Update the selected-clip scene list when selection or metadata changes."""
        try:
            window = get_app().window
            files_model = getattr(window, "files_model", None)

            # Prefer timeline clip selection, fallback to current file selection
            timeline_clip = None
            try:
                from classes.query import Clip, File
                selected_clip_ids = getattr(window, "selected_clips", []) or []
                if selected_clip_ids:
                    timeline_clip = Clip.get(id=selected_clip_ids[0])
            except Exception:
                timeline_clip = None

            file_obj = files_model.current_file() if files_model else None
            self.selected_tags_list.clear()
            self.tags_tree.clear()

            if not timeline_clip and not file_obj:
                self.selected_clip_label.setText("Select a clip to view scene descriptions")
                return

            ai_meta = {}
            name = ""

            if timeline_clip and isinstance(getattr(timeline_clip, "data", None), dict):
                clip_data = timeline_clip.data
                name = clip_data.get("title") or clip_data.get("name") or "Timeline Clip"
                # First, prefer per-clip metadata (set during slice)
                ai_meta = clip_data.get("ai_metadata") if isinstance(clip_data.get("ai_metadata"), dict) else {}

                # Fallback to source File's metadata
                if not ai_meta.get("analyzed"):
                    try:
                        file_id = clip_data.get("file_id")
                        source_file = File.get(id=str(file_id)) if file_id else None
                        if source_file:
                            name = name or source_file.data.get("name") or os.path.basename(source_file.data.get("path", "Clip"))
                            candidate = source_file.data.get("ai_metadata")
                            if isinstance(candidate, dict):
                                ai_meta = candidate
                    except Exception:
                        pass

            if not name and file_obj:
                name = file_obj.data.get('name') or os.path.basename(file_obj.data.get('path', 'Clip'))

            if (not ai_meta or not ai_meta.get("analyzed")) and file_obj:
                candidate = file_obj.get_ai_metadata()
                ai_meta = candidate if isinstance(candidate, dict) else {}

            if not ai_meta.get('analyzed'):
                self.selected_clip_label.setText(f"{name} (processing scene descriptions...)")
                self.selected_tags_list.addItem("Tagging in progress...")
                return

            self.selected_clip_label.setText(name)
            scenes = ai_meta.get("scene_descriptions", [])
            if not isinstance(scenes, list) or not scenes:
                self.selected_tags_list.addItem("No scene descriptions found")
                return

            # Populate list widget with formatted strings
            formatted = get_scene_descriptions_formatted(ai_meta)
            for line in formatted:
                self.selected_tags_list.addItem(line)

            # Populate tree widget with (Time, Description)
            for scene in scenes:
                if not isinstance(scene, dict):
                    continue
                time_sec = scene.get("time", 0)
                desc = scene.get("description", "")
                try:
                    minutes = int(float(time_sec) // 60)
                    seconds = int(float(time_sec) % 60)
                except Exception:
                    minutes, seconds = 0, 0
                time_str = f"{minutes}:{seconds:02d}"
                row = QTreeWidgetItem(self.tags_tree)
                row.setText(0, time_str)
                row.setText(1, str(desc))

        except Exception as e:
            log.error(f"Failed to update selected clip tags: {e}")

    def on_tag_clicked(self, item, column):
        """Deprecated: tag click handler kept for backward compatibility."""
        return
    
    def update_analysis_status(self):
        """Update analysis status – no-op now that the analysis tab is hidden."""
        pass
