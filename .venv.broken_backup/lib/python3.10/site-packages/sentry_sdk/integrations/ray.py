import inspect
import functools
import sys

import sentry_sdk
from sentry_sdk.consts import OP, SPANSTATUS
from sentry_sdk.integrations import _check_minimum_version, DidNotEnable, Integration
from sentry_sdk.tracing import TransactionSource
from sentry_sdk.utils import (
    event_from_exception,
    logger,
    package_version,
    qualname_from_function,
    reraise,
)

try:
    import ray  # type: ignore[import-not-found]
    from ray import remote
except ImportError:
    raise DidNotEnable("Ray not installed.")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Optional
    from sentry_sdk.utils import ExcInfo


def _check_sentry_initialized() -> None:
    if sentry_sdk.get_client().is_active():
        return

    logger.debug(
        "[Tracing] Sentry not initialized in ray cluster worker, performance data will be discarded."
    )


def _insert_sentry_tracing_in_signature(func: "Callable[..., Any]") -> None:
    # Patching new_func signature to add the _sentry_tracing parameter to it
    # Ray later inspects the signature and finds the unexpected parameter otherwise
    signature = inspect.signature(func)
    params = list(signature.parameters.values())
    sentry_tracing_param = inspect.Parameter(
        "_sentry_tracing",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=None,
    )

    # Keyword only arguments are penultimate if function has variadic keyword arguments
    if params and params[-1].kind is inspect.Parameter.VAR_KEYWORD:
        params.insert(-1, sentry_tracing_param)
    else:
        params.append(sentry_tracing_param)

    func.__signature__ = signature.replace(parameters=params)  # type: ignore[attr-defined]


def _patch_ray_remote() -> None:
    old_remote = remote

    @functools.wraps(old_remote)
    def new_remote(
        f: "Optional[Callable[..., Any]]" = None, *args: "Any", **kwargs: "Any"
    ) -> "Callable[..., Any]":
        if inspect.isclass(f):
            # Ray Actors
            # (https://docs.ray.io/en/latest/ray-core/actors.html)
            # are not supported
            # (Only Ray Tasks are supported)
            return old_remote(f, *args, **kwargs)

        def wrapper(user_f: "Callable[..., Any]") -> "Any":
            if inspect.isclass(user_f):
                # Ray Actors
                # (https://docs.ray.io/en/latest/ray-core/actors.html)
                # are not supported
                # (Only Ray Tasks are supported)
                return old_remote(*args, **kwargs)(user_f)

            @functools.wraps(user_f)
            def new_func(
                *f_args: "Any",
                _sentry_tracing: "Optional[dict[str, Any]]" = None,
                **f_kwargs: "Any",
            ) -> "Any":
                _check_sentry_initialized()

                transaction = sentry_sdk.continue_trace(
                    _sentry_tracing or {},
                    op=OP.QUEUE_TASK_RAY,
                    name=qualname_from_function(user_f),
                    origin=RayIntegration.origin,
                    source=TransactionSource.TASK,
                )

                with sentry_sdk.start_transaction(transaction) as transaction:
                    try:
                        result = user_f(*f_args, **f_kwargs)
                        transaction.set_status(SPANSTATUS.OK)
                    except Exception:
                        transaction.set_status(SPANSTATUS.INTERNAL_ERROR)
                        exc_info = sys.exc_info()
                        _capture_exception(exc_info)
                        reraise(*exc_info)

                    return result

            _insert_sentry_tracing_in_signature(new_func)

            if f:
                rv = old_remote(new_func)
            else:
                rv = old_remote(*args, **kwargs)(new_func)
            old_remote_method = rv.remote

            def _remote_method_with_header_propagation(
                *args: "Any", **kwargs: "Any"
            ) -> "Any":
                """
                Ray Client
                """
                with sentry_sdk.start_span(
                    op=OP.QUEUE_SUBMIT_RAY,
                    name=qualname_from_function(user_f),
                    origin=RayIntegration.origin,
                ) as span:
                    tracing = {
                        k: v
                        for k, v in sentry_sdk.get_current_scope().iter_trace_propagation_headers()
                    }
                    try:
                        result = old_remote_method(
                            *args, **kwargs, _sentry_tracing=tracing
                        )
                        span.set_status(SPANSTATUS.OK)
                    except Exception:
                        span.set_status(SPANSTATUS.INTERNAL_ERROR)
                        exc_info = sys.exc_info()
                        _capture_exception(exc_info)
                        reraise(*exc_info)

                    return result

            rv.remote = _remote_method_with_header_propagation

            return rv

        if f is not None:
            return wrapper(f)
        else:
            return wrapper

    ray.remote = new_remote


def _capture_exception(exc_info: "ExcInfo", **kwargs: "Any") -> None:
    client = sentry_sdk.get_client()

    event, hint = event_from_exception(
        exc_info,
        client_options=client.options,
        mechanism={
            "handled": False,
            "type": RayIntegration.identifier,
        },
    )
    sentry_sdk.capture_event(event, hint=hint)


class RayIntegration(Integration):
    identifier = "ray"
    origin = f"auto.queue.{identifier}"

    @staticmethod
    def setup_once() -> None:
        version = package_version("ray")
        _check_minimum_version(RayIntegration, version)

        _patch_ray_remote()
