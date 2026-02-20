"""
Director Loader

Loads and validates .director files (JSON format).
Handles built-in directors and user-created directors.
"""

import json
import os
from typing import Optional, List
from classes.logger import log
from classes.ai_directors.director_agent import (
    Director,
    DirectorMetadata,
    DirectorPersonality,
    DirectorTraining,
)


class DirectorLoader:
    """Loads directors from .director JSON files."""

    def __init__(self):
        """Initialize loader with built-in and user director paths."""
        from classes import info
        self.builtin_dir = os.path.join(info.PATH, "directors", "built_in")
        self.user_dir = os.path.expanduser("~/.config/flowcut/directors/")

        # Ensure user directory exists
        os.makedirs(self.user_dir, exist_ok=True)

    def load_director(self, director_id: str) -> Optional[Director]:
        """
        Load a director by ID.

        Searches built-in directors first, then user directors.

        Args:
            director_id: ID of the director to load

        Returns:
            Director instance or None if not found
        """
        # Try built-in first
        builtin_path = os.path.join(self.builtin_dir, f"{director_id}.director")
        if os.path.exists(builtin_path):
            return self.load_director_from_file(builtin_path)

        # Try user directors
        user_path = os.path.join(self.user_dir, f"{director_id}.director")
        if os.path.exists(user_path):
            return self.load_director_from_file(user_path)

        log.warning(f"Director not found: {director_id}")
        return None

    def load_director_from_file(self, filepath: str) -> Optional[Director]:
        """
        Load a director from a .director JSON file.

        Args:
            filepath: Path to .director file

        Returns:
            Director instance or None if loading fails
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate required fields
            if not self._validate_director_data(data):
                log.error(f"Invalid director file: {filepath}")
                return None

            # Create metadata
            metadata = DirectorMetadata(
                id=data["id"],
                name=data["name"],
                version=data["version"],
                author=data["author"],
                description=data["description"],
                tags=data.get("tags", []),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )

            # Create personality
            personality_data = data["personality"]
            personality = DirectorPersonality(
                system_prompt=personality_data["system_prompt"],
                analysis_focus=personality_data.get("analysis_focus", []),
                critique_style=personality_data.get("critique_style", "constructive"),
                expertise_areas=personality_data.get("expertise_areas", []),
            )

            # Create training (optional)
            training = None
            if "training" in data and data["training"]:
                training = DirectorTraining(
                    type=data["training"].get("type", "examples"),
                    data=data["training"].get("data", {}),
                )

            # Get settings
            settings = data.get("settings", {})

            # Create director
            director = Director(
                metadata=metadata,
                personality=personality,
                training=training,
                settings=settings,
            )

            log.info(f"Loaded director: {director.name} (ID: {director.id})")
            return director

        except Exception as e:
            log.error(f"Failed to load director from {filepath}: {e}", exc_info=True)
            return None

    def list_available_directors(self) -> List[Director]:
        """
        List all available directors (built-in + user).

        Returns:
            List of Director instances (deduplicated by ID)
        """
        directors = []
        seen_ids = set()

        # Load built-in directors
        if os.path.exists(self.builtin_dir):
            for filename in os.listdir(self.builtin_dir):
                if filename.endswith('.director'):
                    filepath = os.path.join(self.builtin_dir, filename)
                    director = self.load_director_from_file(filepath)
                    if director and director.id not in seen_ids:
                        directors.append(director)
                        seen_ids.add(director.id)

        # Load user directors (user directors override built-in if same ID)
        if os.path.exists(self.user_dir):
            for filename in os.listdir(self.user_dir):
                if filename.endswith('.director'):
                    filepath = os.path.join(self.user_dir, filename)
                    director = self.load_director_from_file(filepath)
                    if director and director.id not in seen_ids:
                        directors.append(director)
                        seen_ids.add(director.id)

        return directors

    def save_director(self, director: Director, user_dir: bool = True) -> bool:
        """
        Save a director to a .director file.

        Args:
            director: Director to save
            user_dir: If True, save to user directory; if False, save to built-in

        Returns:
            True if saved successfully
        """
        try:
            target_dir = self.user_dir if user_dir else self.builtin_dir
            os.makedirs(target_dir, exist_ok=True)

            filepath = os.path.join(target_dir, f"{director.id}.director")

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(director.to_dict(), f, indent=2, ensure_ascii=False)

            log.info(f"Saved director: {director.name} to {filepath}")
            return True

        except Exception as e:
            log.error(f"Failed to save director {director.id}: {e}", exc_info=True)
            return False

    def _validate_director_data(self, data: dict) -> bool:
        """
        Validate director JSON data has required fields.

        Args:
            data: Parsed JSON data

        Returns:
            True if valid
        """
        required_fields = ["id", "name", "version", "author", "description", "personality"]
        for field in required_fields:
            if field not in data:
                log.error(f"Missing required field: {field}")
                return False

        # Validate personality
        personality = data.get("personality", {})
        if "system_prompt" not in personality:
            log.error("Missing system_prompt in personality")
            return False

        return True


# Global director loader instance
_director_loader = None


def get_director_loader() -> DirectorLoader:
    """Get global DirectorLoader instance."""
    global _director_loader
    if _director_loader is None:
        _director_loader = DirectorLoader()
    return _director_loader
