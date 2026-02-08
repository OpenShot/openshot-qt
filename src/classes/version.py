"""
 @file
 @brief Check the latest released version from GitHub Releases API.
 @author Zenvi Team

 @section LICENSE

 Copyright (c) 2008-2026 Zenvi.
 This file is part of Zenvi Video Editor (https://zenvi.org).

 Zenvi is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
"""

import threading

import requests

from classes import info
from classes.app import get_app
from classes.logger import log


GITHUB_API_URL = (
    "https://api.github.com/repos/{repo}/releases/latest"
)


def get_current_Version():
    """Kick off a background thread that queries GitHub for the latest release."""
    t = threading.Thread(target=_fetch_latest_version, daemon=True)
    t.start()


def _fetch_latest_version():
    """HTTP call to GitHub Releases — emits FoundVersionSignal on success."""
    url = GITHUB_API_URL.format(repo=info.GITHUB_REPO)

    try:
        resp = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"Zenvi/{info.VERSION}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        tag = data.get("tag_name", "")
        latest_version = tag.lstrip("v")

        if not latest_version:
            log.warning("version: Could not parse version from tag '%s'", tag)
            return

        log.info("version: Latest release on GitHub: %s (local: %s)",
                 latest_version, info.VERSION)

        # Store the stable version for Sentry reporting
        info.ERROR_REPORT_STABLE_VERSION = latest_version

        # Notify the main window
        get_app().window.FoundVersionSignal.emit(latest_version)

    except Exception:
        log.error("version: Failed to fetch latest version from GitHub", exc_info=True)
