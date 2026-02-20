from functools import wraps

import sentry_sdk
from sentry_sdk.consts import SPANSTATUS
from sentry_sdk.tracing_utils import set_span_errored
from ..utils import _record_exception_on_span

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Optional


def _patch_error_tracing() -> None:
    """
    Patches agents error tracing function to inject our span error logic
    when a tool execution fails.

    In newer versions, the function is at: agents.util._error_tracing.attach_error_to_current_span
    In older versions, it was at: agents._utils.attach_error_to_current_span

    This works even when the module or function doesn't exist.
    """
    error_tracing_module = None

    # Try newer location first (agents.util._error_tracing)
    try:
        from agents.util import _error_tracing

        error_tracing_module = _error_tracing
    except (ImportError, AttributeError):
        pass

    # Try older location (agents._utils)
    if error_tracing_module is None:
        try:
            import agents._utils

            error_tracing_module = agents._utils
        except (ImportError, AttributeError):
            # Module doesn't exist in either location, nothing to patch
            return

    # Check if the function exists
    if not hasattr(error_tracing_module, "attach_error_to_current_span"):
        return

    original_attach_error = error_tracing_module.attach_error_to_current_span

    @wraps(original_attach_error)
    def sentry_attach_error_to_current_span(
        error: "Any", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        """
        Wraps agents' error attachment to also set Sentry span status to error.
        This allows us to properly track tool execution errors even though
        the agents library swallows exceptions.
        """
        # Set the current Sentry span to errored
        current_span = sentry_sdk.get_current_span()
        if current_span is not None:
            _record_exception_on_span(current_span, error)

        # Call the original function
        return original_attach_error(error, *args, **kwargs)

    error_tracing_module.attach_error_to_current_span = (
        sentry_attach_error_to_current_span
    )
