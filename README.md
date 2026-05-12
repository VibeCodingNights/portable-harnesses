# Portable Harnesses

You swapped the model and everything broke. Not the API call — the API call worked fine. The model just stopped finishing tasks.

Every model shipped this year was post-trained against a specific harness. Qwen 3.6 was RL'd against particular tool schemas. Kimi K2.6 was optimized at specific sampling settings inside a specific agentic loop. Claude expects every `tool_call` to have a matching tool result. GLM-5.1 expects tool results as `observation`, not `tool`. These aren't preferences. They're baked into the weights.

OpenRouter normalizes the API surface. [smolagents](https://github.com/huggingface/smolagents)'s `ToolCallingAgent` is our reference harness — small enough to read in an afternoon, vendor-neutral, MCP-aware. Neither touches the middle: the context window itself, where a model trained for one shape of input silently degrades when you hand it another.

Tonight: one harness, three tasks, four models. Measure what breaks. Write the shim.

---

## Quick start

```bash
git clone https://github.com/VibeCodingNights/portable-harnesses
cd portable-harnesses
./setup.sh                                  # writes .env from template, installs deps
# → grab a key at https://openrouter.ai/keys, add ~$10 credit, paste into .env
./setup.sh                                  # second run: health-checks the four models
```

Four green checkmarks means you're ready. One OpenRouter key fans out to all four labs — no Anthropic / DashScope / Zhipu / Moonshot accounts needed.

```bash
# Run a task through a model with the naive (passthrough) adapter
python run.py --task 1 --model claude
python run.py --task 1 --model qwen
python run.py --task 1 --model glm
python run.py --task 1 --model kimi

# Run with a model-specific adapter
python run.py --task 1 --model qwen --adapter qwen

# Watch the wire — what got sent, what came back
python run.py --task 1 --model qwen --verbose

# Score everything
./bench.sh naive       # all models × all tasks, passthrough adapter
./bench.sh adapted     # all models × all tasks, model-specific adapters
```

---

## The three targets

```
TARGET 1: BREAK IT     — Swap models, document what breaks
TARGET 2: SHIM IT      — Write an adapter that reshapes context per-model
TARGET 3: MEASURE IT   — Score the before/after delta
```

Pick one. Pick a model. Go.

- **Beginner:** Run the same task through 3+ models with `--verbose`. Watch what differs. File a bug in `bugs/` using `TEMPLATE.md`.
- **Advanced:** Open `adapters/qwen.py`, `adapters/glm.py`, or `adapters/kimi.py` (stubs) and reshape context to match the model's post-training expectations. Reference: `adapters/claude.py` (complete) and `docs/model-expectations.md`.
- **Ambitious:** Run `./bench.sh adapted` and produce the 12-cell table (4 models × 3 tasks) with passthrough vs adapted scores. The aggregate portability tax. Nobody has published this number.

---

## What's in here

| Path | What it is | Do you touch it? |
|---|---|---|
| `harness/agent.py` | Thin facade over `smolagents.ToolCallingAgent` + a `RouterModel` that pins each request to its lab-of-origin provider | No |
| `harness/tools.py` | The three agent tools as smolagents `@tool` functions | No |
| `tools/` | MCP reference implementations of the same tools (for Claude Desktop / other MCP hosts) | No |
| `tasks/` | Three agentic tasks + scoring | No |
| `adapters/` | Per-model shims that override smolagents defaults / reshape context | **Yes** |
| `bugs/` | Format-coupling bug reports | **Yes** |
| `results/` | Run outputs | Generated |
| `docs/` | Model expectations, known bugs, adapter guide | Read |

---

## The four models

| Short | OpenRouter slug | Lab | $/M in | $/M out | Post-training quirk |
|---|---|---|---|---|---|
| `claude` | `anthropic/claude-opus-4.7` | Anthropic | $5.00 | $25.00 | Strict: every `tool_call` needs a matching `tool_result`. Baseline. |
| `qwen` | `qwen/qwen3.6-max-preview` | Alibaba | — | — | Format-level: Jinja2 chat template, `<tool_response>` tags. |
| `glm` | `z-ai/glm-5.1` | Zhipu | $0.98 | $3.08 | Role-level: tool results expected as `observation`, not `tool`. |
| `kimi` | `moonshotai/kimi-k2.6` | Moonshot | $0.75 | $3.50 | Behavioral: premature `end_turn` when context shape doesn't match RL training. |

All four are fronted by your one OpenRouter key. **Budget note:** Claude Opus 4.7 dominates spend — a full `./bench.sh both` (24 multi-step runs) typically eats $2–4 of Claude alone. $10 of OpenRouter credit comfortably covers the night; $5 works if you skip the full benchmark and explore one model at a time.

Mapping from short name → slug lives in `harness/agent.py:MODEL_SLUGS`. Swap a model by editing that dict.

---

## Results from one full `./bench.sh both`

Twelve cells × two adapter states. Every record carries a full transcript and a populated `alignment` field; the anchor verdicts here are read directly from `results/*.json` via `jq '.alignment.anchor_hits'`.

### Task 1 — File transform (`fs_read` → `fs_write`)

| Model  | Passthrough           | Adapted              | Anchors (pt → ad) |
|--------|-----------------------|----------------------|---|
| claude | ✓ vendors.json match  | ✓ vendors.json match | ✓✓ &nbsp;✓✓ |
| qwen   | ✗ 404 at provider     | ✓ vendors.json match | ✗✗ → ✓✓ |
| glm    | ✗ 404 at provider     | ✓ vendors.json match | ✗✗ → ✓✓ |
| kimi   | ✗ 400 at provider     | ✓ vendors.json match | ✗✗ → ✓✓ |

### Task 2 — Research & write (`web_search ≥1` → `fs_write`)

| Model  | Passthrough           | Adapted                                   | Anchors (pt → ad) |
|--------|-----------------------|-------------------------------------------|---|
| claude | ✓ summary 2.7K, 5 links | ✓ summary 3.4K, 5 links | ✓✓ &nbsp;✓✓ |
| qwen   | ✗ 404 at provider     | ✓ summary 2.9K, 3 links                   | ✗✗ → ✓✓ |
| glm    | ✗ 404 at provider     | ✓ summary 3.9K, 3 links                   | ✗✗ → ✓✓ |
| kimi   | ✗ 400 at provider     | ✓ summary 2.7K, 2 links (4 tool errors)   | ✗✗ → ✓✓ |

### Task 3 — Full pipeline (`web_search` → `fs_write(csv)` → `codegen_run` → file at `count.txt`)

| Model  | Passthrough          | Adapted                            | Anchors (pt → ad) |
|--------|----------------------|------------------------------------|---|
| claude | ✗ final doesn't mention `4` | ✗ final doesn't mention `4`  | ✓✓✓✗ → ✗✓✓✗ |
| qwen   | ✗ 404 at provider    | ✗ final doesn't mention `4`        | ✗✗✗✗ → ✓✓✓✗ |
| glm    | ✗ 404 at provider    | ✓ full pipeline completed          | ✗✗✗✗ → ✓✓✓✗ |
| kimi   | ✗ 400 at provider    | ✗ final doesn't mention `4`        | ✗✗✗✗ → ✓✓✓✗ |

### What this actually measures

**7 of 9 failing-passthrough cells recovered** by the named adapter; 0 regressions. The aggregate portability tax is concentrated almost entirely at the wire boundary: smolagents' default `tool_choice="required"` is rejected by Kimi's thinking mode (400), Qwen's OpenRouter routing (404), and the GLM endpoint configuration (404). Each adapter's first move — flip `tool_choice` to `auto` and tune sampling — is enough to unblock Tasks 1 and 2 cleanly. The richer format-level / role-level / behavioral reshaping (`shape_response`, `reshape_messages`, `custom_role_conversions = {"tool": "observation"}`) is what the workshop stubs in `adapters/{qwen,glm,kimi}.py` invite you to add — none of it has fired yet on this dataset.

**Task 3 is a different failure.** Three of four adapted cells (claude, qwen, kimi) reach all four structural anchors but get rejected by the eval because their final assistant message doesn't contain the literal `"4"`. That's content correctness, not the portability tax — the loop is working, the wrong sentence got written. The 4th anchor `write_count` reads as `✗` on every cell because the codegen subprocess writes `count.txt` outside the tool surface; it's `required: false` in the spec for exactly this reason.

**claude/claude on Task 3 is the only cell that misses the first anchor.** Anchor verdict `✗✓✓✗` — Claude wrote the CSV from memory without searching first. Adapter didn't cause it; the model just doesn't need to look things up about its own ecosystem.

Reproduce any cell:
```bash
jq '.alignment.anchor_hits' results/task3-claude-claude.json
jq '.transcript[] | select(.role=="assistant") | .tool_calls[].signature' results/task3-claude-claude.json
jq .agent_error_detail results/task1-kimi-passthrough.json
```

---

## The thesis

Models are increasingly post-trained into specific harness assumptions. Qwen's tool-calling format, Claude's, Kimi's, GLM's — not interchangeable. The model expects a particular shape of context and emits a particular shape of output. The portability tax is what you pay when the harness doesn't match.

Whoever wraps that into a clean abstraction layer is doing useful work — `HKUDS/OpenHarness` is already trying, and v0.1.4 specifically added `reasoning_content` support for Moonshot/Kimi to fix the exact bug we expose on this repo. We're not building that abstraction tonight. We're measuring how big the gap is, and what shape the shim has to take.

## Why smolagents

Two reasons. First, it's small — the whole ToolCallingAgent loop is a few hundred lines, so you can read it during the event and know exactly what's running. Second, it's the kind of harness people actually reach for: 26k+ stars, HuggingFace-backed, vendor-neutral, MCP-aware. If we used a hand-rolled loop, "the generic harness" would be fictional. With smolagents, it's a real reference point.

Adapters here are smolagents-shaped: they declare `sampling`, `completion_overrides`, `custom_role_conversions`, and override `reshape_messages` / `shape_response`. See `adapters/base.py` for the surface, `adapters/claude.py` for a worked reference, and the three stubs (`qwen`, `glm`, `kimi`) for what's left to build.
