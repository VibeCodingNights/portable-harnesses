"""adapters/qwen.py — STUB. Format-level reshaping.

Qwen 3.6 was post-trained against a specific tool-calling format. The vLLM/llama.cpp
chat template emits tool definitions and tool results inside `<tool_call>...</tool_call>`
and `<tool_response>...</tool_response>` tags — and the Jinja2 templates that ship
with the model frequently mis-render edge cases (multi-arg calls, nested JSON, etc.).
See bugs/qwen-jinja2-tool-templates.md.

The *category* of fix here is FORMAT-LEVEL: same content, different envelope.

Things to try in this stub:

    1. Flatten the OpenAI tool spec into the JSON shape that Qwen's chat template
       was trained against (see docs/model-expectations.md → "Qwen 3.6").
    2. Wrap tool-result `content` in a `<tool_response>...</tool_response>` envelope
       so Qwen recognizes it as a tool result rather than free-form user text.
    3. If the response comes back with an empty `tool_calls` array but a
       text-embedded `<tool_call>{"name":..., "arguments":...}</tool_call>`,
       parse it back out in `after_response`.

Score before/after with:

    python run.py --task 1 --model qwen --adapter passthrough --verbose
    python run.py --task 1 --model qwen --adapter qwen --verbose
"""
from __future__ import annotations

import json
import re
from typing import Any

from adapters.base import Adapter


# Qwen's documented sampling defaults for tool-using mode.
# See: dashscope.aliyuncs.com docs → "Qwen3 function calling".
_QWEN_SAMPLING = {"temperature": 0.7, "top_p": 0.8}


class QwenAdapter(Adapter):
    name = "qwen"
    sampling = _QWEN_SAMPLING

    def before_request(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
        model: str,
        step: int,
    ) -> tuple[list[dict], list[dict]]:
        # TODO (attendees): reshape `tools` if the proxy's translation of the OpenAI
        # function spec into Qwen's native tool format is dropping properties.
        # The known landmine: `parameters.type: "object"` is sometimes lost when
        # there are no required fields, which makes Qwen emit tool calls with
        # missing arguments. Force-fill `required: []` and check the result.

        # TODO (attendees): if a previous tool result message is in `messages`,
        # consider whether Qwen wants it as `role: "tool"` (passthrough), or
        # wrapped as a user turn containing `<tool_response>...</tool_response>`.

        return messages, tools

    def after_response(self, choice: Any, *, model: str, step: int) -> dict:
        # Start with the canonical normalization.
        msg = super().after_response(choice, model=model, step=step)

        # TODO (attendees): if `tool_calls` is empty but `content` contains
        # `<tool_call>...</tool_call>` blocks (a known vLLM-template emission
        # mode for Qwen), parse them out and populate `tool_calls`. Sketch:
        #
        #     if not msg["tool_calls"]:
        #         for m in re.finditer(r"<tool_call>(.*?)</tool_call>", msg["content"], re.S):
        #             try:
        #                 payload = json.loads(m.group(1))
        #                 msg["tool_calls"].append({
        #                     "id": f"qwen_{step}_{len(msg['tool_calls'])}",
        #                     "name": payload["name"],
        #                     "arguments": payload.get("arguments", {}),
        #                 })
        #             except json.JSONDecodeError:
        #                 pass

        return msg

    def shape_tool_result(self, *, tool_call: dict, result: Any, model: str) -> dict:
        # TODO (attendees): wrap the result in the envelope Qwen's RL prefers.
        # Qwen's chat template was trained to see tool results as:
        #
        #     <tool_response>
        #     {"name": "...", "content": <string>}
        #     </tool_response>
        #
        # and the model often ignores OpenAI-shape tool messages without it.
        return super().shape_tool_result(tool_call=tool_call, result=result, model=model)
