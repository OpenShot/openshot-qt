from functools import wraps
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterator,
    List,
)

import sentry_sdk
from sentry_sdk.ai.utils import get_start_span_function
from sentry_sdk.integrations import DidNotEnable, Integration
from sentry_sdk.consts import OP, SPANDATA
from sentry_sdk.tracing import SPANSTATUS


try:
    from google.genai.models import Models, AsyncModels
except ImportError:
    raise DidNotEnable("google-genai not installed")


from .consts import IDENTIFIER, ORIGIN, GEN_AI_SYSTEM
from .utils import (
    set_span_data_for_request,
    set_span_data_for_response,
    _capture_exception,
    prepare_generate_content_args,
    prepare_embed_content_args,
    set_span_data_for_embed_request,
    set_span_data_for_embed_response,
)
from .streaming import (
    set_span_data_for_streaming_response,
    accumulate_streaming_response,
)


class GoogleGenAIIntegration(Integration):
    identifier = IDENTIFIER
    origin = ORIGIN

    def __init__(self: "GoogleGenAIIntegration", include_prompts: bool = True) -> None:
        self.include_prompts = include_prompts

    @staticmethod
    def setup_once() -> None:
        # Patch sync methods
        Models.generate_content = _wrap_generate_content(Models.generate_content)
        Models.generate_content_stream = _wrap_generate_content_stream(
            Models.generate_content_stream
        )
        Models.embed_content = _wrap_embed_content(Models.embed_content)

        # Patch async methods
        AsyncModels.generate_content = _wrap_async_generate_content(
            AsyncModels.generate_content
        )
        AsyncModels.generate_content_stream = _wrap_async_generate_content_stream(
            AsyncModels.generate_content_stream
        )
        AsyncModels.embed_content = _wrap_async_embed_content(AsyncModels.embed_content)


def _wrap_generate_content_stream(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    def new_generate_content_stream(
        self: "Any", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        integration = sentry_sdk.get_client().get_integration(GoogleGenAIIntegration)
        if integration is None:
            return f(self, *args, **kwargs)

        _model, contents, model_name = prepare_generate_content_args(args, kwargs)

        span = get_start_span_function()(
            op=OP.GEN_AI_INVOKE_AGENT,
            name="invoke_agent",
            origin=ORIGIN,
        )
        span.__enter__()
        span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)
        span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "invoke_agent")
        set_span_data_for_request(span, integration, model_name, contents, kwargs)
        span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)

        chat_span = sentry_sdk.start_span(
            op=OP.GEN_AI_CHAT,
            name=f"chat {model_name}",
            origin=ORIGIN,
        )
        chat_span.__enter__()
        chat_span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "chat")
        chat_span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
        chat_span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)
        set_span_data_for_request(chat_span, integration, model_name, contents, kwargs)
        chat_span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)
        chat_span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)

        try:
            stream = f(self, *args, **kwargs)

            # Create wrapper iterator to accumulate responses
            def new_iterator() -> "Iterator[Any]":
                chunks: "List[Any]" = []
                try:
                    for chunk in stream:
                        chunks.append(chunk)
                        yield chunk
                except Exception as exc:
                    _capture_exception(exc)
                    chat_span.set_status(SPANSTATUS.INTERNAL_ERROR)
                    raise
                finally:
                    # Accumulate all chunks and set final response data on spans
                    if chunks:
                        accumulated_response = accumulate_streaming_response(chunks)
                        set_span_data_for_streaming_response(
                            chat_span, integration, accumulated_response
                        )
                        set_span_data_for_streaming_response(
                            span, integration, accumulated_response
                        )
                    chat_span.__exit__(None, None, None)
                    span.__exit__(None, None, None)

            return new_iterator()

        except Exception as exc:
            _capture_exception(exc)
            chat_span.__exit__(None, None, None)
            span.__exit__(None, None, None)
            raise

    return new_generate_content_stream


def _wrap_async_generate_content_stream(
    f: "Callable[..., Any]",
) -> "Callable[..., Any]":
    @wraps(f)
    async def new_async_generate_content_stream(
        self: "Any", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        integration = sentry_sdk.get_client().get_integration(GoogleGenAIIntegration)
        if integration is None:
            return await f(self, *args, **kwargs)

        _model, contents, model_name = prepare_generate_content_args(args, kwargs)

        span = get_start_span_function()(
            op=OP.GEN_AI_INVOKE_AGENT,
            name="invoke_agent",
            origin=ORIGIN,
        )
        span.__enter__()
        span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)
        span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "invoke_agent")
        set_span_data_for_request(span, integration, model_name, contents, kwargs)
        span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)

        chat_span = sentry_sdk.start_span(
            op=OP.GEN_AI_CHAT,
            name=f"chat {model_name}",
            origin=ORIGIN,
        )
        chat_span.__enter__()
        chat_span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "chat")
        chat_span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
        chat_span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)
        set_span_data_for_request(chat_span, integration, model_name, contents, kwargs)
        chat_span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)
        chat_span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)

        try:
            stream = await f(self, *args, **kwargs)

            # Create wrapper async iterator to accumulate responses
            async def new_async_iterator() -> "AsyncIterator[Any]":
                chunks: "List[Any]" = []
                try:
                    async for chunk in stream:
                        chunks.append(chunk)
                        yield chunk
                except Exception as exc:
                    _capture_exception(exc)
                    chat_span.set_status(SPANSTATUS.INTERNAL_ERROR)
                    raise
                finally:
                    # Accumulate all chunks and set final response data on spans
                    if chunks:
                        accumulated_response = accumulate_streaming_response(chunks)
                        set_span_data_for_streaming_response(
                            chat_span, integration, accumulated_response
                        )
                        set_span_data_for_streaming_response(
                            span, integration, accumulated_response
                        )
                    chat_span.__exit__(None, None, None)
                    span.__exit__(None, None, None)

            return new_async_iterator()

        except Exception as exc:
            _capture_exception(exc)
            chat_span.__exit__(None, None, None)
            span.__exit__(None, None, None)
            raise

    return new_async_generate_content_stream


def _wrap_generate_content(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    def new_generate_content(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(GoogleGenAIIntegration)
        if integration is None:
            return f(self, *args, **kwargs)

        model, contents, model_name = prepare_generate_content_args(args, kwargs)

        with get_start_span_function()(
            op=OP.GEN_AI_INVOKE_AGENT,
            name="invoke_agent",
            origin=ORIGIN,
        ) as span:
            span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)
            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "invoke_agent")
            set_span_data_for_request(span, integration, model_name, contents, kwargs)

            with sentry_sdk.start_span(
                op=OP.GEN_AI_CHAT,
                name=f"chat {model_name}",
                origin=ORIGIN,
            ) as chat_span:
                chat_span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "chat")
                chat_span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
                chat_span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)
                chat_span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)
                set_span_data_for_request(
                    chat_span, integration, model_name, contents, kwargs
                )

                try:
                    response = f(self, *args, **kwargs)
                except Exception as exc:
                    _capture_exception(exc)
                    chat_span.set_status(SPANSTATUS.INTERNAL_ERROR)
                    raise

                set_span_data_for_response(chat_span, integration, response)
                set_span_data_for_response(span, integration, response)

                return response

    return new_generate_content


def _wrap_async_generate_content(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    async def new_async_generate_content(
        self: "Any", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        integration = sentry_sdk.get_client().get_integration(GoogleGenAIIntegration)
        if integration is None:
            return await f(self, *args, **kwargs)

        model, contents, model_name = prepare_generate_content_args(args, kwargs)

        with get_start_span_function()(
            op=OP.GEN_AI_INVOKE_AGENT,
            name="invoke_agent",
            origin=ORIGIN,
        ) as span:
            span.set_data(SPANDATA.GEN_AI_AGENT_NAME, model_name)
            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "invoke_agent")
            set_span_data_for_request(span, integration, model_name, contents, kwargs)

            with sentry_sdk.start_span(
                op=OP.GEN_AI_CHAT,
                name=f"chat {model_name}",
                origin=ORIGIN,
            ) as chat_span:
                chat_span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "chat")
                chat_span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
                chat_span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)
                set_span_data_for_request(
                    chat_span, integration, model_name, contents, kwargs
                )
                try:
                    response = await f(self, *args, **kwargs)
                except Exception as exc:
                    _capture_exception(exc)
                    chat_span.set_status(SPANSTATUS.INTERNAL_ERROR)
                    raise

                set_span_data_for_response(chat_span, integration, response)
                set_span_data_for_response(span, integration, response)

                return response

    return new_async_generate_content


def _wrap_embed_content(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    def new_embed_content(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(GoogleGenAIIntegration)
        if integration is None:
            return f(self, *args, **kwargs)

        model_name, contents = prepare_embed_content_args(args, kwargs)

        with sentry_sdk.start_span(
            op=OP.GEN_AI_EMBEDDINGS,
            name=f"embeddings {model_name}",
            origin=ORIGIN,
        ) as span:
            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "embeddings")
            span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
            span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)
            set_span_data_for_embed_request(span, integration, contents, kwargs)

            try:
                response = f(self, *args, **kwargs)
            except Exception as exc:
                _capture_exception(exc)
                span.set_status(SPANSTATUS.INTERNAL_ERROR)
                raise

            set_span_data_for_embed_response(span, integration, response)

            return response

    return new_embed_content


def _wrap_async_embed_content(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    async def new_async_embed_content(
        self: "Any", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        integration = sentry_sdk.get_client().get_integration(GoogleGenAIIntegration)
        if integration is None:
            return await f(self, *args, **kwargs)

        model_name, contents = prepare_embed_content_args(args, kwargs)

        with sentry_sdk.start_span(
            op=OP.GEN_AI_EMBEDDINGS,
            name=f"embeddings {model_name}",
            origin=ORIGIN,
        ) as span:
            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "embeddings")
            span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
            span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)
            set_span_data_for_embed_request(span, integration, contents, kwargs)

            try:
                response = await f(self, *args, **kwargs)
            except Exception as exc:
                _capture_exception(exc)
                span.set_status(SPANSTATUS.INTERNAL_ERROR)
                raise

            set_span_data_for_embed_response(span, integration, response)

            return response

    return new_async_embed_content
