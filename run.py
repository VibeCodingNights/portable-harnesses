#!/usr/bin/env python3
"""run.py — entry point for one task × one model × one adapter.

Usage:
    python run.py --task 1 --model claude
    python run.py --task 2 --model qwen --adapter qwen --verbose
    python run.py --task 3 --model kimi --adapter passthrough
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from harness.agent import Agent, SYSTEM_PROMPT_OVERRIDE
from harness.signature import canonical
from harness.alignment import align_trace, load_anchor_spec_for_task
from adapters import load_adapter
from tasks.eval import score


MODELS = ("claude", "qwen", "glm", "kimi")
ADAPTERS = ("passthrough", "claude", "qwen", "glm", "kimi")


def main() -> int:
    load_dotenv(ROOT / ".env")

    p = argparse.ArgumentParser()
    p.add_argument("--task", type=int, required=True, choices=(1, 2, 3))
    p.add_argument("--model", required=True, choices=MODELS)
    p.add_argument("--adapter", default="passthrough", choices=ADAPTERS)
    p.add_argument("--verbose", action="store_true",
                   help="show every message sent and received on the wire")
    p.add_argument("--max-steps", type=int, default=12)
    p.add_argument("--out", default=None,
                   help="path to write the run record (default: results/<task>-<model>-<adapter>.json)")
    p.add_argument("--force", action="store_true",
                   help="re-run even if a record with the same run_id already exists (D6)")
    args = p.parse_args()

    task_path = ROOT / "tasks" / f"0{args.task}-{_task_slug(args.task)}.md"
    if not task_path.exists():
        print(f"[err] task spec not found: {task_path}", file=sys.stderr)
        return 2

    task_spec = task_path.read_text()
    adapter = load_adapter(args.adapter)

    out_path = Path(args.out) if args.out else (
        ROOT / "results" / f"task{args.task}-{args.model}-{args.adapter}.json"
    )

    # Per D6: content-addressed run_id. Cache-hit by default unless --force.
    # F8 caveat: determinism is deferred (sampling temperature > 0), so the
    # cache stores a *representative* run for this config, not a guaranteed-
    # identical replay. Same config → same run_id → existing trace returned.
    versions = _collect_versions(task_spec, adapter)
    run_id = _compute_run_id(args.task, args.model, args.adapter, versions)

    if not args.force and out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
            if existing.get("run_id") == run_id:
                print(f"[cache] {out_path.relative_to(ROOT)} matches run_id {run_id[:12]}; use --force to re-run.")
                _print_summary(existing, out_path)
                return 0 if existing.get("completed") else 1
        except (json.JSONDecodeError, OSError):
            pass  # Malformed cache; fall through and re-run.

    # Wipe the previous run's output so the eval scores THIS run, not a stale
    # vendors.json left over from the last model's success.
    sandbox_root = ROOT / os.environ.get("SANDBOX_DIR", "sandbox")
    output_dir = sandbox_root / "output"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    agent = Agent(
        model=args.model,
        adapter=adapter,
        verbose=args.verbose,
        max_steps=args.max_steps,
    )

    started = time.time()
    error = None
    error_detail = None
    error_traceback = None
    try:
        transcript = agent.run(task_spec=task_spec, task_id=args.task)
    except Exception as e:  # noqa: BLE001 — top-level catch for the harness
        transcript = agent.transcript
        error = f"{type(e).__name__}: {e}"
        error_traceback = traceback.format_exc()
        error_detail = _extract_error_detail(e)
        if args.verbose:
            sys.stderr.write(error_traceback)
    elapsed = time.time() - started

    eval_result = score(task_id=args.task, transcript=transcript, sandbox=ROOT / os.environ.get("SANDBOX_DIR", "sandbox"))

    enriched_transcript = _enrich_transcript(transcript)
    alignment = _compute_alignment(args.task, enriched_transcript)

    record = {
        "run_id": run_id,
        "task": args.task,
        "model": args.model,
        "adapter": args.adapter,
        "seed": None,  # F8: deterministic seeding deferred; temperature > 0
        "tool_versions": versions["tool_versions"],
        "prompt_versions": versions["prompt_versions"],
        "elapsed_s": round(elapsed, 2),
        "completed": eval_result["completed"],
        "tool_calls": eval_result["tool_calls"],
        "errors": eval_result["errors"],
        "loops": eval_result["loops"],
        "early_termination": eval_result["early_termination"],
        "notes": eval_result["notes"],
        "agent_error": error,
        "agent_error_detail": error_detail,
        "agent_error_traceback": error_traceback,
        "transcript": enriched_transcript,
        "alignment": alignment,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))

    _print_summary(record, out_path)
    return 0 if eval_result["completed"] else 1


def _task_slug(task: int) -> str:
    return {
        1: "file-transform",
        2: "research-and-write",
        3: "full-pipeline",
    }[task]


def _compute_alignment(task: int, transcript: list[dict]) -> dict | None:
    """Run the anchored aligner against the trace's anchor spec. Returns the
    {column_map, anchor_hits} dict for embedding in the record. Returns None
    on missing anchor spec — the JSON stays honest about absence."""
    try:
        spec = load_anchor_spec_for_task(task)
        return align_trace(transcript, spec)
    except FileNotFoundError:
        return None
    except Exception as e:  # noqa: BLE001 — defensive; the run should not fail because alignment did
        sys.stderr.write(f"[align] warning: {type(e).__name__}: {e}\n")
        return None


def _enrich_transcript(transcript: list[dict]) -> list[dict]:
    """Per docs/schemas/trace.schema.json: each Message has step_idx; each
    ToolCall has signature. We don't summarize anymore — the viewer needs the
    full text to render step cards and align tool calls across lanes (F1).
    """
    enriched = []
    for i, msg in enumerate(transcript):
        m = dict(msg)
        m["step_idx"] = i
        tool_calls = m.get("tool_calls")
        if tool_calls:
            m["tool_calls"] = [
                {**tc, "signature": canonical(tc.get("name", ""), tc.get("arguments") or {})}
                for tc in tool_calls
            ]
        enriched.append(m)
    return enriched


def _collect_versions(task_spec: str, adapter) -> dict:
    """Hash inputs that should invalidate the cache when they change.

    Tool surface is hashed from harness/tools.py source so a tool change
    forces a re-run. Prompt versions cover the system override and task
    spec. Adapter version is its class name + sampling kwargs (changes to
    temperature/top_p invalidate cache).
    """
    tools_src = (ROOT / "harness" / "tools.py").read_text()
    signature_src = (ROOT / "harness" / "signature.py").read_text()
    return {
        "tool_versions": {
            "harness/tools.py": _hash(tools_src)[:12],
            "harness/signature.py": _hash(signature_src)[:12],
        },
        "prompt_versions": {
            "system": _hash(SYSTEM_PROMPT_OVERRIDE)[:12],
            "task_spec": _hash(task_spec)[:12],
            "adapter": _hash(f"{adapter.__class__.__name__}:{json.dumps(adapter.sampling, sort_keys=True)}")[:12],
        },
    }


def _compute_run_id(task: int, model: str, adapter_name: str, versions: dict) -> str:
    """Content-addressed run_id per D6. Stable when task/model/adapter and all
    version stamps are stable; changes when any of them change.
    """
    payload = json.dumps({
        "task": task,
        "model": model,
        "adapter": adapter_name,
        "versions": versions,
    }, sort_keys=True)
    return _hash(payload)[:16]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _extract_error_detail(e: BaseException) -> dict | None:
    """Best-effort structured form of provider/SDK errors.

    OpenAI SDK exceptions (which smolagents wraps) expose `status_code`,
    `body`, `code`, `request_id` on the underlying API error. Smolagents'
    AgentGenerationError wraps these; we drill through __cause__ /
    __context__ to find them. Always falls back to capturing the exception
    type and module so the consumer knows what kind of failure this was.
    """
    detail: dict = {
        "type": f"{type(e).__module__}.{type(e).__name__}",
    }
    current: BaseException | None = e
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attr in ("status_code", "code", "request_id", "param"):
            val = getattr(current, attr, None)
            if val is not None and attr not in detail:
                detail[attr] = val
        body = getattr(current, "body", None)
        if body is not None and "body" not in detail:
            # OpenAI SDK body is usually a dict; serialize lossily if not.
            detail["body"] = body if isinstance(body, (dict, list, str, int, float, bool, type(None))) else str(body)
        response = getattr(current, "response", None)
        if response is not None and "response_text" not in detail:
            try:
                detail["response_text"] = response.text
            except Exception:  # noqa: BLE001
                pass
        current = current.__cause__ or current.__context__
    return detail


def _print_summary(record: dict, out_path: Path) -> None:
    status = "PASS" if record["completed"] else "FAIL"
    print()
    print(f"  task    {record['task']}")
    print(f"  model   {record['model']}")
    print(f"  adapter {record['adapter']}")
    print(f"  status  {status}")
    print(f"  calls   {record['tool_calls']}  errors {record['errors']}  loops {record['loops']}  early-term {record['early_termination']}")
    alignment = record.get("alignment") or {}
    hits = alignment.get("anchor_hits") or []
    if hits:
        glyphs = " ".join(f"{'✓' if h['satisfied'] else '✗'}{h['anchor_id']}" for h in hits)
        print(f"  anchors {glyphs}")
    if record.get("agent_error"):
        # First line only — full message + traceback in the JSON record.
        print(f"  err     {record['agent_error'].splitlines()[0]}")
    if record["notes"]:
        print(f"  notes   {record['notes']}")
    print(f"  saved   {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
