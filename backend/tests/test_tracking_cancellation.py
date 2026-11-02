"""Offline tests for process-local cancel-one and cancel-all, never call Meta."""
import asyncio
import threading
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import tracking_jobs as jobs


def create_queued_job(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MODEL_API_KEY", "fake-not-billable")
    monkeypatch.delenv("SAM_DEMO_CONCEPTS", raising=False)
    monkeypatch.setattr(jobs, "probe_video", lambda _: {
        "available": True, "width": 640, "height": 360,
        "fps": 12.0, "duration_seconds": 3.0, "codec": "h264"})
    with TestClient(app) as client:
        upload = client.post("/api/v1/videos", files={"file": (
            "video.mp4", BytesIO(b"\x00\x00\x00\x18ftypisom" + b"\0" * 64), "video/mp4")})
        assert upload.status_code == 201
        video_id = upload.json()["id"]
    return jobs.create_job(video_id, ["person"])


def test_cancel_queued_never_calls_meta(tmp_path, monkeypatch):
    job = create_queued_job(tmp_path, monkeypatch)
    called = False

    async def no_remote(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Should never call remote inference")

    monkeypatch.setattr(jobs, "run_video", no_remote)
    assert any(item["id"] == job["id"] for item in jobs.active_jobs())
    req = jobs.cancel_job(job["id"])
    assert req["status"] == "cancelling"
    jobs.process_job(job["id"])
    assert jobs.get_job(job["id"])["status"] == "cancelled"
    assert jobs.active_jobs() == []
    assert not called
    with pytest.raises(jobs.TrackingError) as exc:
        jobs.get_result(job["id"])
    assert exc.value.status_code == 409


def test_cancel_all_cancels_queued_and_is_idempotent(tmp_path, monkeypatch):
    job = create_queued_job(tmp_path, monkeypatch)
    results = jobs.cancel_all_jobs()
    assert any(record["id"] == job["id"] for record in results)
    assert jobs.cancel_job(job["id"])["status"] == "cancelling"
    jobs.process_job(job["id"])
    assert jobs.get_job(job["id"])["status"] == "cancelled"
    assert jobs.cancel_all_jobs() == []


def test_cancel_inflight_async_model_cannot_publish_final(tmp_path, monkeypatch):
    job = create_queued_job(tmp_path, monkeypatch)
    started = threading.Event()

    async def slow_model(*args, **kwargs):
        started.set()
        await asyncio.sleep(30)  # cancelled by loop.call_soon_threadsafe
        raise AssertionError("Cancelled job must not finish")

    monkeypatch.setattr(jobs, "run_video", slow_model)
    worker = threading.Thread(target=jobs.process_job, args=(job["id"],), daemon=True)
    worker.start()
    assert started.wait(5), "Mock inference did not start"
    with TestClient(app) as client:
        active = client.get("/api/v1/tracking-jobs/active")
        assert active.status_code == 200
        assert any(item["id"] == job["id"] for item in active.json()["items"])
        response = client.post("/api/v1/tracking-jobs/cancel-all")
        assert response.status_code == 202
        assert response.json()["count"] >= 1
    worker.join(timeout=5)
    assert not worker.is_alive(), "Cancellation must stop the cooperative worker"
    assert jobs.get_job(job["id"])["status"] == "cancelled"
    assert not jobs._paths(job["id"])[1].exists()
    assert jobs.active_jobs() == []


def test_completed_job_is_not_retroactively_cancelled(tmp_path, monkeypatch):
    job = create_queued_job(tmp_path, monkeypatch)
    with jobs._LOCK:
        jobs._ACTIVE.discard(job["id"])
    record = jobs._read_record(job["id"])
    record["status"] = "completed"
    jobs._write(jobs._paths(job["id"])[0], record)
    assert jobs.cancel_job(job["id"])["status"] == "completed"
    assert jobs.get_job(job["id"])["status"] == "completed"
