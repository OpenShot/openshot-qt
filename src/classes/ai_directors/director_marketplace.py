"""
Director Marketplace

Manages director discovery, installation, and sharing.
Local-first with optional cloud sync.
"""

import os
import json
from typing import List, Optional, Dict, Any
from classes.logger import log
from classes.ai_directors.director_loader import DirectorLoader
from classes.ai_directors.director_agent import Director


class DirectorMarketplace:
    """
    Manages director marketplace functionality.

    Provides:
    - Listing available directors (built-in + user + remote)
    - Installing directors from files/URLs
    - Exporting directors for sharing
    - Marketplace index management
    """

    def __init__(self):
        self.loader = DirectorLoader()
        self.marketplace_index_path = os.path.expanduser("~/.config/flowcut/marketplace/index.json")
        os.makedirs(os.path.dirname(self.marketplace_index_path), exist_ok=True)

    def list_available_directors(self) -> List[Director]:
        """
        List all available directors.

        Returns:
            List of Director instances from all sources
        """
        return self.loader.list_available_directors()

    def install_director_from_file(self, filepath: str) -> bool:
        """
        Install a director from a .director file.

        Args:
            filepath: Path to .director file

        Returns:
            True if installed successfully
        """
        try:
            # Load director
            director = self.loader.load_director_from_file(filepath)
            if not director:
                return False

            # Save to user directory
            return self.loader.save_director(director, user_dir=True)

        except Exception as e:
            log.error(f"Failed to install director from {filepath}: {e}", exc_info=True)
            return False

    def install_director_from_url(self, url: str) -> bool:
        """
        Download and install a director from URL.

        Args:
            url: URL to .director file

        Returns:
            True if installed successfully
        """
        # TODO: Implement URL download
        log.warning("install_director_from_url not yet implemented")
        return False

    def export_director(self, director_id: str, output_path: str) -> bool:
        """
        Export a director to a .director file for sharing.

        Args:
            director_id: ID of director to export
            output_path: Path where to save .director file

        Returns:
            True if exported successfully
        """
        try:
            # Load director
            director = self.loader.load_director(director_id)
            if not director:
                log.error(f"Director not found: {director_id}")
                return False

            # Save to output path
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(director.to_dict(), f, indent=2, ensure_ascii=False)

            log.info(f"Exported director {director_id} to {output_path}")
            return True

        except Exception as e:
            log.error(f"Failed to export director {director_id}: {e}", exc_info=True)
            return False

    def load_marketplace_index(self) -> Dict[str, Any]:
        """
        Load marketplace index (catalog of available directors).

        Returns:
            Marketplace index data
        """
        try:
            if os.path.exists(self.marketplace_index_path):
                with open(self.marketplace_index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Create default index
                default_index = {
                    "version": "1.0.0",
                    "directors": [],
                    "last_updated": "",
                }
                return default_index

        except Exception as e:
            log.error(f"Failed to load marketplace index: {e}", exc_info=True)
            return {"version": "1.0.0", "directors": []}

    def save_marketplace_index(self, index: Dict[str, Any]) -> bool:
        """
        Save marketplace index.

        Args:
            index: Index data to save

        Returns:
            True if saved successfully
        """
        try:
            with open(self.marketplace_index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            return True

        except Exception as e:
            log.error(f"Failed to save marketplace index: {e}", exc_info=True)
            return False


# Global marketplace instance
_marketplace = None


def get_marketplace() -> DirectorMarketplace:
    """Get global DirectorMarketplace instance."""
    global _marketplace
    if _marketplace is None:
        _marketplace = DirectorMarketplace()
    return _marketplace
