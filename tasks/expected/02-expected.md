# Expected shape — Task 2

This file documents what a passing output looks like. It is *not* compared
character-for-character; the eval checks structural properties only.

A passing `output/qwen-tool-calling-summary.md` will:

- Open with a markdown `# heading`.
- Be at least 500 characters long.
- Contain at least two markdown links of the form `[text](url)`.
- Discuss the Qwen 3.6 / vLLM Jinja2 chat-template tool-calling issue with at
  least one specific symptom (malformed JSON in `<tool_call>` blocks, dropped
  arguments, broken multi-tool calls, etc.).

The transcript must contain at least one `web_search` tool call that returned
results (no error).
