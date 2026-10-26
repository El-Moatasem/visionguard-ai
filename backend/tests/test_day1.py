"""Offline checks: CI never calls Meta or requires paid credentials."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.sam import (
    normalized_events, response_input, validate_concept, validate_video,
)
from backend.scripts.meta_smoke import main as cli_main

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok", "stage": "day-1"}


def test_status_never_returns_key(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "very-private-secret")
    response = client.get("/api/v1/meta/status")
    assert response.status_code == 200
    assert response.json()["key_present"] is True
    assert "very-private-secret" not in response.text
    assert response.json()["authenticated"] is None


def test_missing_key_status(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert client.get("/api/v1/meta/status").json()["key_present"] is False


def test_validate_concept():
    assert validate_concept("  person  ") == "person"
    with pytest.raises(ValueError):
        validate_concept("")
    with pytest.raises(ValueError):
        validate_concept("a" * 81)


def test_response_input_structure():
    data = response_input("forklift", "file-123")
    assert data[0]["content"][0] == {"type": "input_text", "text": "forklift"}
    assert data[0]["content"][1] == {"type": "input_video", "file_id": "file-123"}
    with pytest.raises(ValueError):
        response_input("person", "invalid")


def test_validate_video(tmp_path: Path):
    short = tmp_path / "clip.mp4"
    short.write_bytes(b"some test bytes")
    assert validate_video(short) == "video/mp4"
    (tmp_path / "bad.txt").write_bytes(b"abc")
    with pytest.raises(ValueError):
        validate_video(tmp_path / "bad.txt")
    with pytest.raises(ValueError):
        validate_video(tmp_path / "missing.mp4")
    # This function checks size/extension; it does not validate codec contents.


def test_status_cli_no_network(monkeypatch, capsys):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert cli_main(["status"]) == 0
    assert '"api_call_made": false' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_stream_normalization_deduplicates_done():
    async def events():
        yield {"type": "response.content_part.done", "item_id": "msg1",
               "output_index": 0, "content_index": 0,
               "part": {"type": "output_text", "text": "result"}}
        yield {"type": "response.output_text.done", "item_id": "msg1",
               "output_index": 0, "content_index": 0, "text": "result"}

    received = [record async for record in normalized_events(events())]
    assert [x["type"] for x in received].count("response.output_text.done") == 1
    assert received[-1]["text"] == "result"
