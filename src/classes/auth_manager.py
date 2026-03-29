"""
Zenvi authentication manager.

Primary flow (browser OAuth):
  1. start_auth_flow() → opens browser at ZENVI_WEBSITE/login?state=<uuid>
  2. poll_for_session() → polls Supabase RPC every 2s in a background thread
  3. On success, saves session to disk and calls on_success(session_dict)
  4. On timeout, calls on_timeout() so the UI can fall back to the password form

Fallback flow (email + password):
  sign_in_with_password(email, password) / sign_up_with_password(email, password)
  — call Supabase Auth REST API directly; no browser required.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
import webbrowser

import requests

from classes import info

log = logging.getLogger(__name__)


# ── Load .env file (zenvi-core root, one level above src/) ─────────────────────
def _load_dotenv(env_path: str) -> None:
    """Parse a simple KEY=value .env file into os.environ (no overwrite)."""
    try:
        if not os.path.exists(env_path):
            return
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as exc:
        log.debug("Could not load .env: %s", exc)


_load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# ── Constants ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xktarhzbrdnxkaovtdxj.supabase.co/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_2-FCBkJ96Ss35jqL9krVEQ_otR5iGmA")
ZENVI_WEBSITE = os.environ.get("ZENVI_WEBSITE", "https://zenvi.pro")
AUTH_FILE = os.path.join(info.USER_PATH, "zenvi_auth.json")

POLL_INTERVAL = 2
POLL_TIMEOUT = 45   # seconds before falling back to the password form


class AuthError(Exception):
    """Raised when sign-in fails."""


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
        try:
            if os.path.exists(AUTH_FILE):
                with open(AUTH_FILE, "r", encoding="utf-8") as fh:
                    self._session = json.load(fh)
                return self._session
        except Exception as exc:
            log.warning("Could not load Zenvi auth session: %s", exc)
        return None

    def save_session(self, session: dict) -> None:
        try:
            os.makedirs(info.USER_PATH, exist_ok=True)
            with open(AUTH_FILE, "w", encoding="utf-8") as fh:
                json.dump(session, fh, indent=2)
            self._session = session
            log.info("Zenvi session saved for user: %s", session.get("user_email", "?"))
        except Exception as exc:
            log.error("Could not save Zenvi auth session: %s", exc)

    def clear_session(self) -> None:
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

    # ── Browser OAuth flow ─────────────────────────────────────────────────────

    def start_auth_flow(self) -> tuple[str, str]:
        """
        Open ZENVI_WEBSITE/login?state=<uuid> in the system browser.
        Returns (url, state) so the caller can display/copy the URL.
        Tries xdg-open first (Linux), then webbrowser as fallback.
        """
        state = str(uuid.uuid4())
        url = f"{ZENVI_WEBSITE}/login?state={state}"
        log.info("Opening auth URL: %s", url)
        opened = False
        if sys.platform.startswith("linux"):
            try:
                subprocess.Popen(["xdg-open", url],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                opened = True
            except (FileNotFoundError, OSError):
                pass
        if not opened:
            webbrowser.open(url)
        return url, state

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
        Calls on_success(session_dict) or on_timeout() from the background thread.
        Aborts immediately on fatal RPC errors (404 / 405 = RPC not found).
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
                    log.debug("Poll status %s: %s", resp.status_code, resp.text[:200])
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows and isinstance(rows, list) and rows[0].get("authenticated"):
                            session = rows[0]
                            self.save_session(session)
                            on_success(session)
                            return
                    elif resp.status_code in (404, 405):
                        # RPC function does not exist — no point polling further
                        log.warning("poll_desktop_auth_session RPC not found (%s). Falling back.", resp.status_code)
                        on_timeout()
                        return
                except requests.RequestException as exc:
                    log.debug("Poll request failed (will retry): %s", exc)

                time.sleep(interval)

            if not self._cancelled:
                on_timeout()

        self._poll_thread = threading.Thread(target=_worker, daemon=True, name="zenvi-auth-poll")
        self._poll_thread.start()

    def cancel_poll(self) -> None:
        self._cancelled = True

    # ── Direct email/password fallback ────────────────────────────────────────

    def sign_in_with_password(self, email: str, password: str) -> dict:
        """
        Sign in via Supabase email+password REST API.
        Returns session dict on success; raises AuthError on failure.
        """
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise AuthError("Supabase is not configured (check SUPABASE_URL / SUPABASE_ANON_KEY in .env).")

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers=self._anon_headers(),
                json={"email": email, "password": password},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AuthError(f"Network error: {exc}") from exc

        log.debug("sign_in status=%s body=%s", resp.status_code, resp.text[:500])
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise AuthError(f"No access_token in response: {resp.text[:300]}")
            user = data.get("user") or {}
            session = {
                "access_token": access_token,
                "refresh_token": data.get("refresh_token"),
                "user_id": user.get("id"),
                "user_email": user.get("email") or email,
            }
            self.save_session(session)
            return session

        try:
            err = resp.json()
            msg = (err.get("error_description")
                   or err.get("msg")
                   or err.get("message")
                   or err.get("error")
                   or resp.text)
        except Exception:
            msg = resp.text or f"HTTP {resp.status_code}"
        log.warning("sign_in failed: %s", msg)
        raise AuthError(msg)

    def sign_up_with_password(self, email: str, password: str) -> dict:
        """
        Register a new account via Supabase.
        Raises AuthError on failure (including when email confirmation is required).
        """
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise AuthError("Supabase is not configured (check SUPABASE_URL / SUPABASE_ANON_KEY in .env).")

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/auth/v1/signup",
                headers=self._anon_headers(),
                json={"email": email, "password": password},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AuthError(f"Network error: {exc}") from exc

        log.debug("sign_up status=%s body=%s", resp.status_code, resp.text[:500])
        if resp.status_code in (200, 201):
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise AuthError("Account created — check your email to confirm it, then sign in.")
            user = data.get("user") or {}
            session = {
                "access_token": access_token,
                "refresh_token": data.get("refresh_token"),
                "user_id": user.get("id"),
                "user_email": user.get("email") or email,
            }
            self.save_session(session)
            return session

        try:
            err = resp.json()
            msg = (err.get("error_description")
                   or err.get("msg")
                   or err.get("message")
                   or err.get("error")
                   or resp.text)
        except Exception:
            msg = resp.text or f"HTTP {resp.status_code}"
        log.warning("sign_up failed: %s", msg)
        raise AuthError(msg)

    # ── Authenticated API calls ────────────────────────────────────────────────

    def get_subscription_tier(self) -> str | None:
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
                    if rows[0].get("status") in ("active", "trialing"):
                        return rows[0]["tier"]
        except Exception as exc:
            log.warning("Could not fetch subscription tier: %s", exc)
        return None

    def get_subscription_info(self) -> dict | None:
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
