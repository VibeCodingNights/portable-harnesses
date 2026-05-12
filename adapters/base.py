"""adapters/base.py — adapter interface.

An adapter is a small object that tells the harness how to talk to a model
that was post-trained against a specific harness shape. Every adapter overrides
one or more of these four surfaces:

    1. `sampling`             — kwargs forwarded to the OpenAI client (the wire layer).
                                Temperature, top_p, max_tokens — whatever the lab RL'd at.

    2. `completion_overrides` — kwargs forwarded to the same client that override
                                smolagents' defaults. Most common case: smolagents
                                sets `tool_choice="required"` by default; some models
                                (Kimi K2.6) reject that combined with thinking mode.

    3. `custom_role_conversions` — `{from: to}` mapping applied by smolagents to
                                   every message role before the wire. Use this for
                                   role-level taxes (GLM expects `observation`, not
                                   `tool`).

    4. `reshape_messages(messages)` and `shape_response(response)` — Python hooks
                                   for format/behavioral taxes that can't be expressed
                                   as static kwargs. Use these for Qwen (text-embedded
                                   tool_call envelopes) and Kimi (continuation cues,
                                   reasoning preservation).

Three categories of reshaping you'll see in model-specific adapters:

    - format-level     (Qwen): function schema shape, parameter naming, tool_call envelope
    - role-level       (GLM):  what role tool results arrive under (`tool` vs `observation`)
    - behavioral       (Kimi): sampling, tool_choice, system prompt phrasing, end-of-turn signals
"""
from __future__ import annotations

from typing import Any


class Adapter:
    name: str = "base"

    sampling: dict[str, Any] = {"temperature": 0.7, "top_p": 1.0}
    completion_overrides: dict[str, Any] = {}
    custom_role_conversions: dict[str, str] = {}

    def reshape_messages(self, messages: list) -> list:
        """Reshape the message list before the wire. Default: identity.

        Items may be smolagents ChatMessage objects or plain dicts depending on
        where in the pipeline you intercept — code defensively. Common moves:

            - Inject continuation cues after tool results (Kimi)
            - Wrap tool_result content in a model-specific envelope (Qwen)
        """
        return messages

    def shape_response(self, response: Any) -> Any:
        """Post-process the ChatMessage returned by the model. Default: identity.

        Common moves:

            - Parse text-embedded `<tool_call>...</tool_call>` blocks back into
              `response.tool_calls` (Qwen, when the chat template forgot to
              populate the structured field)
            - Preserve `reasoning_content` so the model sees its own trace on
              the next turn (Kimi)
        """
        return response
