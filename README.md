# Portability Tax

You swapped the model and everything broke. Not the API call — the API call worked fine. The model just stopped finishing tasks.

Every model shipped this year was post-trained against a specific harness. Qwen 3.6 was RL'd against particular tool schemas. Kimi K2.6 was optimized at specific sampling settings inside a specific agentic loop. Claude expects every `tool_call` to have a matching tool result. GLM-5.1 expects tool results as `observation`, not `tool`. These aren't preferences. They're baked into the weights.

LiteLLM translates the API surface. OpenRouter normalizes the routing. MCP standardizes what tools exist. None of them touch the middle — the context window itself, where a model trained for one shape of input silently degrades when you hand it another.

Tonight: one harness, three tasks, four models. Measure what breaks. Write the shim.

---

## Quick start

```bash
git clone https://github.com/vibecodingnights/portable-harnesses
cd portable-harnesses
./setup.sh
```

`setup.sh` installs deps, verifies proxy connectivity, and health-checks the four models. Four green checkmarks means you're ready.

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
| `harness/` | The agent loop, model-agnostic | No |
| `tools/` | Three MCP tool servers (filesystem, search, codegen) | No |
| `tasks/` | Three agentic tasks + scoring | No |
| `adapters/` | Context reshaping per model | **Yes** |
| `bugs/` | Format-coupling bug reports | **Yes** |
| `results/` | Run outputs | Generated |
| `docs/` | Model expectations, known bugs, adapter guide | Read |

---

## The four models

| Model | Provider | Lab | Post-training quirk |
|---|---|---|---|
| `claude` | Anthropic | Anthropic | Strict: every `tool_call` needs a matching `tool_result`. Baseline. |
| `qwen` | DashScope | Alibaba | Format-level: Jinja2 chat template, `<tool_response>` tags. |
| `glm` | z.ai (Zhipu) | Zhipu | Role-level: tool results expected as `observation`, not `tool`. |
| `kimi` | Moonshot | Moonshot | Behavioral: premature `end_turn` when context shape doesn't match RL training. |

All four are reachable via the shared LiteLLM proxy at `https://proxy.vibecodingnights.com`. No individual API keys needed. Per-attendee tokens, ~$5 budget.

---

## The thesis

Models are increasingly post-trained into specific harness assumptions. Qwen's tool-calling format, Claude's, Kimi's, GLM's — not interchangeable. The model expects a particular shape of context and emits a particular shape of output. The portability tax is what you pay when the harness doesn't match.

Whoever wraps that into a clean abstraction layer is doing useful work. We're not building that tonight. We're measuring how big the gap is.
