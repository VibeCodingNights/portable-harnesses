# Running your own LiteLLM proxy

The shared proxy at `https://proxy.vibecodingnights.com` is provisioned for the night. If you want to run your own (or run this repo after the event), here's how.

---

## Why a proxy

LiteLLM (used as a proxy server, not just the SDK) gives you:

- One OpenAI-compatible endpoint that fans out to Anthropic, DashScope, z.ai, and Moonshot.
- Per-key rate limiting and budget tracking.
- A single place where the API surface gets normalized — but **not** where context shape gets normalized. The shape is what your adapters fix.

---

## 1. Install

```bash
pip install 'litellm[proxy]'
```

## 2. Configure

The repo ships `harness/litellm_config.yaml`. The model entries:

```yaml
model_list:
  - model_name: claude
    litellm_params:
      model: anthropic/claude-opus-4-7
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: qwen
    litellm_params:
      model: openai/qwen3.6-max
      api_base: https://dashscope.aliyuncs.com/compatible-mode/v1
      api_key: os.environ/DASHSCOPE_API_KEY

  - model_name: glm
    litellm_params:
      model: openai/glm-5.1
      api_base: https://open.bigmodel.cn/api/paas/v4/
      api_key: os.environ/ZHIPUAI_API_KEY

  - model_name: kimi
    litellm_params:
      model: openai/kimi-k2-6
      api_base: https://api.moonshot.cn/v1
      api_key: os.environ/MOONSHOT_API_KEY
```

## 3. Set the four lab keys

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export DASHSCOPE_API_KEY=sk-...      # Alibaba console.dashscope.com
export ZHIPUAI_API_KEY=...           # open.bigmodel.cn
export MOONSHOT_API_KEY=sk-...       # platform.moonshot.cn
export PROXY_MASTER_KEY=sk-anything  # only used for the proxy admin endpoints
```

## 4. Start

```bash
litellm --config harness/litellm_config.yaml --port 4000
```

## 5. Point this repo at it

In `.env`:

```
PROXY_URL=http://localhost:4000
PROXY_TOKEN=sk-anything   # any string, the local proxy doesn't enforce
```

## 6. Per-attendee tokens (event mode)

The shared proxy uses the `database_url` setting in the config plus litellm's `/key/generate` endpoint to mint tokens with `max_budget`, `rpm`, and `tpm` limits per attendee. Skip this for personal use.

---

## Adding your own model

Drop another entry into `model_list`:

```yaml
  - model_name: my-model
    litellm_params:
      model: openai/whatever-the-vendor-calls-it
      api_base: https://your-vendor.example/v1
      api_key: os.environ/YOUR_VENDOR_KEY
```

Then add `my-model` to `MODELS` in `run.py`, and write `adapters/my_model.py` if it has post-training quirks worth shimming.
