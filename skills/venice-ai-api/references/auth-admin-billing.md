# Authentication, API-key administration, rate limits, billing, and x402/SIWX

Venice supports two primary request identities:

1. Bearer API keys associated with a Venice account;
2. x402/SIWX wallet authentication associated with an EVM/Base or Solana wallet and spendable credits.

Use separate client modules for these modes. Do not mix their balance, error, or credential assumptions.

## Bearer authentication

```http
Authorization: Bearer <VENICE_API_KEY>
```

Server-side example:

```python
import os
import requests

session = requests.Session()
session.headers.update(
    {
        "Authorization": f"Bearer {os.environ['VENICE_API_KEY']}",
        "User-Agent": "my-service/1.0",
    }
)
```

Security rules:

- Store keys in a secret manager or environment injection, not source control.
- Never expose a Bearer key in browser/mobile code that users can inspect.
- Use a separate inference key per environment, service, or customer boundary.
- Set a consumption limit and expiration where practical.
- Keep an admin key out of inference workloads.
- Rotate on employee departure, suspected leakage, repository exposure, or logging incidents.
- Redact the full key and authorization header from traces and error reports.

## API-key types

| Type | Intended scope |
|---|---|
| `INFERENCE` | Inference and authenticated non-admin surfaces |
| `ADMIN` | Inference plus key management and account-level billing routes |

Least privilege: application runtimes should normally receive an `INFERENCE` key. Keep `ADMIN` keys in a dedicated control-plane service.

## API-key endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api_keys` | List keys with masked metadata |
| `POST /api_keys` | Create a key; response contains the only copy of the secret |
| `PATCH /api_keys` | Update description, expiration, limit, or limit period |
| `DELETE /api_keys?id=<id>` | Revoke a key |
| `GET /api_keys/{id}` | Inspect one key's metadata and usage |
| `GET /api_keys/rate_limits` | Current key access, balances, model limits, and reset metadata |
| `GET /api_keys/rate_limits/log` | Recent limit breaches |
| `GET /api_keys/generate_web3_key`, `POST /api_keys/generate_web3_key` | Wallet-signed API-key minting flow |

### Create a scoped inference key

```bash
curl -sS https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "apiKeyType": "INFERENCE",
    "description": "production image worker",
    "consumptionLimit": {
      "usd": 25,
      "diem": 10
    },
    "limitPeriod": "MONTH",
    "expiresAt": "2027-01-01T00:00:00Z"
  }'
```

The current limit windows are:

- `EPOCH` — legacy daily/UTC epoch reset;
- `MONTH` — reset on the first day of the UTC calendar month;
- `LIFETIME` — permanent cumulative cap.

`VCU` is a legacy field. Generate new clients with `diem`, not `vcu`.

The secret appears only in the create response. Write it directly to the destination secret store and discard it from process memory as soon as practical. Never log the JSON response.

### Update a key

```bash
curl -sS -X PATCH https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "<uuid>",
    "description": "production image worker v2",
    "consumptionLimit": {"usd": 40},
    "limitPeriod": "MONTH"
  }'
```

Set `expiresAt` to `null` or the current documented empty representation only when intentionally removing expiration.

### Revoke a key

```bash
curl -sS -X DELETE \
  "https://api.venice.ai/api/v1/api_keys?id=<uuid>" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY"
```

Revocation should be immediate in application policy. Stop scheduling new calls before invoking it and invalidate any local connection/session cache.

## Current rate limits

Do not copy a global RPM/TPM table into code. Query the calling key:

```bash
curl -sS https://api.venice.ai/api/v1/api_keys/rate_limits \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

The response can include:

- `accessPermitted`;
- API tier and charge state;
- balances;
- key expiration;
- next reset/epoch time;
- per-model RPM, TPM, RPD, or other limits.

Use this endpoint for startup diagnostics and dashboards. Use response headers for real-time control because limits and remaining capacity can change after discovery.

Recent breaches:

```bash
curl -sS https://api.venice.ai/api/v1/api_keys/rate_limits/log \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

The log is bounded and not a replacement for application telemetry.

## Account billing endpoints

Billing APIs are Beta. Keep their response parsing tolerant and validate against the current OpenAPI schema.

| Endpoint | Purpose |
|---|---|
| `GET /billing/balance` | Account-level consumability and DIEM/USD/bundled balance state |
| `GET /billing/usage-history` | Preferred cursor-paginated usage ledger; JSON or CSV |
| `GET /billing/usage` | Deprecated page-number ledger; do not use for new integrations |
| `GET /billing/usage-analytics` | Aggregated totals by date, model, and API key |

Account-level balance and usage routes can require an `ADMIN` key. Do not assume an inference key has access.

### Balance

```bash
curl -sS https://api.venice.ai/api/v1/billing/balance \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY"
```

Example fields:

```json
{
  "canConsume": true,
  "consumptionCurrency": "DIEM",
  "balances": {
    "diem": 90.5,
    "usd": 25
  },
  "diemEpochAllocation": 100
}
```

Do not reduce the account to one numeric balance. Actual request funding can consider DIEM, bundled credits, USD, product entitlements, per-key limits, and model access. The definitive test is whether the request is accepted; preflight checks only reduce avoidable failures.

### Usage history (preferred)

Use the keyset-paginated replacement endpoint for new integrations:

```bash
curl -sS \
  "https://api.venice.ai/api/v1/billing/usage-history?currency=USD&startTimestamp=2026-07-01T00:00:00.000Z&endTimestamp=2026-08-01T00:00:00.000Z&pageSize=1000" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Accept: application/json"
```

The first request can use:

| Parameter | Contract |
|---|---|
| `currency` | Optional: `USD`, `DIEM`, or `BUNDLED_CREDITS` |
| `startTimestamp` | Optional inclusive lower bound |
| `endTimestamp` | Optional exclusive upper bound |
| `pageSize` | 10–1000; current default 1000 |

JSON responses contain the ledger rows and an opaque continuation cursor:

```json
{
  "data": [
    {
      "timestamp": "2026-07-24T12:34:56.000Z",
      "sku": "<billing-sku>",
      "pricePerUnitUsd": 0.1,
      "units": 1,
      "amount": -0.1,
      "currency": "USD",
      "notes": "API Inference",
      "inferenceDetails": {
        "requestId": "chatcmpl-...",
        "promptTokens": 100,
        "completionTokens": 50,
        "inferenceExecutionTime": 1200
      }
    }
  ],
  "nextCursor": "<opaque-or-null>"
}
```

Continue with **only** the returned cursor:

```bash
curl -sS \
  "https://api.venice.ai/api/v1/billing/usage-history?cursor=$NEXT_CURSOR" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Accept: application/json"
```

Cursor rules:

- rows are returned in ascending timestamp order;
- do not resend `currency`, timestamp bounds, or `pageSize` with a continuation cursor;
- do not decode, edit, sort, or persist assumptions about the opaque cursor format;
- there is no total-count contract—read until `nextCursor` is absent or `null`;
- keyset pages remain stable while new usage is appended, avoiding page-number drift;
- for `Accept: text/csv`, read the continuation from the `x-next-cursor` response header.

Useful ledger data includes timestamp, SKU, units, unit price, debit amount/currency, request ID, token counts, and execution time. Join records to application requests using the returned request ID when available; do not reconcile solely by timestamp and amount.

`GET /billing/usage` is deprecated, capped at five requests per minute per user, and scheduled for removal. Accounts created on or after **2026-07-07** receive `410 Gone` and must use `/billing/usage-history`. Keep the legacy route only while migrating an older client.

### Usage analytics

```bash
curl -sS \
  "https://api.venice.ai/api/v1/billing/usage-analytics?lookback=30d" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Current analytics can aggregate by date, model, and key and is cached for about 10 minutes, so it can lag recent activity. Use the ledger for audit/reconciliation and analytics for dashboards.

## Response-level cost and balance headers

Depending on endpoint and auth mode, responses can include:

- account USD/DIEM balance headers;
- `X-Balance-Remaining` for wallet credit;
- request/token rate-limit headers;
- model deprecation warnings;
- `X-Request-ID` or `CF-RAY` correlation values;
- crypto-RPC credit and USD-cost headers.

Header names and availability vary by route. Normalize them case-insensitively and keep unknown `x-venice-*` metadata for diagnostics without making the request fail.

## x402/SIWX wallet authentication

x402 lets an EVM wallet on Base or a Solana wallet authenticate and pay without a conventional Venice account/API key. Wallet credit is prepaid and wallet-bound; keep it separate from Bearer-account balances.

### Header migration

Current endpoint contracts prefer:

```http
SIGN-IN-WITH-X: <base64-encoded signed SIWX payload>
```

The legacy header below is still accepted during migration and is still emitted by some current guides/SDK versions:

```http
X-Sign-In-With-X: <base64-encoded signed SIWX payload>
```

Treat header names case-insensitively, but emit `SIGN-IN-WITH-X` in new direct integrations. Do not send both names in the same request.

### Prefer the current supported client

The newest endpoint reference advertises the scoped client package:

```bash
npm install @venice-ai/x402-client
```

```typescript
import { VeniceClient } from "@venice-ai/x402-client";

const venice = new VeniceClient(process.env.EVM_PRIVATE_KEY!);

await venice.topUp(10); // only when the wallet needs spendable credit
const response = await venice.chat({
  model: "default",
  messages: [{ role: "user", content: "Hello from a wallet-authenticated agent." }],
});
```

Some older Venice guide pages still show the legacy unscoped package name `venice-x402-client`. Prefer `@venice-ai/x402-client` for new work, verify the installed version's exports, and do not mix imports or lockfile entries from both packages.

This quick-start path is EVM-oriented. For Solana, use the current SIWX and x402 payment tooling that supports Ed25519/Solana rather than forcing a Solana key into an EVM helper.

Use a dedicated automation wallet with a deliberately limited balance. Do not use an organization's main treasury key in an agent process.

### Build the SIWX identity payload

For **EVM/Base**:

- sign an EIP-4361 SIWE message;
- use domain `api.venice.ai`, URI `https://api.venice.ai`, version `1`, and chain ID `8453`;
- use the current statement (`Sign in to Venice API`), a fresh nonce, and a short issued/expiration window (the current endpoint reference recommends about 10 minutes);
- include address, prepared message, signature, timestamp, and chain ID in the base64 JSON payload.

For **Solana**:

- sign the Solana SIWX message with Ed25519;
- set `chainId` to `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp`;
- include `type: "ed25519"` in the encoded JSON payload;
- encode the signature as base58 or base64;
- use the standard URI, version, chain ID, nonce, issued-at, and optional expiration fields.

Generate a fresh payload for each short request flow. Never replay one across machines or hours. The protected wallet path must match the signer. Use a wallet provider or HSM/KMS-backed signer where possible; never embed a raw private key in browser code.

### Supported routes

Many paid inference routes accept SIWX, including chat, Responses, images, embeddings, audio, video, augment, and crypto RPC. Coverage evolves. A route's current API reference is authoritative—do not assume account/admin endpoints accept wallet auth.

## x402 wallet balance and ledger

```bash
curl -sS \
  "https://api.venice.ai/api/v1/x402/balance/$WALLET_ADDRESS" \
  -H "SIGN-IN-WITH-X: $X402_AUTH"
```

```bash
curl -sS \
  "https://api.venice.ai/api/v1/x402/transactions/$WALLET_ADDRESS?limit=50&offset=0" \
  -H "SIGN-IN-WITH-X: $X402_AUTH"
```

The signer must match the EVM `0x...` or Solana base58 wallet address in the path. Transaction types can include:

- `TOP_UP` — credit added;
- `CHARGE` — paid request;
- `REFUND` — failed request reversal or adjustment.

Use request/model IDs from the ledger when reconciling agent spend.

## x402 top-up flow

1. `POST /x402/top-up` with no payment header to discover current payment requirements.
2. Parse the returned `402` body/header.
3. Use the x402 SDK to sign the exact USDC authorization.
4. Repeat `POST /x402/top-up` with the preferred `PAYMENT-SIGNATURE` header. Legacy `X-402-Payment` and `X-PAYMENT` names are accepted during migration.
5. Confirm credited amount and new balance before retrying inference.

Do not hardcode:

- receiver wallet;
- USDC contract address;
- minimum top-up;
- payment scheme/version;
- amount precision;
- network representation.

Take them from the discovery response. The current `accepts` array can contain Base and Solana USDC options; select and sign one exact option rather than hardcoding either network.

### Distinguish the two 402 forms

An inference request with insufficient wallet credit can return:

- a JSON body with `code: "PAYMENT_REQUIRED"` and human/actionable top-up fields;
- a `PAYMENT-REQUIRED` response header containing a base64-encoded x402 protocol object.

These are not the same payload. Protocol clients parse the header; user-facing applications can present the richer body.

A Bearer request with insufficient account balance returns a different, simpler 402 form. Do not route Bearer failures into the wallet top-up flow.

## Wallet and key funding are separate

Keep these accounting domains distinct:

- Bearer-account DIEM;
- Bearer-account bundled credits;
- Bearer-account USD;
- x402 wallet USDC credit;
- any DIEM linked to a wallet account.

Use `/billing/*` for Bearer-account accounting and `/x402/*` for wallet accounting.

## Autonomous Web3 API keys

Venice also exposes a wallet-signed flow under `/api_keys/generate_web3_key` that can mint a conventional Bearer key for an eligible staking wallet. This is separate from x402 request authentication.

High-level flow:

1. fetch a short-lived token;
2. sign it with the eligible wallet;
3. submit address, signature, token, key type, description, and limits;
4. store the returned API key once.

Check current staking/eligibility requirements and never assume a wallet can mint a key merely because it can use x402.

## Credential incident response

When a Bearer key leaks:

1. revoke it immediately;
2. create a replacement with narrower scope/limits;
3. rotate every deployment secret;
4. search logs, CI output, artifacts, and repository history;
5. review billing usage and rate-limit logs for abuse;
6. invalidate cached clients and restart workers;
7. document the incident.

When a wallet private key leaks:

1. stop all signers;
2. move funds and privileges to a new wallet using deterministic, reviewed transactions;
3. revoke linked API keys where possible;
4. rotate every secret copy and deployment;
5. inspect x402 and on-chain ledgers;
6. assume signatures can be forged until migration is complete.

## Sources of truth

- Generate keys: `https://docs.venice.ai/guides/getting-started/generating-api-key`
- Create key: `https://docs.venice.ai/api-reference/endpoint/api_keys/create`
- Update key: `https://docs.venice.ai/api-reference/endpoint/api_keys/update`
- Rate limits: `https://docs.venice.ai/api-reference/endpoint/api_keys/rate_limits`
- Billing balance: `https://docs.venice.ai/api-reference/endpoint/billing/balance`
- Billing usage history: `https://docs.venice.ai/api-reference/endpoint/billing/usage-history`
- Deprecated billing usage: `https://docs.venice.ai/api-reference/endpoint/billing/usage`
- Billing analytics: `https://docs.venice.ai/api-reference/endpoint/billing/usage-analytics`
- x402 guide: `https://docs.venice.ai/guides/integrations/x402-venice-api`
- Wallet balance: `https://docs.venice.ai/api-reference/endpoint/x402/balance`
- Wallet transactions: `https://docs.venice.ai/api-reference/endpoint/x402/transactions`
- Wallet top-up: `https://docs.venice.ai/api-reference/endpoint/x402/top-up`
