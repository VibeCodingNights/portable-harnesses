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

In `adapters/glm.py`, override `shape_tool_result`:

```python
def shape_tool_result(self, *, tool_call, result, model):
    return {
        "role": "observation",
        "name": tool_call["name"],
        "content": json.dumps(result, default=str),
    }
```

If the proxy/API rejects unknown roles at the surface layer, fall back to a `user` turn with a structured prefix that GLM was likely also exposed to during training:

```python
return {
    "role": "user",
    "content": f"[observation:{tool_call['name']}]\n{json.dumps(result, default=str)}",
}
```

Either form should break the loop.

## References

- ChatGLM published chat format (THUDM/ChatGLM3 README)
- z.ai docs → "Function calling" (note the example uses `observation`)
