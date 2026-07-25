# Chat completions, Responses, multimodal input, tools, and search

Use `POST /chat/completions` as the default Venice text endpoint. It is broadly OpenAI-compatible and exposes Venice-only behavior through `venice_parameters`.

Use `POST /responses` only when a client specifically needs the Responses-style typed output. It is an Alpha surface with narrower compatibility and potentially gated access; validate the live schema and account entitlement before depending on it.

## Minimal chat request

```bash
curl -sS https://api.venice.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [
      {"role": "user", "content": "Why is the sky blue?"}
    ],
    "max_completion_tokens": 500
  }'
```

Use `max_completion_tokens`; `max_tokens` remains accepted for compatibility but is deprecated.

## Core request fields

| Field | Notes |
|---|---|
| `model` | Fixed ID, trait, or compatibility alias. Required. Feature suffixes may be appended. |
| `messages` | Conversation history. Required. Roles include `system`, `developer`, `user`, `assistant`, and `tool`. |
| `temperature`, `top_p`, `top_k`, `min_p` | Sampling controls. Prefer changing one primary randomness control at a time. |
| `min_temp`, `max_temp` | Dynamic temperature bounds on supporting models. |
| `frequency_penalty`, `presence_penalty`, `repetition_penalty` | Repetition/topic controls; model support varies. |
| `max_completion_tokens` | Output ceiling including reasoning tokens where applicable. |
| `n` | Number of choices. Keep at `1` unless multiple paid outputs are intentional. |
| `seed` | Reproducibility hint, not a cross-provider guarantee. |
| `stop`, `stop_token_ids` | String or token-level stop controls. |
| `stream`, `stream_options.include_usage` | SSE streaming and optional final usage chunk. |
| `tools`, `tool_choice`, `parallel_tool_calls` | Function calling and built-in tools. |
| `response_format` | `json_schema`, `json_object`, or text. Check capability. |
| `reasoning`, `reasoning_effort` | Reasoning configuration on supporting models. `reasoning.enabled: false` is the Venice-level off switch; flat `reasoning_effort` may take precedence over `reasoning.effort`. |
| `prompt_cache_key`, `prompt_cache_retention` | Cache-routing and retention hints. |
| `text.verbosity` | Output verbosity hint on supporting provider models. |
| `logprobs`, `top_logprobs` | Evaluation/debugging only; require model support. |
| `metadata`, `include` | OpenAI-compatible tracking/inclusion fields. Support can vary. |
| `user`, `store` | Accepted for compatibility; Venice may discard or ignore them. |

Do not send unsupported fields merely because another provider accepts them. Inspect the model capabilities and current endpoint schema.

## Venice parameters

```json
{
  "venice_parameters": {
    "include_venice_system_prompt": false,
    "enable_web_search": "auto",
    "enable_web_scraping": false,
    "enable_web_citations": true,
    "include_search_results_in_stream": false,
    "return_search_results_as_documents": false,
    "enable_x_search": false,
    "character_slug": "alan-watts",
    "strip_thinking_response": false,
    "disable_thinking": false,
    "enable_e2ee": true
  }
}
```

### Semantics

- `include_venice_system_prompt`: Venice normally adds its own curated system prompt alongside yours. Set `false` when exact prompt control matters.
- `enable_web_search`: `off`, `auto`, or `on`. Requires a model that supports Venice web search.
- `enable_web_scraping`: detects public URLs in the latest user message and adds extracted page content. Extra charges and URL limits can apply.
- `enable_web_citations`: asks for inline citations. Treat structured citation metadata as authoritative; inline marker syntax can evolve.
- `include_search_results_in_stream`: includes search result metadata in a streamed response.
- `return_search_results_as_documents`: exposes results in a synthetic tool-call shape for frameworks such as LangChain.
- `enable_x_search`: uses supported xAI models' native web and X search. Check `supportsXSearch` and current pricing.
- `character_slug`: injects a published Venice character persona.
- `strip_thinking_response`: removes legacy visible `<think>`-style blocks after reasoning.
- `disable_thinking`: skips reasoning on models that expose this switch.
- `enable_e2ee`: participates in the supported E2EE flow; this flag alone does not create end-to-end encryption.

## Model feature suffixes

For clients that cannot add `venice_parameters`, supported parameters can be appended to `model`:

```text
<model>:<key>=<value>&<key>=<value>
```

Examples:

```text
default:enable_web_search=auto
default:enable_web_search=on&enable_web_citations=true
default:include_venice_system_prompt=false&character_slug=alan-watts
```

Use URL-safe values. Unknown keys may be ignored rather than rejected, so suffixes are not a substitute for tests. `enable_e2ee` and `enable_x_search` are not generally available as suffixes; use `venice_parameters` unless current documentation says otherwise.

## Message content types

A user message can contain a string or an array of typed parts.

### Text

```json
{"type": "text", "text": "Describe the attached image."}
```

### Image

```json
{
  "type": "image_url",
  "image_url": {
    "url": "https://example.com/photo.png"
  }
}
```

The URL can be public HTTPS or a `data:image/...;base64,...` URL. Require `supportsVision`. For multiple images, also require `supportsMultipleImages` and respect `maxImages`.

Single-image models can discard older images in conversation history. Place all relevant images in the latest user message unless the model explicitly preserves multiple images across turns.

### Audio

```json
{
  "type": "input_audio",
  "input_audio": {
    "data": "<base64 without a URL fetch>",
    "format": "wav"
  }
}
```

Audio input is inline base64. Do not pass an audio URL. Require `supportsAudioInput`. Supported encodings are model/endpoint dependent; current chat docs include common formats such as WAV, MP3, AIFF, AAC, OGG, FLAC, M4A, PCM16, and PCM24.

### Video

```json
{
  "type": "video_url",
  "video_url": {
    "url": "https://example.com/clip.mp4"
  }
}
```

Public URLs and `data:video/...;base64,...` inputs can be accepted by compatible models. Require `supportsVideoInput`. Provider-specific support for sites such as YouTube can vary.

### File input

Files are extracted to text before the request reaches the model.

```python
import base64
from pathlib import Path

path = Path("q3-report.pdf")
file_data = (
    "data:application/pdf;base64,"
    + base64.b64encode(path.read_bytes()).decode("utf-8")
)

response = client.chat.completions.create(
    model="default",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Summarize the report and list the main risks.",
                },
                {
                    "type": "file",
                    "file": {
                        "file_data": file_data,
                        "filename": "q3-report.pdf",
                    },
                },
            ],
        }
    ],
)
```

`file.file_data` can be a supported public URL or a base64 data URL. Include `filename`, especially with multiple files.

Common supported categories include:

- PDF, DOCX, PPTX
- XLSX, XLS, CSV
- TXT, Markdown, JSON
- common source-code formats

Current documented maximum is 25 MB per decoded/fetched file. Extracted text counts toward input context and cost. Base64 also expands the HTTP payload. Use `/augment/text-parser` when you need to inspect token count, persist extracted text, trim it, or reuse it across calls.

## Multiple modalities in one request

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Compare the product photo to the requirements document."},
    {"type": "image_url", "image_url": {"url": "https://example.com/product.jpg"}},
    {
      "type": "file",
      "file": {
        "file_data": "data:application/pdf;base64,...",
        "filename": "requirements.pdf"
      }
    }
  ]
}
```

Select a model with the required modality capabilities and enough context for the extracted document.

## Streaming

```python
stream = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "Write a technical overview."}],
    stream=True,
    stream_options={"include_usage": True},
)

for chunk in stream:
    if not chunk.choices:
        # A final usage-only chunk can have no choices.
        continue
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

REST clients should parse Server-Sent Events until `data: [DONE]`. Be prepared for:

- empty keepalive lines;
- a first or final search-metadata chunk;
- tool-call arguments arriving incrementally;
- a usage-only terminal chunk;
- an error object delivered inside an HTTP 200 stream.

Treat mid-stream errors as terminal. Do not concatenate partial JSON tool arguments until the tool call is complete.

## Reasoning

Require `supportsReasoning`; require `supportsReasoningEffort` if the effort level must be honored.

```json
{
  "reasoning": {
    "enabled": true,
    "effort": "medium",
    "summary": "auto"
  },
  "venice_parameters": {
    "strip_thinking_response": true
  }
}
```

The current effort vocabulary can include:

```text
none, minimal, low, medium, high, xhigh, max
```

Actual support is model-specific. The flat `reasoning_effort` field takes precedence over `reasoning.effort` when both are present.

Responses can expose one or more of:

- `reasoning_content`
- `reasoning_details[]`
- provider-specific opaque signatures
- visible legacy thinking tags

For multi-turn tool flows, pass provider-generated `reasoning_details` or signatures back **unchanged** when required. Never edit, summarize, invent, or merge opaque reasoning metadata.

To disable reasoning, prefer `reasoning: {"enabled": false}` where supported. This Venice-level switch prevents reasoning parameters from being sent to the provider. `reasoning.effort: "none"` is provider-dependent. `strip_thinking_response` only hides legacy visible reasoning after it occurs and does not necessarily reduce billed reasoning tokens. `venice_parameters.disable_thinking` remains available for models that expose Venice's legacy switch, but capability support must still be checked.

## Structured output

Require `supportsResponseSchema`.

```python
response = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "Extract the person's name and age."}],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "person",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
                "additionalProperties": False,
            },
        },
    },
)
```

Schema dialect and strictness support can differ by model/provider. Keep schemas simple, require all intended fields, and disallow additional properties when exact output matters. Validate the returned JSON locally even when strict mode is requested.

## Function calling

### Tool definition

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]
```

### Complete Python loop

```python
import json

messages = [{"role": "user", "content": "What is the weather in Columbus?"}]

first = client.chat.completions.create(
    model="function_calling_default",
    messages=messages,
    tools=tools,
    tool_choice="auto",
    parallel_tool_calls=True,
)

assistant_message = first.choices[0].message
messages.append(assistant_message.model_dump(exclude_none=True))

for call in assistant_message.tool_calls or []:
    args = json.loads(call.function.arguments)

    # Validate args against your own schema and authorization policy.
    result = get_weather(city=args["city"])

    messages.append(
        {
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result),
        }
    )

final = client.chat.completions.create(
    model="function_calling_default",
    messages=messages,
    tools=tools,
)
print(final.choices[0].message.content)
```

Production rules:

1. Treat tool arguments as untrusted input.
2. Validate JSON and the function schema locally.
3. Apply authorization independently of model intent.
4. Bound time, cost, output size, and side effects.
5. Execute all parallel calls before continuing the turn.
6. Preserve the assistant tool-call message exactly, including any reasoning metadata.
7. Never let the model choose arbitrary executable code, shell commands, file paths, SQL, URLs, or transaction data without policy checks.

## Built-in search tools

Some current chat schemas can accept built-in tool declarations such as:

```json
{
  "tools": [
    {"type": "web_search"},
    {"type": "x_search"}
  ]
}
```

These correspond to Venice or provider-native search. Verify the model capability and current schema; `venice_parameters` remains the broadest documented control surface.

When search is enabled:

- capture structured citation/search metadata from the response;
- do not parse only human-readable inline markers;
- surface source title, URL, snippet, and date where present;
- distinguish Venice web search from xAI X search in cost and privacy logs;
- do not claim the model searched successfully if metadata is absent.

## URL scraping

With `enable_web_scraping: true`, Venice can scrape public URLs present in the latest user message. Use it for a small number of user-supplied pages. Use `/augment/scrape` when the application needs explicit scrape results, error handling, storage, or a search-then-scrape pipeline.

Private URLs, localhost, cookie-gated pages, and session-bound signed links are not reliable inputs. Fetch sensitive content in your own trusted backend and pass it as text/file data instead.

## Prompt caching

Root-level hints:

```json
{
  "prompt_cache_key": "tenant-123-policy-v7",
  "prompt_cache_retention": "24h"
}
```

Some models also accept content-part cache controls:

```json
{
  "type": "text",
  "text": "Long stable document...",
  "cache_control": {"type": "ephemeral", "ttl": "1h"}
}
```

Rules:

- Check the model's current cache support and pricing.
- Keep tenant/user identity in cache keys to prevent accidental cross-context routing.
- Put stable content before dynamic content.
- Read `usage.prompt_tokens_details` or current usage metadata for cached token counts.
- Never assume a cache hit; caching is an optimization, not storage.

## Characters

Discover a character first:

```bash
curl -sS "https://api.venice.ai/api/v1/characters?search=philosophy&limit=20" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Then use the returned public `slug`:

```json
{
  "model": "default",
  "messages": [{"role": "user", "content": "What is the nature of mind?"}],
  "venice_parameters": {
    "character_slug": "alan-watts",
    "include_venice_system_prompt": false
  }
}
```

A character bundles a persona and may advertise a backing model, but the caller can select another compatible model. Character APIs are Preview; treat slugs and metadata as external content, not trusted instructions for tool authorization.

## Responses API (Alpha)

`POST /responses` returns a typed `output[]` array rather than one chat message. Possible output items include:

- reasoning
- message / output text
- function call
- web-search call

Minimal request:

```bash
curl -sS https://api.venice.ai/api/v1/responses \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "input": "Explain Rayleigh scattering in one paragraph."
  }'
```

Use it only after checking current docs because:

- Bearer access can be feature-gated; wallet access behavior can differ.
- The endpoint is stateless; send required history each request.
- It does not promise full parity with OpenAI's Responses API.
- Supported Venice extensions are a changing subset.
- structured `response_format`, background jobs, stored conversations, and E2EE may not be supported.
- streaming uses typed SSE events rather than chat chunk deltas.

For the broadest Venice feature support, stay on `/chat/completions`.

## Common failures

- `400`: unsupported field, invalid role/content part, context overflow, malformed schema, invalid model suffix.
- `401`: bad key, gated model, or inaccessible Alpha feature.
- `402`: insufficient Bearer balance or x402 wallet credit.
- `413`: uploaded base64 image/audio/video/file too large.
- `415`: wrong `Content-Type`.
- `429`: model/key limit; honor headers.
- `500` / `503`: inference/provider failure or capacity issue.
- `504`: long non-streaming request; use streaming, smaller context, or a different model.

## Sources of truth

- Chat endpoint: `https://docs.venice.ai/api-reference/endpoint/chat/completions`
- File inputs: `https://docs.venice.ai/guides/features/file-inputs`
- Function calling: `https://docs.venice.ai/guides/features/function-calling`
- Structured responses: `https://docs.venice.ai/guides/features/structured-responses`
- Reasoning: `https://docs.venice.ai/guides/features/reasoning-models`
- Web search: `https://docs.venice.ai/guides/features/web-search`
- Prompt caching: `https://docs.venice.ai/guides/features/prompt-caching`
- Model suffixes: `https://docs.venice.ai/api-reference/endpoint/chat/model_feature_suffix`
