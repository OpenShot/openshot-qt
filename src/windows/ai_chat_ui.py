import html
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QMessageBox, QFrame
)
from PyQt5.QtGui import QTextCursor

from classes.logger import log
from classes.ai_chat_functionality import AIChat


def _markdown_to_html(text: str) -> str:
    """Convert markdown to HTML suitable for QTextEdit. Uses theme text color for body."""
    try:
        import markdown
        body = markdown.markdown(text, extensions=["extra"])
    except Exception:
        body = html.escape(text).replace("\n", "<br/>")
    # Wrap in a div and style code blocks so they don't override theme colors
    # Use 'currentColor' so code inherits the widget's text color
    style = (
        "pre, code { background: rgba(0,0,0,0.15); padding: 4px 6px; border-radius: 0; "
        "font-family: monospace; color: inherit; } "
        "pre { margin: 8px 0; overflow-x: auto; } "
        "pre code { padding: 0; background: transparent; } "
        "p { margin: 4px 0; } "
        "ul, ol { margin: 4px 0 4px 16px; } "
        "strong { font-weight: bold; } "
    )
    return f'<div style="{style}">{body}</div>'


def _plain_to_html(text: str) -> str:
    """Escape plain text for safe HTML display."""
    return "<p>" + html.escape(text).replace("\n", "<br/>") + "</p>"


class AIChatWindow(QDockWidget):
    """Zenvi Assistant chat dock. Supports markdown in assistant replies and matches app theme."""

    def __init__(self, parent=None):
        super().__init__("Zenvi Assistant", parent)
        self.setObjectName("AIChatWindow")

        self.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )

        self.ai_chat = AIChat()
        self.is_processing = False

        main = QWidget()
        main.setObjectName("AIChatWindowContents")
        layout = QVBoxLayout()
        main.setLayout(layout)
        self.setWidget(main)

        # Preamble / context (Cursor-style: what the assistant is and quick tips)
        self.preamble_frame = QFrame()
        self.preamble_frame.setObjectName("chatPreamble")
        preamble_layout = QVBoxLayout(self.preamble_frame)
        preamble_layout.setContentsMargins(8, 8, 8, 8)
        self.preamble_label = QLabel()
        self.preamble_label.setObjectName("chatPreambleLabel")
        self.preamble_label.setWordWrap(True)
        self.preamble_label.setTextFormat(Qt.RichText)
        preamble_layout.addWidget(self.preamble_label)
        layout.addWidget(self.preamble_frame)
        self._update_preamble()

        # Model selector
        model_h = QHBoxLayout()
        model_h.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("modelCombo")
        self._populate_models()
        model_h.addWidget(self.model_combo)
        model_h.addStretch()
        layout.addLayout(model_h)

        # Chat display: rich text for markdown; colors come from theme
        self.chat_box = QTextEdit()
        self.chat_box.setObjectName("chatBox")
        self.chat_box.setReadOnly(True)
        self.chat_box.setAcceptRichText(True)
        self.chat_box.setPlaceholderText("Replies appear here. Assistant messages support **markdown** and code blocks.")
        layout.addWidget(self.chat_box)

        # Input area
        input_h = QHBoxLayout()
        self.msg_input = QTextEdit()
        self.msg_input.setObjectName("msgInput")
        self.msg_input.setMaximumHeight(80)
        self.msg_input.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for newline)")
        input_h.addWidget(self.msg_input)
        layout.addLayout(input_h)

        # Buttons
        btn_h = QHBoxLayout()
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.clicked.connect(self.send_message)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_chat)
        btn_h.addStretch()
        btn_h.addWidget(self.send_btn)
        btn_h.addWidget(self.clear_btn)
        layout.addLayout(btn_h)

        self.msg_input.keyPressEvent = self._key_press

        # Short welcome (preamble has the main context)
        self._add_system_msg("Chat started. Ask to list files, add tracks, export video, or describe your project.")

        self.setMinimumWidth(400)
        self.setMinimumHeight(450)

    def _update_preamble(self):
        """Update preamble text with current context (project name, tips)."""
        try:
            from classes.app import get_app
            app = get_app()
            project_name = "Untitled"
            profile = ""
            if hasattr(app, "project") and app.project:
                if getattr(app.project, "current_filepath", None):
                    import os
                    project_name = os.path.splitext(os.path.basename(app.project.current_filepath))[0] or "Untitled"
                profile = app.project.get("profile") or ""
            profile_line = f" · {profile}" if profile else ""
            text = (
                "<b>Zenvi Assistant</b> — Video editing assistant.<br/>"
                f"Project: <b>{project_name}</b>{profile_line}<br/>"
                "Try: <i>List my files</i> · <i>Add a track</i> · <i>Export video</i> · <i>Undo</i>"
            )
        except Exception:
            text = (
                "<b>Zenvi Assistant</b> — Video editing assistant.<br/>"
                "Try: <i>List my files</i> · <i>Add a track</i> · <i>Export video</i>"
            )
        self.preamble_label.setText(text)

    def _populate_models(self):
        """Populate model combo with all models (OpenAI, Anthropic, Ollama)."""
        try:
            from classes.ai_llm_registry import list_all_models, get_default_model_id
        except ImportError:
            self.model_combo.addItem("No AI providers loaded", "")
            return
        models = list_all_models()
        if not models:
            self.model_combo.addItem("No AI providers loaded", "")
            return
        default_id = get_default_model_id()
        for model_id, display_name in models:
            self.model_combo.addItem(display_name, model_id)
        idx = self.model_combo.findData(default_id)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _key_press(self, event):
        if event.key() == Qt.Key_Return and event.modifiers() != Qt.ShiftModifier:
            self.send_message()
        else:
            QTextEdit.keyPressEvent(self.msg_input, event)

    def send_message(self):
        if self.is_processing:
            QMessageBox.warning(self, "Wait", "Processing previous message...")
            return
        text = self.msg_input.toPlainText().strip()
        if not text:
            return
        self._add_user_msg(text)
        self.msg_input.clear()
        self.is_processing = True
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Processing...")
        try:
            model_id = self.model_combo.currentData()
            if not model_id and self.model_combo.count():
                model_id = self.model_combo.currentText()
            response = self.ai_chat.send_message(text, model_id=model_id)
            self._add_assistant_msg(response)
        except Exception as e:
            log.error("AI chat error: %s", str(e))
            self._add_system_msg("Error: %s" % str(e))
        finally:
            self.is_processing = False
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send")
            self.msg_input.setFocus()

    def clear_chat(self):
        reply = QMessageBox.question(
            self, "Clear", "Clear chat?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.ai_chat.clear_session()
            self.chat_box.clear()
            self._update_preamble()
            self._add_system_msg("Chat cleared. Ask anything about your project or editing.")

    def _add_user_msg(self, text):
        self._add_msg(text, "user", is_assistant=False, is_system=False)

    def _add_assistant_msg(self, text):
        self._add_msg(text, "assistant", is_assistant=True, is_system=False)

    def _add_system_msg(self, text):
        self._add_msg(text, "system", is_assistant=False, is_system=True)

    def _add_msg(self, text, role, is_assistant=False, is_system=False):
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)

        time_str = QDateTime.currentDateTime().toString("hh:mm:ss")
        if is_assistant:
            html_body = _markdown_to_html(text)
            role_label = f'<span style="font-weight: bold;">[{time_str}] assistant</span><br/>'
            self.chat_box.insertHtml(role_label + html_body + "<br/>")
        else:
            safe = html.escape(text).replace("\n", "<br/>")
            role_style = "color: #6366F1;" if role == "user" else ""
            role_label = f'<span style="font-weight: bold; {role_style}">[{time_str}] {role}</span><br/>'
            self.chat_box.insertHtml(role_label + "<p>" + safe + "</p><br/>")

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)
