"""adapters/base.py — adapter interface.

An adapter has four jobs:

    1. before_request   — reshape the messages and tool definitions sent to the model
    2. after_response   — normalize the model's response back into a canonical assistant message
    3. shape_tool_result — frame a tool result the way the model was post-trained to consume
    4. sampling          — declare any per-model sampling defaults the model was RL'd at

The harness calls these four hooks. Everything else is shared.

Three categories of reshaping you'll see in the model-specific adapters:

    - format-level     (Qwen): function schema shape, parameter naming, tool_call envelope
    - role-level       (GLM):  what role tool results arrive under (`tool` vs `observation`)
    - behavioral       (Kimi): sampling, system prompt phrasing, end-of-turn signals
"""
from __future__ import annotations

import json
from typing import Any


class Adapter:
    name: str = "base"

    # Per-model sampling defaults. Override in subclasses.
    sampling: dict[str, float] = {"temperature": 0.7, "top_p": 1.0}

    def before_request(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
        model: str,
        step: int,
    ) -> tuple[list[dict], list[dict]]:
        """Reshape outgoing messages and tools. Default: identity."""
        return messages, tools

    def after_response(self, choice: Any, *, model: str, step: int) -> dict:
        """Normalize the model's response into a canonical assistant message:

            {"role": "assistant", "content": <str>, "tool_calls": [{"id":..., "name":..., "arguments": <dict>}, ...]}

        Default implementation handles the OpenAI-shaped response that LiteLLM
        usually produces. Adapters override when a model emits something
        different (Qwen's text-embedded tool calls, etc.).
        """
        msg = getattr(choice, "message", None) or choice.get("message", {})
        if hasattr(msg, "model_dump"):
            msg = msg.model_dump()
        elif hasattr(msg, "dict"):
            msg = msg.dict()

        content = msg.get("content") or ""
        raw_calls = msg.get("tool_calls") or []
        tool_calls = []
        for tc in raw_calls:
            if hasattr(tc, "model_dump"):
                tc = tc.model_dump()
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            tool_calls.append({
                "id": tc.get("id") or f"call_{step}_{len(tool_calls)}",
                "name": fn.get("name"),
                "arguments": args or {},
            })

        return {"role": "assistant", "content": content, "tool_calls": tool_calls}

    def shape_tool_result(self, *, tool_call: dict, result: Any, model: str) -> dict:
        """Default OpenAI-style tool message:

            {"role": "tool", "tool_call_id": <id>, "name": <fn>, "content": <json>}

        GLM overrides this — its post-training expects role=`observation`.
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id"),
            "name": tool_call.get("name"),
            "content": json.dumps(result, default=str),
        }
