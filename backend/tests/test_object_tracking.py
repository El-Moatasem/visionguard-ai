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
    monkeypatch.setattr(tracking_jobs, "probe_video", lambda _path: {"available": True, "width": 640, "height": 360, "fps": 25.0, "duration_seconds": 4, "codec": "h264"})
    async def fake_run_video(path, concepts, out, *, progress_callback=None):
        assert set(concepts) == {"person", "forklift"}
        if progress_callback is not None:
            progress_callback({"phase": "streaming", "concept": "person", "revision": 3,
                               "boxes": [box(0, 0), box(0, 2)],
                               "message": "Streaming person boxes"})
            progress_callback({"phase": "concept_completed", "concept": "person",
                               "summary": summary("person", [box(0, 0), box(0, 2)]),
                               "message": "Person completed"})
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
    preview = client.get(f"/api/v1/tracking-jobs/{job_id}/preview")
    assert preview.status_code == 200
    assert preview.json()["partial"] is True
    assert preview.json()["box_count"] == 2
    assert preview.json()["concepts_completed"] == ["person"]


def test_webm_rejected_before_spending(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_API_KEY", "fake-key")
    # Valid EBML signature; the local upload store recognizes the container.
    uploaded = client.post("/api/v1/videos", files={"file": ("test.webm", BytesIO(b"\x1a\x45\xdf\xa3" + b"\x00" * 64), "video/webm")})
    assert uploaded.status_code == 201
    video_id = uploaded.json()["id"]
    assert client.post(f"/api/v1/videos/{video_id}/tracking-jobs").status_code == 415


def test_short_tracking_gap_tolerance_retains_provisional_fragment():
    report = build_tracking_report([summary(boxes=[box(1, 1), box(1, 3), box(1, 8)])])
    assert report["fragment_gap_tolerance_frames"] == 2
    assert report["gap_count"] == 2
    assert report["tracks"][0]["fragment_count"] == 2
    assert report["tracks"][0]["has_uncertain_identity_continuity"] is True
    assert report["boxes"][0]["fragment_id"] == report["boxes"][1]["fragment_id"]
    assert report["boxes"][1]["fragment_id"] != report["boxes"][2]["fragment_id"]
    strict = build_tracking_report([summary(boxes=[box(1, 1), box(1, 3)])], max_missing_frames_for_fragment=0)
    assert strict["tracks"][0]["fragment_count"] == 2


def test_sam_media_dimensions_fallback_is_validated():
    report = build_tracking_report([{"concept": "person", "outcome": "completed", "boxes": [],
                                   "media": {"width": 1280, "height": 720, "fps": 25}}], {"available": False})
    assert report["media_metadata"] == {"width": 1280.0, "height": 720.0, "fps": 25.0}
    rejected = build_tracking_report([{"concept": "person", "outcome": "completed", "boxes": [],
                                     "media": {"width": -1, "height": float("inf"), "fps": "unknown"}}])
    assert rejected["media_metadata"] == {}


def test_preflight_requires_ffprobe_before_paid_request(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_API_KEY", "fake-key")
    uploaded = client.post("/api/v1/videos", files={"file": (
        "sample.mp4", BytesIO(b"\x00\x00\x00\x18ftypisom" + b"\x00"*64), "video/mp4")})
    assert uploaded.status_code == 201
    monkeypatch.setattr(tracking_jobs, "probe_video", lambda _: {"available": False})
    response = client.post(f"/api/v1/videos/{uploaded.json()['id']}/tracking-jobs")
    assert response.status_code == 503
    assert "FFprobe" in response.json()["detail"]
    assert client.get(f"/api/v1/videos/{uploaded.json()['id']}/tracking-jobs").json() == {"items": []}


def test_preview_returns_404_if_no_observations(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    assert client.get("/api/v1/tracking-jobs/not-a-uuid/preview").status_code == 404
    job_id = "62a2d3da-d07b-4a7b-9ec2-69e7b14db4c3"
    path, _ = tracking_jobs._paths(job_id)
    tracking_jobs._write(path, {"id": job_id, "status": "failed", "video_id": "a"*32})
    assert client.get(f"/api/v1/tracking-jobs/{job_id}/preview").status_code == 404


def test_preview_does_not_include_masks_or_invent_boxes():
    output = tracking_jobs._safe_preview_boxes("person", [
        {"object_id": "a", "frame": 2, "left": 10, "top": 20, "right": 100, "bottom": 120},
        {"object_id": "a", "frame": 5, "left": 3, "top": 2, "right": 1, "bottom": 120},
        {"object_id": "a", "frame": 3, "left": 10, "top": 20, "right": float("nan"), "bottom": 120},
    ])
    assert len(output) == 1
    assert output[0]["frame"] == 2
    assert output[0]["concept"] == "person"
    assert "mask" not in output[0]


def test_single_concept_live_preflight_option(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_API_KEY", "fake-key")
    monkeypatch.setenv("SAM_DEMO_CONCEPTS", "person")
    monkeypatch.setattr(tracking_jobs, "probe_video", lambda _: {
        "available": True, "width": 640, "height": 480,
        "fps": 12.0, "duration_seconds": 4, "codec": "h264"})
    uploaded = client.post("/api/v1/videos", files={"file": (
        "sample.mp4", BytesIO(b"\x00\x00\x00\x18ftypisom" + b"\x00"*64), "video/mp4")})
    # Direct preflight only; do not start any background/billable jobs.
    job = tracking_jobs.create_job(uploaded.json()["id"])
    assert job["concepts"] == ["person"]
    assert job["phase"] == "queued"
    assert "preview" in job["preview_url"]
    with tracking_jobs._LOCK:
        tracking_jobs._ACTIVE.discard(job["id"])


def test_reject_expensive_video_before_paid_job(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_API_KEY", "fake-key")
    monkeypatch.setattr(tracking_jobs, "probe_video", lambda _: {
        "available": True, "width": 3840, "height": 2160,
        "fps": 60.0, "duration_seconds": 4, "codec": "h264"})
    uploaded = client.post("/api/v1/videos", files={"file": (
        "sample.mp4", BytesIO(b"\x00\x00\x00\x18ftypisom" + b"\x00"*64), "video/mp4")})
    response = client.post(f"/api/v1/videos/{uploaded.json()['id']}/tracking-jobs")
    assert response.status_code == 413
    assert "1080p/30fps" in response.json()["detail"]
