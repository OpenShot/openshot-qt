from sentry_sdk.integrations import DidNotEnable

try:
    from opentelemetry.context import create_key
except ImportError:
    raise DidNotEnable("opentelemetry not installed")

SENTRY_TRACE_KEY = create_key("sentry-trace")
SENTRY_BAGGAGE_KEY = create_key("sentry-baggage")
