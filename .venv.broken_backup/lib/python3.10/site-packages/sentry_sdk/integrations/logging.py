import logging
import sys
from datetime import datetime, timezone
from fnmatch import fnmatch

import sentry_sdk
from sentry_sdk.client import BaseClient
from sentry_sdk.logger import _log_level_to_otel
from sentry_sdk.utils import (
    safe_repr,
    to_string,
    event_from_exception,
    current_stacktrace,
    capture_internal_exceptions,
    has_logs_enabled,
)
from sentry_sdk.integrations import Integration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from logging import LogRecord
    from typing import Any
    from typing import Dict
    from typing import Optional

DEFAULT_LEVEL = logging.INFO
DEFAULT_EVENT_LEVEL = logging.ERROR
LOGGING_TO_EVENT_LEVEL = {
    logging.NOTSET: "notset",
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARN: "warning",  # WARN is same a WARNING
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.FATAL: "fatal",
    logging.CRITICAL: "fatal",  # CRITICAL is same as FATAL
}

# Map logging level numbers to corresponding OTel level numbers
SEVERITY_TO_OTEL_SEVERITY = {
    logging.CRITICAL: 21,  # fatal
    logging.ERROR: 17,  # error
    logging.WARNING: 13,  # warn
    logging.INFO: 9,  # info
    logging.DEBUG: 5,  # debug
}


# Capturing events from those loggers causes recursion errors. We cannot allow
# the user to unconditionally create events from those loggers under any
# circumstances.
#
# Note: Ignoring by logger name here is better than mucking with thread-locals.
# We do not necessarily know whether thread-locals work 100% correctly in the user's environment.
_IGNORED_LOGGERS = set(
    ["sentry_sdk.errors", "urllib3.connectionpool", "urllib3.connection"]
)


def ignore_logger(
    name: str,
) -> None:
    """This disables recording (both in breadcrumbs and as events) calls to
    a logger of a specific name.  Among other uses, many of our integrations
    use this to prevent their actions being recorded as breadcrumbs. Exposed
    to users as a way to quiet spammy loggers.

    :param name: The name of the logger to ignore (same string you would pass to ``logging.getLogger``).
    """
    _IGNORED_LOGGERS.add(name)


class LoggingIntegration(Integration):
    identifier = "logging"

    def __init__(
        self,
        level: "Optional[int]" = DEFAULT_LEVEL,
        event_level: "Optional[int]" = DEFAULT_EVENT_LEVEL,
        sentry_logs_level: "Optional[int]" = DEFAULT_LEVEL,
    ) -> None:
        self._handler = None
        self._breadcrumb_handler = None
        self._sentry_logs_handler = None

        if level is not None:
            self._breadcrumb_handler = BreadcrumbHandler(level=level)

        if sentry_logs_level is not None:
            self._sentry_logs_handler = SentryLogsHandler(level=sentry_logs_level)

        if event_level is not None:
            self._handler = EventHandler(level=event_level)

    def _handle_record(self, record: "LogRecord") -> None:
        if self._handler is not None and record.levelno >= self._handler.level:
            self._handler.handle(record)

        if (
            self._breadcrumb_handler is not None
            and record.levelno >= self._breadcrumb_handler.level
        ):
            self._breadcrumb_handler.handle(record)

        if (
            self._sentry_logs_handler is not None
            and record.levelno >= self._sentry_logs_handler.level
        ):
            self._sentry_logs_handler.handle(record)

    @staticmethod
    def setup_once() -> None:
        old_callhandlers = logging.Logger.callHandlers

        def sentry_patched_callhandlers(self: "Any", record: "LogRecord") -> "Any":
            # keeping a local reference because the
            # global might be discarded on shutdown
            ignored_loggers = _IGNORED_LOGGERS

            try:
                return old_callhandlers(self, record)
            finally:
                # This check is done twice, once also here before we even get
                # the integration.  Otherwise we have a high chance of getting
                # into a recursion error when the integration is resolved
                # (this also is slower).
                if (
                    ignored_loggers is not None
                    and record.name.strip() not in ignored_loggers
                ):
                    integration = sentry_sdk.get_client().get_integration(
                        LoggingIntegration
                    )
                    if integration is not None:
                        integration._handle_record(record)

        logging.Logger.callHandlers = sentry_patched_callhandlers  # type: ignore


class _BaseHandler(logging.Handler):
    COMMON_RECORD_ATTRS = frozenset(
        (
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "linenno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack",
            "tags",
            "taskName",
            "thread",
            "threadName",
            "stack_info",
        )
    )

    def _can_record(self, record: "LogRecord") -> bool:
        """Prevents ignored loggers from recording"""
        for logger in _IGNORED_LOGGERS:
            if fnmatch(record.name.strip(), logger):
                return False
        return True

    def _logging_to_event_level(self, record: "LogRecord") -> str:
        return LOGGING_TO_EVENT_LEVEL.get(
            record.levelno, record.levelname.lower() if record.levelname else ""
        )

    def _extra_from_record(self, record: "LogRecord") -> "MutableMapping[str, object]":
        return {
            k: v
            for k, v in vars(record).items()
            if k not in self.COMMON_RECORD_ATTRS
            and (not isinstance(k, str) or not k.startswith("_"))
        }


class EventHandler(_BaseHandler):
    """
    A logging handler that emits Sentry events for each log record

    Note that you do not have to use this class if the logging integration is enabled, which it is by default.
    """

    def emit(self, record: "LogRecord") -> "Any":
        with capture_internal_exceptions():
            self.format(record)
            return self._emit(record)

    def _emit(self, record: "LogRecord") -> None:
        if not self._can_record(record):
            return

        client = sentry_sdk.get_client()
        if not client.is_active():
            return

        client_options = client.options

        # exc_info might be None or (None, None, None)
        #
        # exc_info may also be any falsy value due to Python stdlib being
        # liberal with what it receives and Celery's billiard being "liberal"
        # with what it sends. See
        # https://github.com/getsentry/sentry-python/issues/904
        if record.exc_info and record.exc_info[0] is not None:
            event, hint = event_from_exception(
                record.exc_info,
                client_options=client_options,
                mechanism={"type": "logging", "handled": True},
            )
        elif (record.exc_info and record.exc_info[0] is None) or record.stack_info:
            event = {}
            hint = {}
            with capture_internal_exceptions():
                event["threads"] = {
                    "values": [
                        {
                            "stacktrace": current_stacktrace(
                                include_local_variables=client_options[
                                    "include_local_variables"
                                ],
                                max_value_length=client_options["max_value_length"],
                            ),
                            "crashed": False,
                            "current": True,
                        }
                    ]
                }
        else:
            event = {}
            hint = {}

        hint["log_record"] = record

        level = self._logging_to_event_level(record)
        if level in {"debug", "info", "warning", "error", "critical", "fatal"}:
            event["level"] = level  # type: ignore[typeddict-item]
        event["logger"] = record.name

        if (
            sys.version_info < (3, 11)
            and record.name == "py.warnings"
            and record.msg == "%s"
        ):
            # warnings module on Python 3.10 and below sets record.msg to "%s"
            # and record.args[0] to the actual warning message.
            # This was fixed in https://github.com/python/cpython/pull/30975.
            message = record.args[0]
            params = ()
        else:
            message = record.msg
            params = record.args

        event["logentry"] = {
            "message": to_string(message),
            "formatted": record.getMessage(),
            "params": params,
        }

        event["extra"] = self._extra_from_record(record)

        sentry_sdk.capture_event(event, hint=hint)


# Legacy name
SentryHandler = EventHandler


class BreadcrumbHandler(_BaseHandler):
    """
    A logging handler that records breadcrumbs for each log record.

    Note that you do not have to use this class if the logging integration is enabled, which it is by default.
    """

    def emit(self, record: "LogRecord") -> "Any":
        with capture_internal_exceptions():
            self.format(record)
            return self._emit(record)

    def _emit(self, record: "LogRecord") -> None:
        if not self._can_record(record):
            return

        sentry_sdk.add_breadcrumb(
            self._breadcrumb_from_record(record), hint={"log_record": record}
        )

    def _breadcrumb_from_record(self, record: "LogRecord") -> "Dict[str, Any]":
        return {
            "type": "log",
            "level": self._logging_to_event_level(record),
            "category": record.name,
            "message": record.message,
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc),
            "data": self._extra_from_record(record),
        }


class SentryLogsHandler(_BaseHandler):
    """
    A logging handler that records Sentry logs for each Python log record.

    Note that you do not have to use this class if the logging integration is enabled, which it is by default.
    """

    def emit(self, record: "LogRecord") -> "Any":
        with capture_internal_exceptions():
            self.format(record)
            if not self._can_record(record):
                return

            client = sentry_sdk.get_client()
            if not client.is_active():
                return

            if not has_logs_enabled(client.options):
                return

            self._capture_log_from_record(client, record)

    def _capture_log_from_record(
        self, client: "BaseClient", record: "LogRecord"
    ) -> None:
        otel_severity_number, otel_severity_text = _log_level_to_otel(
            record.levelno, SEVERITY_TO_OTEL_SEVERITY
        )
        project_root = client.options["project_root"]

        attrs: "Any" = self._extra_from_record(record)
        attrs["sentry.origin"] = "auto.log.stdlib"

        parameters_set = False
        if record.args is not None:
            if isinstance(record.args, tuple):
                parameters_set = bool(record.args)
                for i, arg in enumerate(record.args):
                    attrs[f"sentry.message.parameter.{i}"] = (
                        arg
                        if isinstance(arg, (str, float, int, bool))
                        else safe_repr(arg)
                    )
            elif isinstance(record.args, dict):
                parameters_set = bool(record.args)
                for key, value in record.args.items():
                    attrs[f"sentry.message.parameter.{key}"] = (
                        value
                        if isinstance(value, (str, float, int, bool))
                        else safe_repr(value)
                    )

        if parameters_set and isinstance(record.msg, str):
            # only include template if there is at least one
            # sentry.message.parameter.X set
            attrs["sentry.message.template"] = record.msg

        if record.lineno:
            attrs["code.line.number"] = record.lineno

        if record.pathname:
            if project_root is not None and record.pathname.startswith(project_root):
                attrs["code.file.path"] = record.pathname[len(project_root) + 1 :]
            else:
                attrs["code.file.path"] = record.pathname

        if record.funcName:
            attrs["code.function.name"] = record.funcName

        if record.thread:
            attrs["thread.id"] = record.thread
        if record.threadName:
            attrs["thread.name"] = record.threadName

        if record.process:
            attrs["process.pid"] = record.process
        if record.processName:
            attrs["process.executable.name"] = record.processName
        if record.name:
            attrs["logger.name"] = record.name

        # noinspection PyProtectedMember
        sentry_sdk.get_current_scope()._capture_log(
            {
                "severity_text": otel_severity_text,
                "severity_number": otel_severity_number,
                "body": record.message,
                "attributes": attrs,
                "time_unix_nano": int(record.created * 1e9),
                "trace_id": None,
                "span_id": None,
            },
        )
