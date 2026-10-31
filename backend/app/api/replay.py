"""No-key, read-only synthetic replay of the real deterministic safety engine."""
from fastapi import APIRouter, HTTPException

from backend.app.services.replay_fixtures import ReplayError, get_scenario, list_scenarios
from backend.app.services.safety_engine import SafetyEvaluationError, evaluate_tracking
from backend.app.services.safety_rules import EvaluateRequest

router = APIRouter(prefix="/api/v1/replay", tags=["synthetic benchmark replay"])


@router.get("/scenarios")
def scenarios():
    return {"items": list_scenarios(), "provenance": "synthetic_fixture", "live_inference": False}


@router.get("/scenarios/{scenario_id}")
def scenario(scenario_id: str):
    try:
        return get_scenario(scenario_id)
    except ReplayError:
        raise HTTPException(404, "Unknown synthetic scenario") from None


@router.post("/scenarios/{scenario_id}/evaluate")
def evaluate(scenario_id: str, request: EvaluateRequest):
    try:
        data = get_scenario(scenario_id)
        output = evaluate_tracking(data["tracking_report"], request.rule)
        return {**output, "provenance": "synthetic_fixture", "live_inference": False,
                "note": "Real deterministic rule evaluator; synthetic hand-authored tracking observations. Not a SAM accuracy test."}
    except ReplayError:
        raise HTTPException(404, "Unknown synthetic scenario") from None
    except SafetyEvaluationError as exc:
        raise HTTPException(422, str(exc)) from exc
