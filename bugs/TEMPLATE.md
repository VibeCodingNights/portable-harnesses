# [Bug] <model>: <one-line summary>

**Model:** <claude | qwen | glm | kimi> &nbsp;·&nbsp; **Task:** <1 | 2 | 3> &nbsp;·&nbsp; **Adapter:** <passthrough | model-specific>

**Category:** <format-level | role-level | behavioral>

---

## What broke

One paragraph. The user-visible failure: did the agent loop forever, give up early, write garbage, error out?

## What you sent

The exact request payload (or the relevant slice). Use a fenced code block. Include the message list, the tool definitions, and any sampling params if they're relevant.

```json
{ "messages": [...], "tools": [...] }
```

## What the model emitted

The exact response. Especially the `tool_calls` array, the `content`, the `finish_reason`. If the response embeds tool calls inside text rather than a structured field, paste it verbatim.

```json
{ "content": "...", "tool_calls": [...], "finish_reason": "..." }
```

## What the harness expected

What the agent loop tried to do with the response and where it diverged. ("Expected `tool_calls[0].function.arguments` to be valid JSON; got the literal string `'{path: vendors.json'` — note missing quotes.")

## Smallest reproduction

The minimal command that produces this:

```bash
python run.py --task <N> --model <M> --adapter passthrough --verbose
```

Plus a transcript pointer if it's in `results/`: `results/task<N>-<M>-passthrough.json`.

## Hypothesis

What's coupled, and where? Format-level / role-level / behavioral? Reference `docs/model-expectations.md` if there's a documented post-training convention this violates.

## Fix sketch (optional)

If you took a shot at a shim, what category of reshaping did you do? Did it move the cell from ✗ to ✓?
