"""Adapter registry."""
from __future__ import annotations

from adapters.base import Adapter
from adapters.passthrough import PassthroughAdapter
from adapters.claude import ClaudeAdapter
from adapters.qwen import QwenAdapter
from adapters.glm import GLMAdapter
from adapters.kimi import KimiAdapter

_REGISTRY: dict[str, type[Adapter]] = {
    "passthrough": PassthroughAdapter,
    "claude": ClaudeAdapter,
    "qwen": QwenAdapter,
    "glm": GLMAdapter,
    "kimi": KimiAdapter,
}


def load_adapter(name: str) -> Adapter:
    if name not in _REGISTRY:
        raise ValueError(f"unknown adapter: {name}. options: {list(_REGISTRY)}")
    return _REGISTRY[name]()
