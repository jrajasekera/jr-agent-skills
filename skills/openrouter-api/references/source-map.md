# Source Map and Maintenance Guide

This skill was last verified on **2026-07-25** against OpenRouter's public documentation, OpenAPI specification, changelog, official SDK documentation, and official Agent Skills repository.

## Authority order

When sources disagree, use this order:

1. **Live endpoint behavior and current OpenAPI** for exact paths, methods, request/response fields, enums, and content types.
2. **Dated changelog** for recent migrations, additions, deprecations, and rollout notes.
3. **Endpoint reference pages** for semantics and examples.
4. **Feature/guides pages** for workflows and best practices.
5. **Official generated SDK types/docs** for the pinned SDK version.
6. **Official OpenRouter Agent Skills repository** for practical agent workflows.
7. This local skill and third-party examples.

Do not treat model cards, blog posts, old snippets, or cached search results as stronger than the current API schema.

## Global discovery sources

- Documentation index: https://openrouter.ai/docs/llms.txt
- OpenAPI JSON: https://openrouter.ai/openapi.json
- Changelog: https://openrouter.ai/docs/changelog
- API quickstart: https://openrouter.ai/docs/quickstart
- API overview: https://openrouter.ai/docs/api/reference/overview
- Authentication: https://openrouter.ai/docs/api/reference/authentication
- App attribution: https://openrouter.ai/docs/guides/features/app-attribution

## Models and routing

- Models guide: https://openrouter.ai/docs/guides/overview/models
- Models API: https://openrouter.ai/docs/api/api-reference/models/get-models
- Model endpoint metadata: https://openrouter.ai/docs/api/api-reference/models/get-endpoints-for-model
- Provider routing: https://openrouter.ai/docs/guides/routing/provider-selection
- Model fallbacks: https://openrouter.ai/docs/guides/routing/model-fallbacks
- Model variants: https://openrouter.ai/docs/guides/routing/model-variants
- Latest family resolution: https://openrouter.ai/docs/guides/routing/routers/latest-resolution
- Zero Data Retention: https://openrouter.ai/docs/guides/features/zdr
- Data collection/privacy: https://openrouter.ai/docs/guides/privacy/data-collection
- Service tiers: https://openrouter.ai/docs/guides/features/service-tiers
- Router metadata: https://openrouter.ai/docs/guides/features/router-metadata

## Inference API skins

- Chat Completions endpoint: https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request
- Responses guide: https://openrouter.ai/docs/api/reference/responses/overview
- Responses endpoint: https://openrouter.ai/docs/api/api-reference/responses/create-responses
- Anthropic Messages compatibility: https://openrouter.ai/docs/guides/community/anthropic-agent-sdk
- Streaming: https://openrouter.ai/docs/api/reference/streaming
- Errors and debugging: https://openrouter.ai/docs/api/reference/errors-and-debugging

## Tools and generated output

- User-defined tool calling: https://openrouter.ai/docs/guides/features/tool-calling
- Server tools overview: https://openrouter.ai/docs/guides/features/server-tools/overview
- Web search server tool: https://openrouter.ai/docs/guides/features/server-tools/web-search
- Web fetch: https://openrouter.ai/docs/guides/features/server-tools/web-fetch
- Datetime: https://openrouter.ai/docs/guides/features/server-tools/datetime
- Image generation tool: https://openrouter.ai/docs/guides/features/server-tools/image-generation
- Apply patch: https://openrouter.ai/docs/guides/features/server-tools/apply-patch
- Shell: https://openrouter.ai/docs/guides/features/server-tools/shell
- Files server tool: inspect `openrouter:files` in the live OpenAPI; it requires `x-openrouter-file-ids: openrouter`.
- Search models: https://openrouter.ai/docs/guides/features/server-tools/search-models
- Fusion: https://openrouter.ai/docs/guides/features/server-tools/fusion
- Advisor: https://openrouter.ai/docs/guides/features/server-tools/advisor
- Subagent: https://openrouter.ai/docs/guides/features/server-tools/subagent
- Plugins overview: https://openrouter.ai/docs/guides/features/plugins/overview
- Structured outputs: https://openrouter.ai/docs/guides/features/structured-outputs
- Reasoning: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens

## Caching and transforms

- Prompt caching: https://openrouter.ai/docs/guides/best-practices/prompt-caching
- Response caching: https://openrouter.ai/docs/guides/features/response-caching
- Message transforms: https://openrouter.ai/docs/guides/features/message-transforms
- Usage accounting: https://openrouter.ai/docs/cookbook/administration/usage-accounting
- PDF/file parser plugin: https://openrouter.ai/docs/guides/overview/multimodal/pdfs

## Multimodal, files, and media

- Multimodal overview: https://openrouter.ai/docs/guides/overview/multimodal/overview
- Image inputs: https://openrouter.ai/docs/guides/overview/multimodal/images
- Image generation: https://openrouter.ai/docs/guides/overview/multimodal/image-generation
- Audio inputs: https://openrouter.ai/docs/guides/overview/multimodal/audio
- Speech-to-text: https://openrouter.ai/docs/guides/overview/multimodal/stt
- Text-to-speech: https://openrouter.ai/docs/guides/overview/multimodal/tts
- Video generation: https://openrouter.ai/docs/guides/overview/multimodal/video-generation
- File upload endpoint: https://openrouter.ai/docs/api/api-reference/files/upload-file
- File list endpoint: https://openrouter.ai/docs/api/api-reference/files/list-files

## Retrieval

- Embeddings: https://openrouter.ai/docs/api/reference/embeddings
- Reranking: https://openrouter.ai/docs/api/reference/reranking
- RAG/model modality filters: https://openrouter.ai/models

## SDKs

- Client SDK overview: https://openrouter.ai/docs/client-sdks/overview
- TypeScript SDK: https://openrouter.ai/docs/client-sdks/typescript/overview
- Python SDK: https://openrouter.ai/docs/client-sdks/python/overview
- Go SDK: https://openrouter.ai/docs/client-sdks/go/overview
- Agent SDK: https://openrouter.ai/docs/agent-sdk/overview
- Official skills repository: https://github.com/OpenRouterTeam/skills

## Authentication and administration

- OAuth PKCE: https://openrouter.ai/docs/guides/overview/auth/oauth
- Current key metadata: https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key
- API-key list/create/update/delete: https://openrouter.ai/docs/api/api-reference/api-keys
- Credits: https://openrouter.ai/docs/api/api-reference/credits/get-credits
- Generation metadata/content: https://openrouter.ai/docs/api/api-reference/generations
- Activity: https://openrouter.ai/docs/api/api-reference/analytics/get-user-activity
- Analytics: https://openrouter.ai/docs/api/api-reference/analytics
- Workspaces: https://openrouter.ai/docs/guides/features/workspaces
- Guardrails: https://openrouter.ai/docs/guides/features/guardrails

Some collection URLs above redirect as documentation navigation evolves. Use `llms.txt` and `openapi.json` to locate the canonical current page.

## Review triggers

Review this skill immediately when any of these occurs:

- OpenRouter publishes an API/SDK changelog entry affecting inference surfaces.
- A request begins failing with a previously unseen schema error or typed `error_type`.
- A model alias, provider slug, router, plugin, or server-tool type changes.
- Generated SDK types rename an operation or request field.
- A beta feature becomes stable or changes compatibility surface.
- New output modalities or dedicated media endpoints appear.
- Key/workspace/guardrail/analytics permissions change.
- Response caching, ZDR, logging, or observability semantics change.

## Maintenance procedure

1. Read changelog entries since the last verification date.
2. Download or inspect the latest OpenAPI and diff `paths` plus `components.schemas`.
3. Run `scripts/inspect_openapi.py --list` and compare against [api-endpoints.md](api-endpoints.md).
4. Query live model/media catalogs and test `scripts/discover_models.py`.
5. Check official SDK installation names and quick-start signatures.
6. Revalidate one request for each API skin, one stream, one caller-tool loop, and any beta feature documented here.
7. Search the skill for hardcoded model IDs, prices, rate limits, voices, dimensions, and router membership.
8. Compile and run the included Python helpers with offline fixtures.
9. Check every relative Markdown link.
10. Update the verification date only after these checks pass.

## Explicitly dynamic facts

Never freeze these as authoritative in the skill:

- number of models/providers;
- current router members or selected model;
- model IDs not used only as labeled examples;
- prices and rate-limit numbers;
- context/output limits;
- supported modalities/parameters;
- provider latency, throughput, uptime, quantization, or data policy;
- voices, image controls, video durations/resolutions;
- beta server-tool availability and limits;
- API/SDK enum membership.
