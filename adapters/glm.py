"""adapters/glm.py — STUB. Role-level reshaping.

GLM-5.1 inherits ChatGLM's pre-tool-calling convention: tool results arrive as
a turn with role `observation`, not role `tool`. When you hand it an
OpenAI-shaped `{"role": "tool", ...}` message, the model often acts as if it
received nothing useful — it'll either re-issue the same tool call (loop) or
hallucinate a result.

See `bugs/glm-observation-role.md`.

The *category* of fix here is ROLE-LEVEL: same content, different role label.

Things to try in this stub:

    1. `custom_role_conversions = {"tool": "observation"}` — smolagents will
       rewrite every `role: tool` message to `role: observation` before the
       wire. Cleanest fix. Already commented in below.

    2. If z.ai rejects unknown roles at the surface, fall back to wrapping the
       result in a `user` turn with a structured prefix in `reshape_messages`:
       `f"[observation:{name}] {content}"`.

    3. Some GLM deployments emit function calls as fenced code blocks in
       `content` (````function`) instead of structured `tool_calls`. Parse those
       out in `shape_response`.

Score before/after with:

    python run.py --task 1 --model glm --adapter passthrough --verbose
    python run.py --task 1 --model glm --adapter glm --verbose
"""
from __future__ import annotations

from typing import Any

from adapters.base import Adapter


class GLMAdapter(Adapter):
    name = "glm"
    # GLM-5.1 documented defaults for tool-using mode (z.ai docs).
    sampling = {"temperature": 0.95, "top_p": 0.7}

    # Required minimum: Z.AI's endpoint on OpenRouter rejects
    # tool_choice="required" (smolagents' default) with a 404.
    completion_overrides = {"tool_choice": "auto"}

    # TODO (attendees): the ROLE-level fix — uncomment and try it.
    # custom_role_conversions = {"tool": "observation"}

    def reshape_messages(self, messages: list) -> list:
        # TODO (attendees): if custom_role_conversions doesn't get accepted by
        # z.ai, fall back to a structured user-turn prefix. Sketch:
        #
        #     out = []
        #     for m in messages:
        #         role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        #         if role == "tool":
        #             name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else "")
        #             content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")
        #             out.append({"role": "user", "content": f"[observation:{name}] {content}"})
        #         else:
        #             out.append(m)
        #     return out
        return messages

    def shape_response(self, response: Any) -> Any:
        # TODO (attendees): if GLM puts a function call in `content` as a fenced
        # code block, parse it back into `response.tool_calls`. Sketch:
        #
        #     import json, re
        #     if response.tool_calls or not response.content:
        #         return response
        #     m = re.search(r"```(?:function|tool|json)\n(.*?)```", response.content, re.S)
        #     if m:
        #         try:
        #             fc = json.loads(m.group(1))
        #             response.tool_calls = [{
        #                 "id": "glm_0",
        #                 "type": "function",
        #                 "function": {"name": fc.get("name"), "arguments": json.dumps(fc.get("arguments") or fc.get("parameters") or {})},
        #             }]
        #         except json.JSONDecodeError:
        #             pass
        return response
