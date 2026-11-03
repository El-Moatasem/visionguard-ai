"""Offline regression tests for preview throttling and job-stage progress.

No Meta calls or database migration. Runs in an existing VisionGuard checkout.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from backend.app.services.sam import preview_interval_seconds


@pytest.mark.parametrize("setting,expected", [("1",1.0),("4",4.0),("12.5",12.5),("15",15.0)])
def test_preview_interval_accepts_bounded_values(monkeypatch, setting, expected):
    monkeypatch.setenv("SAM_PREVIEW_INTERVAL_SECONDS", setting)
    assert preview_interval_seconds() == expected


@pytest.mark.parametrize("setting", ["", "nan", "inf", "-3", "0", "0.5", "16", "not-a-number"])
def test_preview_interval_fails_closed_before_billable_calls(monkeypatch, setting):
    monkeypatch.setenv("SAM_PREVIEW_INTERVAL_SECONDS", setting)
    with pytest.raises(ValueError, match="SAM_PREVIEW_INTERVAL_SECONDS"):
        preview_interval_seconds()


def test_job_stores_concept_stage_and_upload_timing_offline(monkeypatch, tmp_path):
    """Fake SAM events prove the API-visible state without calling Meta."""
    from backend.app.services import tracking_jobs as jobs
    monkeypatch.setenv("VISIONGUARD_USE_DATABASE", "0")
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    file = tmp_path / "video.mp4"
    file.write_bytes(b"fake local test")
    monkeypatch.setattr(jobs, "get_video_file", lambda _video_id: (file, {"id": "a" * 32}))
    monkeypatch.setattr(jobs, "build_tracking_report", lambda summaries, probe: {
        "schema_version": 1, "boxes": [], "tracks": [], "gaps": [],
        "track_count": 0, "gap_count": 0, "box_count": 0,
        "concepts_requested": [item["concept"] for item in summaries],
        "media_probe": probe,
    })

    async def fake_run(_path, concepts, _output, progress_callback):
        assert concepts == ["person"]
        progress_callback({"phase": "upload_completed", "upload_seconds": 1.25,
                           "message": "Uploaded"})
        progress_callback({"phase": "segmenting", "concept": "person", "message": "Tracking person"})
        progress_callback({"phase": "concept_completed", "concept": "person",
                           "summary": {"concept": "person", "boxes": []},
                           "inference_seconds": 3.75, "message": "Done"})
        return [{"concept": "person", "outcome": "completed", "boxes": []}]

    monkeypatch.setattr(jobs, "run_video", fake_run)
    job_id = str(uuid.uuid4())
    record = {"id": job_id, "video_id": "a" * 32, "status": "queued",
              "concepts": ["person"], "concepts_completed": [],
              "media_probe": {"width": 640, "height": 360, "fps": 12}}
    jobs._write(jobs._paths(job_id)[0], record)
    jobs._ACTIVE.add(job_id)
    try:
        asyncio.run(jobs._process_job_async(job_id))
        after = jobs._read_record(job_id)
        assert after["status"] == "completed"
        assert after["concepts_completed"] == ["person"]
        assert after["upload_seconds"] == pytest.approx(1.25)
        assert after["last_concept_inference_seconds"] == pytest.approx(3.75)
        assert after["current_concept"] is None
    finally:
        jobs._ACTIVE.discard(job_id)
