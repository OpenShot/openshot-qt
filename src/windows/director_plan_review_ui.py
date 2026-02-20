"""
Director Plan Review UI

PyQt dock widget with HTML/CSS/JS overlay for reviewing and approving director plans.
"""

import os
import json
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt5.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QMessageBox
from classes.logger import log

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False
    log.warning("QtWebEngine not available - Plan Review UI will not work")


class PlanReviewBridge(QObject):
    """
    Bridge between Python and JavaScript for plan review UI.

    Exposed to JavaScript via QWebChannel as 'planReviewBridge'.
    """

    # Signals to JavaScript
    planLoaded = pyqtSignal(str)  # plan JSON

    # Signals to Python
    plan_approved = pyqtSignal(str)  # plan_id
    plan_rejected = pyqtSignal(str)  # plan_id
    plan_modified = pyqtSignal(str, str)  # plan_id, modifications JSON
    step_toggled = pyqtSignal(str, bool)  # step_id, enabled

    def __init__(self):
        super().__init__()
        self.current_plan = None

    @pyqtSlot(str)
    def loadPlan(self, plan_json: str):
        """
        Load a plan into the UI (called from Python).

        Args:
            plan_json: JSON string of DirectorPlan
        """
        try:
            plan_data = json.loads(plan_json)
            self.current_plan = plan_data
            self.planLoaded.emit(plan_json)
            log.info(f"Loaded plan into UI: {plan_data.get('plan_id')}")
        except Exception as e:
            log.error(f"Failed to load plan: {e}", exc_info=True)

    @pyqtSlot(str)
    def approvePlan(self, plan_id: str):
        """Called from JavaScript when user clicks Approve."""
        log.info(f"Plan approved: {plan_id}")
        self.plan_approved.emit(plan_id)

    @pyqtSlot(str)
    def rejectPlan(self, plan_id: str):
        """Called from JavaScript when user clicks Reject."""
        log.info(f"Plan rejected: {plan_id}")
        self.plan_rejected.emit(plan_id)

    @pyqtSlot(str, str)
    def modifyPlan(self, plan_id: str, modifications_json: str):
        """Called from JavaScript when user modifies the plan."""
        log.info(f"Plan modified: {plan_id}")
        self.plan_modified.emit(plan_id, modifications_json)

    @pyqtSlot(str, bool)
    def toggleStep(self, step_id: str, enabled: bool):
        """Called from JavaScript when user toggles a step."""
        log.info(f"Step toggled: {step_id} -> {enabled}")
        self.step_toggled.emit(step_id, enabled)


class PlanReviewDockWidget(QDockWidget):
    """
    Dock widget for reviewing and approving director plans.

    Uses QWebEngineView with HTML/CSS/JS for modern, responsive UI.
    """

    # Signals
    plan_approved = pyqtSignal(str)  # plan_id
    plan_rejected = pyqtSignal(str)  # plan_id
    plan_modified = pyqtSignal(str, dict)  # plan_id, modifications

    def __init__(self, parent=None):
        super().__init__("Director Plan Review", parent)

        self.current_plan = None
        self.bridge = None
        self.web_view = None

        self.setObjectName("director_plan_review_dock")
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with web view."""
        if not _WEBENGINE_AVAILABLE:
            # Fallback: simple label
            from PyQt5.QtWidgets import QLabel
            label = QLabel("QtWebEngine not available.\nPlan Review UI requires QtWebEngine.")
            label.setAlignment(Qt.AlignCenter)
            self.setWidget(label)
            return

        # Create web view
        self.web_view = QWebEngineView()

        # Create bridge for Python<->JavaScript communication
        self.bridge = PlanReviewBridge()

        # Connect bridge signals
        self.bridge.plan_approved.connect(self._on_plan_approved)
        self.bridge.plan_rejected.connect(self._on_plan_rejected)
        self.bridge.plan_modified.connect(self._on_plan_modified)

        # Setup web channel
        self.channel = QWebChannel()
        self.channel.registerObject("planReviewBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load HTML
        from classes import info
        html_path = os.path.join(info.PATH, "timeline", "directors", "plan_review.html")

        if os.path.exists(html_path):
            url = QUrl.fromLocalFile(html_path)
            self.web_view.load(url)
            log.info(f"Loaded plan review UI from {html_path}")
        else:
            log.error(f"Plan review HTML not found: {html_path}")
            # Load placeholder
            self.web_view.setHtml("""
                <html>
                <body style="font-family: sans-serif; padding: 20px; text-align: center;">
                    <h2>Plan Review UI</h2>
                    <p>HTML file not found. UI components pending.</p>
                </body>
                </html>
            """)

        self.setWidget(self.web_view)

    def show_plan(self, plan):
        """
        Display a director plan for review.

        Args:
            plan: DirectorPlan object
        """
        if not self.bridge:
            log.error("Bridge not initialized")
            return

        try:
            self.current_plan = plan
            plan_json = json.dumps(plan.to_dict())
            self.bridge.loadPlan(plan_json)

            # Show the dock
            self.show()
            self.raise_()

            log.info(f"Showing plan: {plan.title}")
        except Exception as e:
            log.error(f"Failed to show plan: {e}", exc_info=True)

    def _on_plan_approved(self, plan_id: str):
        """Handle plan approval."""
        if self.current_plan and self.current_plan.plan_id == plan_id:
            self.plan_approved.emit(plan_id)
            self.hide()
        else:
            log.warning(f"Plan ID mismatch: {plan_id} != {self.current_plan.plan_id if self.current_plan else 'None'}")

    def _on_plan_rejected(self, plan_id: str):
        """Handle plan rejection."""
        if self.current_plan and self.current_plan.plan_id == plan_id:
            self.plan_rejected.emit(plan_id)
            self.hide()
        else:
            log.warning(f"Plan ID mismatch: {plan_id} != {self.current_plan.plan_id if self.current_plan else 'None'}")

    def _on_plan_modified(self, plan_id: str, modifications_json: str):
        """Handle plan modifications."""
        try:
            modifications = json.loads(modifications_json)
            self.plan_modified.emit(plan_id, modifications)
        except Exception as e:
            log.error(f"Failed to parse modifications: {e}", exc_info=True)


# Global instance
_plan_review_dock = None


def get_plan_review_dock(parent=None):
    """Get or create global PlanReviewDockWidget instance."""
    global _plan_review_dock
    if _plan_review_dock is None:
        _plan_review_dock = PlanReviewDockWidget(parent)
    return _plan_review_dock
