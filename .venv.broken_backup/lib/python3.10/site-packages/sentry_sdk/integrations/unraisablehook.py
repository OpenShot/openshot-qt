import sys

import sentry_sdk
from sentry_sdk.utils import (
    capture_internal_exceptions,
    event_from_exception,
)
from sentry_sdk.integrations import Integration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
    from typing import Any


class UnraisablehookIntegration(Integration):
    identifier = "unraisablehook"

    @staticmethod
    def setup_once() -> None:
        sys.unraisablehook = _make_unraisable(sys.unraisablehook)


def _make_unraisable(
    old_unraisablehook: "Callable[[sys.UnraisableHookArgs], Any]",
) -> "Callable[[sys.UnraisableHookArgs], Any]":
    def sentry_sdk_unraisablehook(unraisable: "sys.UnraisableHookArgs") -> None:
        integration = sentry_sdk.get_client().get_integration(UnraisablehookIntegration)

        # Note: If  we replace this with ensure_integration_enabled then
        # we break the exceptiongroup backport;
        # See: https://github.com/getsentry/sentry-python/issues/3097
        if integration is None:
            return old_unraisablehook(unraisable)

        if unraisable.exc_value and unraisable.exc_traceback:
            with capture_internal_exceptions():
                event, hint = event_from_exception(
                    (
                        unraisable.exc_type,
                        unraisable.exc_value,
                        unraisable.exc_traceback,
                    ),
                    client_options=sentry_sdk.get_client().options,
                    mechanism={"type": "unraisablehook", "handled": False},
                )
                sentry_sdk.capture_event(event, hint=hint)

        return old_unraisablehook(unraisable)

    return sentry_sdk_unraisablehook
