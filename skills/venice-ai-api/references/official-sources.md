# Official sources and maintenance procedure

This skill was updated on **2026-07-24** from Venice-maintained sources. When sources disagree, use this precedence order:

1. live authenticated endpoint behavior;
2. current Venice OpenAPI YAML;
3. current endpoint-specific API reference;
4. current Venice-maintained Agent Skills repository;
5. current guides and model pages;
6. examples, blog posts, integration guides, and historical copies.

Never use an old model/pricing table as authority over `/models` or a media quote.

## Primary sources

### Documentation index

```text
https://docs.venice.ai/llms.txt
```

Use it to discover the current documentation tree instead of relying on search results alone.

### API reference

```text
https://docs.venice.ai/api-reference/api-spec
```

### OpenAPI YAML

```text
https://api.venice.ai/doc/api/swagger.yaml
https://docs.venice.ai/swagger.yaml
```

Generate clients and detect schema drift from this file. Do not vendor it into the skill as if it were permanent.

### Official Agent Skills

```text
https://github.com/veniceai/skills
```

Venice maintains modular OpenAPI-derived skills for chat, Responses, images, audio, video, embeddings, models, routing, authentication, billing, x402, augment, characters, crypto RPC, and errors. This single `venice-ai-api` skill consolidates those workflows for repositories that prefer one skill folder.

### Documentation source repository

```text
https://github.com/veniceai/api-docs
```

Use it to inspect documentation changes and source history when the rendered page is ambiguous.

## Core endpoint references

### Models

```text
https://docs.venice.ai/api-reference/endpoint/models/list
https://docs.venice.ai/api-reference/endpoint/models/traits
https://docs.venice.ai/api-reference/endpoint/models/compatibility_mapping
https://docs.venice.ai/overview/deprecations
https://docs.venice.ai/overview/pricing
https://docs.venice.ai/overview/privacy
```

### Chat and text

```text
https://docs.venice.ai/api-reference/endpoint/chat/completions
https://docs.venice.ai/api-reference/endpoint/chat/model_feature_suffix
https://docs.venice.ai/guides/features/file-inputs
https://docs.venice.ai/guides/features/function-calling
https://docs.venice.ai/guides/features/structured-responses
https://docs.venice.ai/guides/features/reasoning-models
https://docs.venice.ai/guides/features/prompt-caching
https://docs.venice.ai/guides/features/web-search
https://docs.venice.ai/guides/features/tee-e2ee-models
```

### Images

```text
https://docs.venice.ai/api-reference/endpoint/image/generate
https://docs.venice.ai/api-reference/endpoint/image/generations
https://docs.venice.ai/api-reference/endpoint/image/styles
https://docs.venice.ai/api-reference/endpoint/image/edit
https://docs.venice.ai/api-reference/endpoint/image/multi-edit
https://docs.venice.ai/api-reference/endpoint/image/upscale
https://docs.venice.ai/api-reference/endpoint/image/background-remove
```

### Audio

```text
https://docs.venice.ai/api-reference/endpoint/audio/speech
https://docs.venice.ai/api-reference/endpoint/audio/voices
https://docs.venice.ai/guides/media/voice-cloning
https://docs.venice.ai/api-reference/endpoint/audio/transcriptions
https://docs.venice.ai/api-reference/endpoint/audio/quote
https://docs.venice.ai/api-reference/endpoint/audio/queue
https://docs.venice.ai/api-reference/endpoint/audio/retrieve
https://docs.venice.ai/api-reference/endpoint/audio/complete
```

### Video

```text
https://docs.venice.ai/guides/media/video-generation
https://docs.venice.ai/guides/media/video-upscaling
https://docs.venice.ai/guides/media/seedance-face-consent
https://docs.venice.ai/api-reference/endpoint/video/quote
https://docs.venice.ai/api-reference/endpoint/video/queue
https://docs.venice.ai/api-reference/endpoint/video/retrieve
https://docs.venice.ai/api-reference/endpoint/video/complete
https://docs.venice.ai/api-reference/endpoint/video/transcriptions
```

### Platform and administration

```text
https://docs.venice.ai/api-reference/endpoint/embeddings/generate
https://docs.venice.ai/api-reference/endpoint/augment/text-parser
https://docs.venice.ai/api-reference/endpoint/augment/scrape
https://docs.venice.ai/api-reference/endpoint/augment/search
https://docs.venice.ai/api-reference/endpoint/characters/list
https://docs.venice.ai/guides/integrations/crypto-rpc-agents
https://docs.venice.ai/api-reference/endpoint/crypto/networks
https://docs.venice.ai/api-reference/endpoint/crypto/rpc
https://docs.venice.ai/guides/integrations/x402-venice-api
https://docs.venice.ai/api-reference/endpoint/x402/balance
https://docs.venice.ai/api-reference/endpoint/x402/top-up
https://docs.venice.ai/api-reference/endpoint/x402/transactions
https://docs.venice.ai/api-reference/endpoint/api_keys/create
https://docs.venice.ai/api-reference/endpoint/api_keys/rate_limits
https://docs.venice.ai/api-reference/endpoint/billing/balance
https://docs.venice.ai/api-reference/endpoint/billing/usage-history
https://docs.venice.ai/api-reference/endpoint/billing/usage  # deprecated
https://docs.venice.ai/api-reference/endpoint/billing/usage-analytics
```

## Maintenance cadence

### At each use

- resolve the selected model or trait;
- inspect constraints and deprecation;
- quote async media;
- honor response headers.

### Monthly or before a release

1. Download the current OpenAPI YAML.
2. Diff paths, methods, required fields, enums, and response types.
3. Review Venice's changelog and deprecation page.
4. Compare the official `veniceai/skills` repository.
5. Run `scripts/discover_models.py` for every model family used by the product.
6. Run contract tests with a limited nonproduction key.
7. Update examples only when request/response contracts changed.
8. Avoid snapshotting current prices and model IDs into prose unless clearly labeled and dated.

### Immediately after a runtime signal

Refresh discovery and docs after:

- `INVALID_MODEL`, `MODEL_NOT_FOUND`, or model `404`;
- a deprecation warning header;
- a previously accepted enum/field returning `400`;
- a Beta/Preview response parser failing;
- repeated provider-capacity errors;
- a trait resolving to a new target;
- a media quote changing unexpectedly.

## Schema-diff checklist

When OpenAPI changes, inspect:

- new or removed routes;
- required versus optional fields;
- renamed request keys such as `queue_id`;
- field asymmetries such as `/image/multi-edit` using `modelId`;
- JSON versus multipart content types;
- binary versus JSON success responses;
- new error statuses;
- enum additions/removals;
- authentication schemes per route;
- Alpha/Beta/Preview labels;
- examples that contain stale model IDs.

## Model-catalog diff checklist

For each product-selected model, compare:

```text
id
privacy
offline/beta
region restrictions
deprecation date
capabilities
context/completion limits
media constraints
voice/reference lists
pricing shape and values
```

A missing field is not automatically false. Review the current schema and provider behavior.

## Verification status of this package

The package was statically validated for:

- Agent Skills frontmatter;
- internal Markdown links;
- current base URL;
- current asynchronous field spelling `queue_id`;
- absence of frozen model-price/rate tables in operational instructions;
- Python helper syntax and `--help` behavior;
- ZIP structure with `venice-ai-api/` as the root directory.

No authenticated Venice API key was available during packaging, so examples were not executed against paid inference endpoints. They were checked against Venice's current public endpoint documentation, OpenAPI-derived official skills, and model-lifecycle guidance.
