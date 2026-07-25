# API Endpoint Inventory

Base URL:

```text
https://openrouter.ai/api/v1
```

This inventory covers the principal public surfaces verified on **2026-07-25**. It is intentionally not a substitute for the live OpenAPI specification. New beta endpoints, fields, and variants may appear without this file changing.

```bash
python scripts/inspect_openapi.py --list
python scripts/inspect_openapi.py --search workspace
python scripts/inspect_openapi.py --path /responses
```

## Authentication conventions

Most authenticated endpoints use:

```http
Authorization: Bearer $OPENROUTER_API_KEY
```

Management operations require a management/provisioning key where documented. Public discovery endpoints such as the general models catalog usually work without a key, but an authenticated request can reveal user-specific availability.

---

# Inference API skins

| Method and path | Purpose | Success body |
|---|---|---|
| `POST /chat/completions` | OpenAI-compatible chat, multimodal input, reasoning, structured output, tools, routing | Chat-completion JSON or SSE |
| `POST /responses` | OpenAI Responses-compatible typed items and server tools | Response JSON or typed SSE events |
| `POST /messages` | Anthropic Messages-compatible requests | Message JSON or Anthropic-style SSE |
| `POST /completions` | Legacy text completion compatibility | Completion JSON or SSE |

Do not mix request/response fields between skins. See [chat-completions.md](chat-completions.md), [responses-api.md](responses-api.md), and [streaming.md](streaming.md).

## Presets

Preset resources and preset-specific inference variants are exposed under `/presets`. Their exact methods and surface-specific paths evolve; search the live OpenAPI for `preset` before implementing them. A preset can centralize model/routing/generation policy, but code should still record the resolved model and validate required capabilities.

---

# Retrieval and ranking

| Method and path | Purpose |
|---|---|
| `POST /embeddings` | Generate embeddings from text or supported multimodal inputs |
| `GET /embeddings/models` | List embedding models and embedding-specific metadata |
| `POST /rerank` | Rank documents against a query |

Discover compatible models from `GET /models` using output modalities and supported parameters. See [embeddings-rerank.md](embeddings-rerank.md).

---

# Dedicated media

| Method and path | Purpose | Body/response note |
|---|---|---|
| `POST /images` | Generate or edit images | JSON request; base64 image data in JSON response; streaming is model/endpoint-specific |
| `GET /images/models` | List dedicated Image API models/capabilities | Public discovery |
| `GET /images/models/{author}/{slug}/endpoints` | Inspect per-provider image controls and pricing | Validate every optional control |
| `POST /audio/speech` | Text-to-speech | JSON request; raw audio bytes on success |
| `POST /audio/transcriptions` | Speech-to-text | Accepts JSON/base64 or OpenAI-style `multipart/form-data` |
| `POST /videos` | Submit asynchronous video generation | Returns job ID/polling information |
| `GET /videos/{jobId}` | Poll video job | JSON status |
| `GET /videos/{jobId}/content` | Download completed output | Raw media; exact index/query fields are schema-defined |
| `GET /videos/models` | List video models and accepted controls | Public discovery |

See [multimodal-media.md](multimodal-media.md).

---

# Files

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /files` | List workspace files | Cursor pagination; optional `workspace_id` |
| `POST /files` | Upload a reusable file | `multipart/form-data`; current maximum is schema-defined |
| `GET /files/{file_id}` | Retrieve metadata | Workspace-scoped |
| `DELETE /files/{file_id}` | Delete a file | Irreversible |
| `GET /files/{file_id}/content` | Download raw bytes | Only server-created downloadable files may support it |

Uploaded files are stored under a workspace and can be referenced by supported inference surfaces. Treat file IDs as access-controlled resources, not public URLs. Verify retention, purpose, and accepted file-reference shape in the current endpoint schema.

---

# Model and provider discovery

| Method and path | Purpose |
|---|---|
| `GET /models` | Filterable, optionally paginated public model catalog |
| `GET /models/count` | Count models matching the requested output modality |
| `GET /models/user` | Models and settings available to the current user |
| `GET /model/{author}/{slug}` | One model's metadata; note singular `model` |
| `GET /models/{author}/{slug}/endpoints` | Provider endpoints, pricing, status, latency/throughput, supported parameters |
| `GET /providers` | Provider catalog/status metadata |
| `GET /endpoints/zdr` | Preview ZDR-eligible endpoint information; management key required |
| `GET /images/models*` | Image-specific discovery |
| `GET /videos/models*` | Video-specific discovery |

Use the helper instead of hardcoding query strings:

```bash
python scripts/discover_models.py --query coding --parameter tools
python scripts/discover_models.py --endpoints 'author/model' --json
```

Model aliases, router membership, availability, prices, and provider statistics are live data.

---

# Keys, credits, OAuth, and BYOK

| Method and path | Purpose | Credential |
|---|---|---|
| `GET /key` | Metadata for the current key | Inference or management key |
| `GET /keys` | List API keys | Management key |
| `POST /keys` | Create API key | Management key |
| `GET /keys/{hash}` | Get key metadata | Management key |
| `PATCH /keys/{hash}` | Update key | Management key |
| `DELETE /keys/{hash}` | Delete key | Management key |
| `GET /credits` | Credit balance/usage | Management key |
| `POST /auth/keys` | Exchange an OAuth authorization code/PKCE verifier for an API key | OAuth exchange |
| `/byok*` | Manage encrypted upstream provider credentials | Management key |

The plaintext secret from key creation/exchange is a one-time sensitive value. See [auth-admin-observability.md](auth-admin-observability.md).

---

# Usage, analytics, and observability

| Method and path | Purpose |
|---|---|
| `GET /generation?id=<id>` | Generation metadata, usage, cost, routing, and timing |
| `GET /generation/content?id=<id>` | Stored prompt/completion content when available |
| `GET /activity` | Account activity data |
| `GET /analytics/meta` | Discover analytics metrics/dimensions/operators |
| `POST /analytics/query` | Query aggregate analytics |
| `/observability*` | Configure/list observability destinations and filters as defined by current schema |

Prefer response-level IDs and metadata for ordinary monitoring. Fetch generation content only for a specific authorized debugging need.

---

# Organization policy

| Resource family | Purpose |
|---|---|
| `/workspaces*` | Workspace lifecycle, members, budgets, and scope |
| `/guardrails*` | Central model/provider/privacy/budget/content policy and assignments |
| `/classifiers*` or classifier resources in the current schema | Custom classifier definitions and policy integration |

These are high-impact management endpoints. Read-before-write, use immutable IDs, handle pagination, and audit changes.

---

# Other evolving resources

OpenRouter's platform/OpenAPI may also expose resources for:

- broadcast and batch-style workflows;
- organization/enterprise administration;
- model/provider configuration and routing resources;
- logging and observability destinations;
- custom classifiers;
- asynchronous job/webhook operations;
- experiments, evaluations, or other beta products.

Do not infer a path from a UI label. Search the OpenAPI and use the exact operation/path currently published.

---

# Content-type rules

| Surface | Request | Success response |
|---|---|---|
| Chat/Responses/Messages/Embeddings/Rerank | `application/json` | JSON or `text/event-stream` |
| Image API | `application/json` | JSON, or stream when supported/requested |
| TTS | `application/json` | Audio bytestream |
| STT | `application/json` with base64 audio, or `multipart/form-data` | JSON transcript/segments |
| Video submit/poll | `application/json` | JSON |
| Video/file download | No JSON body | Raw bytes |
| File upload | `multipart/form-data` | JSON metadata |

Never call `.json()` unconditionally on a raw-byte success. Conversely, non-2xx media responses are normally JSON errors and should be read before deleting a partially written output file.

# Endpoint-selection checklist

1. Is the request using the correct API skin and content type?
2. Was the endpoint/method verified in the current OpenAPI?
3. Does the selected model advertise every modality and parameter?
4. Is the supplied credential type sufficient but not overprivileged?
5. Is the operation synchronous, streamed, or asynchronous?
6. Is the success body JSON, SSE, or bytes?
7. Does the operation need cursor/offset pagination?
8. Is a workspace ID required or implicitly selected?
9. Are idempotency, callback verification, and retries defined for writes/jobs?
10. Are beta response types decoded additively?
