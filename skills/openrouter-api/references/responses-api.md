# Responses API

The OpenRouter Responses API is an OpenAI Responses-compatible API skin for typed input/output items, reasoning, tools, multimodal data, structured text, and OpenRouter server tools.

> **Status:** Beta and stateless. Check the current OpenAPI and changelog before generating durable types or relying on a newly added event/field.

## Endpoint

```text
POST https://openrouter.ai/api/v1/responses
```

## The stateless invariant

OpenRouter does not provide durable server-side conversation state through this endpoint. Each request must contain the history and tool outputs needed to answer the next turn.

A compatibility field such as `previous_response_id` may be accepted by the schema, but it must not be treated as proof that OpenRouter will retrieve and reconstruct prior turns. Build your application so the complete required context can be sent explicitly.

## Minimal request

```json
{
  "model": "author/model-slug",
  "instructions": "Answer accurately and concisely.",
  "input": "Explain compare-and-swap."
}
```

`input` may be a string or a list of typed items.

## Common request fields

| Field | Purpose |
|---|---|
| `model` | Primary model/router |
| `models` | Fallbacks after `model`; without `model`, the complete priority order |
| `input` | String or typed input items |
| `instructions` | System-level instruction |
| `max_output_tokens` | Output limit |
| `stream` | SSE event stream |
| `reasoning` | Unified reasoning controls |
| `tools`, `tool_choice`, `parallel_tool_calls` | Function and server tools |
| `max_tool_calls` | Bound server/tool activity where supported |
| `text.format` | Text, JSON object, or JSON Schema output |
| `text.verbosity` | Output verbosity where supported |
| `modalities` | Requested output modalities, such as text/image |
| `provider` | Provider routing preferences |
| `plugins` | OpenRouter plugins |
| `service_tier` | Requested upstream tier |
| `session_id` | Sticky model/provider routing key |
| `prompt_cache_key` / `cache_control` | Cache-related compatibility controls where supported |
| `user` | Privacy-safe end-user identifier |
| `metadata` | Small application metadata map within documented limits |
| `trace` | Observability/tracing metadata |
| `debug` | Streaming-only upstream request echo via `debug.echo_upstream_body`; development only |

Inspect the current `ResponsesRequest` schema with:

```bash
python scripts/inspect_openapi.py --schema ResponsesRequest
```

## Typed input examples

### Conversation messages

```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": "What is the capital of France?"
    },
    {
      "type": "message",
      "role": "assistant",
      "phase": "final_answer",
      "content": "Paris."
    },
    {
      "type": "message",
      "role": "user",
      "content": "Give me two historical facts about it."
    }
  ]
}
```

### Multimodal message

```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        { "type": "input_text", "text": "What is shown here?" },
        {
          "type": "input_image",
          "image_url": "https://example.com/image.png",
          "detail": "auto"
        }
      ]
    }
  ]
}
```

The exact content item types are additive. Use the current OpenAPI for audio, file, image, and other typed inputs. When replaying prior assistant messages, preserve any `phase` value (`commentary` or `final_answer`) returned by the model.

## Function tool definition

Responses uses the Responses-style function shape rather than nesting the schema under a Chat Completions `function` object:

```json
{
  "tools": [
    {
      "type": "function",
      "name": "get_weather",
      "description": "Get current weather for a location.",
      "parameters": {
        "type": "object",
        "properties": {
          "location": { "type": "string" }
        },
        "required": ["location"],
        "additionalProperties": false
      },
      "strict": true
    }
  ]
}
```

## Returning a function result

A function call appears as an output item. Persist the full prior input and output items, execute the function, then send the history plus a matching `function_call_output`:

```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": "What is the weather in Boston?"
    },
    {
      "type": "function_call",
      "id": "item_123",
      "call_id": "call_123",
      "name": "get_weather",
      "arguments": "{\"location\":\"Boston\"}",
      "status": "completed"
    },
    {
      "type": "function_call_output",
      "call_id": "call_123",
      "output": "{\"temperature_f\":68,\"conditions\":\"clear\"}"
    }
  ]
}
```

The caller remains responsible for authentication, authorization, schema validation, timeouts, idempotency, and side-effect approval for user-defined functions.

## Responses-compatible built-in tool shapes

The live Responses schema can also recognize OpenAI-style built-in/provider tool shapes such as `web_search` variants, `file_search`, `computer_use_preview`, `code_interpreter`, `mcp`, `image_generation`, `local_shell`, `shell`, `apply_patch`, `custom`, and `namespace`. These are distinct from OpenRouter's `openrouter:*` server tools, and availability, execution semantics, required credentials, output items, and provider support vary. Inspect the exact tool schema and selected endpoint before emitting one; do not infer its contract from the type name.

## OpenRouter server tools

Server tools are declared in `tools` with an `openrouter:` type. OpenRouter can execute them during the request. Example:

```json
{
  "tools": [
    { "type": "openrouter:web_search" },
    { "type": "openrouter:web_fetch" }
  ]
}
```

Some server tools, such as `openrouter:apply_patch` and `openrouter:shell`, are Responses-only or have surface-specific behavior. Verify each tool's current documentation. `openrouter:apply_patch` validates and returns a patch; it does **not** apply changes to the caller's filesystem.

See [tool-calling.md](tool-calling.md).

## Structured text output

Responses places the output format under `text.format`:

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "name": "answer",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "answer": { "type": "string" }
        },
        "required": ["answer"],
        "additionalProperties": false
      }
    }
  },
  "provider": {
    "require_parameters": true
  }
}
```

Do not copy Chat Completions' `response_format.json_schema` wrapper into Responses without translating it to the current Responses schema.

## Reasoning

Use the same unified OpenRouter reasoning controls where accepted:

```json
{
  "reasoning": {
    "effort": "high",
    "exclude": false
  }
}
```

Reasoning output may appear as typed `reasoning` items with summary, content, encrypted content, signatures, and status. Preserve opaque fields exactly when continuing a conversation.

## Response shape

A completed response typically contains:

```json
{
  "id": "resp_...",
  "object": "response",
  "created_at": 0,
  "status": "completed",
  "model": "resolved-author/concrete-model",
  "output": [
    {
      "type": "message",
      "id": "msg_...",
      "role": "assistant",
      "phase": "final_answer",
      "status": "completed",
      "content": [
        { "type": "output_text", "text": "...", "annotations": [] }
      ]
    }
  ],
  "output_text": "...",
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "input_tokens_details": { "cached_tokens": 0 },
    "output_tokens_details": { "reasoning_tokens": 0 },
    "cost": 0
  }
}
```

Possible output item types include messages, function calls, reasoning, web-search calls, server-tool calls, images, patches, shell calls, and future additive types. Decode by `type` and ignore unknown fields rather than failing the entire response. Preserve message `phase` when carrying an output message into the next stateless request.

Do not use `output_text` as the only source when tools, images, annotations, or other item types matter.

## Status and incomplete responses

Handle at least:

- `completed` — normal terminal success;
- `incomplete` — inspect incomplete details, such as output limit or content filtering;
- `failed` — inspect top-level error and `error_type`;
- `cancelled` — request was cancelled;
- `in_progress` / queued states if introduced by a specialized workflow.

The schema can grow; do not treat an unknown status as success.

## Streaming

Set:

```json
{ "stream": true }
```

Responses streams named SSE events, for example lifecycle, output-item, text-delta, reasoning, tool, completion, and failure events. Event names and payloads are more expressive than Chat Completion chunks.

A robust client must:

1. parse SSE framing, not individual TCP/newline chunks;
2. preserve the event name as well as the `data` payload;
3. apply deltas to the matching item/content indices;
4. stop on a terminal completed/failed/cancelled event or `[DONE]`;
5. inspect top-level `error_type` on `response.failed`;
6. retain unknown events for forward-compatible telemetry rather than crashing.

Use an official SDK event parser when possible. See [streaming.md](streaming.md).

## Router metadata and response caching

- Send `X-OpenRouter-Metadata: enabled` to receive `openrouter_metadata` in successful/error responses and near the terminal stream event.
- Send `X-OpenRouter-Cache: true` to make an identical successful Responses request eligible for OpenRouter edge response caching.
- Response caching is separate from provider prompt caching and is unavailable under account-level ZDR.
- A cache hit intentionally omits router metadata and returns a fresh generation ID for the replay.

## Debugging

For a non-production diagnostic request:

```json
{
  "stream": true,
  "debug": {
    "echo_upstream_body": true
  }
}
```

The debug option is ignored for non-streaming requests. In a stream, the API can expose the normalized body sent to the provider. This may include sensitive prompt/tool data. Never enable it by default or log the echoed body in production.

## Migration notes

### From Chat Completions

| Chat Completions | Responses |
|---|---|
| `messages` | `input` typed items |
| system/developer message | `instructions` or typed message item |
| `max_tokens` / `max_completion_tokens` | `max_output_tokens` |
| `response_format` | `text.format` |
| `choices[0].message` | `output[]` items |
| `choices[0].delta` | named item/content delta events |
| `prompt_tokens` / `completion_tokens` | `input_tokens` / `output_tokens` |
| nested function definition | flat Responses function definition |
| `role: tool` | `function_call_output` item |

### From OpenAI's stateful conveniences

Persist all conversation and tool state in your own application. Treat `id` values as correlation IDs, not durable conversation handles.

## Common failure modes

### Sending only a previous response ID

Fix: persist and resend the required history explicitly.

### Mixing Chat tool shapes into Responses

Fix: use the flat Responses function definition and `function_call_output` items.

### Reading only `output_text`

Fix: iterate typed `output` items whenever tools, citations, images, reasoning, or status matter.

### Treating any SSE payload as a Chat chunk

Fix: dispatch on the Responses event name and item indices.

### Depending on a beta field without a boundary

Fix: isolate Responses payload translation behind a versioned adapter and add contract tests against a captured live response/OpenAPI schema.
