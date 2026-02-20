import enum

import sentry_sdk
from sentry_sdk.integrations import Integration, DidNotEnable
from sentry_sdk.integrations.logging import (
    BreadcrumbHandler,
    EventHandler,
    _BaseHandler,
)
from sentry_sdk.logger import _log_level_to_otel
from sentry_sdk.utils import has_logs_enabled, safe_repr

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import LogRecord
    from typing import Any, Optional

try:
    import loguru
    from loguru import logger
    from loguru._defaults import LOGURU_FORMAT as DEFAULT_FORMAT

    if TYPE_CHECKING:
        from loguru import Message
except ImportError:
    raise DidNotEnable("LOGURU is not installed")


class LoggingLevels(enum.IntEnum):
    TRACE = 5
    DEBUG = 10
    INFO = 20
    SUCCESS = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


DEFAULT_LEVEL = LoggingLevels.INFO.value
DEFAULT_EVENT_LEVEL = LoggingLevels.ERROR.value


SENTRY_LEVEL_FROM_LOGURU_LEVEL = {
    "TRACE": "DEBUG",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "SUCCESS": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}

# Map Loguru level numbers to corresponding OTel level numbers
SEVERITY_TO_OTEL_SEVERITY = {
    LoggingLevels.CRITICAL: 21,  # fatal
    LoggingLevels.ERROR: 17,  # error
    LoggingLevels.WARNING: 13,  # warn
    LoggingLevels.SUCCESS: 11,  # info
    LoggingLevels.INFO: 9,  # info
    LoggingLevels.DEBUG: 5,  # debug
    LoggingLevels.TRACE: 1,  # trace
}


class LoguruIntegration(Integration):
    identifier = "loguru"

    level: "Optional[int]" = DEFAULT_LEVEL
    event_level: "Optional[int]" = DEFAULT_EVENT_LEVEL
    breadcrumb_format = DEFAULT_FORMAT
    event_format = DEFAULT_FORMAT
    sentry_logs_level: "Optional[int]" = DEFAULT_LEVEL

    def __init__(
        self,
        level: "Optional[int]" = DEFAULT_LEVEL,
        event_level: "Optional[int]" = DEFAULT_EVENT_LEVEL,
        breadcrumb_format: "str | loguru.FormatFunction" = DEFAULT_FORMAT,
        event_format: "str | loguru.FormatFunction" = DEFAULT_FORMAT,
        sentry_logs_level: "Optional[int]" = DEFAULT_LEVEL,
    ) -> None:
        LoguruIntegration.level = level
        LoguruIntegration.event_level = event_level
        LoguruIntegration.breadcrumb_format = breadcrumb_format
        LoguruIntegration.event_format = event_format
        LoguruIntegration.sentry_logs_level = sentry_logs_level

    @staticmethod
    def setup_once() -> None:
        if LoguruIntegration.level is not None:
            logger.add(
                LoguruBreadcrumbHandler(level=LoguruIntegration.level),
                level=LoguruIntegration.level,
                format=LoguruIntegration.breadcrumb_format,
            )

        if LoguruIntegration.event_level is not None:
            logger.add(
                LoguruEventHandler(level=LoguruIntegration.event_level),
                level=LoguruIntegration.event_level,
                format=LoguruIntegration.event_format,
            )

        if LoguruIntegration.sentry_logs_level is not None:
            logger.add(
                loguru_sentry_logs_handler,
                level=LoguruIntegration.sentry_logs_level,
            )


class _LoguruBaseHandler(_BaseHandler):
    def __init__(self, *args: "Any", **kwargs: "Any") -> None:
        if kwargs.get("level"):
            kwargs["level"] = SENTRY_LEVEL_FROM_LOGURU_LEVEL.get(
                kwargs.get("level", ""), DEFAULT_LEVEL
            )

        super().__init__(*args, **kwargs)

    def _logging_to_event_level(self, record: "LogRecord") -> str:
        try:
            return SENTRY_LEVEL_FROM_LOGURU_LEVEL[
                LoggingLevels(record.levelno).name
            ].lower()
        except (ValueError, KeyError):
            return record.levelname.lower() if record.levelname else ""


class LoguruEventHandler(_LoguruBaseHandler, EventHandler):
    """Modified version of :class:`sentry_sdk.integrations.logging.EventHandler` to use loguru's level names."""

    pass


class LoguruBreadcrumbHandler(_LoguruBaseHandler, BreadcrumbHandler):
    """Modified version of :class:`sentry_sdk.integrations.logging.BreadcrumbHandler` to use loguru's level names."""

    pass


def loguru_sentry_logs_handler(message: "Message") -> None:
    # This is intentionally a callable sink instead of a standard logging handler
    # since otherwise we wouldn't get direct access to message.record
    client = sentry_sdk.get_client()

    if not client.is_active():
        return

    if not has_logs_enabled(client.options):
        return

    record = message.record

    if (
        LoguruIntegration.sentry_logs_level is None
        or record["level"].no < LoguruIntegration.sentry_logs_level
    ):
        return

    otel_severity_number, otel_severity_text = _log_level_to_otel(
        record["level"].no, SEVERITY_TO_OTEL_SEVERITY
    )

    attrs: "dict[str, Any]" = {"sentry.origin": "auto.log.loguru"}

    project_root = client.options["project_root"]
    if record.get("file"):
        if project_root is not None and record["file"].path.startswith(project_root):
            attrs["code.file.path"] = record["file"].path[len(project_root) + 1 :]
        else:
            attrs["code.file.path"] = record["file"].path

    if record.get("line") is not None:
        attrs["code.line.number"] = record["line"]

    if record.get("function"):
        attrs["code.function.name"] = record["function"]

    if record.get("thread"):
        attrs["thread.name"] = record["thread"].name
        attrs["thread.id"] = record["thread"].id

    if record.get("process"):
        attrs["process.pid"] = record["process"].id
        attrs["process.executable.name"] = record["process"].name

    if record.get("name"):
        attrs["logger.name"] = record["name"]

    extra = record.get("extra")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if isinstance(value, (str, int, float, bool)):
                attrs[f"sentry.message.parameter.{key}"] = value
            else:
                attrs[f"sentry.message.parameter.{key}"] = safe_repr(value)

    sentry_sdk.get_current_scope()._capture_log(
        {
            "severity_text": otel_severity_text,
            "severity_number": otel_severity_number,
            "body": record["message"],
            "attributes": attrs,
            "time_unix_nano": int(record["time"].timestamp() * 1e9),
            "trace_id": None,
            "span_id": None,
        }
    )
