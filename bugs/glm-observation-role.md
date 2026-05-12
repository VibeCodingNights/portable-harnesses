# [Bug] glm: tool results delivered as `role: tool` are silently ignored

**Model:** glm &nbsp;·&nbsp; **Task:** 2, 3 (any multi-step task) &nbsp;·&nbsp; **Adapter:** passthrough

**Category:** role-level

---

## What broke

GLM-5.1 inherits ChatGLM's pre-tool-calling convention. In ChatGLM's published training format, tool results were a turn with `role: observation`. GLM-5.1 was post-trained on traces in this shape. When the harness hands it an OpenAI-shaped tool message — `{"role": "tool", "tool_call_id": ..., "content": ...}` — the model often acts as if the previous tool call returned nothing.

The user-visible failure is a loop: GLM re-issues the same `web_search` (or `fs_read`) over and over because, from its perspective, no result has come back yet. The eval shows this as `loops > 0`.

## What you'll see in `--verbose`

Step 1: model calls `web_search(query="vLLM Qwen tool calling")`.
Step 2: harness sends back `{"role": "tool", ...}` with results.
Step 3: model calls `web_search(query="vLLM Qwen tool calling")` *again* — same query.
Step 4: same thing.
... until `--max-steps`.

## What the harness expected

The model should have read the tool result and moved on. It read nothing.

## Smallest reproduction

```bash
python run.py --task 2 --model glm --adapter passthrough --verbose
```

## Hypothesis

Role-level coupling. GLM's training data labeled tool results with `role: observation`. The model's attention has effectively learned to look for that token at that position. `role: tool` either tokenizes differently or just isn't the cue the weights are listening for.

## Fix sketch

In `adapters/glm.py`, the cleanest fix is one line — smolagents will rewrite every `role: tool` message to `role: observation` for you:

```python
class GLMAdapter(Adapter):
    custom_role_conversions = {"tool": "observation"}
```

If z.ai's endpoint rejects unknown roles at the surface, fall back to a `user`-turn wrapper in `reshape_messages`:

```python
def reshape_messages(self, messages):
    out = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        if role == "tool":
            name = (m.get("name") if isinstance(m, dict) else getattr(m, "name", "")) or "tool"
            content = (m.get("content") if isinstance(m, dict) else getattr(m, "content", "")) or ""
            out.append({"role": "user", "content": f"[observation:{name}]\n{content}"})
        else:
            out.append(m)
    return out
```

Either form should break the loop.

## References

- ChatGLM published chat format (THUDM/ChatGLM3 README)
- z.ai docs → "Function calling" (note the example uses `observation`)
