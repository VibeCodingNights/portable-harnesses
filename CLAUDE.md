# Vibe Coding Nights — Repo Builder

You are building the event repo for a Vibe Coding Night.

## Event Theme
portable harnessing across heterogeneous models The Chinese labs are each shipping a model with an implicit harness — Bailing's tied to Ant's payment rails, Kimi's tied to its search and coding agent, Qwen's tied to Aliyun's enterprise stack, Stepfun's open platform is itself a harness assumption. Tuesday's frame is "which agentic stack wins." The interesting question OpenClaw can ask at right angles to that: what does a harness look like when no single lab owns it? Not "Claude vs Qwen vs Kimi" but Qwen-and-Kimi-and-Claude inside the same shell, on the same task, with the same memory and tool surface. The labs are all post-training their models into harnesses now — RL'd against specific tool patterns, specific context formats. So a model isn't a model anymore, it's a model+expected-harness pair. The new kernel is harness portability as a first-class concept: where does the model's pre-baked harness assumption end and yours begin, and how cleanly can you swap. That's not in Tuesday's lineup. It's the natural complement.
Thesis: Cost arbitrage. Different models are priced differently per token, and most agent runs have steps with wildly different difficulty — a routing decision is not the same workload as a hard reasoning step. Route the cheap parts to the cheap model. This is real but it's table stakes; LiteLLM and OpenRouter already do it and it's not a conceptual frontier.
Capability arbitrage. Qwen is genuinely better at Chinese, Kimi has a particular feel for long-context Chinese-language synthesis, Claude has its own strengths on code and instruction-following, GLM is good at certain agentic patterns. A harness that picks per-subtask could in principle outperform any single model. But this requires an oracle that knows which model is best for which subtask, and that oracle is itself a hard problem. The naive version usually loses to "just use the best model for everything."
Adversarial cross-checking. One model proposes, another critiques, with non-overlapping training data and failure modes. There's some real signal here — different models hallucinate differently, and disagreement is a useful flag. But this is a debate-style technique, not really a harness-portability claim.
None of those, actually. Walking through it, the real reason most multi-model harnesses exist is operational — vendor risk, geographic compliance (Chinese deployment needs a Chinese model in the loop), or capability gaps that close as models converge. None of these are deep statements about agency.
So what was I actually pointing at, if anything?
I think the genuine kernel was simpler and I dressed it up. The genuine kernel is: models are increasingly post-trained into specific harness assumptions, and that's a real concept. Qwen's tool-calling format, Claude's, Kimi's, are not interchangeable; the model expects a particular shape of context and emits a particular shape of output. Whoever wraps that into a clean abstraction layer is doing useful work, regardless of whether anyone runs the models simultaneously.
The "all three in one shell" framing was me reaching for something that sounded like a research direction when the real observation is more pedestrian: post-training has made models harness-specific, and harness-specificity is now a portability tax.

## Event Description
You swapped the model and everything broke. Not the API call — the API call worked fine. The model just stopped finishing tasks.

This is the part nobody warns you about. Every model shipped in 2026 was post-trained against a specific harness. Qwen 3.6 was RL'd against particular tool schemas. Kimi K2.6 was optimized at specific sampling settings inside a specific agentic loop. Claude expects every tool_call to have a matching tool result. These aren't preferences. They're baked into the weights.

LiteLLM translates the API surface. OpenRouter normalizes the routing. MCP standardizes what tools exist. None of them touch the middle — the context window itself, where a model trained for one shape of input silently degrades when you hand it another.

The bug trackers tell the real story. Entire repos exist just to fix Qwen's Jinja2 chat templates breaking tool calling in vLLM. Kimi on Bedrock emits premature end_turn signals because the harness and the model disagree about what a completed tool call looks like. Mastra had to build a dedicated schema-compat layer because o3-mini silently ignores the `format` property in JSON schemas.

The portability tax is real and nobody's built the abstraction layer for it yet.

Tuesday we're measuring it directly. One agentic task — file manipulation, web search, code generation. One fixed MCP tool surface. Three models through the same harness. Then three models through harness adapters that reshape context to match each model's post-training expectations. The delta between those two runs is the tax. The adapter code is the beginning of the layer that doesn't exist.

Bring a laptop. Pick a model. Break it against someone else's harness. Then write the shim.

vibecodingnights.com

## Event Flow (includes repo structure plan)
# Vibe Coding Night: Portability Tax
**Theme:** Portable harnessing across heterogeneous models
**Date:** Tuesday | **Time:** 6:00–10:00 PM | **Location:** Frontier Tower, SF
**Repo:** `github.com/VibeCodingNights/portable-harnesses`

---

## 0:00–0:15 (6:00–6:15) — Arrival

People arrive, open laptops, connect to wifi. A single card on each table:

> **wifi:** [network/password]
> **repo:** `github.com/VibeCodingNights/portable-harnesses`
> **models:** get an OpenRouter key at `openrouter.ai/keys`, add ~$10 credit
> **start:** `git clone → cd portable-harnesses → ./setup.sh`

`setup.sh` installs dependencies, writes `.env` from the template, and (once they've pasted their OpenRouter key) health-checks all four models (Claude Opus 4.7, Qwen 3.6 Max, GLM-5.1, Kimi K2.6) through OpenRouter. Four green checkmarks means you're ready.

No announcements during this window. Hosts help anyone whose setup script fails.

---

## 0:15–0:20 (6:15–6:20) — Intro (5 minutes, hard stop)

Script for the host — say this, then stop:

> "Every model shipped this year was post-trained against a specific harness. Qwen expects one tool-calling format. GLM expects `observation` where everyone else expects `tool`. Kimi terminates early when the context shape doesn't match its training. Claude requires every tool_call to have a matching tool result. They all speak 'function calling.' None of them speak it the same way.
>
> Tonight you're measuring the gap. The repo wraps smolagents' ToolCallingAgent — a real, popular, vendor-neutral agent loop — and points it at four models through OpenRouter. Run a task through one model. Swap to another — same harness, same tools, same task. Watch what breaks. Then write the adapter that fixes it.
>
> Three targets on the wall. Pick one. Go."

Point to the three targets written on a whiteboard or wall-mounted screen:

```
TARGET 1: BREAK IT     — Swap models, document what breaks
TARGET 2: SHIM IT      — Write an adapter that reshapes context per-model
TARGET 3: MEASURE IT   — Score the before/after delta
```

Walk away. Build time starts.

---

## 0:20–3:30 (6:20–9:30) — Build Time

### The Targets

**TARGET 1: BREAK IT** (entry-level, any experience)

Run the same agentic task through multiple models on the same unmodified harness. Document exactly where and how each model fails. The repo has three tasks of escalating complexity:

- **Task 1 — File Transform:** Read a markdown file, extract structured data, write a JSON file. Single tool, single step. Tests basic tool-calling format compatibility.
- **Task 2 — Research & Write:** Search the web for recent information on a topic, synthesize findings, save a document. Multi-tool, multi-step. Tests tool-call sequencing and result handling.
- **Task 3 — Full Pipeline:** Research a topic → create a data file → generate analysis code → execute it. Tests complex multi-step agentic behavior with chained tool dependencies.

What you're looking for — each model fails differently:
- **Qwen** may emit malformed tool-call JSON (Jinja2 template issue in vLLM/llama.cpp — documented in allanchan339 and froggeric's fix repos)
- **GLM** may silently ignore tool results because it expects them as `observation` role, not `tool` role (ChatGLM heritage)
- **Kimi** may issue premature `end_turn` and stop before completing all steps — the model thinks it's done because the context shape signals completion based on its RL training, even though the harness hasn't received all outputs
- **Claude** is the baseline — it should pass on the unmodified harness

The repo's `bugs/` directory has a `TEMPLATE.md`. Each documented bug is a contribution.

**TARGET 2: SHIM IT** (intermediate, requires reading model docs)

The repo's `adapters/` directory has a base interface and a `passthrough.py` adapter (no-op — sends context as-is). Write an adapter for a specific model that reshapes context to match that model's post-training expectations.

An adapter can do any of:
- Reformat tool definitions to match the model's expected schema shape
- Reshape tool results into the format the model was trained to parse (GLM's `observation` convention, Qwen's `<tool_response>` tags)
- Inject model-specific system prompt conventions
- Adjust sampling parameters the model was RL'd at (Kimi's temperature/top_p sensitivity)
- Fix JSON schema properties the model ignores (Mastra's `format` property fix for o3-mini reduced errors from 15% to 3%)

`adapters/claude.py` is complete as a reference implementation. `adapters/qwen.py`, `adapters/glm.py`, and `adapters/kimi.py` are stubs with comments pointing to the specific post-training conventions documented in `docs/model-expectations.md`.

**TARGET 3: MEASURE IT** (advanced, requires completing Targets 1 or 2 first)

Run the scoring harness: `./bench.sh naive` runs all three tasks through all four models with the passthrough adapter. `./bench.sh adapted` runs them with whatever adapters exist. The output is a comparison table:

```
Task | Model      | Adapter     | Completed | Tool Calls | Errors | Loops
  1  | Claude     | passthrough | ✓         | 3          | 0      | 0
  1  | Qwen 3.6   | passthrough | ✗         | 2          | 1      | 0
  1  | Qwen 3.6   | qwen-shim   | ✓         | 3          | 0      | 0
  1  | GLM-5.1    | passthrough | ✗         | 3          | 0      | 1
  1  | GLM-5.1    | glm-shim    | ✓         | 3          | 0      | 0
  1  | Kimi K2.6  | passthrough | ✗         | 1          | 0      | 0
  1  | Kimi K2.6  | kimi-shim   | ✓         | 3          | 0      | 0
```

The delta between the passthrough and adapted columns is the portability tax, measured. Four models × three tasks = twelve data points. If your adapter moved a model from ✗ to ✓, that's a demo-worthy result.

---

### Entry Paths

**Beginner (first builder night, or unfamiliar with agentic frameworks):**
1. Clone the repo, run `setup.sh`
2. Open `tasks/01-file-transform.md` — read what the task asks
3. Run `python run.py --task 1 --model claude` — watch it succeed (Claude is the baseline)
4. Run `python run.py --task 1 --model qwen` — watch what happens
5. Run `python run.py --task 1 --model glm` — different failure. What changed?
6. Run `python run.py --task 1 --model kimi` — different again. Kimi may just stop early
7. Read the output diffs. Open `bugs/TEMPLATE.md`, fill one in per failure
8. Move to Task 2 when Task 1 stops being interesting
9. If you want to try fixing a bug: open `adapters/qwen.py`, read the comments, try a fix

The beginner path is Target 1 throughout. Every documented bug is a real contribution — these bugs are poorly catalogued and the community repos that fix them have real users.

**Advanced (has built agents, knows the model APIs):**
1. Clone the repo, run `setup.sh`, skim the `adapters/` directory
2. Read `docs/model-expectations.md` — the documented post-training conventions for each model
3. Pick a model. Read its stub adapter. Write the real one
4. Test it: `python run.py --task 2 --model kimi --adapter kimi` vs `python run.py --task 2 --model kimi --adapter passthrough`
5. Run `./bench.sh adapted` to get the full comparison table
6. If your adapter works: what specifically did you reshape? Format-level (Qwen), role-level (GLM), or behavioral (Kimi)? That taxonomy is the deliverable

The advanced path is Targets 2→3. Writing an adapter that moves a model from failing to passing on Task 2 or 3 is a strong demo.

---

### What "Done" Looks Like (3 hours)

**Beginner done:** You've run the same task through 3+ models, documented at least one format-coupling bug with specific evidence (the exact tool call that failed, what the model emitted vs. what the harness expected), and can explain what "post-training coupling" means from what you directly observed. Your bug report is in a PR or in the `bugs/` directory.

**Advanced done:** You've written a context adapter for at least one model, run a multi-step task with and without the adapter, and have a before/after comparison showing the completion rate delta. Your adapter code is in a PR. You can name the failure category — format-level, role-level, or behavioral — and say why.

**Ambitious done:** You've written adapters for 2+ models and the scoring table shows the aggregate portability tax across all four models. The 12-cell table (4 models × 3 tasks) with passthrough vs. adapted scores. This is the number nobody has published.

---

### Resources Available During Build Time

**Provided by attendees (~5 min, at the door):**
- One OpenRouter account + key from `openrouter.ai/keys`, ~$10 credit. One key fans out to all four labs — no Anthropic / DashScope / Zhipu / Moonshot accounts needed
- Optional: a free Brave Search key (`brave.com/search/api/`, 2000 queries/month free tier) for Tasks 2 & 3. Without it, `web_search` returns stubs and Task 1 still works fine

**Pre-provisioned by organizers:**
- Wall-mounted display showing the live scoring table (auto-refreshes from `results/`)
- Spare OpenRouter credit codes / pre-funded backup keys in a sealed envelope, for attendees who blow their budget or can't sign up
- The three tools (filesystem, web search, code execution) run in-process from `harness/tools.py` — no infrastructure

**In the repo:**
- `docs/model-expectations.md` — what each model was RL'd against: tool schema format, system prompt conventions, tool result handling, sampling parameters, known quirks. Covers all four models
- `docs/known-bugs.md` — the Qwen Jinja2 template issue, GLM observation-role mismatch, Kimi end_turn behavior, Mastra `format` property fix, with links to source repos
- `adapters/claude.py` — complete reference adapter showing the pattern
- `tasks/eval.py` — scoring function: checks task output against expected results

**On the tables (printed or QR codes):**
- Qwen 3.6 tool-calling docs + chat template spec
- GLM-5.1 API reference (z.ai/docs) + function calling format
- Kimi K2.6 quickstart (platform.kimi.ai/docs/guide/kimi-k2-6-quickstart)
- smolagents ToolCallingAgent reference (`smolagents/agents.py`) + OpenAIModel reference (`smolagents/models.py`)

---

### Host Behavior During Build Time

Hosts float. No announcements, no check-ins, no schedule. When someone is stuck:

- **"Setup doesn't work"** → Common causes: (1) no OpenRouter credit — send them to `openrouter.ai/credits`; (2) key typo'd into `.env`; (3) `OPENROUTER_API_KEY` still has the `...` placeholder. Re-run `./setup.sh` after fixing
- **"The model just fails and I don't know why"** → Point them to verbose output: `python run.py --task 1 --model qwen --verbose`. The verbose flag shows the exact messages sent and received. The failure is in the diff between what was sent and what the model expected
- **"The model just stops"** → Probably Kimi. Show them the verbose output where `end_turn` fires early. The model thinks it's done. That's the behavioral-level tax
- **"I wrote an adapter but it doesn't help"** → Look at `docs/model-expectations.md` together. Which convention did they miss? For GLM it's usually tool result format. For Kimi it's usually sampling parameters or system prompt shape
- **"This is too easy"** → Move them to Task 3 or suggest writing an adapter for a model nobody else has picked. Or: "What would an adapter look like that auto-detects the model's expectations from its output?"

---

## 3:30–4:00 (9:30–10:00) — Opt-in Demos

Pull up the scoring table on the wall display. Anyone who wants to share gets 2-3 minutes. Natural demo categories:

- **"I found this bug"** — show the exact tool call that broke, what the model emitted, what it should have emitted. 60 seconds
- **"I wrote this adapter"** — show the before/after on the scoring table. What did you reshape? 2 minutes
- **"Here's the number"** — if anyone ran the full benchmark across all four models, show the aggregate portability tax. 3 minutes

No pressure. No queue. Host asks "Anyone want to show what they built or what broke?" and waits. If nobody volunteers, point to the scoring table and narrate the aggregate results.

---

## Pre-Event Setup (Organizer Checklist)

**1 week before:**
- [ ] Mint one OpenRouter key with $50–100 of credit as the org backup pool (for attendees who can't sign up at the door). Save it on a USB stick / in a 1Password vault — do NOT print it
- [ ] Verify the four OpenRouter slugs in `harness/agent.py:MODEL_SLUGS` still resolve (`anthropic/claude-opus-4.7`, `qwen/qwen3.6-max-preview`, `z-ai/glm-5.1`, `moonshotai/kimi-k2.6`). OpenRouter rotates IDs occasionally
- [ ] Run all three tasks through Claude baseline — verify they pass with the passthrough adapter
- [ ] Run all three tasks through Qwen, GLM, and Kimi with passthrough adapter — verify they fail in documented ways. Qwen should hit format errors. GLM should loop or ignore results. Kimi should terminate early. If any model passes with passthrough, the task isn't testing portability — fix the task
- [ ] Print table cards (wifi, repo URL, OpenRouter signup URL, suggested $10 credit)
- [ ] Print reference cards (model docs QR codes for all four models)

**Day of:**
- [ ] Confirm OpenRouter is up — ping `openrouter.ai/api/v1/models` and verify the four slugs are listed
- [ ] Write the three targets on the whiteboard
- [ ] Set up wall display with auto-refreshing scoring table
- [ ] Test `setup.sh` on a clean machine (no cached deps, fresh OpenRouter key)

---

## Event Repo Structure

```
VibeCodingNights/portable-harnesses/
│
├── README.md                           # Theme, quick start, targets
├── .env.example                        # OPENROUTER_API_KEY template (+ optional BRAVE_API_KEY)
├── setup.sh                            # Install deps, validate OpenRouter key, health-check 4 models
├── run.py                              # Main entry: --task, --model, --adapter, --verbose
├── bench.sh                            # Run all tasks × all models × all adapters, output table
│
├── harness/                            # Thin facade over smolagents.ToolCallingAgent
│   ├── agent.py                        # Agent + RouterModel + MODEL_SLUGS + LAB_PROVIDERS
│   └── tools.py                        # Five @tool-decorated functions (fs_read/write/list, web_search, codegen_run)
│
├── tools/                              # Reference MCP server implementations (not used by default;
│   ├── filesystem-server/              # the harness uses in-process tools.py. Kept as the
│   │   ├── package.json                # "this is the production shape" reference for attendees
│   │   └── index.ts                    # who want to expose tools to Claude Desktop / other MCP hosts.
│   ├── search-server/
│   │   ├── package.json
│   │   └── index.ts
│   └── codegen-server/
│       ├── package.json
│       └── index.ts
│
├── tasks/                              # The agentic tasks (test cases)
│   ├── 01-file-transform.md            # Read markdown → extract → write JSON
│   ├── 02-research-and-write.md        # Search → synthesize → save document
│   ├── 03-full-pipeline.md             # Search → file → code → execute
│   ├── inputs/
│   │   └── sample-data.md
│   ├── expected/
│   │   ├── 01-expected.json
│   │   ├── 02-expected.md
│   │   └── 03-expected.json
│   └── eval.py                         # Scoring: compare actual vs expected
│
├── adapters/                           # Context reshaping per model ← ATTENDEES WORK HERE
│   ├── base.py                         # Adapter interface (reshape_tools, reshape_result, etc.)
│   ├── passthrough.py                  # No-op adapter (naive baseline)
│   ├── claude.py                       # Complete reference implementation
│   ├── qwen.py                         # Stub — format-level reshaping
│   ├── glm.py                          # Stub — role-level reshaping
│   ├── kimi.py                         # Stub — behavioral-level reshaping
│   └── README.md                       # How to write an adapter, what to reshape
│
├── bugs/                               # Format-coupling bug reports ← ATTENDEES WORK HERE
│   ├── TEMPLATE.md                     # Bug report template
│   ├── qwen-jinja2-tool-templates.md   # Pre-documented: vLLM chat template issue
│   ├── glm-observation-role.md         # Pre-documented: tool result role mismatch
│   ├── kimi-premature-termination.md   # Pre-documented: end_turn on non-native harnesses
│   └── mastra-format-property.md       # Pre-documented: schema-compat fix (cross-reference)
│
├── results/                            # Run outputs ← GENERATED BY BENCH
│   ├── .gitkeep
│   └── example-run.json                # Sample output showing the format
│
└── docs/
    ├── model-expectations.md           # Post-training conventions: all 4 models
    ├── known-bugs.md                   # Compiled format-coupling bugs with source links
    ├── litellm-setup.md                # Bring your own model: add a slug, use direct lab keys, run a local proxy
    └── writing-adapters.md             # Guide: format-level vs role-level vs behavioral
```

**What attendees touch:** `adapters/qwen.py`, `adapters/glm.py`, `adapters/kimi.py` (writing adapters), `bugs/` (documenting failures), `results/` (generated by their runs). Everything else is pre-built infrastructure they use but don't modify.

---

## Self-Evaluation

1. **Does the flow reference specific challenges from the research?** Yes — Qwen Jinja2 template bugs (allanchan339/froggeric repos), GLM observation-role mismatch (ChatGLM heritage), Kimi K2.6 premature end_turn (anomalyco/opencode#13807), Mastra format property fix (15%→3%). Four models with three distinct failure categories (format-level, role-level, behavioral).

2. **Could someone run this without the organizer?** Yes — intro is scripted, targets are on the wall, the repo has `setup.sh` and `run.py` with flags, host behavior is documented including Kimi-specific troubleshooting, pre-event checklist covers all four API endpoints. A co-host who reads this document could run the night.

3. **Are both paths concrete enough to follow?** Beginner path is 9 numbered steps from clone to bug report, now running through 4 models instead of 3 to observe three different failure categories. Advanced path is 6 steps from clone to scored adapter PR. Both reference specific files and exact commands. The adapter taxonomy (format/role/behavioral) gives advanced attendees a framework for what they're observing.

---

## Existing Repos in github.com/VibeCodingNights
- **superhero-skill** — VCN #31 event package — Claude Code / OpenClaw skill + slides + persona template for superhero.com agents on æternity
- **vcn-32-slides** — VCN #32 — Trading agents on superhero.com (event deck)
- **auto-vcn** — 
- **reverse-engineering** — Your LLM can decompile a function. It cannot understand a binary.
- **metaprompting** — Configuration is solved. Taste isn't. Build the metaprompting loop nobody has built — Gemma 4 watches your aesthetic choices and writes the taste directives that shape the next session.
- **bob** — Finds hackathons. Enters them. Wins.
- **agent-teams** — Think in teams, not prompts.
- **agent-orchestration** — The coordination problems are fifty years old. The frameworks are new.
- **agent-harnesses** — The pattern isn't about code — it's about closing loops
- **information-primitives** — Exercises, primitives, and provocations for exploring how we structure and interact with information
- **design-interaction** — Design & Interaction
- **offensive-security** — AI Security Workshop: Prompt injection, memory poisoning, and MCP tool attacks

## Instructions
- **Name the repo** to match the org convention above (simple kebab-case topic
  names like `agent-harnesses`, `offensive-security`, `design-interaction`).
- Create the directory structure from the flow plan.
- Write the README in the event voice (short, direct, provocative).
- Challenge files should have clear instructions. Starter templates should be minimal and runnable.
- When ready, create the repo on GitHub: `gh repo create VibeCodingNights/{name} --public`
- Stage everything and commit: `git add -A && git commit -m "scaffold: portable harnessing across heterogeneous models The Chinese labs are each shipping a model with an implicit harness — Bailing's tied to Ant's payment rails, Kimi's tied to its search and coding agent, Qwen's tied to Aliyun's enterprise stack, Stepfun's open platform is itself a harness assumption. Tuesday's frame is "which agentic stack wins." The interesting question OpenClaw can ask at right angles to that: what does a harness look like when no single lab owns it? Not "Claude vs Qwen vs Kimi" but Qwen-and-Kimi-and-Claude inside the same shell, on the same task, with the same memory and tool surface. The labs are all post-training their models into harnesses now — RL'd against specific tool patterns, specific context formats. So a model isn't a model anymore, it's a model+expected-harness pair. The new kernel is harness portability as a first-class concept: where does the model's pre-baked harness assumption end and yours begin, and how cleanly can you swap. That's not in Tuesday's lineup. It's the natural complement."`
- Push: `git push -u origin main`
