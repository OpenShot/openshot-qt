from typing import TYPE_CHECKING

from sentry_sdk._batcher import Batcher
from sentry_sdk.utils import serialize_attribute
from sentry_sdk.envelope import Envelope, Item, PayloadRef

if TYPE_CHECKING:
    from typing import Any
    from sentry_sdk._types import Log


class LogBatcher(Batcher["Log"]):
    MAX_BEFORE_FLUSH = 100
    MAX_BEFORE_DROP = 1_000
    FLUSH_WAIT_TIME = 5.0

    TYPE = "log"
    CONTENT_TYPE = "application/vnd.sentry.items.log+json"

    @staticmethod
    def _to_transport_format(item: "Log") -> "Any":
        if "sentry.severity_number" not in item["attributes"]:
            item["attributes"]["sentry.severity_number"] = item["severity_number"]
        if "sentry.severity_text" not in item["attributes"]:
            item["attributes"]["sentry.severity_text"] = item["severity_text"]

        res = {
            "timestamp": int(item["time_unix_nano"]) / 1.0e9,
            "trace_id": item.get("trace_id", "00000000-0000-0000-0000-000000000000"),
            "span_id": item.get("span_id"),
            "level": str(item["severity_text"]),
            "body": str(item["body"]),
            "attributes": {
                k: serialize_attribute(v) for (k, v) in item["attributes"].items()
            },
        }

        return res

    def _record_lost(self, item: "Log") -> None:
        # Construct log envelope item without sending it to report lost bytes
        log_item = Item(
            type=self.TYPE,
            content_type=self.CONTENT_TYPE,
            headers={
                "item_count": 1,
            },
            payload=PayloadRef(json={"items": [self._to_transport_format(item)]}),
        )

        self._record_lost_func(
            reason="queue_overflow",
            data_category="log_item",
            item=log_item,
            quantity=1,
        )
