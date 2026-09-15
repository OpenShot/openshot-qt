"""Feedback eligibility and survey URL metadata (no automatic network requests)."""

import base64
import json
import math
from copy import deepcopy
from threading import local
from functools import wraps
from inspect import signature
from urllib.parse import urlencode

SURVEY_URL = "https://www.openshot.org/{language}feedback/"
FEEDBACK_DELAY_SECONDS = 20 * 60
FEEDBACK_ACTION_CATEGORIES = frozenset(("structure", "adjustments", "effects", "titles", "profile", "export"))
# Commands are synchronous; keep nested-command tracking local to their thread.
_feedback_command_active = local()


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


def record_feedback_action(category):
    """Called after a committed user command; feedback must never break editing."""
    from classes.app import get_app
    from classes.logger import log

    try:
        controller = getattr(getattr(get_app(), "window", None), "feedback_controller", None)
        if controller:
            controller.record_action(category)
    except Exception:
        log.warning("Unable to record feedback activity", exc_info=True)


def _feedback_clip_snapshot(clip_ids):
    """Read only the affected clips, and only while action milestones are needed."""
    from classes.app import get_app
    from classes.query import Clip
    from classes.logger import log

    try:
        controller = getattr(getattr(get_app(), "window", None), "feedback_controller", None)
        if not controller or controller.preview or controller.policy.experienced:
            return {}
        snapshots = {}
        for clip_id in clip_ids:
            clip = Clip.get(id=clip_id)
            if clip is not None:
                snapshots[clip_id] = deepcopy(clip.data)
        return snapshots
    except Exception:
        log.warning("Unable to inspect feedback activity", exc_info=True)
        return {}


def record_feedback_changes(category, originals, fields=None):
    """Count a committed multi-clip operation once, excluding unchanged values."""
    current = _feedback_clip_snapshot(originals)
    for clip_id, data in current.items():
        before = originals[clip_id]
        if fields:
            changed = any(before.get(key) != data.get(key) for key in fields)
        else:
            # Reader serialization is not an editing action.
            changed = ({key: value for key, value in before.items() if key != "reader"}
                       != {key: value for key, value in data.items() if key != "reader"})
        if changed:
            record_feedback_action(category)
            break


def feedback_command(category):
    """Annotate a user command with a clip_ids argument, never a low-level update.

    Snapshot once before the command and compare after it returns successfully.
    This excludes no-ops and exceptions and counts multi-selection only once.
    """
    def decorate(command):
        arguments = signature(command)
        positional_count = sum(parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
                               for parameter in arguments.parameters.values())

        @wraps(command)
        def tracked(*args, **kwargs):
            # QAction adds checked(bool). A *args wrapper must discard this extra
            # argument itself, as Qt did for the original fixed-arity handler.
            if len(args) == positional_count + 1 and isinstance(args[-1], bool):
                args = args[:-1]
            # Some presets delegate to other commands (e.g. volume fade in + out).
            if getattr(_feedback_command_active, "active", False):
                return command(*args, **kwargs)
            clip_ids = arguments.bind(*args, **kwargs).arguments.get("clip_ids", ())
            before = _feedback_clip_snapshot(clip_ids)
            _feedback_command_active.active = True
            try:
                result = command(*args, **kwargs)
            finally:
                _feedback_command_active.active = False
            if before:
                record_feedback_changes(category, before)
            return result
        return tracked
    return decorate


class FeedbackPolicy:
    """Require 3 committed actions in 2 categories, plus 20 minutes this release.

    Actions survive upgrades. Only time and banner acknowledgement reset.
    """

    def __init__(self, settings, release):
        self.settings = settings
        self.unsaved_seconds = 0
        self.dirty = False
        previous_release = settings.get("feedback-release")
        if release is not None and previous_release != release:
            settings.set("feedback-release", release)
            settings.set("feedback-use-seconds", 0)
            # Preserve a legacy dismissal for the first release using this policy.
            if previous_release:
                settings.set("feedback-shown", False)
            self.dirty = True

    @property
    def shown(self):
        return bool(self.settings.get("feedback-shown"))

    @property
    def categories(self):
        values = self.settings.get("feedback-action-categories")
        if not isinstance(values, list):
            return set()
        return {value for value in values if isinstance(value, str) and value in FEEDBACK_ACTION_CATEGORIES}

    @property
    def action_count(self):
        value = self.settings.get("feedback-action-count")
        return min(3, max(0, value)) if isinstance(value, int) and not isinstance(value, bool) else 0

    @property
    def experienced(self):
        return self.action_count >= 3 and len(self.categories) >= 2

    def record_action(self, category):
        if category not in FEEDBACK_ACTION_CATEGORIES or self.experienced:
            return
        if self.action_count == 3 and category in self.categories:
            return
        self.settings.set("feedback-action-count", min(3, self.action_count + 1))
        self.settings.set("feedback-action-categories", sorted(self.categories | {category}))
        self.settings.save()

    def advance(self, seconds):
        if self.shown:
            return False
        try:
            elapsed = float(self.settings.get("feedback-use-seconds") or 0)
        except (TypeError, ValueError, OverflowError):
            elapsed = 0
        if not math.isfinite(elapsed) or elapsed < 0:
            elapsed = 0
        elapsed = min(FEEDBACK_DELAY_SECONDS, elapsed)
        previous = elapsed
        seconds = seconds if math.isfinite(seconds) and seconds > 0 else 0
        elapsed = min(FEEDBACK_DELAY_SECONDS, elapsed + seconds)
        self.settings.set("feedback-use-seconds", elapsed)
        self.unsaved_seconds += elapsed - previous
        if self.unsaved_seconds >= 60 or previous < FEEDBACK_DELAY_SECONDS <= elapsed:
            self.flush()
        return elapsed >= FEEDBACK_DELAY_SECONDS and self.experienced

    def flush(self):
        if self.unsaved_seconds or self.dirty:
            self.settings.save()
            self.unsaved_seconds = 0
            self.dirty = False

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
