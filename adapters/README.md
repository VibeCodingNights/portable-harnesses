# adapters/

This is where you work.

An adapter reshapes context to match what a model was post-trained against. The harness is identical for every model. The adapter is what lets the same harness run a model the model wants to be run.

## Three levels of reshaping

Watch for these as you read failures and write fixes:

| Level | Where it lives | Example |
|---|---|---|
| **Format-level** | function-spec shape, tool-call envelope | Qwen's `<tool_call>` / `<tool_response>` tags, Jinja2 chat template quirks |
| **Role-level** | which `role` carries which content | GLM expects tool results as `observation`, not `tool` |
| **Behavioral** | sampling, system prompt scaffolding, end-of-turn cues | Kimi K2.6 terminating early when the context doesn't match its RL'd loop |

If your adapter doesn't move a model from ✗ to ✓, you've probably named the wrong level.

## The interface

`base.py` defines four hooks:

- `before_request(messages, tools, model, step)` — reshape outgoing context
- `after_response(choice, model, step)` — normalize the response (parse text-embedded tool calls, etc.)
- `shape_tool_result(tool_call, result, model)` — frame the tool result the way the model wants
- `sampling` — class-level dict of `temperature` / `top_p`

Override only what you need. The base class default-handles the OpenAI-shaped path.

## Workflow

1. Run with `--verbose` and the passthrough adapter. Watch the actual messages.
2. Find what differs from what the model expects (use `docs/model-expectations.md`).
3. Edit the stub. Add the smallest reshaping that fixes one thing.
4. Re-run. Compare. Iterate.
5. When `python run.py --task N --model M --adapter M` passes for at least one task that fails under passthrough, you've measured the tax. PR it.

## Reference

`claude.py` is the complete reference. It only really shows how to enforce
tool_call/tool_result pairing and stable JSON content, but that's the *pattern* —
read the hooks, see what's idiomatic, then write your model's adapter the same way.

`docs/model-expectations.md` — what each model was RL'd against
`docs/writing-adapters.md` — guide on picking format/role/behavioral
`bugs/` — pre-documented failures, source repos, evidence
