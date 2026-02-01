from typing import TYPE_CHECKING, Any

from sentry_sdk.feature_flags import add_feature_flag
from sentry_sdk.integrations import DidNotEnable, Integration

try:
    from openfeature import api
    from openfeature.hook import Hook

    if TYPE_CHECKING:
        from openfeature.hook import HookContext, HookHints
except ImportError:
    raise DidNotEnable("OpenFeature is not installed")


class OpenFeatureIntegration(Integration):
    identifier = "openfeature"

    @staticmethod
    def setup_once() -> None:
        # Register the hook within the global openfeature hooks list.
        api.add_hooks(hooks=[OpenFeatureHook()])


class OpenFeatureHook(Hook):
    def after(self, hook_context: "Any", details: "Any", hints: "Any") -> None:
        if isinstance(details.value, bool):
            add_feature_flag(details.flag_key, details.value)

    def error(
        self, hook_context: "HookContext", exception: Exception, hints: "HookHints"
    ) -> None:
        if isinstance(hook_context.default_value, bool):
            add_feature_flag(hook_context.flag_key, hook_context.default_value)
