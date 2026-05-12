"""harness/alignment.py — anchored fuzzy alignment of agent traces.

Per HYPERGRAPH C1.1. Inputs:
  - One trace (a list of Message dicts per docs/schemas/trace.schema.json)
  - An anchor spec (loaded from a tasks/<NN>-*.anchors.yaml file)

Output:
  - column_map: list[ColumnAssignment] — one entry per assistant tool_call,
    mapping step_idx to alignment column.
  - anchor_hits: list[AnchorHit] — which anchors fired, where, and how many times.

V1 algorithm (this file):
  1. Walk each trace. For each assistant message's tool_calls:
     a. Compute canonical signature (already done in C1.4; we trust the field).
     b. Check each anchor in declaration order (first-match wins per F4).
     c. If matched: emit `anchor:<id>` column; record anchor hit.
     d. If unmatched: emit `free:<n>` column with a per-trace sequence index.
  2. After walking, compute anchor satisfaction:
     a. required anchors must have count >= count.min and count <= count.max
     b. order_after constraints must hold (earlier anchor's first hit < later's)
  3. Emit alignment dict ready for the trace.alignment field.

V2 refinements (not in V1):
  - Cross-trace alignment of free regions via Needleman-Wunsch with
    signature-similarity scoring. V1 emits per-trace free columns, so two
    traces' free regions don't share columns — the lane view will show them
    side-by-side but won't claim equivalence.
  - Suggestive-tier matching (D3) between different tools in the same intent
    category. V1 only emits exact-tier matches.

The reason to ship V1 first: it produces correct anchor columns, which are
the load-bearing perceptual elements. Free regions get visualized as "model-
specific free space" — honest about what we know.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from harness.signature import canonical, matches_pattern, intent_category


# ---------- types ----------

@dataclass
class Anchor:
    id: str
    signature_pattern: str
    required: bool
    count_min: int = 1
    count_max: int | None = 1
    order_after: list[str] | None = None
    description: str | None = None


@dataclass
class AnchorSpec:
    task: int
    anchors: list[Anchor]


# ---------- loading ----------

def load_anchor_spec(path: str | Path) -> AnchorSpec:
    """Load an anchor file from disk and validate basic structure."""
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict) or "task" not in data or "anchors" not in data:
        raise ValueError(f"{path}: missing required keys (task, anchors)")

    anchors: list[Anchor] = []
    for raw in data["anchors"]:
        count = raw.get("count") or {}
        anchors.append(Anchor(
            id=raw["id"],
            signature_pattern=raw["signature_pattern"],
            required=bool(raw["required"]),
            count_min=int(count.get("min", 1)),
            count_max=count.get("max", 1),  # may be None for unbounded
            order_after=list(raw.get("order_after") or []),
            description=raw.get("description"),
        ))
    return AnchorSpec(task=int(data["task"]), anchors=anchors)


def load_anchor_spec_for_task(task: int, tasks_dir: str | Path = "tasks") -> AnchorSpec:
    """Convention: tasks/<NN>-<slug>.anchors.yaml."""
    tasks_dir = Path(tasks_dir)
    glob_pattern = f"{task:02d}-*.anchors.yaml"
    matches = list(tasks_dir.glob(glob_pattern))
    if not matches:
        raise FileNotFoundError(f"no anchor spec for task {task} in {tasks_dir}")
    if len(matches) > 1:
        raise ValueError(f"multiple anchor specs for task {task}: {matches}")
    return load_anchor_spec(matches[0])


# ---------- alignment ----------

def align_trace(transcript: list[dict], spec: AnchorSpec) -> dict:
    """Align one trace against the anchor spec. Returns the dict that goes
    into the run record's `alignment` field per the trace schema.

    V1 alignment: anchor columns are shared (cross-trace by id); free columns
    are per-trace (sequence-indexed, not cross-trace).
    """
    column_map: list[dict[str, Any]] = []
    anchor_count: dict[str, int] = {a.id: 0 for a in spec.anchors}
    anchor_first_step: dict[str, int] = {}
    free_idx = 0

    for msg in transcript:
        if msg.get("role") != "assistant":
            continue
        for tc in (msg.get("tool_calls") or []):
            step_idx = msg.get("step_idx")
            if step_idx is None:
                continue  # legacy data without step_idx — skip silently
            # Prefer pre-computed signature (C1.4); fall back to recomputing.
            sig = tc.get("signature") or canonical(
                tc.get("name", ""), tc.get("arguments") or {}
            )

            matched = _match_anchor(sig, spec.anchors)
            if matched is not None:
                column_map.append({
                    "step_idx": step_idx,
                    "column_id": f"anchor:{matched.id}",
                    "column_type": "anchor",
                    "tier": "exact",
                    "confidence": 1.0,
                })
                anchor_count[matched.id] += 1
                anchor_first_step.setdefault(matched.id, step_idx)
            else:
                column_map.append({
                    "step_idx": step_idx,
                    "column_id": f"free:{free_idx}",
                    "column_type": "free",
                    "tier": "exact",
                    "confidence": 1.0,
                })
                free_idx += 1

    # Anchor hits with satisfaction
    anchor_hits: list[dict[str, Any]] = []
    for a in spec.anchors:
        count = anchor_count[a.id]
        within_count = (
            count >= a.count_min
            and (a.count_max is None or count <= a.count_max)
        )
        # Ordering check: every anchor in order_after must have fired earlier
        order_ok = True
        if a.order_after:
            my_first = anchor_first_step.get(a.id)
            for predecessor_id in a.order_after:
                pred_first = anchor_first_step.get(predecessor_id)
                if my_first is None:
                    # If this anchor never fired, ordering is moot (handled by count).
                    continue
                if pred_first is None or pred_first >= my_first:
                    order_ok = False
                    break

        satisfied = within_count and order_ok and (
            count > 0 or not a.required
        )

        anchor_hits.append({
            "anchor_id": a.id,
            "satisfied": satisfied,
            "step_idx": anchor_first_step.get(a.id),
            "count": count,
        })

    return {
        "column_map": column_map,
        "anchor_hits": anchor_hits,
    }


def _match_anchor(signature: str, anchors: list[Anchor]) -> Anchor | None:
    """First-match-wins per F4. Anchor authoring discipline says: more-specific
    patterns precede less-specific in the file."""
    for a in anchors:
        if matches_pattern(signature, a.signature_pattern):
            return a
    return None


# ---------- convenience ----------

def align_record(record: dict, anchors_dir: str | Path = "tasks") -> dict:
    """Compute alignment for a run record, returning a copy with `alignment` set.
    Use this from bench.sh integration (C1.3) or one-shot tooling.
    """
    task = record.get("task")
    if not isinstance(task, int):
        raise ValueError("record.task is required and must be int")
    transcript = record.get("transcript") or []
    if not isinstance(transcript, list):
        raise ValueError("record.transcript is required and must be a list")
    spec = load_anchor_spec_for_task(task, anchors_dir)
    alignment = align_trace(transcript, spec)
    return {**record, "alignment": alignment}
