#!/usr/bin/env python3
"""run.py — entry point for one task × one model × one adapter.

Usage:
    python run.py --task 1 --model claude
    python run.py --task 2 --model qwen --adapter qwen --verbose
    python run.py --task 3 --model kimi --adapter passthrough
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from harness.agent import Agent
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
    args = p.parse_args()

    task_path = ROOT / "tasks" / f"0{args.task}-{_task_slug(args.task)}.md"
    if not task_path.exists():
        print(f"[err] task spec not found: {task_path}", file=sys.stderr)
        return 2

    task_spec = task_path.read_text()
    adapter = load_adapter(args.adapter)

    agent = Agent(
        model=args.model,
        adapter=adapter,
        verbose=args.verbose,
        max_steps=args.max_steps,
    )

    started = time.time()
    try:
        transcript = agent.run(task_spec=task_spec, task_id=args.task)
        error = None
    except Exception as e:  # noqa: BLE001 — top-level catch for the harness
        transcript = agent.transcript
        error = f"{type(e).__name__}: {e}"
        if args.verbose:
            traceback.print_exc()
    elapsed = time.time() - started

    eval_result = score(task_id=args.task, transcript=transcript, sandbox=ROOT / os.environ.get("SANDBOX_DIR", "sandbox"))

    record = {
        "task": args.task,
        "model": args.model,
        "adapter": args.adapter,
        "elapsed_s": round(elapsed, 2),
        "completed": eval_result["completed"],
        "tool_calls": eval_result["tool_calls"],
        "errors": eval_result["errors"],
        "loops": eval_result["loops"],
        "early_termination": eval_result["early_termination"],
        "notes": eval_result["notes"],
        "agent_error": error,
        "transcript_summary": _summarize(transcript),
    }

    out_path = Path(args.out) if args.out else (
        ROOT / "results" / f"task{args.task}-{args.model}-{args.adapter}.json"
    )
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


def _summarize(transcript: list[dict]) -> list[dict]:
    out = []
    for m in transcript:
        role = m.get("role")
        if role == "assistant":
            tcs = m.get("tool_calls") or []
            out.append({
                "role": "assistant",
                "content_preview": (m.get("content") or "")[:120],
                "tool_calls": [{"name": tc.get("name"), "args_preview": json.dumps(tc.get("arguments", {}))[:120]} for tc in tcs],
            })
        elif role == "tool":
            out.append({
                "role": "tool",
                "name": m.get("name"),
                "result_preview": (str(m.get("content") or ""))[:120],
            })
        elif role == "user":
            out.append({"role": "user", "content_preview": (m.get("content") or "")[:120]})
    return out


def _print_summary(record: dict, out_path: Path) -> None:
    status = "PASS" if record["completed"] else "FAIL"
    print()
    print(f"  task    {record['task']}")
    print(f"  model   {record['model']}")
    print(f"  adapter {record['adapter']}")
    print(f"  status  {status}")
    print(f"  calls   {record['tool_calls']}  errors {record['errors']}  loops {record['loops']}  early-term {record['early_termination']}")
    if record["agent_error"]:
        print(f"  err     {record['agent_error']}")
    if record["notes"]:
        print(f"  notes   {record['notes']}")
    print(f"  saved   {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
