"""Offline tracking tests: no Meta API calls, no real uploaded videos needed."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import tracking_jobs
from backend.app.services.tracking_report import TrackingReportError, build_tracking_report

client = TestClient(app)


def summary(concept="person", boxes=None):
    return {"concept": concept, "outcome": "completed", "boxes": boxes or []}


def box(obj, frame, x=0):
    return {"object_id": obj, "frame": frame, "left": x, "top": 10, "right": x + 10, "bottom": 20}


def test_contiguous_track_has_no_identity_gap():
    data = build_tracking_report([summary(boxes=[box(0, 0), box(0, 1), box(0, 2)])], {"fps": 30})
    assert data["track_count"] == 1
    assert data["gap_count"] == 0
    assert data["tracks"][0]["fragment_count"] == 1
    assert data["boxes"][2]["fragment_id"] == "person:0#0"
    assert data["time_alignment"] == "approximate"
    assert data["hazard_detection_implemented"] is False


def test_missing_frames_split_fragment_and_require_review():
    report = build_tracking_report([summary(boxes=[box(3, 0), box(3, 1), box(3, 5)])])
    assert report["gap_count"] == 1
    assert report["gaps"][0]["missing_frames"] == 3
    assert report["gaps"][0]["identity_continuity"] == "unverified"
    assert report["tracks"][0]["has_uncertain_identity_continuity"] is True
    assert [b["fragment_id"] for b in report["boxes"]] == ["person:3#0", "person:3#0", "person:3#1"]


def test_ids_scoped_to_concept_and_invalid_boxes_ignored():
    report = build_tracking_report([
        summary("person", [box(0, 0), {"object_id": "a", "frame": 1, "left": 4, "right": 2, "top": 0, "bottom": 2}]),
        summary("forklift", [box(0, 0, 100)])
    ])
    assert {t["track_id"] for t in report["tracks"]} == {"person:0", "forklift:0"}
    assert report["box_count"] == 2


def test_zero_matches_is_valid_and_no_fabricated_tracks():
    result = build_tracking_report([summary("person"), summary("forklift")])
    assert result["track_count"] == result["box_count"] == result["gap_count"] == 0


def test_reject_duplicate_or_incomplete_summaries():
    with pytest.raises(TrackingReportError):
        build_tracking_report([summary("person"), summary("person")])
    with pytest.raises(TrackingReportError):
        build_tracking_report([{"concept": "person", "outcome": "incomplete"}])


def test_video_tracking_requires_key_and_stored_video(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    missing = client.post("/api/v1/videos/" + "a" * 32 + "/tracking-jobs")
    assert missing.status_code == 404
    res = client.post("/api/v1/videos/not-a-video/tracking-jobs")
    assert res.status_code == 404
    # Existing video is a fake MP4 container for upload tests (no inference).
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
    uploaded = client.post("/api/v1/videos", files={"file": ("sample.mp4", BytesIO(mp4), "video/mp4")})
    assert uploaded.status_code == 201
    video_id = uploaded.json()["id"]
    unconfigured = client.post(f"/api/v1/videos/{video_id}/tracking-jobs")
    assert unconfigured.status_code == 503
    assert client.get(f"/api/v1/videos/{video_id}/tracking-jobs").json() == {"items": []}


def test_invalid_job_id_and_result_not_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    assert client.get("/api/v1/tracking-jobs/123").status_code == 404
    assert client.get(f"/api/v1/tracking-jobs/{'a' * 8}-aaaa-aaaa-aaaa-aaaaaaaaaaaa/result").status_code == 404


def test_interrupted_job_detected_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    job_id = "62a2d3da-d07b-4a7b-9ec2-69e7b14db4c3"
    path, _ = tracking_jobs._paths(job_id)
    tracking_jobs._write(path, {"id": job_id, "video_id": "b" * 32, "status": "running"})
    record = tracking_jobs.get_job(job_id)
    assert record["status"] == "interrupted"
    assert tracking_jobs.get_job(job_id)["status"] == "interrupted"


def test_job_execution_mocked_end_to_end(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key")
    uploaded = client.post("/api/v1/videos", files={"file": ("sample.mp4", BytesIO(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64), "video/mp4")})
    video_id = uploaded.json()["id"]
    monkeypatch.setattr(tracking_jobs, "probe_video", lambda _path: {"available": True, "fps": 25.0, "duration_seconds": 4, "codec": "h264"})
    async def fake_run_video(path, concepts, out):
        assert set(concepts) == {"person", "forklift"}
        return [summary("person", [box(0, 0), box(0, 2)]), summary("forklift", [box(0, 1)])]
    monkeypatch.setattr(tracking_jobs, "run_video", fake_run_video)
    with TestClient(app) as test_client:
        response = test_client.post(f"/api/v1/videos/{video_id}/tracking-jobs")
    assert response.status_code == 202
    job_id = response.json()["id"]
    status = client.get(f"/api/v1/tracking-jobs/{job_id}")
    assert status.json()["status"] == "completed"
    result = client.get(f"/api/v1/tracking-jobs/{job_id}/result").json()
    assert result["gap_count"] == 1
    assert result["track_count"] == 2
    assert result["models"] == ["sam-3.1"]
    assert result["hazard_detection_implemented"] is False


def test_webm_rejected_before_spending(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_API_KEY", "fake-key")
    # Valid EBML signature; the local upload store recognizes the container.
    uploaded = client.post("/api/v1/videos", files={"file": ("test.webm", BytesIO(b"\x1a\x45\xdf\xa3" + b"\x00" * 64), "video/webm")})
    assert uploaded.status_code == 201
    video_id = uploaded.json()["id"]
    assert client.post(f"/api/v1/videos/{video_id}/tracking-jobs").status_code == 415
