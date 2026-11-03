"""Fast SQLite-backed integration tests for the opt-in database adapter.

Run without Neon credentials: python -m pytest backend/tests/test_database_storage.py -q
"""
from __future__ import annotations

import pytest

from backend.app.services import db_store


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("VISIONGUARD_USE_DATABASE", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    db_store.initialize()
    yield db_store
    db_store.engine().dispose()
    db_store._engine.cache_clear()


def test_video_job_result_evidence_roundtrip(db):
    video_id = "a" * 32
    video = {"id": video_id, "created_at": "2026-11-02T20:00:00Z", "name": "warehouse.mp4"}
    db.put_video(video)
    assert db.get_video(video_id)["name"] == "warehouse.mp4"
    assert [x["id"] for x in db.list_videos()] == [video_id]

    job_id = "00000000-0000-4000-8000-000000000001"
    job = {"id": job_id, "video_id": video_id, "created_at": "2026-11-02T20:01:00Z", "status": "running"}
    db.put_job(job)
    db.put_job({**job, "status": "completed"})
    assert db.list_jobs(video_id)[0]["status"] == "completed"
    db.put_result({"job_id": job_id, "box_count": 7, "boxes": [{"frame": 0}]})
    assert db.get_result(job_id)["box_count"] == 7

    report_id = "b" * 32
    document = {"id": report_id, "created_at": "2026-11-02T20:02:00Z",
                "source": {"video_id": video_id, "tracking_job_id": job_id}, "reviews": []}
    db.put_evidence(document)
    db.put_evidence({**document, "reviews": [{"decision": "confirmed"}]})
    assert len(db.get_evidence(report_id)["reviews"]) == 1
    assert len(db.list_evidence(job_id)) == 1
    db.delete_graph({video_id}, {job_id})
    assert db.get_video(video_id) is None
    assert db.get_job(job_id) is None
    assert db.get_result(job_id) is None
    assert db.get_evidence(report_id) is None


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("VISIONGUARD_USE_DATABASE", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db_store.engine()
