import html
import json
import threading
import time

from PyQt5.QtCore import (
    Qt, QDateTime, QPropertyAnimation, QEasingCurve,
    QObject, QThread, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG,
)
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QMessageBox, QFrame,
    QGraphicsOpacityEffect,
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


def _debug_log(location, message, data, hypothesis_id):
    # #region agent log
    try:
        import os
        _path = "/home/vboxuser/Projects/Zenvi/.cursor/debug.log"
        os.makedirs(os.path.dirname(_path), exist_ok=True)
        with open(_path, "a") as f:
            f.write(json.dumps({"location": location, "message": message, "data": data, "hypothesisId": hypothesis_id, "timestamp": time.time()}) + "\n")
    except Exception:
        pass
    # #endregion


REQUEST_TIMEOUT_SECONDS = 120


class AIChatWorker(QObject):
    """Runs AIChat.send_message() in a background thread. Emits response_ready or error_occurred."""

    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_chat = AIChat()

    @pyqtSlot(str, str)
    def run_request(self, text: str, model_id: str):
        # #region agent log
        _debug_log("ai_chat_ui.py:run_request", "worker run_request entered", {"text_len": len(text), "model_id": model_id or "(none)"}, "H1")
        # #endregion
        result_holder = [None]
        exception_holder = [None]

        def run():
            try:
                # #region agent log
                _debug_log("ai_chat_ui.py:run_request:run()", "sub_thread calling send_message", {}, "H2")
                # #endregion
                result_holder[0] = self.ai_chat.send_message(text, model_id=model_id or None)
                # #region agent log
                _debug_log("ai_chat_ui.py:run_request:run()", "send_message returned", {"result_len": len(result_holder[0]) if result_holder[0] else 0}, "H2")
                # #endregion
            except Exception as e:
                exception_holder[0] = e
                # #region agent log
                _debug_log("ai_chat_ui.py:run_request:run()", "send_message raised", {"error": str(e)}, "H2")
                # #endregion

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS)
        timed_out = thread.is_alive()
        # #region agent log
        _debug_log("ai_chat_ui.py:run_request", "after join", {"timed_out": timed_out, "has_result": result_holder[0] is not None, "has_exception": exception_holder[0] is not None}, "H2")
        # #endregion

        if exception_holder[0] is not None:
            log.error("AI chat error: %s", exception_holder[0])
            self.error_occurred.emit(str(exception_holder[0]))
        elif result_holder[0] is not None:
            self.response_ready.emit(result_holder[0])
        else:
            # #region agent log
            _debug_log("ai_chat_ui.py:run_request", "emitting timeout error", {"timed_out": timed_out}, "H5")
            # #endregion
            self.error_occurred.emit(
                "Request timed out after %s seconds. You can try again or send a new message."
                % REQUEST_TIMEOUT_SECONDS
            )

    @pyqtSlot()
    def clear_session(self):
        self.ai_chat.clear_session()

    @pyqtSlot(str, str)
    def on_tool_completed(self, tool_name: str, result: str):
        """When split_file_add_clip runs, start a new chat session (new thread)."""
        if tool_name == "split_file_add_clip_tool":
            self.ai_chat.clear_session()


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

        self.is_processing = False
        self._main_thread_runner = None  # track runner to connect/disconnect tool_completed

        # AI runs in a background thread; worker owns AIChat and emits when done
        self._ai_thread = QThread(self)
        self._worker = AIChatWorker()  # no parent so we can moveToThread
        self._worker.moveToThread(self._ai_thread)
        self._worker.response_ready.connect(self._on_response_ready)
        self._worker.error_occurred.connect(self._on_error)
        self._ai_thread.start()

        main = QWidget()
        main.setObjectName("AIChatWindowContents")
        layout = QVBoxLayout()
        main.setLayout(layout)
        self.setWidget(main)

        # Fade-in effect when dock is shown (GPU-accelerated)
        self._chat_opacity_effect = QGraphicsOpacityEffect(main)
        self._chat_opacity_effect.setOpacity(0.0)
        main.setGraphicsEffect(self._chat_opacity_effect)
        self._chat_fade_done = False
        self._chat_fade_anim = QPropertyAnimation(self._chat_opacity_effect, b"opacity")
        self._chat_fade_anim.setDuration(250)
        self._chat_fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._chat_fade_anim.setStartValue(0.0)
        self._chat_fade_anim.setEndValue(1.0)
        self._chat_fade_anim.finished.connect(self._on_chat_fade_finished)

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
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.cancel_request)
        self.cancel_btn.setVisible(False)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_chat)
        btn_h.addStretch()
        btn_h.addWidget(self.send_btn)
        btn_h.addWidget(self.cancel_btn)
        btn_h.addWidget(self.clear_btn)
        layout.addLayout(btn_h)

        self.msg_input.keyPressEvent = self._key_press

        # Short welcome (preamble has the main context)
        self._add_system_msg("Chat started. Ask to list files, add tracks, export video, or describe your project.")

        self.setMinimumWidth(400)
        self.setMinimumHeight(450)

    def closeEvent(self, event):
        """Stop the AI worker thread when the dock is closed."""
        self._ai_thread.quit()
        if not self._ai_thread.wait(3000):
            log.warning("AI chat thread did not finish within 3s")
        super().closeEvent(event)

    def showEvent(self, event):
        """Run fade-in animation the first time the dock is shown."""
        super().showEvent(event)
        if not self._chat_fade_done:
            self._chat_opacity_effect.setOpacity(0.0)
            self._chat_fade_anim.stop()
            self._chat_fade_anim.start()

    def _on_chat_fade_finished(self):
        self._chat_fade_done = True
        self._chat_opacity_effect.setOpacity(1.0)

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
        self._set_processing_ui(True)
        model_id = self.model_combo.currentData()
        if not model_id and self.model_combo.count():
            model_id = self.model_combo.currentText()
        model_id_str = model_id if model_id else ""
        # Create main-thread runner on main thread so tool invocations (BlockingQueuedConnection) don't deadlock
        try:
            from classes.ai_agent_runner import create_main_thread_runner, set_main_thread_runner
            if self._main_thread_runner is not None and hasattr(self._main_thread_runner, "tool_completed"):
                try:
                    self._main_thread_runner.tool_completed.disconnect(self._worker.on_tool_completed)
                except Exception:
                    pass
            runner = create_main_thread_runner()
            set_main_thread_runner(runner)
            self._main_thread_runner = runner
            if hasattr(runner, "tool_completed"):
                runner.tool_completed.connect(self._worker.on_tool_completed)
        except Exception:
            pass
        # #region agent log
        _debug_log("ai_chat_ui.py:send_message", "invoking worker run_request", {"text_len": len(text), "model_id": model_id_str or "(empty)"}, "H1")
        # #endregion
        QMetaObject.invokeMethod(
            self._worker,
            "run_request",
            Qt.QueuedConnection,
            Q_ARG(str, text),
            Q_ARG(str, model_id_str),
        )
        self.msg_input.setFocus()

    def _set_processing_ui(self, processing: bool):
        """Update Send/Cancel visibility and enabled state."""
        self.is_processing = processing
        self.send_btn.setEnabled(not processing)
        self.send_btn.setText("Processing..." if processing else "Send")
        self.cancel_btn.setVisible(processing)
        if not processing:
            self.msg_input.setFocus()

    def cancel_request(self):
        """Stop waiting for the current request; UI can accept follow-up messages. Late replies still appear."""
        self._set_processing_ui(False)

    @pyqtSlot(str)
    def _on_response_ready(self, text: str):
        self._add_assistant_msg(text)
        self._set_processing_ui(False)

    @pyqtSlot(str)
    def _on_error(self, text: str):
        # #region agent log
        _debug_log("ai_chat_ui.py:_on_error", "error slot", {"text_preview": text[:80] if text else ""}, "H1")
        # #endregion
        self._add_system_msg("Error: %s" % text)
        self._set_processing_ui(False)

    def clear_chat(self):
        reply = QMessageBox.question(
            self, "Clear", "Clear chat?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QMetaObject.invokeMethod(
                self._worker,
                "clear_session",
                Qt.QueuedConnection,
            )
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
            role_style = "color: #3B82F6;" if role == "user" else ""
            role_label = f'<span style="font-weight: bold; {role_style}">[{time_str}] {role}</span><br/>'
            self.chat_box.insertHtml(role_label + "<p>" + safe + "</p><br/>")

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)
