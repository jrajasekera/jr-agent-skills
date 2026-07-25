# Production engineering: errors, retries, streaming, observability, and tests

A successful Venice proof of concept is not yet a production integration. Production clients need status-aware retries, model lifecycle handling, content-type-aware response parsing, spend controls, credential hygiene, and request correlation.

## Client architecture

Keep these concerns separate:

```text
configuration
  -> authentication provider
  -> model discovery/cache
  -> request validation
  -> endpoint client
  -> retry/circuit-breaker policy
  -> response parser
  -> usage/telemetry recorder
  -> application adapter
```

Do not scatter raw `fetch`/`requests` calls and model IDs throughout business logic.

Recommended adapters:

```text
VeniceChatClient
VeniceImageClient
VeniceAudioClient
VeniceVideoClient
VeniceEmbeddingClient
VeniceAugmentClient
VeniceAdminClient
VeniceWalletClient
VeniceCryptoRpcClient
```

Use a shared HTTP transport for authentication, timeouts, correlation IDs, retries, and logging, but allow endpoint-specific response parsers.

## Error body families

Venice errors can appear in several shapes. Handle them defensively.

### Simple error

```json
{"error": "Unauthorized"}
```

### Detailed validation error

```json
{
  "error": "Invalid request",
  "details": {
    "_errors": [],
    "messages": {"_errors": ["Field is required"]}
  },
  "issues": [
    {
      "code": "invalid_type",
      "path": ["messages"],
      "message": "Field is required"
    }
  ]
}
```

`details` can be a nested validation tree, not a flat map. Preserve `issues` and recursively render `_errors` for developers.

### Content-policy or provider validation

```json
{
  "error": "Content policy violation",
  "suggested_prompt": "A safer alternative..."
}
```

A `suggested_prompt` is endpoint-specific. Do not assume every `422` includes it, and do not silently change user intent.

### x402 payment required

```json
{
  "error": "Payment required",
  "code": "PAYMENT_REQUIRED",
  "message": "Insufficient x402 balance",
  "suggestedTopUpUsd": 10,
  "topUpInstructions": {}
}
```

The corresponding `PAYMENT-REQUIRED` header contains a different protocol-level payload.

## Status-code policy

| Status | Meaning varies by endpoint | Default action |
|---|---|---|
| `400` | Invalid request, unsupported model/constraint, bad media | Fix request; never retry unchanged |
| `401` | Missing/invalid key or SIWX payload, inaccessible gated model | Fix credentials/access; never retry unchanged |
| `402` | Insufficient account or wallet balance | Follow matching funding flow; then retry intentionally |
| `403` | Valid identity lacks entitlement, region, beta, admin, or wallet ownership | Surface; do not hammer |
| `404` | Unknown model, character, job, route, or expired media | Re-resolve or fail; do not blind-retry |
| `409` | Potential conflict on evolving/admin routes | Inspect body; retry only if documented |
| `413` | Request/media too large | Reduce or host payload |
| `415` | Wrong media type or multipart/JSON mismatch | Correct body and headers |
| `422` | Policy rejection or endpoint-specific validation | Inspect body; modify only with user/product consent |
| `429` | RPM/TPM/RPD, concurrency, or credit cap | Honor headers and back off with jitter |
| `500` | Internal/provider failure | Bounded retry if operation is safe/idempotent |
| `502` | Upstream proxy failure where surfaced | Bounded retry |
| `503` | Capacity or temporary unavailability | Back off; consider a compatible fallback |
| `504` | Gateway timeout, often large non-streaming text | Stream, shrink context, or retry with bounds |

The same status can mean different things on different routes. Preserve endpoint, method, model, response body, and headers in the typed error object.

## Typed error object

```typescript
export class VeniceError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly method: string,
    readonly path: string,
    readonly requestId?: string,
    readonly code?: string,
    readonly body?: unknown,
    readonly retryAfterMs?: number,
  ) {
    super(message);
    this.name = "VeniceError";
  }
}
```

Never include authorization headers, private keys, file bytes, prompts, or base64 media in the error message.

## Retry matrix

### Never retry unchanged

- `400`
- `401`
- `403`
- `404` when a resource is definitively unknown/expired
- `413`
- `415`
- deterministic `422`

### Retry after an explicit action

- Bearer `402`: user/account top-up or key-limit change
- x402 `402`: successful wallet top-up
- `422` with an acceptable `suggested_prompt`: one user-approved modified request
- invalid/deprecated model: re-resolve a compatible model, then submit as a new request

### Retry with backoff

- `429`
- `500`
- `502`
- `503`
- `504`
- network reset/timeouts before any response, when replay is safe

Use full jitter and a cap:

```python
import random


def backoff_seconds(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    maximum = min(cap, base * (2**attempt))
    return random.uniform(0, maximum)
```

Honor server guidance first:

1. `Retry-After` seconds or HTTP date;
2. general `x-ratelimit-reset-requests` Unix timestamp;
3. route-specific reset headers such as crypto RPC `X-RateLimit-Reset`;
4. client exponential backoff.

Limit most retries to three to five attempts and bound total elapsed time.

## Generic Python request helper

```python
from __future__ import annotations

import json
import os
import random
import time
import uuid
from typing import Any

import requests

BASE = "https://api.venice.ai/api/v1"
RETRYABLE = {429, 500, 502, 503, 504}


class VeniceHttpError(RuntimeError):
    def __init__(self, *, status: int, path: str, request_id: str | None, body: Any):
        message = body.get("error") if isinstance(body, dict) else str(body)
        super().__init__(f"Venice {status} on {path}: {message}")
        self.status = status
        self.path = path
        self.request_id = request_id
        self.body = body


def request_json(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: tuple[float, float] = (10.0, 180.0),
    max_attempts: int = 4,
) -> requests.Response:
    key = os.environ["VENICE_API_KEY"]
    correlation_id = str(uuid.uuid4())

    for attempt in range(max_attempts):
        response = requests.request(
            method,
            f"{BASE}{path}",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Client-Request-ID": correlation_id,
            },
            json=body,
            timeout=timeout,
        )

        if response.ok:
            return response

        try:
            error_body: Any = response.json()
        except (requests.JSONDecodeError, json.JSONDecodeError):
            error_body = {"error": response.text[:2000]}

        request_id = (
            response.headers.get("X-Request-ID")
            or response.headers.get("CF-RAY")
            or correlation_id
        )

        if response.status_code not in RETRYABLE or attempt == max_attempts - 1:
            raise VeniceHttpError(
                status=response.status_code,
                path=path,
                request_id=request_id,
                body=error_body,
            )

        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            delay = float(retry_after)
        else:
            reset = (
                response.headers.get("x-ratelimit-reset-requests")
                or response.headers.get("X-RateLimit-Reset")
            )
            if reset and reset.isdigit():
                delay = max(float(reset) - time.time(), 0.0)
            else:
                delay = random.uniform(0, min(30.0, 0.5 * (2**attempt)))

        time.sleep(delay)

    raise AssertionError("unreachable")
```

Do not use this generic replay helper for paid async queue submissions or blockchain writes without idempotency/deduplication controls.

## Idempotency and duplicate-cost prevention

### Chat, images, TTS, and embeddings

Most inference calls are conceptually repeatable but a retry can produce a second charge and different output. Retry only when:

- no HTTP response was received and product policy accepts duplicate risk;
- the route documents idempotency support; or
- the application deduplicates with its own durable job state.

### Audio/video queue

Persist a client job record before queueing. After receiving `queue_id`, never queue a replacement merely because polling failed. Continue the original job.

### Crypto RPC

Use `Idempotency-Key` for state-mutating calls, especially raw transaction or user-operation submission. Reuse the same key only with the identical body.

### Admin writes

On key creation, a network failure after the server accepted the request can leave an unknown new key. List keys by description/timestamp before retrying creation to avoid duplicates.

## Timeouts

Configure connect and read timeouts separately.

Suggested starting points, then tune from telemetry:

| Route | Connect | Read |
|---|---:|---:|
| Models/admin/light JSON | 5–10 s | 30 s |
| Chat non-streaming | 10 s | 120–300 s |
| Chat streaming | 10 s | idle timeout 60–120 s; total deadline separately |
| Image/TTS | 10 s | 180–300 s |
| Audio/video retrieve | 10 s | 180 s per poll plus overall job deadline |
| File parse/transcription | 10 s | 180–600 s by file size |
| Crypto RPC | 5–10 s | 30–60 s |

A long read timeout is not a job deadline. Always set an overall deadline for polling and streaming.

## Binary versus JSON responses

Several endpoints return JSON while processing/errors and binary bytes when complete.

```typescript
const contentType = response.headers.get("content-type") ?? "";

if (contentType.startsWith("application/json")) {
  const body = await response.json();
  // status or error handling
} else if (contentType.startsWith("image/")) {
  // image bytes
} else if (contentType.startsWith("audio/")) {
  // audio bytes
} else if (contentType.startsWith("video/")) {
  // video bytes
} else {
  throw new Error(`Unexpected Content-Type: ${contentType}`);
}
```

Do not save a JSON error body as `.png`, `.mp3`, or `.mp4`.

Validate downloaded media:

- nonzero size;
- expected MIME/magic bytes;
- decodable dimensions/duration;
- checksum before cleanup;
- object-store write success.

## Streaming chat

SSE parser requirements:

- split events on blank lines, not arbitrary TCP chunks;
- process every `data:` line in an event;
- accept comments/keepalives;
- stop on `[DONE]`;
- accumulate tool arguments by tool-call index/ID;
- handle usage-only chunks;
- handle search metadata chunks;
- treat an embedded error event as terminal even when HTTP status is 200;
- cancel upstream when the client disconnects, if supported by the runtime;
- enforce an idle timeout and total duration.

Do not display incomplete structured JSON or execute incomplete streamed tool arguments.

## Model fallback policy

A fallback model must satisfy the original request's hard constraints:

```text
privacy tier
region
modality
function calling
structured output
reasoning
context size
input/output constraints
cost ceiling
```

Never fall back from private to anonymized, from tool-capable to non-tool-capable, or from a compatible embedding model to another embedding space without explicit product logic.

For media, changing models can change accepted fields. Revalidate and, when available, re-quote before submitting the fallback.

## Circuit breaking

Track failures by route **and model**, not only by host.

Open a short circuit when:

- repeated `503`/provider failures affect one model;
- capacity is unavailable;
- deprecation or region errors become persistent;
- a Beta route's schema changes unexpectedly.

Continue model discovery and health checks at a low rate. Do not globally disable Venice because one provider-backed model is down.

## Observability fields

Record:

```text
timestamp
client request ID
Venice request ID / CF-RAY
endpoint and method
submitted model reference (trait/fixed/mapping)
resolved model ID
model privacy tier
status code
latency to headers
latency to first token/byte
total duration
retry count
input/output/cached token counts
media quote and final billed amount where available
queue_id for async jobs
rate-limit headers
balance headers
deprecation warning
error code/class
```

Do not record by default:

```text
Authorization header
API key or wallet private key
SIWE message/signature
raw prompts or completions
uploaded documents/media
base64 payloads
raw tool credentials or secrets
full blockchain signing keys
```

If prompt logging is a product requirement, make it explicit, access-controlled, encrypted, redacted, retention-limited, and consistent with the selected model's privacy claims.

## Cost controls

Implement three layers:

1. **Configuration ceiling:** maximum model price and permitted feature surcharges.
2. **Per-request estimate/quote:** token estimate for text or quote endpoint for media.
3. **Post-request reconciliation:** usage/billing ledger and returned cost headers.

For agent loops, add:

- maximum model turns;
- maximum tool calls;
- maximum cumulative tokens;
- maximum cumulative USD;
- maximum wall-clock duration;
- maximum web/X searches and scraped URLs;
- maximum media jobs.

Stop cleanly when any budget is exhausted.

## Security boundaries

### Prompt injection

Files, web pages, search results, tool outputs, character prompts, and blockchain data are untrusted. Keep platform/application policy in a higher-priority message and state that external content is data, not instructions.

### Tool calls

- validate against a local schema;
- authorize each operation;
- restrict filesystem/network/database scope;
- require confirmation for destructive or financially consequential actions;
- use deterministic transaction builders and simulators;
- return bounded, sanitized tool output.

### URL handling

Validate image/video/file/scrape URLs against SSRF and internal-network rules. Prefer application-controlled signed URLs with short expiry for private media.

### Media provenance

Respect consent, copyright, biometric/voice rights, and local law. Do not use voice cloning, face reference, or identity-preserving edit features without appropriate authorization.

## Compatibility testing

### Contract tests

Run against a nonproduction key with a strict limit:

- `/models?type=text` returns parseable rows;
- trait resolution returns usable IDs;
- minimal non-streaming chat succeeds;
- stream reaches `[DONE]`;
- function call round-trip succeeds;
- JSON schema output validates locally;
- one tiny embedding succeeds;
- one low-cost image path succeeds if used;
- binary content type is handled;
- async polling persists/reloads state if used;
- invalid request produces a typed `400`;
- expired/bad test credential produces typed `401` without leaking it.

### Model regression tests

For fixed IDs or traits, maintain prompts covering:

- instruction following;
- tool selection/arguments;
- structured output;
- long-context behavior;
- multimodal inputs;
- refusal/content behavior relevant to the product;
- latency and cost;
- privacy and region routing.

Run the suite when a trait target changes or a deprecation warning appears.

### Schema drift tests

Periodically compare generated clients/types with Venice's current OpenAPI spec. Treat Alpha/Beta/Preview route diffs as expected but review them before deployment.

## Deployment checklist

- [ ] Base URL is exactly `https://api.venice.ai/api/v1`.
- [ ] Runtime uses an inference key, not an admin key.
- [ ] Key expiration and `limitPeriod` are intentional.
- [ ] Models are discovered and checked for offline/beta/region/deprecation.
- [ ] Privacy routing is enforced before quality/cost routing.
- [ ] Request schema is validated locally.
- [ ] Timeouts and total deadlines exist.
- [ ] Retry policy is status-aware and bounded.
- [ ] Paid queue/write calls are deduplicated.
- [ ] Binary responses are content-type checked.
- [ ] Async media is downloaded before completion cleanup.
- [ ] SSE errors and partial tool calls are handled.
- [ ] Request IDs, usage, limits, and deprecations are logged.
- [ ] Sensitive content is redacted from logs.
- [ ] Cost and agent-loop ceilings are enforced.
- [ ] Contract/regression tests use a limited nonproduction key.

## Sources of truth

- API reference and headers: `https://docs.venice.ai/api-reference/api-spec`
- Error codes: `https://docs.venice.ai/api-reference/error-codes`
- Rate limits: `https://docs.venice.ai/api-reference/rate-limiting`
- Deprecations: `https://docs.venice.ai/overview/deprecations`
- OpenAPI YAML: `https://api.venice.ai/doc/api/swagger.yaml` (also linked from `https://docs.venice.ai/swagger.yaml`)
