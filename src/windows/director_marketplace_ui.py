"""
Director Marketplace UI

Dialog for browsing, creating, importing, and exporting directors.
In the split architecture, directors are stored locally as .director JSON files
and synced to the backend on demand.
"""

import os
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit, QMessageBox,
    QFileDialog, QGroupBox, QSplitter, QFormLayout, QComboBox,
    QScrollArea, QWidget, QTabWidget
)
from classes.logger import log


def _user_directors_dir():
    """Return the user directors directory, creating it if needed."""
    d = os.path.expanduser("~/.config/zenvi/directors")
    os.makedirs(d, exist_ok=True)
    return d


def _builtin_directors_dir():
    """Return the built-in directors directory (may not exist)."""
    from classes import info
    return os.path.join(info.PATH, "directors", "built_in")


def _load_director_files():
    """Load all .director JSON files from user and built-in directories."""
    directors = []
    for search_dir in (_user_directors_dir(), _builtin_directors_dir()):
        if not os.path.isdir(search_dir):
            continue
        for fname in sorted(os.listdir(search_dir)):
            if not fname.endswith(".director"):
                continue
            fpath = os.path.join(search_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["_source_path"] = fpath
                data["_is_builtin"] = search_dir == _builtin_directors_dir()
                directors.append(data)
            except Exception as e:
                log.warning(f"Failed to load {fpath}: {e}")
    return directors


class DirectorMarketplaceDialog(QDialog):
    """
    Dialog for browsing and installing directors from marketplace.

    Features:
    - Browse available directors
    - View director details
    - Create new directors
    - Import from / export to .director files
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Director Marketplace")
        self.resize(900, 600)

        self.directors = []
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

    # ---- Browse tab --------------------------------------------------------

    def _create_browse_tab(self):
        browse_widget = QWidget()
        layout = QVBoxLayout(browse_widget)

        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Director list
        left_panel = QGroupBox("Available Directors")
        left_layout = QVBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search directors...")
        self.search_box.textChanged.connect(self.filter_directors)
        left_layout.addWidget(self.search_box)

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

        btn_layout = QHBoxLayout()
        self.btn_install = QPushButton("✓ Installed")
        self.btn_install.setEnabled(False)
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

    # ---- Create tab --------------------------------------------------------

    def _create_create_tab(self):
        create_widget = QWidget()
        layout = QVBoxLayout(create_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Basic Info
        form_layout.addRow(QLabel("<h3>📋 Basic Information</h3>"))

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

        # Style placeholder
        form_layout.addRow(QLabel("<h3>🎨 Style Reference (Placeholder)</h3>"))
        media_label = QLabel("📎 Media attachment feature coming soon!\n"
                             "For now, style will be defined through the system prompt.")
        media_label.setStyleSheet("padding: 15px; background: #f0f0f0; border-radius: 5px; color: #666;")
        media_label.setWordWrap(True)
        form_layout.addRow(media_label)

        # Personality
        form_layout.addRow(QLabel("<h3>🎭 Director Personality</h3>"))

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setPlaceholderText(
            "Define the director's personality, expertise, and analysis approach...\n\n"
            "Example: You are an experienced cinematographer who focuses on visual storytelling, "
            "composition, and lighting."
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

        # AI Settings
        form_layout.addRow(QLabel("<h3>⚙️ AI Settings</h3>"))

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-haiku-4-5",
            "openai/gpt-4-turbo",
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
                color: white; padding: 12px 30px; border-radius: 6px;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5568d3, stop:1 #5e3d88);
            }
        """)
        create_btn_layout.addWidget(self.btn_create)
        layout.addLayout(create_btn_layout)

        return create_widget

    # ---- Data loading ------------------------------------------------------

    def load_directors(self):
        """Load available directors from local files."""
        try:
            self.directors = _load_director_files()
            self.director_list.clear()
            for d in self.directors:
                item = QListWidgetItem(d.get("name", d.get("id", "Unknown")))
                item.setData(Qt.UserRole, d)
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
            d = item.data(Qt.UserRole)
            matches = (
                search_text in d.get("name", "").lower()
                or search_text in d.get("description", "").lower()
                or any(search_text in t.lower() for t in d.get("tags", []))
            )
            item.setHidden(not matches)

    def on_director_selected(self, current, previous):
        """Handle director selection."""
        if not current:
            self.details_text.clear()
            self.btn_export.setEnabled(False)
            return

        d = current.data(Qt.UserRole)
        personality = d.get("personality", {})

        details = f"""<h3>{d.get('name', 'Unknown')}</h3>
<p><b>Version:</b> {d.get('version', '1.0.0')}<br>
<b>Author:</b> {d.get('author', 'Unknown')}</p>

<p>{d.get('description', '')}</p>

<p><b>Expertise Areas:</b><br>
{', '.join(personality.get('expertise_areas', d.get('expertise', [])))}</p>

<p><b>Analysis Focus:</b><br>
{', '.join(personality.get('analysis_focus', d.get('focus', [])))}</p>

<p><b>Critique Style:</b> {personality.get('critique_style', 'constructive')}</p>

<p><b>Tags:</b> {', '.join(d.get('tags', []))}</p>
"""
        self.details_text.setHtml(details)
        self.btn_export.setEnabled(True)

    # ---- Export / Import ---------------------------------------------------

    def export_director(self):
        """Export selected director to file."""
        current = self.director_list.currentItem()
        if not current:
            return

        d = current.data(Qt.UserRole)
        did = d.get("id", "director")

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Director", f"{did}.director", "Director Files (*.director)"
        )
        if not filename:
            return

        try:
            # Write a clean copy (strip internal keys)
            export = {k: v for k, v in d.items() if not k.startswith("_")}
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(export, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Success", f"Director exported to:\n{filename}")
            log.info(f"Exported director {did} to {filename}")
        except Exception as e:
            log.error(f"Export failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Export failed: {e}")

    def import_from_file(self):
        """Import director from .director file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Director", "", "Director Files (*.director)"
        )
        if not filename:
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            did = data.get("id")
            if not did:
                QMessageBox.warning(self, "Error", "Director file missing 'id' field.")
                return

            dest = os.path.join(_user_directors_dir(), f"{did}.director")
            if os.path.exists(dest):
                reply = QMessageBox.question(
                    self, "Director Exists",
                    f"A director with ID '{did}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "Success", "Director imported successfully!")
            log.info(f"Imported director from {filename}")
            self.load_directors()

        except Exception as e:
            log.error(f"Import failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Import failed: {e}")

    # ---- Create new director -----------------------------------------------

    def create_director(self):
        """Create a new director from form inputs."""
        try:
            name = self.name_input.text().strip()
            description = self.description_input.toPlainText().strip()
            system_prompt = self.system_prompt_input.toPlainText().strip()
            expertise = self.expertise_input.text().strip()
            focus = self.focus_input.text().strip()

            # Validate required fields
            for field_name, value in [("Director name", name), ("Description", description),
                                       ("System prompt", system_prompt), ("Expertise areas", expertise),
                                       ("Analysis focus", focus)]:
                if not value:
                    QMessageBox.warning(self, "Validation Error", f"{field_name} is required.")
                    return

            # Generate ID
            director_id = name.lower().replace(" ", "_").replace("-", "_")
            director_id = "".join(c for c in director_id if c.isalnum() or c == "_")

            tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
            expertise_areas = [e.strip() for e in expertise.split(",") if e.strip()]
            analysis_focus = [f.strip() for f in focus.split(",") if f.strip()]

            from datetime import datetime
            director_data = {
                "id": director_id,
                "name": name,
                "version": "1.0.0",
                "author": self.author_input.text().strip() or "User",
                "description": description,
                "tags": tags or ["custom"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "personality": {
                    "system_prompt": system_prompt,
                    "analysis_focus": analysis_focus,
                    "critique_style": self.critique_style_combo.currentText(),
                    "expertise_areas": expertise_areas,
                },
                "settings": {
                    "model": self.model_combo.currentText(),
                    "temperature": float(self.temperature_combo.currentText()),
                },
            }

            filepath = os.path.join(_user_directors_dir(), f"{director_id}.director")

            if os.path.exists(filepath):
                reply = QMessageBox.question(
                    self, "Director Exists",
                    f"A director with ID '{director_id}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(director_data, f, indent=2, ensure_ascii=False)

            log.info(f"Created new director: {director_id} at {filepath}")

            QMessageBox.information(
                self, "Success! 🎉",
                f"Director '{name}' has been created successfully!\n\n"
                "The director is now available in the Directors panel.",
            )

            # Clear form
            self.name_input.clear()
            self.description_input.clear()
            self.system_prompt_input.clear()
            self.expertise_input.clear()
            self.focus_input.clear()
            self.tags_input.clear()

            self.load_directors()
            self.tab_widget.setCurrentIndex(0)

        except Exception as e:
            log.error(f"Failed to create director: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to create director: {e}")


def show_marketplace_dialog(parent=None):
    """Show the marketplace dialog."""
    dialog = DirectorMarketplaceDialog(parent)
    dialog.exec_()
