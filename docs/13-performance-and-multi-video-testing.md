# Performance, reliability and multiple-video testing

This is a local research prototype, not a real-time surveillance or certified safety system. Inference is remote and billable, so **neither zero latency nor guaranteed completion is possible**. Public replay is separate, synthetic, and never claims to have made live model calls.

## What changed

- **Responsive API**: a synchronous Starlette BackgroundTasks entrypoint executes the SAM async client on a worker thread. Heavy parser work and file I/O no longer monopolize FastAPI's main event loop. This is still *not* a durable queue. A process restart can interrupt a job.
- **Compact SAM stream**: requests `metadata={"mask_encoding":"one_bit"}` (documented by Meta). This reduces payload size but not necessarily hosted inference duration.
- **No expensive mask work by default**: raster pixel counting disabled; SVG export opt-in; exactly one summary per concept; per-concept JSON saved after each completed response. App overlays and the safety engine use bounding boxes.
- **Conservative concurrency**: person/forklift requests are sequential by default; `SAM_CONCURRENT_CONCEPTS=1` enables concurrent calls as an optional experiment. Beware increased memory, rate limits and spending.
- **Responsive browser viewer**: boxes indexed by frame, video-frame timing used where available; no box interpolation across unobserved frames. Polling errors clear after a successful status response.
- **Size boundary**: up to 100 MiB for *local upload/storage*, up to 25 MiB for *SAM analysis*. Oversized analysis requests fail before credit spend. Public hosting with anonymous paid inference is unsafe.
- **Never start Uvicorn with `--reload` during live model analysis**. Editing source while active can abort the request.

## Install and run (local only)

```bash
# From repository root, in virtual environment using Python 3.11+
python -m pip install -r requirements.txt
cp -n .env.example .env
# Fill MODEL_API_KEY in .env (never commit it)
python -m pytest backend/tests -q
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Second terminal
cd frontend
npm install    # or npm ci if you already have your package-lock.json
npm run typecheck
npm run build
npm run dev
```

Open http://localhost:3000 ; http://localhost:3000/replay is a synthetic offline replay. Do not publicly deploy the live upload/paid inference API without authentication, quotas and durable storage.

## Prepare an analysis clip (FFmpeg and FFprobe required)

For predictable video coordinates, **preprocess the clip before uploading it**, and use the resulting same file for both browser playback and Meta inference. Do not secretly feed a resized clip to SAM while playing the original: their box coordinates, FPS and frame indices differ.

```bash
python -m backend.scripts.prepare_demo_clips \
  --input samples/warehouse_1.mp4 \
  --output samples/warehouse_fast.mp4 \
  --seconds 5 --height 480 --fps 12
```

Verify the clip has clearly visible person/forklift objects and has authorized reuse rights. Compression trades resolution for speed; benchmark tracking quality, not just latency.

## Many-video tests: safe preflight by default

```bash
# FREE. Inspect up to 10 clips; NO remote model calls.
python -m backend.scripts.batch_test_videos --directory samples

# LIVE / BILLABLE. Up to 3 clips sequentially. Two concepts per clip.
python -m backend.scripts.batch_test_videos \
  --directory samples --max-videos 3 --live

# Optional single concept (fewer paid calls):
python -m backend.scripts.batch_test_videos \
  --directory samples --max-videos 3 --concept person --live

# Only if intentionally repeating billable inference for completed clips:
python -m backend.scripts.batch_test_videos \
  --directory samples --max-videos 3 --live --force
```

Results under `outputs/batch/`: one subfolder per video with `person/summary.json`, `forklift/summary.json` if successful, and `manifest.json` + `manifest.csv`. Completed concept files are skipped on subsequent runs unless `--force` is provided. Saved JSON does not prove frame alignment. These outputs are gitignored and should remain local if they contain private footage-derived information.

## Debug performance and model errors

```bash
# Real Meta API connectivity and SAM (LIVE, billable)
python -m backend.scripts.meta_smoke status
python -m backend.scripts.meta_smoke muse
python -m backend.scripts.meta_smoke sam \
  --video samples/warehouse_fast.mp4 --concept person \
  --output outputs/first-success

# Inspect frame stride (offline):
python -m backend.scripts.inspect_sam_frames \
  outputs/first-success/person/summary.json

# Optional investigation: output masks; can be VERY slow / large.
python -m backend.scripts.meta_smoke sam \
  --video samples/warehouse_fast.mp4 --concept person \
  --output outputs/debug --write-masks
```

`sam.py` logs `upload_seconds`, `inference_seconds` and `postprocess_seconds` for each successful concept to help identify remaining delays. A `ResponsesStreamSourceError` **during streaming** is not a mask-conversion problem. A dropped Next.js proxy during Uvicorn reload is not automatically a Meta error. Always inspect the backend trace and job record; avoid automatically retrying a billable stream.

For a failed job, `/api/v1/tracking-jobs/<id>` reports a generic message intentionally; detailed diagnostic errors stay in server logs. Temporary proxy 500s can appear if the backend is unavailable. Failing or interrupted requests must not be represented as completed inference.

**Important:** Before using the seconds-based safety engine, FFprobe or validated SAM metadata must provide FPS and dimensions. If absent, don't invent timestamps or claim frame-accurate events. Also verify whether observed frame skips are model sampling stride versus actual occlusion; do not fill missing observations.

## Benchmark expectations

Evaluate three or more distinct authorized clips: one co-presence event, one clear-aisle negative, and one with ambiguous/occluded observations. Record video duration, FPS, resolution, model completion, boxes/tracks, frame-step counts, true/false positives by manual review, actual latency for each stage, and limitations. Synthetic replay demonstrates rules, **not SAM tracking accuracy**.

Meta references:
- https://dev.meta.ai/docs/sam/segmenting
- https://dev.meta.ai/docs/sam/client-libraries
