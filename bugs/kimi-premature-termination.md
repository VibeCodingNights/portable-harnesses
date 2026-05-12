# [Bug] kimi: premature `end_turn` after the first tool call on non-native harnesses

**Model:** kimi &nbsp;·&nbsp; **Task:** 2, 3 (any multi-step task) &nbsp;·&nbsp; **Adapter:** passthrough

**Category:** behavioral

---

## What broke

Kimi K2.6 was post-trained inside Moonshot's native agentic loop. The end-of-turn predictor was RL'd against very specific context shapes — particular system prompt scaffolding, a particular tool-result envelope, a particular sampling regime. When you run Kimi inside a generic OpenAI-compatible loop with OpenAI-style tool results and default sampling, its termination predictor fires after the first tool call.

The user-visible failure: model calls `web_search` once, gets results, replies with a final summary, and stops. Never writes the file. Task fails with `early_termination: true`.

This is the same class of bug as the ones documented against Kimi on AWS Bedrock (anomalyco/opencode#13807, opencode/issues with Kimi) — premature `end_turn` because the harness and the model disagree about what a "complete" agentic turn looks like.

## What you'll see in `--verbose`

```text
Step 0: assistant tool_calls=[web_search(query=...)]
Step 0: tool result delivered
Step 1: assistant tool_calls=[]   # ← no more tool calls
         content="Based on my search I can summarize..."
         finish_reason="end_turn"
```

The harness loop exits at `tool_calls=[]`. Kimi never got to step 2. The doc was never written.

## What the harness expected

A multi-step trajectory — search, then write, then maybe a confirmation. It got one step.

## Smallest reproduction

```bash
python run.py --task 2 --model kimi --adapter passthrough --verbose
```

## Hypothesis

Behavioral coupling. Three knobs likely matter:

1. **Sampling.** Kimi K2.6 was RL'd at temperature 0.6, top_p 1.0. The default 0.7/1.0 is close but the RL'd termination behavior is calibrated to those exact numbers.
2. **System prompt shape.** Moonshot's native loop ends each turn with a continuation cue that resets the termination predictor. Without it, Kimi's prior is "task complete after one step".
3. **Tool-result envelope.** Kimi's training framed tool results as intermediate steps. OpenAI-shaped `role: tool` messages don't carry the same "more to come" signal.

## Fix sketch

There's also a harness-level prerequisite: smolagents sets `tool_choice="required"`, which Moonshot rejects in combination with Kimi's thinking mode. So step zero is `completion_overrides = {"tool_choice": "auto"}`. Once you can issue a request at all, the behavioral fixes:

In `adapters/kimi.py`:

```python
sampling = {"temperature": 0.6, "top_p": 1.0}
completion_overrides = {"tool_choice": "auto"}

_REMINDER = "Review the original task after each tool result. Only call `final_answer` when every step is finished."

def reshape_messages(self, messages):
    # Inject a continuation cue into the system prompt
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

Re-run. If you see Kimi reach step 2 you've moved the cell.

## References

- anomalyco/opencode#13807 — premature end_turn on Bedrock
- platform.kimi.ai/docs/guide/kimi-k2-6-quickstart — sampling defaults
- Moonshot agentic loop reference (Chinese-language docs at platform.moonshot.cn)
