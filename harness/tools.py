"""harness/tools.py — local in-process MCP tool stubs.

The "real" event uses MCP servers hosted on the proxy. For local runs (and
because the wire shape of an MCP tool call is identical from the model's POV
to a local function call once the harness translates it), we expose the same
three tools in-process. The MCP servers in `tools/` are the production path;
these are the dev path.

The tool *spec* (the JSON schema the model sees) is what adapters reshape.
The implementation is just whatever is fastest to test against.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx


SANDBOX = Path(os.environ.get("SANDBOX_DIR", "sandbox")).resolve()


@dataclass
class Tool:
    name: str
    spec: dict
    impl: Callable[..., Any]

    def run(self, **kwargs: Any) -> Any:
        return self.impl(**kwargs)


def _safe_path(rel: str) -> Path:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    p = (SANDBOX / rel).resolve()
    if not str(p).startswith(str(SANDBOX)):
        raise ValueError(f"path escapes sandbox: {rel}")
    return p


def fs_read(path: str) -> dict:
    p = _safe_path(path)
    if not p.exists():
        # Also check the read-only inputs dir.
        candidate = (Path(__file__).parent.parent / "tasks" / "inputs" / path).resolve()
        if candidate.exists():
            return {"path": path, "content": candidate.read_text()}
        return {"error": f"not found: {path}"}
    return {"path": path, "content": p.read_text()}


def fs_write(path: str, content: str) -> dict:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {"path": path, "bytes": len(content.encode("utf-8"))}


def fs_list(path: str = ".") -> dict:
    p = _safe_path(path)
    if not p.exists():
        return {"error": f"not found: {path}"}
    return {"path": path, "entries": sorted(c.name for c in p.iterdir())}


def web_search(query: str, max_results: int = 5) -> dict:
    """Hits the proxy's /mcp/search endpoint, which fronts a Brave Search key.
    Falls back to a stub when the proxy is not reachable so the loop still runs."""
    url = os.environ.get("MCP_SEARCH_URL")
    token = os.environ.get("PROXY_TOKEN")
    if url and token:
        try:
            r = httpx.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"query": query, "max_results": max_results},
                timeout=20,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            return {"error": f"search proxy unreachable: {e}", "query": query, "results": []}
    return {
        "query": query,
        "results": [
            {"title": "stub result", "url": "https://example.com", "snippet": f"set MCP_SEARCH_URL to enable real search for: {query}"},
        ],
    }


def codegen_run(code: str, stdin: str = "") -> dict:
    """Execute Python in a subprocess. The proxy hosts a sandboxed container
    version; this local version just shells out with a timeout."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(SANDBOX),
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "code execution timed out (30s)"}


# Tool specs in OpenAI function-calling shape. Adapters reshape these per model.
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fs_read",
            "description": "Read a text file from the sandbox or the read-only task inputs directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_write",
            "description": "Write a text file into the sandbox. Overwrites existing files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_list",
            "description": "List files in a sandbox directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web. Returns title/url/snippet for each result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "codegen_run",
            "description": "Execute a short Python program. Returns stdout, stderr, returncode. Timeout 30s. CWD is the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "stdin": {"type": "string", "default": ""},
                },
                "required": ["code"],
            },
        },
    },
]


def build_tool_registry() -> dict[str, Tool]:
    impls: dict[str, Callable[..., Any]] = {
        "fs_read": fs_read,
        "fs_write": fs_write,
        "fs_list": fs_list,
        "web_search": web_search,
        "codegen_run": codegen_run,
    }
    return {
        spec["function"]["name"]: Tool(
            name=spec["function"]["name"],
            spec=spec,
            impl=impls[spec["function"]["name"]],
        )
        for spec in TOOLS
    }
