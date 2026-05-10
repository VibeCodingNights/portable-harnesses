"""adapters/kimi.py — STUB. Behavioral-level reshaping.

Kimi K2.6 is the trickiest of the four. The bug isn't that the wire format is
wrong — it's that the *model thinks it's done* before the harness has finished
collecting outputs. Kimi was RL'd inside Moonshot's native agentic loop, where
end-of-turn signals fire at specific context shapes. Hand it a context shape
that doesn't match (different system prompt structure, missing scratchpad
markers, OpenAI-style tool_result blocks), and it issues a premature
`finish_reason: end_turn` after the first tool call.

See bugs/kimi-premature-termination.md.

The *category* of fix here is BEHAVIORAL: the wire works, the model just stops.

Things to try in this stub:

    1. Lock sampling to Moonshot's published defaults: temperature 0.6, top_p 1.0.
       Kimi K2.6 was RL'd at these settings — drift breaks calibration.
    2. Inject a system prompt suffix that looks like the agentic-loop scaffolding
       Kimi was trained inside: explicit "you have not finished yet — review what
       remains" cues after each tool result.
    3. Re-stamp the tool-result envelope so it doesn't look like a "final" turn
       to Kimi's RL'd termination predictor.

Score before/after with:

    python run.py --task 2 --model kimi --adapter passthrough --verbose
    python run.py --task 2 --model kimi --adapter kimi --verbose
"""
from __future__ import annotations

import json
from typing import Any

from adapters.base import Adapter


# Kimi K2.6 was RL'd at these sampling settings inside Moonshot's native loop.
# Drifting from them is a documented cause of early termination.
_KIMI_SAMPLING = {"temperature": 0.6, "top_p": 1.0}


_CONTINUATION_REMINDER = (
    "Important: review the original task. If any step remains unfinished, "
    "issue another tool call. Only stop when every required output has been written."
)


class KimiAdapter(Adapter):
    name = "kimi"
    sampling = _KIMI_SAMPLING

    def before_request(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
        model: str,
        step: int,
    ) -> tuple[list[dict], list[dict]]:
        # TODO (attendees): patch the system prompt with continuation cues that
        # match Kimi's RL-time scaffolding. Sketch:
        #
        #     if messages and messages[0].get("role") == "system":
        #         messages = [
        #             {**messages[0], "content": messages[0]["content"] + "\n\n" + _CONTINUATION_REMINDER},
        #             *messages[1:],
        #         ]

        # TODO (attendees): after every tool result, append a brief user-shaped
        # nudge ("Continue. What's the next step?"). This re-opens the turn in
        # a shape Kimi's terminator was trained against.

        return messages, tools

    def shape_tool_result(self, *, tool_call: dict, result: Any, model: str) -> dict:
        # TODO (attendees): wrap the result so it doesn't read like a closing turn.
        # Try a "step result" framing:
        #
        #     content = json.dumps({
        #         "step_result": result,
        #         "status": "intermediate",   # not "final"
        #     }, default=str)
        return super().shape_tool_result(tool_call=tool_call, result=result, model=model)

    def after_response(self, choice: Any, *, model: str, step: int) -> dict:
        # TODO (attendees): if Kimi emits an empty content + no tool_calls and
        # finish_reason="stop"/"end_turn" before the task is plausibly done,
        # consider re-prompting once with the continuation reminder before giving up.
        # The harness sees no tool_calls and exits — that's the bug. The fix is
        # either here (force a continuation) or in before_request (preempt with
        # stronger cues so it never fires end_turn early in the first place).
        return super().after_response(choice, model=model, step=step)
