"""harness/agent.py — the workshop's reference harness.

We're not running a hand-rolled agent loop. The point of tonight is to measure
each model against a *real, published* generic harness, so we use
[smolagents](https://github.com/huggingface/smolagents)'s `ToolCallingAgent` —
small enough to read in an afternoon, vendor-neutral, MCP-aware, and the kind
of loop attendees might actually reach for in their own work.

The only per-model knobs are in `adapters/<model>.py`. If a model misbehaves
inside this loop, that's the portability tax — the fix lives in an adapter,
not in this file.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from smolagents import ToolCallingAgent, OpenAIModel, LogLevel

from adapters.base import Adapter
from harness.tools import portable_tools


# Short names → OpenRouter slugs. Verified May 2026. Update when models rev.
MODEL_SLUGS: dict[str, str] = {
    "claude": "anthropic/claude-opus-4.7",
    "qwen":   "qwen/qwen3.6-max-preview",
    "glm":    "z-ai/glm-5.1",
    "kimi":   "moonshotai/kimi-k2.6",
}

# Pin each model to its lab-of-origin provider on OpenRouter. Without this,
# OpenRouter routes to whichever provider is cheapest — for Claude that's
# often Bedrock (different conversation shape requirements); for GLM/Kimi it's
# often a third-party at fp8/int4 (quantization-induced behavioral drift). We
# want to measure post-training, not provider quirks. Provider names match
# what `/api/v1/models/<slug>/endpoints` returns.
LAB_PROVIDERS: dict[str, str] = {
    "claude": "Anthropic",
    "qwen":   "Alibaba",
    "glm":    "Z.AI",
    "kimi":   "Moonshot AI",
}


class RouterModel(OpenAIModel):
    """OpenAIModel pointed at OpenRouter, pinned to a lab provider, with the
    adapter's sampling + completion overrides applied. The adapter can also
    intercept messages before they hit the wire.
    """

    def __init__(self, short_name: str, adapter: Adapter):
        slug = MODEL_SLUGS.get(short_name, short_name)
        provider = LAB_PROVIDERS.get(short_name)
        kwargs: dict[str, Any] = {
            "model_id": slug,
            "api_base": "https://openrouter.ai/api/v1",
            "api_key": os.environ.get("OPENROUTER_API_KEY"),
            "max_tokens": 2048,
            **adapter.sampling,
            **adapter.completion_overrides,
        }
        if provider:
            kwargs["extra_body"] = {"provider": {"order": [provider], "allow_fallbacks": False}}
        if adapter.custom_role_conversions:
            kwargs["custom_role_conversions"] = adapter.custom_role_conversions
        super().__init__(**kwargs)
        self.short_name = short_name
        self.adapter = adapter

    def generate(self, messages, stop_sequences=None, **kwargs):
        messages = self.adapter.reshape_messages(messages)
        response = super().generate(messages, stop_sequences=stop_sequences, **kwargs)
        return self.adapter.shape_response(response)


SYSTEM_PROMPT_OVERRIDE = """You are an agent solving a task using tools.

You have access to: filesystem (read/write/list inside a sandbox), web_search, and codegen_run (write+execute Python).

Plan briefly, then call the tools you need. When the task is complete, call the `final_answer` tool with a short description of what you did. Do not call other tools after `final_answer`."""


@dataclass
class Agent:
    """Thin facade over smolagents.ToolCallingAgent that the rest of the repo
    uses. Keeps the surface stable (model, adapter, verbose, max_steps, run)
    so run.py and bench.sh don't care that we swapped loops underneath.
    """

    model: str
    adapter: Adapter
    verbose: bool = False
    max_steps: int = 12
    transcript: list[dict] = field(default_factory=list)

    def run(self, task_spec: str, task_id: int) -> list[dict]:
        router = RouterModel(self.model, self.adapter)
        inner = ToolCallingAgent(
            tools=portable_tools(),
            model=router,
            max_steps=self.max_steps,
            verbosity_level=LogLevel.DEBUG if self.verbose else LogLevel.OFF,
            instructions=SYSTEM_PROMPT_OVERRIDE,
            return_full_result=False,
        )
        try:
            inner.run(task_spec)
        except Exception:
            # Re-raise after capturing whatever made it into memory so the
            # eval still sees partial progress. The caller logs the error.
            self.transcript = _memory_to_transcript(inner)
            raise
        self.transcript = _memory_to_transcript(inner)
        return self.transcript


def _memory_to_transcript(inner: ToolCallingAgent) -> list[dict]:
    """Translate smolagents memory → the canonical transcript shape that
    tasks/eval.py expects: a flat list of {role, content, tool_calls, name, ...}.
    """
    out: list[dict] = []
    for step in inner.memory.steps:
        # ActionStep carries the model's response and the tool calls + observations.
        model_output = getattr(step, "model_output", None)
        tool_calls = getattr(step, "tool_calls", None) or []
        observations = getattr(step, "observations", None)
        error = getattr(step, "error", None)

        if model_output is not None or tool_calls:
            assistant = {
                "role": "assistant",
                "content": model_output or "",
                "tool_calls": [
                    {
                        "id": getattr(tc, "id", None) or f"call_{i}",
                        "name": getattr(tc, "name", None),
                        "arguments": _normalize_args(getattr(tc, "arguments", None)),
                    }
                    for i, tc in enumerate(tool_calls)
                ],
            }
            out.append(assistant)

        if observations is not None:
            # smolagents collapses tool results into a single observations string
            # per step. The eval just checks for successful tool calls by name +
            # absence of "error" — so we emit one tool message per tool_call with
            # the shared observation content. Imperfect but eval-compatible.
            content = observations if isinstance(observations, str) else json.dumps(observations, default=str)
            for i, tc in enumerate(tool_calls):
                out.append({
                    "role": "tool",
                    "tool_call_id": getattr(tc, "id", None) or f"call_{i}",
                    "name": getattr(tc, "name", None),
                    "content": content,
                })

        if error is not None and not tool_calls:
            out.append({"role": "tool", "name": "error", "content": json.dumps({"error": str(error)})})

    return out


def _normalize_args(args: Any) -> dict:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"_raw": args}
    return {}
