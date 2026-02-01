import os
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QMessageBox
)
from PyQt5.QtGui import QFont, QColor, QTextCursor

from classes.logger import log
from classes.ai_chat_functionality import AIChat


class AIChatWindow(QDockWidget):
    # Main AI Chat dock widget
    
    def __init__(self, parent=None):
        super().__init__("AI Assistant", parent)
        self.setObjectName("AIChatWindow")
        
        # Make it closable so it appears in View menu
        self.setFeatures(
            QDockWidget.DockWidgetClosable |
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )
        
        self.ai_chat = AIChat()
        self.is_processing = False

        # Main widget
        main = QWidget()
        layout = QVBoxLayout()
        main.setLayout(layout)
        self.setWidget(main)

        # Model selector (populated from LLM registry)
        model_h = QHBoxLayout()
        model_h.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self._populate_models()
        model_h.addWidget(self.model_combo)
        model_h.addStretch()
        layout.addLayout(model_h)
        
        # Chat display
        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #404040;")
        layout.addWidget(self.chat_box)
        
        # Input area
        input_h = QHBoxLayout()
        self.msg_input = QTextEdit()
        self.msg_input.setMaximumHeight(60)
        self.msg_input.setPlaceholderText("Type message... (Enter to send, Shift+Enter for newline)")
        self.msg_input.setStyleSheet("background-color: #3b3b3b; color: #e0e0e0; border: 1px solid #404040;")
        input_h.addWidget(self.msg_input)
        layout.addLayout(input_h)
        
        # Buttons
        btn_h = QHBoxLayout()
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_chat)
        btn_h.addStretch()
        btn_h.addWidget(self.send_btn)
        btn_h.addWidget(self.clear_btn)
        layout.addLayout(btn_h)
        
        # Keyboard shortcut
        self.msg_input.keyPressEvent = self._key_press
        
        # Welcome message
        self._add_system_msg("Welcome to AI Assistant!")
        
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)

    def _populate_models(self):
        """Populate model combo with all models (OpenAI, Anthropic, Ollama); API key checked when sending."""
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
        # Select default if present in list
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
            log.error(f"AI chat error: {str(e)}")
            self._add_system_msg(f"Error: {str(e)}")
        finally:
            self.is_processing = False
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send")
            self.msg_input.setFocus()
    
    def clear_chat(self):
        reply = QMessageBox.question(self, "Clear", "Clear chat?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.ai_chat.clear_session()
            self.chat_box.clear()
            self._add_system_msg("Chat cleared.")
    
    def _add_user_msg(self, text):
        self._add_msg(text, "user", "#4fc3f7")
    
    def _add_assistant_msg(self, text):
        self._add_msg(text, "assistant", "#81c784")
    
    def _add_system_msg(self, text):
        self._add_msg(text, "system", "#ffb74d")
    
    def _add_msg(self, text, role, color):
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)
        
        time = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.chat_box.setTextColor(QColor(color))
        self.chat_box.insertPlainText(f"[{time}] {role}: ")
        self.chat_box.setTextColor(QColor("#e0e0e0"))
        self.chat_box.insertPlainText(text + "\n\n")
        
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)
