"""adapters/passthrough.py — the naive baseline.

Sends context as-is. No reshaping. No per-model knowledge. This is what every
agent framework does by default. Use this when you want to *measure* how much
the portability tax costs you.
"""
from __future__ import annotations

from adapters.base import Adapter


class PassthroughAdapter(Adapter):
    name = "passthrough"
    # Generic defaults — same for every model, ignoring what the model was RL'd at.
    sampling = {"temperature": 0.7, "top_p": 1.0}
