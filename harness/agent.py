"""harness/agent.py — model-agnostic agent loop.

The whole point: this loop does the same thing for every model. It plans, calls
tools, feeds back results, repeats. The *only* per-model knob is the adapter.
If a model misbehaves under this loop, that's the portability tax — and the fix
is in `adapters/<model>.py`, not here.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel

from adapters.base import Adapter
from harness.tools import build_tool_registry

# LiteLLM is the wire layer — it speaks the OpenAI-shaped chat completions
# protocol to the proxy, which routes to the model's native API. The proxy
# normalizes the API surface; the *content shape* is exactly what we want
# to vary, which is what adapters do.
from litellm import completion


SYSTEM_PROMPT = """You are an agent solving a task using tools.

You have three tools available: filesystem (read/write/list), web_search, and codegen (write+execute Python).

Plan briefly, then call the tools you need. After each tool result, decide whether you're done or need another step. When the task is complete, respond with a final message describing what you did and stop calling tools."""


@dataclass
class Agent:
    model: str
    adapter: Adapter
    verbose: bool = False
    max_steps: int = 12
    transcript: list[dict] = field(default_factory=list)
    _console: Console = field(default_factory=Console, repr=False)

    def run(self, task_spec: str, task_id: int) -> list[dict]:
        tools = build_tool_registry()
        tool_specs = [t.spec for t in tools.values()]

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_spec},
        ]

        for step in range(self.max_steps):
            shaped_messages, shaped_tools = self.adapter.before_request(
                messages=messages, tools=tool_specs, model=self.model, step=step,
            )

            self._dump("REQUEST", {"step": step, "messages": shaped_messages, "tools": [t["function"]["name"] for t in shaped_tools]})

            response = completion(
                model=f"openai/{self.model}",
                messages=shaped_messages,
                tools=shaped_tools,
                tool_choice="auto",
                api_base=os.environ.get("PROXY_URL"),
                api_key=os.environ.get("PROXY_TOKEN"),
                temperature=self.adapter.sampling.get("temperature", 0.7),
                top_p=self.adapter.sampling.get("top_p", 1.0),
                max_tokens=2048,
                timeout=60,
            )

            choice = response.choices[0]
            assistant_msg = self.adapter.after_response(choice, model=self.model, step=step)

            self._dump("RESPONSE", assistant_msg)

            messages.append(assistant_msg)
            self.transcript.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls") or []
            finish_reason = getattr(choice, "finish_reason", None) or choice.get("finish_reason") if isinstance(choice, dict) else getattr(choice, "finish_reason", None)

            if not tool_calls:
                # No tool calls → model thinks it's done. May be premature
                # (Kimi behavior) or genuinely done. The eval decides.
                if self.verbose:
                    self._console.print(f"[dim]finish_reason: {finish_reason}[/dim]")
                break

            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("arguments") or {}
                if name not in tools:
                    result = {"error": f"unknown tool: {name}"}
                else:
                    try:
                        result = tools[name].run(**args)
                    except Exception as e:  # noqa: BLE001
                        result = {"error": f"{type(e).__name__}: {e}"}

                tool_msg = self.adapter.shape_tool_result(
                    tool_call=tc, result=result, model=self.model,
                )
                self._dump("TOOL", tool_msg)
                messages.append(tool_msg)
                self.transcript.append(tool_msg)

        return self.transcript

    def _dump(self, label: str, payload: Any) -> None:
        if not self.verbose:
            return
        try:
            text = json.dumps(payload, indent=2, default=str)
        except Exception:
            text = repr(payload)
        self._console.print(Panel(text, title=label, border_style="cyan"))
