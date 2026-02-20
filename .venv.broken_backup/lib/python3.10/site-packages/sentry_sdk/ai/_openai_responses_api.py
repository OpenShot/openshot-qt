from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Union

    from openai.types.responses import ResponseInputParam, ResponseInputItemParam


def _is_system_instruction(message: "ResponseInputItemParam") -> bool:
    if not isinstance(message, dict) or not message.get("role") == "system":
        return False

    return "type" not in message or message["type"] == "message"


def _get_system_instructions(
    messages: "Union[str, ResponseInputParam]",
) -> "list[ResponseInputItemParam]":
    if not isinstance(messages, list):
        return []

    return [message for message in messages if _is_system_instruction(message)]
