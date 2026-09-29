"""
 @file
 @brief Helpers for OpenShot release details metadata
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 """

import json
import os
import re

from classes import http_client, info
from classes.logger import log


RELEASE_DETAILS_URL = "https://www.openshot.org/releases/%s/"
RELEASE_VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?$")


def release_details_url(version):
    """Return the release details URL for official release versions only."""
    version = str(version or "").strip()
    if not RELEASE_VERSION_RE.match(version):
        return None
    return RELEASE_DETAILS_URL % version


def get_release_details(version):
    """Fetch release metadata without making offline/missing releases fatal."""
    url = release_details_url(version)
    if not url:
        return None
    try:
        metadata = http_client.get_json(
            http_client.urls_with_http_fallback(url),
            "OpenShot release details",
            headers={"user-agent": "openshot-qt-%s" % version},
        )
        if isinstance(metadata, dict):
            return metadata
    except Exception as ex:
        log.warning("OpenShot release details unavailable: %s", ex)
    return None


def get_build_details():
    """Read the existing packaged build metadata, if available."""
    path = os.path.join(info.PATH, "settings", "version.json")
    try:
        with open(path, encoding="utf-8") as stream:
            metadata = json.load(stream)
        if isinstance(metadata, dict):
            return metadata
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as ex:
        log.warning("OpenShot build details unavailable: %s", ex)
    return {}


def is_release_build(build_metadata, release_metadata):
    """Only a nonempty matching commit identifies a confirmed release build."""
    if not isinstance(build_metadata, dict) or not isinstance(release_metadata, dict):
        return False
    qt_metadata = build_metadata.get("openshot-qt")
    if not isinstance(qt_metadata, dict):
        return False
    build_sha = qt_metadata.get("CI_COMMIT_SHA")
    release_sha = release_metadata.get("sha")
    return (isinstance(build_sha, str) and bool(build_sha.strip())
            and build_sha == release_sha)
