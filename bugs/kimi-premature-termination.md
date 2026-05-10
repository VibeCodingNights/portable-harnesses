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

In `adapters/kimi.py`:

```python
sampling = {"temperature": 0.6, "top_p": 1.0}

def before_request(self, *, messages, tools, model, step):
    # Inject continuation cue into system prompt
    if messages and messages[0].get("role") == "system":
        messages = [
            {**messages[0], "content": messages[0]["content"] + "\n\nReview the original task after each tool result. Only stop when every step is finished."},
            *messages[1:],
        ]
    return messages, tools

def shape_tool_result(self, *, tool_call, result, model):
    content = json.dumps({"step_result": result, "status": "intermediate"}, default=str)
    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "name": tool_call["name"],
        "content": content,
    }
```

Re-run. If you see Kimi reach step 2 you've moved the cell.

## References

- anomalyco/opencode#13807 — premature end_turn on Bedrock
- platform.kimi.ai/docs/guide/kimi-k2-6-quickstart — sampling defaults
- Moonshot agentic loop reference (Chinese-language docs at platform.moonshot.cn)
