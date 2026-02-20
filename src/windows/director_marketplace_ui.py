"""
Director Marketplace UI

Dialog for browsing, downloading, and installing directors.
"""

import os
import json
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit, QMessageBox,
    QFileDialog, QGroupBox, QSplitter, QFormLayout, QComboBox, QCheckBox,
    QScrollArea, QWidget, QTabWidget
)
from classes.logger import log


class DirectorMarketplaceDialog(QDialog):
    """
    Dialog for browsing and installing directors from marketplace.

    Features:
    - Browse available directors
    - View director details
    - Install from file
    - Export directors for sharing
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Director Marketplace")
        self.resize(900, 600)

        self.setup_ui()
        self.load_directors()

    def setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout()

        # Header
        header = QLabel("<h2>🎬 Director Marketplace</h2>")
        layout.addWidget(header)

        # Tab widget for Browse/Create
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self._create_browse_tab(), "📚 Browse Directors")
        self.tab_widget.addTab(self._create_create_tab(), "➕ Create New Director")
        layout.addWidget(self.tab_widget)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_close)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def _create_browse_tab(self):
        """Create the browse directors tab."""
        browse_widget = QWidget()
        layout = QVBoxLayout(browse_widget)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Director list
        left_panel = QGroupBox("Available Directors")
        left_layout = QVBoxLayout()

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search directors...")
        self.search_box.textChanged.connect(self.filter_directors)
        left_layout.addWidget(self.search_box)

        # Director list
        self.director_list = QListWidget()
        self.director_list.currentItemChanged.connect(self.on_director_selected)
        left_layout.addWidget(self.director_list)

        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # Right panel: Director details
        right_panel = QGroupBox("Director Details")
        right_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Select a director to view details")
        right_layout.addWidget(self.details_text)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_install = QPushButton("✓ Installed")
        self.btn_install.setEnabled(False)
        self.btn_install.clicked.connect(self.install_director)
        btn_layout.addWidget(self.btn_install)

        self.btn_export = QPushButton("📤 Export")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_director)
        btn_layout.addWidget(self.btn_export)

        right_layout.addLayout(btn_layout)
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        # Import button
        import_layout = QHBoxLayout()
        self.btn_import = QPushButton("📥 Import from File...")
        self.btn_import.clicked.connect(self.import_from_file)
        import_layout.addWidget(self.btn_import)
        import_layout.addStretch()
        layout.addLayout(import_layout)

        return browse_widget

    def _create_create_tab(self):
        """Create the 'Create New Director' tab."""
        create_widget = QWidget()
        layout = QVBoxLayout(create_widget)

        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Basic Info Section
        basic_label = QLabel("<h3>📋 Basic Information</h3>")
        form_layout.addRow(basic_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Documentary Director")
        form_layout.addRow("Director Name*:", self.name_input)

        self.author_input = QLineEdit()
        self.author_input.setPlaceholderText("Your name")
        self.author_input.setText("User")
        form_layout.addRow("Author:", self.author_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Brief description of what this director focuses on...")
        self.description_input.setMaximumHeight(80)
        form_layout.addRow("Description*:", self.description_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("e.g., documentary, narrative, cinematic")
        form_layout.addRow("Tags (comma-separated):", self.tags_input)

        # Style Media Section
        media_label = QLabel("<h3>🎨 Style Reference (Placeholder)</h3>")
        form_layout.addRow(media_label)

        media_placeholder = QLabel("📎 Media attachment feature coming soon!\nFor now, style will be defined through the system prompt.")
        media_placeholder.setStyleSheet("padding: 15px; background: #f0f0f0; border-radius: 5px; color: #666;")
        media_placeholder.setWordWrap(True)
        form_layout.addRow(media_placeholder)

        # Personality Section
        personality_label = QLabel("<h3>🎭 Director Personality</h3>")
        form_layout.addRow(personality_label)

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setPlaceholderText(
            "Define the director's personality, expertise, and analysis approach...\n\n"
            "Example: You are an experienced cinematographer who focuses on visual storytelling, "
            "composition, and lighting. You provide constructive feedback to help creators improve their craft."
        )
        self.system_prompt_input.setMinimumHeight(150)
        form_layout.addRow("System Prompt*:", self.system_prompt_input)

        self.expertise_input = QLineEdit()
        self.expertise_input.setPlaceholderText("e.g., cinematography, lighting, composition")
        form_layout.addRow("Expertise Areas*:", self.expertise_input)

        self.focus_input = QLineEdit()
        self.focus_input.setPlaceholderText("e.g., composition, lighting, pacing")
        form_layout.addRow("Analysis Focus*:", self.focus_input)

        self.critique_style_combo = QComboBox()
        self.critique_style_combo.addItems(["constructive", "direct", "encouraging", "detailed"])
        form_layout.addRow("Critique Style:", self.critique_style_combo)

        # AI Settings Section
        settings_label = QLabel("<h3>⚙️ AI Settings</h3>")
        form_layout.addRow(settings_label)

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-opus-4",
            "openai/gpt-4-turbo"
        ])
        form_layout.addRow("AI Model:", self.model_combo)

        self.temperature_combo = QComboBox()
        self.temperature_combo.addItems(["0.5", "0.6", "0.7", "0.8", "0.9"])
        self.temperature_combo.setCurrentText("0.7")
        form_layout.addRow("Temperature:", self.temperature_combo)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # Create button
        create_btn_layout = QHBoxLayout()
        create_btn_layout.addStretch()
        self.btn_create = QPushButton("✨ Create Director")
        self.btn_create.clicked.connect(self.create_director)
        self.btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                padding: 12px 30px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5568d3, stop:1 #5e3d88);
            }
        """)
        create_btn_layout.addWidget(self.btn_create)
        layout.addLayout(create_btn_layout)

        return create_widget

    def load_directors(self):
        """Load available directors."""
        try:
            from classes.ai_directors.director_loader import get_director_loader

            loader = get_director_loader()
            self.directors = loader.list_available_directors()

            self.director_list.clear()
            for director in self.directors:
                item = QListWidgetItem(f"{director.name}")
                item.setData(Qt.UserRole, director)
                self.director_list.addItem(item)

            log.info(f"Loaded {len(self.directors)} directors into marketplace")

        except Exception as e:
            log.error(f"Failed to load directors: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to load directors: {e}")

    def filter_directors(self):
        """Filter directors based on search text."""
        search_text = self.search_box.text().lower()

        for i in range(self.director_list.count()):
            item = self.director_list.item(i)
            director = item.data(Qt.UserRole)

            # Search in name, description, tags
            matches = (
                search_text in director.name.lower() or
                search_text in director.metadata.description.lower() or
                any(search_text in tag.lower() for tag in director.metadata.tags)
            )

            item.setHidden(not matches)

    def on_director_selected(self, current, previous):
        """Handle director selection."""
        if not current:
            self.details_text.clear()
            self.btn_install.setEnabled(False)
            self.btn_export.setEnabled(False)
            return

        director = current.data(Qt.UserRole)

        # Display details
        details = f"""<h3>{director.name}</h3>
<p><b>Version:</b> {director.metadata.version}<br>
<b>Author:</b> {director.metadata.author}</p>

<p>{director.metadata.description}</p>

<p><b>Expertise Areas:</b><br>
{', '.join(director.personality.expertise_areas)}</p>

<p><b>Analysis Focus:</b><br>
{', '.join(director.personality.analysis_focus)}</p>

<p><b>Critique Style:</b> {director.personality.critique_style}</p>

<p><b>Tags:</b> {', '.join(director.metadata.tags)}</p>
"""

        self.details_text.setHtml(details)
        self.btn_install.setEnabled(False)  # Already installed (from list)
        self.btn_export.setEnabled(True)

    def install_director(self):
        """Install selected director (not yet implemented)."""
        QMessageBox.information(
            self,
            "Not Implemented",
            "Installing directors from remote marketplace is not yet implemented.\n\n"
            "Use 'Import from File' to install custom directors."
        )

    def export_director(self):
        """Export selected director to file."""
        current = self.director_list.currentItem()
        if not current:
            return

        director = current.data(Qt.UserRole)

        # Ask for save location
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Director",
            f"{director.id}.director",
            "Director Files (*.director)"
        )

        if not filename:
            return

        try:
            from classes.ai_directors.director_marketplace import get_marketplace

            marketplace = get_marketplace()
            success = marketplace.export_director(director.id, filename)

            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Director exported to:\n{filename}"
                )
                log.info(f"Exported director {director.id} to {filename}")
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to export director. Check logs for details."
                )

        except Exception as e:
            log.error(f"Export failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Export failed: {e}")

    def import_from_file(self):
        """Import director from .director file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Director",
            "",
            "Director Files (*.director)"
        )

        if not filename:
            return

        try:
            from classes.ai_directors.director_marketplace import get_marketplace

            marketplace = get_marketplace()
            success = marketplace.install_director_from_file(filename)

            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Director imported successfully!\n\nReload the directors panel to see the new director."
                )
                log.info(f"Imported director from {filename}")

                # Reload directors list
                self.load_directors()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to import director. Check logs for details."
                )

        except Exception as e:
            log.error(f"Import failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Import failed: {e}")

    def create_director(self):
        """Create a new director from form inputs."""
        try:
            # Validate required fields
            name = self.name_input.text().strip()
            description = self.description_input.toPlainText().strip()
            system_prompt = self.system_prompt_input.toPlainText().strip()
            expertise = self.expertise_input.text().strip()
            focus = self.focus_input.text().strip()

            if not name:
                QMessageBox.warning(self, "Validation Error", "Director name is required.")
                return
            if not description:
                QMessageBox.warning(self, "Validation Error", "Description is required.")
                return
            if not system_prompt:
                QMessageBox.warning(self, "Validation Error", "System prompt is required.")
                return
            if not expertise:
                QMessageBox.warning(self, "Validation Error", "Expertise areas are required.")
                return
            if not focus:
                QMessageBox.warning(self, "Validation Error", "Analysis focus is required.")
                return

            # Generate director ID from name
            director_id = name.lower().replace(" ", "_").replace("-", "_")
            director_id = ''.join(c for c in director_id if c.isalnum() or c == '_')

            # Parse comma-separated lists
            tags = [tag.strip() for tag in self.tags_input.text().split(",") if tag.strip()]
            expertise_areas = [e.strip() for e in expertise.split(",") if e.strip()]
            analysis_focus = [f.strip() for f in focus.split(",") if f.strip()]

            # Create director data structure
            from datetime import datetime
            director_data = {
                "id": director_id,
                "name": name,
                "version": "1.0.0",
                "author": self.author_input.text().strip() or "User",
                "description": description,
                "tags": tags if tags else ["custom"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "personality": {
                    "system_prompt": system_prompt,
                    "analysis_focus": analysis_focus,
                    "critique_style": self.critique_style_combo.currentText(),
                    "expertise_areas": expertise_areas
                },
                "settings": {
                    "model": self.model_combo.currentText(),
                    "temperature": float(self.temperature_combo.currentText())
                }
            }

            # Save to user directory
            import os
            user_dir = os.path.expanduser("~/.config/flowcut/directors")
            os.makedirs(user_dir, exist_ok=True)

            filepath = os.path.join(user_dir, f"{director_id}.director")

            # Check if already exists
            if os.path.exists(filepath):
                reply = QMessageBox.question(
                    self,
                    "Director Exists",
                    f"A director with ID '{director_id}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(director_data, f, indent=2, ensure_ascii=False)

            log.info(f"Created new director: {director_id} at {filepath}")

            # Show success message
            QMessageBox.information(
                self,
                "Success! 🎉",
                f"Director '{name}' has been created successfully!\n\n"
                f"The director is now available in the marketplace and can be selected in the Directors panel."
            )

            # Clear form
            self.name_input.clear()
            self.description_input.clear()
            self.system_prompt_input.clear()
            self.expertise_input.clear()
            self.focus_input.clear()
            self.tags_input.clear()

            # Reload directors list in browse tab
            self.load_directors()

            # Switch to browse tab
            self.tab_widget.setCurrentIndex(0)

        except Exception as e:
            log.error(f"Failed to create director: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to create director: {e}")


def show_marketplace_dialog(parent=None):
    """Show the marketplace dialog."""
    dialog = DirectorMarketplaceDialog(parent)
    dialog.exec_()
