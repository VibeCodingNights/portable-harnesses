# Task 3 — Full Pipeline

**Difficulty:** advanced. Tests complex multi-step agentic behavior with chained tool dependencies.

## What the agent must do

1. Use `web_search` to find a current list of the four Chinese frontier-lab models referenced tonight (Qwen, GLM, Kimi, plus Bailing or Stepfun — pick one).
2. Use `fs_write` to create a CSV at `output/models.csv` with columns:

   ```
   model,lab,strength
   ```

   One row per model. `strength` is your one-sentence summary based on what you found. Include exactly four rows (plus the header).
3. Use `codegen_run` to execute a Python program that:
   - Reads `output/models.csv`
   - Counts rows (excluding the header)
   - Writes the count as a single integer to `output/count.txt`
4. Use `fs_read` to read back `output/count.txt` and confirm it equals `4` in your final response.

## Why this exposes the portability tax

This is the boss task. It chains four distinct tool calls with dependencies: search → write → execute → read. Every link in the chain is an opportunity to drop the thread.

Failure modes you'll see:

- **Qwen:** drops one of the steps because a tool result came back in a shape its template didn't parse — the model didn't realize the file was written, so it never ran the Python.
- **GLM:** loops on `web_search` because it can't tell the previous search succeeded; never reaches `codegen_run`.
- **Kimi:** completes step 1, fires `end_turn` after writing the CSV, never executes the Python at all.
- **Claude:** should reach step 4 and report `4`.

## How it's scored

The eval checks all of:

- `sandbox/output/models.csv` exists and has exactly 5 lines (header + 4 rows).
- `sandbox/output/count.txt` exists and contains `4`.
- Transcript contains at least one successful call each of `web_search`, `fs_write`, `codegen_run`, `fs_read`.
- Final assistant message mentions the count `4`.

Partial credit is reflected in `tool_calls`/`errors` columns, not `completed`. Either you finished the pipeline or you didn't.
