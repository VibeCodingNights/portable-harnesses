# Known bugs (compiled)

A reading list. Each entry links to a per-bug writeup in `bugs/` and to the source repos / issues in the wild that catalog the same failure.

---

## Qwen — Jinja2 chat template breaks tool calling

- **Local writeup:** `bugs/qwen-jinja2-tool-templates.md`
- **Category:** format-level
- **Symptoms:** structured `tool_calls` empty; tool calls appear as text inside `<tool_call>` tags within `content`. Multi-arg calls with newlines drop arguments entirely.
- **Source repos that exist solely to fix this:**
  - allanchan339/chat-template-qwen3
  - froggeric/qwen-tool-template-fix
- **vLLM tracker:** open issues searching "qwen tool calling chat template"
- **Affects:** Qwen 3.6 served via vLLM, llama.cpp, and other Jinja2-template-driven runners. DashScope's hosted endpoint is mostly fine.

## GLM — `observation` role mismatch

- **Local writeup:** `bugs/glm-observation-role.md`
- **Category:** role-level
- **Symptoms:** model loops on the same tool call because it never registers the previous result. Eval shows `loops > 0`.
- **Origin:** ChatGLM's published chat format uses `role: observation` for tool results. GLM-5.1 inherits this RL trace. The OpenAI-compat layer at z.ai accepts `role: tool` but the weights weren't trained to attend to it the same way.
- **Reference:** THUDM/ChatGLM3 README, z.ai function-calling docs.

## Kimi — premature `end_turn` on non-native harnesses

- **Local writeup:** `bugs/kimi-premature-termination.md`
- **Category:** behavioral
- **Symptoms:** model issues one tool call, gets the result, summarizes, stops. Multi-step tasks fail with `early_termination: true`.
- **Reported in the wild:** anomalyco/opencode#13807 (Kimi on Bedrock), Moonshot Discord threads on AWS deployments.
- **Root cause:** Moonshot's RL'd termination predictor is calibrated to native scaffolding (sampling + system prompt + tool-result framing). Generic OpenAI-style harnesses miss all three.

## Mastra — schema-compat layer for `format` property

- **Local writeup:** `bugs/mastra-format-property.md`
- **Category:** format-level (cross-reference; not one of tonight's four models)
- **Result:** tool-call error rate dropped from ~15% to ~3% by stripping/rewriting the `format` JSON Schema property for o3-mini.
- **Why it's here:** clearest published example of the portability tax measured as a single number. The bench you'll run tonight is the same kind of measurement, across our four models.

---

## How these connect

Three categories. Three failure modes. Three different shapes of fix.

| Bug | Model | Category | What you reshape |
|---|---|---|---|
| Jinja2 template | Qwen | format-level | Parse `<tool_call>` text out of `content` back into structured `tool_calls`; wrap results in `<tool_response>`. |
| observation role | GLM | role-level | Send tool results as `role: observation`; or as `role: user` with `[observation:tool_name]` prefix. |
| premature end_turn | Kimi | behavioral | Match RL'd sampling (0.6/1.0); inject continuation cues; frame results as intermediate. |
| format property | o3-mini | format-level | Rewrite unsupported JSON Schema properties into `description`/`pattern`. |

If you find a new bug not listed here, file it under `bugs/` using `TEMPLATE.md`. That's a contribution.
