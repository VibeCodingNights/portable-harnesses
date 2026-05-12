# Writing adapters

A guide to picking the right level of reshaping. Read this once before opening a stub.

---

## The four hook points

Every adapter is a subclass of `adapters.base.Adapter`. You override one or more of these:

| Hook | What it controls | When you reach for it |
|---|---|---|
| `sampling: dict` | kwargs forwarded to the OpenAI client (temperature, top_p, max_tokens) | The lab published RL'd defaults different from generic defaults |
| `completion_overrides: dict` | kwargs forwarded to the same client that override smolagents' defaults | smolagents sets `tool_choice="required"` and your endpoint rejects it |
| `custom_role_conversions: dict[str, str]` | `{from: to}` smolagents applies to every message role | Model expects `observation`, not `tool` (GLM) |
| `reshape_messages(messages) -> messages` | Python hook on the message list before the wire | Inject continuation cues (Kimi), wrap tool results in custom envelopes (Qwen) |
| `shape_response(response) -> response` | Python hook on the ChatMessage returned by the model | Parse text-embedded `<tool_call>` blocks into `response.tool_calls` (Qwen), preserve `reasoning_content` |

`adapters/claude.py` is the smallest possible example — just `sampling` is overridden. `adapters/qwen.py`, `glm.py`, and `kimi.py` are stubs with TODOs.

---

## Step 1: name what you're seeing

Run with `--verbose`:

```bash
python run.py --task 1 --model qwen --adapter passthrough --verbose
```

smolagents will log every step. The questions to ask:

| Question | If yes, you're at this level |
|---|---|
| Endpoint 400/404s with a specific complaint (e.g., "tool_choice 'required' is not supported")? | **harness-default** — `completion_overrides` |
| Is the model emitting tool calls inside `content` text instead of a structured `tool_calls` array? | **format-level** — `shape_response` |
| Are tool definitions arriving with the wrong shape, missing keys, dropped types? | **format-level** — `reshape_messages` |
| Is the model looping on the same call because it never "saw" the result? | **role-level** — `custom_role_conversions` |
| Is the model stopping early — one tool call, then `finish_reason: stop` while clearly more steps remain? | **behavioral** — `reshape_messages` + `sampling` |
| Is sampling default but the model was RL'd at different settings? | **behavioral** — `sampling` |

The same model can have failures at multiple levels. Address one at a time.

---

## Step 2: pick the smallest possible reshaping

### Harness-default

This is the cheapest fix. Three of our four endpoints (Qwen, GLM, Kimi) reject `tool_choice="required"`:

```python
class MyAdapter(Adapter):
    completion_overrides = {"tool_choice": "auto"}
```

That single line takes Qwen, GLM, and Kimi from FAIL to PASS on Task 1. It's also the only fix in the Kimi adapter today.

### Format-level

Parse text-embedded tool calls in `shape_response`:

```python
import re, json
from adapters.base import Adapter

class QwenAdapter(Adapter):
    def shape_response(self, response):
        if response.tool_calls or not response.content:
            return response
        parsed = []
        for i, m in enumerate(re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", response.content, re.S)):
            try:
                p = json.loads(m.group(1))
                parsed.append({
                    "id": f"qwen_{i}",
                    "type": "function",
                    "function": {"name": p["name"], "arguments": json.dumps(p.get("arguments") or {})},
                })
            except json.JSONDecodeError:
                continue
        if parsed:
            response.tool_calls = parsed
        return response
```

### Role-level

The cleanest fix is `custom_role_conversions` — smolagents will rewrite every `role: tool` to `role: observation` before sending:

```python
class GLMAdapter(Adapter):
    custom_role_conversions = {"tool": "observation"}
```

If the endpoint rejects unknown roles entirely, fall back to a `user`-turn wrapper in `reshape_messages`:

```python
def reshape_messages(self, messages):
    out = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        if role == "tool":
            name = (m.get("name") if isinstance(m, dict) else getattr(m, "name", "")) or "tool"
            content = (m.get("content") if isinstance(m, dict) else getattr(m, "content", "")) or ""
            out.append({"role": "user", "content": f"[observation:{name}] {content}"})
        else:
            out.append(m)
    return out
```

### Behavioral

Match RL'd sampling at the class level:

```python
class KimiAdapter(Adapter):
    sampling = {"temperature": 0.6, "top_p": 1.0}
```

Inject continuation cues into the system prompt in `reshape_messages`:

```python
_REMINDER = "Important: if any step remains unfinished, issue another tool call."

def reshape_messages(self, messages):
    if not messages:
        return messages
    m0 = messages[0]
    role = m0.get("role") if isinstance(m0, dict) else getattr(m0, "role", None)
    if role != "system":
        return messages
    existing = m0.get("content") if isinstance(m0, dict) else getattr(m0, "content", "")
    patched = existing + "\n\n" + _REMINDER
    if isinstance(m0, dict):
        return [{**m0, "content": patched}, *messages[1:]]
    m0.content = patched
    return messages
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
