"""Offline local deletion tests: never invoke Meta and never touch the default video store."""
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import tracking_jobs
from backend.app.services.video_store import storage_dir


def seed(folder: Path, name: str, original_id=None):
    uid = uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=True)
    record = {"id": uid, "name": name, "media_type": "video/mp4", "size_bytes": 5,
              "analysis_source_video_id": original_id}
    (folder / (uid + ".json")).write_text(json.dumps(record))
    (folder / (uid + ".mp4")).write_bytes(b"12345")
    return uid


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VISIONGUARD_ALLOW_LIBRARY_DELETE", "1")
    monkeypatch.delenv("VISIONGUARD_REPLAY_ONLY", raising=False)
    with tracking_jobs._LOCK:
        assert not tracking_jobs._ACTIVE, "Tests require no active external SAM jobs"
    return TestClient(app)


def test_delete_single_cascades_prepared_video_and_reports(client, tmp_path):
    folder = storage_dir()
    original = seed(folder, "original.mp4")
    derived = seed(folder, "derived.mp4", original)
    other = seed(folder, "keep.mp4")
    job = str(uuid.uuid4())
    root = folder.parent / "tracking"
    root.mkdir(parents=True)
    (root / (job + ".json")).write_text(json.dumps({"id":job,"video_id": derived, "status":"completed"}))
    (root / (job + ".result.json")).write_text("{}")
    evidence = folder.parent / "evidence"
    evidence.mkdir()
    evidence_id = uuid.uuid4().hex
    (evidence / f"{evidence_id}.json").write_text(json.dumps({"source": {"tracking_job_id": job, "video_id": derived}}))
    r = client.delete(f"/api/v1/videos/{original}")
    assert r.status_code == 200, r.text
    assert r.json()["deleted_videos"] == 2
    assert r.json()["deleted_jobs"] == 1
    assert r.json()["deleted_evidence"] == 1
    assert not (folder / (original + ".mp4")).exists()
    assert not (folder / (derived + ".json")).exists()
    assert (folder / (other + ".mp4")).exists()
    assert client.get(f"/api/v1/videos/{other}").status_code == 200


def test_delete_all_requires_exact_confirmation(client):
    uid = seed(storage_dir(), "one.mp4")
    invalid = client.post("/api/v1/videos/delete-all", json={"confirm": "yes"})
    assert invalid.status_code == 422
    assert (storage_dir() / (uid + ".mp4")).exists()
    ok = client.post("/api/v1/videos/delete-all", json={"confirm": "DELETE ALL VIDEOS"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["deleted_videos"] == 1


def test_active_job_rejects_deletion(client):
    video_id = seed(storage_dir(), "busy.mp4")
    job_id = str(uuid.uuid4())
    root = storage_dir().parent / "tracking"
    root.mkdir(exist_ok=True)
    (root / (job_id + ".json")).write_text(json.dumps({"id":job_id,"video_id": video_id,"status":"running"}))
    with tracking_jobs._LOCK:
        tracking_jobs._ACTIVE.add(job_id)
    try:
        assert client.delete(f"/api/v1/videos/{video_id}").status_code == 409
        assert client.post("/api/v1/videos/delete-all", json={"confirm":"DELETE ALL VIDEOS"}).status_code == 409
        assert (storage_dir() / (video_id + ".mp4")).exists()
    finally:
        with tracking_jobs._LOCK:
            tracking_jobs._ACTIVE.discard(job_id)


def test_delete_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.delenv("VISIONGUARD_ALLOW_LIBRARY_DELETE", raising=False)
    uid = seed(storage_dir(), "private.mp4")
    assert TestClient(app).delete(f"/api/v1/videos/{uid}").status_code == 403
    assert (storage_dir() / (uid + ".mp4")).exists()
