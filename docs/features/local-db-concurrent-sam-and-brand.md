# VisionGuard AI — Local PostgreSQL + Two SAM Jobs + Brand Icon

## Safety and scope

This local patch **does not** execute any Meta requests, create databases, commit Git changes, or push to GitHub. New database persistence is optional and **off by default**. Binary videos and SAM raw preview files remain on local disk. The two-job limit applies only within a **single FastAPI process**; it is not a durable queue and provides no cross-instance coordination or crash recovery.

## Create separate local branch

```bash
git status --short
git switch -c feature/local-postgres-multi-sam-brand
python3 ~/Downloads/VisionGuard_LocalDB_MultiSAM_Logo/apply.py --repo .
python3 ~/Downloads/VisionGuard_LocalDB_MultiSAM_Logo/apply.py --repo . --apply --build-full-zip
```

The script preflights all text modifications before writing, creates a timestamped backup folder outside the repository, and refuses to overwrite locally customized database source files. It can be re-run. No tracked user file is deleted. If the current branch already has PostgreSQL patches from an earlier ZIP, the script reuses them.

Review modifications before committing:

```bash
git diff --stat
git diff -- backend/app/services/tracking_jobs.py frontend/src/app/globals.css
```

## Install Python dependencies

```bash
python3 -m pip install -r requirements.txt
```

## Local PostgreSQL (MacPorts, Homebrew, Docker, or existing PostgreSQL service)

Start PostgreSQL using your installation's normal service manager, then create a dedicated empty database:

```bash
createdb visionguard_local
```

Put connection settings in a private environment file **not committed to Git**. Example for a local PostgreSQL server:

```dotenv
VISIONGUARD_USE_DATABASE=1
DATABASE_URL=postgresql://localhost:5432/visionguard_local
SAM_MAX_ACTIVE_JOBS=2
SAM_CONCURRENT_CONCEPTS=0
```

If your PostgreSQL server requires a username and password, use the appropriate PostgreSQL URL with credentials; do not paste passwords in chat. **Do not assume the app loads `.env` automatically**: export variables in the backend's process environment (or load a private env file with your existing startup tooling). `DATABASE_URL` is a server-side setting, never `NEXT_PUBLIC_...`.

If your database isn't running, start it before running the next commands. **Only initialize and migrate a disposable local database**, not an existing production DB.

```bash
python -m backend.scripts.init_database
python -m backend.scripts.migrate_local_records
python -m backend.scripts.migrate_local_records --apply
```

Always review the migration dry-run before applying it. The migration uses upserts and does not remove the original JSON files.

## Run tests (no paid model calls)

```bash
VISIONGUARD_USE_DATABASE=0 python -m pytest backend/tests/test_sam_concurrency.py -q
VISIONGUARD_USE_DATABASE=0 python -m pytest backend/tests -q
python -m backend.scripts.verify_all_replays
cd frontend && yarn typecheck && yarn build
```

For isolated database tests use the bundled SQLite test, not a live Postgres DB:

```bash
VISIONGUARD_USE_DATABASE=0 python -m pytest backend/tests/test_database_storage.py -q
```

To run paid concurrency test locally, **intentionally** start two separate short prepared clips and select only one concept per video. Monitor the `/api/v1/tracking-jobs/active` route. A third active request returns `409` until one slot becomes free. There is no queue in this release.

## Logo locations

- `frontend/public/visionguard-logo.png`: Gallery + Studio top-bar logo, and Replay branding (the CSS overrides the old glyphs).
- `frontend/src/app/icon.png`: browser tab/app icon, picked up by Next.js App Router.
- The logo is drawn using `/visionguard-logo.png` in `frontend/src/app/globals.css`.
- Primary original logo inside the patch: `logo/visionguard-logo.png`.

## Important limitations

- Database metadata, job records, tracking results, evidence persist; raw SAM file outputs and MP4 files remain on local disk.
- DB-enabled mode requires installed SQLAlchemy + psycopg and a reachable initialized DB.
- DB and disk transactions cannot commit atomically; preserve backups when migrating.
- Process restart interrupts running jobs; stored job state is marked interrupted when queried.
- Two simultaneous jobs can increase **Meta API spending** and stream errors. Do not enable `SAM_CONCURRENT_CONCEPTS=1` initially.
- Do not run multiple Uvicorn workers or deploy without auth, quotas, rate limits and shared storage; the local lock is not distributed.
- You have six deterministic synthetic replay fixtures, not six verified real SAM demos. Treat stock clips as candidate footage only.
- Do not put copyrighted/promotional photos into logo or attach the brand to stock footage in ways that imply endorsement.

## Commit the separate branch

```bash
git add backend/app/services backend/scripts backend/tests \
  requirements.txt .env.example docs/architecture docs/features \
  frontend/src/app/globals.css frontend/src/app/icon.png frontend/public/visionguard-logo.png
git commit -m 'feat: add optional local PostgreSQL, bounded SAM concurrency, and brand assets'
```

Do not run `git add -A` if you have unrelated uncommitted video or database work. GitHub push is not performed by any tool in this package.
