"""Local prototype endpoints: manual deterministic safety checks and explicit paid Muse drafting."""
from fastapi import APIRouter, HTTPException

from backend.app.services.tracking_jobs import TrackingError, get_result
from backend.app.services.safety_engine import SafetyEvaluationError, evaluate_tracking
from backend.app.services.safety_rules import EvaluateRequest, InterpretRequest
from backend.app.services.muse_rules import RuleInterpretationError, interpret_rule
from backend.app.config import api_configured, MUSE_MODEL

router = APIRouter(prefix="/api/v1", tags=["safety rules"])


@router.post("/tracking-jobs/{job_id}/evaluate")
def evaluate_job(job_id: str, request: EvaluateRequest):
    try:
        report = get_result(job_id)
        result = evaluate_tracking(report, request.rule)
        result["tracking_job_id"] = job_id
        return result
    except TrackingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except SafetyEvaluationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/rules/interpret")
async def interpret(request: InterpretRequest):
    if not api_configured():
        raise HTTPException(status_code=503, detail="MODEL_API_KEY is required for billable Muse drafting")
    try:
        draft = await interpret_rule(request.description)
        return {"draft": draft.model_dump(), "model": MUSE_MODEL, "requires_human_approval": True,
                "note": "Muse only drafts rule parameters. The deterministic evaluator never uses generated judgments."}
    except (RuleInterpretationError, RuntimeError):
        raise HTTPException(status_code=502, detail="Could not validate Muse's proposed rule; configure it manually")
    except Exception:
        # Do not expose API credentials, request contents or remote exception bodies.
        raise HTTPException(status_code=502, detail="Muse request failed; check server logs and Model API account")
