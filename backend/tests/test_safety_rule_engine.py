"""Offline checks for observed vs provisional safety events; no Meta credits."""
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


def spec(rule_type="person_and_forklift_in_zone", duration=.2, max_gap=2, zone=None):
    return RuleSpec(name="Forklift operating zone", rule_type=rule_type,
                    zone=zone or NormalizedZone(name="Aisle", x_min=.2, y_min=.2, x_max=.8, y_max=.8),
                    min_duration_seconds=duration, max_observation_gap_frames=max_gap)


def obs(concept, actor, frame, cx=.5, cy=.5, fragment=0, height=10):
    return {"concept": concept, "track_id": f"{concept}:{actor}",
            "fragment_id": f"{concept}:{actor}#{fragment}", "frame": frame,
            "box": {"left": cx * 100 - 5, "top": cy * 100 - height / 2,
                    "right": cx * 100 + 5, "bottom": cy * 100 + height / 2}}


def tracking(boxes=None, gaps=None, probe=None, media=None):
    return {"schema_version": 1,
            "media_probe": probe if probe is not None else {"width": 100, "height": 100, "fps": 10},
            "media_metadata": media or {}, "boxes": boxes or [], "gaps": gaps or []}


def test_contiguous_copresence_same_pair_is_observed_event():
    boxes = [obs("person", "p", f) for f in (1, 2, 3, 6)] + [obs("forklift", "f", f) for f in (2, 3, 4, 6)]
    outcome = evaluate_tracking(tracking(boxes), spec())
    assert outcome["outcome"] == "potential_hazard"
    assert outcome["event_count"] == 1
    assert outcome["events"][0]["start_frame"] == 2
    assert outcome["events"][0]["end_frame"] == 3
    assert outcome["events"][0]["actor_fragments"] == ["forklift:f#0", "person:p#0"]
    assert outcome["events"][0]["identity_continuity"] == "observed_in_contiguous_frames"


def test_person_zone_rule_no_forklift_required():
    report = tracking([obs("person", "a", 3), obs("person", "a", 4)])
    assert evaluate_tracking(report, spec("person_in_zone"))["event_count"] == 1
    assert evaluate_tracking(report, spec())["event_count"] == 0


def test_person_outside_zone_never_triggers():
    boxes = [obs("person", "p", f, cx=.05) for f in (0, 1, 2)] + [obs("forklift", "f", f) for f in (0, 1, 2)]
    result = evaluate_tracking(tracking(boxes), spec())
    assert result["outcome"] == "no_rule_match_observed"
    assert result["event_count"] == 0


def test_fragment_change_yields_review_not_verified_hazard():
    boxes = [obs("person", "p", 1), obs("person", "p", 2, fragment=1)]
    result = evaluate_tracking(tracking(boxes), spec("person_in_zone"))
    assert result["event_count"] == 0
    assert result["review_items"][0]["identity_continuity"] == "unverified"


def test_short_gap_is_review_candidate_not_interpolated():
    data = tracking([obs("person", "p", 1), obs("person", "p", 3, fragment=1)],
                    [{"track_id": "person:p", "after_frame": 1, "before_frame": 3, "missing_frames": 1}])
    result = evaluate_tracking(data, spec("person_in_zone"))
    assert result["outcome"] == "needs_review"
    assert result["event_count"] == 0
    assert result["review_count"] >= 1
    candidate = next(x for x in result["review_items"] if "event_id" in x)
    assert candidate["observed_frames"] == 2
    assert candidate["contains_missing_observations"] is True
    assert candidate["observed_coverage_ratio"] == pytest.approx(2 / 3, abs=.0001)


def test_configurable_gap_tolerance_wont_invent_hazard():
    boxes = [obs("person", "p", f, fragment=i) for i, f in enumerate((0, 3, 6, 9))]
    report = tracking(boxes)
    permissive = evaluate_tracking(report, spec("person_in_zone", duration=.5, max_gap=2))
    strict = evaluate_tracking(report, spec("person_in_zone", duration=.5, max_gap=0))
    assert permissive["event_count"] == strict["event_count"] == 0
    assert any("event_id" in x for x in permissive["review_items"])
    assert strict["review_items"] == []


def test_distant_tracking_gap_not_global_uncertainty():
    boxes = [obs("person", "p", f) for f in (1, 2, 3)]
    boxes += [obs("forklift", "remote", 1, cx=.95), obs("forklift", "remote", 4, cx=.95)]
    result = evaluate_tracking(tracking(boxes, [{"track_id": "forklift:remote", "after_frame": 1, "before_frame": 4,
                                                  "missing_frames": 2}]), spec("person_in_zone"))
    assert result["event_count"] == 1
    assert result["uncertainty_count"] == 0
    assert result["has_unresolved_review_items"] is False


def test_hazard_and_relevant_gap_reported_together():
    boxes = [obs("person", "p", f) for f in (1, 2, 3)] + [obs("person", "q", 1), obs("person", "q", 5, fragment=1)]
    gaps = [{"track_id": "person:q", "after_frame": 1, "before_frame": 5, "missing_frames": 3}]
    out = evaluate_tracking(tracking(boxes, gaps), spec("person_in_zone"))
    assert out["event_count"] == 1
    assert out["uncertainty_count"] == 1
    assert out["has_unresolved_review_items"] is True
    assert out["outcome"] == "potential_hazard"


def test_person_foot_point_for_floor_zone_not_box_center():
    ground_zone = NormalizedZone(name="Floor", x_min=.3, x_max=.7, y_min=.7, y_max=.95)
    boxes = [obs("person", "p", f, cx=.5, cy=.55, height=48) for f in (1, 2)]
    result = evaluate_tracking(tracking(boxes), spec("person_in_zone", zone=ground_zone))
    assert result["event_count"] == 1  # center y=.55 outside, bottom=.79 inside


def test_seconds_threshold_varies_with_fps():
    boxes = [obs("person", "p", f) for f in (0, 1, 2)]
    assert evaluate_tracking(tracking(boxes, probe={"width": 100, "height": 100, "fps": 10}),
                             spec("person_in_zone", duration=.25))["event_count"] == 1
    assert evaluate_tracking(tracking(boxes, probe={"width": 100, "height": 100, "fps": 30}),
                             spec("person_in_zone", duration=.25))["event_count"] == 0


def test_actors_not_combined_to_meet_duration():
    report = tracking([obs("person", "p1", 1), obs("person", "p2", 2)])
    assert evaluate_tracking(report, spec("person_in_zone"))["event_count"] == 0


def test_missing_dimensions_fps_and_invalid_schema_rejected():
    with pytest.raises(SafetyEvaluationError):
        evaluate_tracking(tracking([obs("person", "p", 1)], probe={"fps": 10}), spec())
    with pytest.raises(SafetyEvaluationError):
        evaluate_tracking(tracking(probe={"width": 100, "height": 100}), spec())
    with pytest.raises(SafetyEvaluationError):
        evaluate_tracking({**tracking(), "schema_version": 2}, spec())


def test_sam_metadata_fallback_dimensions_and_fps():
    boxes = [obs("person", "p", f) for f in (1, 2)]
    result = evaluate_tracking(tracking(boxes, probe={"available": False}, media={"width": 100, "height": 100, "fps": 10}),
                               spec("person_in_zone"))
    assert result["event_count"] == 1


def test_zone_and_rule_reject_invalid_input():
    with pytest.raises(ValidationError):
        NormalizedZone(x_min=.6, x_max=.4, y_min=0, y_max=1)
    with pytest.raises(ValidationError):
        NormalizedZone(x_min=-.1, x_max=.4, y_min=0, y_max=1)
    for kw in ({"min_duration_seconds": 0}, {"min_duration_seconds": float("nan")},
               {"max_observation_gap_frames": 31}, {"min_consecutive_frames": 3}):
        with pytest.raises(ValidationError):
            RuleSpec(**{**spec().model_dump(), **kw})


def test_api_evaluates_saved_tracking_job(monkeypatch):
    monkeypatch.setattr(safety_api, "get_result", lambda _: tracking([obs("person", "p", 1), obs("person", "p", 2)]))
    r = client.post("/api/v1/tracking-jobs/fake-job/evaluate", json={"rule": spec("person_in_zone").model_dump()})
    assert r.status_code == 200
    assert r.json()["event_count"] == 1
    assert r.json()["tracking_job_id"] == "fake-job"


def test_api_rejects_unsupported_rules(monkeypatch):
    monkeypatch.setattr(safety_api, "get_result", lambda _: tracking())
    for invalid in ({"rule_type": "unsupported"}, {"arbitrary_code": "eval(1)"}):
        r = client.post("/api/v1/tracking-jobs/x/evaluate", json={"rule": {**spec().model_dump(), **invalid}})
        assert r.status_code == 422


def test_interpret_requires_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert client.post("/api/v1/rules/interpret", json={"description": "Alert when worker enters forklift zone"}).status_code == 503


def test_interpret_uses_validated_draft_and_configured_model(monkeypatch):
    async def fake(description):
        assert "forklift" in description
        return RuleDraft(name="Shared zone", rule_type="person_and_forklift_in_zone", min_duration_seconds=.5, rationale="Both observed")
    monkeypatch.setenv("MODEL_API_KEY", "test-not-real")
    monkeypatch.setattr(safety_api, "interpret_rule", fake)
    r = client.post("/api/v1/rules/interpret", json={"description": "Flag workers and forklifts in same zone"})
    assert r.status_code == 200
    assert r.json()["draft"]["rule_type"] == "person_and_forklift_in_zone"
    assert r.json()["model"] == safety_api.MUSE_MODEL
    assert r.json()["requires_human_approval"] is True


@pytest.mark.asyncio
async def test_muse_supported_and_unsupported_drafts(monkeypatch):
    class Completion:
        def __init__(self): self.kind = "person_and_forklift_in_zone"
        async def create(self, **kwargs):
            assert "unsupported" in kwargs["response_format"]["json_schema"]["schema"]["properties"]["rule_type"]["enum"]
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps({
                "name": "Rule proposal", "rule_type": self.kind, "min_duration_seconds": .5,
                "rationale": "Unsupported measurement" if self.kind == "unsupported" else "Co-presence"})))])
    completion = Completion()
    class FakeClient:
        async def __aenter__(self):return self
        async def __aexit__(self, *args): pass
        chat = SimpleNamespace(completions=completion)
    import sys
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=lambda **kwargs: FakeClient()))
    monkeypatch.setenv("MODEL_API_KEY", "test-not-real")
    assert (await muse_rules.interpret_rule("Check forklift and worker in zone")).rule_type == "person_and_forklift_in_zone"
    completion.kind = "unsupported"
    assert (await muse_rules.interpret_rule("Detect speeding forklifts")).rule_type == "unsupported"


def test_reproducible_synthetic_benchmark():
    from pathlib import Path
    from backend.scripts.evaluate_fixture import run
    assert run(Path("benchmarks/fixtures/safety-rule-synthetic.json"))["passed"] is True


def test_saved_sam_stride_inspector(tmp_path):
    from backend.scripts.inspect_sam_frames import inspect
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"concept": "person", "boxes": [
        {"object_id": 1, "frame": f} for f in (0, 2, 4, 6)]}))
    result = inspect(path)
    assert result["tracks"][0]["frame_step_counts"] == {2: 3}
    assert result["tracks"][0]["any_missing_frame_indices"] is True
