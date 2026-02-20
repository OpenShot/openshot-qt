"""
 @file
 @brief AI Media Management panel for tags, collections, and analysis
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import asyncio
import os
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QProgressBar,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QLineEdit
)
from PyQt5.QtGui import QIcon

from classes.logger import log
from classes.app import get_app
from classes.ai_metadata_utils import get_scene_descriptions_formatted
from classes.media_analyzer import get_analysis_queue


class AIMediaPanel(QDockWidget):
    """Dock widget for AI media management features"""
    
    analysisComplete = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("AI Media Manager", parent)
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
        
        # Create tab pages
        self._create_tags_tab()
        self._create_analysis_tab()
        self._create_collections_tab()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_analysis_status)
        self.update_timer.start(2000)  # Update every 2 seconds
        
        # Track selection changes for clip tag display
        self._wire_selection_signals()
        self.update_selected_clip_tags()

        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
    
    def _create_tags_tab(self):
        """Create the tags browser tab"""
        tags_widget = QWidget()
        layout = QVBoxLayout()
        tags_widget.setLayout(layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Scenes:"))
        self.tag_search = QLineEdit()
        self.tag_search.setPlaceholderText("Filter scene descriptions...")
        self.tag_search.textChanged.connect(self.filter_tags)
        search_layout.addWidget(self.tag_search)
        layout.addLayout(search_layout)
        
        # Tags tree
        self.tags_tree = QTreeWidget()
        self.tags_tree.setHeaderLabels(["Time", "Description"])
        self.tags_tree.setUniformRowHeights(True)
        self.tags_tree.setWordWrap(True)
        self.tags_tree.setRootIsDecorated(False)
        layout.addWidget(self.tags_tree)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Scenes")
        refresh_btn.clicked.connect(self.refresh_tags)
        layout.addWidget(refresh_btn)

        # Selected clip scenes
        self.selected_clip_group = QGroupBox("Selected Clip Scenes")
        selected_layout = QVBoxLayout()
        self.selected_clip_group.setLayout(selected_layout)
        self.selected_clip_label = QLabel("Select a clip to view scene descriptions")
        self.selected_tags_list = QListWidget()
        selected_layout.addWidget(self.selected_clip_label)
        selected_layout.addWidget(self.selected_tags_list)
        layout.addWidget(self.selected_clip_group)
        
        self.tabs.addTab(tags_widget, "Tags")
        
        # Load initial tags
        self.refresh_tags()
    
    def _create_analysis_tab(self):
        """Create the analysis queue tab"""
        analysis_widget = QWidget()
        layout = QVBoxLayout()
        analysis_widget.setLayout(layout)
        
        # Status group
        status_group = QGroupBox("Analysis Status")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        
        self.status_label = QLabel("Queue: 0 pending")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)
        
        self.current_file_label = QLabel("No file processing")
        self.current_file_label.setWordWrap(True)
        status_layout.addWidget(self.current_file_label)
        
        layout.addWidget(status_group)
        
        # Queue list
        queue_group = QGroupBox("Analysis Queue")
        queue_layout = QVBoxLayout()
        queue_group.setLayout(queue_layout)
        
        self.queue_list = QListWidget()
        queue_layout.addWidget(self.queue_list)
        
        layout.addWidget(queue_group)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Analysis")
        self.start_btn.clicked.connect(self.start_analysis)
        btn_layout.addWidget(self.start_btn)
        
        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.clicked.connect(self.clear_queue)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(analysis_widget, "Analysis")
    
    def _create_collections_tab(self):
        """Create the smart collections tab"""
        collections_widget = QWidget()
        layout = QVBoxLayout()
        collections_widget.setLayout(layout)
        
        # Collections list
        self.collections_list = QListWidget()
        layout.addWidget(self.collections_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        new_btn = QPushButton("New Collection")
        new_btn.clicked.connect(self.create_collection)
        btn_layout.addWidget(new_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_collection)
        btn_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_collection)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(collections_widget, "Collections")
        
        # Load collections
        self.refresh_collections()
    
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
        """Update analysis queue status"""
        try:
            queue = get_analysis_queue()
            status = queue.get_queue_status()
            
            # Update status label
            self.status_label.setText(
                f"Queue: {status['pending']} pending, {status['processing']} processing"
            )
            
            # Update progress bar
            total = status['total']
            if total > 0:
                completed = total - status['pending'] - status['processing']
                progress = int((completed / total) * 100)
                self.progress_bar.setValue(progress)
            else:
                self.progress_bar.setValue(0)
            
            # Update current file
            if status['current_file']:
                import os
                filename = os.path.basename(status['current_file'])
                self.current_file_label.setText(f"Analyzing: {filename}")
            else:
                self.current_file_label.setText("No file processing")
            
            # Update queue list
            self.queue_list.clear()
            for item in queue.queue:
                import os
                filename = os.path.basename(item['file_path'])
                status_text = item['status'].upper()
                list_item = QListWidgetItem(f"{filename} - {status_text}")
                self.queue_list.addItem(list_item)
            
        except Exception as e:
            log.error(f"Failed to update analysis status: {e}")
    
    def start_analysis(self):
        """Start processing the analysis queue"""
        try:
            queue = get_analysis_queue()
            
            # Run async processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(queue.process_queue())
            loop.close()
            
            self.analysisComplete.emit()
            self.refresh_tags()
            
        except Exception as e:
            log.error(f"Failed to start analysis: {e}")
    
    def clear_queue(self):
        """Clear the analysis queue"""
        try:
            queue = get_analysis_queue()
            queue.clear_queue()
            self.update_analysis_status()
        except Exception as e:
            log.error(f"Failed to clear queue: {e}")
    
    def refresh_collections(self):
        """Refresh collections list"""
        self.collections_list.clear()
        # TODO: Load collections from project data
    
    def create_collection(self):
        """Create new smart collection"""
        log.info("Create collection clicked")
        # TODO: Open collection editor dialog
    
    def edit_collection(self):
        """Edit selected collection"""
        log.info("Edit collection clicked")
        # TODO: Open collection editor dialog
    
    def delete_collection(self):
        """Delete selected collection"""
        log.info("Delete collection clicked")
        # TODO: Delete collection
