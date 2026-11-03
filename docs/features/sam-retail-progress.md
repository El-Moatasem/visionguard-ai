# Fixed v2 — corrects JSX anchor matching

The previous `apply.py` incorrectly assumed **seven** spaces before the Retail tracking selector and saved-job paragraph; the repository uses **six**. Version 2 accepts indentation-only differences while still verifying that every source block is unique before writing. If the source actually differs, the installer stops without changing any files.

# VisionGuard AI — SAM Retail & Progress Improvements

**Scope:** self-contained patch for a local VisionGuard checkout compatible with the Nov 3 public `main` (`96dd4552`) and indentation-only variations in newer checkouts. No database changes, no migrations, no deployment, and no paid API calls during installation.

## Fixes

- New **Retail: people + carts** tracking preset (two Meta concept requests). Retains the three-concept Retail people+carts+boxes preset and the lower-cost carts+boxes-only preset.
- When opening an existing job, the UI restores **that job's actual requested concepts** instead of misleadingly showing the warehouse default.
- While the analysis is running, the disabled dropdown shows the **immutable concepts of that running job**. After completion, the dropdown can be changed for a *new* billable run.
- Honest, per-concept progress: uploading, tracking the latest concept, number of completed concepts, and final report creation. The progress bar counts **completed concepts**, not processed frames or a percentage of completion time.
- API job status now includes `current_concept`, `upload_seconds`, and `last_concept_inference_seconds` diagnostics.
- Streaming snapshots are serialized to preview JSON no more often than the configured interval (4 seconds default). This reduces repeated work on large full snapshots; it **does not speed up Meta's inference service** and retains full final SAM results.
- Existing concept concurrency remains opt-in; not enabled by this patch.

## Apply on your Mac

From your existing repo root (activate `.venv` first):

```bash
git status --short
# Commit or stash unrelated changes before branching.
git switch -c fix/sam-retail-progress-performance
unzip -o ~/Downloads/VisionGuard_SAM_Retail_Progress_Fixes.zip -d ~/Downloads
python3 ~/Downloads/VisionGuard_SAM_Retail_Progress_Fixes/apply.py --repo .
python3 ~/Downloads/VisionGuard_SAM_Retail_Progress_Fixes/apply.py --repo . --apply
```

The first invocation is a **dry run**, and the installer aborts without writing anything if the expected code anchors are absent. Modified files are backed up in a timestamped sibling folder before writing. Reapplying is safe. The installer does not touch `.env`, PostgreSQL, logos, uploads, completed jobs, or GitHub.

## Environment settings

```dotenv
SAM_PREVIEW_INTERVAL_SECONDS=4
SAM_CONCURRENT_CONCEPTS=0
SAM_MAX_ACTIVE_JOBS=2
```

- Keep `SAM_CONCURRENT_CONCEPTS=0` until sequential jobs are stable. Turning it on may shorten wall time but increases parallel billable Meta streams and streaming failure risk.
- `SAM_PREVIEW_INTERVAL_SECONDS` accepts numbers from **1 to 15**; `4` is the default. Higher values reduce local preview I/O, **not inference cost**. Long intervals make previews appear less often.
- `SAM_MAX_ACTIVE_JOBS=2` requires your separate multi-video jobs patch, which exists in your newer branch. The present patch does not change that limit.
- SAM requests remain separately billable for every concept. Do not mistake a shorter preview interval for lower Meta charges.

## Offline validation

```bash
python -m pytest backend/tests/test_sam_preview_interval.py backend/tests/test_sam_concurrency.py -q
python -m pytest backend/tests -q
cd frontend
corepack enable
yarn install --frozen-lockfile
yarn typecheck
yarn build
```

Restart **both FastAPI and Next.js** after patching. Test one 8–15-second H.264 / 480p / 12 FPS retail clip using **Retail: people + carts**; inspect the progress stage and wait for final status before evaluating rules.

## Important boundaries

- The UI can show live provisional people boxes **before completion**, but final safety evaluation requires a complete job.
- This does **not** automatically retry streams that fail; automatic retries could add Meta charges. Examine FastAPI traceback for failures.
- A per-concept progress bar should not be read as exact timing, nor as proof every expected object was detected.
- Model inference latency, API availability, network upload, and occasional `ResponsesStreamSourceError` are separate from preview rendering.

## Git / PR

Stage only the changed files and new test/documentation. The installer does not run Git commands.

```bash
git add backend/app/services/sam.py backend/app/services/tracking_jobs.py \
  backend/tests/test_sam_preview_interval.py frontend/src/components/TrackingViewer.tsx \
  frontend/src/lib/api.ts frontend/src/app/globals.css \
  docs/features/sam-retail-progress.md
git commit -m "fix(sam): clarify retail jobs and throttle preview updates"
```
