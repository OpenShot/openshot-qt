"""
 @file
 @brief AI Media Management panel for tags, collections, and analysis
 @author Zenvi Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import asyncio
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QProgressBar,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QLineEdit
)
from PyQt5.QtGui import QIcon

from classes.logger import log
from classes.app import get_app
from classes.tag_manager import get_tag_manager
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
        
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
    
    def _create_tags_tab(self):
        """Create the tags browser tab"""
        tags_widget = QWidget()
        layout = QVBoxLayout()
        tags_widget.setLayout(layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Tags:"))
        self.tag_search = QLineEdit()
        self.tag_search.setPlaceholderText("Filter tags...")
        self.tag_search.textChanged.connect(self.filter_tags)
        search_layout.addWidget(self.tag_search)
        layout.addLayout(search_layout)
        
        # Tags tree
        self.tags_tree = QTreeWidget()
        self.tags_tree.setHeaderLabels(["Tag", "Count"])
        self.tags_tree.itemClicked.connect(self.on_tag_clicked)
        layout.addWidget(self.tags_tree)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Tags")
        refresh_btn.clicked.connect(self.refresh_tags)
        layout.addWidget(refresh_btn)
        
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
        """Refresh the tags tree"""
        self.tags_tree.clear()
        
        try:
            tag_manager = get_tag_manager()
            all_tags = tag_manager.get_all_tags()
            
            # Create category items
            for category, tags in all_tags.items():
                if not tags:
                    continue
                
                category_item = QTreeWidgetItem(self.tags_tree)
                category_item.setText(0, category.capitalize())
                category_item.setText(1, str(len(tags)))
                
                # Add tag items
                for tag in tags:
                    tag_item = QTreeWidgetItem(category_item)
                    tag_item.setText(0, tag)
                    
                    # Get count
                    files = tag_manager.get_files_with_tag(tag, category[:-1] if category.endswith('s') else category)
                    tag_item.setText(1, str(len(files)))
                    tag_item.setData(0, Qt.UserRole, {'category': category, 'tag': tag})
                
                category_item.setExpanded(True)
            
        except Exception as e:
            log.error(f"Failed to refresh tags: {e}")
    
    def filter_tags(self, text):
        """Filter tags by search text"""
        # Simple filter - hide items that don't match
        iterator = QTreeWidgetItemIterator(self.tags_tree)
        while iterator.value():
            item = iterator.value()
            if item.parent():  # Only filter tag items, not categories
                tag_text = item.text(0).lower()
                item.setHidden(text.lower() not in tag_text if text else False)
            iterator += 1
    
    def on_tag_clicked(self, item, column):
        """Handle tag click - filter files panel"""
        if not item.parent():  # Category item
            return
        
        data = item.data(0, Qt.UserRole)
        if data:
            log.info(f"Tag clicked: {data['category']} - {data['tag']}")
            # TODO: Filter files panel by this tag
    
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
