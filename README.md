# VisionGuard AI

**Explainable visual safety intelligence powered by Meta SAM 3.1 + Muse Spark**

**Meta Global AI Developer Hackathon 2026** · Indie Developer · Push the Frontier

> **Current stage: Video ingestion, SAM object tracking, and deterministic reviewer-configured safety rules.** FastAPI upload/list/playback and a mobile-first Next.js frontend are included. This prototype reports potential rule matches, **not** certified danger, real-time monitoring, or safety compliance. Live remote Meta calls were not executed during package generation.

VisionGuard aims to help safety reviewers analyze short, authorized workplace videos. The proposed workflow is: detect/track people and vehicles using SAM 3.1; interpret reviewer-specified monitoring rules with Muse Spark; evaluate temporal events deterministically; show evidence with timestamped, human-reviewable incident reports. It **must not** be used as a replacement for trained safety professionals or real-time emergency protection.

## Hackathon compliance (read first)

- The participant guide lists **Oct 27–Nov 4, 2026** as the building period. This reference starter was generated **Oct 26, 2026**, before that period. **Do not claim earlier code was created during the event.** Confirm permitted usage with organizers, develop and document your actual original hackathon contributions within the permitted period, and disclose any reused material.
- Official submission requires a **public** repository and a **3-minute demo video** showing specific work built during the hackathon.
- Use only videos, assets and datasets you have the rights to use; follow applicable privacy and safety laws.
- Your application originally mentioned a different idea: confirm with Cerebral Valley that switching final submissions is allowed.
- References: [participant event](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), [SAM API basics](https://dev.meta.ai/docs/cookbook/sam-api-basics), [Muse chat quickstart](https://dev.meta.ai/docs/cookbook/quickstart-chat-completions).

## Scope by stage

| Period | Planned milestone | Implementation status |
|---|---|---|
| Day 1 | Model account, Muse ping, SAM video tracking outputs | **Starter code included; real API validation pending** |
| Day 2 | Upload API, Next.js interface, video playback | **Implemented in `feature/video-ingestion`; validate locally** |
| Days 3–4 | SAM tracks, fragment uncertainty + approximate box overlays | **Implemented in `feature/object-tracking`; live verification pending** |
| Days 5–6 | Muse rule translation + deterministic event logic | **Implemented in `feature/safety-rule-engine`; live validation pending** |
| Days 7–8 | Evidence dashboard and incident timeline | Planned |
| Days 9–10 | Benchmark, demo, submission | Planned (compress to fit official dates) |

Full stage details live in [`docs/`](docs/).

## Prerequisites

- Python 3.11+ recommended; Git; a terminal; internet for remote API calls
- Meta Model API account and `MODEL_API_KEY` for live tests (required only for the `muse` and `sam` commands)
- Short, properly licensed H.264 MP4 or MOV clip to test the video workflow
- **No camera, local CUDA GPU, or special device is necessary** when using the hosted Meta API
- The Day 1 `sam` test uploads video to Meta. Do not use confidential or unconsented video

## Quick start — macOS/Linux

From your repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally and set your real key:

```dotenv
MODEL_API_KEY=YOUR_REAL_KEY_HERE
```

> `.env` is gitignored. Never commit an API key, user video, logs containing sensitive data, or raw model output with private content. Setting a billing **notification** is not necessarily a hard spending cap.

### Start FastAPI (offline, no API credits)

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs, or test in another terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/meta/status
```

The `/api/v1/meta/status` response checks **whether a key is present**, not whether credentials, account access, or quota are valid.

### Check Meta account with Muse Spark (LIVE, billable)

```bash
python -m backend.scripts.meta_smoke status  # offline key presence check
python -m backend.scripts.meta_smoke muse    # LIVE API request, confirms usable credentials
```

Expected Muse response is typically `ready`. Wording is not a guaranteed exact assertion. Missing key, 401/403, quota, payment or rate-limit errors will be shown in the terminal.

### Upload and track a short clip with SAM 3.1 (LIVE, billable)

1. Put a **licensed/consented** short clip at `samples/warehouse.mp4` (the `samples/` directory is ignored by Git).
2. Run one noun phrase per model request:

```bash
python -m backend.scripts.meta_smoke sam \
  --video samples/warehouse.mp4 \
  --concept person \
  --concept forklift \
  --output outputs/day1
```

SAM 3.1 receives **two separate** segmentation prompts, one for `person` and one for `forklift`, and the uploaded video file is reused. Testing with an unrelated short video first is okay; choose the noun actually present.

For a previously uploaded video (copy the `file-...` identifier printed by the first run):

```bash
python -m backend.scripts.meta_smoke sam \
  --file-id file-YOUR-UPLOAD-ID \
  --concept person \
  --output outputs/retry
```

Results are written under `outputs/day1/person/` and `outputs/day1/forklift/`, including:

```text
summary.json        # real parsed bounding boxes, masks and track extents
mask-0000.svg       # decoded inspectable segmentation-mask paths
mask-0001.svg
...
```

Open `summary.json` in a code editor. A completed request with zero matches is **valid**, not proof that the model failed. Inspect `tracks`, `visible_frames`, `box_count` and `mask_count`, and compare with the actual clip. Track IDs from independent concept requests are **not** automatically globally unique; normalize them when combining on Days 3–4.

**Note:** Day 1 limits input file size to 25 MiB as a local cost/speed guard, *not* an official Meta API limit. Use short H.264 video clips. The `meta_sam_parser` package decodes the protocol—do not treat raw output text as ordinary JSON.

### Run automated tests (offline)

```bash
python -m pytest backend/tests -q
```

The automated suite checks the ingestion and tracking endpoints, key secrecy, CLI status, result normalization, missing-frame gaps, and mocked job execution. These tests **do not call Meta** and do not demonstrate SAM's real-world tracking accuracy.

## Repository map

```text
visionguard-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI liveness/config endpoints
│   │   ├── config.py               # model IDs and local .env loading
│   │   └── services/
│   │       ├── muse.py             # live Muse Spark ping
│   │       └── sam.py              # SAM upload, parse, track summary, SVG output
│   ├── scripts/meta_smoke.py       # CLI
│   └── tests/test_day1.py         # offline unit tests
├── frontend/                       # Next.js mobile-first upload/camera/playback app
├── docs/                           # stage by stage plan and acceptance gates
├── benchmarks/                     # annotation example (no actual licensed clips)
├── var/                            # ignored local uploads, created at runtime
├── samples/                        # ignored local video inputs
├── outputs/                        # ignored generated segmentation artifacts
├── examples/                       # data rights notes
├── .github/workflows/              # offline GitHub Actions unit tests
├── requirements.txt
├── .env.example
└── LICENSE
```

## Important architecture choices

- Video upload/list/playback endpoints are now included for **local prototype use only**. They are NOT production-safe without authentication and abuse prevention.
- SAM returns masks and track geometry, not a guarantee of safety compliance, physical distance, or collision prediction.
- The proposed event engine will use deterministic rules over normalized tracks, with **reviewer-configured** operating zones and explicit uncertainty.
- Muse Spark can interpret instructions and help configure a rule but should not override deterministic checks or certify safety conclusions.
- Preserve provenance: source clip hash, model ID, request timestamp, frame/time indices, rule version, reviewer decision (planned in later stages).

## Deployment recommendation

**Current feature:** run locally. **Day 7 or 8:** deploy an API/demo to Render if the application is stable and protected by authentication. **Neon PostgreSQL:** add only after incident persistence is needed (e.g. days 7–8). A SQL database is not video storage; use separate object storage for uploads. Render free instances may sleep and have ephemeral disk; see [`docs/07-deployment.md`](docs/07-deployment.md). For the final judged demo, consider a paid stable service or a local demo plus recording as a reliability fallback.

## Data protection and evaluation

Research/demo only. Do not make safety-critical decisions based on detections. Keep sample footage private and consented. The project will need an evaluation set including hazard events, non-events, occlusions, false positives, and ambiguous situations before making meaningful performance claims.

## License

MIT for *this project's original source* only. Third-party dependencies, Meta models, video footage and external examples retain their own separate licenses/terms. See official documentation before incorporating any example assets.


## Milestone 3 - SAM object tracking (new)

After uploading an authorized **MP4/MOV** clip (H.264 preferred, <=30 seconds for this demo), select it in the player and click **Analyze with SAM (billable)**. The backend uses your local `MODEL_API_KEY` and makes two SAM 3.1 requests (`person` and `forklift`). The UI polls for results and shows box overlays and observed track fragments.

New tracking endpoints:

- `POST /api/v1/videos/{video_id}/tracking-jobs` - explicitly start billable local job (202).
- `GET /api/v1/videos/{video_id}/tracking-jobs` - recent job statuses.
- `GET /api/v1/tracking-jobs/{job_id}` - status and error-safe message.
- `GET /api/v1/tracking-jobs/{job_id}/result` - normalized boxes, track fragments and gaps.

The jobs run in a **single FastAPI process only** and are not durable across restarts. Both videos and results are stored privately under ignored `var/`. Output from Meta can be empty; that is a valid case. A missing observation breaks verified track continuity; we do not reidentify people from guesswork. Browser overlay timing is an **approximation**, not frame-accurate evidence or live monitoring.

Read [object-tracking architecture](docs/architecture/object-tracking-pipeline.md), [milestone 3](docs/milestones/03-object-tracking.md), [occlusion policy](docs/features/tracking-identity-uncertainty.md), and [player caveats](docs/features/video-overlay.md).

**Run locally:**

```bash
# Terminal 1 (repository root)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env  # Set MODEL_API_KEY locally for paid inference
python -m pytest backend/tests -q
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

Open `http://localhost:3000`, upload a video, select it, and click Analyze. **Do not deploy these unauthenticated endpoints on a public host.** Automated tests are offline; real Meta SAM inference, playback alignment, privacy/retention and safety accuracy must be validated separately.


## Milestone 4 — Reviewer-configured safety rules

After a SAM tracking job completes, the viewer exposes a **Safety Intelligence** panel. Choose a rectangle (normalized coordinates), one of two supported rule types, and a required number of consecutive observed frames. **Evaluate tracked frames** makes a local deterministic API call with no model charges. The result returns potential rule matches, frame indices, approximate seek times, and tracking-gap uncertainty; it does **not** certify danger.

Optionally describe your rule and click **Interpret with Muse (billable)**. Muse Spark 1.3 proposes a constrained JSON rule draft. Inspect it and click **Approve and apply draft**; you must still set the zone. Only explicit Muse and SAM calls use Meta credits.

```bash
python -m pytest backend/tests -q
python -m backend.scripts.evaluate_fixture
```

API endpoints:
- `POST /api/v1/rules/interpret` — optional billable Muse draft (manual approval required).
- `POST /api/v1/tracking-jobs/{job_id}/evaluate` — offline deterministic rule evaluation against completed SAM report.

Documentation: [architecture](docs/architecture/safety-rule-engine.md), [Muse drafting](docs/features/muse-safety-rule-drafting.md), [event semantics](docs/features/deterministic-hazard-events.md), [milestone](docs/milestones/04-safety-rule-engine.md).

**Not yet validated:** live Muse/SAM compatibility, actual danger detection performance, frame-accurate timing, public deployment safety. The local API is not authenticated and must not be deployed publicly as-is.
