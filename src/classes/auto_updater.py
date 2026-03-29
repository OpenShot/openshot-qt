"""
 @file
 @brief Background auto-updater that checks GitHub releases and downloads
        platform-specific updates silently while the app is running.
        Updates are staged locally and applied on next launch.
 @author Zenvi Team

 @section LICENSE

 Copyright (c) 2008-2026 Zenvi.
 This file is part of Zenvi Video Editor (https://zenvi.org).

 Zenvi is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
"""

import os
import json
import platform
import threading
import time
import hashlib
import shutil

import requests

from classes import info
from classes.logger import log


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API_URL = (
    "https://api.github.com/repos/{repo}/releases/latest"
)

UPDATE_STAGING_DIR = info.UPDATE_PATH
UPDATE_MANIFEST = os.path.join(UPDATE_STAGING_DIR, "update_manifest.json")

# How long to wait after app launch before first check (seconds)
INITIAL_DELAY = 15

# Chunk size for streaming downloads
DOWNLOAD_CHUNK_SIZE = 64 * 1024  # 64 KB


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def _platform_asset_suffix():
    """Return the expected asset file suffix for the running platform."""
    system = platform.system().lower()
    if system == "linux":
        # Prefer AppImage; fall back to .deb
        appimage = os.environ.get("APPIMAGE")
        if appimage:
            return ".AppImage"
        # Check if installed via deb (binary in /usr)
        exe = os.path.realpath(os.sys.executable)
        if exe.startswith("/usr"):
            return ".deb"
        return ".AppImage"
    elif system == "darwin":
        return ".dmg"
    elif system == "windows":
        return ".exe"
    return None


def _platform_asset_arch_hint():
    """Return a substring that should appear in the asset name for arch matching."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    elif machine in ("aarch64", "arm64"):
        return "arm64"
    return machine


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

def _parse_version(v):
    """Parse a version string like '3.4.1' into a comparable tuple."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0,)


def is_newer(remote_version, local_version):
    """Return True if *remote_version* is strictly newer than *local_version*."""
    return _parse_version(remote_version) > _parse_version(local_version)


# ---------------------------------------------------------------------------
# Manifest helpers (used by both auto_updater and update_installer)
# ---------------------------------------------------------------------------

def has_pending_update():
    """Return True when a verified update is staged and ready to install."""
    if not os.path.exists(UPDATE_MANIFEST):
        return False
    try:
        with open(UPDATE_MANIFEST, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        return os.path.exists(manifest.get("filepath", ""))
    except Exception:
        return False


def get_update_manifest():
    """Read and return the update manifest dict, or None."""
    try:
        with open(UPDATE_MANIFEST, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def cleanup_staged_update():
    """Remove all staged update files."""
    try:
        manifest = get_update_manifest()
        if manifest:
            fp = manifest.get("filepath", "")
            if os.path.exists(fp):
                os.unlink(fp)
        if os.path.exists(UPDATE_MANIFEST):
            os.unlink(UPDATE_MANIFEST)
        log.info("AutoUpdater: Staged update cleaned up")
    except Exception as exc:
        log.warning("AutoUpdater: Cleanup error: %s", exc)


# ---------------------------------------------------------------------------
# AutoUpdater class
# ---------------------------------------------------------------------------

class AutoUpdater:
    """Checks GitHub Releases for a newer version in a background thread,
    downloads the platform-appropriate installer to a local staging directory,
    and writes a manifest so the next launch can apply it."""

    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        os.makedirs(UPDATE_STAGING_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Launch the background check-and-download thread (daemon)."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="AutoUpdater", daemon=True,
        )
        self._thread.start()
        log.info("AutoUpdater: Background thread started")

    def stop(self):
        """Signal the background thread to stop as soon as possible."""
        self._stop.set()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        """Entry point for the background thread."""
        try:
            # Wait before first check so the UI is fully loaded
            for _ in range(INITIAL_DELAY):
                if self._stop.is_set():
                    return
                time.sleep(1)

            # If there is already a staged update, skip the network check
            if has_pending_update():
                log.info("AutoUpdater: Pending update already staged — skipping network check")
                self._notify_ui_pending()
                return

            self._check_and_download()
        except Exception:
            log.error("AutoUpdater: Unhandled error in background thread", exc_info=True)

    def _check_and_download(self):
        """Query GitHub for the latest release; download if newer."""
        url = GITHUB_API_URL.format(repo=info.GITHUB_REPO)
        log.info("AutoUpdater: Checking %s", url)

        try:
            resp = requests.get(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"Zenvi/{info.VERSION}",
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            log.warning("AutoUpdater: Network error checking for updates: %s", exc)
            return

        if resp.status_code != 200:
            log.warning("AutoUpdater: GitHub API returned HTTP %d", resp.status_code)
            return

        release = resp.json()
        tag = release.get("tag_name", "")
        latest_version = tag.lstrip("v")

        if not latest_version:
            log.warning("AutoUpdater: Could not parse version from tag '%s'", tag)
            return

        if not is_newer(latest_version, info.VERSION):
            log.info(
                "AutoUpdater: Current version %s is up-to-date (latest: %s)",
                info.VERSION, latest_version,
            )
            # Still emit the version signal so the UI can confirm up-to-date
            self._emit_version_signal(latest_version)
            return

        log.info(
            "AutoUpdater: New version available — %s (current %s)",
            latest_version, info.VERSION,
        )

        # --- Find the matching platform asset ---
        suffix = _platform_asset_suffix()
        arch_hint = _platform_asset_arch_hint()
        if not suffix:
            log.warning("AutoUpdater: No known asset suffix for this platform")
            return

        download_url = None
        asset_name = None
        asset_size = 0

        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if not name.endswith(suffix):
                continue
            # Prefer an asset whose name contains the arch hint
            if arch_hint and arch_hint not in name.lower():
                # Accept it only if we haven't found a better match
                if download_url is None:
                    download_url = asset.get("browser_download_url")
                    asset_name = name
                    asset_size = asset.get("size", 0)
                continue
            download_url = asset.get("browser_download_url")
            asset_name = name
            asset_size = asset.get("size", 0)
            break  # exact match found

        if not download_url:
            log.warning(
                "AutoUpdater: No asset matching '%s' for arch '%s' in release %s",
                suffix, arch_hint, latest_version,
            )
            # Still notify UI about the version
            self._emit_version_signal(latest_version)
            return

        log.info(
            "AutoUpdater: Downloading %s (%s bytes)",
            asset_name, f"{asset_size:,}" if asset_size else "unknown",
        )
        success = self._download(download_url, asset_name, latest_version, asset_size)

        if success:
            self._emit_update_ready_signal(latest_version)
        else:
            # Notify the UI that an update exists even if download failed
            self._emit_version_signal(latest_version)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _download(self, url, filename, version, expected_size):
        """Stream-download *url* to the staging directory. Returns True on success."""
        staging_file = os.path.join(UPDATE_STAGING_DIR, filename)
        temp_file = staging_file + ".part"

        try:
            resp = requests.get(url, stream=True, timeout=600)
            resp.raise_for_status()

            sha256 = hashlib.sha256()
            downloaded = 0

            with open(temp_file, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if self._stop.is_set():
                        log.info("AutoUpdater: Download aborted (stop signal)")
                        self._safe_remove(temp_file)
                        return False
                    fh.write(chunk)
                    sha256.update(chunk)
                    downloaded += len(chunk)

            # Size sanity check
            if expected_size and downloaded != expected_size:
                log.error(
                    "AutoUpdater: Size mismatch — expected %d, got %d",
                    expected_size, downloaded,
                )
                self._safe_remove(temp_file)
                return False

            # Promote temp → final
            shutil.move(temp_file, staging_file)

            # Write manifest
            manifest = {
                "version": version,
                "filename": filename,
                "filepath": staging_file,
                "sha256": sha256.hexdigest(),
                "size": downloaded,
                "platform": platform.system().lower(),
                "downloaded_at": time.time(),
            }
            with open(UPDATE_MANIFEST, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)

            log.info(
                "AutoUpdater: Download complete — %s  sha256=%s",
                filename, sha256.hexdigest(),
            )
            return True

        except Exception:
            log.error("AutoUpdater: Download failed", exc_info=True)
            self._safe_remove(temp_file)
            return False

    # ------------------------------------------------------------------
    # Signal helpers
    # ------------------------------------------------------------------

    def _emit_version_signal(self, version):
        """Emit the existing FoundVersionSignal so the UI shows 'Update Available'."""
        try:
            from classes.app import get_app
            app = get_app()
            if app and hasattr(app, "window") and app.window:
                app.window.FoundVersionSignal.emit(version)
        except Exception:
            pass

    def _emit_update_ready_signal(self, version):
        """Emit a signal indicating the update has been downloaded and staged."""
        try:
            from classes.app import get_app
            app = get_app()
            if app and hasattr(app, "window") and app.window:
                app.window.UpdateReadySignal.emit(version)
        except Exception:
            pass

    def _notify_ui_pending(self):
        """Notify the UI about an already-staged update."""
        manifest = get_update_manifest()
        if manifest:
            version = manifest.get("version", "")
            if version:
                self._emit_update_ready_signal(version)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_remove(path):
        try:
            if os.path.exists(path):
                os.unlink(path)
        except OSError:
            pass
