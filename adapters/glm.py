"""adapters/glm.py — STUB. Role-level reshaping.

GLM-5.1 inherits ChatGLM's pre-tool-calling convention: tool results arrive as a
turn with role `observation`, not role `tool`. When you hand it an OpenAI-shaped
`{"role": "tool", ...}` message, the model often acts as if it received nothing
useful — it'll either re-issue the same tool call (loop) or hallucinate a result.

See bugs/glm-observation-role.md.

The *category* of fix here is ROLE-LEVEL: same content, different role label.

Things to try in this stub:

    1. In `shape_tool_result`, emit `{"role": "observation", ...}` instead of
       `{"role": "tool", ...}`.
    2. Some GLM deployments accept `tool` but require the tool name to live
       under a different key. Check what z.ai's docs say for your deployment.
    3. The function-call response from GLM sometimes appears as a code block
       in `content` rather than a structured `tool_calls` array — be ready to
       parse `function_call` blocks out of text.

Score before/after with:

    python run.py --task 1 --model glm --adapter passthrough --verbose
    python run.py --task 1 --model glm --adapter glm --verbose
"""
from __future__ import annotations

import json
from typing import Any

from adapters.base import Adapter


class GLMAdapter(Adapter):
    name = "glm"
    # GLM-5.1 documented defaults for tool-using mode (z.ai docs).
    sampling = {"temperature": 0.95, "top_p": 0.7}

    def before_request(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
        model: str,
        step: int,
    ) -> tuple[list[dict], list[dict]]:
        # TODO (attendees): some GLM deployments only honor a `tools` array if
        # each entry has its `function` block at the top level, not nested.
        # Try transforming
        #     {"type": "function", "function": {...}}
        # into
        #     {...}
        # and see whether Qwen-style nesting was breaking discovery.
        return messages, tools

    def shape_tool_result(self, *, tool_call: dict, result: Any, model: str) -> dict:
        # TODO (attendees): swap role to "observation".
        # The ChatGLM heritage means GLM-5.1 was post-trained on traces where
        # tool results arrived under `observation`. Try:
        #
        #     return {
        #         "role": "observation",
        #         "name": tool_call["name"],
        #         "content": json.dumps(result, default=str),
        #     }
        #
        # If z.ai's API rejects unknown roles at the surface, fall back to
        # role: "user" with a structured prefix:
        #
        #     return {
        #         "role": "user",
        #         "content": f"[observation:{tool_call['name']}] {json.dumps(result, default=str)}",
        #     }
        return super().shape_tool_result(tool_call=tool_call, result=result, model=model)

    def after_response(self, choice: Any, *, model: str, step: int) -> dict:
        # TODO (attendees): when GLM emits a function call as a fenced code
        # block in `content` instead of structured tool_calls, parse it. Sketch:
        #
        #     if not msg["tool_calls"] and "```function" in msg["content"]:
        #         block = re.search(r"```(?:function|tool|json)\n(.*?)```", msg["content"], re.S)
        #         if block:
        #             try:
        #                 fc = json.loads(block.group(1))
        #                 msg["tool_calls"].append({
        #                     "id": f"glm_{step}_0",
        #                     "name": fc.get("name"),
        #                     "arguments": fc.get("arguments") or fc.get("parameters") or {},
        #                 })
        #             except json.JSONDecodeError:
        #                 pass
        return super().after_response(choice, model=model, step=step)
