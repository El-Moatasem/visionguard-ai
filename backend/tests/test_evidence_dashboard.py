"""Feature 5: offline evidence + replay tests, no real video or Meta API."""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import evidence_store
from backend.app.services.replay_fixtures import get_scenario
from backend.app.services.safety_engine import evaluate_tracking
from backend.app.services.safety_rules import RuleSpec

client = TestClient(app)


def rule():
    return get_scenario("warehouse-copresence")["default_rule"]


def test_read_only_replay_and_three_cases():
    result = client.get("/api/v1/replay/scenarios")
    assert result.status_code == 200
    assert result.json()["provenance"] == "synthetic_fixture"
    assert len(result.json()["items"]) >= 6
    assert {"parking-car-dwell", "retail-cart-aisle", "construction-zone-entry"}.issubset({x["id"] for x in result.json()["items"]})
    expected = {
        "warehouse-copresence": (True, False),
        "occlusion-review": (True, True),
        "clear-aisle": (False, False),
    }
    for scenario_id, (has_hazard, has_uncertainty) in expected.items():
        response = client.get(f"/api/v1/replay/scenarios/{scenario_id}")
        assert response.status_code == 200
        scenario = response.json()
        assert scenario["provenance"] == "synthetic_fixture"
        assert scenario["video_asset_included"] is False
        assert scenario["live_inference"] is False
        posted = client.post(f"/api/v1/replay/scenarios/{scenario_id}/evaluate", json={"rule": scenario["default_rule"]})
        assert posted.status_code == 200, posted.text
        data = posted.json()
        assert (data["event_count"] > 0) is has_hazard
        assert (data["uncertainty_count"] > 0) is has_uncertainty
        assert data["live_inference"] is False


def test_replay_rule_change_uses_same_runtime():
    original = get_scenario("clear-aisle")
    updated = original["default_rule"].copy()
    updated["rule_type"] = "person_in_zone"
    assert client.post("/api/v1/replay/scenarios/clear-aisle/evaluate", json={"rule": updated}).json()["event_count"] == 0
    changed = updated.copy()
    changed["zone"] = {**updated["zone"], "x_min": 0, "x_max": 1}
    assert client.post("/api/v1/replay/scenarios/clear-aisle/evaluate", json={"rule": changed}).json()["event_count"] > 0
    assert client.get("/api/v1/replay/scenarios/not-found").status_code == 404
    assert client.post("/api/v1/replay/scenarios/not-found/evaluate", json={"rule": updated}).status_code == 404
    assert client.post("/api/v1/replay/scenarios/clear-aisle/evaluate", json={"rule": {}}).status_code == 422


def fake_live_report():
    return get_scenario("occlusion-review")["tracking_report"]


def setup_mocks(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_STORAGE_DIR", str(tmp_path / "videos"))
    job_id = str(uuid.uuid4())
    monkeypatch.setattr(evidence_store, "get_job", lambda requested: {"id": requested, "status": "completed", "video_id": "a" * 32, "model": "sam-3.1"})
    monkeypatch.setattr(evidence_store, "get_result", lambda requested: fake_live_report())
    monkeypatch.setattr(evidence_store, "read_video", lambda requested: {
        "id": requested, "name": '<script>alert("x")</script>.mp4', "sha256": "f" * 64,
    })
    return job_id


def test_save_evidence_read_review_and_exports(monkeypatch, tmp_path):
    job_id = setup_mocks(monkeypatch, tmp_path)
    created = client.post("/api/v1/evidence-reports", json={"tracking_job_id": job_id, "rule": rule()})
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["source"]["video_sha256"] == "f" * 64
    assert data["source"]["tracking_sha256"]
    assert data["origin"] == "live_tracking_job"
    assert data["evaluation"]["event_count"] >= 1
    assert data["evaluation"]["review_count"] >= 1
    assert data["items"]
    assert data["observations"]
    report_id = data["id"]
    first_id = data["items"][0]["item_id"]
    assert client.get(f"/api/v1/evidence-reports/{report_id}").status_code == 200
    assert client.get("/api/v1/evidence-reports", params={"tracking_job_id": job_id}).json()["items"][0]["id"] == report_id
    assert client.post(f"/api/v1/evidence-reports/{report_id}/reviews", json={
        "item_id": "not-in-report", "decision": "confirmed", "note": "no"
    }).status_code == 422
    for decision in ["confirmed", "unresolved"]:
        recorded = client.post(f"/api/v1/evidence-reports/{report_id}/reviews", json={
            "item_id": first_id, "decision": decision, "reviewer": "Tester", "note": '<img src=x onerror=alert("x")>'
        })
        assert recorded.status_code == 201
    saved = client.get(f"/api/v1/evidence-reports/{report_id}").json()
    assert [x["decision"] for x in saved["reviews"]] == ["confirmed", "unresolved"]
    assert saved["items"] == data["items"]
    assert saved["evaluation"] == data["evaluation"]
    exported = client.get(f"/api/v1/evidence-reports/{report_id}/export.json")
    assert exported.status_code == 200
    assert exported.json()["reviews"][1]["decision"] == "unresolved"
    assert "attachment" in exported.headers["content-disposition"]
    printable = client.get(f"/api/v1/evidence-reports/{report_id}/export.html")
    assert printable.status_code == 200
    assert "<script>alert" not in printable.text
    assert "<img src=x" not in printable.text
    assert "&lt;script&gt;" in printable.text
    assert "<table>" in printable.text
    assert "default-src 'none'" in printable.headers["content-security-policy"]


def test_evidence_inputs_are_strict_and_missing_ids(monkeypatch, tmp_path):
    job_id = setup_mocks(monkeypatch, tmp_path)
    assert client.post("/api/v1/evidence-reports", json={"tracking_job_id": job_id, "rule": rule(), "unknown": 1}).status_code == 422
    assert client.get("/api/v1/evidence-reports/nope").status_code == 404
    assert client.get("/api/v1/evidence-reports/"+"a"*32).status_code == 404
    assert client.get("/api/v1/evidence-reports?tracking_job_id=invalid").status_code == 422
    monkeypatch.setattr(evidence_store, "get_job", lambda requested: {"id": requested, "status": "running", "video_id": "a"*32})
    assert client.post("/api/v1/evidence-reports",json={"tracking_job_id":job_id,"rule":rule()}).status_code == 409


def test_replay_only_mode_hides_live_and_persistent_routes():
    env = dict(os.environ, VISIONGUARD_REPLAY_ONLY="1")

    # Verify actual HTTP routing, not internal FastAPI/Starlette router shapes.
    # Recent releases may include _IncludedRouter without a .path attribute.
    code = """
from fastapi.testclient import TestClient
from backend.app.main import app

with TestClient(app) as client:
    response = client.get("/api/v1/replay/scenarios")
    assert response.status_code == 200, response.text

    blocked = [
        ("GET", "/api/v1/videos"),
        ("POST", "/api/v1/videos"),
        ("GET", "/api/v1/evidence-reports"),
        ("POST", "/api/v1/evidence-reports"),
        ("POST", "/api/v1/rules/interpret"),
        ("POST", "/api/v1/videos/test/tracking-jobs"),
    ]

    for method, path in blocked:
        response = client.request(method, path)
        assert response.status_code == 404, (method, path, response.status_code)

    status = client.get("/api/v1/meta/status")
    assert status.status_code == 200, status.text
    assert status.json()["key_present"] is False
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
