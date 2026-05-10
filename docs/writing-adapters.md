# Writing adapters

A guide to picking the right level of reshaping. Read this once before opening a stub.

---

## Step 1: name what you're seeing

Run with `--verbose`:

```bash
python run.py --task 1 --model qwen --adapter passthrough --verbose
```

Two messages matter:

1. **REQUEST** — what got sent. The `messages` array, the `tools` array, the sampling params.
2. **RESPONSE** — what came back. The `tool_calls` (might be empty!), the `content` (might contain a buried tool call), the `finish_reason`.

Read both. Then ask:

| Question | If yes, you're at this level |
|---|---|
| Is the model emitting tool calls inside `content` text instead of a structured `tool_calls` array? | **format-level** |
| Are tool definitions arriving with the wrong shape, missing keys, dropped types? | **format-level** |
| Is the model looping on the same call because it never "saw" the result? | **role-level** |
| Is the model stopping early — one tool call, then `finish_reason: stop` while clearly more steps remain? | **behavioral** |
| Is sampling default but the model was RL'd at different settings? | **behavioral** |

The same model can have failures at multiple levels. Address one at a time.

---

## Step 2: pick the smallest possible reshaping

For each level, here's the minimal change that usually moves the needle.

### Format-level

Override `after_response` to parse text-embedded tool calls:

```python
import re, json
from adapters.base import Adapter

class MyAdapter(Adapter):
    def after_response(self, choice, *, model, step):
        msg = super().after_response(choice, model=model, step=step)
        if not msg["tool_calls"] and "<tool_call>" in (msg["content"] or ""):
            for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", msg["content"], re.S):
                try:
                    p = json.loads(m.group(1))
                    msg["tool_calls"].append({
                        "id": f"adapt_{step}_{len(msg['tool_calls'])}",
                        "name": p["name"],
                        "arguments": p.get("arguments", {}),
                    })
                except json.JSONDecodeError:
                    pass
        return msg
```

Override `shape_tool_result` to wrap the result in the envelope the model wants:

```python
def shape_tool_result(self, *, tool_call, result, model):
    payload = json.dumps({"name": tool_call["name"], "content": result}, default=str)
    return {
        "role": "user",
        "content": f"<tool_response>\n{payload}\n</tool_response>",
    }
```

### Role-level

Just swap the role:

```python
def shape_tool_result(self, *, tool_call, result, model):
    return {
        "role": "observation",
        "name": tool_call["name"],
        "content": json.dumps(result, default=str),
    }
```

If the API rejects unknown roles, fall back to a `user` turn with a structured prefix:

```python
return {
    "role": "user",
    "content": f"[observation:{tool_call['name']}] {json.dumps(result, default=str)}",
}
```

### Behavioral

Match RL'd sampling defaults at the class level:

```python
class MyAdapter(Adapter):
    sampling = {"temperature": 0.6, "top_p": 1.0}
```

Inject continuation cues in `before_request`:

```python
def before_request(self, *, messages, tools, model, step):
    if messages and messages[0].get("role") == "system":
        messages = [
            {**messages[0], "content": messages[0]["content"] + "\n\nContinue with the next step until every output is written."},
            *messages[1:],
        ]
    return messages, tools
```

---

## Step 3: measure

Don't trust your gut. Run the same task, same model, with `passthrough` and with your adapter:

```bash
python run.py --task 2 --model glm --adapter passthrough
python run.py --task 2 --model glm --adapter glm
```

Compare the two records in `results/`. The fields to watch:

- `completed` — did it pass? (the headline)
- `tool_calls` — more is not always better; look for the right number, not the largest
- `errors` — should drop
- `loops` — should drop to 0 for role-level fixes on GLM
- `early_termination` — should flip to false for behavioral fixes on Kimi

If your adapter moved any of those columns in a good direction, write a one-paragraph note in the bug file you fixed and PR it. That's the deliverable.

---

## What "done" looks like

You can name the level. You can show the before/after numbers. The cell flipped ✗ → ✓. That's the unit of progress tonight.
