"""Offline acceptance tests for deterministic safety evaluation and optional Muse drafting."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.services.safety_engine import SafetyEvaluationError, evaluate_tracking
from backend.app.services.safety_rules import NormalizedZone, RuleDraft, RuleSpec
from backend.app.services import muse_rules
from backend.app.api import safety as safety_api

client = TestClient(app)


def spec(rule_type="person_and_forklift_in_zone", minimum=2):
    return RuleSpec(name="Forklift operating zone", rule_type=rule_type,
                    zone=NormalizedZone(name="Aisle", x_min=.2, y_min=.2, x_max=.8, y_max=.8),
                    min_consecutive_frames=minimum)


def obs(concept, actor, frame, center_x=.5, center_y=.5):
    return {"concept": concept, "track_id": f"{concept}:{actor}",
            "fragment_id": f"{concept}:{actor}#0", "frame": frame,
            "box": {"left": center_x * 100 - 5, "top": center_y * 100 - 5,
                    "right": center_x * 100 + 5, "bottom": center_y * 100 + 5}}


def tracking(boxes=None, gaps=None, probe=None):
    return {"schema_version": 1, "media_probe": probe if probe is not None else {"width": 100, "height": 100, "fps": 10},
            "boxes": boxes or [], "gaps": gaps or []}


def test_copresence_qualifies_only_consecutive_frames_same_pair():
    boxes = [obs("person", "p", f) for f in (1, 2, 3, 6)] + [obs("forklift", "f", f) for f in (2, 3, 4, 6)]
    outcome = evaluate_tracking(tracking(boxes), spec())
    assert outcome["outcome"] == "potential_hazard"
    assert outcome["event_count"] == 1
    assert outcome["events"][0]["start_frame"] == 2
    assert outcome["events"][0]["end_frame"] == 3
    assert outcome["events"][0]["actor_fragments"] == ["person:p#0", "forklift:f#0"]
    assert outcome["events"][0]["start_seconds_approx"] == .2


def test_person_zone_rule_does_not_need_forklift():
    report = tracking([obs("person", "a", 3), obs("person", "a", 4)])
    assert evaluate_tracking(report, spec("person_in_zone"))["event_count"] == 1
    assert evaluate_tracking(report, spec())["event_count"] == 0


def test_person_outside_zone_never_triggers():
    boxes = [obs("person", "p", f, center_x=.05) for f in (0,1,2)] + [obs("forklift", "f", f) for f in (0,1,2)]
    result = evaluate_tracking(tracking(boxes), spec())
    assert result["outcome"] == "no_rule_match_observed"
    assert result["event_count"] == 0


def test_track_fragment_change_does_not_join_alerts():
    boxes = [obs("person", "p", 1), obs("person", "p", 2)]
    boxes[1]["fragment_id"] = "person:p#1"
    assert evaluate_tracking(tracking(boxes), spec("person_in_zone", 2))["event_count"] == 0


def test_missing_frame_no_interpolation_and_review():
    report = tracking([obs("person", "p", 1), obs("person", "p", 3)],
                      [{"track_id": "person:p", "after_frame": 1, "before_frame": 3, "missing_frames": 1}])
    result = evaluate_tracking(report, spec("person_in_zone", 2))
    assert result["outcome"] == "needs_review"
    assert result["uncertainty_count"] == 1
    assert result["events"] == []


def test_multiple_pedestrians_cannot_be_combined_to_meet_threshold():
    report = tracking([obs("person", "p1", 1), obs("person", "p2", 2)])
    assert evaluate_tracking(report, spec("person_in_zone", 2))["event_count"] == 0


def test_missing_video_dimensions_or_wrong_schema_rejected():
    with pytest.raises(SafetyEvaluationError):
        evaluate_tracking(tracking([obs("person", "p", 1)], probe={}), spec())
    with pytest.raises(SafetyEvaluationError):
        evaluate_tracking({**tracking(), "schema_version": 2}, spec())


def test_zone_validation_refuses_zero_area_and_out_of_range():
    with pytest.raises(ValidationError):
        NormalizedZone(x_min=.6, x_max=.4, y_min=0, y_max=1)
    with pytest.raises(ValidationError):
        NormalizedZone(x_min=-.1, x_max=.4, y_min=0, y_max=1)
    with pytest.raises(ValidationError):
        RuleSpec(name="bad", rule_type="person_in_zone", zone=spec().zone, min_consecutive_frames=0)


def test_api_evaluates_saved_tracking_job(monkeypatch):
    monkeypatch.setattr(safety_api, "get_result", lambda _: tracking([obs("person", "p", 1), obs("person", "p", 2)]))
    r = client.post("/api/v1/tracking-jobs/fake-job/evaluate", json={"rule": spec("person_in_zone").model_dump()})
    assert r.status_code == 200
    assert r.json()["event_count"] == 1
    assert r.json()["tracking_job_id"] == "fake-job"


def test_api_rejects_unsupported_and_invalid_rules(monkeypatch):
    monkeypatch.setattr(safety_api, "get_result", lambda _: tracking())
    r = client.post("/api/v1/tracking-jobs/x/evaluate", json={"rule": {**spec().model_dump(), "rule_type": "collision_predictor"}})
    assert r.status_code == 422
    r = client.post("/api/v1/tracking-jobs/x/evaluate", json={"rule": {**spec().model_dump(), "arbitrary_code": "eval(1)"}})
    assert r.status_code == 422


def test_interpret_requires_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert client.post("/api/v1/rules/interpret", json={"description": "Alert when a worker enters the forklift zone"}).status_code == 503


def test_interpret_endpoint_uses_validated_draft_not_executable_rule(monkeypatch):
    async def fake(description):
        assert "forklift" in description
        return RuleDraft(name="Shared zone", rule_type="person_and_forklift_in_zone", min_consecutive_frames=3, rationale="Both observed")
    monkeypatch.setenv("MODEL_API_KEY", "test-not-real")
    monkeypatch.setattr(safety_api, "interpret_rule", fake)
    r=client.post("/api/v1/rules/interpret",json={"description":"Alert when workers and forklifts enter the same area"})
    assert r.status_code == 200
    assert r.json()["draft"]["rule_type"] == "person_and_forklift_in_zone"
    assert r.json()["requires_human_approval"] is True
    assert "zone" not in r.json()["draft"]


@pytest.mark.asyncio
async def test_muse_adapter_parses_strict_json(monkeypatch):
    class FakeCompletions:
        async def create(self, **kwargs):
            assert kwargs["response_format"]["type"] == "json_schema"
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",message=SimpleNamespace(content=json.dumps({
                "name":"Forklift zone", "rule_type":"person_and_forklift_in_zone", "min_consecutive_frames":3,"rationale":"Review co-presence"})))])
    class FakeClient:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        chat=SimpleNamespace(completions=FakeCompletions())
    import sys
    monkeypatch.setitem(sys.modules,"openai", SimpleNamespace(AsyncOpenAI=lambda **kwargs:FakeClient()))
    monkeypatch.setenv("MODEL_API_KEY","test-not-real")
    draft=await muse_rules.interpret_rule("Check forklift and person in same zone")
    assert draft.rule_type=="person_and_forklift_in_zone"


@pytest.mark.asyncio
async def test_invalid_model_rule_fails_closed(monkeypatch):
    class FakeCompletions:
        async def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",message=SimpleNamespace(content=json.dumps({
                "name":"Danger", "rule_type":"teleportation", "min_consecutive_frames":3,"rationale":""})))])
    class FakeClient:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        chat=SimpleNamespace(completions=FakeCompletions())
    import sys
    monkeypatch.setitem(sys.modules,"openai", SimpleNamespace(AsyncOpenAI=lambda **kwargs:FakeClient()))
    monkeypatch.setenv("MODEL_API_KEY","test-not-real")
    with pytest.raises(muse_rules.RuleInterpretationError):
        await muse_rules.interpret_rule("Check forklift and person in same zone")


def test_reproducible_synthetic_benchmark():
    from pathlib import Path
    from backend.scripts.evaluate_fixture import run
    result=run(Path("benchmarks/fixtures/safety-rule-synthetic.json"))
    assert result["passed"] is True
