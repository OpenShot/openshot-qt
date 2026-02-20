import sys
import functools

import sentry_sdk
from sentry_sdk.consts import OP
from sentry_sdk.integrations import Integration, DidNotEnable
from sentry_sdk.integrations._wsgi_common import nullcontext
from sentry_sdk.utils import event_from_exception, logger, reraise

try:
    import asyncio
    from asyncio.tasks import Task
except ImportError:
    raise DidNotEnable("asyncio not available")

from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, TypeVar
    from collections.abc import Coroutine

    from sentry_sdk._types import ExcInfo

    T = TypeVar("T", bound=Callable[..., Any])


def get_name(coro: "Any") -> str:
    return (
        getattr(coro, "__qualname__", None)
        or getattr(coro, "__name__", None)
        or "coroutine without __name__"
    )


def _wrap_coroutine(wrapped: "Coroutine[Any, Any, Any]") -> "Callable[[T], T]":
    # Only __name__ and __qualname__ are copied from function to coroutine in CPython
    return functools.partial(
        functools.update_wrapper,
        wrapped=wrapped,  # type: ignore
        assigned=("__name__", "__qualname__"),
        updated=(),
    )


def patch_asyncio() -> None:
    orig_task_factory = None
    try:
        loop = asyncio.get_running_loop()
        orig_task_factory = loop.get_task_factory()

        # Check if already patched
        if getattr(orig_task_factory, "_is_sentry_task_factory", False):
            return

        def _sentry_task_factory(
            loop: "asyncio.AbstractEventLoop",
            coro: "Coroutine[Any, Any, Any]",
            **kwargs: "Any",
        ) -> "asyncio.Future[Any]":
            @_wrap_coroutine(coro)
            async def _task_with_sentry_span_creation() -> "Any":
                result = None

                integration = sentry_sdk.get_client().get_integration(
                    AsyncioIntegration
                )
                task_spans = integration.task_spans if integration else False

                with sentry_sdk.isolation_scope():
                    with (
                        sentry_sdk.start_span(
                            op=OP.FUNCTION,
                            name=get_name(coro),
                            origin=AsyncioIntegration.origin,
                        )
                        if task_spans
                        else nullcontext()
                    ):
                        try:
                            result = await coro
                        except StopAsyncIteration as e:
                            raise e from None
                        except Exception:
                            reraise(*_capture_exception())

                return result

            task = None

            # Trying to use user set task factory (if there is one)
            if orig_task_factory:
                task = orig_task_factory(
                    loop, _task_with_sentry_span_creation(), **kwargs
                )

            if task is None:
                # The default task factory in `asyncio` does not have its own function
                # but is just a couple of lines in `asyncio.base_events.create_task()`
                # Those lines are copied here.

                # WARNING:
                # If the default behavior of the task creation in asyncio changes,
                # this will break!
                task = Task(_task_with_sentry_span_creation(), loop=loop, **kwargs)
                if task._source_traceback:  # type: ignore
                    del task._source_traceback[-1]  # type: ignore

            # Set the task name to include the original coroutine's name
            try:
                cast("asyncio.Task[Any]", task).set_name(
                    f"{get_name(coro)} (Sentry-wrapped)"
                )
            except AttributeError:
                # set_name might not be available in all Python versions
                pass

            return task

        _sentry_task_factory._is_sentry_task_factory = True  # type: ignore
        loop.set_task_factory(_sentry_task_factory)  # type: ignore

    except RuntimeError:
        # When there is no running loop, we have nothing to patch.
        logger.warning(
            "There is no running asyncio loop so there is nothing Sentry can patch. "
            "Please make sure you call sentry_sdk.init() within a running "
            "asyncio loop for the AsyncioIntegration to work. "
            "See https://docs.sentry.io/platforms/python/integrations/asyncio/"
        )


def _capture_exception() -> "ExcInfo":
    exc_info = sys.exc_info()

    client = sentry_sdk.get_client()

    integration = client.get_integration(AsyncioIntegration)
    if integration is not None:
        event, hint = event_from_exception(
            exc_info,
            client_options=client.options,
            mechanism={"type": "asyncio", "handled": False},
        )
        sentry_sdk.capture_event(event, hint=hint)

    return exc_info


class AsyncioIntegration(Integration):
    identifier = "asyncio"
    origin = f"auto.function.{identifier}"

    def __init__(self, task_spans: bool = True) -> None:
        self.task_spans = task_spans

    @staticmethod
    def setup_once() -> None:
        patch_asyncio()


def enable_asyncio_integration(*args: "Any", **kwargs: "Any") -> None:
    """
    Enable AsyncioIntegration with the provided options.

    This is useful in scenarios where Sentry needs to be initialized before
    an event loop is set up, but you still want to instrument asyncio once there
    is an event loop. In that case, you can sentry_sdk.init() early on without
    the AsyncioIntegration and then, once the event loop has been set up,
    execute:

    ```python
    from sentry_sdk.integrations.asyncio import enable_asyncio_integration

    async def async_entrypoint():
        enable_asyncio_integration()
    ```

    Any arguments provided will be passed to AsyncioIntegration() as is.

    If AsyncioIntegration has already patched the current event loop, this
    function won't have any effect.

    If AsyncioIntegration was provided in
    sentry_sdk.init(disabled_integrations=[...]), this function will ignore that
    and the integration will be enabled.
    """
    client = sentry_sdk.get_client()
    if not client.is_active():
        return

    # This function purposefully bypasses the integration machinery in
    # integrations/__init__.py. _installed_integrations/_processed_integrations
    # is used to prevent double patching the same module, but in the case of
    # the AsyncioIntegration, we don't monkeypatch the standard library directly,
    # we patch the currently running event loop, and we keep the record of doing
    # that on the loop itself.
    logger.debug("Setting up integration asyncio")

    integration = AsyncioIntegration(*args, **kwargs)
    integration.setup_once()

    if "asyncio" not in client.integrations:
        client.integrations["asyncio"] = integration
