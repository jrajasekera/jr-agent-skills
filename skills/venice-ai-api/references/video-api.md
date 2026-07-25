# Video generation, upscaling, references, and transcription

Venice video generation is asynchronous. The stable operational pattern is:

```text
POST /video/quote
POST /video/queue
POST /video/retrieve
POST /video/complete
```

`/video/complete` finalizes and removes Venice-hosted media after the client has downloaded it. It is not a synchronous generation endpoint.

A separate Beta endpoint, `POST /video/transcriptions`, transcribes audio from a public video URL.

## Discover current video models

```bash
curl -sS "https://api.venice.ai/api/v1/models?type=video" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Before forming a request, inspect:

- `model_type` such as text-to-video, image-to-video, video-to-video, or upscale;
- allowed `durations[]`;
- allowed `aspect_ratios[]`;
- allowed `resolutions[]`;
- whether audio is supported or configurable;
- required source media;
- prompt-character limit;
- support for end frames, reference images, elements, scenes, input audio, or input video;
- `offline`, beta/access, region, privacy, and deprecation metadata.

Video model IDs and allowed combinations change frequently. Never build a permanent switch statement from a historical catalog.

## 1. Quote the exact request

```bash
curl -sS https://api.venice.ai/api/v1/video/quote \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_VIDEO_MODEL\",
    \"duration\": \"5s\",
    \"aspect_ratio\": \"16:9\",
    \"resolution\": \"720p\",
    \"audio\": true
  }"
```

The response includes a USD `quote`. Quote with every billable field that will be used in `/video/queue`; otherwise the estimate can be wrong.

Application policy should compare the quote with:

- a per-request maximum;
- the remaining account/wallet balance;
- a daily/project budget;
- the number of planned variants or retries.

Do not auto-submit an expensive job merely because the API accepted the quote request.

## 2. Queue generation

```bash
curl -sS https://api.venice.ai/api/v1/video/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_VIDEO_MODEL\",
    \"prompt\": \"A slow aerial push toward a glass observatory on a snowy ridge at blue hour\",
    \"negative_prompt\": \"low resolution, distorted architecture, flicker\",
    \"duration\": \"5s\",
    \"aspect_ratio\": \"16:9\",
    \"resolution\": \"720p\",
    \"audio\": true
  }"
```

A queue response contains at least the model and `queue_id`, and can also contain a temporary `download_url` for some provider-backed models:

```json
{
  "model": "<model>",
  "queue_id": "<uuid>",
  "download_url": "https://..."
}
```

Persist all returned fields. The correct key is `queue_id`, not `queueid`.

## Queue request fields

Availability and accepted combinations are model-specific.

| Field | Purpose |
|---|---|
| `model` | Required current video model ID |
| `prompt` | Required for generation/edit models; not accepted by the current dedicated Topaz upscaler |
| `negative_prompt` | Optional undesired visual traits on supporting generation models |
| `duration` | Generation-model value such as `5s` or `Auto`; dedicated upscalers can detect source duration |
| `aspect_ratio` | Model-specific ratio |
| `resolution` | Model-specific generation size; the Topaz upscaler rejects it |
| `upscale_factor` | `1`, `2`, or `4` for the current dedicated video upscaler |
| `audio` | Generate/retain audio when supported |
| `image_url` | Starting frame or image-to-video source |
| `end_image_url` | Ending frame or transition target |
| `audio_url` | Background or conditioning audio on supporting models |
| `video_url` | Video-to-video or upscale source |
| `reference_image_urls[]` | Identity/style/subject image references |
| `reference_video_urls[]` | Identity/subject video references on supporting models |
| `elements[]` | Named subject elements for advanced reference-to-video models |
| `scene_image_urls[]` | Named scene references for advanced models |
| `consents` | Provider-specific attestation, sent only after the exact server challenge described below |

Public URLs must be fetchable without cookies or interactive authentication. Data URLs count toward request size and can trigger `413`; use secure temporary object-storage URLs for large assets when privacy policy allows.

## Text-to-video

```json
{
  "model": "<current-text-to-video-model>",
  "prompt": "A golden retriever chases a red frisbee across a beach at sunset, low tracking shot",
  "duration": "6s",
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "audio": true
}
```

Good prompts separate:

- subject and action;
- environment and time;
- camera framing and motion;
- lighting and visual style;
- timing or shot progression;
- sound only when the model supports audio.

Do not request a duration, resolution, or audio mode absent from the selected model's constraints.

## Image-to-video

```json
{
  "model": "<current-image-to-video-model>",
  "prompt": "The camera slowly dollies backward while snow drifts across the foreground; preserve the building design",
  "image_url": "https://example.com/observatory.png",
  "duration": "5s",
  "aspect_ratio": "16:9"
}
```

For first-frame conditioning:

- match the requested aspect ratio to the input where possible;
- describe motion rather than redescribing every static detail;
- state preservation requirements explicitly;
- avoid conflicting camera motions;
- use a supported end frame only when needed.

## Start and end frames

```json
{
  "model": "<supporting-model>",
  "prompt": "A smooth transition from daylight to night as the city lights turn on",
  "image_url": "https://example.com/day.png",
  "end_image_url": "https://example.com/night.png",
  "duration": "5s",
  "aspect_ratio": "16:9"
}
```

The endpoint accepting `end_image_url` does not guarantee every model honors it. Verify capability and constraints.

## Reference-image consistency

```json
{
  "model": "<supporting-reference-model>",
  "prompt": "The same character walks into a quiet cafe and sits by the window",
  "reference_image_urls": [
    "https://example.com/front.png",
    "https://example.com/profile.png",
    "https://example.com/outfit.png"
  ],
  "duration": "5s",
  "aspect_ratio": "16:9"
}
```

Current models can cap reference images, commonly at a single-digit count. Use diverse, clean views of the same subject. Do not exceed the live model limit.

## Elements and scene references

Advanced reference-to-video models can expose structured subject elements:

```json
{
  "model": "<advanced-reference-model>",
  "prompt": "@Element1 walks toward @Element2 across @Image1",
  "elements": [
    {
      "frontal_image_url": "https://example.com/person-a-front.png",
      "reference_image_urls": [
        "https://example.com/person-a-side.png"
      ]
    },
    {
      "frontal_image_url": "https://example.com/person-b-front.png"
    }
  ],
  "scene_image_urls": [
    "https://example.com/street.png"
  ],
  "duration": "5s"
}
```

Use the exact token convention documented by the selected model, such as `@Element1` and `@Image1`. Current platform-level caps can be lower than the general request schema; inspect both the endpoint and model metadata.

## Video-to-video

General video-to-video models can accept a source clip plus an instruction, but their exact fields remain model-specific:

```json
{
  "model": "<current-video-to-video-model>",
  "prompt": "Preserve the motion and composition while changing the scene to winter at blue hour",
  "video_url": "https://example.com/input.mp4",
  "duration": "Auto"
}
```

Confirm whether the selected model accepts `prompt`, `duration`, audio controls, and output sizing before submitting.

## Dedicated Topaz video upscaling

The current dedicated upscaler uses a narrower request contract:

```json
{
  "model": "topaz-video-upscale",
  "video_url": "https://example.com/input-video.mp4",
  "upscale_factor": 2
}
```

For this model:

- `upscale_factor` is `1`, `2` (default), or `4`; `1` enhances without enlarging;
- do not send `prompt` or `resolution`—they are rejected;
- do not rely on a caller-supplied duration; Venice detects duration, frame rate, and dimensions from the source;
- the current guide accepts MP4, MOV, and WebM by HTTPS or `data:video/...;base64,...`, up to 300 seconds;
- query `GET /models?type=video` before use in case the model ID or limits change.

Quote the upscale separately. `input_height` lets the quote endpoint estimate the output pricing tier:

```json
{
  "model": "topaz-video-upscale",
  "duration": "10",
  "input_height": 720
}
```

The queue call is ultimately billed from the inspected source metadata, so treat the quote as a preflight estimate and enforce an application budget.

## Audio inputs and generated audio

Some models can:

- generate synchronized sound from the visual prompt;
- accept `audio_url` as conditioning/background audio;
- preserve or replace audio in video-to-video jobs.

Check `audio` and `audio_configurable` metadata. Current documented input-audio limits can include format, duration, and file-size restrictions. Validate them instead of assuming arbitrary MP3/WAV support.

## Seedance face-media consent handshake

Eligible Seedance image-to-video and reference-to-video models can require an explicit likeness attestation when Venice detects a human face in `image_url`, `end_image_url`, `reference_image_urls`, or `reference_video_urls`.

1. Submit the ordinary queue request **without** a consent object.
2. A detected face can produce a non-charging `409` response with `error.code: "needs_consent"`, `consent_flow: "seedance"`, `face_media_roles`, and server-provided `consent.policy_text` / `consent_version`.
3. Present the returned policy text to the responsible user or operator.
4. Resubmit the same request body with:

```json
{
  "consents": {
    "seedance": {
      "confirmed_terms_and_privacy": true,
      "confirmed_legal_right": true,
      "confirmed_screening_acknowledged": true
    }
  }
}
```

All three values must be the boolean `true`. Do not add `consent_version` or any extra field—the server owns the policy version and rejects malformed consent with `400`.

Consent is not a content-policy bypass. Minor/sexual-content combinations and recognizable public-figure likenesses can return non-charging `422` failures that cannot be overridden. Exact previously attested media bytes can be deduplicated; re-encoding, resizing, cropping, or adding a new face-bearing input can trigger a new challenge. Never pre-fill this attestation or claim legal rights on the user's behalf.

## 3. Retrieve status or media

```bash
curl -sS https://api.venice.ai/api/v1/video/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_VIDEO_MODEL\",
    \"queue_id\": \"$QUEUE_ID\",
    \"delete_media_on_completion\": false
  }" \
  --output retrieve-response
```

There are two completion paths.

### Path A: binary response

For some models, completed retrieval returns raw `video/mp4` bytes. Save the body.

### Path B: JSON status plus prior `download_url`

For some provider-backed models, `/queue` returned a `download_url`. `/retrieve` then returns JSON status:

```json
{
  "status": "COMPLETED",
  "average_execution_time": 145000,
  "execution_duration": 151200
}
```

When status is complete, fetch the preserved `download_url`. It is short-lived and provider-specific; download immediately, retry transient download failures only a small number of times, and never treat the URL as durable storage.

While processing:

```json
{
  "status": "PROCESSING",
  "average_execution_time": 145000,
  "execution_duration": 53200
}
```

Times are milliseconds. Polling faster does not make the job run faster.

## 4. Complete and clean up

After the output is safely stored:

```bash
curl -sS https://api.venice.ai/api/v1/video/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VENICE_VIDEO_MODEL\",
    \"queue_id\": \"$QUEUE_ID\"
  }"
```

Alternatively, set `delete_media_on_completion: true` on retrieval if the client can atomically persist the response. Do not call `/complete` before downloading.

## Robust TypeScript polling loop

```typescript
import { writeFile } from "node:fs/promises";

const base = "https://api.venice.ai/api/v1";
const headers = {
  Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
  "Content-Type": "application/json",
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function parseError(response: Response): Promise<never> {
  const text = await response.text();
  throw new Error(`Venice ${response.status}: ${text.slice(0, 1000)}`);
}

async function waitForVideo(options: {
  model: string;
  queueId: string;
  downloadUrl?: string;
  outputPath: string;
  timeoutMs?: number;
}): Promise<void> {
  const deadline = Date.now() + (options.timeoutMs ?? 20 * 60_000);

  while (Date.now() < deadline) {
    const response = await fetch(`${base}/video/retrieve`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model: options.model,
        queue_id: options.queueId,
        delete_media_on_completion: false,
      }),
    });

    if (!response.ok) await parseError(response);

    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.startsWith("video/") || contentType === "application/octet-stream") {
      await writeFile(options.outputPath, Buffer.from(await response.arrayBuffer()));
      return;
    }

    const status = await response.json() as {
      status?: string;
      average_execution_time?: number;
      execution_duration?: number;
    };

    if (status.status === "COMPLETED") {
      if (!options.downloadUrl) {
        throw new Error("Job completed but no binary body or download_url is available");
      }
      const download = await fetch(options.downloadUrl);
      if (!download.ok) await parseError(download);
      await writeFile(options.outputPath, Buffer.from(await download.arrayBuffer()));
      return;
    }

    if (status.status !== "PROCESSING") {
      throw new Error(`Unexpected video status: ${JSON.stringify(status)}`);
    }

    const estimate = status.average_execution_time ?? 50_000;
    await sleep(Math.min(Math.max(estimate / 10, 3_000), 15_000));
  }

  throw new Error(`Timed out waiting for video job ${options.queueId}`);
}

async function completeVideo(model: string, queueId: string): Promise<void> {
  const response = await fetch(`${base}/video/complete`, {
    method: "POST",
    headers,
    body: JSON.stringify({ model, queue_id: queueId }),
  });
  if (!response.ok) await parseError(response);
}
```

Only call `completeVideo` after `waitForVideo` has persisted a verified non-empty output.

## Video transcription

`POST /video/transcriptions` is synchronous and currently Beta. It accepts a public video URL, including supported YouTube URLs.

```bash
curl -sS https://api.venice.ai/api/v1/video/transcriptions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=...",
    "response_format": "json"
  }'
```

JSON response:

```json
{
  "transcript": "...",
  "lang": "en"
}
```

`response_format: "text"` can return plain text. This endpoint is for a public URL, not arbitrary multipart video upload. For a local/private video:

```bash
ffmpeg -i input.mp4 -vn -c:a aac audio.m4a
```

Then send the audio file to `/audio/transcriptions`.

## Failure handling

| Status | Typical cause |
|---|---|
| `400` | Unsupported model fields/constraints, missing source media, malformed URL, or malformed Seedance consent |
| `401` | Invalid key or gated model |
| `402` | Insufficient balance |
| `403` | Region or entitlement restriction |
| `404` | Unknown/expired `queue_id` on retrieve/complete |
| `409` | Seedance face media needs the explicit consent handshake; not billed |
| `413` | Source media or data URL too large |
| `422` | Content-policy/provider validation; Seedance policy blocks are not overrideable and are not billed |
| `429` | Model/key/concurrency limit |
| `500` | Queue/provider inference failure |
| `503` | Capacity/backlog, especially while retrieving status |

Retry transient failures with bounded exponential backoff. Do not blindly queue a second paid job because status polling briefly failed; continue using the original `queue_id` unless the API definitively reports the job failed or does not exist.

## Job-state persistence

For production, persist:

```text
client_job_id
model
queue_id
download_url (if returned)
quote
submitted_at
last_polled_at
status
request parameters hash
output object-storage URI
cleanup_completed_at
```

This prevents duplicate charges after process restarts and makes cleanup auditable.

## Sources of truth

- Video guide: `https://docs.venice.ai/guides/media/video-generation`
- Video upscaling: `https://docs.venice.ai/guides/media/video-upscaling`
- Seedance face consent: `https://docs.venice.ai/guides/media/seedance-face-consent`
- Quote: `https://docs.venice.ai/api-reference/endpoint/video/quote`
- Queue: `https://docs.venice.ai/api-reference/endpoint/video/queue`
- Retrieve: `https://docs.venice.ai/api-reference/endpoint/video/retrieve`
- Complete: `https://docs.venice.ai/api-reference/endpoint/video/complete`
- Transcription: `https://docs.venice.ai/api-reference/endpoint/video/transcriptions`
- Video models: `https://docs.venice.ai/models/video`
