"""adapters/passthrough.py — the naive baseline.

No reshaping. No per-model knowledge. Generic sampling. This is what every
agent framework does by default. Use this to *measure* what the portability
tax costs you.
"""
from __future__ import annotations

from adapters.base import Adapter


class PassthroughAdapter(Adapter):
    name = "passthrough"
    sampling = {"temperature": 0.7, "top_p": 1.0}
