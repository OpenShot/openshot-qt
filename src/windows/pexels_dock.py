"""
Pexels stock-video search dock for Zenvi.

Search bar (QLineEdit + magnifying-glass button) → results grid (thumbnail +
duration overlay) → click a card to download and import into Project Files.
"""

import os
from typing import List, Dict, Any

from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer, QRunnable, QThreadPool,
    pyqtSlot, QObject,
)
from PyQt5.QtGui import QPixmap, QColor, QPainter, QFont, QPen, QBrush
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QGridLayout,
    QLabel, QSizePolicy, QFrame, QProgressBar, QApplication,
)

from classes.logger import log


# ── Async helpers ─────────────────────────────────────────────────────────────

class _SearchWorker(QObject):
    """Runs pexels_search on a background thread."""
    finished = pyqtSignal(dict)   # payload: PexelsSearchResponse dict

    def __init__(self, query: str, page: int = 1):
        super().__init__()
        self._query = query
        self._page = page

    @pyqtSlot()
    def run(self):
        try:
            from classes.api_client import get_backend_client
            result = get_backend_client().pexels_search(self._query, per_page=16, page=self._page)
        except Exception as exc:
            result = {"videos": [], "error": str(exc)}
        self.finished.emit(result)


class _DownloadWorker(QObject):
    """Downloads a single Pexels video on a background thread."""
    finished = pyqtSignal(int, str, str)   # video_id, local_path, error

    def __init__(self, video_id: int, link: str, filename: str):
        super().__init__()
        self._video_id = video_id
        self._link = link
        self._filename = filename

    @pyqtSlot()
    def run(self):
        try:
            from classes.api_client import get_backend_client
            result = get_backend_client().pexels_download(
                self._video_id, self._link, self._filename
            )
            local_path = result.get("local_path", "")
            error = result.get("error", "")
        except Exception as exc:
            local_path, error = "", str(exc)
        self.finished.emit(self._video_id, local_path, error)


class _ThumbnailRunnable(QRunnable):
    """Fetches a thumbnail URL and emits the result via a signal carrier."""

    class _Signals(QObject):
        ready = pyqtSignal(int, QPixmap)   # video_id, pixmap

    def __init__(self, video_id: int, url: str):
        super().__init__()
        self.signals = _ThumbnailRunnable._Signals()
        self._video_id = video_id
        self._url = url

    def run(self):
        try:
            import requests as _req
            resp = _req.get(
                self._url,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
                timeout=10,
            )
            resp.raise_for_status()
            pix = QPixmap()
            pix.loadFromData(resp.content)
            if not pix.isNull():
                self.signals.ready.emit(self._video_id, pix)
        except Exception as exc:
            log.warning("Pexels thumbnail fetch failed (%s): %s", self._url, exc)


# ── Video card widget ─────────────────────────────────────────────────────────

CARD_W = 160
CARD_H = 108


class _VideoCard(QFrame):
    """A single result card: thumbnail + duration badge + hover overlay."""

    clicked = pyqtSignal(dict)   # emits the video dict

    def __init__(self, video: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._video = video
        self._thumb: QPixmap | None = None
        self._downloading = False

        self.setFixedSize(CARD_W, CARD_H)
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)

        # Duration label (bottom-left overlay)
        dur = video.get("duration", 0)
        mins, secs = divmod(int(dur), 60)
        self._dur_text = f"{mins}:{secs:02d}"

        # Loading indicator
        self._spinner = QLabel(self)
        self._spinner.setText("⏳")
        self._spinner.setAlignment(Qt.AlignCenter)
        self._spinner.setStyleSheet("color: #8a8a8a; font-size: 18px;")
        self._spinner.setGeometry(0, 0, CARD_W, CARD_H)

        self._status_label = QLabel("", self)
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "color: #d4d4d4; font-size: 10px; background: transparent;"
        )
        self._status_label.setGeometry(4, CARD_H // 2, CARD_W - 8, CARD_H // 2)
        self._status_label.hide()

        self.setToolTip(f"User: {video.get('user_name','')}\n{video.get('width',0)}×{video.get('height',0)}  {self._dur_text}")

    def set_thumbnail(self, pix: QPixmap):
        self._thumb = pix.scaled(CARD_W, CARD_H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self._spinner.hide()
        self.update()

    def set_downloading(self, downloading: bool):
        self._downloading = downloading
        self._status_label.setText("Downloading…" if downloading else "")
        self._status_label.setVisible(downloading)
        self.update()

    def set_done(self):
        self._downloading = False
        self._status_label.setText("✓ Added")
        self._status_label.setStyleSheet(
            "color: #4d9cf6; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self._status_label.show()
        QTimer.singleShot(2500, self._status_label.hide)
        self.update()

    def set_error(self, msg: str):
        self._downloading = False
        self._status_label.setText(f"Error: {msg[:40]}")
        self._status_label.setStyleSheet(
            "color: #ef4444; font-size: 10px; background: transparent;"
        )
        self._status_label.show()
        self.update()

    # ── Qt overrides ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()

        # Background
        painter.fillRect(rect, QColor("#1a1a1a"))

        # Thumbnail
        if self._thumb:
            # Centre-crop
            tw, th = self._thumb.width(), self._thumb.height()
            x = (tw - CARD_W) // 2
            y = (th - CARD_H) // 2
            painter.drawPixmap(rect, self._thumb, self._thumb.rect().adjusted(x, y, -(tw - CARD_W - x), -(th - CARD_H - y)))

        # Dark overlay when downloading
        if self._downloading:
            painter.fillRect(rect, QColor(0, 0, 0, 140))

        # Duration badge
        dur_rect = self.rect().adjusted(0, CARD_H - 22, 0, 0)
        painter.fillRect(dur_rect, QColor(0, 0, 0, 160))
        painter.setPen(QColor("#d4d4d4"))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(dur_rect.adjusted(4, 0, -4, -2), Qt.AlignLeft | Qt.AlignVCenter, self._dur_text)

        # Resolution badge (bottom-right)
        res_text = f"{self._video.get('width',0) // max(self._video.get('height',1), 1) >= 16 // 9 and self._video.get('height',0) or self._video.get('height',0)}p"
        h = self._video.get("height", 0)
        if h >= 2160:
            res_text = "4K"
        elif h >= 1080:
            res_text = "HD"
        elif h >= 720:
            res_text = "720p"
        else:
            res_text = f"{h}p"
        painter.drawText(dur_rect.adjusted(4, 0, -4, -2), Qt.AlignRight | Qt.AlignVCenter, res_text)

        # Hover border
        if self.underMouse():
            pen = QPen(QColor("#4d9cf6"), 2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._downloading:
            self.clicked.emit(self._video)


# ── Main dock ─────────────────────────────────────────────────────────────────

class PexelsDock(QDockWidget):
    """Pexels stock-video search dock."""

    def __init__(self, parent=None):
        super().__init__("Pexels Stock Videos", parent)
        self.setObjectName("PexelsDock")
        self.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        self.setMinimumWidth(300)
        self.resize(340, 520)

        self._search_thread: QThread | None = None
        self._dl_thread: QThread | None = None
        self._cards: Dict[int, _VideoCard] = {}
        self._thumb_pool = QThreadPool.globalInstance()

        self._build_ui()

        # Clean up background threads on app quit
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._cleanup_threads)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("PexelsDockContents")
        root.setStyleSheet("""
            QWidget#PexelsDockContents { background: #0d0d0d; }
            QLineEdit {
                background: #1a1a1a;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 4px;
                color: #d4d4d4;
                padding: 4px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #4d9cf6; }
            QPushButton#searchBtn {
                background: #4d9cf6;
                border: none;
                border-radius: 4px;
                color: #fff;
                font-size: 14px;
                padding: 4px 10px;
                min-width: 30px;
            }
            QPushButton#searchBtn:hover  { background: #3b8fe8; }
            QPushButton#searchBtn:pressed { background: #2d7dd4; }
            QLabel#statusLabel { color: #8a8a8a; font-size: 11px; }
            QScrollArea { background: #0d0d0d; border: none; }
            QWidget#scrollContents { background: #0d0d0d; }
            QPushButton#loadMoreBtn {
                background: #252525;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 4px;
                color: #d4d4d4;
                padding: 6px;
                font-size: 11px;
                margin: 6px;
            }
            QPushButton#loadMoreBtn:hover { background: #2e2e2e; border-color: #4d9cf6; }
        """)

        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        # ── Search bar ────────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search Pexels videos…")
        self._search_input.returnPressed.connect(self._on_search)
        bar.addWidget(self._search_input)

        self._search_btn = QPushButton("🔍")
        self._search_btn.setObjectName("searchBtn")
        self._search_btn.setToolTip("Search")
        self._search_btn.clicked.connect(self._on_search)
        bar.addWidget(self._search_btn)
        vbox.addLayout(bar)

        # ── Status label ──────────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignCenter)
        vbox.addWidget(self._status_label)

        # ── Progress bar (hidden normally) ────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: #1a1a1a; border: none; border-radius: 1px; }"
            "QProgressBar::chunk { background: #4d9cf6; border-radius: 1px; }"
        )
        self._progress.hide()
        vbox.addWidget(self._progress)

        # ── Results scroll area ───────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._grid_container = QWidget()
        self._grid_container.setObjectName("scrollContents")
        self._grid = QGridLayout(self._grid_container)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setSpacing(6)
        self._scroll.setWidget(self._grid_container)
        vbox.addWidget(self._scroll, 1)

        # ── Load more ─────────────────────────────────────────────────────────
        self._load_more_btn = QPushButton("Load more…")
        self._load_more_btn.setObjectName("loadMoreBtn")
        self._load_more_btn.hide()
        self._load_more_btn.clicked.connect(self._on_load_more)
        vbox.addWidget(self._load_more_btn)

        self.setWidget(root)

        # State
        self._current_query = ""
        self._current_page = 1
        self._total_results = 0

    # ── Search flow ───────────────────────────────────────────────────────────

    def _on_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._current_query = query
        self._current_page = 1
        self._clear_grid()
        self._cards.clear()
        self._load_more_btn.hide()
        self._run_search(query, page=1)

    def _on_load_more(self):
        self._current_page += 1
        self._run_search(self._current_query, page=self._current_page)

    def _run_search(self, query: str, page: int):
        self._set_searching(True)

        self._search_thread = QThread()
        self._worker = _SearchWorker(query, page)
        self._worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_search_done)
        self._worker.finished.connect(self._search_thread.quit)
        self._search_thread.start()

    @pyqtSlot(dict)
    def _on_search_done(self, data: dict):
        self._set_searching(False)
        error = data.get("error")
        if error:
            self._status_label.setText(f"Error: {error}")
            return

        videos = data.get("videos", [])
        self._total_results = data.get("total_results", 0)

        if not videos:
            self._status_label.setText("No results found.")
            return

        self._status_label.setText(
            f"{self._total_results:,} results  •  page {self._current_page}"
        )

        # Add cards
        existing = self._grid.count()
        cols = max(1, (self.width() - 24) // (CARD_W + 6))
        for idx, video in enumerate(videos):
            vid_id = video.get("id", idx)
            card = _VideoCard(video)
            card.clicked.connect(self._on_card_clicked)
            self._cards[vid_id] = card
            pos = existing + idx
            row, col = divmod(pos, cols)
            self._grid.addWidget(card, row, col)

            # Prefer video_pictures[nr==0], fall back to image field
            thumb_url = ""
            pictures = video.get("video_pictures", [])
            if pictures:
                # find nr==0, else just take the first entry
                pic0 = next((p for p in pictures if p.get("nr") == 0), pictures[0])
                thumb_url = pic0.get("picture", "")
            if not thumb_url:
                thumb_url = video.get("image", "")
            if thumb_url:
                runnable = _ThumbnailRunnable(vid_id, thumb_url)
                runnable.signals.ready.connect(self._on_thumbnail_ready)
                self._thumb_pool.start(runnable)

        # Show "Load more" if more pages exist
        shown = self._current_page * data.get("per_page", 15)
        if shown < self._total_results:
            self._load_more_btn.show()
        else:
            self._load_more_btn.hide()

    @pyqtSlot(int, QPixmap)
    def _on_thumbnail_ready(self, video_id: int, pix: QPixmap):
        card = self._cards.get(video_id)
        if card:
            card.set_thumbnail(pix)

    # ── Download flow ─────────────────────────────────────────────────────────

    @pyqtSlot(dict)
    def _on_card_clicked(self, video: dict):
        vid_id = video.get("id", 0)
        card = self._cards.get(vid_id)
        if card:
            card.set_downloading(True)

        # Pick best HD file (prefer hd, then sd)
        files = video.get("video_files", [])
        mp4_files = [f for f in files if "mp4" in f.get("file_type", "").lower()]
        hd_files = [f for f in mp4_files if f.get("quality") == "hd"]
        chosen = hd_files[0] if hd_files else (mp4_files[0] if mp4_files else None)
        if not chosen:
            if card:
                card.set_error("No downloadable MP4 found")
            return

        link = chosen.get("link", "")
        filename = f"pexels_{vid_id}"

        self._dl_thread = QThread()
        self._dl_worker = _DownloadWorker(vid_id, link, filename)
        self._dl_worker.moveToThread(self._dl_thread)
        self._dl_thread.started.connect(self._dl_worker.run)
        self._dl_worker.finished.connect(self._on_download_done)
        self._dl_worker.finished.connect(self._dl_thread.quit)
        self._dl_thread.start()

    @pyqtSlot(int, str, str)
    def _on_download_done(self, video_id: int, local_path: str, error: str):
        card = self._cards.get(video_id)
        if error or not local_path:
            log.error("Pexels download error: %s", error)
            if card:
                card.set_error(error or "Download failed")
            return

        if card:
            card.set_done()

        # Add to Project Files
        try:
            from classes.app import get_app
            app = get_app()
            if app and hasattr(app, "window") and app.window:
                app.window.files_model.add_files([local_path])
                log.info("Pexels video added to Project Files: %s", local_path)
        except Exception as exc:
            log.error("Failed to add Pexels video to Project Files: %s", exc)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_searching(self, active: bool):
        self._search_btn.setEnabled(not active)
        self._search_input.setEnabled(not active)
        if active:
            self._progress.show()
        else:
            self._progress.hide()

    def _clear_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._status_label.setText("")

    def _cleanup_threads(self):
        for t in (self._search_thread, self._dl_thread):
            if t and t.isRunning():
                t.quit()
                t.wait(2000)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-flow grid on resize
        if self._cards:
            cols = max(1, (self.width() - 24) // (CARD_W + 6))
            widgets = []
            while self._grid.count():
                item = self._grid.takeAt(0)
                if item and item.widget():
                    widgets.append(item.widget())
            for idx, w in enumerate(widgets):
                row, col = divmod(idx, cols)
                self._grid.addWidget(w, row, col)
