# VisionGuard AI

**Turn short workplace video into explainable observations, configurable rule matches, and human-reviewable evidence.**

[![Meta SAM 3.1](https://img.shields.io/badge/Visual%20tracking-Meta%20SAM%203.1-38cdb2)](https://dev.meta.ai/docs/cookbook/sam-api-basics)
[![Muse Spark](https://img.shields.io/badge/Rule%20drafting-Muse%20Spark-7cb9e8)](https://dev.meta.ai/docs/cookbook/quickstart-chat-completions)
![Status](https://img.shields.io/badge/Status-research%20MVP-f1ba75)
![License](https://img.shields.io/badge/License-MIT-9eafbc)

**Meta Global AI Developer Hackathon 2026 · Indie track**

> **Project status — November 2, 2026:** The local application has successfully completed a hosted SAM 3.1 analysis of a short warehouse clip, with **person and forklift** bounding boxes displayed over video playback. This demonstrates a working integration on one test clip, **not** calibrated detection accuracy or reliability across videos. Deterministic rules, evidence review, and synthetic replay are implemented; further live end-to-end scenario validation remains in progress.

## VisionGuard AI, powered by SceneOps

![VisionGuard AI / SceneOps architecture](docs/assets/visionguard-sceneops-architecture.png)

**VisionGuard AI** is the safety-review application: ingest footage, inspect tracked observations, define monitored zones, evaluate rules, and review evidence. **SceneOps** is the name for the reusable **video-to-rule architecture inside the current application**—not a separate shipped library, model, or product.

The long-term direction is to reuse SceneOps for parking, retail, and construction workflows. **Those industry modules and generic object concepts are planned, not implemented in the current MVP.**

### What works today

| Capability | Current scope |
| --- | --- |
| Video ingest & playback | Local MP4/MOV/WebM uploads, a selectable **Recent Uploads** list, browser playback, and camera capture where supported. WebM must be converted before SAM inference. |
| Hosted visual tracking | Explicit, billable Meta SAM 3.1 requests for **`person`** and **`forklift`**; progressive **provisional** box previews; final normalized tracks and gaps. |
| Zone-based evaluation | Reviewer-defined rectangle; `person_in_zone` and `person_and_forklift_in_zone` rules; observed-duration thresholds. Runs locally **without** a model call. |
| Muse Spark | Optional, billable natural-language drafting of a *supported* rule; human approval is required. Unsupported requests remain unsupported. |
| Uncertainty | Missing frames, approximate timing, and unverified track continuity are surfaced as review candidates rather than invented observations. |
| Evidence & review | Local evidence snapshots, source hashes, sampled boxes, reviewer decisions, and JSON / printable HTML exports. |
| Synthetic replay | Offline fixtures for co-presence, occlusion review, and clear aisle; distinctly labeled **synthetic**, not real video or actual SAM output. |

**Not implemented:** continuous live-camera inference, collision prediction, calibrated distance/speed estimates, certified danger detection, generalized SceneOps concepts, a pre-seeded multi-industry video gallery, or production authentication. Uploads currently appear automatically in **Recent Uploads**; a unified curated demo gallery is a **planned UI enhancement**.

## How it works

```text
Authorized MP4/MOV upload ──► Local video store + SHA-256
          │
          └──► Explicit "Analyze with SAM" (billable)
                        │
                  Meta SAM 3.1
             person + forklift requests
                        │
          Provisional streamed box previews
                        │
              Final tracking report
           boxes • track fragments • gaps
                        │
             Reviewer-defined floor zone
                   + temporal rule
                        │
          Deterministic, local evaluation
                        │
         ┌──────────────┴───────────────┐
  Observed potential match       Needs human review
         └──────────────┬───────────────┘
                        │
             Evidence snapshot +
          reviewer decisions + export
```

**Detection is not a safety verdict.** A person and forklift observed in the same drawn zone meet an image-space rule condition; this does not establish physical proximity, an imminent collision, or whether the detected person is the seated operator. Missing observations are not filled in or assumed safe. Timestamps are approximate (`frame / FPS`).

## Quick start

### Requirements

- Python **3.11+**, Node.js **20.9+**, Yarn Classic or npm, and Git.
- **FFmpeg and FFprobe** available on your `PATH` for billable video preflight and demo-clip preparation.
- A Meta Models API key (`MODEL_API_KEY`) for optional live SAM/Muse requests. **Offline tests and synthetic replay do not require one.**
- Authorized, appropriately licensed footage; no confidential or unconsented recordings.

**1. Set up the backend** (from the repository root):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally if you intend to use Meta:

```dotenv
MODEL_API_KEY=YOUR_META_MODEL_API_KEY
SAM_CONCURRENT_CONCEPTS=0
```

On a Mac using **MacPorts**, ensure FFprobe is visible (the package installer must be installed separately first):

```bash
export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
command -v ffprobe
ffprobe -version
```

Install FFmpeg/FFprobe using your operating system's package manager if missing. The preflight **blocks billable tracking** without readable FPS and dimensions.

**2. Start FastAPI** (terminal 1, repository root):

```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

**Do not use `--reload` during a billable SAM job.** Reloading can terminate the local worker mid-stream. For a cost-controlled single-concept test, start with `SAM_DEMO_CONCEPTS=person` in front of the command. By default the backend analyzes **both** concepts sequentially; `SAM_CONCURRENT_CONCEPTS=1` enables optional parallel requests after basic integration succeeds.

Check [Swagger API docs](http://127.0.0.1:8000/docs) or:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/meta/status
```

The Meta status route checks for a configured key; it does **not** prove account permissions, remaining credits, or model availability.

**3. Start Next.js** (terminal 2):

```bash
cd frontend
yarn install --frozen-lockfile
yarn dev --webpack
```

Open **http://localhost:3000**. The app uses a same-origin Next.js rewrite to proxy backend requests; keep API keys on the server, never in `NEXT_PUBLIC_*` variables.

### Prepare a fast, reproducible clip

SAM demo preflight currently requires: **MP4/MOV**, a supported video codec, **≤25 MiB**, **≤30 seconds**, and **≤1080p / 30 FPS**. The regular upload endpoint allows files up to **100 MiB** but has a *separate* inference limit.

```bash
# Provide your own licensed source video first.
python -m backend.scripts.prepare_demo_clips \
  --input samples/warehouse_source.mp4 \
  --output samples/warehouse_demo_480p.mp4 \
  --seconds 5 --height 480 --fps 12
```

**Upload the converted clip to the UI.** The video played in the browser must be the **same file** sent to SAM; converting only the model input would misalign bounding boxes.

### First end-to-end local demo

1. Upload and select the prepared video in **Recent Uploads**.
2. Click **Analyze with SAM (billable)** once. The interface shows phases and may display **provisional** observations before completion.
3. After **COMPLETED**, inspect boxes, track fragments, and missing-frame gaps. A completed request with **zero detections** is a valid possible result.
4. In **Safety Intelligence**, choose/draw a zone and evaluate a supported rule. Rule evaluation is **offline and does not consume Meta credits**.
5. Inspect observed potential matches and separate review items; click an event to seek to its approximate time.
6. Save an evidence snapshot, record **confirmed / rejected / unresolved** human decisions, and export JSON or HTML.

**Do not present an observed rule match as a confirmed accident.** The shared-zone rule can also match an operator in the forklift; review the actual frames before interpreting a result.

## Demonstrations

| Demo | Data source | What it demonstrates |
| --- | --- | --- |
| Warehouse person + forklift | **Real local video**, after user-authorized SAM processing | Hosted tracking, boxes, zone-based rule evaluation, and evidence workflow. |
| Warehouse co-presence | **Synthetic replay fixture** | Positive observed-rule-match path without API costs. |
| Occlusion review | **Synthetic replay fixture** | Observation gaps and unverified continuity routed for review. |
| Clear aisle | **Synthetic replay fixture** | Negative control: no invented match when conditions are not observed. |
| Parking / retail / construction | **Future SceneOps extensions** | New object concepts, rules, data, and validation are required; **not live demos yet**. |

Use **http://localhost:3000/replay** for the labeled synthetic demonstrations. They use hand-authored coordinates, not recorded footage or actual SAM output. Only real, completed model results should be described as live SAM detections.

## Architecture and repository layout

- **Frontend:** Next.js 16, React 19, TypeScript; upload, browser playback, overlays, rule controls, and evidence review.
- **Backend:** FastAPI; local file-backed video store, job records, streaming previews, constrained model integration, deterministic evaluation, and evidence exports.
- **Model boundary:** SAM provides observations; Muse proposes a draft; **neither model is allowed to produce a final safety certification**. The deterministic rule evaluator operates on observed tracking data only.

```text
visionguard-ai/
├── backend/
│   ├── app/
│   │   ├── api/                  # video, tracking, safety, evidence, replay routes
│   │   └── services/
│   │       ├── sam.py             # hosted SAM stream parsing
│   │       ├── tracking_jobs.py   # local background jobs + previews
│   │       ├── tracking_report.py # boxes / fragments / gaps
│   │       ├── safety_engine.py   # deterministic temporal rules
│   │       ├── evidence_store.py  # local evidence and audit history
│   │       └── replay_fixtures.py # synthetic scenario loader
│   ├── scripts/                  # smoke tests and video preparation
│   └── tests/                    # offline test suite
├── frontend/                     # Next.js app (Yarn lockfile)
├── benchmarks/replay/            # labeled synthetic fixtures
├── docs/                         # implementation and architecture notes
│   └── assets/                   # README architecture illustration
├── .github/workflows/            # backend / frontend CI
├── var/                          # local uploads/jobs/evidence (gitignored)
├── samples/                      # user-provided footage (gitignored)
├── outputs/                      # generated model artifacts (gitignored)
└── .env.example
```

Further technical notes: [tracking pipeline](docs/architecture/object-tracking-pipeline.md), [temporal evaluation](docs/architecture/temporal-evaluation-v2.md), [rule engine](docs/architecture/safety-rule-engine.md), [evidence and replay](docs/architecture/evidence-review-and-replay.md), and [performance / multi-video testing](docs/13-performance-and-multi-video-testing.md).

## API overview

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Backend health |
| `GET /api/v1/meta/status` | Local Meta key-presence check only |
| `POST /api/v1/videos` | Store an uploaded video |
| `GET /api/v1/videos` | List recent uploads |
| `POST /api/v1/videos/{id}/tracking-jobs` | **Explicitly billable** SAM analysis |
| `GET /api/v1/tracking-jobs/{id}` | Job state, phase and safe diagnostics |
| `GET /api/v1/tracking-jobs/{id}/preview` | Provisional, read-only observations (may be 404 until ready) |
| `GET /api/v1/tracking-jobs/{id}/result` | Completed normalized tracking report |
| `POST /api/v1/rules/interpret` | Optional **billable** Muse rule draft |
| `POST /api/v1/tracking-jobs/{id}/evaluate` | Offline deterministic safety evaluation |
| `/api/v1/evidence-reports` | Local evidence snapshots, reviews and exports |
| `/api/v1/replay/scenarios` | Read-only synthetic benchmarks |

All endpoints that store data or trigger Meta inference are intended for **trusted local use**, not an unprotected public deployment.

## Testing and reproducibility

```bash
# Offline backend tests; do not spend model credits
python -m pytest backend/tests -q

# Local rule fixture check
python -m backend.scripts.evaluate_fixture

# Frontend checks
cd frontend
yarn typecheck
yarn build
```

The GitHub Actions workflows run backend tests and frontend typecheck/build. These checks **do not** establish live SAM accuracy, model availability, or safe behavior in a real workplace.

Optional real Meta checks are **billable** and should use short licensed inputs:

```bash
python -m backend.scripts.meta_smoke muse
python -m backend.scripts.meta_smoke sam \
  --video samples/warehouse_demo_480p.mp4 \
  --concept person --concept forklift \
  --output outputs/live-check
```

Single-process background jobs can be interrupted by server restarts and are **not** a durable queue. Mask SVG generation is optional; the normal pipeline avoids expensive full-mask conversion. Progressive preview revisions are **not percentages**.

## Safety, privacy, and deployment

- **Research prototype only:** not certified safety monitoring, emergency response, workplace compliance verification, or continuous real-time surveillance.
- Keep `.env`, user footage, raw model outputs, local jobs, and reviewer notes out of Git. Verify clip rights and authorization before sending footage to a third-party model API.
- Local API routes have **no authentication, tenant isolation, or production abuse controls**. Do not publicly expose upload, billable inference, or persistent review endpoints.
- For an intentionally **public read-only synthetic replay**, start FastAPI with `VISIONGUARD_REPLAY_ONLY=1` and build the frontend with `NEXT_PUBLIC_REPLAY_ONLY=1`. Those flags disable the local upload/paid/review-write routes; verify your deployment configuration independently.
- Local evidence records preserve source hashes, rule parameters, sampled observations, and appended human decisions. They are **not** independently verified model outputs or tamper-proof audit records.
- Evaluate positive examples, negative controls, occlusion, model failures, and false positives before making performance claims.

## Hackathon disclosure

This repository includes work from different development stages. **Do not represent pre-event code or third-party assets as originally created during the official hackathon building window.** Identify and demonstrate the work actually performed for the event, disclose reused components where required, and verify the organizer's current submission rules. This project is intended for a short, accurate demo of its actual capabilities.

- [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)
- [Meta SAM API basics](https://dev.meta.ai/docs/cookbook/sam-api-basics)
- [Meta Muse Spark quickstart](https://dev.meta.ai/docs/cookbook/quickstart-chat-completions)

## License

MIT applies to original repository code only. Meta models, third-party dependencies, video footage, and external media are governed by their respective terms. See [LICENSE](LICENSE).
