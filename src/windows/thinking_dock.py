"""
Thinking Dock Widget

Real-time display of director thinking, analysis, debate, and voting.
Shows the collaborative decision-making process as it happens.
"""

from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG
from PyQt5.QtWidgets import QDockWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
import json
import time
from classes.logger import log


class ThinkingBridge(QObject):
    """Bridge for bidirectional Python↔JavaScript communication"""

    # Signals TO JavaScript (emit from Python)
    messagePushed = pyqtSignal(str)  # JSON message
    phaseChanged = pyqtSignal(str)   # Phase name

    # Signals FROM JavaScript (slots called by JS)
    clearRequested = pyqtSignal()
    pauseRequested = pyqtSignal()

    @pyqtSlot()
    def clear(self):
        """User clicked clear button"""
        self.clearRequested.emit()

    @pyqtSlot()
    def pause(self):
        """User clicked pause button"""
        self.pauseRequested.emit()


class ThinkingDockWidget(QDockWidget):
    """Real-time display of director thinking and communication"""

    # Public signals
    pause_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Director Thinking", parent)
        self.setObjectName("thinkingDock")
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        # Create web view
        self.web_view = QWebEngineView()

        # Create bridge
        self.bridge = ThinkingBridge()
        self.bridge.clearRequested.connect(self._clear)
        self.bridge.pauseRequested.connect(self.pause_requested)

        # Setup web channel
        self.channel = QWebChannel()
        self.channel.registerObject("thinkingBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load HTML UI
        self._load_html()
        self.setWidget(self.web_view)
        self.setMinimumWidth(350)

    def _load_html(self):
        """Load the thinking UI HTML"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Director Thinking</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            font-size: 13px;
            line-height: 1.5;
        }

        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        .header {
            padding: 12px 16px;
            background: #252526;
            border-bottom: 1px solid #3c3c3c;
            flex-shrink: 0;
        }

        .phase {
            font-size: 14px;
            font-weight: 600;
            color: #4ec9b0;
            display: flex;
            align-items: center;
        }

        .phase-icon {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4ec9b0;
            margin-right: 8px;
            animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }

        .message {
            margin: 8px 0;
            padding: 10px 12px;
            background: #2d2d30;
            border-left: 3px solid #007acc;
            border-radius: 4px;
            animation: slideIn 0.2s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-10px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        .message.analysis {
            border-color: #4ec9b0;
            background: #1a2d2d;
        }

        .message.debate {
            border-color: #dcdcaa;
            background: #2d2d1a;
        }

        .message.voting {
            border-color: #c586c0;
            background: #2d1a2d;
        }

        .message.decision {
            border-color: #4fc1ff;
            background: #1a2a2d;
        }

        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
            align-items: center;
        }

        .message-role {
            font-weight: 600;
            color: #569cd6;
            font-size: 12px;
        }

        .message-time {
            font-size: 11px;
            color: #858585;
        }

        .message-content {
            font-size: 13px;
            line-height: 1.5;
            color: #cccccc;
        }

        .controls {
            padding: 8px 12px;
            border-top: 1px solid #3c3c3c;
            background: #252526;
            flex-shrink: 0;
            display: flex;
            gap: 8px;
        }

        button {
            padding: 6px 12px;
            background: #0e639c;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: background 0.2s;
        }

        button:hover {
            background: #1177bb;
        }

        button:active {
            background: #0d5a8c;
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #858585;
            text-align: center;
            padding: 20px;
        }

        .empty-icon {
            font-size: 48px;
            margin-bottom: 12px;
            opacity: 0.5;
        }

        .empty-text {
            font-size: 14px;
        }

        /* Scrollbar styling */
        .messages::-webkit-scrollbar {
            width: 8px;
        }

        .messages::-webkit-scrollbar-track {
            background: #1e1e1e;
        }

        .messages::-webkit-scrollbar-thumb {
            background: #424242;
            border-radius: 4px;
        }

        .messages::-webkit-scrollbar-thumb:hover {
            background: #4e4e4e;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="phase" id="phase">
                <span class="phase-icon"></span>
                Idle
            </div>
        </div>
        <div id="messages" class="messages">
            <div class="empty-state">
                <div class="empty-icon">💭</div>
                <div class="empty-text">Waiting for director analysis...</div>
            </div>
        </div>
        <div class="controls">
            <button onclick="thinkingBridge.clear()">Clear</button>
            <button onclick="thinkingBridge.pause()">Pause</button>
        </div>
    </div>

    <script src="qrc:/qtwebchannel/qwebchannel.js"></script>
    <script>
        let messagesEl = document.getElementById('messages');
        let phaseEl = document.getElementById('phase');
        let messageCount = 0;

        // Initialize QWebChannel
        if (window.qt && window.qt.webChannelTransport) {
            new QWebChannel(window.qt.webChannelTransport, function(channel) {
                window.thinkingBridge = channel.objects.thinkingBridge;

                // Listen for new messages from Python
                thinkingBridge.messagePushed.connect(function(jsonStr) {
                    try {
                        let msg = JSON.parse(jsonStr);
                        addMessage(msg);
                    } catch (e) {
                        console.error('Failed to parse message:', e);
                    }
                });

                // Listen for phase changes
                thinkingBridge.phaseChanged.connect(function(phase) {
                    phaseEl.innerHTML = '<span class="phase-icon"></span>' + escapeHtml(phase);
                });
            });
        }

        function addMessage(msg) {
            // Remove empty state if present
            if (messageCount === 0) {
                messagesEl.innerHTML = '';
            }
            messageCount++;

            let div = document.createElement('div');
            div.className = 'message ' + (msg.type || 'general');

            let timestamp = new Date(msg.timestamp * 1000).toLocaleTimeString();

            div.innerHTML =
                '<div class="message-header">' +
                '<span class="message-role">' + escapeHtml(msg.role) + '</span>' +
                '<span class="message-time">' + escapeHtml(timestamp) + '</span>' +
                '</div>' +
                '<div class="message-content">' + escapeHtml(msg.content) + '</div>';

            messagesEl.appendChild(div);

            // Auto-scroll to bottom
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function escapeHtml(text) {
            let div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function clearMessages() {
            messagesEl.innerHTML = '<div class="empty-state">' +
                '<div class="empty-icon">💭</div>' +
                '<div class="empty-text">Cleared</div>' +
                '</div>';
            messageCount = 0;
        }
    </script>
</body>
</html>"""
        self.web_view.setHtml(html)

    def add_message(self, role: str, content: str, msg_type: str = "general"):
        """
        Add a message to the thinking display (thread-safe).

        Args:
            role: Who is speaking (director name, "Orchestrator", etc.)
            content: Message content
            msg_type: Message type for styling ("analysis", "debate", "voting", "decision")
        """
        msg = json.dumps({
            "role": role,
            "content": content,
            "type": msg_type,
            "timestamp": time.time()
        })

        # Use QMetaObject.invokeMethod for thread-safe UI updates
        QMetaObject.invokeMethod(
            self, "_push_message",
            Qt.QueuedConnection,
            Q_ARG(str, msg)
        )

    @pyqtSlot(str)
    def _push_message(self, msg_json: str):
        """Push message to JavaScript (must run on main thread)"""
        self.bridge.messagePushed.emit(msg_json)

    def set_phase(self, phase: str):
        """
        Update the current phase display.

        Args:
            phase: Phase name (e.g., "Phase 1: Analysis", "Phase 2: Debate")
        """
        QMetaObject.invokeMethod(
            self, "_set_phase",
            Qt.QueuedConnection,
            Q_ARG(str, phase)
        )

    @pyqtSlot(str)
    def _set_phase(self, phase: str):
        """Set phase in UI (must run on main thread)"""
        self.bridge.phaseChanged.emit(phase)

    def clear(self):
        """Clear all messages"""
        self._run_js("clearMessages();")

    def _clear(self):
        """Internal clear handler"""
        self.clear()

    def _run_js(self, code: str):
        """Execute JavaScript safely"""
        if self.web_view and self.web_view.page():
            self.web_view.page().runJavaScript(code)
