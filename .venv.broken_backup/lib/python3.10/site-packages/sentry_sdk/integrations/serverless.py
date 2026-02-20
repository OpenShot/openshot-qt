import sys
from functools import wraps
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk.utils import event_from_exception, reraise

if TYPE_CHECKING:
    from typing import Any, Callable, Optional, TypeVar, Union, overload

    F = TypeVar("F", bound=Callable[..., Any])

else:

    def overload(x: "F") -> "F":
        return x


@overload
def serverless_function(f: "F", flush: bool = True) -> "F":
    pass


@overload
def serverless_function(f: None = None, flush: bool = True) -> "Callable[[F], F]":  # noqa: F811
    pass


def serverless_function(  # noqa
    f: "Optional[F]" = None, flush: bool = True
) -> "Union[F, Callable[[F], F]]":
    def wrapper(f: "F") -> "F":
        @wraps(f)
        def inner(*args: "Any", **kwargs: "Any") -> "Any":
            with sentry_sdk.isolation_scope() as scope:
                scope.clear_breadcrumbs()

                try:
                    return f(*args, **kwargs)
                except Exception:
                    _capture_and_reraise()
                finally:
                    if flush:
                        sentry_sdk.flush()

        return inner  # type: ignore

    if f is None:
        return wrapper
    else:
        return wrapper(f)


def _capture_and_reraise() -> None:
    exc_info = sys.exc_info()
    client = sentry_sdk.get_client()
    if client.is_active():
        event, hint = event_from_exception(
            exc_info,
            client_options=client.options,
            mechanism={"type": "serverless", "handled": False},
        )
        sentry_sdk.capture_event(event, hint=hint)

    reraise(*exc_info)
