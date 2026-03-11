"""
Zenvi login window — minimal, Cursor-inspired sign-in dialog.

Flow:
  1. Window opens, immediately starts the browser-based auth flow
  2. User authenticates in their browser
  3. Window detects the completed session (via polling) and auto-closes
  4. Emits auth_completed(session_dict) so the main window can refresh

Usage:
    from windows.login_window import LoginWindow

    dlg = LoginWindow(parent=main_window)
    dlg.auth_completed.connect(on_signed_in)
    dlg.exec_()
"""

import logging

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from classes.auth_manager import AuthManager

log = logging.getLogger(__name__)


# ── Background polling worker ──────────────────────────────────────────────────

class _PollWorker(QObject):
    """Runs AuthManager.poll_for_session() in a QThread and emits signals."""

    succeeded = pyqtSignal(dict)
    timed_out = pyqtSignal()

    def __init__(self, auth_manager: AuthManager, state: str) -> None:
        super().__init__()
        self._auth = auth_manager
        self._state = state

    def start(self) -> None:
        self._auth.poll_for_session(
            state=self._state,
            on_success=lambda s: self.succeeded.emit(s),
            on_timeout=lambda: self.timed_out.emit(),
        )


# ── Login dialog ───────────────────────────────────────────────────────────────

class LoginWindow(QDialog):
    """
    Minimal dark sign-in dialog.  Opens a browser tab, waits for the user to
    authenticate, then closes itself automatically.
    """

    auth_completed = pyqtSignal(dict)   # emits session dict on success
    auth_cancelled = pyqtSignal()       # emits when the user cancels

    # Internal thread-safe bridges (background thread → Qt main thread)
    _sig_success = pyqtSignal(dict)
    _sig_timeout = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._auth = AuthManager.instance()
        self._thread: QThread | None = None
        self._worker: _PollWorker | None = None

        self._build_ui()
        self._sig_success.connect(self._on_success)
        self._sig_timeout.connect(self._on_timeout)

        # Kick off the auth flow immediately after the dialog shows
        QTimer.singleShot(0, self._start_flow)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Sign in to Zenvi")
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #0A0A0A;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setContentsMargins(44, 48, 44, 44)
        root.setSpacing(0)

        # ── Wordmark ───────────────────────────────────────────────────────────
        wordmark = QLabel("Zenvi")
        wordmark.setAlignment(Qt.AlignCenter)
        wordmark.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #ffffff; margin-bottom: 6px;"
        )
        root.addWidget(wordmark)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.06); margin: 14px 0 18px 0;")
        root.addWidget(sep)

        # ── Status label ──────────────────────────────────────────────────────
        self._status = QLabel("Opening browser…")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            "font-size: 14px; font-weight: 500; color: #ffffff; margin-bottom: 8px;"
        )
        root.addWidget(self._status)

        self._sub = QLabel("Complete sign-in in your browser.\nThis window will close automatically.")
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setWordWrap(True)
        self._sub.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.38); line-height: 1.7;"
        )
        root.addWidget(self._sub)

        root.addStretch(1)

        # ── Cancel button ─────────────────────────────────────────────────────
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedSize(120, 36)
        self._cancel_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 8px;
                color: rgba(255,255,255,0.45);
                font-size: 13px;
            }
            QPushButton:hover {
                border-color: rgba(255,255,255,0.2);
                color: rgba(255,255,255,0.75);
            }
            QPushButton:pressed {
                background: rgba(255,255,255,0.04);
            }
            """
        )
        root.addWidget(self._cancel_btn, alignment=Qt.AlignCenter)

    # ── Auth flow ──────────────────────────────────────────────────────────────

    def _start_flow(self) -> None:
        """Open the browser and begin polling."""
        state = self._auth.start_auth_flow()

        # Update label once the browser has had a moment to open
        QTimer.singleShot(1400, lambda: self._status.setText("Waiting for authentication…"))

        # Spawn polling in a QThread
        self._thread = QThread(self)
        self._worker = _PollWorker(self._auth, state)
        self._worker.moveToThread(self._thread)
        self._worker.succeeded.connect(lambda s: self._sig_success.emit(s))
        self._worker.timed_out.connect(self._sig_timeout)
        self._thread.started.connect(self._worker.start)
        self._thread.start()

    def _stop_thread(self) -> None:
        self._auth.cancel_poll()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_success(self, session: dict) -> None:
        log.info("Desktop auth succeeded.")
        self._stop_thread()
        self.auth_completed.emit(session)
        self.accept()

    def _on_timeout(self) -> None:
        log.warning("Desktop auth timed out.")
        self._status.setText("Authentication timed out")
        self._sub.setText("Please close this window and try again.")
        self._cancel_btn.setText("Close")

    def _cancel(self) -> None:
        self._stop_thread()
        self.auth_cancelled.emit()
        self.reject()

    def closeEvent(self, event) -> None:
        self._stop_thread()
        event.accept()
