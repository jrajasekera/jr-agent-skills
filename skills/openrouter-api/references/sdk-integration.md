# SDK Integration and Migration

OpenRouter supports official type-safe clients plus compatibility with common OpenAI and Anthropic SDKs.

## Official packages

| Language/use | Package | Install |
|---|---|---|
| TypeScript client | `@openrouter/sdk` | `npm install @openrouter/sdk` |
| Python client | `openrouter` | `pip install openrouter` |
| Go client | `github.com/OpenRouterTeam/go-sdk` | `go get github.com/OpenRouterTeam/go-sdk` |
| TypeScript agent loop | `@openrouter/agent` | `npm install @openrouter/agent` |

The client SDKs are generated from OpenRouter's OpenAPI and expose inference plus platform endpoints. Their generated method names/types can change when the specification changes; pin package versions and inspect release notes when upgrading.

The Agent SDK adds multi-turn loops, caller tool execution, stop conditions, and stream/result helpers. Use it when those abstractions are desirable; use the client SDK for direct API control.

## TypeScript client SDK

```typescript
import { OpenRouter } from "@openrouter/sdk";

const model = process.env.OPENROUTER_MODEL;
if (!model) throw new Error("OPENROUTER_MODEL is required");

const client = new OpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY ?? "",
  httpReferer: "https://your-app.example",
  appTitle: "Your App",
  appCategories: "cli-agent,programming-app",
});

const response = await client.chat.send({
  model,
  messages: [{ role: "user", content: "Explain MVCC." }],
});

console.log(response.choices[0]?.message.content);
console.log(response.model);
```

Generated SDK casing follows its current types and can differ from the raw JSON's snake_case. Let the installed package's type checker/autocomplete be authoritative.

## Python client SDK

```python
import os
from openrouter import OpenRouter

with OpenRouter(
    api_key=os.environ["OPENROUTER_API_KEY"],
    http_referer="https://your-app.example",
    x_open_router_title="Your App",
    x_open_router_categories="cli-agent,programming-app",
) as client:
    response = client.chat.send(
        model=os.environ["OPENROUTER_MODEL"],
        messages=[{"role": "user", "content": "Explain MVCC."}],
    )

print(response.choices[0].message.content)
print(response.model)
```

Use a context manager or explicitly close the client so pooled connections are released.

## Go client SDK

```go
package main

import (
    "context"
    "log"
    "os"

    openrouter "github.com/OpenRouterTeam/go-sdk"
)

func main() {
    client := openrouter.New(
        openrouter.WithSecurity(os.Getenv("OPENROUTER_API_KEY")),
    )

    _ = context.Background()
    _ = client
    log.Println("Use the generated operation types from the pinned SDK version")
}
```

Because generated Go operation packages/types are version-sensitive, copy the exact example from the installed SDK documentation for the endpoint being used rather than freezing an unverified struct name in a reusable skill.

---

# TypeScript Agent SDK

`@openrouter/agent` is intended for multi-turn workflows where tools should execute automatically under application-defined bounds.

```typescript
import { OpenRouter } from "@openrouter/agent";

const agent = new OpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY,
});

const result = agent.callModel({
  model: process.env.OPENROUTER_MODEL!,
  input: "Explain MVCC in one paragraph.",
});

console.log(await result.getText());
```

Tool definitions use the Agent SDK's current `tool()` helper and schema library. Add explicit stop conditions such as step count, cost, elapsed time, or a particular tool call. Do not rely only on a model deciding to stop.

Use the Agent SDK when:

- the app wants a managed caller-tool loop;
- streaming text/reasoning/tool events should be consumed through one result object;
- stop conditions and tool isolation are desirable;
- the team accepts an abstraction over raw Responses semantics.

Use the client SDK/raw REST when:

- exact wire compatibility matters;
- custom state, retries, stream parsing, or persistence is already implemented;
- using specialized media/admin endpoints;
- beta fields need immediate access before the Agent SDK supports them.

---

# OpenAI SDK compatibility

## Python

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
        "session_id": "conversation-123",
    },
)
```

## TypeScript

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
```

OpenRouter-only fields may not exist in OpenAI SDK types. Use the SDK's extension mechanism or a narrow augmented type. Do not delete routing/reasoning fields simply to satisfy stale SDK types.

OpenAI SDK compatibility is also useful for TTS. Dedicated OpenRouter STT/media endpoints can have shapes that differ from OpenAI; verify each endpoint.

---

# Anthropic SDK compatibility

OpenRouter exposes an Anthropic Messages skin at `/api/v1/messages`. Configure Anthropic SDKs with:

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  baseURL: "https://openrouter.ai/api",
  apiKey: process.env.OPENROUTER_API_KEY,
});
```

The `/api` base is intentional: Anthropic SDKs append their own versioned Messages path.

The Messages skin supports Anthropic-shaped messages, tools, thinking, and event streams while retaining OpenRouter fields such as provider routing, service tiers, and `fallbacks` through extension/beta request mechanisms.

Do not send Chat Completions' nested function tools to the Messages API without translating them to Anthropic tool blocks.

---

# Raw REST

Prefer raw REST when:

- a beta endpoint is absent from the installed SDK;
- exact headers/SSE events are needed;
- implementing in an unsupported language;
- minimizing dependencies;
- debugging SDK serialization.

Centralize raw requests in a small client that handles:

- base URL and auth;
- attribution and trace headers;
- timeouts and cancellation;
- retries for safe transient errors;
- JSON/non-JSON success bodies;
- SSE parsing;
- typed errors;
- generation/cache/routing metadata;
- secret redaction.

Do not scatter hand-written `fetch`/`requests` calls throughout an application.

---

# Migration from a direct provider

## OpenAI migration

1. Change base URL to `https://openrouter.ai/api/v1`.
2. Replace the API key with an OpenRouter inference key.
3. Replace model names with OpenRouter namespaced IDs or intentionally selected latest aliases.
4. Add attribution headers.
5. Move OpenRouter-only fields to the SDK extension body.
6. Inspect returned concrete model/provider and usage.
7. Test tool calling, reasoning, structured outputs, files, and streaming separately.
8. Add provider/fallback constraints only after baseline parity.

Common incompatibilities:

- direct-provider model ID is not an OpenRouter slug;
- provider-specific beta header/field is not normalized;
- OpenAI SDK strips unknown OpenRouter fields;
- an endpoint such as STT has a different body;
- direct provider returns a field in a different location.

## Anthropic migration

1. Use the Anthropic-compatible OpenRouter base.
2. Use an OpenRouter model slug.
3. Keep Messages-shaped blocks and streaming.
4. Put OpenRouter routing/fallback fields through the SDK extension mechanism.
5. Preserve thinking blocks and tool-use IDs exactly.
6. Verify `service_tier` in `usage` and OpenRouter typed errors.

## Generic OpenAI-compatible framework

Many frameworks accept:

```text
base_url = https://openrouter.ai/api/v1
api_key  = OPENROUTER_API_KEY
model    = author/model-slug
```

But frameworks often expose only a subset of fields. Confirm that they pass through:

- `provider`;
- `models`;
- `reasoning` and `reasoning_details`;
- `plugins`;
- server tools;
- multimodal typed parts;
- extra headers;
- SSE error events.

If they drop required fields, subclass the transport or call the official SDK directly.

---

# Versioning and upgrades

- Pin SDK versions in lockfiles.
- Subscribe to OpenRouter's changelog/RSS when operating production integrations.
- Re-run generated type checks when upgrading.
- Keep captured contract fixtures for each API skin.
- Validate that moving model aliases still meet capability/cost policy.
- Treat new additive response fields as compatible.
- Treat renamed methods/enums in generated SDKs as migration work.
- Run a live smoke test against a low-cost compatible model after upgrades.

## SDK choice checklist

| Question | Choice |
|---|---|
| Need raw endpoint parity and type safety? | Official client SDK |
| Need a managed TypeScript agent loop? | Agent SDK |
| Existing OpenAI app with minimal changes? | OpenAI SDK compatibility |
| Existing Anthropic/Claude Code client? | Messages skin + Anthropic SDK |
| Beta endpoint not yet in installed package? | Raw REST behind a local adapter |
| Need another language? | Raw REST/OpenAPI-generated client |

## Common mistakes

- Importing the wrong package (`@openrouter/sdk` vs `@openrouter/agent`).
- Assuming generated SDK method casing matches raw JSON.
- Copying an SDK example tied to an old generated version.
- Setting the Anthropic SDK base to `/api/v1` and producing a duplicated path.
- Letting a compatibility SDK silently drop OpenRouter-only fields.
- Returning an SDK object directly from a public API without normalizing/redacting it.
