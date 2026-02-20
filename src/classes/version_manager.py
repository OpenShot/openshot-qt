"""
Version Management System for Parallel Execution

This module provides version management for parallel content generation tasks.
Each version maintains an isolated project state snapshot, allowing multiple
content types to be generated simultaneously without interfering with each other.
"""

import copy
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from PyQt5.QtCore import QObject, pyqtSignal


class VersionStatus(Enum):
    """Status of a version's execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Version:
    """
    Represents a single version of parallel content generation.

    Each version maintains:
    - Isolated project state snapshot
    - Execution status and progress
    - Activity log of tool executions
    - Associated chat session
    """

    def __init__(
        self,
        version_id: str,
        title: str,
        content_type: str,
        instructions: str,
        base_snapshot: dict,
        chat_session_id: Optional[str] = None
    ):
        self.version_id = version_id
        self.title = title
        self.content_type = content_type
        self.instructions = instructions
        self.status = VersionStatus.PENDING
        self.progress = 0.0
        self.project_snapshot = copy.deepcopy(base_snapshot)
        self.chat_session_id = chat_session_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.error_message = ""
        self.activity_log = []

    def update_progress(self, progress: float):
        """Update version progress (0.0 to 1.0)."""
        self.progress = max(0.0, min(1.0, progress))
        self.updated_at = datetime.now()

    def update_status(self, status: VersionStatus, error_message: str = ""):
        """Update version status."""
        self.status = status
        self.error_message = error_message
        self.updated_at = datetime.now()

    def add_activity_step(self, label: str, detail: str = "", completed: bool = False):
        """Add a step to the activity log."""
        self.activity_log.append({
            "label": label,
            "detail": detail,
            "completed": completed,
            "timestamp": datetime.now().isoformat()
        })
        self.updated_at = datetime.now()

    def complete_last_activity_step(self):
        """Mark the last activity step as completed."""
        if self.activity_log:
            self.activity_log[-1]["completed"] = True
            self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert version to dictionary for JSON serialization."""
        return {
            "version_id": self.version_id,
            "title": self.title,
            "content_type": self.content_type,
            "instructions": self.instructions,
            "status": self.status.value,
            "progress": self.progress,
            "chat_session_id": self.chat_session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "activity_log": self.activity_log
        }


class VersionManager(QObject):
    """
    Manages parallel execution versions.

    Responsibilities:
    - Create and track versions
    - Switch between version states
    - Maintain active version reference
    - Emit signals for UI updates
    """

    # Signals for UI updates
    version_created = pyqtSignal(str)  # version_id
    version_updated = pyqtSignal(str, dict)  # version_id, version_dict
    version_deleted = pyqtSignal(str)  # version_id
    active_version_changed = pyqtSignal(str)  # version_id

    def __init__(self):
        super().__init__()
        self._versions: Dict[str, Version] = {}
        self._active_version_id: Optional[str] = None

    def create_version(
        self,
        title: str,
        content_type: str,
        instructions: str,
        base_snapshot: dict,
        chat_session_id: Optional[str] = None
    ) -> Version:
        """
        Create a new version with isolated project state.

        Args:
            title: Display title for the version
            content_type: Type of content (video, manim, voice, music)
            instructions: Task instructions for the sub-agent
            base_snapshot: Base project state to copy
            chat_session_id: Optional associated chat session

        Returns:
            Created Version object
        """
        version_id = str(uuid.uuid4())
        version = Version(
            version_id=version_id,
            title=title,
            content_type=content_type,
            instructions=instructions,
            base_snapshot=base_snapshot,
            chat_session_id=chat_session_id
        )

        self._versions[version_id] = version
        self.version_created.emit(version_id)

        return version

    def get_version(self, version_id: str) -> Optional[Version]:
        """Get version by ID."""
        return self._versions.get(version_id)

    def list_versions(self) -> List[Version]:
        """List all versions."""
        return list(self._versions.values())

    def delete_version(self, version_id: str) -> bool:
        """Delete a version."""
        if version_id in self._versions:
            del self._versions[version_id]
            self.version_deleted.emit(version_id)

            # Clear active version if it was deleted
            if self._active_version_id == version_id:
                self._active_version_id = None

            return True
        return False

    def get_active_version_id(self) -> Optional[str]:
        """Get the currently active version ID."""
        return self._active_version_id

    def switch_to_version(self, version_id: str) -> bool:
        """
        Switch to a different version.

        This method:
        1. Saves current project state to active version (if any)
        2. Loads target version's project state
        3. Updates active version reference
        4. Emits signal for UI update

        Args:
            version_id: ID of version to switch to

        Returns:
            True if switch was successful
        """
        from classes.app import get_app

        version = self.get_version(version_id)
        if not version:
            return False

        app = get_app()

        # Save current state to currently active version (if any)
        if self._active_version_id:
            active_version = self.get_version(self._active_version_id)
            if active_version:
                active_version.project_snapshot = copy.deepcopy(app.project._data)

        # Load target version's project state
        app.project._data = copy.deepcopy(version.project_snapshot)

        # Trigger UI refresh via UpdatesRouter
        # This broadcasts to all listeners (timeline, properties, etc.)
        app.updates.load(app.project._data, reset_history=False)

        # Update active version tracking
        self._active_version_id = version_id
        self.active_version_changed.emit(version_id)

        return True

    def save_current_state_to_active_version(self):
        """Save current project state to the active version."""
        from classes.app import get_app

        if self._active_version_id:
            active_version = self.get_version(self._active_version_id)
            if active_version:
                app = get_app()
                active_version.project_snapshot = copy.deepcopy(app.project._data)

    def clear_all_versions(self):
        """Clear all versions (useful for cleanup)."""
        version_ids = list(self._versions.keys())
        for version_id in version_ids:
            self.delete_version(version_id)


# Global version manager instance
_version_manager = None


def get_version_manager() -> VersionManager:
    """Get or create the global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
