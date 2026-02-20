"""
Director Selection Panel UI

PyQt dock widget with HTML/CSS/JS overlay for selecting and managing directors.
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
            from classes.ai_directors.director_loader import get_director_loader
            import os

            loader = get_director_loader()

            # Check both user and built-in directories
            user_dir = os.path.expanduser("~/.config/flowcut/directors")
            user_path = os.path.join(user_dir, f"{director_id}.director")

            from classes import info
            builtin_dir = os.path.join(info.PATH, "directors", "built_in")
            builtin_path = os.path.join(builtin_dir, f"{director_id}.director")

            # Only delete from user directory (don't delete built-in directors)
            if os.path.exists(user_path):
                os.remove(user_path)
                log.info(f"Deleted user director: {director_id}")
                # Reload directors after deletion
                self.loadDirectors()
            elif os.path.exists(builtin_path):
                log.warning(f"Cannot delete built-in director: {director_id}")
            else:
                log.warning(f"Director not found: {director_id}")

        except Exception as e:
            log.error(f"Failed to delete director {director_id}: {e}", exc_info=True)

    @pyqtSlot()
    def loadDirectors(self):
        """Load available directors (called from JavaScript on init)."""
        try:
            from classes.ai_directors.director_loader import get_director_loader

            loader = get_director_loader()
            directors = loader.list_available_directors()

            # Convert to JSON-serializable format
            directors_data = []
            for director in directors:
                directors_data.append({
                    'id': director.id,
                    'name': director.name,
                    'description': director.metadata.description,
                    'author': director.metadata.author,
                    'version': director.metadata.version,
                    'tags': director.metadata.tags,
                    'expertise': director.personality.expertise_areas,
                    'focus': director.personality.analysis_focus,
                })

            self.directors = directors_data
            directors_json = json.dumps(directors_data)
            self.directorsLoaded.emit(directors_json)

            log.info(f"Loaded {len(directors)} directors into panel")
        except Exception as e:
            log.error(f"Failed to load directors: {e}", exc_info=True)
            self.directorsLoaded.emit("[]")

    @pyqtSlot(str)
    def selectDirectors(self, director_ids_json: str):
        """
        Called from JavaScript when user clicks Analyze button.
        Immediately triggers director analysis.

        Args:
            director_ids_json: JSON array of director IDs
        """
        try:
            director_ids = json.loads(director_ids_json)
            log.info(f"Starting analysis with directors: {director_ids}")

            # Emit signal for any listeners
            self.directors_selected.emit(director_ids_json)

            # Trigger director analysis immediately
            self._trigger_director_analysis(director_ids)

        except Exception as e:
            log.error(f"Failed to start director analysis: {e}", exc_info=True)

    def _trigger_director_analysis(self, director_ids):
        """
        Trigger director orchestrator to analyze the project.

        Args:
            director_ids: List of director IDs to use
        """
        try:
            from classes.app import get_app
            from classes.ai_directors.director_orchestrator import DirectorOrchestrator
            from classes.ai_directors.director_loader import get_director_loader
            from classes.ai_agent_runner import create_main_thread_runner, get_main_thread_runner, set_main_thread_runner
            from classes import settings

            app = get_app()

            # Get current model ID from settings or use default
            model_id = settings.get_settings().get("ai-default-model") or "anthropic/claude-sonnet-4"

            # Load directors
            loader = get_director_loader()
            directors = []
            for director_id in director_ids:
                director = loader.load_director(director_id)
                if director:
                    directors.append(director)
                else:
                    log.warning(f"Failed to load director: {director_id}")

            if not directors:
                log.error("No directors loaded for analysis")
                return

            log.info(f"Running {len(directors)} directors in parallel...")

            # Prefer the app's existing main-thread runner (shared tools + context).
            # If absent, create one (must be called on main thread) and cache it.
            runner = get_main_thread_runner()
            if runner is None:
                runner = create_main_thread_runner()
                set_main_thread_runner(runner)

            # Run orchestrator in background thread
            import threading
            def run_analysis():
                try:
                    orchestrator = DirectorOrchestrator(directors)
                    plan = orchestrator.run_directors(
                        model_id=model_id,
                        task="Analyze the current video project and suggest improvements",
                        main_thread_runner=runner,
                        project_data={}
                    )

                    # Display plan in UI (must be done in main thread)
                    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(
                        self,
                        "_show_plan_in_ui",
                        Qt.QueuedConnection,
                        Q_ARG(object, plan)
                    )

                    log.info(f"Director analysis complete! Generated plan with {len(plan.steps)} steps")

                except Exception as e:
                    log.error(f"Director analysis failed: {e}", exc_info=True)

            analysis_thread = threading.Thread(target=run_analysis, daemon=True)
            analysis_thread.start()

        except Exception as e:
            log.error(f"Failed to trigger director analysis: {e}", exc_info=True)

    @pyqtSlot(object)
    def _show_plan_in_ui(self, plan):
        """Show the director plan in the Plan Review UI (called from main thread)."""
        try:
            from classes.app import get_app
            app = get_app()

            if hasattr(app, 'window') and hasattr(app.window, 'dockPlanReview'):
                app.window.dockPlanReview.show_plan(plan)
                app.window.dockPlanReview.setVisible(True)
                log.info("Director plan displayed in Plan Review panel")
            else:
                log.warning("Plan Review UI not available")

        except Exception as e:
            log.error(f"Failed to display plan in UI: {e}", exc_info=True)

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
