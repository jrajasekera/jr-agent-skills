# Streaming and Server-Sent Events

OpenRouter streams Chat Completions, Responses, and Anthropic Messages with Server-Sent Events (SSE). The event payload differs by API skin, but the framing rules are shared.

## Core rules

1. Check the HTTP status before parsing the body as a successful stream.
2. Read arbitrary byte chunks; network chunks do not align with SSE events.
3. Decode incrementally and split events on a blank line.
4. Join multiple `data:` lines with `\n`.
5. Ignore comment lines beginning with `:` such as OpenRouter processing keepalives.
6. Preserve `event:` names for Responses and Messages.
7. Stop on the skin's terminal event and/or `data: [DONE]`.
8. Treat a top-level/in-event error after HTTP `200` as a real failure.
9. Capture `X-Generation-Id` from response headers before consuming the body.

## Enable Chat Completions streaming

```json
{
  "model": "author/model-slug",
  "messages": [{ "role": "user", "content": "Write a short story." }],
  "stream": true
}
```

OpenRouter now includes usage automatically. Legacy `usage: { "include": true }` and `stream_options: { "include_usage": true }` settings are deprecated and have no effect. Read usage from the terminal response/event for the selected API skin, and tolerate additive fields.

## Robust TypeScript SSE parser

```typescript
type SseEvent = {
  event?: string;
  id?: string;
  retry?: number;
  data: string;
};

export async function* parseSse(response: Response): AsyncGenerator<SseEvent> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`OpenRouter HTTP ${response.status}: ${body}`);
  }
  if (!response.body) throw new Error("OpenRouter response has no body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName: string | undefined;
  let eventId: string | undefined;
  let retry: number | undefined;
  let dataLines: string[] = [];

  const emit = (): SseEvent | undefined => {
    if (dataLines.length === 0 && eventName === undefined && eventId === undefined) {
      return undefined;
    }
    const value: SseEvent = {
      event: eventName,
      id: eventId,
      retry,
      data: dataLines.join("\n"),
    };
    eventName = undefined;
    eventId = undefined;
    retry = undefined;
    dataLines = [];
    return value;
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let newline: number;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      let line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);

      if (line === "") {
        const complete = emit();
        if (complete) yield complete;
        continue;
      }

      if (line.startsWith(":")) continue; // SSE comment/keepalive

      const separator = line.indexOf(":");
      const field = separator < 0 ? line : line.slice(0, separator);
      let fieldValue = separator < 0 ? "" : line.slice(separator + 1);
      if (fieldValue.startsWith(" ")) fieldValue = fieldValue.slice(1);

      switch (field) {
        case "event":
          eventName = fieldValue;
          break;
        case "data":
          dataLines.push(fieldValue);
          break;
        case "id":
          eventId = fieldValue;
          break;
        case "retry": {
          const parsed = Number.parseInt(fieldValue, 10);
          if (Number.isFinite(parsed)) retry = parsed;
          break;
        }
        default:
          // Ignore unknown SSE fields for forward compatibility.
          break;
      }
    }

    if (done) break;
  }

  // A compliant server terminates events with a blank line, but retain a final
  // buffered event defensively when the connection closes cleanly.
  if (buffer.length > 0) {
    let line = buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer;
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  const finalEvent = emit();
  if (finalEvent) yield finalEvent;
}
```

## Consuming Chat Completion chunks

```typescript
const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: process.env.OPENROUTER_MODEL,
    messages: [{ role: "user", content: "Hello" }],
    stream: true,
  }),
});

const generationId = response.headers.get("X-Generation-Id");
let text = "";

for await (const event of parseSse(response)) {
  if (event.data === "[DONE]") break;
  if (!event.data) continue;

  const chunk = JSON.parse(event.data);
  if (chunk.error) {
    const errorType = chunk.error?.metadata?.error_type;
    throw new Error(`OpenRouter stream error (${errorType ?? "unknown"}): ${chunk.error.message}`);
  }

  const delta = chunk.choices?.[0]?.delta;
  if (delta?.content) {
    text += delta.content;
    process.stdout.write(delta.content);
  }

  // Accumulate delta.tool_calls and delta.reasoning_details separately.
  if (chunk.usage) console.error("Usage:", chunk.usage);
  if (chunk.openrouter_metadata) {
    console.error("Routing:", chunk.openrouter_metadata);
  }
}
```

Do not discard partial `text` if a later event fails. Return or store it separately from a successful final answer.

## Chat Completion chunk shape

Typical chunks can include:

```json
{
  "id": "gen-...",
  "object": "chat.completion.chunk",
  "model": "resolved-author/concrete-model",
  "choices": [
    {
      "index": 0,
      "delta": {
        "role": "assistant",
        "content": "partial text",
        "tool_calls": [],
        "reasoning_details": []
      },
      "finish_reason": null
    }
  ],
  "usage": null
}
```

Fields may be omitted on most chunks and appear only on the first or terminal chunk.

## In-band errors

### Before the stream starts

OpenRouter can return a normal non-`2xx` HTTP response:

```json
{
  "error": {
    "code": 429,
    "message": "Rate limit exceeded",
    "metadata": {
      "error_type": "rate_limit_exceeded"
    }
  }
}
```

At this stage OpenRouter can still retry/fallback internally because no content was sent.

### After content starts

The HTTP status remains `200`. A Chat stream emits a chunk with an `error` and error finish reason. OpenRouter cannot transparently fail over after partial output.

Classify by canonical `error_type`:

- Chat Completions: `error.metadata.error_type`;
- Messages: `error.error_type`;
- Responses: top-level `error_type` on `response.failed`.

Do not classify solely by text matching or status code.

## Tool-call deltas

Tool names and argument JSON arrive incrementally. Group by `tool_calls[].index` and concatenate strings. Parse arguments only after the tool call is complete. See [tool-calling.md](tool-calling.md).

## Reasoning deltas

Reasoning can arrive in `delta.reasoning` and/or `delta.reasoning_details`. Preserve full detail objects and their order. Do not concatenate encrypted/signature fields as if they were text.

## Responses streaming

Responses uses named events such as response lifecycle, output-item, content-delta, tool, completion, and failure events. Dispatch on `event.event` and the payload `type`; do not assume `choices[0].delta` exists.

A terminal failure includes top-level `error_type`. Keep unknown events for telemetry or ignore them permissively; the event set is additive while the API is beta.

## Messages streaming

Anthropic Messages uses events such as message start/stop, content-block start/delta/stop, and error. Prefer the Anthropic SDK event parser when using this skin. Router metadata appears in the terminal `message_stop` event when enabled.

## Keepalive comments

OpenRouter may emit comments like:

```text
: OPENROUTER PROCESSING
```

These are legal SSE comments used to keep intermediaries from timing out. Ignore them; never pass them to `JSON.parse`.

## Cancellation

### Fetch/TypeScript

```typescript
const controller = new AbortController();

const response = await fetch(url, {
  method: "POST",
  headers,
  body,
  signal: controller.signal,
});

// Abort from user cancellation, deadline, or application shutdown.
controller.abort();
```

Cancellation can stop upstream generation/billing only when the selected provider supports it and the cancellation reaches OpenRouter in time. Do not promise zero additional tokens after a local abort.

## Backpressure

Consume the body as it arrives. If forwarding to a browser/WebSocket:

- bound outbound queues;
- pause or terminate slow consumers;
- avoid storing unbounded deltas;
- cap total bytes/tokens;
- propagate cancellation upstream;
- separate user-visible text from internal reasoning/tool events.

## Response caching and streams

OpenRouter response caching can replay eligible streaming responses through the same streaming pipeline. Streaming and non-streaming requests use different cache keys.

On a cache hit:

- content is replayed;
- billable usage counters are zero;
- a fresh generation ID is created;
- router metadata is omitted because the original route metadata may be stale.

Inspect `X-OpenRouter-Cache-Status` before consuming the body.

## Router metadata

Send:

```http
X-OpenRouter-Metadata: enabled
```

For streaming Chat/Responses, `openrouter_metadata` is delivered near the terminal event before `[DONE]`. For Messages it appears in the terminal message event. Decode unknown pipeline stages permissively.

## Debug mode

`debug.echo_upstream_body` can expose the transformed provider request for Chat Completions and Responses, and currently applies only to streaming requests. Use it only in a controlled diagnostic request. The echo may contain prompts, tools, files, or sensitive identifiers.

## Python with `requests`

```python
import json
import os
import requests

with requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "model": os.environ["OPENROUTER_MODEL"],
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    },
    stream=True,
    timeout=(10, 300),
) as response:
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line or raw_line.startswith(":"):
            continue
        if not raw_line.startswith("data:"):
            continue

        data = raw_line[5:].lstrip()
        if data == "[DONE]":
            break

        chunk = json.loads(data)
        if "error" in chunk:
            raise RuntimeError(chunk["error"])

        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        if content:
            print(content, end="", flush=True)
```

`iter_lines()` is adequate for OpenRouter's normal single-line JSON events, but a general-purpose SSE parser should support multiline `data:` fields and event names.

## Common mistakes

- Calling `JSON.parse` on every network line, including comments and partial frames.
- Assuming HTTP `200` means the stream completed successfully.
- Dropping partial content on a mid-stream provider error.
- Parsing tool arguments before all deltas arrive.
- Treating Responses or Messages events as Chat chunks.
- Ignoring backpressure and cancellation.
- Logging reasoning, file contents, or raw upstream debug bodies.
