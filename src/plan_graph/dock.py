"""
Plan Graph dock: shows the hierarchy of what the AI did during an edit run.
"""

import json
import os

from PyQt5.QtCore import QFileInfo, Qt, QUrl, pyqtSlot
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QDockWidget, QSizePolicy, QWidget


class PlanGraphDock(QDockWidget):
    """Dock that displays the edit plan graph (root -> branches -> steps)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dockPlanGraph")
        self.setWindowTitle("Plan Graph")
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self._view = QWebEngineView(self)
        self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWidget(self._view)

        # Load UI from this package's ui/ folder
        ui_dir = os.path.join(os.path.dirname(__file__), "ui")
        index_path = os.path.join(ui_dir, "index.html")
        if os.path.isfile(index_path):
            base_url = QUrl.fromLocalFile(QFileInfo(index_path).absoluteFilePath())
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
            self._view.setHtml(html, base_url)
        else:
            self._view.setHtml(
                "<p>Plan graph UI not found (plan_graph/ui/index.html).</p>",
                QUrl(),
            )

    @pyqtSlot(str)
    def set_plan_json(self, json_str: str) -> None:
        """Update the graph with new plan JSON. Called when plan is updated or when response is ready."""
        if not json_str or not getattr(self._view, "page", None):
            return
        try:
            escaped = json.dumps(json_str)
        except Exception:
            escaped = json.dumps("null")
        self._view.page().runJavaScript("setPlanGraph(%s);" % escaped)
