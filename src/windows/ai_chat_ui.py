import concurrent.futures
import html
import json
import os
import threading
import time

from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    QObject, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG,
    QUrl, QFileInfo,
)
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QMessageBox, QFrame,
    QGraphicsOpacityEffect,
)
from PyQt5.QtGui import QTextCursor

from classes.logger import log
from classes.ai_chat_functionality import AIChat, ChatSessionManager

# Optional CEP/WebEngine for HTML chat UI
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    from PyQt5.QtWebChannel import QWebChannel
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False

# Theme colors for chat CEP UI (match theme QSS). Keys match ThemeName.value.
# Bloomberg Light: high information density, sharp edges, accent #6366F1.
CHAT_THEME_COLORS = {
    "Bloomberg Light": {
        "chat-bg": "#F8FAFC",
        "chat-preamble-bg": "#F1F5F9",
        "chat-text": "#0F172A",
        "chat-border": "#E2E8F0",
        "chat-input-bg": "#FFFFFF",
        "chat-button-bg": "#F1F5F9",
        "chat-button-hover-bg": "#6366F1",
        "chat-accent": "#6366F1",
        "chat-code-bg": "#E2E8F0",
        "chat-placeholder": "rgba(15, 23, 42, 0.5)",
    },
    "Humanity: Dark": {
        "chat-bg": "#191919",
        "chat-preamble-bg": "#252525",
        "chat-text": "#ffffff",
        "chat-border": "#404040",
        "chat-input-bg": "#252525",
        "chat-button-bg": "#353535",
        "chat-button-hover-bg": "#2a82da",
        "chat-accent": "#6366F1",
        "chat-code-bg": "#2A2A2A",
        "chat-placeholder": "rgba(255, 255, 255, 0.5)",
    },
    "Retro": {
        "chat-bg": "#f0f0f0",
        "chat-preamble-bg": "#e8e8e8",
        "chat-text": "#333333",
        "chat-border": "#ccc",
        "chat-input-bg": "#ffffff",
        "chat-button-bg": "#e8e8e8",
        "chat-button-hover-bg": "#217dd4",
        "chat-accent": "#217dd4",
        "chat-code-bg": "#DCDCDC",
        "chat-placeholder": "rgba(51, 51, 51, 0.5)",
    },
    "Cosmic Dusk": {
        "chat-bg": "#151A23",
        "chat-preamble-bg": "#151A23",
        "chat-text": "#E6E6EB",
        "chat-border": "rgba(230, 230, 235, 0.12)",
        "chat-input-bg": "#151A23",
        "chat-button-bg": "#151A23",
        "chat-button-hover-bg": "#1E2433",
        "chat-accent": "#6366F1",
        "chat-code-bg": "#1E2433",
        "chat-placeholder": "rgba(230, 230, 235, 0.5)",
    },
}


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


def _friendly_tool_name(name: str) -> str:
    """Convert tool_name_tool to a readable label like 'Tool Name'."""
    s = name
    if s.endswith("_tool"):
        s = s[:-5]
    return s.replace("_", " ").title()


def _format_tool_args(args_json: str) -> str:
    """Format tool args JSON into a compact, readable string for display."""
    try:
        args = json.loads(args_json) if args_json else {}
        if not args:
            return ""
        parts = []
        for k, v in args.items():
            sv = str(v)
            if len(sv) > 30:
                sv = sv[:27] + "..."
            parts.append("%s: %s" % (k, sv))
        detail = ", ".join(parts)
        if len(detail) > 80:
            detail = detail[:77] + "..."
        return detail
    except Exception:
        if args_json and len(args_json) > 80:
            return args_json[:77] + "..."
        return args_json or ""


def _summarize_prompt(prompt: str, max_words: int = 6) -> str:
    """Use the default LLM to summarize the user prompt in a few words. Returns empty on failure."""
    try:
        from classes.ai_llm_registry import get_model, get_default_model_id
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError:
        return ""
    model_id = get_default_model_id()
    llm = get_model(model_id)
    if not llm:
        return ""
    system = (
        "Summarize the following user request in at most %d words. "
        "Reply with only the short phrase, no punctuation, no period."
    ) % max_words
    try:
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        out = (response.content if hasattr(response, "content") else str(response)).strip()
        return out[:80] if out else ""
    except Exception:
        return ""


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

# Maximum concurrent chat worker threads (leaves room for sub-agent pool)
_MAX_CHAT_WORKERS = 3


class ChatWorkerPool(QObject):
    """
    Manages a ``ThreadPoolExecutor`` for running AI chat requests.

    Each request is tagged with a *session_id* so the UI knows which tab
    to update when the response arrives.  Results are delivered via Qt
    signals on the main thread.
    """

    # session_id, response_text
    response_ready = pyqtSignal(str, str)
    # session_id, error_text
    error_occurred = pyqtSignal(str, str)

    def __init__(self, session_manager: ChatSessionManager, parent=None):
        super().__init__(parent)
        self._session_manager = session_manager
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_CHAT_WORKERS,
            thread_name_prefix="zenvi_chat",
        )
        # Track in-flight requests per session so we can reject duplicates
        self._in_flight: set = set()
        self._lock = threading.Lock()

    def submit_request(self, session_id: str, text: str, model_id: str):
        """Submit a chat request to the thread pool."""
        with self._lock:
            if session_id in self._in_flight:
                log.warning("ChatWorkerPool: session %s already has an in-flight request", session_id)
                return
            self._in_flight.add(session_id)
        self._executor.submit(self._run, session_id, text, model_id)

    def is_session_busy(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._in_flight

    def _run(self, session_id: str, text: str, model_id: str):
        """Executed on a pool thread.  Calls AIChat.send_message and posts result to main thread."""
        _debug_log("ChatWorkerPool._run", "entered", {"session_id": session_id[:8], "text_len": len(text)}, "H1")
        result_holder = [None]
        exception_holder = [None]

        def inner():
            try:
                chat = self._session_manager.get_session(session_id)
                if chat is None:
                    exception_holder[0] = RuntimeError("Session %s not found" % session_id)
                    return
                result_holder[0] = chat.send_message(text, model_id=model_id or None)
            except Exception as e:
                exception_holder[0] = e

        thread = threading.Thread(target=inner, daemon=True)
        thread.start()
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS)
        timed_out = thread.is_alive()

        with self._lock:
            self._in_flight.discard(session_id)

        if exception_holder[0] is not None:
            log.error("AI chat error (session %s): %s", session_id[:8], exception_holder[0])
            QMetaObject.invokeMethod(
                self, "_emit_error", Qt.QueuedConnection,
                Q_ARG(str, session_id), Q_ARG(str, str(exception_holder[0])),
            )
        elif result_holder[0] is not None:
            QMetaObject.invokeMethod(
                self, "_emit_response", Qt.QueuedConnection,
                Q_ARG(str, session_id), Q_ARG(str, result_holder[0]),
            )
        else:
            msg = "Request timed out after %s seconds." % REQUEST_TIMEOUT_SECONDS
            QMetaObject.invokeMethod(
                self, "_emit_error", Qt.QueuedConnection,
                Q_ARG(str, session_id), Q_ARG(str, msg),
            )

    @pyqtSlot(str, str)
    def _emit_response(self, session_id: str, text: str):
        self.response_ready.emit(session_id, text)

    @pyqtSlot(str, str)
    def _emit_error(self, session_id: str, text: str):
        self.error_occurred.emit(session_id, text)

    @pyqtSlot(str, str)
    def on_tool_completed(self, tool_name: str, result: str):
        """When split_file_add_clip runs, clear the active session."""
        if tool_name == "split_file_add_clip_tool":
            chat = self._session_manager.get_active_session()
            if chat:
                chat.clear_session()

    def shutdown(self):
        self._executor.shutdown(wait=False)


class ChatBridge(QObject):
    """QWebChannel bridge: exposes chat operations to the CEP chat UI via QWebChannel."""

    def __init__(self, window=None, parent=None):
        super().__init__(parent)
        self.window = window

    # -- Original slots -----------------------------------------------------

    @pyqtSlot(str, str)
    def sendMessage(self, text: str, model_id: str):
        if self.window:
            self.window._handle_web_send_message(text.strip(), model_id or "")

    @pyqtSlot()
    def cancelRequest(self):
        if self.window:
            self.window.cancel_request()

    @pyqtSlot()
    def clearChat(self):
        if self.window:
            self.window.clear_chat()

    @pyqtSlot()
    def ready(self):
        """Called from JS when QWebChannel is ready; push initial state."""
        if self.window and getattr(self.window, "_chat_web_ready", None):
            self.window._chat_web_ready()

    # -- Multi-session slots ------------------------------------------------

    @pyqtSlot(str)
    def createSession(self, model_id: str):
        """Create a new chat session and push updated tab list to JS."""
        if self.window:
            self.window._handle_create_session(model_id or "")

    @pyqtSlot(str)
    def switchSession(self, session_id: str):
        """Switch to an existing session tab."""
        if self.window:
            self.window._handle_switch_session(session_id)

    @pyqtSlot(str)
    def closeSession(self, session_id: str):
        """Close a session tab."""
        if self.window:
            self.window._handle_close_session(session_id)

    @pyqtSlot(str)
    def carryForward(self, session_id: str):
        """Carry-forward the conversation (summarize + new session)."""
        if self.window:
            self.window._handle_carry_forward(session_id)

    @pyqtSlot(str)
    def getContextUsage(self, session_id: str):
        """Push context-usage info for the given session to the JS ring."""
        if self.window:
            self.window._push_context_usage(session_id)


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
        self._use_web_ui = _WEBENGINE_AVAILABLE
        self._first_prompt_summary = None  # AI-generated summary of first user message for preamble

        # Multi-session manager & thread-pool worker
        self._session_manager = ChatSessionManager()
        self._session_manager.create_session()  # create the default first session
        self._worker_pool = ChatWorkerPool(self._session_manager, parent=self)
        self._worker_pool.response_ready.connect(self._on_response_ready)
        self._worker_pool.error_occurred.connect(self._on_error)

        if self._use_web_ui:
            self._init_web_ui()
        else:
            self._init_widget_ui()

        self.setMinimumWidth(400)
        self.setMinimumHeight(450)

    def _init_widget_ui(self):
        """Build classic Qt widget chat UI."""
        main = QWidget()
        main.setObjectName("AIChatWindowContents")
        layout = QVBoxLayout()
        main.setLayout(layout)
        self.setWidget(main)

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

        model_h = QHBoxLayout()
        model_h.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("modelCombo")
        self._populate_models()
        model_h.addWidget(self.model_combo)
        model_h.addStretch()
        layout.addLayout(model_h)

        self.chat_box = QTextEdit()
        self.chat_box.setObjectName("chatBox")
        self.chat_box.setReadOnly(True)
        self.chat_box.setAcceptRichText(True)
        self.chat_box.setPlaceholderText("Replies appear here. Assistant messages support **markdown** and code blocks.")
        layout.addWidget(self.chat_box)

        input_h = QHBoxLayout()
        self.msg_input = QTextEdit()
        self.msg_input.setObjectName("msgInput")
        self.msg_input.setMaximumHeight(80)
        self.msg_input.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for newline)")
        input_h.addWidget(self.msg_input)
        layout.addLayout(input_h)

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
        self._add_system_msg("Chat started. Ask to list files, add tracks, export video, or describe your project.")

    def _init_web_ui(self):
        """Build CEP/WebEngine HTML chat UI."""
        from classes import info
        self._chat_fade_done = True
        self._chat_web_ready = lambda: None
        self.preamble_frame = self.preamble_label = None
        self.model_combo = self.chat_box = self.msg_input = None
        self.send_btn = self.cancel_btn = self.clear_btn = None
        self._chat_opacity_effect = self._chat_fade_anim = None

        self._chat_view = QWebEngineView(self)
        self._chat_view.setObjectName("AIChatWindowContents")
        self.setWidget(self._chat_view)

        self._chat_channel = QWebChannel(self._chat_view.page())
        self._chat_bridge = ChatBridge(window=self, parent=self)
        self._chat_bridge.window = self
        self._chat_view.page().setWebChannel(self._chat_channel)
        self._chat_channel.registerObject("zenviChatBridge", self._chat_bridge)

        chat_ui_dir = os.path.join(info.PATH, "chat_ui")
        index_path = os.path.join(chat_ui_dir, "index.html")
        base_url = QUrl.fromLocalFile(QFileInfo(index_path).absoluteFilePath())
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self._chat_view.setHtml(html, base_url)

        def on_load_finished(ok):
            if ok:
                self._chat_web_ready = self._inject_web_ready

        self._chat_view.loadFinished.connect(on_load_finished)

    def _run_js(self, code, callback=None):
        """Run JavaScript in the chat WebEngine page. No-op if not using web UI."""
        if not self._use_web_ui or not getattr(self, "_chat_view", None):
            return
        page = self._chat_view.page()
        if callback:
            page.runJavaScript(code, callback)
        else:
            page.runJavaScript(code)

    def _inject_web_ready(self):
        """Push theme colors, models, preamble, tab list, and welcome message to the CEP UI."""
        try:
            from classes.app import get_app
            app = get_app()
            theme = app.theme_manager.get_current_theme() if getattr(app, "theme_manager", None) else None
            name = getattr(theme, "name", "Humanity: Dark")
            colors = CHAT_THEME_COLORS.get(name)
            if colors is None:
                colors = CHAT_THEME_COLORS["Bloomberg Light"] if "Light" in name or "Retro" in name else CHAT_THEME_COLORS["Humanity: Dark"]
            self._run_js("setThemeColors(%s);" % json.dumps(json.dumps(colors)))
        except Exception:
            colors = CHAT_THEME_COLORS["Bloomberg Light"]
            self._run_js("setThemeColors(%s);" % json.dumps(json.dumps(colors)))

        models = []
        try:
            from classes.ai_llm_registry import list_all_models, get_default_model_id
            default_id = get_default_model_id()
            for model_id, display_name in list_all_models():
                models.append({"id": model_id, "name": display_name, "default": model_id == default_id})
        except Exception:
            pass
        self._run_js("setModels(%s);" % json.dumps(json.dumps(models)))

        preamble = self._get_preamble_html()
        self._run_js("setPreamble(%s);" % json.dumps(preamble))

        self._run_js("clearMessages();")

        # Push initial tab list
        self._push_tab_list()

    def _get_preamble_html(self):
        """Return preamble as HTML: AI summary as heading when set, else 'Zenvi Assistant'."""
        if self._first_prompt_summary:
            return '<span class="preamble-title">%s</span>' % html.escape(self._first_prompt_summary.strip())
        return '<span class="preamble-title">Zenvi Assistant</span>'

    def _request_preamble_summary(self, prompt: str):
        """Start a background thread to summarize the first user prompt and update preamble."""
        if self._first_prompt_summary or not prompt or not prompt.strip():
            return

        def run():
            summary = _summarize_prompt(prompt.strip())
            if summary:
                QMetaObject.invokeMethod(
                    self,
                    "_on_preamble_summary",
                    Qt.QueuedConnection,
                    Q_ARG(str, summary),
                )

        t = threading.Thread(target=run, daemon=True)
        t.start()

    @pyqtSlot(str)
    def _on_preamble_summary(self, text: str):
        """Called on main thread when first-prompt summary is ready."""
        if not self._first_prompt_summary and text:
            self._first_prompt_summary = text
            self._update_preamble()
            # Update the session title in the manager + push tabs
            sid = self._session_manager.active_session_id
            if sid:
                self._session_manager.set_title(sid, text)
                self._push_tab_list()

    def _handle_web_send_message(self, text: str, model_id: str):
        """Handle send from CEP UI (same logic as send_message but with args)."""
        sid = self._session_manager.active_session_id
        if not sid:
            sid = self._session_manager.create_session(model_id)
        if self._worker_pool.is_session_busy(sid):
            self._run_js("alert('Processing previous message...');")
            return
        if not text:
            return
        self._add_user_msg(text)
        self._request_preamble_summary(text)
        self._set_processing_ui(True)
        self._setup_main_thread_runner()
        self._worker_pool.submit_request(sid, text, model_id)

    def closeEvent(self, event):
        """Shut down the worker pool when the dock is closed."""
        self._worker_pool.shutdown()
        super().closeEvent(event)

    def showEvent(self, event):
        """Run fade-in animation the first time the dock is shown (widget UI only)."""
        super().showEvent(event)
        if not self._use_web_ui and not self._chat_fade_done and self._chat_opacity_effect and self._chat_fade_anim:
            self._chat_opacity_effect.setOpacity(0.0)
            self._chat_fade_anim.stop()
            self._chat_fade_anim.start()

    def _on_chat_fade_finished(self):
        self._chat_fade_done = True
        self._chat_opacity_effect.setOpacity(1.0)

    def _update_preamble(self):
        """Update preamble text with current context (project name, tips)."""
        text = self._get_preamble_html()
        if self._use_web_ui:
            self._run_js("setPreamble(%s);" % json.dumps(text))
        elif self.preamble_label:
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
        """Send message from the classic Qt widget UI."""
        sid = self._session_manager.active_session_id
        if not sid:
            sid = self._session_manager.create_session()
        if self._worker_pool.is_session_busy(sid):
            QMessageBox.warning(self, "Wait", "Processing previous message...")
            return
        text = self.msg_input.toPlainText().strip()
        if not text:
            return
        self._add_user_msg(text)
        self._request_preamble_summary(text)
        self.msg_input.clear()
        self._set_processing_ui(True)
        model_id = self.model_combo.currentData()
        if not model_id and self.model_combo.count():
            model_id = self.model_combo.currentText()
        model_id_str = model_id if model_id else ""
        self._setup_main_thread_runner()
        _debug_log("ai_chat_ui.py:send_message", "submitting to worker pool", {"text_len": len(text), "model_id": model_id_str or "(empty)"}, "H1")
        self._worker_pool.submit_request(sid, text, model_id_str)
        self.msg_input.setFocus()

    def _set_processing_ui(self, processing: bool):
        """Update Send/Cancel visibility and enabled state."""
        self.is_processing = processing
        if self._use_web_ui:
            self._run_js("setProcessing(%s);" % ("true" if processing else "false"))
            return
        if self.send_btn:
            self.send_btn.setEnabled(not processing)
            self.send_btn.setText("Processing..." if processing else "Send")
        if self.cancel_btn:
            self.cancel_btn.setVisible(processing)
        if not processing and self.msg_input:
            self.msg_input.setFocus()

    def cancel_request(self):
        """Stop waiting for the current request; UI can accept follow-up messages. Late replies still appear."""
        self._set_processing_ui(False)

    @pyqtSlot(str, str)
    def _on_response_ready(self, session_id: str, text: str):
        """Handle a completed response from the worker pool."""
        active = self._session_manager.active_session_id
        if session_id == active:
            self._add_assistant_msg(text)
            self._set_processing_ui(False)
            self._push_context_usage(session_id)
        else:
            # Response for a background tab -- push via JS so user sees a badge
            self._run_js("onBackgroundResponse(%s, %s);" % (
                json.dumps(session_id), json.dumps(_markdown_to_html(text)),
            ))
        self._push_tab_list()

    @pyqtSlot(str, str)
    def _on_error(self, session_id: str, text: str):
        _debug_log("ai_chat_ui.py:_on_error", "error slot", {"text_preview": text[:80] if text else ""}, "H1")
        active = self._session_manager.active_session_id
        if session_id == active:
            self._add_system_msg("Error: %s" % text)
            self._set_processing_ui(False)
        self._push_tab_list()

    @pyqtSlot(str, str)
    def _on_tool_started_ui(self, name: str, args_json: str):
        """Push a new activity step to the chat UI when a tool begins executing."""
        friendly = _friendly_tool_name(name)
        detail = _format_tool_args(args_json)
        self._run_js("addActivityStep(%s, %s);" % (json.dumps(friendly), json.dumps(detail)))

    @pyqtSlot(str, str)
    def _on_tool_completed_ui(self, name: str, result: str):
        """Mark the current activity step as done in the chat UI."""
        self._run_js("completeLastActivityStep();")

    def clear_chat(self):
        reply = QMessageBox.question(
            self, "Clear", "Clear chat?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._first_prompt_summary = None
            sid = self._session_manager.active_session_id
            chat = self._session_manager.get_session(sid) if sid else None
            if chat:
                chat.clear_session()
            if self._use_web_ui:
                self._run_js("clearMessages();")
            else:
                self.chat_box.clear()
            self._update_preamble()
            self._add_system_msg("Chat cleared. Ask anything about your project or editing.")
            self._push_tab_list()

    def _add_user_msg(self, text):
        self._add_msg(text, "user", is_assistant=False, is_system=False)

    def _add_assistant_msg(self, text):
        self._add_msg(text, "assistant", is_assistant=True, is_system=False)

    def _add_system_msg(self, text):
        self._add_msg(text, "system", is_assistant=False, is_system=True)

    def _add_msg(self, text, role, is_assistant=False, is_system=False):
        if self._use_web_ui:
            if is_assistant:
                html_body = _markdown_to_html(text)
                self._run_js("appendMessage(%s, %s, true);" % (json.dumps(role), json.dumps(html_body)))
            else:
                safe = html.escape(text).replace("\n", "<br/>")
                self._run_js("appendMessage(%s, %s, false);" % (json.dumps(role), json.dumps("<p>" + safe + "</p>")))
            return
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)
        role_display = "You" if role == "user" else ("Assistant" if role == "assistant" else role)
        if is_assistant:
            html_body = _markdown_to_html(text)
            role_label = f'<span style="font-weight: bold;">{html.escape(role_display)}</span><br/>'
            self.chat_box.insertHtml(role_label + html_body + "<br/>")
        else:
            safe = html.escape(text).replace("\n", "<br/>")
            role_style = "color: #3B82F6;" if role == "user" else ""
            role_label = f'<span style="font-weight: bold; {role_style}">{html.escape(role_display)}</span><br/>'
            self.chat_box.insertHtml(role_label + "<p>" + safe + "</p><br/>")
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Multi-session helpers (called by ChatBridge slots)
    # ------------------------------------------------------------------

    def _setup_main_thread_runner(self):
        """Create/refresh the MainThreadToolRunner on the main thread."""
        try:
            from classes.ai_agent_runner import create_main_thread_runner, set_main_thread_runner
            if self._main_thread_runner is not None:
                for attr, slot in [
                    ("tool_completed", self._worker_pool.on_tool_completed),
                    ("tool_started", self._on_tool_started_ui),
                    ("tool_completed", self._on_tool_completed_ui),
                ]:
                    if hasattr(self._main_thread_runner, attr):
                        try:
                            getattr(self._main_thread_runner, attr).disconnect(slot)
                        except Exception:
                            pass
            runner = create_main_thread_runner()
            set_main_thread_runner(runner)
            self._main_thread_runner = runner
            for attr, slot in [
                ("tool_completed", self._worker_pool.on_tool_completed),
                ("tool_started", self._on_tool_started_ui),
                ("tool_completed", self._on_tool_completed_ui),
            ]:
                if hasattr(runner, attr):
                    getattr(runner, attr).connect(slot)
        except Exception:
            pass

    def _handle_create_session(self, model_id: str):
        """Create a new chat tab."""
        sid = self._session_manager.create_session(model_id)
        self._first_prompt_summary = None
        if self._use_web_ui:
            self._run_js("clearMessages();")
        self._update_preamble()
        self._push_tab_list()

    def _handle_switch_session(self, session_id: str):
        """Switch the active chat tab and reload its messages."""
        if not self._session_manager.switch_session(session_id):
            return
        self._first_prompt_summary = None
        chat = self._session_manager.get_session(session_id)
        if chat and chat.current_session:
            title = chat.current_session.title
            if title and title != "New Chat":
                self._first_prompt_summary = title
        if self._use_web_ui:
            self._run_js("clearMessages();")
            # Re-render the message history for this session
            if chat and chat.current_session:
                for msg in chat.current_session.messages:
                    role = msg.role.value
                    if role == "system":
                        continue
                    is_assistant = role == "assistant"
                    if is_assistant:
                        body = _markdown_to_html(msg.content)
                    else:
                        body = "<p>" + html.escape(msg.content).replace("\n", "<br/>") + "</p>"
                    self._run_js("appendMessage(%s, %s, %s);" % (
                        json.dumps(role), json.dumps(body),
                        "true" if is_assistant else "false",
                    ))
        self._update_preamble()
        self._push_tab_list()
        self._push_context_usage(session_id)

    def _handle_close_session(self, session_id: str):
        """Close a chat tab."""
        new_active = self._session_manager.close_session(session_id)
        if new_active:
            self._handle_switch_session(new_active)

    def _handle_carry_forward(self, session_id: str):
        """Carry-forward: summarize + create continuation session."""
        self._set_processing_ui(True)

        def run():
            sid = session_id or self._session_manager.active_session_id
            new_sid = self._session_manager.carry_forward(sid)
            QMetaObject.invokeMethod(
                self, "_on_carry_forward_done", Qt.QueuedConnection,
                Q_ARG(str, new_sid or ""),
            )

        t = threading.Thread(target=run, daemon=True)
        t.start()

    @pyqtSlot(str)
    def _on_carry_forward_done(self, new_session_id: str):
        """Called on main thread when carry-forward completes."""
        self._set_processing_ui(False)
        if new_session_id:
            self._handle_switch_session(new_session_id)
        self._push_tab_list()

    def _push_tab_list(self):
        """Push the current session list to the JS tab bar."""
        if not self._use_web_ui:
            return
        tabs = self._session_manager.list_sessions()
        self._run_js("setTabs(%s);" % json.dumps(json.dumps(tabs)))

    def _push_context_usage(self, session_id: str = ""):
        """Push context-window usage info for a session to the JS ring."""
        if not self._use_web_ui:
            return
        sid = session_id or self._session_manager.active_session_id
        if not sid:
            return
        chat = self._session_manager.get_session(sid)
        if not chat or not chat.current_session:
            return
        model_id = chat.current_session.model
        if model_id == "default":
            try:
                from classes.ai_llm_registry import get_default_model_id
                model_id = get_default_model_id()
            except Exception:
                model_id = "openai/gpt-4o-mini"
        from classes.ai_context_tracker import get_usage_info
        usage = get_usage_info(model_id, chat.current_session.get_conversation_history())
        self._run_js("updateContextUsage(%s);" % json.dumps(json.dumps(usage)))
