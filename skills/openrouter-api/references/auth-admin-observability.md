# Authentication, Administration, and Observability

OpenRouter separates ordinary inference credentials from management operations. Treat every credential as a secret and keep management credentials on a trusted server.

## Credential classes

| Credential or flow | Primary purpose | Where it belongs |
|---|---|---|
| Inference API key | Model calls, file access, and self-inspection through `GET /key` | Server-side runtime; a user-authorized browser only when the product deliberately uses OpenRouter OAuth |
| Management/provisioning key | Create/manage keys, credits, workspaces, guardrails, analytics, BYOK, and other account controls | Trusted backend or administrator workstation only |
| OAuth PKCE-issued API key | Let an end user authorize an OpenRouter key for an application | Store encrypted; scope use to that user and application |
| BYOK provider credential | Route requests through a user-supplied upstream provider key | Submit only through the management API; never log or expose it after creation |

Do not infer privilege from a key's text prefix. Call the intended endpoint and handle `401`/`403` without falling back to a more privileged key in client code.

## Bearer authentication

```http
Authorization: Bearer $OPENROUTER_API_KEY
```

Recommended app-attribution headers:

```http
HTTP-Referer: https://your-app.example
X-OpenRouter-Title: Your App
X-OpenRouter-Categories: cli-agent,programming-app
```

- `X-OpenRouter-Title` is preferred for new integrations.
- `X-Title` is a legacy compatibility alias.
- Categories are comma-separated. Use only categories that accurately describe the application.
- Attribution is not an authentication mechanism and must not contain secrets or user PII.

## Secret handling

- Load keys from a secret manager or runtime environment, not source code or committed `.env` files.
- Use separate keys for development, CI, staging, and production.
- Apply key spend limits and expiration dates where practical.
- Encrypt user-authorized keys at rest and limit which service can decrypt them.
- Redact `Authorization`, OAuth codes/verifiers, provider credentials, and raw key-creation responses from logs and traces.
- Rotate keys after suspected disclosure. Disabling or deleting a key is safer than relying on application-side denial lists.

---

# Sign in with OpenRouter: OAuth PKCE

Use OAuth PKCE when users should authorize their own OpenRouter key. The flow does not require a client secret, but it still requires normal OAuth protections.

## Browser flow

1. Generate a cryptographically random `code_verifier`.
2. Derive `code_challenge = BASE64URL(SHA256(code_verifier))`.
3. Store the verifier and a one-time pending-flow marker in session-scoped storage.
4. Redirect the browser using the documented parameters:

```text
https://openrouter.ai/auth?callback_url=<URL>&code_challenge=<CHALLENGE>&code_challenge_method=S256
```

5. On the callback, process `code` only when the same browser session has a pending verifier/flow marker. OpenRouter's documented URL does not define a dedicated `state` parameter, so do not rely on an undocumented parameter being echoed.
6. Exchange the code:

```http
POST https://openrouter.ai/api/v1/auth/keys
Content-Type: application/json
```

```json
{
  "code": "authorization-code",
  "code_verifier": "original-pkce-verifier",
  "code_challenge_method": "S256"
}
```

7. Store the returned `key` securely, remove the one-time verifier/pending marker, and strip the authorization code from the URL.

## OAuth rules

- Prefer `S256`; do not use `plain` unless current documentation explicitly requires it for a constrained environment.
- Store the verifier in session-scoped storage, not a long-lived shared location.
- Reject unsolicited callbacks for which no flow is pending.
- Expire the pending-flow marker and verifier quickly. When stronger CSRF correlation is needed, encode application state in a callback route or server session that you control and verify its round trip; do not add undocumented authorization parameters.
- Use an exact HTTPS callback URL in production.
- Do not put the issued API key in a URL, analytics event, browser error report, or client-visible server log.
- OAuth gives the application an API key; it is not an identity token. Use a separate identity system if the application needs stable user authentication claims.

---

# API-key administration

Management-key operations:

| Operation | Method and path | Important behavior |
|---|---|---|
| Inspect current key | `GET /key` | Works for the key used on the request; useful for limits, usage, and status |
| List keys | `GET /keys` | Management key required |
| Create key | `POST /keys` | Plaintext key is returned only in the creation response |
| Get one key | `GET /keys/{hash}` | Uses the key hash/identifier, not the plaintext secret |
| Update key | `PATCH /keys/{hash}` | Update name, limit/reset policy, disabled state, and other fields published by the current schema |
| Delete key | `DELETE /keys/{hash}` | Irreversible; confirm the target hash and environment |

Example creation body; verify the live schema before relying on optional fields:

```json
{
  "name": "production-service",
  "limit": 50,
  "limit_reset": "monthly",
  "include_byok_in_limit": true,
  "expires_at": "2027-01-01T00:00:00Z"
}
```

Immediately write the returned plaintext key into a secret store and discard the response body. Never expect a later GET to reveal it.

## Credits and activity

| Need | Endpoint | Credential |
|---|---|---|
| Credit balance/usage | `GET /credits` | Management key |
| Account activity summary | `GET /activity` | Management key |
| One generation's metadata | `GET /generation?id=<generation_id>` | Authorized key |
| Stored generation content | `GET /generation/content?id=<generation_id>` | Authorized key; unavailable when content was not stored/ZDR applies |

Generation content can contain complete prompts, outputs, tool arguments, and user data. Fetch it only for an explicit operational need, apply access controls, and do not copy it into general logs.

---

# Workspaces

Workspaces isolate keys, files, budgets, members, provider credentials, guardrails, and related settings. The current management API includes operations under `/workspaces` for listing, creating, reading, updating, deleting, and managing members.

Operational guidance:

- Resolve and store the workspace UUID; do not key authorization logic only by a mutable display name.
- Pass `workspace_id` only on endpoints whose current schema supports it.
- Enforce least privilege for members and automation keys.
- Use workspace budgets as a backstop, not as the only cost-control mechanism.
- Treat bulk add/remove-member calls as high-impact operations requiring an audit trail.
- Reconcile workspace membership and key assignments periodically.

Because workspace endpoints are evolving, inspect the live OpenAPI before constructing member/budget payloads.

---

# Guardrails

Guardrails can centrally constrain models/providers, budgets, privacy requirements, and supported content filters. Management operations live under `/guardrails`; assignment endpoints associate guardrails with API keys or organization members.

Use guardrails for organization policy, then retain application-level validation for request-specific safety and correctness.

Safe workflow:

1. Read the current guardrail schema and existing object.
2. Build a minimal patch rather than replacing unknown fields.
3. Validate model/provider identifiers against live metadata.
4. Test with a non-production key/workspace.
5. Assign by immutable key hash/member ID.
6. Verify both allowed and denied requests.
7. Record who changed the policy and why.

Do not assume a `403` is always moderation. It may reflect a guardrail, missing management privilege, workspace policy, provider policy, region, or another authorization decision.

---

# BYOK provider credentials

The management API exposes BYOK operations for storing upstream provider credentials. OpenRouter encrypts the raw provider key and does not return it later.

- Create credentials only from a trusted backend.
- Scope them to the intended workspace.
- Use a clear non-secret name and the exact provider slug.
- Confirm whether OpenRouter fees, key limits, and guardrails include BYOK usage.
- Rotate by creating a replacement, testing it, switching traffic, and deleting the old credential.
- Do not use an OpenRouter inference key where the endpoint requires a management key.

Provider routing may expose whether a request used BYOK in usage/router metadata. Do not expose that metadata if it reveals account topology to an untrusted user.

---

# Analytics

OpenRouter's analytics API is schema-driven:

| Endpoint | Purpose |
|---|---|
| `GET /analytics/meta` | Discover current metrics, dimensions, filters, operators, and granularities |
| `POST /analytics/query` | Run an analytics query |

A management key is required. Always query metadata before generating a durable analytics query because metrics and dimensions can evolve.

For reports:

- define an explicit UTC time range;
- identify whether the range is complete or still in progress;
- check response truncation/pagination metadata;
- distinguish OpenRouter credits, BYOK cost/fees, cache, web/file/tool, and upstream components;
- state the currency/unit for every metric;
- avoid summing pre-aggregated rows across incompatible dimensions;
- use generation IDs to drill down only when authorized and necessary.

---

# Observability destinations

OpenRouter can forward observability data to configured destinations. Management operations and supported providers are represented in the live OpenAPI/SDK under observability resources.

When configuring a destination:

- prefer metadata-only/privacy mode unless prompt/output forwarding is required;
- set a sampling rate intentionally;
- restrict by workspace, application, or API-key hash where supported;
- store destination credentials as secrets;
- verify whether retries can duplicate exported events;
- document retention and access controls at the destination;
- never assume ZDR at model providers automatically prevents a separately configured observability export.

---

# Request-level observability

Capture the following fields where available:

| Field | Why it matters |
|---|---|
| Your trace/correlation ID | Join application logs without relying on prompt content |
| `X-Generation-Id` and response `id` | Support/debug lookup and cost reconciliation |
| Requested model and returned `model` | Detect alias/router/fallback resolution |
| Provider and service tier | Explain latency, availability, and cost differences |
| Finish/native finish reason | Distinguish normal stop, length, tool call, filter, and provider failure |
| Token, cache, image/audio/video/tool usage and `cost` | Billing and optimization |
| `X-OpenRouter-Cache-Status`, age, TTL | Diagnose response-cache behavior |
| Typed `error_type`, HTTP status, `Retry-After` | Stable failure classification |
| Router metadata | Inspect candidate filtering, attempts, transforms, guardrails, and server tools |

Enable router metadata per request:

```http
X-OpenRouter-Metadata: enabled
```

Decode `openrouter_metadata` as an additive tagged structure: accept unknown stage types and fields. Cache hits omit router metadata because replaying a previous routing trace could be misleading.

## Privacy-safe identifiers

Use a stable, pseudonymous end-user ID in request fields intended for abuse/rate analysis. Do not send email addresses, full names, access tokens, or raw database keys. Rotate or namespace IDs when crossing tenants.

## Logging policy

Log:

- endpoint, method, timeout, retry number;
- model/provider/service tier;
- generation/trace IDs;
- token/media/tool counts and cost;
- status, typed error, latency, cache state.

Do not log by default:

- API keys or OAuth artifacts;
- full prompts/completions;
- file/audio/image/video bytes or URLs containing signatures;
- raw tool arguments/results;
- hidden reasoning or encrypted reasoning blocks;
- full generation-content responses.

## Rate limits and retries

Rate limits depend on account, key, model, provider, endpoint, and current platform policy. Do not freeze a numeric table in code.

- Inspect `GET /key` and response rate-limit/retry headers.
- Honor `Retry-After` when present.
- Use bounded exponential backoff with jitter for `429`, `502`, and `503` where the operation is safe to repeat.
- Do not retry `400`, `401`, `402`, or policy `403` unchanged.
- Use an idempotency strategy for administrative writes and asynchronous media submissions.
- Never allow retries to exceed the caller's total deadline or cost budget.

## Administration checklist

Before shipping an administrative integration:

1. The endpoint and request schema were verified in the current OpenAPI.
2. A management key is used only on a trusted server.
3. Every write is scoped to the intended workspace/object ID.
4. Plaintext keys and provider credentials are captured once into a secret store and then redacted.
5. Destructive actions require an explicit target and audit entry.
6. Pagination/truncation is handled before reporting totals.
7. ZDR, logging, observability exports, and generation-content access were evaluated separately.
8. `401`, `403`, `409`, `429`, and partial/bulk failures have explicit handling.
