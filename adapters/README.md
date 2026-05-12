# adapters/

This is where you work.

An adapter is a small object that tells the harness (smolagents' `ToolCallingAgent`) how to talk to a model that was post-trained against a different shape than smolagents' defaults assume.

## Three levels of reshaping

Watch for these as you read failures and write fixes:

| Level | Where it lives | Example |
|---|---|---|
| **Harness-default** | `completion_overrides` | Three of our four endpoints reject smolagents' `tool_choice="required"` |
| **Format-level** | `shape_response`, `reshape_messages` | Qwen's `<tool_call>` / `<tool_response>` tags, text-embedded tool calls |
| **Role-level** | `custom_role_conversions`, `reshape_messages` | GLM expects tool results as `observation`, not `tool` |
| **Behavioral** | `sampling`, `reshape_messages` | Kimi K2.6 terminating early when the context doesn't match its RL'd loop |

If your adapter doesn't move a model from ✗ to ✓, you've probably named the wrong level.

## The interface

`base.py` exposes five surfaces:

- `sampling: dict` — class-level kwargs forwarded to the OpenAI client (`temperature`, `top_p`, `max_tokens`)
- `completion_overrides: dict` — class-level kwargs that override smolagents' defaults (`tool_choice`, etc.)
- `custom_role_conversions: dict[str, str]` — `{from: to}` mapping smolagents applies to every message role before the wire
- `reshape_messages(messages) -> messages` — Python hook on the message list before sending
- `shape_response(response) -> response` — Python hook on the `ChatMessage` returned by the model

Override only what you need. The base class is identity for the hooks and empty for the dicts.

## Workflow

1. Run with `--verbose` and the passthrough adapter. Watch what the agent prints.
2. Find what differs from what the model expects (use `docs/model-expectations.md`).
3. Edit the stub. Start with the smallest reshaping (often `completion_overrides` or `custom_role_conversions`).
4. Re-run. Compare. Iterate.
5. When `python run.py --task N --model M --adapter M` passes for at least one task that fails under passthrough, you've measured the tax. PR it.

## Reference

`claude.py` is the smallest possible adapter — just `sampling` is overridden, because Anthropic-direct happens to fit smolagents' defaults cleanly. Read it as the *pattern*, then look at `qwen.py` / `glm.py` / `kimi.py` for the active stubs (each ships with the harness-default fix; format/role/behavioral fixes are TODOs).

- `docs/model-expectations.md` — what each model was RL'd against
- `docs/writing-adapters.md` — guide on picking the right hook
- `bugs/` — pre-documented failures, source repos, evidence
