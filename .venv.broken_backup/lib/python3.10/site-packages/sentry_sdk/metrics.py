import time
from typing import Any, Optional, TYPE_CHECKING, Union

import sentry_sdk
from sentry_sdk.utils import format_attribute, safe_repr

if TYPE_CHECKING:
    from sentry_sdk._types import Attributes, Metric, MetricType


def _capture_metric(
    name: str,
    metric_type: "MetricType",
    value: float,
    unit: "Optional[str]" = None,
    attributes: "Optional[Attributes]" = None,
) -> None:
    attrs: "Attributes" = {}

    if attributes:
        for k, v in attributes.items():
            attrs[k] = format_attribute(v)

    metric: "Metric" = {
        "timestamp": time.time(),
        "trace_id": None,
        "span_id": None,
        "name": name,
        "type": metric_type,
        "value": float(value),
        "unit": unit,
        "attributes": attrs,
    }

    sentry_sdk.get_current_scope()._capture_metric(metric)


def count(
    name: str,
    value: float,
    unit: "Optional[str]" = None,
    attributes: "Optional[dict[str, Any]]" = None,
) -> None:
    _capture_metric(name, "counter", value, unit, attributes)


def gauge(
    name: str,
    value: float,
    unit: "Optional[str]" = None,
    attributes: "Optional[dict[str, Any]]" = None,
) -> None:
    _capture_metric(name, "gauge", value, unit, attributes)


def distribution(
    name: str,
    value: float,
    unit: "Optional[str]" = None,
    attributes: "Optional[dict[str, Any]]" = None,
) -> None:
    _capture_metric(name, "distribution", value, unit, attributes)
