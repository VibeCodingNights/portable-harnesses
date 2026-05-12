"""adapters/kimi.py — STUB. Behavioral-level reshaping.

Kimi K2.6 is the trickiest of the four. Two distinct taxes show up in the
smolagents-based harness:

    A. **tool_choice='required' is incompatible with thinking mode.** smolagents
       defaults to `tool_choice="required"` to force a tool call every turn.
       Moonshot rejects this when thinking is enabled — and Kimi K2.6 has
       thinking enabled by default. Outright 400 on the first request.
       Fix: `completion_overrides = {"tool_choice": "auto"}`.

    B. **Premature termination at the wrong context shape.** Kimi was RL'd
       inside Moonshot's native agentic loop, where end-of-turn signals fire
       at specific context shapes. Hand it a context shape that doesn't match
       (different system prompt structure, missing scratchpad markers, no
       continuation cue after a tool result), and it issues an early
       `finish_reason: stop` after the first tool call.
       See `bugs/kimi-premature-termination.md`.

The *category* of fix here is BEHAVIORAL: the wire works, the model just stops.

Things to try in this stub:

    1. Uncomment `completion_overrides = {"tool_choice": "auto"}` — the
       minimal viable fix for the 400.

    2. `sampling`: Moonshot's published defaults are temperature 0.6, top_p 1.0.
       Kimi was RL'd at these — drift breaks calibration. Already set below.

    3. `reshape_messages`: inject a continuation reminder into the system
       prompt, or append a brief user-shaped nudge after each tool result.
       This re-opens the turn in a shape Kimi's terminator was trained against.

Score before/after with:

    python run.py --task 1 --model kimi --adapter passthrough --verbose
    python run.py --task 1 --model kimi --adapter kimi --verbose
"""
from __future__ import annotations

from typing import Any

from adapters.base import Adapter


_KIMI_SAMPLING = {"temperature": 0.6, "top_p": 1.0}

_CONTINUATION_REMINDER = (
    "Important: review the original task. If any step remains unfinished, "
    "issue another tool call. Only call `final_answer` when every required "
    "output has been written."
)


class KimiAdapter(Adapter):
    name = "kimi"
    sampling = _KIMI_SAMPLING

    # Required minimum: smolagents sets tool_choice="required" by default,
    # which Moonshot rejects in combination with Kimi's thinking mode.
    # Override to "auto". Without this, the agent 400s on the first request.
    completion_overrides = {"tool_choice": "auto"}

    def reshape_messages(self, messages: list) -> list:
        # TODO (attendees): patch the system prompt with continuation cues
        # that match Kimi's RL-time scaffolding. Sketch (defensive to dict
        # vs ChatMessage):
        #
        #     if not messages:
        #         return messages
        #     m0 = messages[0]
        #     role = getattr(m0, "role", None) or (m0.get("role") if isinstance(m0, dict) else None)
        #     if role == "system":
        #         existing = getattr(m0, "content", None) or (m0.get("content") if isinstance(m0, dict) else "")
        #         patched_content = existing + "\n\n" + _CONTINUATION_REMINDER
        #         if isinstance(m0, dict):
        #             messages = [{**m0, "content": patched_content}, *messages[1:]]
        #         else:
        #             m0.content = patched_content
        return messages

    def shape_response(self, response: Any) -> Any:
        # TODO (attendees): if Kimi emits empty content + no tool_calls before
        # the task is plausibly done, that's premature termination. You can
        # detect it here and surface a clearer signal, or short-circuit by
        # injecting a synthetic tool_call (less clean).
        return response
