import io
import logging
import os
import time
import urllib.parse
import urllib.request
import urllib.error
import urllib3
import sys

from itertools import chain, product

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable
    from typing import Dict
    from typing import Optional
    from typing import Self

from sentry_sdk.utils import (
    logger as sentry_logger,
    env_to_bool,
    capture_internal_exceptions,
)
from sentry_sdk.envelope import Envelope


logger = logging.getLogger("spotlight")


DEFAULT_SPOTLIGHT_URL = "http://localhost:8969/stream"
DJANGO_SPOTLIGHT_MIDDLEWARE_PATH = "sentry_sdk.spotlight.SpotlightMiddleware"


class SpotlightClient:
    """
    A client for sending envelopes to Sentry Spotlight.

    Implements exponential backoff retry logic per the SDK spec:
    - Logs error at least once when server is unreachable
    - Does not log for every failed envelope
    - Uses exponential backoff to avoid hammering an unavailable server
    - Never blocks normal Sentry operation
    """

    # Exponential backoff settings
    INITIAL_RETRY_DELAY = 1.0  # Start with 1 second
    MAX_RETRY_DELAY = 60.0  # Max 60 seconds

    def __init__(self, url: str) -> None:
        self.url = url
        self.http = urllib3.PoolManager()
        self._retry_delay = self.INITIAL_RETRY_DELAY
        self._last_error_time: float = 0.0

    def capture_envelope(self, envelope: "Envelope") -> None:
        # Check if we're in backoff period - skip sending to avoid blocking
        if self._last_error_time > 0:
            time_since_error = time.time() - self._last_error_time
            if time_since_error < self._retry_delay:
                # Still in backoff period, skip this envelope
                return

        body = io.BytesIO()
        envelope.serialize_into(body)
        try:
            req = self.http.request(
                url=self.url,
                body=body.getvalue(),
                method="POST",
                headers={
                    "Content-Type": "application/x-sentry-envelope",
                },
            )
            req.close()
            # Success - reset backoff state
            self._retry_delay = self.INITIAL_RETRY_DELAY
            self._last_error_time = 0.0
        except Exception as e:
            self._last_error_time = time.time()

            # Increase backoff delay exponentially first, so logged value matches actual wait
            self._retry_delay = min(self._retry_delay * 2, self.MAX_RETRY_DELAY)

            # Log error once per backoff cycle (we skip sends during backoff, so only one failure per cycle)
            sentry_logger.warning(
                "Failed to send envelope to Spotlight at %s: %s. "
                "Will retry after %.1f seconds.",
                self.url,
                e,
                self._retry_delay,
            )


try:
    from django.utils.deprecation import MiddlewareMixin
    from django.http import HttpResponseServerError, HttpResponse, HttpRequest
    from django.conf import settings

    SPOTLIGHT_JS_ENTRY_PATH = "/assets/main.js"
    SPOTLIGHT_JS_SNIPPET_PATTERN = (
        "<script>window.__spotlight = {{ initOptions: {{ sidecarUrl: '{spotlight_url}', fullPage: false }} }};</script>\n"
        '<script type="module" crossorigin src="{spotlight_js_url}"></script>\n'
    )
    SPOTLIGHT_ERROR_PAGE_SNIPPET = (
        '<html><base href="{spotlight_url}">\n'
        '<script>window.__spotlight = {{ initOptions: {{ fullPage: true, startFrom: "/errors/{event_id}" }}}};</script>\n'
    )
    CHARSET_PREFIX = "charset="
    BODY_TAG_NAME = "body"
    BODY_CLOSE_TAG_POSSIBILITIES = tuple(
        "</{}>".format("".join(chars))
        for chars in product(*zip(BODY_TAG_NAME.upper(), BODY_TAG_NAME.lower()))
    )

    class SpotlightMiddleware(MiddlewareMixin):  # type: ignore[misc]
        _spotlight_script: "Optional[str]" = None
        _spotlight_url: "Optional[str]" = None

        def __init__(self: "Self", get_response: "Callable[..., HttpResponse]") -> None:
            super().__init__(get_response)

            import sentry_sdk.api

            self.sentry_sdk = sentry_sdk.api

            spotlight_client = self.sentry_sdk.get_client().spotlight
            if spotlight_client is None:
                sentry_logger.warning(
                    "Cannot find Spotlight client from SpotlightMiddleware, disabling the middleware."
                )
                return None
            # Spotlight URL has a trailing `/stream` part at the end so split it off
            self._spotlight_url = urllib.parse.urljoin(spotlight_client.url, "../")

        @property
        def spotlight_script(self: "Self") -> "Optional[str]":
            if self._spotlight_url is not None and self._spotlight_script is None:
                try:
                    spotlight_js_url = urllib.parse.urljoin(
                        self._spotlight_url, SPOTLIGHT_JS_ENTRY_PATH
                    )
                    req = urllib.request.Request(
                        spotlight_js_url,
                        method="HEAD",
                    )
                    urllib.request.urlopen(req)
                    self._spotlight_script = SPOTLIGHT_JS_SNIPPET_PATTERN.format(
                        spotlight_url=self._spotlight_url,
                        spotlight_js_url=spotlight_js_url,
                    )
                except urllib.error.URLError as err:
                    sentry_logger.debug(
                        "Cannot get Spotlight JS to inject at %s. SpotlightMiddleware will not be very useful.",
                        spotlight_js_url,
                        exc_info=err,
                    )

            return self._spotlight_script

        def process_response(
            self: "Self", _request: "HttpRequest", response: "HttpResponse"
        ) -> "Optional[HttpResponse]":
            content_type_header = tuple(
                p.strip()
                for p in response.headers.get("Content-Type", "").lower().split(";")
            )
            content_type = content_type_header[0]
            if len(content_type_header) > 1 and content_type_header[1].startswith(
                CHARSET_PREFIX
            ):
                encoding = content_type_header[1][len(CHARSET_PREFIX) :]
            else:
                encoding = "utf-8"

            if (
                self.spotlight_script is not None
                and not response.streaming
                and content_type == "text/html"
            ):
                content_length = len(response.content)
                injection = self.spotlight_script.encode(encoding)
                injection_site = next(
                    (
                        idx
                        for idx in (
                            response.content.rfind(body_variant.encode(encoding))
                            for body_variant in BODY_CLOSE_TAG_POSSIBILITIES
                        )
                        if idx > -1
                    ),
                    content_length,
                )

                # This approach works even when we don't have a `</body>` tag
                response.content = (
                    response.content[:injection_site]
                    + injection
                    + response.content[injection_site:]
                )

                if response.has_header("Content-Length"):
                    response.headers["Content-Length"] = content_length + len(injection)

            return response

        def process_exception(
            self: "Self", _request: "HttpRequest", exception: Exception
        ) -> "Optional[HttpResponseServerError]":
            if not settings.DEBUG or not self._spotlight_url:
                return None

            try:
                spotlight = (
                    urllib.request.urlopen(self._spotlight_url).read().decode("utf-8")
                )
            except urllib.error.URLError:
                return None
            else:
                event_id = self.sentry_sdk.capture_exception(exception)
                return HttpResponseServerError(
                    spotlight.replace(
                        "<html>",
                        SPOTLIGHT_ERROR_PAGE_SNIPPET.format(
                            spotlight_url=self._spotlight_url, event_id=event_id
                        ),
                    )
                )

except ImportError:
    settings = None


def _resolve_spotlight_url(
    spotlight_config: "Any", sentry_logger: "Any"
) -> "Optional[str]":
    """
    Resolve the Spotlight URL based on config and environment variable.

    Implements precedence rules per the SDK spec:
    https://develop.sentry.dev/sdk/expected-features/spotlight/

    Returns the resolved URL string, or None if Spotlight should be disabled.
    """
    spotlight_env_value = os.environ.get("SENTRY_SPOTLIGHT")

    # Parse env var to determine if it's a boolean or URL
    spotlight_from_env: "Optional[bool]" = None
    spotlight_env_url: "Optional[str]" = None
    if spotlight_env_value:
        parsed = env_to_bool(spotlight_env_value, strict=True)
        if parsed is None:
            # It's a URL string
            spotlight_from_env = True
            spotlight_env_url = spotlight_env_value
        else:
            spotlight_from_env = parsed

    # Apply precedence rules per spec:
    # https://develop.sentry.dev/sdk/expected-features/spotlight/#precedence-rules
    if spotlight_config is False:
        # Config explicitly disables spotlight - warn if env var was set
        if spotlight_from_env:
            sentry_logger.warning(
                "Spotlight is disabled via spotlight=False config option, "
                "ignoring SENTRY_SPOTLIGHT environment variable."
            )
        return None
    elif spotlight_config is True:
        # Config enables spotlight with boolean true
        # If env var has URL, use env var URL per spec
        if spotlight_env_url:
            return spotlight_env_url
        else:
            return DEFAULT_SPOTLIGHT_URL
    elif isinstance(spotlight_config, str):
        # Config has URL string - use config URL, warn if env var differs
        if spotlight_env_value and spotlight_env_value != spotlight_config:
            sentry_logger.warning(
                "Spotlight URL from config (%s) takes precedence over "
                "SENTRY_SPOTLIGHT environment variable (%s).",
                spotlight_config,
                spotlight_env_value,
            )
        return spotlight_config
    elif spotlight_config is None:
        # No config - use env var
        if spotlight_env_url:
            return spotlight_env_url
        elif spotlight_from_env:
            return DEFAULT_SPOTLIGHT_URL
        # else: stays None (disabled)

    return None


def setup_spotlight(options: "Dict[str, Any]") -> "Optional[SpotlightClient]":
    url = _resolve_spotlight_url(options.get("spotlight"), sentry_logger)

    if url is None:
        return None

    # Only set up logging handler when spotlight is actually enabled
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(" [spotlight] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

    # Update options with resolved URL for consistency
    options["spotlight"] = url

    with capture_internal_exceptions():
        if (
            settings is not None
            and settings.DEBUG
            and env_to_bool(os.environ.get("SENTRY_SPOTLIGHT_ON_ERROR", "1"))
            and env_to_bool(os.environ.get("SENTRY_SPOTLIGHT_MIDDLEWARE", "1"))
        ):
            middleware = settings.MIDDLEWARE
            if DJANGO_SPOTLIGHT_MIDDLEWARE_PATH not in middleware:
                settings.MIDDLEWARE = type(middleware)(
                    chain(middleware, (DJANGO_SPOTLIGHT_MIDDLEWARE_PATH,))
                )
                logger.info("Enabled Spotlight integration for Django")

    client = SpotlightClient(url)
    logger.info("Enabled Spotlight using sidecar at %s", url)

    return client
