# Mobile-first ingestion design and security notes

## Capture modes
1. **Select a local video file**: best for deterministic benchmark runs.
2. **Capture with phone**: HTML file input with `accept="video/*" capture="environment"`; browser decides whether camera capture is offered.
3. **Preview + MediaRecorder**: on HTTPS/localhost, ask camera permission and record up to 15s to MP4 or WebM depending on browser support.

These are clip capture modes, **not real-time hazard analysis**. The hosted SAM workflow remains asynchronous. No low-latency guarantee is claimed.

## Data lifecycle (prototype only)
- POST `/api/v1/videos` writes a temporary file while streaming 1 MiB chunks.
- Payload is rejected if it exceeds `VIDEO_MAX_BYTES` (default 25 MiB).
- File container is signature checked and stored as `var/uploads/<uuid>.<ext>`.
- JSON manifest contains original filename (display only), SHA-256, timestamp, media type, and SAM container readiness flag.
- GET `/api/v1/videos` and GET `/api/v1/videos/<id>` return metadata.
- GET `/api/v1/videos/<id>/file` supports browser playback and byte-range responses.
- `var/` is ignored by Git. No uploaded videos or API keys should be committed.

## Config
| Variable | Default | Description |
|---|---|---|
| `VIDEO_MAX_BYTES` | `26214400` | Server enforced max file bytes |
| `VIDEO_STORAGE_DIR` | `<repo>/var/uploads` | Local data directory |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Server-side Next.js rewrite target |
| `MODEL_API_KEY` | unset | Meta API key (only for Day 1 CLI) |

## Before deployment
Do **not** expose this storage API publicly unchanged. Add auth, signed review access, upload and rate limits, a cleanup/deletion policy, content/codec validation, malware scanning or isolation, and secure object storage. Videos may contain identifiable individuals; obtain permission and minimize retention. Never promise industrial real-time protection without substantial validation.
