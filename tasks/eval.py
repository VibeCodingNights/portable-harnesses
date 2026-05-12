"""tasks/eval.py — score a transcript against the expected outcome.

Returns a dict shaped:

    {
      "completed": bool,
      "tool_calls": int,         # total successful tool calls
      "errors": int,             # tool errors + agent errors
      "loops": int,              # repeated identical tool calls (heuristic)
      "early_termination": bool, # finished without writing required outputs
      "notes": str,              # one-line human-readable
    }

The eval is deliberately forgiving on Task 2 (content-quality grading is out
of scope tonight) and strict on Tasks 1 and 3 (structural correctness).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_DIR = ROOT / "tasks" / "expected"

# Local import — keep loop detection honest by using the full canonical signature
# rather than a truncated heuristic. The eval runs in the same process as run.py
# so harness/ is already importable.
sys.path.insert(0, str(ROOT))
from harness.signature import canonical  # noqa: E402


def score(*, task_id: int, transcript: list[dict], sandbox: Path) -> dict:
    fns = {1: _score_task1, 2: _score_task2, 3: _score_task3}
    fn = fns.get(task_id)
    if not fn:
        return _result(False, transcript, notes=f"unknown task: {task_id}")
    return fn(transcript=transcript, sandbox=sandbox)


# ---------- task 1 ----------

def _score_task1(*, transcript: list[dict], sandbox: Path) -> dict:
    out = sandbox / "output" / "vendors.json"
    if not out.exists():
        return _result(False, transcript, notes="output/vendors.json missing", early=True)
    try:
        actual = json.loads(out.read_text())
    except json.JSONDecodeError as e:
        return _result(False, transcript, notes=f"output is not valid JSON: {e}")
    expected = json.loads((EXPECTED_DIR / "01-expected.json").read_text())
    if actual != expected:
        diff = _shallow_diff(expected, actual)
        return _result(False, transcript, notes=f"output diverges from expected: {diff}")
    return _result(True, transcript, notes="vendors.json matches expected")


# ---------- task 2 ----------

def _score_task2(*, transcript: list[dict], sandbox: Path) -> dict:
    out = sandbox / "output" / "qwen-tool-calling-summary.md"
    if not out.exists():
        return _result(False, transcript, notes="qwen-tool-calling-summary.md missing", early=True)
    text = out.read_text()
    if len(text) < 500:
        return _result(False, transcript, notes=f"summary too short ({len(text)} chars)")
    if not re.search(r"^#\s+\S", text, re.M):
        return _result(False, transcript, notes="missing markdown # heading")
    links = re.findall(r"\[[^\]]+\]\([^)]+\)", text)
    if len(links) < 2:
        return _result(False, transcript, notes=f"only {len(links)} markdown links (need ≥2)")
    if not _has_successful_tool(transcript, "web_search"):
        return _result(False, transcript, notes="no successful web_search call in transcript")
    return _result(True, transcript, notes=f"summary {len(text)} chars, {len(links)} links")


# ---------- task 3 ----------

def _score_task3(*, transcript: list[dict], sandbox: Path) -> dict:
    csv = sandbox / "output" / "models.csv"
    count = sandbox / "output" / "count.txt"
    if not csv.exists():
        return _result(False, transcript, notes="output/models.csv missing", early=True)
    if not count.exists():
        return _result(False, transcript, notes="output/count.txt missing — codegen step skipped?", early=True)
    csv_lines = [ln for ln in csv.read_text().splitlines() if ln.strip()]
    if len(csv_lines) != 5:
        return _result(False, transcript, notes=f"models.csv has {len(csv_lines)} lines, expected 5")
    if count.read_text().strip() != "4":
        return _result(False, transcript, notes=f"count.txt is {count.read_text().strip()!r}, expected '4'")
    for fn in ("web_search", "fs_write", "codegen_run", "fs_read"):
        if not _has_successful_tool(transcript, fn):
            return _result(False, transcript, notes=f"transcript missing successful {fn} call")
    final = _final_assistant_text(transcript)
    if "4" not in final:
        return _result(False, transcript, notes="final message doesn't mention the count 4")
    return _result(True, transcript, notes="full pipeline completed")


# ---------- helpers ----------

def _result(completed: bool, transcript: list[dict], *, notes: str, early: bool = False) -> dict:
    return {
        "completed": completed,
        "tool_calls": _count_tool_calls(transcript),
        "errors": _count_errors(transcript),
        "loops": _count_loops(transcript),
        "early_termination": early or _looks_early(transcript),
        "notes": notes,
    }


def _count_tool_calls(transcript: list[dict]) -> int:
    n = 0
    for m in transcript:
        if m.get("role") == "assistant":
            n += len(m.get("tool_calls") or [])
    return n


def _count_errors(transcript: list[dict]) -> int:
    n = 0
    for m in transcript:
        if m.get("role") == "tool":
            content = m.get("content") or ""
            if isinstance(content, str) and ('"error"' in content or "error:" in content.lower()):
                n += 1
    return n


def _count_loops(transcript: list[dict]) -> int:
    """Count tool calls with identical canonical signatures.

    Uses the full canonical form from harness/signature.py — no truncation.
    Two calls with identical canonical signatures ARE the same call; 3+ such
    calls in a transcript indicate a loop. The signature already collapses
    cosmetic variation (path normalization, key order, whitespace) and
    preserves semantic variation (different content → different sha hashes
    for codegen_run, etc.), so this is a sharper definition than the prior
    [:60] heuristic.
    """
    sigs: list[str] = []
    for m in transcript:
        if m.get("role") == "assistant":
            for tc in (m.get("tool_calls") or []):
                # Prefer pre-computed signature (post C1.4); fall back to recompute.
                sig = tc.get("signature") or canonical(tc.get("name", ""), tc.get("arguments") or {})
                sigs.append(sig)
    if not sigs:
        return 0
    repeats = 0
    counts = Counter(sigs)
    for _, c in counts.items():
        if c >= 3:  # 3+ identical = a loop
            repeats += c - 1
    return repeats


def _looks_early(transcript: list[dict]) -> bool:
    """Final assistant message has no tool calls and barely any content."""
    if not transcript:
        return True
    last_assistant = None
    for m in transcript:
        if m.get("role") == "assistant":
            last_assistant = m
    if not last_assistant:
        return True
    if last_assistant.get("tool_calls"):
        return False
    return len((last_assistant.get("content") or "").strip()) < 30


def _has_successful_tool(transcript: list[dict], name: str) -> bool:
    # Find a tool message with this name whose content is not an error.
    for i, m in enumerate(transcript):
        if m.get("role") == "tool" and m.get("name") == name:
            c = m.get("content") or ""
            if isinstance(c, str) and '"error"' not in c:
                return True
    return False


def _final_assistant_text(transcript: list[dict]) -> str:
    for m in reversed(transcript):
        if m.get("role") == "assistant":
            return m.get("content") or ""
    return ""


def _shallow_diff(expected, actual) -> str:
    if type(expected) is not type(actual):
        return f"type mismatch: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        if missing or extra:
            return f"keys: missing={sorted(missing)} extra={sorted(extra)}"
        for k in expected:
            if expected[k] != actual[k]:
                return f"key {k!r}: expected {expected[k]!r}, got {actual[k]!r}"
    return "values differ"
