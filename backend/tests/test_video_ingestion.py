"""Offline integration tests; no Meta API and no video fixture licensing needed."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.video_store import sniff_video

client = TestClient(app)

MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
MOV = b"\x00\x00\x00\x18ftypqt  " + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


@pytest.fixture(autouse=True)
def isolate_upload_store(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.delenv("VIDEO_MAX_BYTES", raising=False)


def upload(name: str, content: bytes, content_type="application/octet-stream"):
    return client.post("/api/v1/videos", files={"file": (name, BytesIO(content), content_type)})


def test_detect_container_without_trusting_browser():
    assert sniff_video(MP4) == (".mp4", "video/mp4")
    assert sniff_video(MOV) == (".mov", "video/quicktime")
    assert sniff_video(WEBM) == (".webm", "video/webm")
    assert sniff_video(b"not a video") is None


def test_upload_list_retrieve_and_range():
    response = upload("../test.mp4", MP4)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["name"] == "test.mp4"
    assert record["size_bytes"] == len(MP4)
    assert len(record["sha256"]) == 64
    assert record["sam_compatible_container"] is True
    assert "MODEL_API_KEY" not in str(record)
    video_id = record["id"]
    assert client.get(f"/api/v1/videos/{video_id}").json()["id"] == video_id
    listed = client.get("/api/v1/videos").json()["items"]
    assert len(listed) == 1
    full = client.get(record["file_url"])
    assert full.status_code == 200
    assert full.content == MP4
    part = client.get(record["file_url"], headers={"Range": "bytes=0-7"})
    assert part.status_code == 206
    assert part.content == MP4[:8]


def test_webm_recording_is_not_claimed_sam_ready():
    response = upload("camera.webm", WEBM, "video/webm")
    assert response.status_code == 201
    assert response.json()["sam_compatible_container"] is False


def test_reject_unrecognized_payload_and_no_orphans(tmp_path: Path):
    response = upload("faked.mp4", b"not really an mp4", "video/mp4")
    assert response.status_code == 415
    assert list((tmp_path / "uploads").iterdir()) == []


def test_reject_oversized_upload(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VIDEO_MAX_BYTES", "30")
    response = upload("huge.mp4", MP4)
    assert response.status_code == 413
    assert list((tmp_path / "uploads").iterdir()) == []


def test_unknown_video_id():
    assert client.get("/api/v1/videos/invalid").status_code == 404
    assert client.get("/api/v1/videos/" + "a" * 32 + "/file").status_code == 404


def test_key_status_still_not_exposed(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-secret-token")
    status = client.get("/api/v1/meta/status")
    assert status.status_code == 200
    assert "test-secret-token" not in status.text
