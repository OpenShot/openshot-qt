"""
Remotion API client for product launch video generation.
Thread-safe, no Qt dependencies.

This module is called from worker threads and makes HTTP requests
to a separate Node.js process, ensuring the Qt main thread never freezes.
"""

import requests
import json
import time
from typing import Dict, Any, Tuple
from classes.logger import log

REMOTION_API_URL = "http://localhost:3100"


def check_remotion_service() -> bool:
    """Check if Remotion service is running."""
    try:
        resp = requests.get(f"{REMOTION_API_URL}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def render_product_launch_video(
    repo_name: str,
    description: str,
    stars: int,
    forks: int,
    language: str,
    features: list,
    github_url: str,
    homepage: str = None,
    timeout_seconds: int = 60
) -> Tuple[bool, str, str]:
    """
    Render a product launch video using Remotion.

    Args:
        repo_name: Repository name
        description: Repo description
        stars: Star count
        forks: Fork count
        language: Primary language
        features: List of feature strings
        github_url: GitHub URL
        homepage: Optional homepage URL
        timeout_seconds: Render timeout

    Returns:
        (success: bool, output_path: str, error_message: str)
    """
    try:
        # Check if service is running
        if not check_remotion_service():
            return False, "", "Remotion service is not running. Start it with: npm run serve"

        log.info(f"[Remotion] Requesting render for: {repo_name}")

        # Prepare payload
        payload = {
            "repoName": repo_name,
            "description": description,
            "stars": stars,
            "forks": forks,
            "language": language,
            "features": features,
            "githubUrl": github_url,
            "homepage": homepage,
        }

        # Send render request
        resp = requests.post(
            f"{REMOTION_API_URL}/render/product-launch",
            json=payload,
            timeout=timeout_seconds
        )

        if resp.status_code != 200:
            return False, "", f"Remotion API error: {resp.status_code}"

        result = resp.json()

        if result.get("success"):
            output_path = result.get("outputPath")
            log.info(f"[Remotion] Render successful: {output_path}")
            return True, output_path, ""
        else:
            error = result.get("error", "Unknown error")
            log.error(f"[Remotion] Render failed: {error}")
            return False, "", error

    except requests.Timeout:
        return False, "", f"Render timed out after {timeout_seconds}s"
    except Exception as e:
        log.error(f"[Remotion] Exception: {e}", exc_info=True)
        return False, "", str(e)
