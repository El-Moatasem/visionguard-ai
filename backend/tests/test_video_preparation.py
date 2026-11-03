"""Offline checks; none of these tests call Meta or spend credits."""
from io import BytesIO
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import video_preparation

client = TestClient(app)
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 80


def test_prepare_keeps_original_and_adds_new_video(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    uploaded = client.post("/api/v1/videos", files={"file": ("long.mp4", BytesIO(MP4), "video/mp4")})
    assert uploaded.status_code == 201
    original = uploaded.json()
    monkeypatch.setattr(video_preparation, "probe_video", lambda path: {
        "available": True, "duration_seconds": 37 if path.name != "prepared.mp4" else 19.9,
        "width": 640, "height": 360, "fps": 12, "codec": "h264"})

    def fake_encode(source, target, start, duration):
        assert source.exists() and start == 10 and duration == 20
        target.write_bytes(MP4)

    monkeypatch.setattr(video_preparation, "_encode", fake_encode)
    prepared = client.post(f"/api/v1/videos/{original['id']}/prepare-for-sam", json={
        "start_seconds": 10, "duration_seconds": 20})
    assert prepared.status_code == 201, prepared.text
    derivative = prepared.json()
    assert derivative["analysis_source_video_id"] == original["id"]
    assert derivative["id"] != original["id"]
    assert derivative["sha256"] == original["sha256"]  # Same bytes in mock fixture only
    assert client.get(derivative["file_url"]).content == MP4
    assert client.get(original["file_url"]).content == MP4
    assert len(client.get("/api/v1/videos").json()["items"]) == 2


def test_reject_invalid_segment_without_spending(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    original = client.post("/api/v1/videos", files={"file": ("x.mp4", BytesIO(MP4), "video/mp4")}).json()
    monkeypatch.setattr(video_preparation, "probe_video", lambda _: {
        "available": True, "duration_seconds": 37, "width": 640, "height": 360, "fps": 12, "codec": "h264"})
    for payload in ({"start_seconds": 29, "duration_seconds": 20},
                    {"start_seconds": -1, "duration_seconds": 20},
                    {"start_seconds": 0, "duration_seconds": 121}):
        response = client.post(f"/api/v1/videos/{original['id']}/prepare-for-sam", json=payload)
        assert response.status_code == 422, response.text
    assert len(client.get("/api/v1/videos").json()["items"]) == 1
