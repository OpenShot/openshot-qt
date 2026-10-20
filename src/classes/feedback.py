"""Feedback eligibility and survey URL metadata (no automatic network requests)."""

import base64
import json
from urllib.parse import urlencode

SURVEY_URL = "https://www.openshot.org/{language}feedback/"


def survey_url(distribution, install_id, website_language=""):
    """Encode the website's v1 context as unpadded URL-safe base64 UTF-8 JSON.

    Official website packages use ``direct``; our official MSIX uses
    ``microsoft-store``. Unidentified installs stay ``unknown`` until we can
    reliably detect distro or Steam packaging.
    """
    kind = distribution.get("package_type", "unknown")
    source = kind if kind in ("snap", "flatpak") else "unknown"
    if distribution.get("official") and kind in ("exe", "appimage", "appbundle"):
        source = "direct"
    elif distribution.get("official") and kind == "msix":
        source = "microsoft-store"
    system = distribution.get("platform", "unknown").lower()
    system = {"windows": "windows", "darwin": "macos", "macos": "macos",
              "linux": "linux"}.get(system, "unknown")
    # Website context contract (v=1):
    # os: windows, macos, linux, unknown.
    # source: direct, microsoft-store, steam, flatpak, snap, distro, unknown.
    # direct means official website downloads; distro means distribution packages.
    # steam/distro are reserved here until reliable detection is implemented.
    # version is the OpenShot version string; install_uuid is the existing
    # unique_install_id (installation/profile identifier, not a person-wide ID).
    payload = {
        "v": 1,
        "version": distribution["app_version"],
        "os": system,
        "source": source,
        "install_uuid": install_id,
    }
    context = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return SURVEY_URL.format(language=website_language) + "?" + urlencode({"context": context})


class FeedbackPolicy:
    """Invite feedback once per release, after a successful export.

    Only the banner acknowledgement is stored, and it resets on upgrade.
    """

    def __init__(self, settings, release):
        self.settings = settings
        previous_release = settings.get("feedback-release")
        if release is not None and previous_release != release:
            settings.set("feedback-release", release)
            # Preserve a legacy dismissal for the first release using this policy.
            if previous_release:
                settings.set("feedback-shown", False)

    @property
    def shown(self):
        return bool(self.settings.get("feedback-shown"))

    def consume(self):
        """Acknowledge this release's banner, independently of the survey URL."""
        if self.shown:
            return False
        self.settings.set("feedback-shown", True)
        try:
            self.settings.save()
        except Exception:
            self.settings.set("feedback-shown", False)
            raise
        return True
