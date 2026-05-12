# [Bug] qwen: Jinja2 chat template breaks tool calling under vLLM/llama.cpp

**Model:** qwen &nbsp;·&nbsp; **Task:** 1, 2, 3 (any task that uses tools) &nbsp;·&nbsp; **Adapter:** passthrough

**Category:** format-level

---

## What broke

Qwen-served-via-vLLM (and llama.cpp builds) emits tool calls as raw text wrapped in `<tool_call>...</tool_call>` tags rather than structured `tool_calls` field, OR emits structured tool_calls but with arguments as un-parseable strings (missing quotes around keys, trailing commas, escaped chars dropped). The shipped Jinja2 chat template that drives this was trained against a specific Qwen-Agent format and doesn't survive contact with the OpenAI tool-calling shape that LiteLLM forwards.

When the harness reads `tool_calls` and finds it empty, it concludes the model didn't call any tools and exits the loop. Task fails with zero apparent errors.

## What you'll see in `--verbose`

```text
RESPONSE message:
  content: "I'll read the file.\n<tool_call>\n{\"name\": \"fs_read\", \"arguments\": {\"path\": \"sample-data.md\"}}\n</tool_call>"
  tool_calls: []
  finish_reason: "stop"
```

The harness sees `tool_calls: []` and stops. The model thought it called the tool. The wire dropped the call.

## What the harness expected

```json
{ "tool_calls": [ {"id": "...", "function": {"name": "fs_read", "arguments": "{\"path\": \"sample-data.md\"}"} } ] }
```

## Smallest reproduction

```bash
python run.py --task 1 --model qwen --adapter passthrough --verbose
```

## Hypothesis

Format-level coupling. The Qwen-Agent chat template uses `<tool_call>` text-tag emission. When wrapped behind an OpenAI-compatible proxy, the proxy needs to extract the tag-wrapped JSON back out into the structured field. Some inference stacks do this; many don't (the bugs are catalogued in the allanchan339 and froggeric chat-template fix repos that exist solely to patch this). vLLM 0.7.x ships a Qwen template that forgets to populate the structured `tool_calls` when arguments contain newlines.

## Fix sketch

In `adapters/qwen.py`, override `shape_response` to parse text-embedded tool calls back into the structured field smolagents reads:

```python
import json, re

def shape_response(self, response):
    if response.tool_calls or not response.content:
        return response
    parsed = []
    for i, m in enumerate(re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", response.content, re.S)):
        try:
            payload = json.loads(m.group(1))
            parsed.append({
                "id": f"qwen_{i}",
                "type": "function",
                "function": {"name": payload["name"], "arguments": json.dumps(payload.get("arguments") or {})},
            })
        except json.JSONDecodeError:
            continue
    if parsed:
        response.tool_calls = parsed
        response.content = ""  # avoid double-execution
    return response
```

Re-run the same task. The cell should flip ✗ → ✓.

## References

- allanchan339 / chat-template-qwen3 (github)
- froggeric / qwen-tool-template-fix (github)
- vLLM issues tracker: search "qwen tool calling chat template"
