"""adapters/claude.py — reference implementation.

Claude is the baseline because the harness already speaks its native protocol
when fronted by LiteLLM. The interesting Claude-specific concern is *strictness*:

    Every assistant message with `tool_calls` must be followed, in the next
    turn, by exactly as many `tool_result` blocks as there were `tool_calls`,
    in the same order, with matching ids.

If you skip a tool result (e.g., one tool errored and you swallowed the message),
Claude will refuse the next turn. The default base.py shape_tool_result already
emits a tool message per call, so we just enforce ordering and content discipline
here as a worked example.

Read this file as the *pattern*. Then write the equivalent for qwen / glm / kimi.
"""
from __future__ import annotations

import json
from typing import Any

from adapters.base import Adapter


class ClaudeAdapter(Adapter):
    name = "claude"

    # Claude's published guidance: low temperature for tool-heavy agentic loops.
    sampling = {"temperature": 0.2, "top_p": 1.0}

    def before_request(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
        model: str,
        step: int,
    ) -> tuple[list[dict], list[dict]]:
        # Pair-check: every assistant tool_call has a matching tool result before it.
        # If something upstream dropped a tool result, inject a stub error so Claude
        # doesn't 400 on us. This is the kind of defensive shaping the docs warn about.
        repaired: list[dict] = []
        for i, m in enumerate(messages):
            repaired.append(m)
            if m.get("role") == "assistant" and m.get("tool_calls"):
                expected_ids = [tc["id"] for tc in m["tool_calls"]]
                # Look ahead for matching tool results before the next assistant.
                seen: set[str] = set()
                j = i + 1
                while j < len(messages) and messages[j].get("role") != "assistant":
                    if messages[j].get("role") == "tool":
                        seen.add(messages[j].get("tool_call_id"))
                    j += 1
                missing = [tc for tc in m["tool_calls"] if tc["id"] not in seen]
                for tc in missing:
                    repaired.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": json.dumps({"error": "tool result missing — repaired by claude adapter"}),
                    })
        return repaired, tools

    def shape_tool_result(self, *, tool_call: dict, result: Any, model: str) -> dict:
        # Claude expects the content to be a string; if our tool returned a dict,
        # stringify deterministically so prompt caching has a stable shape.
        if not isinstance(result, str):
            content = json.dumps(result, sort_keys=True, default=str)
        else:
            content = result
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_call["name"],
            "content": content,
        }
