# ElevenLabs — API Reference

ElevenLabs **Scribe** is a batch (REST) speech-to-text API. There is no streaming/WebSocket transcription endpoint.

## API Endpoint

- Base URL: `https://api.elevenlabs.io`
- Batch: `POST {base}/v1/speech-to-text` (multipart/form-data)

## Authentication

- Header: `xi-api-key: <API_KEY>`
- Get a key: https://elevenlabs.io/app/settings/api-keys

## Modules / Libraries Used (what we can use)

- `httpx` — async HTTP client for the batch request.

## Languages

- **90+ languages** (Scribe v2). Accepts ISO-639-1 (e.g. `en`) or ISO-639-3 (e.g. `eng`) language hints; auto-detects when omitted.

## Parameters

All parameters for `POST /v1/speech-to-text`:

| Parameter | Description | Default | Notes |
|-----------|-------------|---------|-------|
| `model_id` | Transcription model to use | — (required) | Enum: `scribe_v1`, `scribe_v2` |
| `file` | Audio/video file to transcribe | — (required, or `cloud_storage_url`) | Min 100 ms; max 5 GB; all major audio/video formats |
| `language_code` | Language hint | `null` (auto-detect) | ISO-639-1 or ISO-639-3 (e.g. `en` / `eng`) |
| `tag_audio_events` | Tag non-speech events like `(laughter)` | `true` | boolean |
| `num_speakers` | Maximum number of speakers | `null` (model max) | integer 1–32 |
| `timestamps_granularity` | Timestamp granularity | `word` | Enum: `none`, `word`, `character` |
| `diarize` | Label which speaker is talking | `false` | boolean |
| `diarization_threshold` | Diarization sensitivity | `null` | double 0.1–0.4 |
| `cloud_storage_url` | File URL instead of upload | `null` | Alternative to `file` |
| `keyterms` | Terms to bias recognition | `null` | List of strings (≤50 chars each; batch ≤1000) |
| `no_verbatim` | Remove filler words / false starts | `false` | boolean |
| `entity_detection` | Detect entities (SSN, names, etc.) | `null` | object config |
| `use_multi_channel` | Transcribe channels separately | `false` | boolean |
| `multichannel_output_style` | Combined vs per-channel output | `null` | Enum: `combined` |
| `webhook` | Process async + send webhook | `false` | boolean |
| `webhook_url` | Where to send the webhook | `null` | string |
| `webhook_metadata` | Custom data echoed in webhook | `null` | object |
| `enable_logging` | Zero-retention when `false` (enterprise) | `true` | Query param, boolean |

## References

- Official batch API reference: https://elevenlabs.io/docs/api-reference/speech-to-text/convert
- Capabilities overview: https://elevenlabs.io/docs/overview/capabilities/speech-to-text
- API keys: https://elevenlabs.io/app/settings/api-keys
