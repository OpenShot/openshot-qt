"""
 @file
 @brief Pre-launch update installer.  Called from launch.py *before* any
        heavy imports (PyQt5, openshot, etc.) to apply a previously downloaded
        update that was staged by the AutoUpdater background thread.
 @author Zenvi Team

 @section LICENSE

 Copyright (c) 2008-2026 Zenvi.
 This file is part of Zenvi Video Editor (https://zenvi.org).

 Zenvi is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 NOTE: This module intentionally avoids importing PyQt5 or any heavy
 dependency so it can run quickly at the very start of the process.
"""

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time


# ---------------------------------------------------------------------------
# Paths  (mirror the constants in info.py without importing it)
# ---------------------------------------------------------------------------

_USER_PATH = os.path.join(os.path.expanduser("~"), ".openshot_qt")
UPDATE_STAGING_DIR = os.path.join(_USER_PATH, "updates")
UPDATE_MANIFEST = os.path.join(UPDATE_STAGING_DIR, "update_manifest.json")
UPDATE_LOG = os.path.join(UPDATE_STAGING_DIR, "install.log")


# ---------------------------------------------------------------------------
# Logging (minimal — no dependency on classes.logger)
# ---------------------------------------------------------------------------

def _log(msg):
    line = f"[ZenviUpdater] {msg}"
    print(line)
    try:
        with open(UPDATE_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Public API — called from launch.py
# ---------------------------------------------------------------------------

def has_pending_update():
    """Return True if a verified update package is staged and ready."""
    if not os.path.exists(UPDATE_MANIFEST):
        return False
    try:
        with open(UPDATE_MANIFEST, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        filepath = manifest.get("filepath", "")
        return bool(filepath) and os.path.isfile(filepath)
    except Exception:
        return False


def apply_pending_update():
    """Try to install a staged update.

    Returns
    -------
    bool
        True  — update applied; the caller should restart the process.
        False — nothing was applied (missing, corrupt, or unsupported).
    """
    manifest = _read_manifest()
    if manifest is None:
        return False

    _log(f"Applying staged update  version={manifest.get('version')}  "
         f"file={manifest.get('filename')}")

    if not _verify_integrity(manifest):
        _log("Integrity check FAILED — discarding staged update")
        _cleanup(manifest)
        return False

    system = platform.system().lower()
    filepath = manifest.get("filepath", "")
    filename = manifest.get("filename", "")

    try:
        if system == "linux":
            ok = _apply_linux(filepath, filename)
        elif system == "darwin":
            ok = _apply_macos(filepath, filename)
        elif system == "windows":
            ok = _apply_windows(filepath, filename)
        else:
            _log(f"Unsupported platform: {system}")
            ok = False
    except Exception as exc:
        _log(f"Installation error: {exc}")
        ok = False

    if ok:
        _log("Update applied successfully")
        _cleanup(manifest)
    else:
        _log("Update could not be applied — keeping staged files for retry")

    return ok


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------

def _apply_linux(filepath, filename):
    if filename.endswith(".AppImage"):
        return _apply_appimage(filepath)
    if filename.endswith(".deb"):
        return _apply_deb(filepath)
    _log(f"Unknown Linux package type: {filename}")
    return False


def _apply_appimage(filepath):
    """Replace the running AppImage binary with the new one."""
    current = os.environ.get("APPIMAGE") or _find_current_appimage()

    if not current:
        # Fallback: place in ~/Applications/
        current = os.path.expanduser("~/Applications/Zenvi.AppImage")
        os.makedirs(os.path.dirname(current), exist_ok=True)
        _log(f"No existing AppImage detected — installing to {current}")

    _log(f"Replacing AppImage  {current}")

    backup = current + ".bak"
    try:
        if os.path.exists(current):
            shutil.copy2(current, backup)

        shutil.copy2(filepath, current)
        # Ensure executable
        st = os.stat(current)
        os.chmod(current, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Remove backup on success
        if os.path.exists(backup):
            os.unlink(backup)

        _log("AppImage replaced successfully")
        return True

    except Exception as exc:
        _log(f"AppImage replacement failed: {exc}")
        if os.path.exists(backup):
            _log("Restoring backup")
            shutil.move(backup, current)
        return False


def _apply_deb(filepath):
    """Install a .deb package (requires elevated privileges)."""
    _log(f"Installing deb: {filepath}")

    # Try pkexec (graphical polkit prompt — zero terminal friction)
    for tool in ("pkexec", "sudo"):
        try:
            result = subprocess.run(
                [tool, "dpkg", "-i", filepath],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                _log(f"deb installed via {tool}")
                return True
            _log(f"{tool} dpkg returned {result.returncode}: {result.stderr.strip()}")
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            _log(f"{tool} dpkg timed out")
            continue

    _log("Could not install .deb (no pkexec/sudo available or permission denied)")
    return False


def _find_current_appimage():
    """Best-effort search for an existing Zenvi AppImage on the system."""
    # /proc/self/exe on Linux
    try:
        exe = os.readlink("/proc/self/exe")
        if exe.endswith(".AppImage"):
            return exe
    except OSError:
        pass

    search_dirs = [
        os.path.expanduser("~/Applications"),
        os.path.expanduser("~/Desktop"),
        "/usr/local/bin",
        "/opt",
    ]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        try:
            for entry in os.listdir(d):
                low = entry.lower()
                if "zenvi" in low and low.endswith(".appimage"):
                    return os.path.join(d, entry)
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------

def _apply_macos(filepath, filename):
    """Mount a .dmg, copy the .app bundle to /Applications."""
    if not filename.endswith(".dmg"):
        _log(f"Unknown macOS package type: {filename}")
        return False

    mount_point = tempfile.mkdtemp(prefix="zenvi_update_")
    _log(f"Mounting DMG at {mount_point}")

    try:
        # Mount
        res = subprocess.run(
            ["hdiutil", "attach", filepath,
             "-mountpoint", mount_point,
             "-nobrowse", "-quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if res.returncode != 0:
            _log(f"hdiutil attach failed: {res.stderr.strip()}")
            return False

        # Locate .app bundle
        app_bundle = None
        for entry in os.listdir(mount_point):
            if entry.endswith(".app"):
                app_bundle = os.path.join(mount_point, entry)
                break

        if not app_bundle:
            _log("No .app bundle found inside DMG")
            return False

        dest = os.path.join("/Applications", os.path.basename(app_bundle))

        # Remove old and copy new
        if os.path.exists(dest):
            _log(f"Removing old installation at {dest}")
            shutil.rmtree(dest)

        _log(f"Copying {app_bundle} → {dest}")
        shutil.copytree(app_bundle, dest)

        _log("macOS update installed")
        return True

    except Exception as exc:
        _log(f"macOS install error: {exc}")
        return False

    finally:
        # Always unmount
        try:
            subprocess.run(
                ["hdiutil", "detach", mount_point, "-quiet"],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
        try:
            os.rmdir(mount_point)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _apply_windows(filepath, filename):
    """Run an Inno-Setup .exe installer in fully silent mode."""
    if not filename.endswith(".exe"):
        _log(f"Unknown Windows package type: {filename}")
        return False

    _log(f"Launching silent installer: {filepath}")
    try:
        # Inno Setup silent flags:
        #   /VERYSILENT       — no user prompts at all
        #   /SUPPRESSMSGBOXES — suppress any message boxes
        #   /NORESTART        — don't auto-reboot the machine
        #   /CLOSEAPPLICATIONS — close running Zenvi instances
        #   /SP-              — disable "This will install..." prompt
        subprocess.Popen(
            [filepath,
             "/VERYSILENT",
             "/SUPPRESSMSGBOXES",
             "/NORESTART",
             "/CLOSEAPPLICATIONS",
             "/SP-"],
        )
        _log("Windows silent installer launched — it will complete in the background")
        return True

    except Exception as exc:
        _log(f"Windows install error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_manifest():
    try:
        with open(UPDATE_MANIFEST, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _verify_integrity(manifest):
    """SHA-256 verification of the staged file."""
    filepath = manifest.get("filepath", "")
    expected = manifest.get("sha256", "")

    if not os.path.isfile(filepath):
        _log(f"Staged file missing: {filepath}")
        return False

    if not expected:
        _log("No SHA-256 in manifest — skipping integrity check")
        return True  # can't verify, proceed anyway

    sha = hashlib.sha256()
    with open(filepath, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)

    actual = sha.hexdigest()
    if actual != expected:
        _log(f"SHA-256 mismatch  expected={expected}  actual={actual}")
        return False
    return True


def _cleanup(manifest):
    """Remove staged update files after successful (or discarded) install."""
    try:
        fp = manifest.get("filepath", "")
        if fp and os.path.exists(fp):
            os.unlink(fp)
        if os.path.exists(UPDATE_MANIFEST):
            os.unlink(UPDATE_MANIFEST)
        _log("Staged files cleaned up")
    except Exception as exc:
        _log(f"Cleanup error: {exc}")
