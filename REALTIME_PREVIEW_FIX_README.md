# VisionGuard AI — progressive SAM preview and failure diagnostics

This archive is based on the earlier `VisionGuard_AI_Performance_Optimized_Full_Codebase_FIXED_2026-11-01.zip`, not your current uncommitted local tree. **Do not overwrite running servers or active billable jobs.** No GitHub push has been made.

## What this does

- Exposes box-only snapshots from the Meta SAM 3.1 video stream, approximately every 2 seconds when new parser snapshots arrive. `GET /api/v1/tracking-jobs/{id}/preview` is a read-only endpoint. A missing preview returns 404 until observations exist.
- Frontend polls this endpoint and displays provisional tracking boxes while inference continues; `requestVideoFrameCallback` and the existing frame index keep overlays aligned during playback.
- Reports actual phases and parser revisions in the job status (`uploading`, `segmenting`, `streaming`, `summarizing`, `concept_completed`, etc.). **Revision is NOT a completion percentage.**
- Persists a partial preview if inference fails after emitting boxes, and exposes a safe exception *class name* (`failure_type`). The full traceback is only logged by FastAPI. No API key or raw exception text is sent to the browser.
- Requires FFprobe, positive FPS/dimensions and at most 1080p/30fps **before** starting a billable request, so the video player can map frame indices to timestamps. The uploaded/played file is exactly the analyzed file; no on-the-fly transcode is performed.
- Defaults to the existing two SAM concept requests. For your **first small live test** set `SAM_DEMO_CONCEPTS=person` in the backend environment; this deliberately skips forklift until you re-enable the default.
- `SAM_MASK_ENCODING=default` can omit the optional `one_bit` request metadata to troubleshoot a Meta 400 response. Default remains `one_bit`.
- No automatic retries of paid SAM requests. If Meta's event stream fails remotely, diagnostics and any existing partial preview survive, but the job is marked FAILED and no final safety report is produced.
- Loop video playback while the SAM job is running; play/seek the uploaded clip to view observed boxes. No frames or labels are fabricated. **This is progressive analysis of an uploaded clip, not real-time live camera inference.**

## 1. Stop active jobs and back up

From your checkout:

```bash
git status --short
git diff > ../visionguard-local-before-streaming.patch
```

Stop both FastAPI and Next.js *only when no existing paid SAM request is in progress*. Do not delete `var/` or your `.env` files.

## 2. Apply the changed-files ZIP (recommended)

From the **visionguard-ai repository root**:

```bash
unzip -o ~/Downloads/VisionGuard_AI_SAM_Streaming_Preview_Changed_Files_2026-11-01.zip -d .
```

Or, from the **parent directory** of `visionguard-ai`, extract the full-codebase ZIP:

```bash
unzip -o ~/Downloads/VisionGuard_AI_SAM_Streaming_Preview_Full_Codebase_2026-11-01.zip -d .
```

The ZIPs do not contain `.env`, `.git`, `var/`, `.next`, `node_modules`, local videos, `yarn.lock` or `package-lock.json`. They do not remove any of your files.

## 3. Install FFprobe

**Required to prevent billable inference with missing FPS.** On macOS, install FFmpeg (includes ffprobe), e.g. `brew install ffmpeg` with Homebrew or `sudo port install ffmpeg` with MacPorts. Confirm:

```bash
command -v ffprobe
ffprobe -version
```

If installation isn't working, the backend now returns HTTP 503 with an actionable message **before any Meta API call**.

## 4. Prepare an eligible video

Use the included utility to prepare the same clip that the browser and SAM will consume:

```bash
python -m backend.scripts.prepare_demo_clips \
  --input samples/warehouse_1.mp4 \
  --output samples/warehouse_fast.mp4 \
  --seconds 5 --height 480 --fps 12
```

Upload **warehouse_fast.mp4** through the UI; do not instead analyze the original 12-second video. This step is optional for already-small videos but recommended for first integration testing.

## 5. Run back end (without auto-reload)

```bash
source .venv/bin/activate
python -m pytest backend/tests -q
SAM_DEMO_CONCEPTS=person python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 2>&1 | tee /tmp/visionguard-sam.log
```

The *single-concept* setting is for cost-controlled testing. For the full people + forklifts demo, stop the server and restart **without** `SAM_DEMO_CONCEPTS=person`. Never modify server code during live inference.

## 6. Front end

From `frontend/` after stopping any old frontend dev process:

```bash
yarn install --network-timeout 300000
yarn typecheck
yarn dev --webpack
```

No frontend dependencies were added by this change. If you use npm instead, use `npm install`/`npm run dev -- --webpack`. Do not use npm and Yarn at the same time.

## 7. Inspect job progress

```bash
JOB_ID=PASTE_UUID_FROM_BROWSER
curl -sS "http://127.0.0.1:8000/api/v1/tracking-jobs/$JOB_ID" | python -m json.tool
curl -sS "http://127.0.0.1:8000/api/v1/tracking-jobs/$JOB_ID/preview" | python -m json.tool
```

When a job reaches `completed`, the regular `/result` endpoint contains its final report and unlocks the rule/evidence panels. A failed job can retain a **provisional** `/preview`, but this cannot be used for safety conclusions. Inspect `/tmp/visionguard-sam.log` for the real traceback. Don't disclose API keys or private video contents from logs.

For the previously failed job `ac8deabb-99e7-43bf-a02d-f0abde812413`, check if `var/tracking/<id>/raw/person/summary.json` already exists, but it cannot be retroactively converted into a streaming preview if it wasn't saved during the old run.

## Validation performed here

- 69 backend offline tests passed.
- Python compileall passed.
- TypeScript/TSX syntax parsing passed for changed frontend files.
- Full Next.js build not run (registry network unavailable in test environment).
- Live Meta SAM 3.1 API run not possible without user credentials and an authorized clip. **The remote streaming failure is not claimed fixed.**
