"""harness/tools.py — the agent's three tools, as smolagents `@tool` functions.

This is what the agent loop calls. The MCP servers under `tools/` are
reference implementations of the same surface in stdio-MCP shape — kept for
attendees who want to expose these tools to Claude Desktop or another MCP
host. Nothing in `run.py` consumes them.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
from smolagents import tool


SANDBOX = Path(os.environ.get("SANDBOX_DIR", "sandbox")).resolve()
INPUTS_DIR = Path(__file__).parent.parent / "tasks" / "inputs"


def _safe_path(rel: str) -> Path:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    p = (SANDBOX / rel).resolve()
    if not str(p).startswith(str(SANDBOX)):
        raise ValueError(f"path escapes sandbox: {rel}")
    return p


@tool
def fs_read(path: str) -> str:
    """Read a text file from the sandbox, or from the read-only task inputs dir.

    Args:
        path: relative path inside the sandbox (or task inputs).
    """
    p = _safe_path(path)
    if p.exists():
        return p.read_text()
    candidate = (INPUTS_DIR / path).resolve()
    if candidate.exists():
        return candidate.read_text()
    return f"ERROR: not found: {path}"


@tool
def fs_write(path: str, content: str) -> str:
    """Write a text file into the sandbox. Overwrites if it exists.

    Args:
        path: relative path inside the sandbox.
        content: the text to write.
    """
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content.encode('utf-8'))} bytes to {path}"


@tool
def fs_list(path: str = ".") -> str:
    """List entries in a sandbox directory.

    Args:
        path: relative path inside the sandbox. Defaults to the sandbox root.
    """
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: not found: {path}"
    entries = sorted(c.name for c in p.iterdir())
    return "\n".join(entries) if entries else "(empty)"


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web. Returns up to `max_results` results as title/url/snippet
    lines. Uses Brave Search if BRAVE_API_KEY is set; otherwise returns a stub
    so the agent loop still runs end-to-end (Task 1 doesn't need real search).

    Args:
        query: the search query.
        max_results: how many results to return (default 5, max 20).
    """
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return f"STUB: set BRAVE_API_KEY in .env for real search. query={query!r}"
    max_results = max(1, min(int(max_results), 20))
    try:
        r = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            params={"q": query, "count": max_results},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return f"ERROR: brave search failed: {e}"
    results = (data.get("web", {}).get("results") or [])[:max_results]
    return "\n\n".join(
        f"{it.get('title')}\n{it.get('url')}\n{it.get('description')}" for it in results
    ) or "(no results)"


@tool
def codegen_run(code: str, stdin: str = "") -> str:
    """Execute a short Python program in a subprocess (30s timeout, CWD = sandbox).
    Returns stdout, then stderr, then returncode.

    Args:
        code: the Python source to run.
        stdin: optional stdin payload.
    """
    SANDBOX.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(SANDBOX),
        )
    except subprocess.TimeoutExpired:
        return "ERROR: code execution timed out (30s)"
    return f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}\nreturncode: {proc.returncode}"


def portable_tools() -> list:
    """The five tools as a list, in a stable order. ToolCallingAgent consumes this."""
    return [fs_read, fs_write, fs_list, web_search, codegen_run]
