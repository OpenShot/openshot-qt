"""
Zenvi Credits Client.

Handles point deductions and balance checks against the Supabase `user_credits`
table via RPC calls. All network calls are non-blocking (background thread) so
they never stall the UI or video generation pipeline.

Usage:
    from classes.credits_client import credits

    # Check before an expensive op (blocking — returns fast from local cache)
    ok, balance = credits.check(points_needed=10)

    # Deduct after a successful op (non-blocking)
    credits.deduct(points=10, operation="video_generation", provider="runware")

    # Refund if an op failed (non-blocking)
    credits.refund(points=10, operation="video_generation")

    # Award a bonus (non-blocking)
    credits.award_bonus("first_export")
"""

import logging
import threading
from typing import Optional, Tuple

log = logging.getLogger(__name__)

# Points per operation — single source of truth in Python land.
# These mirror tier_config values; keep in sync if you change the DB seed.
POINTS = {
    "video_generation": 10,     # Runware/Kling flat $0.10 = 10 pts
    "morph_generation": 10,     # same API
    "indexing_per_minute": 8,   # TwelveLabs Marengo ~$0.08/min
    "research_query": 2,        # Perplexity ~$0.008/query
    "chat": 0,                  # Chat is free — drive engagement
    "stock_add": 3,             # External stock API
    "product_demo": 5,          # Composite LLM + render
    "face_profile": 1,          # One-time per person
}


class CreditsClient:
    """
    Thin wrapper around Supabase RPC calls for the credits system.

    Thread-safety: deduct/refund/award_bonus are fire-and-forget in a daemon
    thread. check() is synchronous but fast (single HTTP call with 5s timeout).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cached_balance: Optional[int] = None   # refreshed on each check()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_auth(self):
        """Return (auth_manager, headers, supabase_url) or (None, None, None)."""
        try:
            from classes.auth_manager import AuthManager, SUPABASE_URL
            auth = AuthManager.instance()
            if not auth.is_authenticated():
                return None, None, None
            # Ensure URL ends without trailing slash for clean path joining
            url = SUPABASE_URL.rstrip("/")
            return auth, auth._authed_headers(), url
        except Exception as exc:
            log.debug("credits_client: could not get auth: %s", exc)
            return None, None, None

    def _rpc(self, function_name: str, payload: dict, timeout: int = 8) -> Optional[dict]:
        """
        Call a Supabase RPC function with the current user's auth token.
        Returns the parsed JSON response or None on failure.
        """
        auth, headers, url = self._get_auth()
        if auth is None:
            return None
        try:
            import requests
            resp = requests.post(
                f"{url}/rest/v1/rpc/{function_name}",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            log.debug("credits_client: RPC %s returned %s: %s",
                      function_name, resp.status_code, resp.text[:200])
            return None
        except Exception as exc:
            log.debug("credits_client: RPC %s failed: %s", function_name, exc)
            return None

    def _fire(self, function_name: str, payload: dict) -> None:
        """Fire-and-forget RPC in a daemon thread. Never blocks the caller."""
        t = threading.Thread(
            target=self._rpc,
            args=(function_name, payload),
            daemon=True,
            name=f"credits-{function_name}",
        )
        t.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, points_needed: int = 0) -> Tuple[bool, int]:
        """
        Check if the user has enough points for an operation.

        Returns (allowed: bool, current_balance: int).
        Returns (True, 0) if not authenticated — don't block unauthenticated use.
        Returns (True, 0) on network error — fail open, log warning.
        """
        auth, _, _ = self._get_auth()
        if auth is None:
            return True, 0   # not logged in — don't block, backend will handle

        result = self._rpc("get_credits_balance", {}, timeout=5)
        if result is None:
            log.warning("credits_client: could not fetch balance — allowing operation")
            return True, 0

        # get_credits_balance returns a row (or list with one row)
        row = result if isinstance(result, dict) else (result[0] if result else {})
        total = int(row.get("total_points", 0))
        in_standard = bool(row.get("in_standard_mode", False))
        overage_enabled = bool(row.get("overage_enabled", False))

        with self._lock:
            self._cached_balance = total

        # User can proceed if they have enough points OR overage is on
        allowed = (total >= points_needed) or overage_enabled
        return allowed, total

    def deduct(
        self,
        points: int,
        operation: str,
        provider: Optional[str] = None,
        session_id: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """
        Deduct points after a successful operation. Non-blocking.
        If points == 0, still logs the transaction for analytics.
        """
        if points <= 0:
            return   # chat and other free ops — nothing to deduct
        payload = {
            "p_points": points,
            "p_operation": operation,
            "p_provider": provider,
            "p_session_id": session_id,
            "p_note": note,
        }
        self._fire("deduct_points", payload)

    def refund(
        self,
        points: int,
        operation: str,
        note: Optional[str] = None,
    ) -> None:
        """
        Refund points for a failed operation. Non-blocking.
        Call this when a generation or API call returns an error AFTER points
        would have been deducted — but since we deduct only on success, this
        is mainly a safety net for partial failures (e.g., download failed after
        generation succeeded).
        """
        if points <= 0:
            return
        payload = {
            "p_points": points,
            "p_operation": operation,
            "p_original_txn": None,
            "p_note": note or "Operation failed — refund",
        }
        self._fire("refund_points", payload)

    def award_bonus(self, event_type: str, event_key: Optional[str] = None) -> None:
        """
        Award bonus credits for a one-time event. Non-blocking.
        Safe to call multiple times — the RPC is idempotent.
        """
        payload = {
            "p_event_type": event_type,
            "p_event_key": event_key,
        }
        self._fire("award_bonus", payload)

    def get_mode(self) -> str:
        """
        Return 'premium' or 'standard' based on current points balance.
        'standard' means the user has 0 points and no overage — use open-source models.
        Calls Supabase synchronously (fast, 5s timeout). Fails open → 'premium'.
        """
        auth, _, _ = self._get_auth()
        if auth is None:
            return "premium"

        result = self._rpc("get_credits_balance", {}, timeout=5)
        if result is None:
            return "premium"   # fail open

        row = result if isinstance(result, dict) else (result[0] if result else {})
        in_standard = bool(row.get("in_standard_mode", False))
        return "standard" if in_standard else "premium"


# ── Module-level singleton ─────────────────────────────────────────────────────
credits = CreditsClient()
