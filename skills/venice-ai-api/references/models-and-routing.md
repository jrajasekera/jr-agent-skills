# Models, capabilities, pricing, privacy, and routing

The Venice model catalog is an API, not a static list. Query it when selecting a model, generating configuration, estimating cost, validating media parameters, or debugging a rejected request.

## Discovery endpoints

| Endpoint | Purpose |
|---|---|
| `GET /models?type=<type>` | Current models plus `model_spec` metadata |
| `GET /models/traits?type=<type>` | Symbolic trait to model-ID mappings |
| `GET /models/compatibility_mapping?type=<type>` | OpenAI/vendor/legacy aliases to Venice IDs |

All use the base URL `https://api.venice.ai/api/v1`.

Current type filters include:

```text
text, image, inpaint, upscale, video, music, tts, asr, embedding, all
```

For coding models, request `type=text` and filter `model_spec.capabilities.optimizedForCode`, or use the `default_code` trait when it exists. New filters can appear; validate against the current OpenAPI schema.

## Fetch the catalog

```bash
curl -sS "https://api.venice.ai/api/v1/models?type=text" \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  | jq '.data[] | {id, spec: .model_spec}'
```

```python
import os
import requests

BASE = "https://api.venice.ai/api/v1"
headers = {"Authorization": f"Bearer {os.environ['VENICE_API_KEY']}"}

catalog = requests.get(
    f"{BASE}/models",
    params={"type": "text"},
    headers=headers,
    timeout=30,
)
catalog.raise_for_status()
models = catalog.json()["data"]
```

Do not assume the response always has every optional field. Use `.get()` defensively.

## Important `model_spec` fields

### Common fields

| Field | Meaning | Required handling |
|---|---|---|
| `name`, `description` | Human-readable model metadata | Display only; route by machine fields |
| `privacy` | Commonly `private` or `anonymized` | Apply the user's privacy requirement before cost optimization |
| `offline` | Model is known but not currently serving | Exclude from scheduling |
| `beta` / `betaModel` | Access may be gated | Exclude unless the key is known to have access |
| `regionRestrictions[]` | Allowed or restricted country codes, depending on current schema | Check before selecting the model |
| `deprecation.date` | Retirement date | Warn, migrate, and stop new adoption |
| `pricing` | Model-family-specific price object | Never apply one family's formula to another |
| `constraints` | Model-family-specific input constraints | Validate before making the paid call |

### Text-model capabilities

Common flags include:

- `optimizedForCode`
- `supportsFunctionCalling`
- `supportsReasoning`
- `supportsReasoningEffort`
- `supportsResponseSchema`
- `supportsVision`
- `supportsMultipleImages`
- `maxImages`
- `supportsAudioInput`
- `supportsVideoInput`
- `supportsWebSearch`
- `supportsXSearch`
- `supportsLogProbs`
- `supportsTeeAttestation`
- `supportsE2EE`

Capabilities can be added. Prefer a positive capability check over assumptions based on a model's name or provider.

### Text-model limits

Use:

- `availableContextTokens`
- `maxCompletionTokens`
- sampling defaults under `constraints`

Budget the context as:

```text
system/developer instructions
+ conversation history
+ extracted file text
+ tool definitions and tool outputs
+ image/audio/video tokenization overhead
+ requested completion
```

Leave headroom. A request that fits exactly on paper can exceed the provider's tokenizer-specific limit.

### Image constraints

Look for:

- `promptCharacterLimit`
- `widthHeightDivisor`
- `steps.default`, `steps.max`
- `aspectRatios[]`, `defaultAspectRatio`
- `resolutions[]`, `defaultResolution`
- style-reference support and maximum reference count

A model generally uses one sizing idiom:

1. explicit `width` + `height`, or
2. `aspect_ratio` + `resolution`, or
3. OpenAI-compatible `size` on `/images/generations`.

Do not mix them without confirming support.

### Video constraints

Look for:

- `model_type`
- `durations[]`
- `aspect_ratios[]`
- `resolutions[]`
- audio support and configurability
- prompt character limit
- reference-image, element, scene, end-frame, input-video, or upscale support

Video price is quote-driven. Do not infer it from a text or image pricing object.

### TTS, ASR, music, and embeddings

Depending on the family, fields may appear at the top of `model_spec` rather than under `constraints`:

- TTS: `voices[]`, `default_voice`, language/speed/style support, and optional `voice_cloning` metadata
- ASR: per-audio-second pricing and language behavior
- Music: lyric, instrumental, duration, language, speed, and voice support
- Embeddings: `embeddingDimensions`, `maxInputTokens`, `supportsCustomDimensions`

## Traits versus fixed IDs

### Traits

Traits are stable symbolic selectors whose backing model may change. Example request:

```bash
curl -sS "https://api.venice.ai/api/v1/models/traits?type=text" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Text traits commonly include concepts such as:

- `default`
- `fastest`
- `default_reasoning`
- `default_code`
- `default_vision`
- `function_calling_default`
- `most_intelligent`
- `most_uncensored`

Image traits can use a different set, such as `default`, `fastest`, or `highest_quality`. Never assume a trait exists for every type.

Use a trait when:

- the user asks for the current recommended model;
- automatic quality improvements are desirable;
- the application accepts some behavior drift;
- operational continuity matters more than exact reproducibility.

### Fixed IDs

Use a fixed ID when:

- running benchmarks or acceptance tests;
- prompt behavior is regression-tested;
- a regulated workflow requires a validated configuration;
- embeddings must remain compatible with stored vectors;
- output consistency matters more than automatic upgrades.

Store the selected ID with generated artifacts, embeddings, eval results, and usage records.

## Compatibility mappings

```bash
curl -sS "https://api.venice.ai/api/v1/models/compatibility_mapping?type=text" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Mappings help existing OpenAI/vendor clients call Venice without immediately rewriting every model name. They resolve identifiers, not capabilities. After resolving a mapping, still check the target model's `model_spec`.

## Privacy routing

Apply privacy requirements before performance and price.

| Level | Detection | Practical meaning |
|---|---|---|
| Anonymized | `model_spec.privacy == "anonymized"` | Venice proxies a third-party model after removing identifying metadata; provider terms still matter |
| Private | `model_spec.privacy == "private"` | Venice-hosted private inference with the platform's no-content-retention guarantees |
| TEE | `supportsTeeAttestation` and/or current TEE model naming/metadata | Confidential-compute execution with attestation support |
| E2EE | `supportsE2EE` and current E2EE flow | Client-side encrypted payload to a supported confidential-compute model |

Rules:

1. Never route secrets, credentials, private source code, PHI, or other sensitive data to an anonymized model merely because it is stronger.
2. Do not infer TEE/E2EE solely from an ID prefix. Check current capabilities and the official guide.
3. E2EE requires more than TLS and more than `enable_e2ee: true`; follow the current handshake/header flow.
4. `/responses` may not support the full E2EE path. Prefer `/chat/completions` for encrypted inference unless current docs explicitly say otherwise.
5. Record the chosen privacy tier in audit metadata.

## Routing algorithm

Apply these gates in order:

1. **Availability:** exclude `offline`, inaccessible beta, deprecated past retirement, and region-incompatible entries.
2. **Privacy:** require the minimum acceptable privacy tier.
3. **Modality:** require vision, multiple images, audio, video, or file-compatible context as needed.
4. **Capabilities:** require function calling, reasoning, structured output, web/X search, code optimization, or logprobs as needed.
5. **Context:** require enough input plus completion capacity with headroom.
6. **User override:** honor requests such as fastest, cheapest, private, frontier, fixed model, or uncensored when compatible with safety and product policy.
7. **Cost:** among survivors, compare live pricing using the correct family formula.
8. **Latency/quality:** use observed telemetry or a current trait as a tie-breaker.

Do not choose a model first and then silently weaken requirements to make it fit.

## Example capability filter

```python
from typing import Any


def eligible_text_models(
    rows: list[dict[str, Any]],
    *,
    require_tools: bool = False,
    require_reasoning: bool = False,
    require_vision: bool = False,
    privacy: str | None = None,
    minimum_context: int = 0,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    for row in rows:
        spec = row.get("model_spec") or {}
        caps = spec.get("capabilities") or {}

        if spec.get("offline") is True:
            continue
        if spec.get("beta") is True or spec.get("betaModel") is True:
            continue
        if privacy and spec.get("privacy") != privacy:
            continue
        if (spec.get("availableContextTokens") or 0) < minimum_context:
            continue
        if require_tools and not caps.get("supportsFunctionCalling"):
            continue
        if require_reasoning and not caps.get("supportsReasoning"):
            continue
        if require_vision and not caps.get("supportsVision"):
            continue

        matches.append(row)

    return matches
```

The example deliberately does not sort by price because pricing has model-family and extended-context nuances. Add a comparator only after inspecting actual `pricing` shapes.

## Pricing shapes

### Text

Typical fields are per one million tokens:

```text
pricing.input.usd
pricing.output.usd
pricing.cache_input.usd
pricing.cache_write.usd
pricing.extended.*
pricing.extended.context_token_threshold
```

Estimate:

```python
cost = (
    input_tokens / 1_000_000 * input_usd
    + output_tokens / 1_000_000 * output_usd
    + cached_input_tokens / 1_000_000 * cache_read_usd
    + cache_write_tokens / 1_000_000 * cache_write_usd
)
```

If an extended-context threshold applies, switch to the documented extended rates for the applicable token ranges.

### Image

Models may expose:

- `pricing.generation` for a flat image price;
- `pricing.resolutions` for legacy/per-resolution prices; or
- `pricing.quality[resolution][quality]` for models whose price changes by both resolution and quality.

When `pricing.quality` is present, price the exact `(resolution, quality)` pair rather than falling back to `pricing.resolutions`. An account-wide upscale block may appear on image rows; that does not prove the selected generation model itself can upscale, so use the upscale endpoint/model catalog.

### Inpaint/edit

Look for `pricing.inpaint` or the current equivalent. Do not preserve a historical per-edit constant in source code.

### TTS and ASR

- TTS is usually priced per input character quantity.
- ASR is usually priced per audio second.

Read the units from the live model metadata before calculating.

### Music and video

Call the corresponding quote endpoint with the exact model, duration, resolution, aspect ratio, audio, and other billable fields. Gate queue submission against a configured maximum cost.

## Deprecation handling

At startup or deployment:

1. Fetch the fixed model's row.
2. Fail configuration if it is missing or offline.
3. Warn if `deprecation.date` is present.
4. Compare the retirement date with the current date.
5. Log model-deprecation response headers on every call.
6. Run a compatibility eval against the proposed replacement before switching a fixed production model.

Traits reduce maintenance but do not remove the need for acceptance tests; the trait target can change.

## Cache policy

- Cache traits and catalog metadata for minutes or a single process/session.
- In long-running services, refresh periodically and after `404`, `INVALID_MODEL`, deprecation warnings, or repeated capacity failures.
- Do not refresh on every token request unless necessary; discovery calls still consume network and can become a dependency.
- Persist the resolved model ID with request telemetry even when the caller submitted a trait.

## Included discovery helper

From the skill root:

```bash
export VENICE_API_KEY='...'
python scripts/discover_models.py --type text --show-traits
python scripts/discover_models.py --type text \
  --capability supportsFunctionCalling \
  --capability supportsResponseSchema \
  --minimum-context 100000
```

The helper uses only Python's standard library and does not make inference calls.

## Sources of truth

- Model listing: `https://docs.venice.ai/api-reference/endpoint/models/list`
- Model traits: `https://docs.venice.ai/api-reference/endpoint/models/traits`
- Compatibility mappings: `https://docs.venice.ai/api-reference/endpoint/models/compatibility_mapping`
- Model lifecycle: `https://docs.venice.ai/overview/deprecations`
- Pricing: `https://docs.venice.ai/overview/pricing`
- Privacy: `https://docs.venice.ai/overview/privacy`
- TEE/E2EE guide: `https://docs.venice.ai/guides/features/tee-e2ee-models`
