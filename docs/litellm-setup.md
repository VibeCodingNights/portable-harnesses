# Bring your own model

The repo defaults to OpenRouter — one key fans out to all four labs. Three escape hatches if you want something else.

---

## 1. Add another OpenRouter slug

OpenRouter has ~300 models. To add one:

1. Find its slug at [openrouter.ai/models](https://openrouter.ai/models) (e.g. `deepseek/deepseek-v3.1`).
2. Add it to `harness/agent.py:MODEL_SLUGS`:
   ```python
   MODEL_SLUGS = {
       # ...existing entries...
       "deepseek": "deepseek/deepseek-v3.1",
   }
   ```
3. Add the short name to `MODELS` in `run.py` and `bench.sh`.
4. Optional: write `adapters/deepseek.py` if it has post-training quirks worth shimming.

That's it. No keys to add — OpenRouter routes everything through the one key you already have.

---

## 2. Skip OpenRouter, use direct lab keys

The portability tax is harshest when you hit each lab's native API directly — OpenRouter does some normalization that softens some quirks. To bypass OpenRouter and feel the full tax:

1. Grab keys: Anthropic (console.anthropic.com), DashScope (console.dashscope.com), Zhipu/z.ai (open.bigmodel.cn), Moonshot (platform.moonshot.cn). The Chinese labs need either a Chinese phone number or a business account — budget 1-2 weeks if you don't have either.

2. Set them in `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   DASHSCOPE_API_KEY=sk-...
   ZHIPUAI_API_KEY=...
   MOONSHOT_API_KEY=sk-...
   ```

3. Patch `harness/agent.py` to route per-model. The simplest version replaces the OpenRouter `completion()` call with a small switch:

   ```python
   LAB_CONFIGS = {
       "claude": {"model": "anthropic/claude-opus-4-7",
                  "api_key": os.environ["ANTHROPIC_API_KEY"]},
       "qwen":   {"model": "openai/qwen3.6-max",
                  "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                  "api_key": os.environ["DASHSCOPE_API_KEY"]},
       "glm":    {"model": "openai/glm-5.1",
                  "api_base": "https://open.bigmodel.cn/api/paas/v4/",
                  "api_key": os.environ["ZHIPUAI_API_KEY"]},
       "kimi":   {"model": "openai/kimi-k2-6",
                  "api_base": "https://api.moonshot.cn/v1",
                  "api_key": os.environ["MOONSHOT_API_KEY"]},
   }
   ```

   Then `completion(**LAB_CONFIGS[self.model], messages=..., tools=..., ...)`.

---

## 3. Run a local LiteLLM proxy (budget caps, per-user keys)

Useful if you're hosting an event or want centralized budget tracking. Adds a proxy layer in front of either OpenRouter or direct lab keys.

```bash
pip install 'litellm[proxy]'
```

Minimal config (`litellm_proxy.yaml`):

```yaml
model_list:
  - model_name: claude
    litellm_params:
      model: openrouter/anthropic/claude-opus-4.7
      api_key: os.environ/OPENROUTER_API_KEY
  - model_name: qwen
    litellm_params:
      model: openrouter/qwen/qwen3.6-max-preview
      api_key: os.environ/OPENROUTER_API_KEY
  - model_name: glm
    litellm_params:
      model: openrouter/z-ai/glm-5.1
      api_key: os.environ/OPENROUTER_API_KEY
  - model_name: kimi
    litellm_params:
      model: openrouter/moonshotai/kimi-k2.6
      api_key: os.environ/OPENROUTER_API_KEY

general_settings:
  master_key: sk-anything
```

Start it:

```bash
litellm --config litellm_proxy.yaml --port 4000
```

Then point `harness/agent.py` at it by changing the `completion()` call:

```python
response = completion(
    model=f"openai/{self.model}",   # short name; the proxy resolves it
    api_base="http://localhost:4000",
    api_key="sk-anything",
    ...
)
```

LiteLLM's [virtual keys docs](https://docs.litellm.ai/docs/proxy/virtual_keys) cover minting per-user tokens with `max_budget`, `rpm`, `tpm`.

---

## Why the layers exist

- **OpenRouter** normalizes the API surface (auth, model naming, billing) and provides one billing relationship instead of four.
- **LiteLLM** normalizes the SDK surface (same `completion()` call works against OpenAI, Anthropic, OpenRouter, Bedrock, ...).
- **Adapters** are what neither of those touch — the *content shape* of context and tool results, which each model was post-trained against. That's the portability tax. That's why this repo exists.
