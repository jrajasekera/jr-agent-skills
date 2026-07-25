---
name: venice-ai-api
description: Build, migrate, and debug integrations with the Venice.ai API. Covers OpenAI-compatible chat and Responses, live model discovery and routing, multimodal and file inputs, reasoning, tools, web/X search, image generation and editing, audio, video, embeddings, augment APIs, characters, API-key administration, billing, x402/SIWX wallet authentication, and crypto RPC. Use whenever code calls api.venice.ai, a user asks which Venice model or endpoint to use, or an existing Venice integration may be stale.
---

# Venice.ai API

Last verified against Venice's public documentation, OpenAPI-derived skills, and model-lifecycle guidance: **2026-07-24**.

Venice exposes an OpenAI-compatible API plus native endpoints for images, asynchronous media, document parsing, search, account administration, wallet payments, and crypto RPC. The API surface is stable under `/api/v1`, but the **model catalog, capabilities, constraints, pricing, rate limits, and deprecations change frequently**.

## Non-negotiable operating rules

1. **Do not guess model IDs, prices, voices, dimensions, durations, context limits, or rate limits.** Query the live discovery endpoints before generating production code or making recommendations.
2. **Match the request to the selected model's metadata.** Inspect `model_spec.capabilities`, `model_spec.constraints`, `model_spec.pricing`, `privacy`, `offline`, `beta`, `regionRestrictions`, and `deprecation`.
3. **Use traits for automatic upgrades; use fixed IDs for reproducibility.** Resolve traits with `/models/traits`; never assume what a trait currently points to.
4. **Use `queue_id`, not legacy `queueid`,** for asynchronous audio and video requests.
5. **Quote asynchronous media before queueing it.** For music and video: `quote -> queue -> retrieve -> complete`.
6. **Treat Alpha, Beta, Preview, and experimental endpoints as unstable.** Validate the current OpenAPI schema before shipping or pinning generated types.
7. **Never expose credentials or wallet private keys.** Do not place API keys in browser bundles, logs, prompts, screenshots, or checked-in files.
8. **Do not retry validation, authentication, entitlement, or media-type errors unchanged.** Retry only transient failures, honoring `Retry-After` and rate-limit headers.

## Base URL and authentication

```text
https://api.venice.ai/api/v1
```

Choose one authentication mode per request:

| Mode | Header | Typical use |
|---|---|---|
| Bearer API key | `Authorization: Bearer $VENICE_API_KEY` | Servers, scoped inference keys, account billing, usage analytics |
| x402 / SIWX wallet | `SIGN-IN-WITH-X: <base64 SIWX payload>` | Accountless pay-per-request flows using prepaid USDC credit on Base or Solana |

Prefer Bearer authentication unless the product explicitly needs wallet-native billing. Current endpoint contracts prefer `SIGN-IN-WITH-X`; the legacy `X-Sign-In-With-X` name remains accepted during migration. For x402, use Venice's supported client or an x402 SDK rather than hand-rolling signatures. See [references/auth-admin-billing.md](references/auth-admin-billing.md).

## Start every task with this decision flow

### 1. Choose the API surface

| Need | Endpoint or workflow |
|---|---|
| General text, reasoning, tools, multimodal, files | `POST /chat/completions` |
| OpenAI Responses-style typed output | `POST /responses` — Alpha; verify access and current schema |
| Text embeddings | `POST /embeddings` |
| Text-to-image with native controls | `POST /image/generate` |
| OpenAI-compatible image generation | `POST /images/generations` |
| Single-image edit | `POST /image/edit` |
| Compose/edit multiple images | `POST /image/multi-edit` |
| Upscale/enhance image | `POST /image/upscale` |
| Remove image background | `POST /image/background-remove` |
| List image styles | `GET /image/styles` |
| Short text-to-speech | `POST /audio/speech` |
| Create a temporary cloned-voice handle | `POST /audio/voices` |
| Audio-file transcription | `POST /audio/transcriptions` |
| Music or long-form async audio | `/audio/quote`, `/audio/queue`, `/audio/retrieve`, `/audio/complete` |
| Video generation/upscale | `/video/quote`, `/video/queue`, `/video/retrieve`, `/video/complete` |
| Public video/YouTube transcription | `POST /video/transcriptions` |
| Extract text from a document | `POST /augment/text-parser` |
| Scrape a public URL to Markdown | `POST /augment/scrape` |
| Structured web search | `POST /augment/search` |
| Browse model catalog | `GET /models` |
| Resolve recommended aliases | `GET /models/traits` |
| Resolve compatibility aliases | `GET /models/compatibility_mapping` |
| Browse public characters | `GET /characters*` |
| Manage API keys and inspect limits | `/api_keys*` |
| Inspect account balance, cursor usage history, and analytics | `/billing/balance`, `/billing/usage-history`, `/billing/usage-analytics` |
| Inspect/top up wallet credits | `/x402/*` |
| Proxy blockchain JSON-RPC | `/crypto/rpc/*` |

### 2. Discover a current model

```bash
curl -sS "https://api.venice.ai/api/v1/models?type=text" \
  -H "Authorization: Bearer $VENICE_API_KEY"

curl -sS "https://api.venice.ai/api/v1/models/traits?type=text" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Valid discovery types currently include:

```text
text, image, inpaint, upscale, video, music, tts, asr, embedding, all
```

For coding models, query `type=text` and filter `model_spec.capabilities.optimizedForCode`, or resolve the `default_code` trait when present. The catalog can add types or fields; treat the OpenAPI document and live response as authoritative.

Use the included helper for a compact, filtered view:

```bash
python scripts/discover_models.py --type text
python scripts/discover_models.py --type text --capability supportsFunctionCalling
python scripts/discover_models.py --type text --capability optimizedForCode --privacy private --json
python scripts/discover_models.py --type image --show-traits
```

See [references/models-and-routing.md](references/models-and-routing.md).

### 3. Validate the request against `model_spec`

For text models, check at least:

- `availableContextTokens` and `maxCompletionTokens`
- `privacy`, `offline`, `beta`, `regionRestrictions`, `deprecation`
- `supportsFunctionCalling`, `supportsReasoning`, `supportsReasoningEffort`
- `supportsResponseSchema`, `supportsVision`, `supportsMultipleImages`, `maxImages`
- `supportsAudioInput`, `supportsVideoInput`, `supportsWebSearch`, `supportsXSearch`
- `supportsTeeAttestation`, `supportsE2EE`, `optimizedForCode`

For media models, also validate prompt limits, aspect ratios, resolutions, durations, dimensions, step ranges, voices, reference-image counts, and model-specific feature flags.

### 4. Pick a stable or adaptive model reference

- Use a **fixed model ID** when output stability, evaluations, regression tests, or reproducibility matter.
- Use a **trait** such as `default`, `fastest`, `default_code`, `default_vision`, `default_reasoning`, or `most_intelligent` when automatic upgrades are desirable.
- Resolve the trait once at startup and cache the mapping briefly. Do not cache the entire catalog for days.
- Monitor `model_spec.deprecation` and model-deprecation response headers.

## OpenAI SDK quick start

### Python

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["VENICE_API_KEY"],
    base_url="https://api.venice.ai/api/v1",
)

response = client.chat.completions.create(
    model="default",
    messages=[
        {"role": "system", "content": "Answer accurately and concisely."},
        {"role": "user", "content": "Explain zero-knowledge proofs."},
    ],
    max_completion_tokens=800,
    extra_body={
        "venice_parameters": {
            "include_venice_system_prompt": False,
        }
    },
)

print(response.choices[0].message.content)
```

### TypeScript

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.VENICE_API_KEY,
  baseURL: "https://api.venice.ai/api/v1",
});

const response = await client.chat.completions.create({
  model: "default",
  messages: [{ role: "user", content: "Explain zero-knowledge proofs." }],
  max_completion_tokens: 800,
  // Venice extension; cast only if the SDK type does not yet include it.
  venice_parameters: { include_venice_system_prompt: false },
} as OpenAI.Chat.Completions.ChatCompletionCreateParamsNonStreaming & {
  venice_parameters: { include_venice_system_prompt: boolean };
});

console.log(response.choices[0]?.message.content);
```

OpenAI-compatible surfaces include chat completions, embeddings, image generations, TTS, transcription, and model listing. Native Venice endpoints generally require direct HTTP calls.

## Chat-specific extensions

Pass Venice-only features in `venice_parameters`:

| Parameter | Purpose |
|---|---|
| `include_venice_system_prompt` | Include or suppress Venice's default system prompt |
| `enable_web_search` | `off`, `auto`, or `on` |
| `enable_web_scraping` | Scrape public URLs found in the latest user message |
| `enable_web_citations` | Ask the model to mark web sources in its answer |
| `include_search_results_in_stream` | Emit search-result metadata in a stream |
| `return_search_results_as_documents` | Surface search results as a synthetic tool call |
| `enable_x_search` | Native web + X search on supporting xAI models |
| `character_slug` | Apply a published Venice character |
| `strip_thinking_response` | Remove legacy visible thinking blocks |
| `disable_thinking` | Disable reasoning on models that support doing so |
| `enable_e2ee` | Enable E2EE behavior when the selected model and request headers support it |

For current reasoning-capable models, prefer top-level `reasoning: {"enabled": false}` when reasoning must be disabled; `reasoning.effort: "none"` and `venice_parameters.disable_thinking` remain model-dependent.

When the client cannot add `venice_parameters`, supported options may be encoded as a model suffix:

```text
default:enable_web_search=on&enable_web_citations=true&include_venice_system_prompt=false
```

Do not encode `enable_e2ee` or `enable_x_search` as suffixes unless the current docs explicitly add support.

See [references/chat-completions.md](references/chat-completions.md).

## Multimodal and file inputs

`messages[].content` can be an array of typed parts on compatible models:

- `text`
- `image_url`
- `input_audio` — inline base64, not an audio URL
- `video_url`
- `file` — public URL or base64 data URL; Venice extracts text before inference

A file block uses:

```json
{
  "type": "file",
  "file": {
    "file_data": "data:application/pdf;base64,...",
    "filename": "report.pdf"
  }
}
```

Files are request-scoped, and extracted text counts against the model context window. For reusable extraction or token counting, use `/augment/text-parser` instead.

## Function calling and agent loops

Before sending tools, require `supportsFunctionCalling`. Then:

1. Send `tools` and `tool_choice` with the conversation.
2. Execute every returned `tool_call`; `parallel_tool_calls` may yield several at once.
3. Append the assistant tool-call message unchanged.
4. Append one `role: "tool"` message per result using the matching `tool_call_id`.
5. Call the model again for the final response.
6. On providers that return opaque `reasoning_details`, round-trip that field verbatim in later turns. Never fabricate or normalize it.

For schema-constrained output, require `supportsResponseSchema` and prefer `response_format.type = "json_schema"` over legacy `json_object`.

## Asynchronous audio and video invariant

Use the same model ID and `queue_id` throughout the job:

```text
POST /{audio|video}/quote
POST /{audio|video}/queue       -> queue_id, sometimes download_url
POST /{audio|video}/retrieve    -> JSON status or binary media
POST /{audio|video}/complete    -> finalize and delete Venice-hosted media
```

- Poll at a reasonable interval; do not busy-loop.
- `/retrieve` may return binary media directly, or a JSON `COMPLETED` state that requires downloading a temporary `download_url` returned by `/queue`.
- `delete_media_on_completion: true` can combine retrieval and cleanup where supported.
- Download before calling `/complete`.

See [references/audio-api.md](references/audio-api.md) and [references/video-api.md](references/video-api.md).

## Production error policy

| Status | Default action |
|---|---|
| `400` | Fix schema, model, or constraints; do not retry unchanged |
| `401` | Fix or rotate credentials; do not retry unchanged |
| `402` | Bearer: top up account; x402: follow structured wallet top-up flow |
| `403` | Check key type, beta/Pro entitlement, region, or wallet ownership |
| `404` | Re-resolve model/character/queue ID; check expiration |
| `413` | Reduce payload size |
| `415` | Correct `Content-Type` or multipart body |
| `422` | Treat by endpoint: policy rejection or upstream validation; inspect body |
| `429` | Honor `Retry-After` and rate-limit reset headers; back off with jitter |
| `500`, `503`, `504` | Bounded exponential backoff; consider a compatible fallback model |

Log a client correlation ID plus any `X-Request-ID`, `CF-RAY`, model-deprecation warning, balance, and rate-limit headers returned. Never log prompts, uploaded files, raw media, API keys, SIWE payloads, or wallet signatures unless the product's explicit privacy policy permits it.

See [references/production.md](references/production.md).

## Reference map

- [references/models-and-routing.md](references/models-and-routing.md) — live catalog, traits, capabilities, privacy, pricing, deprecation, routing
- [references/chat-completions.md](references/chat-completions.md) — chat, Responses Alpha, multimodal/files, tools, reasoning, search, caching, characters
- [references/image-api.md](references/image-api.md) — generation, OpenAI compatibility, style references, edit, multi-edit, upscale, background removal
- [references/audio-api.md](references/audio-api.md) — TTS, transcription, async music/long audio
- [references/video-api.md](references/video-api.md) — quote/queue/retrieve/complete, reference media, transcription
- [references/platform-api.md](references/platform-api.md) — embeddings, augment tools, characters, crypto RPC
- [references/auth-admin-billing.md](references/auth-admin-billing.md) — Bearer, x402, API keys, limits, billing, usage
- [references/production.md](references/production.md) — errors, retries, streaming, observability, testing
- [references/official-sources.md](references/official-sources.md) — authoritative Venice resources used to maintain this skill

## Before declaring an integration complete

- [ ] The current model was discovered rather than remembered.
- [ ] Required capabilities and constraints were checked.
- [ ] Fixed ID versus trait was chosen intentionally.
- [ ] Deprecation, offline, beta, region, and privacy fields were handled.
- [ ] Cost was estimated from live pricing or a media quote.
- [ ] API keys are server-side and scoped with an appropriate consumption limit.
- [ ] Retries are bounded and status-aware.
- [ ] Streaming parsers handle terminal and mid-stream errors.
- [ ] Async jobs persist both `model` and `queue_id` and clean up media.
- [ ] Binary versus JSON responses are distinguished by `Content-Type`.
- [ ] Logs retain request correlation metadata without sensitive content.
- [ ] Alpha/Beta/Preview behavior is feature-flagged or isolated behind an adapter.
