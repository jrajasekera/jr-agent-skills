---
name: openrouter-api
description: Build, migrate, debug, and operate integrations with the OpenRouter API. Covers live model and provider discovery, Chat Completions, the stateless Responses API, the Anthropic-compatible Messages API, official SDKs, routing and fallbacks, reasoning, structured outputs, client and server tools, streaming, multimodal inputs, image/audio/video generation, embeddings, reranking, caching, OAuth, administration, observability, privacy, and production error handling. Use whenever code calls openrouter.ai, a user asks which OpenRouter endpoint/model/provider to use, or an existing OpenRouter integration may be stale.
---

# OpenRouter API

Last verified against OpenRouter's public documentation, OpenAPI specification, changelog, and official skill repository: **2026-07-25**.

OpenRouter exposes several interoperable API “skins” plus specialized media, retrieval, and administration endpoints under one base URL:

```text
https://openrouter.ai/api/v1
```

The endpoint surface is relatively stable, but the **model catalog, aliases, providers, capabilities, accepted parameters, prices, rate limits, service tiers, and beta features change frequently**.

## Non-negotiable operating rules

1. **Discover live metadata; do not guess.** Never invent a model ID, provider slug, voice, price, context limit, media dimension, duration, supported parameter, or rate limit. Query the catalog and, for beta or unfamiliar endpoints, inspect the current OpenAPI schema.
2. **Use a concrete model ID for reproducibility.** Use a `~author/family-latest` alias or a router only when automatic upgrades are an intentional product decision. Record the concrete `model` returned by OpenRouter.
3. **Match capabilities before sending the request.** Inspect `architecture.input_modalities`, `architecture.output_modalities`, `supported_parameters`, model-level reasoning metadata, and provider endpoint metadata.
4. **Choose the API skin deliberately.** Chat Completions, Responses, and Messages use different request, response, streaming, tool, and error shapes. Do not mix fields between them casually.
5. **Treat Responses, server tools, response caching, dedicated media APIs, and other marked features as evolving.** Check the changelog and OpenAPI before shipping generated types or durable abstractions.
6. **Distinguish three extension mechanisms:** user-defined function tools are executed by the caller; OpenRouter server tools can run zero or more times during a request; plugins transform a request or response once.
7. **Distinguish prompt caching from response caching.** Provider prompt caches reduce repeated input processing. OpenRouter response caching can replay an identical completed response from the edge.
8. **Preserve continuation state exactly.** When continuing a conversation, round-trip `reasoning_details` unchanged and in the original order. Never synthesize, edit, or reorder encrypted/signed reasoning blocks. Preserve and resend assistant `phase` metadata (`commentary` or `final_answer`) whenever the response supplies it.
9. **Parse streams as SSE, not newline-delimited JSON.** Buffer partial frames, ignore comments, recognize `[DONE]`, and handle in-band errors after HTTP status `200`.
10. **Keep credentials out of clients, logs, prompts, screenshots, and repositories.** A management key is more privileged than an inference key and must remain server-side. Use OAuth PKCE only when the product intentionally lets users authorize their own OpenRouter key.
11. **Do not retry permanent failures unchanged.** Retry only transient failures with bounded exponential backoff and jitter, honoring `Retry-After`. Once a stream has emitted content, provider fallback cannot safely restart it.
12. **Log identifiers and routing facts, not sensitive payloads.** Capture `X-Generation-Id`, the response `id`, resolved model/provider, typed `error_type`, cache status, service tier, and optional router metadata.

## Start every task with this decision flow

### 1. Choose the API surface

| Need | Endpoint or package | Notes |
|---|---|---|
| General text, reasoning, structured output, tools, multimodal input | `POST /chat/completions` | Broadest OpenAI-compatible surface |
| OpenAI Responses-compatible typed items and server tools | `POST /responses` | Beta and **stateless**; send the full required history |
| Anthropic Messages-compatible clients and payloads | `POST /messages` | Anthropic-shaped messages, thinking, tools, and streaming |
| Legacy text completion | `POST /completions` | Use only for an existing compatibility requirement |
| Text or multimodal embeddings | `POST /embeddings` | Discover with `GET /embeddings/models` or the filtered general catalog |
| Rank documents against a query | `POST /rerank` | Documents may be strings or supported structured inputs |
| Generate or edit an image | `POST /images` | Dedicated Image API; discover per-model controls first |
| Text-to-speech | `POST /audio/speech` | Returns raw audio bytes, not JSON on success |
| Speech-to-text | `POST /audio/transcriptions` | JSON/base64 or OpenAI-style multipart body |
| Generate video | `POST /videos` then poll | Asynchronous submit, poll, and download workflow |
| Upload, list, inspect, or delete reusable files | `GET/POST /files`, `/files/{file_id}*` | Multipart upload; workspace-scoped IDs and cursor pagination |
| Browse text/embedding/general models | `GET /models` | Public catalog with filters, prices, modalities, and parameters |
| Inspect one model | `GET /model/{author}/{slug}` | Singular `model` path |
| Inspect serving endpoints for a model | `GET /models/{author}/{slug}/endpoints` | Provider performance, pricing, capabilities, and status |
| Inspect image or video capabilities | `/images/models*`, `/videos/models*` | Dedicated model metadata for media controls |
| Direct, type-safe API access | `@openrouter/sdk`, `openrouter`, Go SDK | Thin clients generated from OpenAPI |
| Managed agent loop and caller tools | `@openrouter/agent` | TypeScript agent primitives and stop conditions |
| User-authorized API key | OAuth PKCE | No client secret; validate the pending PKCE callback/session and store keys securely |
| Keys, guardrails, workspaces, analytics | Management APIs | Require a management/provisioning key where documented |

### 2. Discover the current model and endpoint capabilities

Use the included dependency-free helper:

```bash
# Browse and filter models
python scripts/discover_models.py --query coding --output-modality text
python scripts/discover_models.py --parameter tools --parameter structured_outputs
python scripts/discover_models.py --output-modality embeddings --json

# Inspect a concrete model and its provider endpoints
python scripts/discover_models.py --model 'author/model-slug' --json
python scripts/discover_models.py --endpoints 'author/model-slug' --json

# Inspect dedicated media catalogs
python scripts/discover_models.py --image-endpoints 'author/image-model' --json
python scripts/discover_models.py --video-models --json
```

The catalog endpoint is also directly callable:

```bash
curl -sS 'https://openrouter.ai/api/v1/models?output_modalities=text' \
  -H 'Accept: application/json'
```

Before selecting a model, inspect at least:

- exact `id`, `canonical_slug`, `expiration_date`, and returned alias resolution;
- `context_length` and `top_provider.max_completion_tokens`;
- `architecture.input_modalities` and `architecture.output_modalities`;
- `supported_parameters`, especially `tools`, `structured_outputs`, `reasoning`, and search-related parameters;
- model-level `reasoning` metadata such as supported efforts, default state, and whether reasoning is mandatory;
- `pricing` fields, remembering token prices are normally per token as decimal strings, and `pricing.overrides` for long-context or UTC-window pricing exceptions;
- endpoint status, latency/throughput percentiles, quantization, data policy, service tier, and accepted parameters.

For a recently added or beta endpoint, inspect the live schema:

```bash
python scripts/inspect_openapi.py --search responses
python scripts/inspect_openapi.py --path /responses
python scripts/inspect_openapi.py --schema ResponsesRequest
```

See [references/routing-providers.md](references/routing-providers.md) and [references/api-endpoints.md](references/api-endpoints.md).

### 3. Validate the request against the selected model

Do not assume that a provider silently ignores unsupported parameters. Prefer one of these approaches:

- omit optional fields the selected model does not advertise;
- set `provider.require_parameters: true` so routing only considers endpoints that support every supplied parameter;
- explicitly constrain `provider.only`, `provider.ignore`, or `provider.order` using current provider slugs;
- supply a compatible `models` fallback list rather than falling back to models with incompatible modalities or tools.

### 4. Select a stable or adaptive routing strategy

- **Pinned concrete ID:** evaluations, regression tests, reproducible production behavior.
- **Latest alias (`~author/family-latest`):** automatic upgrades within a known model family.
- **Multiple `models`:** explicit ordered model fallback.
- **Provider preferences:** control cost, latency, throughput, data policy, service tier, or provider.
- **OpenRouter router:** task-aware or specialized model selection; always read the returned concrete model.

Do not hardcode the current members or defaults of a router. See [references/routing-providers.md](references/routing-providers.md).

## Authentication and app attribution

Required for authenticated endpoints:

```http
Authorization: Bearer $OPENROUTER_API_KEY
Content-Type: application/json
```

Optional attribution headers:

```http
HTTP-Referer: https://your-app.example
X-OpenRouter-Title: Your App Name
X-OpenRouter-Categories: cli-agent,programming-app
```

`X-OpenRouter-Title` is the preferred title header. The older `X-Title` name remains a compatibility alias but should not be used in new integrations.

## Minimal REST request

Require the caller to choose a live model rather than embedding a dated example:

```bash
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY}"
: "${OPENROUTER_MODEL:?Set OPENROUTER_MODEL to an ID from /models}"

curl -sS https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'X-OpenRouter-Metadata: enabled' \
  -d "$(jq -n --arg model "$OPENROUTER_MODEL" '{
    model: $model,
    messages: [{role: "user", content: "Explain optimistic concurrency control."}]
  }')"
```

## Official client SDK quick starts

### TypeScript

```typescript
import { OpenRouter } from "@openrouter/sdk";

const model = process.env.OPENROUTER_MODEL;
if (!model) throw new Error("Set OPENROUTER_MODEL from the live /models catalog");

const client = new OpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY ?? "",
  httpReferer: "https://your-app.example",
  appTitle: "Your App",
});

const response = await client.chat.send({
  model,
  messages: [{ role: "user", content: "Hello from OpenRouter" }],
});

console.log(response.choices[0]?.message.content);
console.log("Resolved model:", response.model);
```

### Python

```python
import os
from openrouter import OpenRouter

model = os.environ["OPENROUTER_MODEL"]

with OpenRouter(
    api_key=os.environ["OPENROUTER_API_KEY"],
    http_referer="https://your-app.example",
    x_open_router_title="Your App",
) as client:
    response = client.chat.send(
        model=model,
        messages=[{"role": "user", "content": "Hello from OpenRouter"}],
    )

print(response.choices[0].message.content)
print("Resolved model:", response.model)
```

The official client SDKs mirror the REST API. Use `@openrouter/agent` when a TypeScript application wants OpenRouter to manage a multi-turn caller-tool loop. Use OpenAI or Anthropic SDK compatibility when migrating an existing codebase, but place OpenRouter-only fields in the SDK's extension mechanism (`extra_body`, extra headers, or equivalent). See [references/sdk-integration.md](references/sdk-integration.md).

## Core request patterns

### Structured output

Require live support for `structured_outputs`, route only to compatible endpoints, and still validate the returned value locally:

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "answer",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "answer": { "type": "string" },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
        },
        "required": ["answer", "confidence"],
        "additionalProperties": false
      }
    }
  },
  "provider": { "require_parameters": true }
}
```

### Reasoning

Use the unified top-level `reasoning` object. Supply either `effort` or `max_tokens`, not both, unless the current model metadata explicitly documents a combined behavior:

```json
{
  "reasoning": {
    "effort": "high",
    "exclude": false
  }
}
```

Accepted efforts and whether reasoning can be disabled are model-specific. Prefer the model's live `reasoning` metadata. The legacy `:thinking` suffix is not a portable replacement and is no longer supported for Anthropic models.

### Tools

- Caller function: `{ "type": "function", "function": { ... } }`; the application executes it.
- Server tool: `{ "type": "openrouter:web_search" }`; OpenRouter operates it during the request.
- Plugin: `{ "id": "response-healing" }`; OpenRouter transforms the request or response once.

See [references/tool-calling.md](references/tool-calling.md) and [references/plugins-features.md](references/plugins-features.md).

### Routing and fallback

```json
{
  "model": "author/primary-model",
  "models": [
    "other-author/compatible-fallback"
  ],
  "provider": {
    "allow_fallbacks": true,
    "require_parameters": true,
    "sort": "throughput",
    "data_collection": "deny",
    "zdr": true
  }
}
```

Use placeholder IDs only in templates. Replace them with live IDs and verify that every fallback supports the request's modalities and parameters.

### Caching

Provider prompt caching and OpenRouter response caching can be used together but solve different problems:

```http
X-OpenRouter-Cache: true
X-OpenRouter-Cache-TTL: 300
```

Response caching is beta, is keyed by the exact normalized request (including JSON property order), and currently supports Chat Completions, Responses, Messages, and Embeddings. It is unavailable when account-level ZDR is enforced. See [references/plugins-features.md](references/plugins-features.md).

## Production response and error policy

| Condition | Default action |
|---|---|
| `400` / invalid request | Correct the schema, model, modality, or unsupported parameter; do not retry unchanged |
| `401` | Fix or rotate credentials; do not retry unchanged |
| `402` | Restore credits or key limits; do not retry unchanged |
| `403` | Check guardrails, moderation, permissions, management-key requirements, provider policy, or region |
| `408` / timeout | Retry only if the operation is idempotent; use bounded backoff |
| `429` | Honor `Retry-After`; back off with jitter; consider a compatible fallback |
| `502` / provider failure | Retry through allowed fallbacks before content starts; otherwise surface partial output plus error |
| `503` / no capacity | Honor `Retry-After`; use bounded backoff or another compatible model/provider |
| Mid-stream error with HTTP `200` | Stop parsing normal output, preserve partial content separately, classify by typed `error_type` |

The canonical `error_type` location differs by API skin:

- Chat Completions: `error.metadata.error_type`;
- Messages: `error.error_type`;
- Responses: top-level `error_type` on a failed response/event.

Never rely only on HTTP status to classify provider failures. See [references/streaming.md](references/streaming.md).

## Production observability checklist

For every request, capture where available:

- your own correlation/trace ID and a privacy-safe end-user identifier;
- response `id` and `X-Generation-Id`;
- requested model and resolved concrete `model`;
- provider, service tier, finish reason, latency, usage, and cost;
- `prompt_tokens_details.cached_tokens` and cache-write fields;
- `X-OpenRouter-Cache-Status` when response caching is enabled;
- stable `error_type`, retry headers, and fallback attempt count;
- optional `openrouter_metadata` by sending `X-OpenRouter-Metadata: enabled`.

Decode `openrouter_metadata` permissively because new pipeline stage types may be added. Cache hits intentionally omit router metadata because replayed metadata could be stale.

## Reference map

Read only the reference relevant to the task:

- [chat-completions.md](references/chat-completions.md) — Chat Completions, Anthropic Messages, request and response shapes
- [responses-api.md](references/responses-api.md) — stateless Responses API, typed items, tools, and streaming
- [routing-providers.md](references/routing-providers.md) — aliases, variants, endpoint selection, fallbacks, routers, privacy
- [tool-calling.md](references/tool-calling.md) — caller functions, server tools, safe agent loops
- [streaming.md](references/streaming.md) — robust SSE parsing, cancellation, usage, and in-band errors
- [plugins-features.md](references/plugins-features.md) — plugins, structured output, reasoning, prompt/response caching, metadata
- [multimodal-media.md](references/multimodal-media.md) — images, files/PDFs, audio, speech, and asynchronous video
- [embeddings-rerank.md](references/embeddings-rerank.md) — embedding and reranking workflows
- [sdk-integration.md](references/sdk-integration.md) — official SDKs, OpenAI/Anthropic compatibility, migration guidance
- [auth-admin-observability.md](references/auth-admin-observability.md) — API keys, OAuth, management APIs, guardrails, workspaces, analytics
- [api-endpoints.md](references/api-endpoints.md) — endpoint inventory and discovery rules
- [source-map.md](references/source-map.md) — authoritative documentation used for this update

## Completion criteria for an OpenRouter integration task

Before declaring the task complete:

1. The exact model, provider, endpoint, and optional parameters were verified live.
2. Every requested modality and feature is supported by all permitted fallback routes.
3. Secrets are loaded from a secure runtime source and never logged.
4. Non-streaming and streaming error paths are both covered.
5. Tool loops have iteration, cost, timeout, and output-size bounds.
6. Retry behavior distinguishes permanent errors from transient ones.
7. The resolved model/provider, usage, generation ID, and cache behavior are observable.
8. Beta features are isolated behind a compatibility boundary or feature flag.
9. Tests do not depend on an unpinned moving alias unless upgrade behavior is the test subject.
10. The implementation links to the current OpenAPI/changelog rather than copying a permanent model catalog.
