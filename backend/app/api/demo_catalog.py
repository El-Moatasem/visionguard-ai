"""Read-only scenario catalog; listing has no billable side effects."""
from fastapi import APIRouter, HTTPException
from backend.app.services.demo_catalog import get_scenario, list_scenarios

router = APIRouter(prefix="/api/v1/demo", tags=["demo catalog"])

@router.get("/scenarios")
def scenarios():
    return {"items": list_scenarios()}

@router.get("/scenarios/{scenario_id}")
def scenario(scenario_id: str):
    result = get_scenario(scenario_id)
    if result is None:
        raise HTTPException(404, "Unknown demo scenario")
    return result
