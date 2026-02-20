# NOTE: this is the logger sentry exposes to users, not some generic logger.
import functools
import time
from typing import Any, TYPE_CHECKING

import sentry_sdk
from sentry_sdk.utils import format_attribute, safe_repr, capture_internal_exceptions

if TYPE_CHECKING:
    from sentry_sdk._types import Attributes, Log


OTEL_RANGES = [
    # ((severity level range), severity text)
    # https://opentelemetry.io/docs/specs/otel/logs/data-model
    ((1, 4), "trace"),
    ((5, 8), "debug"),
    ((9, 12), "info"),
    ((13, 16), "warn"),
    ((17, 20), "error"),
    ((21, 24), "fatal"),
]


class _dict_default_key(dict):  # type: ignore[type-arg]
    """dict that returns the key if missing."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _capture_log(
    severity_text: str, severity_number: int, template: str, **kwargs: "Any"
) -> None:
    body = template

    attributes: "Attributes" = {}

    if "attributes" in kwargs:
        provided_attributes = kwargs.pop("attributes") or {}
        for attribute, value in provided_attributes.items():
            attributes[attribute] = format_attribute(value)

    for k, v in kwargs.items():
        attributes[f"sentry.message.parameter.{k}"] = format_attribute(v)

    if kwargs:
        # only attach template if there are parameters
        attributes["sentry.message.template"] = format_attribute(template)

        with capture_internal_exceptions():
            body = template.format_map(_dict_default_key(kwargs))

    sentry_sdk.get_current_scope()._capture_log(
        {
            "severity_text": severity_text,
            "severity_number": severity_number,
            "attributes": attributes,
            "body": body,
            "time_unix_nano": time.time_ns(),
            "trace_id": None,
            "span_id": None,
        }
    )


trace = functools.partial(_capture_log, "trace", 1)
debug = functools.partial(_capture_log, "debug", 5)
info = functools.partial(_capture_log, "info", 9)
warning = functools.partial(_capture_log, "warn", 13)
error = functools.partial(_capture_log, "error", 17)
fatal = functools.partial(_capture_log, "fatal", 21)


def _otel_severity_text(otel_severity_number: int) -> str:
    for (lower, upper), severity in OTEL_RANGES:
        if lower <= otel_severity_number <= upper:
            return severity

    return "default"


def _log_level_to_otel(level: int, mapping: "dict[Any, int]") -> "tuple[int, str]":
    for py_level, otel_severity_number in sorted(mapping.items(), reverse=True):
        if level >= py_level:
            return otel_severity_number, _otel_severity_text(otel_severity_number)

    return 0, "default"
