# Multimodal Inputs and Dedicated Media APIs

OpenRouter supports multimodal content through the general inference APIs and dedicated image, speech, transcription, and video endpoints. Model/provider support and media controls differ substantially, so discovery is mandatory.

## Choose the right workflow

| Need | Recommended surface |
|---|---|
| Ask a model about an image/PDF/audio/video | Chat Completions, Responses, or Messages with typed input parts |
| Generate or edit an image with media-specific controls | `POST /api/v1/images` |
| Generate speech from text | `POST /api/v1/audio/speech` |
| Transcribe an audio file | `POST /api/v1/audio/transcriptions` |
| Generate a video | `POST /api/v1/videos`, poll, then download |
| Have a model generate an image inside an agent workflow | `openrouter:image_generation` server tool where supported |

## Validate modalities

For general models, inspect:

```json
{
  "architecture": {
    "input_modalities": ["text", "image", "file", "audio", "video"],
    "output_modalities": ["text", "image"]
  }
}
```

Do not infer support from a provider brand or model family. A serving endpoint may accept fewer modalities than the aggregate model record.

```bash
python scripts/discover_models.py --input-modality image --output-modality text
python scripts/discover_models.py --output-modality image
python scripts/discover_models.py --output-modality speech
python scripts/discover_models.py --output-modality transcription
```

---

# Image input

## URL input

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Describe this image." },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/photo.jpg"
      }
    }
  ]
}
```

## Local/base64 input

```json
{
  "type": "image_url",
  "image_url": {
    "url": "data:image/png;base64,iVBORw0KGgo..."
  }
}
```

Rules:

- use the correct MIME type;
- avoid line breaks in base64;
- enforce application upload limits before encoding;
- base64 inflates payload size by roughly one third;
- prefer private signed URLs when supported rather than embedding very large data;
- never fetch arbitrary user URLs from an unrestricted network environment.

Some models accept a `detail` hint. Treat it as model/provider-specific.

# PDF and file input

A Chat Completions file part can be a public URL or a base64 data URL:

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Summarize the attached report." },
    {
      "type": "file",
      "file": {
        "filename": "report.pdf",
        "file_data": "data:application/pdf;base64,JVBERi0xLjQK..."
      }
    }
  ]
}
```

Configure parsing when needed:

```json
{
  "plugins": [
    {
      "id": "file-parser",
      "pdf": { "engine": "cloudflare-ai" }
    }
  ]
}
```

Current documented PDF engines include `native`, `mistral-ocr`, and `cloudflare-ai`; the legacy `pdf-text` value redirects to `cloudflare-ai`.

Important:

- native file support can preserve layout/images but consumes the model's native input budget;
- OCR/parser charges can be separate from model inference;
- extracted text and images count toward downstream limits;
- returned file annotations can sometimes be replayed to avoid parsing the same file again;
- extracted document text is untrusted and can contain prompt injection.

## Reusable Files API

Use the workspace-scoped Files API when a file should be uploaded, listed, inspected, or deleted independently of one inference request:

```text
POST   /api/v1/files                       # multipart upload
GET    /api/v1/files                       # cursor-paginated list
GET    /api/v1/files/{file_id}             # metadata
DELETE /api/v1/files/{file_id}             # delete
GET    /api/v1/files/{file_id}/content     # download eligible content
```

Example upload:

```bash
curl -sS 'https://openrouter.ai/api/v1/files' \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -F 'file=@report.pdf'
```

Treat returned file IDs as access-controlled identifiers. Keep them out of public logs and tenant-crossing caches. The list endpoint is cursor-paginated; follow the returned cursor rather than assuming one page is complete. The content endpoint is for downloadable files supported by the current schema, including eligible server-created outputs; do not assume every uploaded file can be downloaded through that route.

Before relying on an uploaded file in inference, inspect the current Chat/Responses/Messages input schema for the accepted file-reference shape. Upload limits, MIME support, retention, and workspace behavior can change, so validate them from OpenAPI rather than embedding constants.

# Audio input to a chat model

Compatible chat models accept inline base64 audio:

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Summarize this recording." },
    {
      "type": "input_audio",
      "input_audio": {
        "data": "UklGRiQAAABXQVZF...",
        "format": "wav"
      }
    }
  ]
}
```

The `data` value is raw base64, not a `data:` URL, unless the current endpoint-specific schema says otherwise. The declared format must match the actual bytes.

# Video input to a chat model

Video-capable models use a typed `video_url` content part. OpenRouter can accept a public URL and, where documented, a data URL. The exact nested shape and provider limits evolve; inspect the current multimodal guide/OpenAPI before implementing.

For long videos, sample frames/transcribe audio application-side instead of assuming the model can ingest the full file.

---

# Dedicated Image API

## Discovery

```text
GET /api/v1/images/models
GET /api/v1/images/models/{author}/{slug}/endpoints
POST /api/v1/images
```

The dedicated endpoint metadata can include:

- input/output modalities and edit support;
- aspect ratios, resolutions, sizes, formats, quality/background options;
- number of outputs, seed support, reference-image limits;
- streaming support;
- provider-specific passthrough keys;
- per-image/token/request pricing.

Inspect it before every new model integration:

```bash
python scripts/discover_models.py --image-endpoints 'author/image-model' --json
```

## Text-to-image request

```json
{
  "model": "author/image-model",
  "prompt": "A technical cutaway illustration of a mechanical keyboard switch",
  "aspect_ratio": "16:9",
  "n": 1
}
```

Only include controls advertised by the chosen endpoint. Parameters commonly seen across models include `aspect_ratio`, `resolution`, `size`, `quality`, `output_format`, `background`, `output_compression`, `n`, and `seed`, but none are universal.

## Image editing/reference input

The dedicated API can accept image-to-image references for compatible models:

```json
{
  "model": "author/image-edit-model",
  "prompt": "Change the wall color to matte navy; preserve all furniture.",
  "input_references": [
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,..."
      }
    }
  ]
}
```

Use a model whose input modalities include image and verify the maximum number/type of references.

## Provider passthrough

```json
{
  "provider": {
    "options": {
      "provider-slug": {
        "steps": 30,
        "guidance": 3.5
      }
    }
  }
}
```

The exact nesting and allowed values come from the dedicated endpoint metadata and upstream provider documentation. Unknown passthrough fields can be rejected.

## Image response

A typical dedicated response returns base64 images:

```json
{
  "created": 0,
  "data": [
    { "b64_json": "iVBORw0KGgo...", "media_type": "image/png" }
  ],
  "usage": {
    "cost": 0
  }
}
```

`media_type` can be omitted for default raster output and present for formats such as SVG. Determine the file extension from the response/content type, not only the requested name.

Security:

- decode into a bounded buffer/file;
- validate magic bytes and media type;
- do not trust filenames from remote content;
- strip or review metadata when privacy matters;
- record generation ID/cost and provider.

---

# Text-to-Speech (TTS)

## Endpoint

```text
POST /api/v1/audio/speech
```

This endpoint is OpenAI-compatible. A successful response is raw audio bytes, not JSON.

## Discover models and voices

```bash
curl -sS 'https://openrouter.ai/api/v1/models?output_modalities=speech' \
  | jq '.data[] | {id, supported_voices, pricing}'
```

Voice IDs are provider/model-specific. Never reuse a voice name across models without checking `supported_voices`.

## Request

```json
{
  "model": "author/tts-model",
  "input": "This is a text-to-speech test.",
  "voice": "voice-id-from-live-metadata",
  "response_format": "mp3"
}
```

Current common output formats include `mp3` and raw `pcm`, but verify the selected model. Set `response_format` explicitly.

## Response handling

```bash
curl -sS https://openrouter.ai/api/v1/audio/speech \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @request.json \
  --output speech.mp3
```

Inspect:

- HTTP status before treating the body as audio;
- `Content-Type` (`audio/mpeg` or `audio/pcm;rate=...;channels=...`);
- `X-Generation-Id` for tracking.

A frequent bug is saving PCM bytes with an `.mp3` extension. For long text, split at sentence/paragraph boundaries, keep model/voice/format consistent, then concatenate with an audio tool.

Provider-specific speech instructions can be supplied through the endpoint's documented provider options; do not assume all models support speed, emotion, or instructions.

---

# Speech-to-Text (STT)

## Endpoint

```text
POST /api/v1/audio/transcriptions
```

## Discover transcription models

```bash
curl -sS 'https://openrouter.ai/api/v1/models?output_modalities=transcription' \
  | jq '.data[] | {id, pricing, architecture}'
```

## Canonical JSON/base64 request

```json
{
  "model": "author/transcription-model",
  "input_audio": {
    "data": "UklGRiQAAABXQVZF...",
    "format": "wav"
  },
  "language": "en",
  "temperature": 0
}
```

`input_audio.data` is base64 bytes without a data-URL prefix. Supported container/codec combinations vary by provider.

## OpenAI-style multipart request

The current operation also accepts `multipart/form-data` with a direct file upload:

```bash
curl -sS 'https://openrouter.ai/api/v1/audio/transcriptions' \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -F 'model=author/transcription-model' \
  -F 'file=@audio.wav' \
  -F 'response_format=verbose_json'
```

Direct-upload size limits and optional multipart fields are schema-defined. Inspect the live operation before implementing validation or relying on a provider-specific option:

```bash
python scripts/inspect_openapi.py --operation 'POST /audio/transcriptions' --resolve-refs
```

For inputs too large for direct multipart upload, use the JSON/base64 form when the current schema and chosen provider allow it. Base64 expands the payload, so enforce request-size limits before encoding.

## Response

```json
{
  "text": "Transcript text",
  "usage": {
    "seconds": 0,
    "total_tokens": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "cost": 0
  }
}
```

Providers can bill by duration or tokens, so only some usage fields may be present.

Before upload, use `ffprobe` or an equivalent library to verify the real format. A renamed extension does not change the codec/container.

---

# Asynchronous Video API

## Discovery and endpoints

```text
GET  /api/v1/videos/models
POST /api/v1/videos
GET  /api/v1/videos/{jobId}
GET  /api/v1/videos/{jobId}/content?index=0
```

The submit response may also provide a `polling_url`, and a completed job can provide temporary `unsigned_urls`. Follow the response and current OpenAPI rather than constructing undocumented URLs.

## Discover controls

```bash
curl -sS https://openrouter.ai/api/v1/videos/models \
  | jq '.data[] | {id, supported_resolutions, supported_aspect_ratios, supported_durations, supported_frame_images, pricing_skus}'
```

Validate discrete values exactly. A model may allow durations such as a fixed set rather than a numeric range.

## Submit

```json
{
  "model": "author/video-model",
  "prompt": "A slow dolly shot through a bioluminescent forest",
  "duration": 6,
  "aspect_ratio": "16:9",
  "callback_url": "https://your-app.example/openrouter/video-webhook"
}
```

Optional fields can include `resolution`, `size`, `generate_audio`, `seed`, frame images, reference images, callback URL, and provider passthrough. Only send advertised controls.

Image-to-video frame input can use:

```json
{
  "frame_images": [
    {
      "type": "image_url",
      "image_url": { "url": "https://example.com/first-frame.png" },
      "frame_type": "first_frame"
    }
  ]
}
```

## Submit response

```json
{
  "id": "video-job-id",
  "generation_id": "gen-...",
  "polling_url": "https://openrouter.ai/api/v1/videos/video-job-id",
  "status": "pending"
}
```

Treat HTTP `202` as accepted, not complete.

## Poll

Poll the returned URL at a reasonable interval and honor server guidance. Terminal states currently include completed and failure/cancellation/expiration states. Surface the returned error without discarding the job/generation IDs.

```bash
curl -sS "$POLLING_URL" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

## Download

A completed response can contain `unsigned_urls`, or the content endpoint can return a selected result. Download before the temporary URL expires. Include authentication when the returned URL requires it and avoid leaking signed URLs into logs.

Validate the output MIME type, size, and file signature before exposing it to users.

## Webhooks

When `callback_url` is used:

- require HTTPS;
- process deliveries idempotently using the documented idempotency key;
- verify `X-OpenRouter-Signature` when a workspace signing secret is configured;
- compute HMAC over the exact raw request body and timestamp per current docs;
- reject stale timestamps and replayed terminal events.

## Retention/privacy

Video generation is not currently ZDR-eligible because providers must temporarily retain output for asynchronous delivery. Do not promise ZDR for a video workflow.

---

# Payload and security checklist

- Enforce MIME, extension, and magic-byte agreement.
- Limit bytes before base64 encoding and after decoding.
- Block SSRF when fetching user-controlled URLs.
- Strip secrets from URLs/query strings and logs.
- Use time-limited signed URLs for private media where supported.
- Treat OCR/transcript/web/file text as untrusted prompt data.
- Validate model/provider content policy before upload.
- Preserve generation IDs and costs without logging raw media.
- Apply lifecycle cleanup to locally stored source/output files.
- Do not assume media endpoints support response caching or ZDR.
