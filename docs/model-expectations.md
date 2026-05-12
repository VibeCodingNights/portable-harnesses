# Model expectations

What each of the four models was post-trained against. Read the row for the model you're shimming. The TODOs in `adapters/<model>.py` reference this file directly.

---

## Claude (Anthropic, baseline)

| Aspect | Convention |
|---|---|
| Tool schema | OpenAI-style `{"type": "function", "function": {"name": ..., "parameters": ...}}` (OpenRouter translates this to Claude's native `input_schema` upstream). |
| Tool result role | `tool` with `tool_call_id` matching the call. |
| Strictness | **Every** assistant message with `tool_calls` must be followed by a `tool_result` for *every* call, in order, before the next assistant turn. Skip one and the API 400s. |
| Sampling | Temperature 0.2 for tool-heavy agentic loops (Anthropic's published guidance). |
| End-of-turn | `stop_reason: end_turn` when the model has nothing more to say; `tool_use` when emitting calls. Predictable. |
| Quirks | Won't accept `tool` messages without a preceding `tool_calls` in the same conversation. Won't tolerate stale `tool_call_id`s. |

---

## Qwen 3.6 (Alibaba DashScope)

| Aspect | Convention |
|---|---|
| Tool schema | Native: Qwen-Agent format with explicit `name_for_model`, `description_for_model`, `parameters` keys. The OpenAI translation usually works but loses some metadata (`name_for_human`, etc.). |
| Tool result role | Native: `<tool_response>...</tool_response>` blocks inside a `user` turn. OpenAI's `role: tool` works on DashScope's compat endpoint *but* edge cases (multi-line content, embedded JSON) sometimes get mangled by the chat template. |
| Tool call emission | Should be structured `tool_calls`. **Frequently** comes back as `<tool_call>...</tool_call>` text inside `content` instead — see bugs/qwen-jinja2-tool-templates.md. |
| Sampling | Temperature 0.7, top_p 0.8 (DashScope docs default for tool-using mode). |
| End-of-turn | `stop` after a complete answer. Mostly well-behaved. |
| Quirks | Jinja2 chat template (vLLM/llama.cpp) breaks on certain argument shapes; multi-arg calls with newlines in strings drop arguments. Multi-tool calls in a single turn are unreliable on llama.cpp; reliable on DashScope. |

**RL'd against:** Qwen-Agent harness with `<tool_call>` / `<tool_response>` text-tag protocol.

**Adapter level:** primarily format-level.

---

## GLM-5.1 (Zhipu BigModel / z.ai)

| Aspect | Convention |
|---|---|
| Tool schema | OpenAI-style accepted by z.ai's API. The model itself was trained on a flatter shape — try sending each tool def with `function` block hoisted to top level if discovery feels off. |
| Tool result role | **`observation`** is the native role inherited from ChatGLM. `tool` is accepted at the API surface but the model often acts as if no result was provided. |
| Tool call emission | Sometimes structured `tool_calls`, sometimes a fenced ```function code block in `content`. Be ready to parse either. |
| Sampling | Temperature 0.95, top_p 0.7 (z.ai docs default). High temperature is intentional — GLM tends toward determinism otherwise. |
| End-of-turn | `stop` is fine; no early termination issues. |
| Quirks | Looping on the same tool call is the dominant failure mode — see bugs/glm-observation-role.md. The fix is the role swap. |

**RL'd against:** ChatGLM's `observation`-role tool-result format, function calling embedded as code blocks.

**Adapter level:** primarily role-level.

---

## Kimi K2.6 (Moonshot)

| Aspect | Convention |
|---|---|
| Tool schema | OpenAI-style accepted on Moonshot's API. |
| Tool result role | `tool` accepted at API; semantically the model expects the result to feel like an *intermediate step*, not a turn closure. |
| Tool call emission | Structured `tool_calls`. Wire is well-behaved. |
| Sampling | **Temperature 0.6, top_p 1.0** (Moonshot docs, kimi-k2-6 quickstart). The model was RL'd at these settings — the termination predictor is calibrated to them. |
| End-of-turn | The dangerous one: `end_turn` fires *early* when the context shape doesn't match Moonshot's native agentic-loop scaffolding. See bugs/kimi-premature-termination.md. |
| Quirks | System prompt scaffolding matters. Continuation cues after each tool result drastically reduce premature termination. The OpenAI-shape default tool envelope reads as a closing turn to Kimi. |

**RL'd against:** Moonshot's native agentic loop with continuation scaffolding, intermediate-step framing for tool results.

**Adapter level:** behavioral. (Sometimes format-level too — wrapping the result in a `step_result/status:intermediate` envelope fights the same battle from a different direction.)

---

## Cross-cutting: what OpenRouter + smolagents translate, and what they don't

OpenRouter normalizes **the API surface** (one endpoint, one auth, one model namespace across labs). smolagents normalizes **the agent loop** (one `ToolCallingAgent.run()` regardless of model). Neither touches **the context shape inside the conversation** — and smolagents itself ships with defaults (`tool_choice="required"`, a specific system prompt structure) that *are* part of the harness assumption and will fail against models whose endpoints don't support them.

| Translated for you | Not translated (your job) |
|---|---|
| Top-level request envelope | System prompt scaffolding |
| Tool spec → native tool format | Tool result envelope (e.g., `<tool_response>` tags) |
| `tool_calls` → native call shape | Role labels (`tool` vs `observation`) |
| Streaming chunk normalization | Sampling parameters that match RL'd defaults |
| Authentication / routing | End-of-turn cue conventions |

The right column is the portability tax. Adapters live there.
