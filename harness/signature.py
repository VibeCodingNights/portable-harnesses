"""harness/signature.py — canonical form for tool calls.

Two logically equivalent calls must produce the same signature; cosmetic
variation (path normalization, key order, whitespace, type coercion) is
collapsed, but semantic variation is preserved.

Used by:
    - the alignment engine (harness/alignment.py) for exact-tier matching
    - anchor matching (compare canonical signature against anchor pattern)
    - the dedup hash (run_id includes per-call signatures so cache is honest)

Per-tool conventions live in TOOL_CANONICALIZERS. For tools without a
dedicated entry, the default canonicalizer applies recursive key-sort +
primitive normalization.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Callable


def canonical(tool_name: str, arguments: dict[str, Any] | None) -> str:
    """Return a stable canonical signature for `tool_name(**arguments)`.

    Same logical call → same signature, regardless of cosmetic variation.
    Used both for exact matching (signature equality) and pattern matching
    (against anchor signature_pattern).
    """
    args = arguments or {}
    canonicalize = TOOL_CANONICALIZERS.get(tool_name, _default_canonicalize)
    canonical_args = canonicalize(args)
    body = ", ".join(f"{k}={_repr(v)}" for k, v in sorted(canonical_args.items()))
    return f"{tool_name}({body})"


def matches_pattern(signature: str, pattern: str) -> bool:
    """Does a canonical signature match an anchor signature_pattern?

    Patterns use:
        tool_name(arg=value|*, arg=*<suffix>, arg=<prefix>*)
    An omitted arg in the pattern means "don't constrain". An arg with value `*`
    accepts any value. Prefix/suffix wildcards on string values.
    """
    pat_tool, pat_args = _parse_pattern(pattern)
    sig_tool, sig_args = _parse_pattern(signature)

    if pat_tool != sig_tool:
        return False

    for arg_name, arg_pattern in pat_args.items():
        if arg_name not in sig_args:
            return False
        if not _arg_matches(sig_args[arg_name], arg_pattern):
            return False
    return True


# ---------- pattern parsing ----------

_CALL_RE = re.compile(r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\((?P<body>.*)\)$", re.DOTALL)


def _parse_pattern(s: str) -> tuple[str, dict[str, str]]:
    """Parse 'tool_name(k1=v1, k2=v2)' into ('tool_name', {'k1': 'v1', 'k2': 'v2'}).

    Values may contain commas if JSON-encoded; we use a small state machine to
    split on top-level commas only. Bare `*` (wildcard) is supported as a
    sentinel for "any value".
    """
    m = _CALL_RE.match(s.strip())
    if not m:
        return ("", {})
    name = m.group("name")
    body = m.group("body").strip()
    if not body or body == "*":
        return (name, {})

    args: dict[str, str] = {}
    for chunk in _split_top_level(body):
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        args[k.strip()] = v.strip()
    return (name, args)


def _split_top_level(s: str) -> list[str]:
    """Split on commas at JSON nesting depth zero."""
    out: list[str] = []
    depth = 0
    in_str = False
    escape = False
    buf: list[str] = []
    for ch in s:
        if escape:
            buf.append(ch); escape = False; continue
        if ch == "\\":
            buf.append(ch); escape = True; continue
        if ch == '"':
            buf.append(ch); in_str = not in_str; continue
        if in_str:
            buf.append(ch); continue
        if ch in "{[(":
            depth += 1; buf.append(ch); continue
        if ch in "}])":
            depth -= 1; buf.append(ch); continue
        if ch == "," and depth == 0:
            out.append("".join(buf)); buf = []; continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return [c.strip() for c in out if c.strip()]


def _arg_matches(value: str, pattern: str) -> bool:
    """Match a single arg value against a pattern. Both are stringified."""
    pattern = pattern.strip()
    if pattern == "*":
        return True
    # Strip surrounding JSON quotes for prefix/suffix matching.
    v = value.strip().strip('"')
    p = pattern.strip('"')
    if p.startswith("*") and p.endswith("*"):
        return p[1:-1] in v
    if p.startswith("*"):
        return v.endswith(p[1:])
    if p.endswith("*"):
        return v.startswith(p[:-1])
    return v == p


# ---------- canonicalizers ----------

def _default_canonicalize(args: dict[str, Any]) -> dict[str, Any]:
    return {k: _normalize_value(v) for k, v in args.items()}


def _normalize_value(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return {k: _normalize_value(vv) for k, vv in sorted(v.items())}
    if isinstance(v, list):
        return [_normalize_value(vv) for vv in v]
    return v


def _repr(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonicalize_path(args: dict[str, Any]) -> dict[str, Any]:
    """fs_* tools: normalize the 'path' field — collapse separators, strip
    leading slashes so '/foo/bar' and 'foo/bar' produce identical signatures.

    Does NOT collapse to basename. 'sample-data.md' and 'sub/sample-data.md'
    remain distinct signatures because they reference different files.
    Anchor patterns with a `*suffix` wildcard handle the abs-vs-relative case
    for callers that need to match across path variations; exact-tier
    alignment only matches when paths are the same after normalization.
    """
    out = dict(args)
    if "path" in out and isinstance(out["path"], str):
        p = PurePosixPath(out["path"])
        s = str(p).lstrip("/")
        out["path"] = s if s else str(p)
    return _default_canonicalize(out)


def _canonicalize_web_search(args: dict[str, Any]) -> dict[str, Any]:
    """web_search: query whitespace-collapse + lowercase. Same query in
    different casings → same signature. max_results untouched (it changes
    behavior, so it's semantic).
    """
    out = dict(args)
    if "query" in out and isinstance(out["query"], str):
        out["query"] = re.sub(r"\s+", " ", out["query"].strip().lower())
    return _default_canonicalize(out)


def _canonicalize_codegen(args: dict[str, Any]) -> dict[str, Any]:
    """codegen_run: the code IS the call — different code is a different call.
    But code can be kilobytes; we hash it for a stable, compact signature.
    Whitespace in the code does count toward the hash — minor variants ARE
    different calls. This is intentional; if a model rewrites its code, that's
    a meaningful difference.
    """
    out = dict(args)
    if "code" in out and isinstance(out["code"], str):
        digest = hashlib.sha1(out["code"].encode("utf-8")).hexdigest()[:12]
        out["code"] = f"sha:{digest}"
    if "stdin" in out and isinstance(out["stdin"], str) and out["stdin"]:
        digest = hashlib.sha1(out["stdin"].encode("utf-8")).hexdigest()[:8]
        out["stdin"] = f"sha:{digest}"
    return _default_canonicalize(out)


TOOL_CANONICALIZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "fs_read": _canonicalize_path,
    "fs_write": _canonicalize_path,
    "fs_list": _canonicalize_path,
    "web_search": _canonicalize_web_search,
    "codegen_run": _canonicalize_codegen,
    # final_answer uses default — its arguments are descriptive text.
}


# ---------- intent categories (D3 commit) ----------

INTENT_CATEGORIES: dict[str, str] = {
    "fs_read": "gather",
    "fs_list": "gather",
    "web_search": "gather",
    "fs_write": "produce",
    "codegen_run": "execute",
    "final_answer": "terminal",
}


def intent_category(tool_name: str) -> str:
    """Coarse intent for cross-tool suggestive matching (D3)."""
    return INTENT_CATEGORIES.get(tool_name, "unknown")
