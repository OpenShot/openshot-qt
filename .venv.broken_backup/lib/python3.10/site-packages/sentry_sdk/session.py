import uuid
from datetime import datetime, timezone

from sentry_sdk.utils import format_timestamp

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional
    from typing import Union
    from typing import Any
    from typing import Dict

    from sentry_sdk._types import SessionStatus


def _minute_trunc(ts: "datetime") -> "datetime":
    return ts.replace(second=0, microsecond=0)


def _make_uuid(
    val: "Union[str, uuid.UUID]",
) -> "uuid.UUID":
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(val)


class Session:
    def __init__(
        self,
        sid: "Optional[Union[str, uuid.UUID]]" = None,
        did: "Optional[str]" = None,
        timestamp: "Optional[datetime]" = None,
        started: "Optional[datetime]" = None,
        duration: "Optional[float]" = None,
        status: "Optional[SessionStatus]" = None,
        release: "Optional[str]" = None,
        environment: "Optional[str]" = None,
        user_agent: "Optional[str]" = None,
        ip_address: "Optional[str]" = None,
        errors: "Optional[int]" = None,
        user: "Optional[Any]" = None,
        session_mode: str = "application",
    ) -> None:
        if sid is None:
            sid = uuid.uuid4()
        if started is None:
            started = datetime.now(timezone.utc)
        if status is None:
            status = "ok"
        self.status = status
        self.did: "Optional[str]" = None
        self.started = started
        self.release: "Optional[str]" = None
        self.environment: "Optional[str]" = None
        self.duration: "Optional[float]" = None
        self.user_agent: "Optional[str]" = None
        self.ip_address: "Optional[str]" = None
        self.session_mode: str = session_mode
        self.errors = 0

        self.update(
            sid=sid,
            did=did,
            timestamp=timestamp,
            duration=duration,
            release=release,
            environment=environment,
            user_agent=user_agent,
            ip_address=ip_address,
            errors=errors,
            user=user,
        )

    @property
    def truncated_started(self) -> "datetime":
        return _minute_trunc(self.started)

    def update(
        self,
        sid: "Optional[Union[str, uuid.UUID]]" = None,
        did: "Optional[str]" = None,
        timestamp: "Optional[datetime]" = None,
        started: "Optional[datetime]" = None,
        duration: "Optional[float]" = None,
        status: "Optional[SessionStatus]" = None,
        release: "Optional[str]" = None,
        environment: "Optional[str]" = None,
        user_agent: "Optional[str]" = None,
        ip_address: "Optional[str]" = None,
        errors: "Optional[int]" = None,
        user: "Optional[Any]" = None,
    ) -> None:
        # If a user is supplied we pull some data form it
        if user:
            if ip_address is None:
                ip_address = user.get("ip_address")
            if did is None:
                did = user.get("id") or user.get("email") or user.get("username")

        if sid is not None:
            self.sid = _make_uuid(sid)
        if did is not None:
            self.did = str(did)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        self.timestamp = timestamp
        if started is not None:
            self.started = started
        if duration is not None:
            self.duration = duration
        if release is not None:
            self.release = release
        if environment is not None:
            self.environment = environment
        if ip_address is not None:
            self.ip_address = ip_address
        if user_agent is not None:
            self.user_agent = user_agent
        if errors is not None:
            self.errors = errors

        if status is not None:
            self.status = status

    def close(
        self,
        status: "Optional[SessionStatus]" = None,
    ) -> "Any":
        if status is None and self.status == "ok":
            status = "exited"
        if status is not None:
            self.update(status=status)

    def get_json_attrs(
        self,
        with_user_info: "Optional[bool]" = True,
    ) -> "Any":
        attrs = {}
        if self.release is not None:
            attrs["release"] = self.release
        if self.environment is not None:
            attrs["environment"] = self.environment
        if with_user_info:
            if self.ip_address is not None:
                attrs["ip_address"] = self.ip_address
            if self.user_agent is not None:
                attrs["user_agent"] = self.user_agent
        return attrs

    def to_json(self) -> "Any":
        rv: "Dict[str, Any]" = {
            "sid": str(self.sid),
            "init": True,
            "started": format_timestamp(self.started),
            "timestamp": format_timestamp(self.timestamp),
            "status": self.status,
        }
        if self.errors:
            rv["errors"] = self.errors
        if self.did is not None:
            rv["did"] = self.did
        if self.duration is not None:
            rv["duration"] = self.duration
        attrs = self.get_json_attrs()
        if attrs:
            rv["attrs"] = attrs
        return rv
