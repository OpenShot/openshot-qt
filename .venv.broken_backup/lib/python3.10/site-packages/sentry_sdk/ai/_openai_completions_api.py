from collections.abc import Iterable

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentry_sdk._types import TextPart

    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
    )


def _is_system_instruction(message: "ChatCompletionMessageParam") -> bool:
    return isinstance(message, dict) and message.get("role") == "system"


def _get_system_instructions(
    messages: "Iterable[ChatCompletionMessageParam]",
) -> "list[ChatCompletionMessageParam]":
    if not isinstance(messages, Iterable):
        return []

    return [message for message in messages if _is_system_instruction(message)]


def _transform_system_instructions(
    system_instructions: "list[ChatCompletionSystemMessageParam]",
) -> "list[TextPart]":
    instruction_text_parts: "list[TextPart]" = []

    for instruction in system_instructions:
        if not isinstance(instruction, dict):
            continue

        content = instruction.get("content")

        if isinstance(content, str):
            instruction_text_parts.append({"type": "text", "content": content})

        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", None)
                    if text is not None:
                        instruction_text_parts.append({"type": "text", "content": text})

    return instruction_text_parts
