# Models, Providers, Routing, and Fallbacks

OpenRouter's routing layer can select among models, aliases, routers, providers, endpoint variants, quantizations, data policies, and service tiers. This is powerful but creates a central invariant: **every request must be validated against live metadata**.

## Live discovery endpoints

```text
GET /api/v1/models
GET /api/v1/models/user
GET /api/v1/model/{author}/{slug}
GET /api/v1/models/{author}/{slug}/endpoints
GET /api/v1/providers
GET /api/v1/endpoints/zdr  # management/provisioning key
```

Dedicated image and video catalogs expose additional media-specific controls:

```text
GET /api/v1/images/models
GET /api/v1/images/models/{author}/{slug}/endpoints
GET /api/v1/videos/models
```

Use the included helper rather than manually scrolling a web catalog:

```bash
python scripts/discover_models.py --query code --parameter tools
python scripts/discover_models.py --model 'author/model' --json
python scripts/discover_models.py --endpoints 'author/model' --json
```

## Model metadata that matters

A model record can include:

- `id` and `canonical_slug`;
- display name, description, creation timestamp, knowledge cutoff, and expiration date;
- `context_length` and top-provider output limit;
- input/output modalities and tokenizer/architecture information;
- prompt, completion, request, image, audio, reasoning, web, and cache pricing fields, plus conditional `pricing.overrides`;
- supported API parameters and default parameters;
- model-level reasoning capabilities and allowed efforts;
- links to per-provider endpoint details;
- benchmark and popularity metadata.

Treat all fields as additive and nullable. Prices are commonly returned as decimal strings in USD per token or per unit; convert token prices to per-million only for display. Inspect `pricing.overrides` before estimating cost: it can apply different prices above a prompt-token threshold or during a UTC time window. All conditions in an override must match, absent price keys inherit the base value, and later matching overrides win per key.

## Concrete IDs vs latest aliases

### Concrete model ID

```text
author/model-version
```

Use for:

- production regressions and evaluations;
- prompt baselines;
- deterministic routing requirements;
- legal/compliance review tied to a specific provider/model;
- comparing costs or latency over time.

### Latest family alias

```text
~author/family-latest
```

Use only when automatic family upgrades are intentional. The response `model` field reports the concrete model that served the request; record it. An alias can move between requests, so do not use it as an immutable test fixture.

Latest aliases also carry a compatibility contract: if a newly resolved target requires reasoning, OpenRouter can remap attempts to disable reasoning (`effort: "none"`, `enabled: false`, or a zero token budget) to the lowest supported effort. Concrete slugs keep strict validation for those controls. Use a concrete slug whenever exact parameter semantics matter.

## Model variants and suffixes

Variants are model- and router-specific. Do not assume a suffix is valid on every slug.

| Variant | Typical behavior | Guidance |
|---|---|---|
| `:free` | Select a zero-price endpoint/version | Expect stricter availability/rate constraints; discover live |
| `:nitro` | Optimize for measured throughput | Equivalent to throughput-oriented routing where supported |
| `:floor` | Optimize for price | Equivalent to price-oriented routing where supported |
| `:online` | Enable the legacy web-search plugin shortcut | Prefer explicit `openrouter:web_search` server tool in new agentic integrations |
| `:extended` | Select an extended-context version | Verify context length and price live |
| `:exacto` | Curated tool-calling-oriented variant | Verify that it exists for the requested family |
| `:thinking` | Legacy/model-specific reasoning variant | Do not rely on it as portable; Anthropic uses unified `reasoning` instead |

Multiple suffixes may be composable for some models, but current docs/model metadata are authoritative.

## Provider preferences

The `provider` object controls eligible serving endpoints and their ordering:

```json
{
  "provider": {
    "allow_fallbacks": true,
    "require_parameters": true,

    "order": ["provider-slug-a", "provider-slug-b"],
    "only": ["provider-slug-a", "provider-slug-b"],
    "ignore": ["provider-slug-c"],

    "sort": "price",

    "max_price": {
      "prompt": 0.000003,
      "completion": 0.000015,
      "request": 0.001,
      "image": 0.02
    },

    "preferred_min_throughput": { "p50": 40 },
    "preferred_max_latency": { "p50": 2.0, "p99": 10.0 },

    "data_collection": "deny",
    "zdr": true,
    "enforce_distillable_text": true,
    "quantizations": ["bf16", "fp16", "fp8"]
  }
}
```

The numeric values above are illustrative request constraints, not current provider prices or performance promises.

### Exact provider slugs

Use the provider/endpoint slugs returned by current metadata. Display names shown in dashboards are not necessarily valid request values. A provider can expose multiple endpoint variants, regions, service tiers, or BYOK routes with distinct slugs.

### `order`, `only`, and `ignore`

- `order` tries eligible providers in the specified preference order.
- `only` restricts routing to a whitelist.
- `ignore` removes providers/endpoints from consideration.
- `allow_fallbacks: false` prevents routing beyond the explicitly selected provider strategy.

An explicit `order` takes precedence over sticky routing and can reduce provider prompt-cache hit rates.

### `require_parameters`

Set this when a field is semantically required, especially:

- tools or parallel tool calls;
- strict structured outputs;
- reasoning controls;
- log probabilities;
- multimodal inputs;
- web/search options;
- service tiers or provider passthrough.

Without it, a provider adapter may drop or normalize unsupported optional fields.

## Sorting behavior

Simple form:

```json
{ "provider": { "sort": "throughput" } }
```

Current common sort values are:

- `price` — lowest eligible price;
- `throughput` — highest measured output throughput;
- `latency` — lowest measured latency.

Advanced form:

```json
{
  "provider": {
    "sort": {
      "by": "price",
      "partition": "none"
    }
  }
}
```

`partition: "model"` sorts provider endpoints within each model fallback. `partition: "none"` can sort globally across eligible endpoints for all models in a fallback set. Verify current semantics before relying on cross-model sorting.

### Default routing

When no explicit sort/order is supplied, OpenRouter filters unhealthy/ineligible endpoints, biases load balancing toward lower-priced endpoints, and retains other eligible routes as fallbacks. The exact weighting and health windows are an implementation detail and may change.

## Soft preferences vs hard constraints

- `preferred_min_throughput` and `preferred_max_latency` are preferences: they influence ordering but may be relaxed when capacity is limited.
- `max_price`, `only`, `ignore`, `zdr`, and parameter requirements are hard eligibility constraints.

Inspect the returned route/provider metadata to confirm the actual choice.

## Model fallback

Chat Completions and Responses can use an ordered fallback list. When both fields are present, OpenRouter tries the top-level `model` first and then each entry in `models`. When `model` is omitted, `models` is the complete priority order.

```json
{
  "model": "author/primary",
  "models": [
    "author/compatible-fallback",
    "other-author/compatible-fallback"
  ]
}
```

Fallback can be triggered by context-length validation, moderation/refusal conditions, rate limits, unavailable providers, and other errors documented by OpenRouter. Billing and response metadata correspond to the model that ultimately served the request.

### Fallback safety checklist

Every fallback must support:

- all input and output modalities;
- the tool schema and parallel-tool behavior;
- required structured output;
- the selected reasoning mode;
- sufficient context/output limits;
- the required data policy/ZDR;
- any service tier or provider-specific extension.

A cheap text-only model is not a safe fallback for an image+tool request.

### Messages API fallbacks

The Anthropic Messages skin supports:

```json
{
  "fallbacks": [
    { "model": "author/fallback-a" },
    { "model": "author/fallback-b" }
  ]
}
```

These map to OpenRouter routing. Each entry contains only `model`, the list is currently limited to three, and it cannot be combined with `models`.

### Streaming limitation

Provider/model fallback is possible before response content begins. Once a stream has emitted partial content, OpenRouter cannot transparently restart with a new provider without duplicating or contradicting output. Surface the partial result and typed error to the caller.

## Endpoint performance and availability

`GET /models/{author}/{slug}/endpoints` exposes endpoint-specific facts such as:

- provider name/slug and endpoint tag;
- operational/degraded status and recent uptime;
- latency and throughput percentiles;
- context and maximum output limits;
- provider-specific prices and cache prices;
- supported parameters and implicit caching;
- quantization and data-retention policy;
- service-tier variants and regions.

Use percentiles, not only averages. A low median with a very high p99 may be unsuitable for an interactive service. Treat short-window metrics as observations, not guarantees.

## Privacy and data policy

### Data collection

```json
{
  "provider": {
    "data_collection": "deny"
  }
}
```

This restricts routes based on provider data-use policies. Verify account-level privacy settings and guardrails too.

### Zero Data Retention

```json
{
  "provider": {
    "zdr": true
  }
}
```

This restricts the request to ZDR-eligible endpoints. Account- or guardrail-level ZDR remains enforced even when the field is omitted.

OpenRouter response caching requires temporary storage and is unavailable under account-level ZDR. Provider prompt caching can still be compatible with ZDR under OpenRouter's documented policy because it is treated separately from durable retention.

For an updated list, call the management-key endpoint:

```text
GET https://openrouter.ai/api/v1/endpoints/zdr
```

## Service tiers

Top-level request field:

```json
{
  "service_tier": "flex"
}
```

Current requested values include `flex` and `priority` on eligible provider/model combinations. The response reports the tier actually served:

- Chat Completions/Responses: top-level `service_tier`, typically `default`, `flex`, `priority`, or `null`;
- Messages: `usage.service_tier`, with `standard` as the base-tier label.

Do not assume a tier is available for every model or provider. Check provider endpoint metadata and price it using live data.

## Sticky routing and `session_id`

Provider prompt caches live at a provider endpoint. OpenRouter uses sticky routing to improve cache reuse.

```json
{
  "session_id": "agent-run-8f8d3f2c"
}
```

The same value can be supplied through `x-session-id`. Keep it stable per conversation/run and within the documented length limit. With an explicit session ID, stickiness begins after the first successful request; without one, OpenRouter can derive a conversation key from opening messages after cache behavior is observed.

For router models, sticky routing can pin both the resolved model and the provider. A manually supplied `provider.order` overrides stickiness.

## OpenRouter routers

OpenRouter publishes dynamic router models and specialized workflows. Current families include task-aware routing, free-model routing, coding-quality routing, multi-model fusion, and request-body generation. Their membership, policies, and defaults can change independently of this skill.

Rules:

1. Discover the router model live.
2. Read its current guide and plugin/tool requirements.
3. Apply cost/tool/latency bounds.
4. Record the concrete model returned.
5. Use `session_id` for multi-turn consistency where documented.
6. Do not assert a fixed list of models behind a router.

## Provider-specific passthrough

Specialized endpoints may accept provider options under a provider slug, for example:

```json
{
  "provider": {
    "options": {
      "provider-slug": {
        "parameters": {
          "providerSpecificOption": "value"
        }
      }
    }
  }
}
```

The nesting differs by endpoint. Use the relevant media/API documentation and `allowed_passthrough_parameters`; do not apply an image/video passthrough shape to Chat Completions.

## Recommended selection algorithm

1. Query the relevant catalog with required output modality.
2. Filter expired/deprecated models unless intentionally testing them.
3. Filter required input modalities and `supported_parameters`.
4. Filter hard policy constraints: ZDR, data collection, region, price, service tier.
5. Inspect per-provider endpoints for actual limits and status.
6. Rank surviving routes by the user goal: quality, price, latency, throughput, or a Pareto combination.
7. Build a compatible fallback chain.
8. Send `require_parameters: true` when features are mandatory.
9. Log requested model, resolved model, provider, service tier, and router metadata.
10. Re-run discovery periodically and when a request begins failing.

## Common mistakes

- Using a provider display name where an endpoint slug is required.
- Assuming model-level capabilities are identical on every provider endpoint.
- Combining incompatible fallback models.
- Hardcoding a router's current member list.
- Using `:thinking` instead of the unified reasoning parameter.
- Setting soft latency preferences and treating them as an SLA.
- Forcing `provider.order` and accidentally defeating sticky prompt caching.
- Enabling account-level ZDR and expecting OpenRouter response-cache hits.
