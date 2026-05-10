# Task 1 — File Transform

**Difficulty:** entry. Single tool, single step. Tests basic tool-calling format compatibility.

## What the agent must do

1. Read the file `sample-data.md` from the inputs directory using `fs_read`.
2. Extract the structured fields. The file is a markdown document with a YAML-like front-matter block listing **vendors**, each with `name`, `region`, and `priority`.
3. Write a JSON file to `output/vendors.json` using `fs_write` containing exactly:

   ```json
   {
     "vendors": [
       {"name": "...", "region": "...", "priority": <int>},
       ...
     ],
     "count": <int>
   }
   ```

   The `count` field equals the number of vendors. Vendors must appear in the same order as in the input.

## Why this exposes the portability tax

This is the smallest possible agentic loop: one tool, one read, one parse, one write. If a model can't complete this, the failure is unambiguous — it's pure tool-calling format compatibility.

- **Qwen:** may emit a `tool_call` with malformed JSON arguments (the Jinja2 template issue).
- **GLM:** may write to the wrong path because it never registered our tool result as a tool result.
- **Kimi:** may issue one `fs_read` and then immediately stop, never writing the output.
- **Claude:** should pass.

## How it's scored

The eval reads `sandbox/output/vendors.json` and compares it to `tasks/expected/01-expected.json`. Order-sensitive. Type-sensitive (`priority` must be an integer, not a string).
