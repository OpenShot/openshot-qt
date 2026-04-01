import html
import json
import os
import threading
import time

from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    QObject, QThread, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG,
    QUrl, QFileInfo, QTimer,
)
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QMessageBox, QFrame,
    QGraphicsOpacityEffect, QScrollArea, QToolButton,
)
from PyQt5.QtGui import QColor, QTextCursor

from classes.logger import log
from classes.api_client import get_backend_client

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
        "chat-placeholder": "rgba(51, 51, 51, 0.5)",
    },
    "Cosmic Dusk": {
        "chat-bg":              "#161616",
        "chat-surface":         "#1e1e1e",
        "chat-text":            "#d4d4d4",
        "chat-muted":           "#6b7280",
        "chat-placeholder":     "#6b7280",
        "chat-border":          "#2a2a2a",
        "chat-input-bg":        "#1a1a1a",
        "chat-button-bg":       "#252525",
        "chat-button-hover-bg": "#2e2e2e",
        "chat-accent":          "#4d9cf6",
        "chat-code-bg":         "#252525",
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


def _summarize_prompt(prompt: str, max_words: int = 6) -> str:
    """Ask the backend to summarize the user prompt in a few words. Returns empty on failure."""
    try:
        client = get_backend_client()
        system = (
            "Summarize the following user request in at most %d words. "
            "Reply with only the short phrase, no punctuation, no period."
        ) % max_words
        resp = client.send_message(message=f"[SYSTEM]{system}[/SYSTEM]\n{prompt}")
        out = resp.get("response", "").strip()
        return out[:80] if out else ""
    except Exception:
        return ""


REQUEST_TIMEOUT_SECONDS = 120


def _format_mmss(seconds: float) -> str:
    try:
        seconds = float(seconds)
    except Exception:
        seconds = 0.0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def _text_likely_needs_clip_context(text: str) -> bool:
    t = (text or "").lower()
    keywords = [
        "this clip",
        "selected clip",
        "timeline clip",
        "in this clip",
        "within this clip",
        "search",
        "find",
        "slice",
        "split",
        "cut",
        "razor",
        "yellow marker",
        "where",
        "when",
    ]
    return any(k in t for k in keywords)


class AIChatWorker(QObject):
    """Sends chat messages to the zenvi-backend API server in a background thread.

    Uses WebSocket for bidirectional communication: the backend can delegate
    tool calls (e.g. timeline operations) back to the frontend for execution.
    Falls back to REST if WebSocket is unavailable.

    Emits *response_ready* with the assistant reply or *error_occurred* on failure.
    """

    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend_session_id = None
        self._stopping = False  # Set to True during app shutdown to suppress fallback/emit

    @pyqtSlot(str, str)
    def run_request(self, text: str, model_id: str):
        """Send the user message to the backend via WebSocket (with tool delegation)."""
        try:
            from classes.tool_handlers import execute_tool

            client = get_backend_client()

            last_tool_result = None

            def on_tool_call(tool_name, tool_args, call_id):
                """Execute a tool locally and return the result."""
                nonlocal last_tool_result
                log.info("Tool delegated from backend: %s", tool_name)
                args = tool_args or {}
                # Ensure tool state that depends on the chat/request identity
                # (e.g. split→add_clip chains) is isolated per UI tab/session.
                if self._backend_session_id:
                    args["chat_session_id"] = self._backend_session_id
                result = execute_tool(tool_name, args)
                # Remember the last successful tool result so we can use it
                # if the WebSocket breaks after the tool already completed.
                if result and not str(result).startswith("Error"):
                    last_tool_result = result
                return result

            final_response = None
            final_error = None

            def on_response(response_text, session_id):
                nonlocal final_response
                final_response = response_text
                self._backend_session_id = session_id or self._backend_session_id

            def on_error(error_message):
                nonlocal final_error
                final_error = error_message

            result = client.send_message_ws(
                message=text,
                model_id=model_id or None,
                session_id=self._backend_session_id,
                on_tool_call=on_tool_call,
                on_response=on_response,
                on_error=on_error,
            )

            if final_error:
                # App is shutting down — the WS was closed intentionally.
                # Don't fall back to REST or emit signals into a dying Qt stack.
                if self._stopping:
                    return

                # If a tool already executed successfully (e.g. v2v clip
                # was generated and imported), use that result instead of
                # falling back to REST which would re-run the entire agent.
                if last_tool_result:
                    log.info("WebSocket failed (%s) but tool already succeeded, using tool result", final_error)
                    self.response_ready.emit(last_tool_result)
                    return
                if final_response:
                    log.info("WebSocket failed (%s) but response already received", final_error)
                    self.response_ready.emit(final_response)
                    return
                # Fall back to REST only if no tool result and no response
                log.warning("WebSocket failed (%s), falling back to REST", final_error)
                resp = client.send_message(
                    message=text,
                    model_id=model_id or None,
                    session_id=self._backend_session_id,
                )
                result = resp.get("response", "")
                self._backend_session_id = resp.get("session_id", self._backend_session_id)
                if result is not None:
                    self.response_ready.emit(result)
                else:
                    self.error_occurred.emit("No response from backend.")
                return

            if self._stopping:
                return
            if result is not None:
                self.response_ready.emit(result)
            elif final_response is not None:
                self.response_ready.emit(final_response)
            else:
                self.error_occurred.emit("No response from backend.")
        except Exception as e:
            if self._stopping:
                return  # Swallow exceptions during shutdown — Qt stack is going away
            log.error("AI chat error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))

    @pyqtSlot()
    def clear_session(self):
        """Clear the backend chat session."""
        if self._backend_session_id:
            try:
                get_backend_client().clear_chat_session(self._backend_session_id)
            except Exception:
                pass
            # Keep the backend session_id stable for this UI tab/session.
            # Clearing only resets conversation state + Supabase memory rows.

    @pyqtSlot(str, str)
    def on_tool_completed(self, tool_name: str, result: str):
        """When split_file_add_clip runs, clear the session so the next message starts fresh."""
        if tool_name == "split_file_add_clip_tool":
            self.clear_session()


class ChatBridge(QObject):
    """QWebChannel bridge: exposes sendMessage, cancelRequest, clearChat to the CEP chat UI."""

    def __init__(self, window=None, parent=None):
        super().__init__(parent)
        self.window = window

    @pyqtSlot(str, str, str)
    def sendMessage(self, text: str, model_id: str, context_json: str = ""):
        if self.window:
            self.window._handle_web_send_message(text.strip(), model_id or "", context_json)

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

    @pyqtSlot(str)
    def requestClipPick(self, purpose: str):
        """Enter clip-pick mode: the next timeline SelectionChanged fires chatSetPickResult in JS."""
        if self.window:
            self.window._start_clip_pick(purpose)

    @pyqtSlot()
    def cancelClipPick(self):
        if self.window:
            self.window._cancel_clip_pick()

    @pyqtSlot(str)
    def createSession(self, model_id: str):
        if self.window:
            self.window._create_session(model_id)

    @pyqtSlot(str)
    def switchSession(self, session_id: str):
        if self.window:
            self.window._switch_session(session_id)

    @pyqtSlot(str)
    def closeSession(self, session_id: str):
        if self.window:
            self.window._close_session(session_id)


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
        self._use_web_ui = _WEBENGINE_AVAILABLE
        self._first_prompt_summary = None  # mirrors active session's first_prompt_summary
        self._auto_attach_selected_clip_context = True
        self._clip_pick_purpose = None   # None | 'selected_clip' | 'transition_a' | 'transition_b'

        # Per-session state: each entry holds {"worker", "thread", "title",
        # "messages", "processing", "first_prompt_summary"}.
        self._sessions: dict = {}
        self._active_sid: str = ""
        self._history_restore_started = False

        # Stop all threads on app quit (covers the shutdown path where
        # closeEvent is never called on dock widgets).
        from PyQt5.QtWidgets import QApplication
        app_instance = QApplication.instance()
        if app_instance:
            app_instance.aboutToQuit.connect(self._stop_all_threads)

        # Restore previously open chat sessions (if any) before building UI.
        store = self._load_chat_sessions_store()
        restored_sessions = store.get("sessions", []) if isinstance(store, dict) else []
        if isinstance(restored_sessions, list) and restored_sessions:
            for entry in restored_sessions:
                if not isinstance(entry, dict):
                    continue
                sid = entry.get("session_id")
                title = entry.get("title") or "New Chat"
                if not sid or sid in self._sessions:
                    continue
                worker, thread = self._make_worker(sid)
                self._sessions[sid] = {
                    "worker": worker,
                    "thread": thread,
                    "title": title,
                    "messages": [],
                    "processing": False,
                    "unread": False,
                    "first_prompt_summary": title,
                }

            active_from_store = store.get("active_session_id") if isinstance(store, dict) else None
            if active_from_store in self._sessions:
                self._active_sid = active_from_store
            elif self._sessions:
                self._active_sid = next(iter(self._sessions))
            self._first_prompt_summary = self._sessions[self._active_sid].get("first_prompt_summary")
        if not self._sessions:
            # Create the initial session before building the UI widgets.
            self._create_initial_session()
            self._save_chat_sessions_store()

        if self._use_web_ui:
            self._init_web_ui()
        else:
            self._init_widget_ui()

        self.setMinimumWidth(400)
        self.setMinimumHeight(450)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _make_worker(self, session_id: str):
        """Create and start a new AIChatWorker thread pair for the given session_id."""
        thread = QThread()
        worker = AIChatWorker()
        worker._session_id = session_id   # used by signal handlers to route responses
        # Keep backend memory namespaced by the same session id as the UI tab.
        worker._backend_session_id = session_id
        worker.moveToThread(thread)
        worker.response_ready.connect(self._on_response_ready)
        worker.error_occurred.connect(self._on_error)
        thread.start()
        return worker, thread

    def _create_initial_session(self):
        import uuid
        sid = str(uuid.uuid4())
        worker, thread = self._make_worker(sid)
        self._sessions[sid] = {
            "worker": worker,
            "thread": thread,
            "title": "New Chat",
            "messages": [],
            "processing": False,
            "unread": False,
            "first_prompt_summary": None,
        }
        self._active_sid = sid

    def _create_session(self, model_id: str = ""):
        """Create a new chat session and switch to it (called from the + tab button)."""
        import uuid
        sid = str(uuid.uuid4())
        worker, thread = self._make_worker(sid)
        self._sessions[sid] = {
            "worker": worker,
            "thread": thread,
            "title": "New Chat",
            "messages": [],
            "processing": False,
            "unread": False,
            "first_prompt_summary": None,
        }
        self._active_sid = sid
        self._first_prompt_summary = None
        self.is_processing = False
        if self._use_web_ui:
            self._run_js("clearMessages();")
            self._push_tabs_to_js()
            self._update_preamble()
            self._add_system_msg("New session started. Ask anything about your project.")
        else:
            self.chat_box.clear()
            self._add_system_msg("New session started. Ask anything about your project.")
            self._update_preamble()
            self._rebuild_widget_tabs()
        self._save_chat_sessions_store()

    def _switch_session(self, session_id: str):
        """Switch the displayed session to *session_id* (called when user clicks a tab)."""
        if session_id not in self._sessions or session_id == self._active_sid:
            return
        self._active_sid = session_id
        sess = self._sessions[session_id]
        self._first_prompt_summary = sess.get("first_prompt_summary")
        self.is_processing = sess.get("processing", False)
        if self._use_web_ui:
            self._run_js("clearMessages();")
            for role, html_body, is_assistant in sess.get("messages", []):
                self._run_js("appendMessage(%s, %s, %s);" % (
                    json.dumps(role),
                    json.dumps(html_body),
                    "true" if is_assistant else "false",
                ))
            self._push_tabs_to_js()
            self._run_js("setProcessing(%s);" % ("true" if self.is_processing else "false"))
        self._update_preamble()
        self._save_chat_sessions_store()
        if not self._use_web_ui:
            # Widget mode: render the stored messages for the newly active session.
            sess["unread"] = False
            self._render_active_session_widget()
            self._rebuild_widget_tabs()

    def _close_session(self, session_id: str):
        """Close a session and delete its Pinecone namespace (called from the × on a tab)."""
        if len(self._sessions) <= 1:
            return  # never close the last session
        if session_id not in self._sessions:
            return
        sess = self._sessions.pop(session_id)
        # Clear backend session in background
        QMetaObject.invokeMethod(sess["worker"], "clear_session", Qt.QueuedConnection)
        # Stop the worker thread
        thread = sess["thread"]
        if thread.isRunning():
            thread.quit()
            thread.wait(1000)
        # If we just closed the active session, switch to the first remaining one
        if self._active_sid == session_id:
            self._active_sid = next(iter(self._sessions))
            self._switch_session(self._active_sid)
        else:
            if self._use_web_ui:
                self._push_tabs_to_js()
            else:
                self._rebuild_widget_tabs()
        self._save_chat_sessions_store()

    def _push_tabs_to_js(self):
        """Push the current session list to the JS tab bar."""
        tabs = []
        for sid, sess in self._sessions.items():
            tabs.append({
                "id": sid,
                "title": sess.get("first_prompt_summary") or sess.get("title", "New Chat"),
                "active": sid == self._active_sid,
                "processing": bool(sess.get("processing", False)),
            })
        self._run_js("setTabs(%s);" % json.dumps(json.dumps(tabs)))

    # ------------------------------------------------------------------
    # Local persistence for open chat sessions (session ids + titles)
    # ------------------------------------------------------------------
    def _chat_sessions_store_path(self) -> str:
        from classes import info
        return os.path.join(info.USER_PATH, "zenvi_chat_sessions.json")

    def _load_chat_sessions_store(self) -> dict:
        try:
            path = self._chat_sessions_store_path()
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception:
            return {}

    def _save_chat_sessions_store(self) -> None:
        try:
            from classes import info

            path = self._chat_sessions_store_path()
            os.makedirs(info.USER_PATH, exist_ok=True)

            sessions_payload = []
            for sid, sess in self._sessions.items():
                title = sess.get("first_prompt_summary") or sess.get("title", "New Chat")
                sessions_payload.append({"session_id": sid, "title": title})

            payload = {
                "version": 1,
                "active_session_id": self._active_sid,
                "sessions": sessions_payload,
            }

            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp_path, path)
        except Exception:
            # Non-fatal: chat can still run without local persistence.
            pass

    @pyqtSlot(str, str)
    def _on_history_restored(self, session_id: str, messages_json: str):
        """Apply restored /chat/history data into in-memory + visible UI."""
        if session_id not in self._sessions:
            return
        try:
            restored_items = json.loads(messages_json) if messages_json else []
        except Exception:
            restored_items = []

        system_parts = [m for m in self._sessions[session_id].get("messages", []) if m and m[0] == "system"]
        restored_messages = [(m.get("role", ""), m.get("html_body", ""), bool(m.get("is_assistant", False))) for m in restored_items]
        # Preserve any existing system messages (if present) and append restored conversation turns.
        self._sessions[session_id]["messages"] = system_parts + restored_messages
        self._sessions[session_id]["unread"] = False
        self._sessions[session_id]["processing"] = False

        if session_id != self._active_sid:
            # Inactive tabs only need data stored for the next switch.
            if self._use_web_ui:
                self._push_tabs_to_js()
            else:
                self._rebuild_widget_tabs()
            return

        if self._use_web_ui:
            self._run_js("clearMessages();")
            for role, html_body, is_assistant in self._sessions[session_id].get("messages", []):
                self._run_js(
                    "appendMessage(%s, %s, %s);" % (
                        json.dumps(role),
                        json.dumps(html_body),
                        "true" if is_assistant else "false",
                    )
                )
            self._push_tabs_to_js()
        else:
            self._render_active_session_widget()
            self._rebuild_widget_tabs()

    def _start_restore_chat_histories_async(self) -> None:
        """Fetch /chat/history/{session_id} for all open sessions."""
        if self._history_restore_started:
            return
        self._history_restore_started = True

        session_ids = list(self._sessions.keys())

        def _restore_all():
            try:
                client = get_backend_client()
            except Exception:
                client = None

            for sid in session_ids:
                if client is None:
                    return
                try:
                    resp = client.get_chat_history(sid)
                    messages = (resp or {}).get("messages", []) or []
                except Exception:
                    messages = []

                restored_items = []
                for m in messages:
                    role = m.get("role", "")
                    content = m.get("content", "") or ""
                    if role == "assistant":
                        html_body = _markdown_to_html(content)
                        restored_items.append({"role": role, "html_body": html_body, "is_assistant": True})
                    else:
                        safe = html.escape(content).replace("\n", "<br/>")
                        html_body = "<p>" + safe + "</p>"
                        restored_items.append({"role": role, "html_body": html_body, "is_assistant": False})

                # Apply on the Qt main thread.
                try:
                    QMetaObject.invokeMethod(
                        self,
                        "_on_history_restored",
                        Qt.QueuedConnection,
                        Q_ARG(str, sid),
                        Q_ARG(str, json.dumps(restored_items)),
                    )
                except Exception:
                    pass

        threading.Thread(target=_restore_all, daemon=True).start()

    def _active_session(self) -> dict:
        return self._sessions.get(self._active_sid, {})

    # ------------------------------------------------------------------
    # Widget multi-chat tab bar + rendering helpers
    # ------------------------------------------------------------------
    def _display_stored_msg_widget(self, role: str, html_body: str, is_assistant: bool):
        """Render a stored (role, html_body) tuple into the widget chat box."""
        if not getattr(self, "chat_box", None):
            return

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)

        role_display = "You" if role == "user" else ("Assistant" if role == "assistant" else role)
        if is_assistant:
            role_label = f'<span style="font-weight: bold;">{html.escape(role_display)}</span><br/>'
        else:
            role_style = "color: #3B82F6;" if role == "user" else ""
            role_label = (
                f'<span style="font-weight: bold; {role_style}">{html.escape(role_display)}</span><br/>'
            )

        self.chat_box.insertHtml(role_label + html_body + "<br/>")

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)

    def _render_active_session_widget(self):
        """Clear and re-render stored messages for the active session (widget mode only)."""
        if self._use_web_ui:
            return
        if not getattr(self, "chat_box", None):
            return
        self.chat_box.clear()
        sess = self._active_session()
        for role, html_body, is_assistant in sess.get("messages", []):
            self._display_stored_msg_widget(role, html_body, is_assistant)

    def _rebuild_widget_tabs(self):
        """Rebuild the widget fallback multi-chat tab bar."""
        if self._use_web_ui:
            return
        layout = getattr(self, "_widget_tabs_layout", None)
        if layout is None:
            return

        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for sid, sess in self._sessions.items():
            title = sess.get("first_prompt_summary") or sess.get("title", "New Chat")
            processing = bool(sess.get("processing", False))
            unread = bool(sess.get("unread", False))

            suffix = ""
            if processing:
                suffix += " [P]"
            if unread:
                suffix += " [U]"

            tab_btn = QPushButton(title + suffix)
            tab_btn.setObjectName("chatWidgetTabBtn")
            tab_btn.setFlat(True)
            tab_btn.setCheckable(False)
            tab_btn.setStyleSheet(
                "text-align: left; background: transparent; border: 1px solid transparent;"
                if sid != self._active_sid else
                "text-align: left; background: rgba(77,156,246,0.14); border: 1px solid rgba(77,156,246,0.35);"
            )
            tab_btn.clicked.connect(lambda _=False, s=sid: self._switch_session(s))
            layout.addWidget(tab_btn)

            if len(self._sessions) > 1:
                close_btn = QToolButton()
                close_btn.setObjectName("chatWidgetTabCloseBtn")
                close_btn.setAutoRaise(True)
                close_btn.setText("x")
                close_btn.setStyleSheet("border: none; color: #6b7280;")
                close_btn.clicked.connect(lambda _=False, s=sid: self._close_session(s))
                layout.addWidget(close_btn)

        add_btn = QPushButton("+")
        add_btn.setObjectName("chatWidgetTabAddBtn")
        add_btn.setFlat(True)
        add_btn.setStyleSheet("border: 1px solid rgba(255,255,255,0.08);")
        add_btn.clicked.connect(
            lambda _=False: self._create_session(
                self.model_combo.currentData() if getattr(self, "model_combo", None) else ""
            )
        )
        layout.addWidget(add_btn)

    # ------------------------------------------------------------------
    # Widget UI (fallback when WebEngine is unavailable)
    # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Widget multi-chat tab bar (fallback mode)
        # ------------------------------------------------------------------
        self._widget_tab_scroll = QScrollArea()
        self._widget_tab_scroll.setWidgetResizable(True)
        self._widget_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._widget_tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._widget_tab_scroll.setFrameShape(QFrame.NoFrame)
        self._widget_tabs_container = QWidget()
        self._widget_tabs_container.setObjectName("widgetChatTabContainer")
        self._widget_tabs_layout = QHBoxLayout()
        self._widget_tabs_layout.setContentsMargins(8, 4, 8, 4)
        self._widget_tabs_layout.setSpacing(6)
        self._widget_tabs_container.setLayout(self._widget_tabs_layout)
        self._widget_tab_scroll.setWidget(self._widget_tabs_container)
        self._widget_tab_scroll.setFixedHeight(38)
        layout.addWidget(self._widget_tab_scroll)

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
        self.chat_box.setPlaceholderText("")
        layout.addWidget(self.chat_box)

        input_h = QHBoxLayout()
        self.msg_input = QTextEdit()
        self.msg_input.setObjectName("msgInput")
        self.msg_input.setMaximumHeight(80)
        self.msg_input.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for newline)")
        input_h.addWidget(self.msg_input)
        layout.addLayout(input_h)

        btn_h = QHBoxLayout()
        self.attach_btn = QPushButton("Attach Clip")
        self.attach_btn.setObjectName("attachClipBtn")
        self.attach_btn.setToolTip("Insert @selected_clip into your message")
        self.attach_btn.clicked.connect(self._insert_selected_clip_token)
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
        btn_h.addWidget(self.attach_btn)
        btn_h.addWidget(self.send_btn)
        btn_h.addWidget(self.cancel_btn)
        btn_h.addWidget(self.clear_btn)
        layout.addLayout(btn_h)

        self.msg_input.keyPressEvent = self._key_press
        self._add_system_msg("Chat started. Ask to list files, add tracks, export video, or describe your project.")
        self._rebuild_widget_tabs()
        self._start_restore_chat_histories_async()

    def _insert_selected_clip_token(self):
        """Attach the currently selected timeline clip as context (widget UI only)."""
        try:
            if self._use_web_ui:
                # Web UI handles this via the JS tag system.
                return
            if not self.msg_input:
                return
            cursor = self.msg_input.textCursor()
            cursor.insertText("@selected_clip ")
            self.msg_input.setTextCursor(cursor)
            self.msg_input.setFocus()
        except Exception:
            pass

    def _build_selected_clip_context(self) -> tuple[str, str]:
        """Return (context_block, short_summary). Empty strings if no timeline clip is selected."""
        try:
            from classes.app import get_app
            from classes.query import Clip, File

            app = get_app()
            win = getattr(app, "window", None)
            selected_ids = getattr(win, "selected_clips", []) or []
            if not selected_ids:
                selected_ids = getattr(win, "ai_last_selected_clips", []) or []
            if not selected_ids:
                return "", ""
            clip_obj = Clip.get(id=str(selected_ids[0]))
            if not clip_obj:
                return "", ""
            data = clip_obj.data if isinstance(getattr(clip_obj, "data", None), dict) else {}
            title = data.get("title") or data.get("label") or "Selected Clip"

            clip_start = float(data.get("start", 0.0) or 0.0)
            clip_end = float(data.get("end", 0.0) or 0.0)
            position = float(data.get("position", 0.0) or 0.0)
            # Keep context minimal (avoid leaking internal IDs into the prompt)

            context = (
                "[Selected timeline clip context]\n"
                f"title: {title}\n"
                f"source_window_seconds: {clip_start:.3f} to {clip_end:.3f}\n"
                f"source_window_mmss: {_format_mmss(clip_start)} to {_format_mmss(clip_end)}\n"
                f"timeline_position_seconds: {position:.3f}\n"
                "[/Selected timeline clip context]"
            )
            summary = f"{title} ({_format_mmss(clip_start)}–{_format_mmss(clip_end)})"
            return context, summary
        except Exception:
            return "", ""

    def _augment_text_with_clip_context(self, text: str) -> tuple[str, str]:
        """Return (augmented_text, attached_summary)."""
        ctx, summary = self._build_selected_clip_context()
        if not ctx:
            try:
                log.debug("AIChat: no selected clip context available")
            except Exception:
                pass
            return text, ""

        if "@selected_clip" in text or "@clip" in text:
            augmented = text.replace("@selected_clip", ctx).replace("@clip", ctx)
            try:
                log.debug("AIChat: attached selected clip context via token: %s", summary)
            except Exception:
                pass
            return augmented, summary

        if self._auto_attach_selected_clip_context and _text_likely_needs_clip_context(text):
            try:
                log.debug("AIChat: auto-attached selected clip context: %s", summary)
            except Exception:
                pass
            return f"{ctx}\n\n{text}", summary

        return text, ""

    def _prepend_editor_snapshot(self, text: str) -> str:
        """Ground the model with a bounded timeline snapshot (main thread)."""
        try:
            from classes.tool_handlers import build_editor_snapshot_for_chat

            snap = build_editor_snapshot_for_chat()
            if snap:
                return f"{snap}\n{text}"
        except Exception:
            pass
        return text

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
        self._chat_view.page().setBackgroundColor(QColor(13, 13, 13))
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
                # Force CSS variables and element backgrounds regardless of caching
                self._chat_view.page().runJavaScript("""
                    var r = document.documentElement.style;
                    r.setProperty('--chat-bg',       '#0d0d0d');
                    r.setProperty('--chat-surface',  '#0d0d0d');
                    r.setProperty('--chat-input-bg', '#171717');
                    r.setProperty('--chat-border',   'transparent');
                    document.body.style.background = '#0d0d0d';
                    var msgs = document.getElementById('chat-messages');
                    if (msgs) { msgs.style.background = '#0d0d0d'; msgs.style.border = 'none'; }
                    var preamble = document.querySelector('.chat-container > div');
                    if (preamble) { preamble.style.background = '#0d0d0d'; preamble.style.border = 'none'; }
                """)
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
        """Push theme colors, models, preamble and welcome message to the CEP UI."""
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
            client = get_backend_client()
            api_models = client.list_models()  # returns List[{model_id, display_name}]
            default_id = client.get_default_model_id()
            for m in api_models:
                mid = m.get("model_id", "")
                models.append({"id": mid, "name": m.get("display_name", mid), "default": mid == default_id})
        except Exception:
            log.warning("Failed to fetch models from backend")
        self._run_js("setModels(%s);" % json.dumps(json.dumps(models)))

        preamble = self._get_preamble_html()
        self._run_js("setPreamble(%s);" % json.dumps(preamble))

        self._run_js("clearMessages();")
        self._push_tabs_to_js()
        self._start_restore_chat_histories_async()

        # Kick off credits balance display and start periodic refresh
        self._start_credits_refresh()

    def _start_credits_refresh(self):
        """Fetch credits balance once and start a 60-second refresh timer."""
        self._fetch_credits_balance()
        if not getattr(self, "_credits_timer", None):
            self._credits_timer = QTimer(self)
            self._credits_timer.timeout.connect(self._fetch_credits_balance)
            self._credits_timer.start(60_000)   # refresh every 60 seconds

    def _fetch_credits_balance(self):
        """Fetch balance in a background thread; push result to JS on main thread."""
        def run():
            try:
                from classes.credits_client import credits as _creds
                _, balance = _creds.check(0)
                QMetaObject.invokeMethod(
                    self,
                    "_on_credits_balance",
                    Qt.QueuedConnection,
                    Q_ARG(int, balance),
                )
            except Exception as exc:
                log.debug("credits refresh failed: %s", exc)

        threading.Thread(target=run, daemon=True, name="credits-ui-refresh").start()

    @pyqtSlot(int)
    def _on_credits_balance(self, balance: int):
        """Push updated balance to the JS badge (called on main thread)."""
        self._run_js("if(window.updateCreditsBalance) updateCreditsBalance(%d);" % balance)

    def _get_preamble_html(self):
        """Return preamble as HTML: AI summary as heading when set, else 'Zenvi Assistant'."""
        if self._first_prompt_summary:
            return '<span class="preamble-title">%s</span>' % html.escape(self._first_prompt_summary.strip())
        return '<span class="preamble-title">Zenvi Assistant</span>'

    def _request_preamble_summary(self, prompt: str):
        """Start a background thread to summarize the first user prompt and update preamble."""
        sess = self._active_session()
        if not sess or sess.get("first_prompt_summary") or not prompt or not prompt.strip():
            return
        active_sid = self._active_sid  # capture for closure

        def run():
            summary = _summarize_prompt(prompt.strip())
            if summary:
                QMetaObject.invokeMethod(
                    self,
                    "_on_preamble_summary",
                    Qt.QueuedConnection,
                    Q_ARG(str, active_sid),
                    Q_ARG(str, summary),
                )

        t = threading.Thread(target=run, daemon=True)
        t.start()

    @pyqtSlot(str, str)
    def _on_preamble_summary(self, session_id: str, text: str):
        """Called on main thread when first-prompt summary is ready."""
        if session_id in self._sessions and not self._sessions[session_id].get("first_prompt_summary") and text:
            self._sessions[session_id]["first_prompt_summary"] = text
            if session_id == self._active_sid:
                self._first_prompt_summary = text
                self._update_preamble()
            self._push_tabs_to_js()
            self._save_chat_sessions_store()

    def _start_clip_pick(self, purpose: str):
        """Connect one-shot to SelectionChanged for the given pick purpose."""
        self._clip_pick_purpose = purpose
        try:
            from classes.app import get_app
            win = getattr(get_app(), "window", None)
            if win:
                win.SelectionChanged.connect(self._on_pick_selection_changed)
        except Exception as exc:
            log.debug("AIChat: _start_clip_pick connect error: %s", exc)

    def _cancel_clip_pick(self):
        self._clip_pick_purpose = None
        try:
            from classes.app import get_app
            win = getattr(get_app(), "window", None)
            if win:
                try:
                    win.SelectionChanged.disconnect(self._on_pick_selection_changed)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_pick_selection_changed(self):
        """Called when the timeline selection changes while in pick mode."""
        purpose = self._clip_pick_purpose
        if not purpose:
            return
        try:
            from classes.app import get_app
            from classes.query import Clip
            import json as _json
            win = getattr(get_app(), "window", None)
            if not win:
                return
            try:
                win.SelectionChanged.disconnect(self._on_pick_selection_changed)
            except Exception:
                pass
            selected_ids = list(getattr(win, "selected_clips", []) or [])
            if not selected_ids:
                return
            clip_obj = Clip.get(id=str(selected_ids[0]))
            if not clip_obj:
                return
            data = clip_obj.data if isinstance(getattr(clip_obj, "data", None), dict) else {}
            title = data.get("title") or data.get("label") or "Clip"
            result = {
                "id": str(selected_ids[0]),
                "title": title,
                "start": float(data.get("start", 0.0) or 0.0),
                "end": float(data.get("end", 0.0) or 0.0),
            }
            self._clip_pick_purpose = None
            self._run_js(f"window.chatSetPickResult({_json.dumps(result)});")
        except Exception as exc:
            log.error("AIChat: _on_pick_selection_changed: %s", exc)

    def _build_clip_context_from_data(self, data: dict) -> tuple[str, str]:
        """Build a [Selected timeline clip context] block from a JS tag data dict."""
        title = data.get("title", "Selected Clip")
        clip_start = float(data.get("start", 0.0))
        clip_end = float(data.get("end", 0.0))
        context = (
            "[Selected timeline clip context]\n"
            f"title: {title}\n"
            f"source_window_seconds: {clip_start:.3f} to {clip_end:.3f}\n"
            f"source_window_mmss: {_format_mmss(clip_start)} to {_format_mmss(clip_end)}\n"
            "[/Selected timeline clip context]"
        )
        summary = f"{title} ({_format_mmss(clip_start)}–{_format_mmss(clip_end)})"
        return context, summary

    def _build_transition_clip_context(self, data: dict) -> tuple[str, str]:
        """Build context for generate_transition_clip_tool from a JS transition tag dict."""
        clip_a = data.get("clipA") or {}
        clip_b = data.get("clipB") or {}
        a_id = clip_a.get("id", "")
        b_id = clip_b.get("id", "")
        a_title = clip_a.get("title", "Clip A")
        b_title = clip_b.get("title", "Clip B")
        context = (
            "[Transition clips context]\n"
            f"clip_a_id: {a_id}\n"
            f"clip_a_title: {a_title}\n"
            f"clip_b_id: {b_id}\n"
            f"clip_b_title: {b_title}\n"
            "Call generate_transition_clip_tool with the clip_a_id and clip_b_id values above.\n"
            "[/Transition clips context]"
        )
        summary = f"Transition: {a_title} → {b_title}"
        return context, summary

    def _augment_text_with_context(self, text: str, context_json: str = "") -> tuple[str, str]:
        """Augment text using the structured tag context (JS tags) or fall back to auto-attach."""
        import json as _json
        ctx_data: dict = {}
        if context_json:
            try:
                ctx_data = _json.loads(context_json)
            except Exception:
                pass

        ctx_type = ctx_data.get("type", "")
        if ctx_type == "selected_clip":
            ctx, summary = self._build_clip_context_from_data(ctx_data)
            return f"{ctx}\n\n{text}", summary
        if ctx_type == "transition_clips":
            ctx, summary = self._build_transition_clip_context(ctx_data)
            return f"{ctx}\n\n{text}", summary

        # No structured tag — fall back to token-replacement / auto-attach behaviour
        return self._augment_text_with_clip_context(text)

    def _handle_web_send_message(self, text: str, model_id: str, context_json: str = ""):
        """Handle send from CEP UI (same logic as send_message but with args)."""
        if self.is_processing:
            self._run_js("alert('Processing previous message...');")
            return
        if not text:
            return
        worker = self._active_session().get("worker")
        if worker is None:
            return
        self._add_user_msg(text)
        if self._try_local_command(text):
            return
        self._request_preamble_summary(text)
        augmented_text, attached_summary = self._augment_text_with_context(text, context_json)
        augmented_text = self._prepend_editor_snapshot(augmented_text)
        if attached_summary:
            self._add_system_msg(f"Context attached: {attached_summary}")
        self._set_processing_ui(True)
        QMetaObject.invokeMethod(
            worker,
            "run_request",
            Qt.QueuedConnection,
            Q_ARG(str, augmented_text),
            Q_ARG(str, model_id),
        )

    def _stop_all_threads(self):
        """Cleanly stop all session worker threads. Safe to call more than once."""
        # Mark all workers as stopping FIRST so that when cancel_current_request()
        # closes the WebSocket, the worker's run_request slot sees _stopping=True
        # and returns silently instead of trying to fall back to REST or emit signals
        # into a Qt stack that is already being torn down.
        for sess in list(self._sessions.values()):
            worker = sess.get("worker")
            if worker:
                worker._stopping = True
        try:
            from classes.api_client import get_backend_client
            get_backend_client().cancel_current_request()
        except Exception:
            pass
        for sess in list(self._sessions.values()):
            thread = sess.get("thread")
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(2000):
                    log.warning("AI chat thread did not stop within 2 s; terminating")
                    thread.terminate()
                    thread.wait(500)

    def closeEvent(self, event):
        """Stop all AI worker threads when the dock is explicitly closed."""
        self._stop_all_threads()
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
        """Populate model combo from the backend API."""
        models = []
        default_id = ""
        try:
            client = get_backend_client()
            api_resp = client.list_models()
            default_id = api_resp.get("default_model_id", "")
            models = [(m["id"], m["name"]) for m in api_resp.get("models", [])]
        except Exception:
            log.warning("Failed to fetch models from backend")
        if not models:
            self.model_combo.addItem("No AI providers loaded", "")
            return
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

    _WATCH_CLIP_PATTERNS = [
        "watch clip", "view clip", "show clip", "play clip",
        "play the feral", "show the feral", "watch the feral",
        "play the trailer", "show me the clip", "show me the trailer",
        "load the feral", "open the feral",
    ]

    def _try_local_command(self, text: str) -> bool:
        """Execute certain commands locally without sending to the backend.
        Returns True if the command was handled and no backend call is needed.
        """
        lower = text.lower().strip()
        if any(pat in lower for pat in self._WATCH_CLIP_PATTERNS):
            self._add_system_msg("Loading Feral trailer and starting playback...")
            try:
                from classes.tool_handlers import execute_tool
                result = execute_tool("watch_clip_tool", {})
                self._add_assistant_msg(result)
            except Exception as exc:
                self._add_assistant_msg(f"Error: {exc}")
            self._set_processing_ui(False)
            return True
        return False

    def send_message(self):
        if self.is_processing:
            QMessageBox.warning(self, "Wait", "Processing previous message...")
            return
        text = self.msg_input.toPlainText().strip()
        if not text:
            return
        self._add_user_msg(text)
        self.msg_input.clear()
        if self._try_local_command(text):
            return
        self._request_preamble_summary(text)
        augmented_text, attached_summary = self._augment_text_with_clip_context(text)
        augmented_text = self._prepend_editor_snapshot(augmented_text)
        if attached_summary:
            self._add_system_msg(f"Context attached: {attached_summary}")
        self._set_processing_ui(True)
        model_id = self.model_combo.currentData()
        if not model_id and self.model_combo.count():
            model_id = self.model_combo.currentText()
        model_id_str = model_id if model_id else ""
        worker = self._active_session().get("worker")
        if worker:
            QMetaObject.invokeMethod(
                worker,
                "run_request",
                Qt.QueuedConnection,
                Q_ARG(str, augmented_text),
                Q_ARG(str, model_id_str),
            )
        self.msg_input.setFocus()

    def _set_processing_ui(self, processing: bool):
        """Update Send/Cancel visibility and enabled state."""
        self.is_processing = processing
        sess = self._active_session()
        if sess:
            sess["processing"] = processing
        if self._use_web_ui:
            self._run_js("setProcessing(%s);" % ("true" if processing else "false"))
            # Refresh tab bar so per-session processing indicators stay in sync.
            self._push_tabs_to_js()
            return
        # Widget mode: rebuild tabs so the active processing indicator updates.
        if getattr(self, "_widget_tabs_layout", None):
            self._rebuild_widget_tabs()
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

    @pyqtSlot(str)
    def _on_response_ready(self, text: str):
        sid = getattr(self.sender(), "_session_id", self._active_sid)
        if sid in self._sessions:
            self._sessions[sid]["processing"] = False
            if sid == self._active_sid:
                self._sessions[sid]["unread"] = False
            else:
                # Widget mode uses an in-Python unread flag; WebEngine unread is
                # tracked inside chat.js.
                if not self._use_web_ui:
                    self._sessions[sid]["unread"] = True
        if sid == self._active_sid:
            self._add_assistant_msg(text)
            self._set_processing_ui(False)
        else:
            # Background session — store message and notify JS for unread badge
            if sid in self._sessions:
                html_body = _markdown_to_html(text)
                self._sessions[sid]["messages"].append(("assistant", html_body, True))
                self._run_js(
                    "if(window.onBackgroundResponse) window.onBackgroundResponse(%s, %s);"
                    % (json.dumps(sid), json.dumps(html_body))
                )
            if self._use_web_ui:
                self._push_tabs_to_js()
            else:
                self._rebuild_widget_tabs()

    @pyqtSlot(str)
    def _on_error(self, text: str):
        sid = getattr(self.sender(), "_session_id", self._active_sid)
        if sid in self._sessions:
            self._sessions[sid]["processing"] = False
        if sid == self._active_sid:
            log.debug("ai_chat_ui _on_error: %s", text[:80] if text else "")
            self._add_system_msg("Error: %s" % text)
            self._set_processing_ui(False)

    def clear_chat(self):
        reply = QMessageBox.question(
            self, "Clear", "Clear chat?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._first_prompt_summary = None
            sess = self._active_session()
            if sess:
                sess["messages"] = []
                sess["first_prompt_summary"] = None
                sess["unread"] = False
                worker = sess.get("worker")
                if worker:
                    QMetaObject.invokeMethod(worker, "clear_session", Qt.QueuedConnection)
            if self._use_web_ui:
                self._run_js("clearMessages();")
                self._push_tabs_to_js()
            else:
                self.chat_box.clear()
                self._rebuild_widget_tabs()
            self._update_preamble()
            self._add_system_msg("Chat cleared. Ask anything about your project or editing.")

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
            else:
                safe = html.escape(text).replace("\n", "<br/>")
                html_body = "<p>" + safe + "</p>"
            # Store for replay when the user switches back to this tab
            sess = self._active_session()
            if sess is not None:
                sess["messages"].append((role, html_body, is_assistant))
            self._run_js("appendMessage(%s, %s, %s);" % (
                json.dumps(role),
                json.dumps(html_body),
                "true" if is_assistant else "false",
            ))
            return
        if is_assistant:
            html_body = _markdown_to_html(text)
        else:
            safe = html.escape(text).replace("\n", "<br/>")
            html_body = "<p>" + safe + "</p>"

        # Store for replay when switching sessions (widget mode).
        sess = self._active_session()
        if sess is not None:
            sess["messages"].append((role, html_body, is_assistant))

        self._display_stored_msg_widget(role, html_body, is_assistant)
