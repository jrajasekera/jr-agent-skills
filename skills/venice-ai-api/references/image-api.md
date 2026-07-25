# Image generation, editing, upscaling, and background removal

Venice exposes both a native image-generation endpoint and an OpenAI-compatible endpoint, plus separate native endpoints for editing, multi-image composition, enhancement/upscaling, and background removal.

## Endpoint map

| Endpoint | Purpose | Response |
|---|---|---|
| `POST /image/generate` | Native text-to-image with seeds, variants, negative prompts, styles, and references | JSON base64 array or binary image |
| `POST /images/generations` | OpenAI-compatible text-to-image | OpenAI image response |
| `GET /image/styles` | Current style preset names | JSON |
| `POST /image/edit` | Prompt-driven single-image edit | Binary PNG/image |
| `POST /image/multi-edit` | Compose/edit one to three images | Binary PNG/image |
| `POST /image/upscale` | Scale and/or enhance an image | Binary PNG/image |
| `POST /image/background-remove` | Transparent foreground cutout | Binary PNG |

Before calling any endpoint, query:

```bash
curl -sS "https://api.venice.ai/api/v1/models?type=image" \
  -H "Authorization: Bearer $VENICE_API_KEY"

curl -sS "https://api.venice.ai/api/v1/models?type=inpaint" \
  -H "Authorization: Bearer $VENICE_API_KEY"

curl -sS "https://api.venice.ai/api/v1/models?type=upscale" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Do not copy a model ID from this guide into long-lived production configuration. Resolve current models, constraints, and prices.

## Native generation: `/image/generate`

```bash
curl -sS https://api.venice.ai/api/v1/image/generate \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "prompt": "A modern glass observatory on a snowy ridge at blue hour",
    "width": 1024,
    "height": 1024,
    "format": "webp",
    "variants": 1,
    "safe_mode": true,
    "return_binary": false
  }' > response.json
```

### Common fields

| Field | Notes |
|---|---|
| `model` | Required model ID or supported trait. Verify via `type=image`. |
| `prompt` | Required. Honor `model_spec.constraints.promptCharacterLimit`. |
| `negative_prompt` | Optional; effectiveness varies by model family. |
| `width`, `height` | Use only for dimension-driven models. Honor max values and `widthHeightDivisor`. |
| `aspect_ratio` | Use for ratio-driven models. Validate against `aspectRatios[]`. |
| `resolution` | Commonly `1K`, `2K`, or `4K` on supporting models. Validate. |
| `cfg_scale` | Prompt-adherence control; model-specific and often ignored by newer provider APIs. |
| `steps` | Inference-step control; turbo/provider models can ignore it. |
| `seed` | Reproducibility hint within the same model/configuration. |
| `variants` | Multiple outputs, commonly 1–4. Requires JSON/base64 mode. |
| `style_preset` | Name returned by `GET /image/styles`. |
| `style_references` | Existing images that guide output aesthetics on supporting models. |
| `lora_strength` | Model-specific; do not send unless advertised. |
| `format` | Commonly `webp`, `png`, or `jpeg`. |
| `return_binary` | `false`: JSON base64; `true`: direct image bytes. |
| `embed_exif_metadata` | Embed generation metadata where supported. |
| `hide_watermark` | Advisory; policy may still require a watermark. |
| `safe_mode` | Controls safety blurring/filtering on supported image routes. |
| `enable_web_search` | Only on models that advertise it; extra cost can apply. |

### Sizing rules

Inspect the selected model's `constraints` before building the body.

```python
spec = selected_model["model_spec"]
constraints = spec.get("constraints", {})

prompt_limit = constraints.get("promptCharacterLimit")
divisor = constraints.get("widthHeightDivisor")
aspect_ratios = constraints.get("aspectRatios")
resolutions = constraints.get("resolutions")
```

Use exactly one supported sizing strategy:

```json
{"width": 1024, "height": 1024}
```

or:

```json
{"aspect_ratio": "16:9", "resolution": "2K"}
```

Do not assume arbitrary dimensions are accepted. If a divisor is present, both dimensions must be divisible by it.

### Decode JSON/base64 output

```python
import base64
import os
import requests

BASE = "https://api.venice.ai/api/v1"
headers = {
    "Authorization": f"Bearer {os.environ['VENICE_API_KEY']}",
    "Content-Type": "application/json",
}

res = requests.post(
    f"{BASE}/image/generate",
    headers=headers,
    json={
        "model": "default",
        "prompt": "A minimal architectural model photographed in a studio",
        "width": 1024,
        "height": 1024,
        "format": "webp",
        "return_binary": False,
    },
    timeout=180,
)
res.raise_for_status()

payload = res.json()
for index, encoded in enumerate(payload["images"]):
    with open(f"image-{index}.webp", "wb") as output:
        output.write(base64.b64decode(encoded))
```

### Stream binary output

```python
res = requests.post(
    f"{BASE}/image/generate",
    headers=headers,
    json={
        "model": "default",
        "prompt": "A dark blue abstract gradient with a subtle glow",
        "return_binary": True,
        "format": "png",
    },
    timeout=180,
)
res.raise_for_status()

content_type = res.headers.get("Content-Type", "")
if not content_type.startswith("image/"):
    raise RuntimeError(f"Expected image, got {content_type}: {res.text[:500]}")

with open("generated.png", "wb") as output:
    output.write(res.content)
```

`variants > 1` is incompatible with binary mode because one HTTP body cannot carry multiple independent image files.

## Style presets

```bash
curl -sS https://api.venice.ai/api/v1/image/styles \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Use the exact returned style name. Do not freeze the preset list in application code.

## Style references

On models with current style-reference support:

```json
{
  "model": "<supporting-image-model>",
  "prompt": "A lighthouse on a rocky coast at dusk",
  "style_references": [
    {
      "image": "https://example.com/reference-1.png",
      "strength": 0.8
    },
    {
      "image": "data:image/png;base64,...",
      "strength": 0.4
    }
  ]
}
```

Check:

- style-reference capability flag;
- `constraints.maxStyleReferences`;
- whether per-reference strength is supported;
- current file-size limit and accepted URL/base64 forms;
- whether the model is private or anonymized before sending proprietary references.

Describe the desired **subject/content** in the prompt; use references primarily for visual language. Do not assume they provide identity-perfect copying.

## OpenAI-compatible generation: `/images/generations`

Use this for a low-friction OpenAI SDK migration. Use the native endpoint when you need variants, seeds, negative prompts, CFG, steps, presets, or style references.

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["VENICE_API_KEY"],
    base_url="https://api.venice.ai/api/v1",
)

result = client.images.generate(
    model="default",
    prompt="A white ceramic lamp on a walnut desk, product photograph",
    size="1024x1024",
    response_format="b64_json",
)

image_b64 = result.data[0].b64_json
```

Common compatibility fields:

- `model`
- `prompt`
- `size`
- `response_format`
- `output_format`
- `moderation`
- `n` (currently `1`)
- `quality`
- `style`
- `background`
- `user`

Some OpenAI fields are accepted but ignored. Venice currently supports a single output on this compatibility route; use `/image/generate` for multiple variants. A `url` response can be a data URL rather than a durable hosted URL—persist the bytes yourself.

## Single-image editing: `/image/edit`

Resolve a current `type=inpaint` model first.

```python
import base64
import os
import requests

with open("photo.jpg", "rb") as source:
    image_b64 = base64.b64encode(source.read()).decode("ascii")

res = requests.post(
    "https://api.venice.ai/api/v1/image/edit",
    headers={
        "Authorization": f"Bearer {os.environ['VENICE_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "model": os.environ["VENICE_INPAINT_MODEL"],
        "prompt": "Replace the overcast sky with a warm sunrise while preserving the buildings",
        "image": image_b64,
        "aspect_ratio": "16:9",
        "safe_mode": True,
    },
    timeout=240,
)
res.raise_for_status()

if not res.headers.get("Content-Type", "").startswith("image/"):
    raise RuntimeError(res.text[:1000])

with open("edited.png", "wb") as output:
    output.write(res.content)
```

Key points:

- `/image/edit` prefers the field name `model`.
- `modelId` can exist as a deprecated compatibility alias on this route; do not generate new code with it unless the live schema requires it.
- `image` can be base64 or, where documented, a public HTTPS URL.
- Validate aspect ratio against the chosen inpaint model.
- Response is binary, not base64 JSON.

Write prompts as explicit edit instructions:

```text
Change only the jacket from black to dark green. Preserve the face, pose,
lighting, background, crop, camera angle, and all other clothing.
```

Avoid vague prompts such as “make it better.”

## Multi-image editing: `/image/multi-edit`

This route has a deliberate field-name asymmetry: it uses **`modelId`**, not `model`, in the current schema.

### JSON form

```json
{
  "modelId": "<current-multi-edit-model>",
  "prompt": "Place the person from image 2 naturally into the beach scene in image 1",
  "images": [
    "https://example.com/beach.jpg",
    "data:image/png;base64,..."
  ],
  "safe_mode": true
}
```

The first image is the base; later images are subjects, layers, or references. Current documented limit is one to three images, but validate the live model constraint.

### Multipart form

```bash
curl -sS https://api.venice.ai/api/v1/image/multi-edit \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "modelId=$VENICE_INPAINT_MODEL" \
  -F "prompt=Place the person from image 2 into image 1" \
  -F "images=@base.jpg" \
  -F "images=@subject.png" \
  --output composite.png
```

Use multiple parts with the same `images` field name. Preserve order.

## Upscale and enhancement: `/image/upscale`

```python
res = requests.post(
    "https://api.venice.ai/api/v1/image/upscale",
    headers={
        "Authorization": f"Bearer {os.environ['VENICE_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "image": image_b64,
        "scale": 2,
        "enhance": True,
        "enhanceCreativity": 0.35,
        "enhancePrompt": "natural skin texture, fine fabric detail",
        "replication": 0.55,
    },
    timeout=300,
)
res.raise_for_status()
```

Current controls include:

| Field | Purpose |
|---|---|
| `scale` | Commonly 1–4. `1` is enhancement without enlargement and requires enhancement. |
| `enhance` | Enable generative enhancement. |
| `enhanceCreativity` | More reinterpretation at higher values. |
| `enhancePrompt` | Short texture/style cue. |
| `replication` | Preserve original line/noise/detail structure. |

Large inputs can be clamped to the endpoint's output-pixel ceiling. Inspect returned dimensions rather than assuming the exact requested multiplier was possible.

Use plain upscaling for fidelity. Use enhancement only when generative changes are acceptable.

## Background removal: `/image/background-remove`

Base64 form:

```bash
curl -sS https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image":"<base64>"}' \
  --output cutout.png
```

URL form:

```bash
curl -sS https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image_url":"https://example.com/product.jpg"}' \
  --output cutout.png
```

Send `image` **or** `image_url`, not both. Preserve PNG alpha when saving or transforming the result.

## Shared input rules

Image edit endpoints can enforce:

- maximum encoded/upload size;
- minimum and maximum pixel area;
- public reachability for URLs;
- supported image MIME types;
- endpoint-specific base64 format (plain base64 versus data URL);
- safe-mode policy.

Do not blindly add a `data:image/...` prefix to every endpoint. Follow the current request schema. If a route expects plain base64 and returns `400`, strip the prefix.

## Cost control

1. Read `model_spec.pricing` for generation/edit models.
2. Select the exact resolution tier before estimating.
3. Multiply by `variants`.
4. Include style-reference, web-search, upscale, or enhancement charges where advertised.
5. Enforce an application-level maximum before submitting.
6. Reconcile against billing usage rather than assuming the estimate equals final cost.

## Error handling

| Status | Likely cause |
|---|---|
| `400` | Invalid dimensions, ratio, prompt length, model, image, image count, or content-policy result |
| `401` | Invalid credentials or gated model |
| `402` | Insufficient account/wallet balance |
| `413` | Platform payload limit, depending on route |
| `415` | JSON versus multipart mismatch or invalid media type |
| `422` | Endpoint/provider-specific validation or policy behavior |
| `429` | Image endpoint/key limit |
| `500` / `503` | Inference or capacity failure |

For a binary route, an error response is JSON/text. Always check `response.ok` and `Content-Type` before writing bytes to an image file.

## Sources of truth

- Native generation: `https://docs.venice.ai/api-reference/endpoint/image/generate`
- OpenAI generation: `https://docs.venice.ai/api-reference/endpoint/image/generations`
- Styles: `https://docs.venice.ai/api-reference/endpoint/image/styles`
- Edit: `https://docs.venice.ai/api-reference/endpoint/image/edit`
- Multi-edit: `https://docs.venice.ai/api-reference/endpoint/image/multi-edit`
- Upscale: `https://docs.venice.ai/api-reference/endpoint/image/upscale`
- Background removal: `https://docs.venice.ai/api-reference/endpoint/image/background-remove`
- Current image models: `https://docs.venice.ai/models/image`
