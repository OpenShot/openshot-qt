"""
Zenvi authentication manager.

Handles the desktop OAuth-style flow:
  1. generate_state() → opens browser at /login?state=<uuid>
  2. poll_for_session() → polls Supabase RPC every 2s in a background thread
  3. save_session() / load_session() → persist JWT to ~/.openshot_qt/zenvi_auth.json

The token file is a plain JSON file for simplicity. In production, migrate to
the OS keychain via the `keyring` library.
"""

import json
import logging
import os
import threading
import time
import uuid
import webbrowser

import requests

from classes import info

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://fmeawyasfffvyoactenu.supabase.co"
# anon key (public — safe to ship in the app)
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZtZWF3eWFzZmZmdnlvYWN0ZW51Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg4MDYyMTMsImV4cCI6MjA1NDM4MjIxM30"
    ".placeholder"  # TODO: replace with real anon key from .env
)
ZENVI_WEBSITE = "https://zenvi.app"
AUTH_FILE = os.path.join(info.USER_PATH, "zenvi_auth.json")

# Poll interval and timeout (seconds)
POLL_INTERVAL = 2
POLL_TIMEOUT = 300  # 5 minutes


class AuthManager:
    """Singleton that manages the Zenvi account session."""

    _instance = None

    @classmethod
    def instance(cls) -> "AuthManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._session: dict | None = None
        self._cancelled = False
        self._poll_thread: threading.Thread | None = None

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    def _anon_headers(self) -> dict:
        return {
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        }

    def _authed_headers(self) -> dict:
        token = self.get_access_token()
        h = self._anon_headers()
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    # ── Session persistence ────────────────────────────────────────────────────

    def load_session(self) -> dict | None:
        """Load the stored session from disk into memory."""
        try:
            if os.path.exists(AUTH_FILE):
                with open(AUTH_FILE, "r", encoding="utf-8") as fh:
                    self._session = json.load(fh)
                return self._session
        except Exception as exc:
            log.warning("Could not load Zenvi auth session: %s", exc)
        return None

    def save_session(self, session: dict) -> None:
        """Persist a session dict to disk."""
        try:
            os.makedirs(info.USER_PATH, exist_ok=True)
            with open(AUTH_FILE, "w", encoding="utf-8") as fh:
                json.dump(session, fh, indent=2)
            self._session = session
            log.info("Zenvi session saved for user: %s", session.get("user_email", "?"))
        except Exception as exc:
            log.error("Could not save Zenvi auth session: %s", exc)

    def clear_session(self) -> None:
        """Sign out — remove stored tokens."""
        try:
            if os.path.exists(AUTH_FILE):
                os.remove(AUTH_FILE)
        except Exception as exc:
            log.warning("Could not clear Zenvi auth file: %s", exc)
        self._session = None

    # ── Session queries ────────────────────────────────────────────────────────

    def is_authenticated(self) -> bool:
        if self._session is None:
            self.load_session()
        return bool(self._session and self._session.get("access_token"))

    def get_access_token(self) -> str | None:
        if self._session is None:
            self.load_session()
        return (self._session or {}).get("access_token")

    def get_user_email(self) -> str | None:
        if self._session is None:
            self.load_session()
        return (self._session or {}).get("user_email")

    # ── Desktop OAuth flow ─────────────────────────────────────────────────────

    def start_auth_flow(self) -> str:
        """
        Generate a random state UUID, open the browser at /login?state=<uuid>,
        and return the state so the caller can start polling.
        """
        state = str(uuid.uuid4())
        url = f"{ZENVI_WEBSITE}/login?state={state}"
        log.info("Opening auth URL: %s", url)
        webbrowser.open(url)
        return state

    def poll_for_session(
        self,
        state: str,
        on_success,
        on_timeout,
        interval: int = POLL_INTERVAL,
        timeout: int = POLL_TIMEOUT,
    ) -> None:
        """
        Poll the Supabase RPC in a daemon thread.

        Calls on_success(session_dict) when auth completes, or on_timeout()
        if the timeout is reached without a response.

        Both callbacks are invoked from the background thread — connect them
        to Qt signals if you need to update the UI.
        """
        self._cancelled = False

        def _worker():
            deadline = time.monotonic() + timeout
            while not self._cancelled and time.monotonic() < deadline:
                try:
                    resp = requests.post(
                        f"{SUPABASE_URL}/rest/v1/rpc/poll_desktop_auth_session",
                        headers=self._anon_headers(),
                        json={"session_state": state},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows and isinstance(rows, list) and rows[0].get("authenticated"):
                            session = rows[0]
                            self.save_session(session)
                            on_success(session)
                            return
                except requests.RequestException as exc:
                    log.debug("Poll request failed (will retry): %s", exc)

                time.sleep(interval)

            if not self._cancelled:
                on_timeout()

        self._poll_thread = threading.Thread(target=_worker, daemon=True, name="zenvi-auth-poll")
        self._poll_thread.start()

    def cancel_poll(self) -> None:
        """Stop any in-progress polling thread."""
        self._cancelled = True

    # ── Authenticated API calls ────────────────────────────────────────────────

    def get_subscription_tier(self) -> str | None:
        """
        Fetch the current user's active subscription tier from Supabase.
        Returns 'creator' | 'pro' | 'studio', or None if no active subscription.
        Requires the user to be authenticated.
        """
        if not self.is_authenticated():
            return None
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/get_user_subscription",
                headers=self._authed_headers(),
                json={},
                timeout=8,
            )
            if resp.status_code == 200:
                rows = resp.json()
                if rows and isinstance(rows, list) and rows[0].get("tier"):
                    tier = rows[0]["tier"]
                    status = rows[0].get("status", "")
                    if status in ("active", "trialing"):
                        return tier
        except Exception as exc:
            log.warning("Could not fetch subscription tier: %s", exc)
        return None

    def get_subscription_info(self) -> dict | None:
        """
        Returns the full subscription record: tier, status, current_period_end,
        cancel_at_period_end. Returns None if not authenticated or no active sub.
        """
        if not self.is_authenticated():
            return None
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/get_user_subscription",
                headers=self._authed_headers(),
                json={},
                timeout=8,
            )
            if resp.status_code == 200:
                rows = resp.json()
                if rows and isinstance(rows, list):
                    return rows[0]
        except Exception as exc:
            log.warning("Could not fetch subscription info: %s", exc)
        return None
