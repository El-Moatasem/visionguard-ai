# VisionGuard AI — Neon PostgreSQL Integration

## Scope and architecture

This package adds **optional, real SQL database persistence** to the existing FastAPI app. When enabled, PostgreSQL (or SQLite for offline automated tests) is the source of truth for:

- Video metadata (`vg_videos`), including prepared clip lineage
- SAM tracking job state (`vg_tracking_jobs`)
- Completed tracking results (`vg_tracking_results`)
- Evidence snapshots and review decisions (`vg_evidence_reports`)

The existing local JSON files are retained as mirrors for backward compatibility, and the existing binary media, raw SAM files, and progressive preview files **remain on local disk**. This is a phased architecture, **not** a finished cloud-storage or production-authentication implementation.

```
Next.js Gallery / Analysis Studio
              |
        FastAPI REST API
        /           \
Neon PostgreSQL    Local VIDEO_STORAGE_DIR / var/
 metadata +          MP4, MOV, WebM, previews,
 jobs + evidence      SAM raw artifacts
              |
         Meta SAM 3.1 (only by explicit action)
```

## Apply to your local checkout

From `visionguard-ai`:

```bash
git status --short
git switch -c feature/neon-postgres-persistence
python3 /path/to/VisionGuard_Neon_Postgres_Integration/apply.py --repo .
python3 /path/to/VisionGuard_Neon_Postgres_Integration/apply.py --repo . --apply
python -m pip install -r requirements.txt
```

The first command is a dry run; `--apply` modifies files and makes backups alongside your repository. No GitHub action or database connection is performed by the installer. The existing file-only mode remains the default when `VISIONGUARD_USE_DATABASE=0`.

## Create your Neon database

1. In [Neon Console](https://console.neon.tech/), create/select a project and a dedicated database.
2. Click **Connect** and copy the `DATABASE_URL` connection string; for application requests use the **pooled** connection string. Keep TLS parameters such as `sslmode=require` and `channel_binding=require` from Neon.
3. Put it in the repo-root **untracked** `.env` file (NOT `frontend/.env.local`, never Git):

```dotenv
VISIONGUARD_USE_DATABASE=1
DATABASE_URL=postgresql://ROLE:PASSWORD@NEON_HOST-pooler/DB_NAME?sslmode=require&channel_binding=require
```

The example values are placeholders: copy your real URL from Neon. `db_store.py` normalizes `postgresql://` to SQLAlchemy's Psycopg 3 dialect. A separate direct URL is suitable for administrative migration jobs when needed. Do not expose this URL in browsers, logs, README, or screenshots.

**First-run schema and import, in this exact order:**

```bash
source .venv/bin/activate
python -m backend.scripts.init_database
python -m backend.scripts.migrate_local_records
python -m backend.scripts.migrate_local_records --apply
python -m pytest backend/tests/test_database_storage.py -q
# IMPORTANT: run older filesystem tests in file mode, NOT against real Neon!
VISIONGUARD_USE_DATABASE=0 python -m pytest backend/tests -q
```

The import scans all locally stored JSON metadata and uses idempotent SQL upserts. It does **not** delete any JSON or transfer any video bytes. If the database is enabled without importing existing JSON, the video/job/evidence lists will initially be empty.

To verify your actual Neon records:

```bash
python - <<'PY'
from backend.app.services import db_store
print('Database connected:', db_store.check())
print('Videos:', len(db_store.list_videos(limit=None)))
print('Tracking jobs:', len(db_store.list_jobs(limit=None)))
print('Evidence reports:', len(db_store.list_evidence(limit=None)))
PY
```

Do not paste the database connection string in chat or command output.

## Rollback safely

1. Stop FastAPI first.
2. Set `VISIONGUARD_USE_DATABASE=0` in root `.env`, or remove it.
3. Start FastAPI again; it uses the existing filesystem JSON metadata.

Because writes are mirrored to disk during normal operations, rollback generally preserves locally created records **as long as their files remain present**. As with any dual-storage migration, do not switch modes during an active paid job; first stop/cancel jobs and back up both stores.

## Deployment caveats (important)

- This **does not make the full app deployable on ephemeral Render instances**. Database records survive, but video bytes, progressive overlays and SAM artifacts still require persistent disk or object storage (S3/R2). If those files disappear, playback and analysis will fail even though DB rows remain.
- The SAM execution gate and cancellation remain **single-process and in-memory**. Don't scale to multiple worker processes until you implement an atomic database-backed job claim, queue, and recovery policy.
- Current paid inference, upload, evidence and deletion routes are **unauthenticated**. Do not expose them publicly. Keep `VISIONGUARD_REPLAY_ONLY=1` for public demo until authentication, quotas and storage controls exist.
- The PostgreSQL schema is a version-1 bootstrap using SQLAlchemy `create_all`. Future schema changes require a real migration discipline such as Alembic; do not use `create_all` as a substitute for migrations in a deployed multi-user product.
- Postgres transactions cannot atomically commit remote files. The implementation writes metadata to PostgreSQL and still mirrors JSON; review operational retry behavior before production use.
- **Do not run the existing full backend test suite with a live Neon `DATABASE_URL` and `VISIONGUARD_USE_DATABASE=1`.** Those older tests assume an isolated file store and may write fake fixtures to your live database. Use `VISIONGUARD_USE_DATABASE=0` for that suite and the new isolated SQLite test for DB operations.
- The integration is tested via SQLite locally. A real Neon live connection, actual SAM job, and complete app suite **must be verified in your environment**; no real Neon credentials are shipped in this package.

## Tests to run before merging

```bash
python -m pytest backend/tests/test_database_storage.py -v
# Never let existing filesystem fixtures write into a real Neon database:
VISIONGUARD_USE_DATABASE=0 python -m pytest backend/tests -q
python -m backend.scripts.verify_all_replays
cd frontend && yarn install --frozen-lockfile && yarn typecheck && yarn build
```

Verify one video upload, one prepared derivative, one completed SAM job (if you wish to spend credits), evidence review/export, then deletion in your **local** environment. Confirm the DB records survive FastAPI restart. Export any evidence you must preserve before testing deletion.
