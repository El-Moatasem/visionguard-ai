# Architecture - SAM 3.1 object-tracking pipeline

**Scope:** Local hackathon MVP. No production-ready authentication, durable queue, camera stream processing, or automatic danger detection.

## Data flow

1. Next.js mobile-first UI uploads a licensed or consented short MP4/MOV file to FastAPI (`POST /api/v1/videos`).
2. API stores it in `var/uploads` with a generated ID, SHA-256 hash, signature sniffing and 25 MiB cap. An optional `ffprobe` examines container FPS, codec and duration.
3. User explicitly clicks **Analyze with SAM** (billable), creating `POST /api/v1/videos/{id}/tracking-jobs`. No paid inference is triggered just by uploading.
4. A local FastAPI background task uses the existing SAM adapter (`backend/app/services/sam.py`) to upload the clip to Meta once and issue **separate** `person` and `forklift` concept requests.
5. The Meta Python parser decodes model boxes/masks. The existing adapter saves summary JSON and SVG masks privately under `var/tracking/{job_id}/raw`.
6. `tracking_report.py` normalizes object IDs to `person:{id}` or `forklift:{id}`, validates geometry, deduplicates boxes, and splits continuity fragments whenever a frame gap is observed.
7. The result is saved in `var/tracking/{job_id}.result.json`, retrievable through a read-only local JSON API. UI polls for completion and draws color-coded box overlays using approximate constant-FPS timing.

## API contracts

- `POST /api/v1/videos/{video_id}/tracking-jobs`: creates billable tracking job; rejects missing API key, WebM, incompatible codec, clips > 30 s when duration is known, and overlapping jobs.
- `GET /api/v1/videos/{video_id}/tracking-jobs`: lists recent jobs.
- `GET /api/v1/tracking-jobs/{job_id}`: queued / running / completed / failed / interrupted.
- `GET /api/v1/tracking-jobs/{job_id}/result`: report only after successful completion.

## Reliability boundaries

- The background-task runner is **single-process only** and is not crash durable. A restart marks abandoned jobs `interrupted` when queried.
- A separate tracking request per concept means IDs are namespace-scoped; two `0` IDs are unrelated across concepts.
- An observed gap **cannot** establish whether a reappearing ID is the same physical object. A new fragment is created and marked unverified.
- Source HTML5 playback timestamps approximated as `round(seconds * fps)` may not match SAM frame indices for variable-frame-rate or reordered video; do not treat them as evidentiary timestamps. Later use Meta `@meta-sam/video` / `@meta-sam/react` frame-accurate playback or validated time mappings.
- No detection confidence is synthesized when the API has not supplied it. The current overlay draws source-pixel boxes, not full semantic masks.
- Neither image-space overlap nor model tracking proves risk, velocity, world-space distance, collision trajectory or compliance. Danger-event rules are for the next branch.

## Privacy and operations

- API endpoints are **unauthenticated**, so run bound to loopback only. Never expose this prototype publicly with private video.
- Never commit `.env`, `var/`, raw video, incident artifacts or paid API credentials. `.gitignore` covers these runtime files.
- Both Meta prompts are billable, and repeated analysis creates new charges. Meta docs: https://dev.meta.ai/docs/sam/overview and https://dev.meta.ai/docs/pricing-rate-limits.
