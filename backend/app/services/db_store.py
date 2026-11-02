"""Opt-in PostgreSQL/SQLite structured storage for VisionGuard metadata.

Enable only with VISIONGUARD_USE_DATABASE=1 and DATABASE_URL. Video BYTES,
streaming previews and raw SAM artifacts remain on local disk for now.
No DB requests occur when the feature flag is off.

Run ``python -m backend.scripts.init_database`` once before enabling.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from sqlalchemy import JSON, Column, Index, MetaData, String, Table, Text, create_engine, delete, insert, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
meta = MetaData()
videos = Table(
    "vg_videos", meta,
    Column("id", String(32), primary_key=True),
    Column("created_at", String(40), nullable=False),
    Column("source_video_id", String(32)),
    Column("document", JSON_DOCUMENT, nullable=False),
    Index("vg_videos_created", "created_at"),
    Index("vg_videos_source", "source_video_id"),
)
jobs = Table(
    "vg_tracking_jobs", meta,
    Column("id", String(36), primary_key=True),
    Column("video_id", String(32), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("status", String(24), nullable=False),
    Column("document", JSON_DOCUMENT, nullable=False),
    Index("vg_jobs_video", "video_id"),
    Index("vg_jobs_created", "created_at"),
)
results = Table(
    "vg_tracking_results", meta,
    Column("job_id", String(36), primary_key=True),
    Column("document", JSON_DOCUMENT, nullable=False),
)
evidence = Table(
    "vg_evidence_reports", meta,
    Column("id", String(32), primary_key=True),
    Column("tracking_job_id", String(36), nullable=False),
    Column("video_id", String(32), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("document", JSON_DOCUMENT, nullable=False),
    Index("vg_evidence_job", "tracking_job_id"),
    Index("vg_evidence_video", "video_id"),
)


def enabled() -> bool:
    return os.environ.get("VISIONGUARD_USE_DATABASE", "0") == "1"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("VISIONGUARD_USE_DATABASE=1 requires DATABASE_URL")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith(("postgresql+psycopg://", "sqlite://")):
        raise RuntimeError("DATABASE_URL must be PostgreSQL (psycopg) or local test SQLite")
    return url


@lru_cache(maxsize=4)
def _engine(url: str) -> Engine:
    options: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("postgresql"):
        options.update(pool_size=3, max_overflow=2, pool_recycle=300, connect_args={"connect_timeout": 10})
    return create_engine(url, **options)


def engine() -> Engine:
    return _engine(database_url())


def initialize() -> None:
    if not enabled():
        raise RuntimeError("Enable VISIONGUARD_USE_DATABASE=1 to initialize the schema")
    # Explicit setup operation, never automatic during FastAPI startup.
    meta.create_all(engine())


def check() -> bool:
    from sqlalchemy import text
    with engine().connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1


def _upsert(table: Table, key: str, document: dict[str, Any], **other: Any) -> None:
    values = {key: document[key], **other, "document": document}
    db = engine()
    # Database-native upsert is atomic for simultaneous legitimate updates.
    if db.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif db.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        raise RuntimeError("Unsupported SQL dialect")
    statement = dialect_insert(table).values(**values)
    statement = statement.on_conflict_do_update(index_elements=[key], set_={k: statement.excluded[k] for k in values if k != key})
    with db.begin() as connection:
        connection.execute(statement)


def _one(table: Table, key: str, value: str) -> dict[str, Any] | None:
    with engine().connect() as connection:
        row = connection.execute(select(table.c.document).where(table.c[key] == value)).first()
        return row[0] if row else None


def _many(table: Table, *where: Any, limit: int | None = None) -> list[dict[str, Any]]:
    statement = select(table.c.document).where(*where).order_by(table.c.created_at.desc())
    if limit is not None:
        statement = statement.limit(limit)
    with engine().connect() as connection:
        return list(connection.execute(statement).scalars())


def put_video(document: dict[str, Any]) -> None:
    _upsert(videos, "id", document, created_at=document.get("created_at", ""),
            source_video_id=document.get("analysis_source_video_id"))


def get_video(video_id: str) -> dict[str, Any] | None:
    return _one(videos, "id", video_id)


def list_videos(limit: int | None = 30) -> list[dict[str, Any]]:
    return _many(videos, limit=limit)


def put_job(document: dict[str, Any]) -> None:
    _upsert(jobs, "id", document, video_id=document.get("video_id", ""),
            created_at=document.get("created_at", ""), status=document.get("status", "unknown"))


def get_job(job_id: str) -> dict[str, Any] | None:
    return _one(jobs, "id", job_id)


def list_jobs(video_id: str | None = None, limit: int | None = 10) -> list[dict[str, Any]]:
    where = (jobs.c.video_id == video_id,) if video_id else ()
    return _many(jobs, *where, limit=limit)


def put_result(document: dict[str, Any]) -> None:
    _upsert(results, "job_id", {"job_id": document["job_id"], **document})


def get_result(job_id: str) -> dict[str, Any] | None:
    return _one(results, "job_id", job_id)


def put_evidence(document: dict[str, Any]) -> None:
    source = document.get("source") or {}
    _upsert(evidence, "id", document, tracking_job_id=source.get("tracking_job_id", ""),
            video_id=source.get("video_id", ""), created_at=document.get("created_at", ""))


def get_evidence(report_id: str) -> dict[str, Any] | None:
    return _one(evidence, "id", report_id)


def list_evidence(job_id: str | None = None, limit: int | None = 30) -> list[dict[str, Any]]:
    where = (evidence.c.tracking_job_id == job_id,) if job_id else ()
    return _many(evidence, *where, limit=limit)


def delete_graph(video_ids: set[str], job_ids: set[str]) -> None:
    """Remove DB metadata for deleted videos and their derived results atomically.

    Only call after validating all active jobs have finished. Uploaded video bytes
    are unlinked separately by the existing deletion service.
    """
    if not video_ids:
        return
    with engine().begin() as connection:
        connection.execute(delete(evidence).where(evidence.c.video_id.in_(video_ids)))
        if job_ids:
            connection.execute(delete(evidence).where(evidence.c.tracking_job_id.in_(job_ids)))
            connection.execute(delete(results).where(results.c.job_id.in_(job_ids)))
            connection.execute(delete(jobs).where(jobs.c.id.in_(job_ids)))
        connection.execute(delete(videos).where(videos.c.id.in_(video_ids)))
