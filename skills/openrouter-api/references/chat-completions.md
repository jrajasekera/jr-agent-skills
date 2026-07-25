# Chat Completions and Anthropic Messages

Use this reference when implementing the main text-generation surfaces. OpenRouter exposes both an OpenAI-compatible Chat Completions endpoint and an Anthropic-compatible Messages endpoint. They route through the same underlying model/provider system but use different wire formats.

## Choose the skin first

| Requirement | Prefer |
|---|---|
| Existing OpenAI chat integration | `/api/v1/chat/completions` |
| Broad OpenRouter examples and compatibility | `/api/v1/chat/completions` |
| Existing Anthropic SDK, Claude Code, or Anthropic message blocks | `/api/v1/messages` |
| OpenAI Responses-style typed output/server tools | `/api/v1/responses` — see [responses-api.md](responses-api.md) |

Do not translate request fields by name alone. Tool definitions, tool results, system instructions, reasoning blocks, usage, streaming events, and errors differ between the skins.

---

## Chat Completions

### Endpoint

```text
POST https://openrouter.ai/api/v1/chat/completions
```

### Headers

```http
Authorization: Bearer $OPENROUTER_API_KEY
Content-Type: application/json
HTTP-Referer: https://your-app.example          # optional attribution
X-OpenRouter-Title: Your App                    # optional attribution
X-OpenRouter-Categories: cli-agent,programming-app  # optional
```

`X-OpenRouter-Title` is preferred for new code. `X-Title` remains a legacy compatibility alias.

### Minimal request

```json
{
  "model": "author/model-slug",
  "messages": [
    { "role": "system", "content": "Answer accurately and concisely." },
    { "role": "user", "content": "Explain compare-and-swap." }
  ]
}
```

Replace the placeholder with an ID discovered from `GET /api/v1/models`. Do not copy a dated model ID from documentation into a durable integration without checking that it still exists.

### Common request fields

The exact set accepted by a model/provider is exposed in `supported_parameters` and endpoint metadata.

| Field | Purpose |
|---|---|
| `model` | Primary model or router ID |
| `models` | Fallbacks after `model`; without `model`, the complete priority order |
| `messages` | Conversation history |
| `stream` | Return Server-Sent Events |
| `max_tokens` / `max_completion_tokens` | Output cap; use the field supported by the selected model |
| `temperature`, `top_p`, `top_k`, `min_p` | Sampling controls; newer models may reject or ignore some |
| `frequency_penalty`, `presence_penalty`, `repetition_penalty` | Repetition controls; model-specific |
| `stop` | Stop sequences |
| `seed` | Best-effort deterministic sampling where supported |
| `tools`, `tool_choice`, `parallel_tool_calls` | Caller-defined or OpenRouter server tools |
| `response_format` | JSON object or strict JSON Schema output |
| `reasoning` | Unified reasoning control |
| `provider` | Provider routing preferences and constraints |
| `plugins` | One-shot request/response transforms |
| `transforms` | Context/message transforms where supported |
| `service_tier` | Request an upstream capacity tier |
| `session_id` | Sticky routing key for a conversation/agent run |
| `user` | Privacy-safe end-user identifier, up to the documented limit |
| `trace` | Tracing metadata where supported |
| `debug` | Streaming-only upstream request echo via `debug.echo_upstream_body`; development only |

When a feature is required, set:

```json
{
  "provider": {
    "require_parameters": true
  }
}
```

This keeps OpenRouter from selecting an endpoint that cannot honor supplied parameters.

## Message roles

OpenRouter accepts the common roles used by OpenAI-compatible clients:

```json
{ "role": "system", "content": "System policy" }
{ "role": "developer", "content": "Developer instruction" }
{ "role": "user", "content": "User input" }
{ "role": "assistant", "content": "Prior assistant output" }
{ "role": "tool", "tool_call_id": "call_123", "content": "{\"ok\":true}" }
```

Provider adapters may normalize role semantics. If a target model requires a particular role or does not support `developer`, inspect the model/provider documentation and generated upstream request using the debug facility in a non-production environment.

Assistant messages can also carry `phase: "commentary" | "final_answer"`. For follow-up requests, preserve and resend a returned phase on every prior assistant message; omitting it can degrade models that distinguish intermediate commentary from the final answer.

## Typed multimodal content

A compatible model can accept an array of content parts:

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Describe this image." },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/image.png"
      }
    }
  ]
}
```

Other supported content types include PDF/file, inline audio, and video URL inputs. Validate input modalities before sending them. See [multimodal-media.md](multimodal-media.md).

## Structured output

Prefer strict JSON Schema when the model advertises `structured_outputs`:

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "ticket",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "category": { "type": "string" },
          "severity": { "type": "integer", "minimum": 1, "maximum": 5 }
        },
        "required": ["category", "severity"],
        "additionalProperties": false
      }
    }
  },
  "provider": { "require_parameters": true }
}
```

Still validate the final value in application code. `response-healing` can repair some malformed non-streaming JSON, but it does not replace validation and cannot fix every truncated or semantically invalid response.

## Unified reasoning

```json
{
  "reasoning": {
    "effort": "high",
    "exclude": false
  }
}
```

Use either `effort` or `max_tokens` as the main allocation control. Current gateway effort names include `max`, `xhigh`, `high`, `medium`, `low`, `minimal`, and `none`, but each model may expose only a subset and some models make reasoning mandatory. Inspect the live model-level `reasoning` object.

Reasoning may appear as:

- `choices[].message.reasoning` for readable text;
- `choices[].message.reasoning_details` for normalized text, summary, encrypted, or signed blocks;
- usage detail fields for billed reasoning tokens.

When sending tool results back, preserve the complete `reasoning_details` sequence without modification. Preserve any assistant `phase` field too.

## Non-streaming response

A typical response contains:

```json
{
  "id": "gen-...",
  "object": "chat.completion",
  "created": 0,
  "model": "resolved-author/concrete-model",
  "provider": "provider-slug-or-name",
  "choices": [
    {
      "index": 0,
      "finish_reason": "stop",
      "native_finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "...",
        "tool_calls": null,
        "reasoning": null,
        "reasoning_details": null,
        "phase": "final_answer"
      }
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost": 0,
    "prompt_tokens_details": {
      "cached_tokens": 0,
      "cache_write_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0
    }
  }
}
```

Fields are additive and model-dependent. Decode unknown fields permissively. Always record the returned `model`, because aliases, routers, and fallback lists may resolve to a different concrete model than requested.

A non-streaming provider failure that occurs after partial output may be embedded alongside a choice with `finish_reason: "error"`; do not assume every HTTP `200` is a successful completion.

## OpenAI SDK compatibility

### Python

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={
        "HTTP-Referer": "https://your-app.example",
        "X-OpenRouter-Title": "Your App",
    },
)

response = client.chat.completions.create(
    model=os.environ["OPENROUTER_MODEL"],
    messages=[{"role": "user", "content": "Hello"}],
    extra_body={
        "provider": {"require_parameters": True},
        "reasoning": {"effort": "medium"},
    },
)

print(response.choices[0].message.content)
```

### TypeScript

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://openrouter.ai/api/v1",
  apiKey: process.env.OPENROUTER_API_KEY,
  defaultHeaders: {
    "HTTP-Referer": "https://your-app.example",
    "X-OpenRouter-Title": "Your App",
  },
});

const response = await client.chat.completions.create({
  model: process.env.OPENROUTER_MODEL!,
  messages: [{ role: "user", content: "Hello" }],
  // SDK typings may lag OpenRouter-specific fields; use the SDK extension
  // mechanism rather than deleting those fields from the wire request.
  provider: { require_parameters: true },
} as OpenAI.Chat.Completions.ChatCompletionCreateParamsNonStreaming & {
  provider: { require_parameters: boolean };
});
```

When SDK types do not include an OpenRouter extension, use `extra_body`, `extra_headers`, or a narrow local type extension. Do not use `any` across the entire client.

---

# Anthropic-compatible Messages API

## Endpoint

```text
POST https://openrouter.ai/api/v1/messages
```

OpenRouter's Messages skin accepts Anthropic-shaped message blocks, system prompts, tool use, thinking blocks, and event-stream semantics while retaining OpenRouter routing, fallbacks, service tiers, and observability.

## Minimal request

```json
{
  "model": "author/model-slug",
  "max_tokens": 1024,
  "system": "Answer accurately and concisely.",
  "messages": [
    { "role": "user", "content": "Explain compare-and-swap." }
  ]
}
```

## Anthropic SDK compatibility

The Anthropic SDK should use OpenRouter's `/api` base so the SDK can append its own versioned Messages path:

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  baseURL: "https://openrouter.ai/api",
  apiKey: process.env.OPENROUTER_API_KEY,
});

const message = await client.messages.create({
  model: process.env.OPENROUTER_MODEL!,
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello" }],
});

console.log(message.content);
```

For OpenRouter-only request fields that the SDK does not type, use the SDK's beta/extra-body mechanism rather than rewriting the whole request through an incompatible shape.

## Messages-specific model fallback

The Messages endpoint accepts Anthropic-shaped `fallbacks` entries:

```json
{
  "model": "author/primary-model",
  "fallbacks": [
    { "model": "author/compatible-fallback-1" },
    { "model": "author/compatible-fallback-2" }
  ]
}
```

Rules:

- OpenRouter performs the fallback; it is not Anthropic server-side fallback behavior.
- Each entry accepts only a `model` field.
- At most three fallback entries are currently accepted.
- `fallbacks` and OpenRouter's `models` field cannot be used together.
- Every fallback must support the request's modalities, tools, thinking, and output requirements.

## Service tier response location

- Chat Completions and Responses return `service_tier` at the top level.
- Messages returns it inside `usage` to match Anthropic's format.
- Messages uses `standard` for the base tier where OpenAI-shaped responses use `default`.

## Messages streaming and errors

Messages uses Anthropic event names such as content-block and message lifecycle events rather than Chat Completion chunks. A typed provider error is exposed as `error.error_type`. Router metadata appears in the terminal `message_stop` event when `X-OpenRouter-Metadata: enabled` is set.

Use an Anthropic SDK event parser or implement the SSE rules in [streaming.md](streaming.md). Do not pass Chat Completion chunks into a Messages parser.

---

## Common failure modes

### The model exists but rejects a field

The model-level catalog is an aggregate. A particular serving endpoint may support fewer parameters. Inspect `/models/{author}/{slug}/endpoints`, set `require_parameters: true`, or constrain the provider.

### A moving alias changed behavior

Read the returned `model`, compare the new concrete model's metadata, and pin a concrete ID for regressions/evaluations.

### HTTP `200` contains an error

Provider failures can occur after generation begins. Inspect `choices[].finish_reason`, choice-level/top-level `error`, and typed `error_type`; streaming failures are in-band SSE events.

### Structured output is invalid

Confirm `structured_outputs` support, use strict schema, set `require_parameters`, increase the output limit if truncation occurred, and validate locally. Response healing applies only to eligible non-streaming requests.

### Tool continuation loses context

Append the assistant tool-call message exactly, including `reasoning_details` and `phase` when present, then append one result for each matching tool-call ID. Do not reconstruct the assistant message from only its visible text.
