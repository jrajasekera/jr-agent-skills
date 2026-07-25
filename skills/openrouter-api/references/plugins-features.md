# Plugins, Structured Output, Reasoning, Caching, and Metadata

This reference covers cross-cutting OpenRouter features that are not tied to one model provider.

## Plugins vs server tools

Plugins transform a request/response once. Server tools are model-callable and may run zero or more times.

```json
{
  "plugins": [{ "id": "response-healing" }],
  "tools": [{ "type": "openrouter:web_search" }]
}
```

Do not wait for a plugin tool call or send a tool result for a plugin.

## Current plugin families

OpenRouter currently documents these plugin families:

| Plugin | ID / control | Purpose |
|---|---|---|
| Web search | `web` | Legacy one-shot grounding; deprecated in favor of `openrouter:web_search` |
| PDF/file parser | `file-parser` | Parse PDFs/files for models without suitable native file handling |
| Response healing | `response-healing` | Repair some malformed non-streaming JSON outputs |
| Pareto router | `pareto-router` | Configure the `openrouter/pareto-code` coding-quality router |
| Context compression | `transforms: ["middle-out"]` / plugin settings | Reduce prompts that exceed context limits |

The list and IDs can grow. Check the current plugin overview before using an unfamiliar configuration.

## Web search plugin (legacy)

```json
{
  "plugins": [
    {
      "id": "web",
      "max_results": 5
    }
  ]
}
```

The `:online` model suffix is a shortcut for the web plugin. It remains useful for a simple grounded response, but new agentic integrations should prefer:

```json
{
  "tools": [{ "type": "openrouter:web_search" }]
}
```

The server tool lets the model decide whether and how often to search and can return tool-level annotations/citations.

## PDF/file parser

A Chat Completions message can include a file part. Configure PDF parsing with:

```json
{
  "plugins": [
    {
      "id": "file-parser",
      "pdf": {
        "engine": "cloudflare-ai"
      }
    }
  ]
}
```

Current PDF engines include:

- `native` — pass to a model with native PDF handling;
- `mistral-ocr` — OCR for scanned/visual documents, billed separately;
- `cloudflare-ai` — text/Markdown extraction;
- `pdf-text` — deprecated compatibility name redirected to `cloudflare-ai`.

If no engine is set, OpenRouter can prefer native support and otherwise fall back to a parsing engine. Reuse returned file annotations on later turns where documented to avoid repeated parsing cost.

Treat extracted text as untrusted input and account for it in the context window.

## Response healing

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "result",
      "schema": {
        "type": "object",
        "properties": {
          "value": { "type": "string" }
        },
        "required": ["value"],
        "additionalProperties": false
      }
    }
  },
  "plugins": [{ "id": "response-healing" }]
}
```

Response healing can repair missing punctuation/brackets, Markdown wrappers, trailing commas, unquoted keys, and mixed prose/JSON in some cases.

Limitations:

- non-streaming only;
- requires JSON object/schema output;
- cannot reliably repair truncated output;
- does not make semantically invalid data valid;
- local schema validation remains mandatory.

## Pareto coding router plugin

The dynamic coding router uses:

```json
{
  "model": "openrouter/pareto-code",
  "plugins": [
    {
      "id": "pareto-router",
      "min_coding_score": 0.8
    }
  ],
  "session_id": "coding-session-id"
}
```

The shortlist and concrete model can change as benchmarks/models evolve. Always read the returned `model`. Use `session_id` to keep a multi-turn coding session on a consistent resolved model/provider where documented.

## Context compression and middle-out

```json
{
  "transforms": ["middle-out"]
}
```

Context compression can help a request fit, but it changes the prompt. For safety-critical tasks, deterministic retrieval, or exact transcript requirements, prefer explicit application-side truncation/summarization and log what was removed.

Disable account/default transforms for a request when preserving the exact prompt is more important than automatic recovery.

---

# Structured outputs

## JSON object mode

```json
{
  "response_format": { "type": "json_object" }
}
```

This asks for JSON but provides less structural assurance.

## Strict JSON Schema mode

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "weather",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "temperature": { "type": "number" },
          "conditions": { "type": "string" }
        },
        "required": ["temperature", "conditions"],
        "additionalProperties": false
      }
    }
  },
  "provider": {
    "require_parameters": true
  }
}
```

Use live `supported_parameters` to require `structured_outputs`. Keep schemas within the selected model/provider's supported JSON Schema subset.

Responses uses a different wrapper under `text.format`; see [responses-api.md](responses-api.md).

## Validation pattern

1. Validate the model response as JSON.
2. Validate against the same schema locally.
3. Reject additional properties unless intentionally allowed.
4. Enforce application-level rules that JSON Schema does not express.
5. Treat refusal/content-filter/error states separately from schema failure.
6. Do not blindly retry malformed output without changing model, limit, schema, or healing strategy.

---

# Unified reasoning

```json
{
  "reasoning": {
    "effort": "high",
    "exclude": false
  }
}
```

Use one primary allocation mechanism:

```json
{ "reasoning": { "effort": "medium" } }
```

or:

```json
{ "reasoning": { "max_tokens": 2000 } }
```

Additional controls:

- `enabled: true` — enable the model's default reasoning behavior;
- `exclude: true` — allow internal reasoning but omit returned reasoning content;
- `context: "auto" | "all_turns" | "current_turn"` — control which conversation turns receive reasoning context on models that advertise this feature;
- `mode: "standard" | "pro"` — select a supported reasoning mode independently of effort.

At this verification date, the current reasoning guide scopes `context` and `mode` to supported GPT-5.6-or-newer models. Treat that as a live capability, not a permanent family rule: inspect model metadata and the current schema before sending either field. With stateless Responses, preserving prior reasoning may additionally require replaying the relevant output items or requesting the documented include fields.

Current gateway effort names include `max`, `xhigh`, `high`, `medium`, `low`, `minimal`, and `none`. Model metadata can expose `supported_efforts`, `default_effort`, `default_enabled`, `supports_max_tokens`, and `mandatory`. Use that metadata to build controls.

Provider mappings differ. Some models ignore token budgets, some map them to discrete effort, some reject sampling controls during reasoning, and some cannot disable reasoning. Do not infer behavior from the provider family alone.

Reasoning tokens are output tokens for billing. Some models do not reveal their internal reasoning even though usage reports reasoning tokens.

## Preserving reasoning

For tool continuations, prefer the complete `reasoning_details` array. It can contain normalized types such as text, summary, or encrypted data with format/signature fields. Preserve it verbatim and in order.

The legacy `include_reasoning` field remains a compatibility mechanism, but new code should use `reasoning`. The legacy `:thinking` suffix is not supported for current Anthropic models.

---

# Prompt caching (provider-side)

Prompt caching reduces the cost/latency of repeatedly processing a stable prefix at a provider endpoint.

Many providers cache automatically. Others support explicit breakpoints:

```json
{
  "messages": [
    {
      "role": "system",
      "content": [
        { "type": "text", "text": "Stable instructions and reference data..." },
        {
          "type": "text",
          "text": "Large reusable document...",
          "cache_control": { "type": "ephemeral", "ttl": "1h" }
        }
      ]
    },
    { "role": "user", "content": "Dynamic question" }
  ]
}
```

Provider/model rules, minimum token thresholds, TTLs, write multipliers, and read discounts change. Query live prices and read current prompt-caching docs rather than copying constants.

## Sticky routing

OpenRouter attempts to keep cached conversations on the same provider endpoint. Set a stable session key for agent workflows:

```json
{ "session_id": "run-123" }
```

or:

```http
x-session-id: run-123
```

A manual `provider.order` overrides stickiness. Inspect:

```json
{
  "usage": {
    "prompt_tokens_details": {
      "cached_tokens": 1000,
      "cache_write_tokens": 0
    }
  }
}
```

A non-zero `cached_tokens` confirms a provider prompt-cache read.

---

# Response caching (OpenRouter edge)

Response caching is beta and replays an identical successful response before contacting a provider.

## Enable per request

```http
X-OpenRouter-Cache: true
X-OpenRouter-Cache-TTL: 300
```

Force a refresh of that exact cache key:

```http
X-OpenRouter-Cache-Clear: true
```

Current TTL range is 1–86400 seconds, with a 300-second default. Recheck the docs while the feature is beta.

## Supported endpoints

Current support:

- `/api/v1/chat/completions`;
- `/api/v1/responses`;
- `/api/v1/messages`;
- `/api/v1/embeddings`.

It does not currently cover legacy completions, TTS, STT, rerank, image/video generation, or other specialized endpoints unless the docs later say otherwise.

## Cache key

The cache key includes:

- API key;
- model;
- endpoint type;
- streaming mode;
- normalized request body.

JSON property order is significant. Omitting a default field and explicitly sending it produce different keys. Attribution headers are not part of the key.

## Response headers

```http
X-OpenRouter-Cache-Status: HIT | MISS
X-OpenRouter-Cache-Age: <seconds>       # HIT
X-OpenRouter-Cache-TTL: <seconds>
```

On a hit:

- billable usage counters are zero;
- the request does not consume provider rate limits;
- OpenRouter returns a new generation ID;
- router metadata is omitted;
- streaming content is replayed as a stream.

Only successful `200` responses are cached. Concurrent identical misses are not coalesced and can both be billed.

## ZDR limitation

Response caching is disabled when account-level ZDR is enforced because it requires temporary response storage. Per-request `provider.zdr` does not by itself make an otherwise eligible request ineligible; account/guardrail policy is the controlling limitation documented by OpenRouter.

---

# Router metadata

Enable routing diagnostics:

```http
X-OpenRouter-Metadata: enabled
```

Successful and eligible error responses can include an additive `openrouter_metadata` object describing requested/resolved routing, endpoint candidates, attempts, region, BYOK state, and pipeline stages such as guardrails, plugins, server tools, response healing, or context compression.

Rules:

- decode unknown fields and stage types permissively;
- do not build authorization logic from optional debug metadata;
- cache hits omit metadata intentionally;
- the legacy `X-OpenRouter-Experimental-Metadata` header is accepted for compatibility, but new code should use `X-OpenRouter-Metadata`.

---

# Service tiers

Request:

```json
{ "service_tier": "flex" }
```

Current request values include `flex` and `priority` for selected models/providers. Billing follows the actual served tier.

Response placement:

- Chat Completions/Responses: top-level `service_tier` (`default`, `flex`, `priority`, or `null`);
- Messages: `usage.service_tier`, with `standard` as the base label.

Do not assume availability or discounts. Inspect live endpoint metadata and response tier.

---

# Presets

OpenRouter presets can store reusable request/routing/plugin/cache configuration and can expose endpoint variants such as preset-backed Chat, Responses, or Messages requests. Preset schemas and administrative APIs change more quickly than core inference.

Use presets when centrally managed configuration is desirable, but:

- version and review them like code;
- log the designated preset version;
- keep request-level overrides explicit;
- understand cache-precedence rules;
- inspect the current OpenAPI before automating creation/update.

## Common mistakes

- Treating prompt-cache reads as free response-cache hits.
- Enabling response caching for a request expected to be fresh/random.
- Assuming logical JSON equivalence produces the same response-cache key.
- Using response healing with streaming.
- Relying on a moving router without recording the resolved model.
- Exposing returned reasoning/details to logs or users without policy review.
- Parsing router metadata with a closed enum that breaks on a new stage type.
