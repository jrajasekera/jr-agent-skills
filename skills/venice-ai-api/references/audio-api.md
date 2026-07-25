# Audio APIs: speech, voice cloning, transcription, music, and long-form generation

Venice currently has four distinct audio workflows:

1. synchronous text-to-speech through `/audio/speech`;
2. temporary cloned-voice handle creation through `/audio/voices`, followed by `/audio/speech`;
3. synchronous file transcription through `/audio/transcriptions`;
4. asynchronous music, sound-effect, or long-form audio generation through `/audio/quote`, `/audio/queue`, `/audio/retrieve`, and `/audio/complete`.

Do not mix their request shapes.

## Discover current audio models

```bash
curl -sS "https://api.venice.ai/api/v1/models?type=tts" \
  -H "Authorization: Bearer $VENICE_API_KEY"

curl -sS "https://api.venice.ai/api/v1/models?type=asr" \
  -H "Authorization: Bearer $VENICE_API_KEY"

curl -sS "https://api.venice.ai/api/v1/models?type=music" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Never freeze a TTS voice list. Voices are case-sensitive and model-specific. Read `model_spec.voices` and `default_voice` for the chosen model.

## Text-to-speech: `/audio/speech`

### cURL

```bash
curl -sS https://api.venice.ai/api/v1/audio/speech \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_TTS_MODEL\",
    \"voice\": \"$VENICE_TTS_VOICE\",
    \"input\": \"Hello from Venice.\",
    \"response_format\": \"mp3\",
    \"speed\": 1.0,
    \"streaming\": false
  }" \
  --output speech.mp3
```

### OpenAI Python SDK

```python
import os
from pathlib import Path
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["VENICE_API_KEY"],
    base_url="https://api.venice.ai/api/v1",
)

response = client.audio.speech.create(
    model=os.environ["VENICE_TTS_MODEL"],
    voice=os.environ["VENICE_TTS_VOICE"],
    input="Hello from Venice.",
    response_format="mp3",
    speed=1.0,
)

Path("speech.mp3").write_bytes(response.read())
```

### Current request fields

| Field | Notes |
|---|---|
| `input` | Required; current endpoint cap is 4096 characters. Split longer text at sentence boundaries. |
| `model` | TTS model from `GET /models?type=tts`. |
| `voice` | Must belong to the selected model. Case-sensitive. |
| `response_format` | `mp3`, `opus`, `aac`, `flac`, `wav`, or `pcm`. |
| `speed` | Current endpoint range is 0.25–4.0; moderate values sound most natural. |
| `streaming` | Streams generated audio instead of waiting for the complete file. |
| `language` | Model-specific hint; accepted conventions differ by provider. |
| `prompt` | Delivery/emotion instruction on supporting models. |
| `temperature` | Sampling control on supporting models. |
| `top_p` | Nucleus sampling on supporting models. |

Unsupported style controls can be silently ignored. Do not infer support from a successful HTTP status; inspect the current model capability or run a controlled A/B test.

### Response handling

The response body is raw audio. Check `Content-Type` before saving:

```python
import requests

res = requests.post(url, headers=headers, json=payload, timeout=180, stream=True)
res.raise_for_status()

content_type = res.headers.get("Content-Type", "")
if not content_type.startswith("audio/") and content_type != "application/octet-stream":
    raise RuntimeError(f"Expected audio, received {content_type}: {res.text[:500]}")

with open("speech.mp3", "wb") as output:
    for chunk in res.iter_content(64 * 1024):
        if chunk:
            output.write(chunk)
```

For `pcm`, confirm sample rate, channel count, and integer format from the current endpoint docs before playback. The current documented PCM format is raw signed 16-bit little-endian at 24 kHz, but clients should not hardcode provider details without validation.

### Long narration

Because `input` is capped, split on sentence or paragraph boundaries rather than arbitrary character positions. For each chunk:

1. use the same model, voice, language, speed, and style controls;
2. write a lossless intermediate format when practical;
3. concatenate with `ffmpeg` or an audio library;
4. normalize gaps and loudness after assembly;
5. preserve order and retry only the failed chunk.

Avoid sending hundreds of chunks concurrently. Rate-limit and cost controls still apply.

### Voice cloning: `/audio/voices`

Some TTS models expose a `voice_cloning` object in `GET /models?type=tts`. Validate that object before uploading reference audio. Current metadata can include:

```json
{
  "voice_cloning": {
    "mode": "zero_shot",
    "accepted_formats": ["mp3", "wav", "flac", "m4a"],
    "min_sample_seconds": 5,
    "retention_days": 7
  }
}
```

Create a temporary, model-bound handle with multipart form data:

```bash
curl -sS https://api.venice.ai/api/v1/audio/voices \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "model=$VENICE_TTS_MODEL" \
  -F "file=@./reference-voice.wav"
```

Response:

```json
{
  "id": "vv_voice_abc123xyz",
  "model": "<same-model-id>"
}
```

Use the returned handle with the **same model**:

```bash
curl -sS https://api.venice.ai/api/v1/audio/speech \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_TTS_MODEL\",
    \"voice\": \"$VENICE_VOICE_ID\",
    \"input\": \"This sentence uses the authorized reference voice.\",
    \"response_format\": \"mp3\"
  }" \
  --output cloned-voice.mp3
```

Operational rules:

- voice handles are model-specific; an incompatible model/handle pair returns `400`;
- the current documented workflow is zero-shot and stores reference audio temporarily rather than creating a permanent trained voice;
- handles expire according to `voice_cloning.retention_days`; re-upload after expiration;
- use clean, single-speaker speech with minimal background noise and at least the model's minimum duration;
- validate file type and size before upload, and treat `413` as a signal to shorten/compress the sample;
- store the handle as sensitive biometric metadata and delete local reference copies according to product policy;
- clone only a voice the user owns or has explicit, documented authorization to use; do not use this workflow for impersonation, fraud, bypassing voice authentication, or deceptive attribution.

## Speech-to-text: `/audio/transcriptions`

This endpoint is multipart, not JSON/base64.

```bash
curl -sS https://api.venice.ai/api/v1/audio/transcriptions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "file=@meeting.m4a" \
  -F "model=$VENICE_ASR_MODEL" \
  -F "response_format=json" \
  -F "timestamps=true"
```

### OpenAI Python SDK

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["VENICE_API_KEY"],
    base_url="https://api.venice.ai/api/v1",
)

with open("meeting.m4a", "rb") as audio:
    transcript = client.audio.transcriptions.create(
        file=audio,
        model=os.environ["VENICE_ASR_MODEL"],
        response_format="json",
        language="en",
        # Venice-specific; pass through only if the SDK allows extra fields.
        extra_body={"timestamps": True},
    )

print(transcript.text)
```

### Current input behavior

- Upload a real multipart file part named `file`.
- Common supported formats include WAV/WAVE, FLAC, M4A, AAC, MP4, MP3, OGG/OGA, and WEBM.
- The current documented file-size ceiling is 25 MB.
- `language` is a hint and is ignored by models that do not support it.
- `timestamps=true` can return word, segment, or character timing depending on the model.
- Cost is generally based on audio duration; read `pricing.per_audio_second` from the current ASR model.

The endpoint reference currently guarantees `json` and `text`. Venice's model guide also describes `verbose_json`, `srt`, and `vtt` for some models. Treat those additional formats as schema/model-sensitive: check the current endpoint enum or make a small test before relying on them.

### Long files

For oversized or very long files:

```bash
ffmpeg -i long-recording.m4a \
  -f segment -segment_time 600 -reset_timestamps 1 \
  -c:a aac chunk-%03d.m4a
```

Then:

1. transcribe chunks with bounded concurrency;
2. offset timestamps by each chunk's true start time;
3. account for overlap if using overlapping windows;
4. deduplicate repeated boundary text;
5. store model ID and language alongside the transcript.

Do not use `/video/transcriptions` for an arbitrary local video file. Either upload its audio track to `/audio/transcriptions` or host a supported public video URL and use the video endpoint.

## Async music and long-form audio

### Lifecycle

```text
POST /audio/quote
POST /audio/queue
POST /audio/retrieve
POST /audio/complete
```

Always persist both `model` and `queue_id`.

### 1. Quote

```bash
curl -sS https://api.venice.ai/api/v1/audio/quote \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_MUSIC_MODEL\",
    \"duration_seconds\": 60
  }"
```

Current quote inputs include:

- `model`
- `duration_seconds` for duration-priced models
- `character_count` for character-priced long narration models

The response contains an estimated USD `quote`. Reject or require approval when it exceeds the application's maximum.

### 2. Queue

```bash
curl -sS https://api.venice.ai/api/v1/audio/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_MUSIC_MODEL\",
    \"prompt\": \"Uplifting indie-folk instrumental, 120 BPM, warm acoustic guitar\",
    \"duration_seconds\": 60,
    \"force_instrumental\": true
  }"
```

Response shape includes:

```json
{
  "model": "<model>",
  "queue_id": "<uuid>",
  "status": "QUEUED"
}
```

Use `queue_id`, never the legacy spelling `queueid`.

### Queue fields

| Field | Use only when model supports it |
|---|---|
| `prompt` | Required description of the audio |
| `lyrics_prompt` | Explicit lyrics/text on lyric-capable or lyric-required models |
| `duration_seconds` | Duration-aware models |
| `force_instrumental` | `supports_force_instrumental` |
| `lyrics_optimizer` | `supports_lyrics_optimizer`; do not also send `lyrics_prompt` |
| `voice` | Voice-enabled music/long-audio model |
| `language_code` | `supports_language_code` |
| `speed` | `supports_speed`; honor `min_speed` and `max_speed` |

Probe these fields on `GET /models?type=music` before constructing the request.

### 3. Retrieve

```bash
curl -sS https://api.venice.ai/api/v1/audio/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_MUSIC_MODEL\",
    \"queue_id\": \"$QUEUE_ID\",
    \"delete_media_on_completion\": false
  }" \
  --output retrieve-response
```

While processing, the endpoint returns JSON similar to:

```json
{
  "status": "PROCESSING",
  "average_execution_time": 20000,
  "execution_duration": 5200
}
```

Times are milliseconds. When complete, the endpoint returns binary audio. Inspect `Content-Type` on every poll rather than assuming JSON.

### 4. Complete

After successfully storing the audio:

```bash
curl -sS https://api.venice.ai/api/v1/audio/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_MUSIC_MODEL\",
    \"queue_id\": \"$QUEUE_ID\"
  }"
```

`/audio/complete` is a cleanup/finalization call. It does not generate audio synchronously. Use `delete_media_on_completion: true` during retrieval only when the client can safely persist the media before the response is lost.

## Robust async Python loop

```python
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

BASE = "https://api.venice.ai/api/v1"
HEADERS = {
    "Authorization": f"Bearer {os.environ['VENICE_API_KEY']}",
    "Content-Type": "application/json",
}


def post_json(path: str, payload: dict[str, Any], timeout: int = 60) -> requests.Response:
    response = requests.post(
        f"{BASE}{path}",
        headers=HEADERS,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def generate_audio(model: str, prompt: str, duration_seconds: int, output: Path) -> None:
    quote = post_json(
        "/audio/quote",
        {"model": model, "duration_seconds": duration_seconds},
    ).json()["quote"]

    maximum = float(os.environ.get("VENICE_MAX_AUDIO_USD", "1.00"))
    if quote > maximum:
        raise RuntimeError(f"Quote ${quote:.4f} exceeds limit ${maximum:.4f}")

    queued = post_json(
        "/audio/queue",
        {
            "model": model,
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "force_instrumental": True,
        },
    ).json()
    queue_id = queued["queue_id"]

    downloaded = False
    try:
        deadline = time.monotonic() + 20 * 60
        delay = 3.0

        while time.monotonic() < deadline:
            response = post_json(
                "/audio/retrieve",
                {
                    "model": model,
                    "queue_id": queue_id,
                    "delete_media_on_completion": False,
                },
                timeout=180,
            )
            content_type = response.headers.get("Content-Type", "")

            if content_type.startswith("audio/") or content_type == "application/octet-stream":
                output.write_bytes(response.content)
                downloaded = True
                return

            body = response.json()
            status = body.get("status")
            if status != "PROCESSING":
                raise RuntimeError(f"Unexpected audio status: {body}")

            estimate_ms = body.get("average_execution_time")
            if isinstance(estimate_ms, (int, float)):
                delay = min(max(estimate_ms / 1000 / 10, 2.0), 10.0)
            time.sleep(delay)

        raise TimeoutError(f"Audio job {queue_id} did not finish before deadline")
    finally:
        if downloaded:
            post_json("/audio/complete", {"model": model, "queue_id": queue_id})
```

A production version should add bounded retry logic for transient HTTP failures while preserving the same job identifiers.

## Audio errors

| Status | Typical cause |
|---|---|
| `400` | Invalid model/voice pair, input length, unsupported format, bad duration/lyrics combination |
| `401` | Invalid key or gated model |
| `402` | Insufficient account or wallet credit |
| `403` | Entitlement or region restriction |
| `404` | Unknown or expired async `queue_id` |
| `413` | File/payload too large on endpoints that expose this status |
| `415` | JSON versus multipart mismatch |
| `422` | Content policy or upstream audio validation; inspect endpoint-specific body |
| `429` | Rate/concurrency limit |
| `500` / `503` | Inference or capacity failure |

An audio-generation `422` can include a safer `suggested_prompt`. Do not silently replace the user's request; surface the change or obtain consent before one modified retry.

## Sources of truth

- TTS: `https://docs.venice.ai/api-reference/endpoint/audio/speech`
- TTS models: `https://docs.venice.ai/models/text-to-speech`
- Voice cloning guide: `https://docs.venice.ai/guides/media/voice-cloning`
- Create voice handle: `https://docs.venice.ai/api-reference/endpoint/audio/voices`
- Transcription: `https://docs.venice.ai/api-reference/endpoint/audio/transcriptions`
- ASR models: `https://docs.venice.ai/models/speech-to-text`
- Audio quote: `https://docs.venice.ai/api-reference/endpoint/audio/quote`
- Audio queue: `https://docs.venice.ai/api-reference/endpoint/audio/queue`
- Audio retrieve: `https://docs.venice.ai/api-reference/endpoint/audio/retrieve`
- Audio complete: `https://docs.venice.ai/api-reference/endpoint/audio/complete`
