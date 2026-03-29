"""
Director Selection Panel UI

PyQt dock widget with HTML/CSS/JS overlay for selecting and managing directors.
In the split architecture, director data is fetched from the zenvi-backend API.
"""

import os
import json
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt5.QtWidgets import QDockWidget, QWidget, QVBoxLayout
from classes.logger import log

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False
    log.warning("QtWebEngine not available - Director Panel UI will not work")


class DirectorPanelBridge(QObject):
    """
    Bridge between Python and JavaScript for director panel UI.

    Exposed to JavaScript via QWebChannel as 'directorPanelBridge'.
    """

    # Signals to JavaScript
    directorsLoaded = pyqtSignal(str)  # directors JSON array

    # Signals to Python
    directors_selected = pyqtSignal(str)  # selected director IDs as JSON array
    open_marketplace = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.directors = []

    @pyqtSlot(str)
    def deleteDirector(self, director_id: str):
        """Delete a director (called from JavaScript)."""
        try:
            # Delete from user config directory only
            user_dir = os.path.expanduser("~/.config/zenvi/directors")
            user_path = os.path.join(user_dir, f"{director_id}.director")

            if os.path.exists(user_path):
                os.remove(user_path)
                log.info(f"Deleted user director: {director_id}")
                # Reload directors after deletion
                self.loadDirectors()
            else:
                log.warning(f"Director not found or is a built-in: {director_id}")

        except Exception as e:
            log.error(f"Failed to delete director {director_id}: {e}", exc_info=True)

    @pyqtSlot()
    def loadDirectors(self):
        """Load available directors from backend API."""
        try:
            from classes.api_client import get_backend_client
            client = get_backend_client()
            try:
                import requests
                resp = requests.get(
                    f"{client.base_url}/api/v1/directors",
                    timeout=5,
                )
                if resp.status_code == 200:
                    directors_data = resp.json().get("directors", [])
                    self.directors = directors_data
                    directors_json = json.dumps(directors_data)
                    self.directorsLoaded.emit(directors_json)
                    log.info(f"Loaded {len(directors_data)} directors from backend")
                    return
            except Exception as api_err:
                log.warning(f"Backend directors API unavailable: {api_err}")

            # Fallback: load from local .director files
            self._load_local_directors()

        except Exception as e:
            log.error(f"Failed to load directors: {e}", exc_info=True)
            self.directorsLoaded.emit("[]")

    def _load_local_directors(self):
        """Load directors from local .director files as fallback."""
        directors_data = []

        # Check user directors directory
        user_dir = os.path.expanduser("~/.config/zenvi/directors")
        if os.path.isdir(user_dir):
            for fname in os.listdir(user_dir):
                if fname.endswith(".director"):
                    fpath = os.path.join(user_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        directors_data.append({
                            "id": data.get("id", fname.replace(".director", "")),
                            "name": data.get("name", fname),
                            "description": data.get("description", ""),
                            "author": data.get("author", ""),
                            "version": data.get("version", "1.0.0"),
                            "tags": data.get("tags", []),
                            "expertise": data.get("personality", {}).get("expertise_areas", []),
                            "focus": data.get("personality", {}).get("analysis_focus", []),
                        })
                    except Exception as e:
                        log.warning(f"Failed to load director file {fpath}: {e}")

        # Also check built-in directors
        from classes import info
        builtin_dir = os.path.join(info.PATH, "directors", "built_in")
        if os.path.isdir(builtin_dir):
            for fname in os.listdir(builtin_dir):
                if fname.endswith(".director"):
                    fpath = os.path.join(builtin_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        directors_data.append({
                            "id": data.get("id", fname.replace(".director", "")),
                            "name": data.get("name", fname),
                            "description": data.get("description", ""),
                            "author": data.get("author", ""),
                            "version": data.get("version", "1.0.0"),
                            "tags": data.get("tags", []),
                            "expertise": data.get("personality", {}).get("expertise_areas", []),
                            "focus": data.get("personality", {}).get("analysis_focus", []),
                        })
                    except Exception as e:
                        log.warning(f"Failed to load director file {fpath}: {e}")

        self.directors = directors_data
        directors_json = json.dumps(directors_data)
        self.directorsLoaded.emit(directors_json)
        log.info(f"Loaded {len(directors_data)} directors from local files")

    @pyqtSlot(str)
    def selectDirectors(self, director_ids_json: str):
        """
        Called from JavaScript when user clicks Analyze button.
        Sends the analysis request to the backend via the chat WebSocket.

        Args:
            director_ids_json: JSON array of director IDs
        """
        try:
            director_ids = json.loads(director_ids_json)
            log.info(f"Starting analysis with directors: {director_ids}")

            # Emit signal for any listeners
            self.directors_selected.emit(director_ids_json)

            # Send analysis request to backend via chat
            self._trigger_director_analysis(director_ids)

        except Exception as e:
            log.error(f"Failed to start director analysis: {e}", exc_info=True)

    def _trigger_director_analysis(self, director_ids):
        """
        Send a director analysis request to the backend.
        The backend handles orchestrator logic; we just send the message via chat.
        """
        try:
            from classes.app import get_app
            app = get_app()

            # Build a chat message that triggers director analysis
            directors_str = ", ".join(director_ids)
            message = f"Run director analysis with directors: {directors_str}. Analyze the current video project and suggest improvements."

            # Send through the AI chat UI
            if hasattr(app, 'window') and hasattr(app.window, 'dockAIChat'):
                app.window.dockAIChat.send_message(message)
                log.info(f"Sent director analysis request to backend for {len(director_ids)} directors")
            else:
                log.warning("AI Chat dock not available for sending director analysis request")

        except Exception as e:
            log.error(f"Failed to trigger director analysis: {e}", exc_info=True)

    @pyqtSlot()
    def openMarketplace(self):
        """Called from JavaScript when user clicks Browse Marketplace."""
        log.info("Opening marketplace")
        self.open_marketplace.emit()


class DirectorPanelDockWidget(QDockWidget):
    """
    Dock widget for selecting directors.

    Uses QWebEngineView with HTML/CSS/JS for modern, card-based UI.
    """

    # Signals
    directors_selected = pyqtSignal(list)  # List of director IDs

    def __init__(self, parent=None):
        super().__init__("Directors", parent)

        self.bridge = None
        self.web_view = None

        self.setObjectName("director_panel_dock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with web view."""
        if not _WEBENGINE_AVAILABLE:
            # Fallback: simple label
            from PyQt5.QtWidgets import QLabel
            label = QLabel("QtWebEngine not available.\nDirector Panel requires QtWebEngine.")
            label.setAlignment(Qt.AlignCenter)
            self.setWidget(label)
            return

        # Create web view
        self.web_view = QWebEngineView()

        # Create bridge for Python<->JavaScript communication
        self.bridge = DirectorPanelBridge()

        # Connect bridge signals
        self.bridge.directors_selected.connect(self._on_directors_selected)
        self.bridge.open_marketplace.connect(self._on_open_marketplace)

        # Setup web channel
        self.channel = QWebChannel()
        self.channel.registerObject("directorPanelBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load HTML
        from classes import info
        html_path = os.path.join(info.PATH, "timeline", "directors", "panel.html")

        if os.path.exists(html_path):
            url = QUrl.fromLocalFile(html_path)
            self.web_view.load(url)
            log.info(f"Loaded director panel UI from {html_path}")
        else:
            log.error(f"Director panel HTML not found: {html_path}")
            # Load placeholder
            self.web_view.setHtml("""
                <html>
                <body style="font-family: sans-serif; padding: 20px; text-align: center;">
                    <h2>Director Panel</h2>
                    <p>HTML file not found. UI components pending.</p>
                </body>
                </html>
            """)

        self.setWidget(self.web_view)

    def _on_directors_selected(self, director_ids_json: str):
        """Handle director selection."""
        try:
            director_ids = json.loads(director_ids_json)
            self.directors_selected.emit(director_ids)
        except Exception as e:
            log.error(f"Failed to parse selected directors: {e}", exc_info=True)

    def _on_open_marketplace(self):
        """Handle marketplace button click."""
        try:
            from windows.director_marketplace_ui import show_marketplace_dialog
            show_marketplace_dialog(self)
            log.info("Opened marketplace dialog")
        except Exception as e:
            log.error(f"Failed to open marketplace: {e}", exc_info=True)


# Global instance
_director_panel_dock = None


def get_director_panel_dock(parent=None):
    """Get or create global DirectorPanelDockWidget instance."""
    global _director_panel_dock
    if _director_panel_dock is None:
        _director_panel_dock = DirectorPanelDockWidget(parent)
    return _director_panel_dock
