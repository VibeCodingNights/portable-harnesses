# [Cross-ref] mastra: o3-mini silently ignores the `format` property in JSON Schema

**Model:** o3-mini (not in our four-model lineup, but the *pattern* applies to several) &nbsp;·&nbsp; **Category:** format-level

---

## Why this is in the repo

This isn't one of tonight's four models, but it's the cleanest published example of the portability tax. Mastra (an agent framework) found that o3-mini silently ignored the `format` property in JSON schemas it sent. They added a schema-compat layer that strips/rewrites unsupported properties per-model. **Result: tool-call error rate dropped from ~15% to ~3%.**

That delta — 15% → 3%, from a single format-level shim — is the portability tax made legible. The number you're aiming to produce tonight in `bench.sh adapted` is the same kind of thing across our four models.

## What the bug looked like

Mastra sent JSON schemas like:

```json
{
  "type": "string",
  "format": "date-time"
}
```

o3-mini parsed `type: string` correctly and ignored `format` entirely. Tool calls came back with arbitrary strings where datetime-shaped strings were required. Validation against the schema failed.

## What the fix looked like

A schema-compat layer that, for o3-mini, transformed `format` properties into either:

- a `description` augmentation (`"description": "ISO 8601 datetime"`)
- or a `pattern` regex constraint, when the format had a regex equivalent

So the model received a schema it could actually act on.

## Why we care

This is the *taxonomy* you're producing tonight:

- **Format-level** (Mastra/o3-mini, Qwen Jinja2): the wire shape is wrong; the model never reads the right thing.
- **Role-level** (GLM): the wire is fine but the role label is off; the model reads it as the wrong kind of input.
- **Behavioral** (Kimi): everything is fine except the model thinks it's done.

A clean adapter framework names the level it operates at. If you write a Qwen shim that "fixes" the empty `tool_calls` problem, that's format-level work. If you write a Kimi shim that adjusts sampling, that's behavioral. The framework that doesn't exist yet is one that does all three behind a single interface.

## References

- mastra.ai blog: schema compat for o3-mini (search "mastra o3-mini format")
- mastra/mastra GitHub: `packages/core/src/llm/openai-compat-schema.ts` (path approximate)
