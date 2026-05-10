# Task 2 — Research and Write

**Difficulty:** intermediate. Multi-tool, multi-step. Tests tool-call sequencing and result handling.

## What the agent must do

1. Use `web_search` to find recent information about **"vLLM Qwen tool calling chat template"**. Issue at most 3 searches.
2. Synthesize what you find into a short markdown document (3–6 paragraphs). The document must include:
   - A title (markdown `#`).
   - A summary of the issue in your own words.
   - At least two cited sources, formatted as `- [title](url)`.
3. Write the document to `output/qwen-tool-calling-summary.md` using `fs_write`.

## Why this exposes the portability tax

This task forces multiple tool calls *and* requires the model to feed each result back into its plan. Models that mishandle tool result framing tend to fail one of three ways here:

- **GLM:** loops — it issues `web_search` repeatedly because it never "saw" the previous results land.
- **Kimi:** gives up after the first search, writes the doc with no citations because it terminated early.
- **Qwen:** writes a doc but with broken markdown because it didn't escape special chars in the search-result snippets when interpolating them.
- **Claude:** should pass.

## How it's scored

The eval reads `sandbox/output/qwen-tool-calling-summary.md` and checks:

- File exists and is non-trivial (>500 chars).
- Contains at least one markdown `#` heading.
- Contains at least two `[text](url)` markdown links.
- Transcript shows at least one `web_search` tool call that succeeded.

The scoring is generous on content — the goal is to test whether the agent *completed* the loop, not whether the writing is great.
