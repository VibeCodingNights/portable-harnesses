# Portable Harnesses

You swapped the model and everything broke. Not the API call — the API call worked fine. The model just stopped finishing tasks.

Every model shipped this year was post-trained against a specific harness. Qwen 3.6 was RL'd against particular tool schemas. Kimi K2.6 was optimized at specific sampling settings inside a specific agentic loop. Claude expects every `tool_call` to have a matching tool result. GLM-5.1 expects tool results as `observation`, not `tool`. These aren't preferences. They're baked into the weights.

OpenRouter normalizes the API surface. [smolagents](https://github.com/huggingface/smolagents)'s `ToolCallingAgent` is our reference harness — small enough to read in an afternoon, vendor-neutral, MCP-aware. Neither touches the middle: the context window itself, where a model trained for one shape of input silently degrades when you hand it another.

Tonight: one harness, three tasks, four models. Measure what breaks. Write the shim.

---

## Quick start

```bash
git clone https://github.com/vibecodingnights/portable-harnessing
cd portable-harnessing
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

## The thesis

Models are increasingly post-trained into specific harness assumptions. Qwen's tool-calling format, Claude's, Kimi's, GLM's — not interchangeable. The model expects a particular shape of context and emits a particular shape of output. The portability tax is what you pay when the harness doesn't match.

Whoever wraps that into a clean abstraction layer is doing useful work — `HKUDS/OpenHarness` is already trying, and v0.1.4 specifically added `reasoning_content` support for Moonshot/Kimi to fix the exact bug we expose on this repo. We're not building that abstraction tonight. We're measuring how big the gap is, and what shape the shim has to take.

## Why smolagents

Two reasons. First, it's small — the whole ToolCallingAgent loop is a few hundred lines, so you can read it during the event and know exactly what's running. Second, it's the kind of harness people actually reach for: 26k+ stars, HuggingFace-backed, vendor-neutral, MCP-aware. If we used a hand-rolled loop, "the generic harness" would be fictional. With smolagents, it's a real reference point.

Adapters here are smolagents-shaped: they declare `sampling`, `completion_overrides`, `custom_role_conversions`, and override `reshape_messages` / `shape_response`. See `adapters/base.py` for the surface, `adapters/claude.py` for a worked reference, and the three stubs (`qwen`, `glm`, `kimi`) for what's left to build.
