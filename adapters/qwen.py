"""adapters/qwen.py — STUB. Format-level reshaping.

Qwen 3.6 was post-trained against a specific tool-calling format. The vLLM/llama.cpp
chat template emits tool definitions and tool results inside `<tool_call>...</tool_call>`
and `<tool_response>...</tool_response>` tags — and the Jinja2 templates that ship
with the model frequently mis-render edge cases (multi-arg calls, nested JSON,
arguments containing newlines). See `bugs/qwen-jinja2-tool-templates.md`.

The *category* of fix here is FORMAT-LEVEL: same content, different envelope.

Things to try in this stub:

    1. `shape_response`: if the response comes back with an empty `tool_calls`
       array but `content` contains `<tool_call>{"name":..., "arguments":...}</tool_call>`,
       parse it back out and populate `response.tool_calls`.

    2. `reshape_messages`: wrap tool-result `content` in a `<tool_response>...</tool_response>`
       envelope so Qwen recognizes it as a tool result rather than free-form
       user text — particularly when the Alibaba endpoint translates OpenAI
       `role: tool` into a plain user turn.

    3. `sampling`: Qwen's documented defaults for tool-using mode are
       temperature 0.7, top_p 0.8 (dashscope.aliyuncs.com docs → Qwen3 function
       calling). Already set below.

Score before/after with:

    python run.py --task 1 --model qwen --adapter passthrough --verbose
    python run.py --task 1 --model qwen --adapter qwen --verbose
"""
from __future__ import annotations

import json
import re
from typing import Any

from adapters.base import Adapter


_QWEN_SAMPLING = {"temperature": 0.7, "top_p": 0.8}


class QwenAdapter(Adapter):
    name = "qwen"
    sampling = _QWEN_SAMPLING

    # Required minimum: Alibaba's Qwen endpoint on OpenRouter rejects
    # tool_choice="required" (smolagents' default) with a 404. Disable it.
    # This gets you a running baseline; the format-level taxes below are
    # what actually move the score.
    completion_overrides = {"tool_choice": "auto"}

    def shape_response(self, response: Any) -> Any:
        # TODO (attendees): when Qwen emits `<tool_call>...</tool_call>` blocks
        # inside `content` (a known vLLM-template emission mode) instead of
        # populating `tool_calls`, parse them out. Sketch:
        #
        #     if response.tool_calls or not response.content:
        #         return response
        #     parsed = []
        #     for i, m in enumerate(re.finditer(r"<tool_call>(.*?)</tool_call>", response.content, re.S)):
        #         try:
        #             payload = json.loads(m.group(1))
        #             parsed.append({
        #                 "id": f"qwen_{i}",
        #                 "type": "function",
        #                 "function": {"name": payload["name"], "arguments": json.dumps(payload.get("arguments") or {})},
        #             })
        #         except json.JSONDecodeError:
        #             continue
        #     if parsed:
        #         response.tool_calls = parsed
        return response

    def reshape_messages(self, messages: list) -> list:
        # TODO (attendees): if a tool result message exists, wrap its content
        # in <tool_response>...</tool_response> tags before sending. Qwen's
        # chat template was trained to see tool results inside that envelope.
        # The shape depends on how smolagents presents these messages to you
        # — print them with --verbose to see what you're working with.
        return messages
