"""adapters/claude.py — reference implementation.

Claude on OpenRouter (pinned to Anthropic-direct) generally works under the
smolagents loop without further shimming — OpenRouter's API surface translates
OpenAI shape ↔ Anthropic shape correctly for the common path, and smolagents
handles tool_call ↔ tool_result pairing on its own.

The Claude-specific concern that still matters is *sampling*. Anthropic's own
guidance for agentic tool-use says: keep temperature low. Higher temperatures
nudge Claude toward over-narrating between calls and occasionally toward
emitting prose instead of a tool_call when one is required.

Read this file as the *pattern*. Then write the equivalent for qwen / glm / kimi.
"""
from __future__ import annotations

from adapters.base import Adapter


class ClaudeAdapter(Adapter):
    name = "claude"
    # Anthropic's published guidance: low temperature for tool-heavy agentic loops.
    sampling = {"temperature": 0.2, "top_p": 1.0}
