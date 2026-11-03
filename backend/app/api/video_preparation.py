"""Local-only, no-Meta video preparation endpoint."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.video_preparation import VideoPreparationError, prepare_for_sam

router = APIRouter(prefix="/api/v1/videos", tags=["video preparation"])


class PrepareVideoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_seconds: float = Field(default=0, ge=0, le=3600, allow_inf_nan=False)
    # Broad schema bound; the configured application policy is checked in service.
    duration_seconds: float = Field(default=20, gt=0, le=600, allow_inf_nan=False)


@router.post("/{video_id}/prepare-for-sam", status_code=201)
async def prepare(video_id: str, request: PrepareVideoRequest):
    try:
        return await prepare_for_sam(video_id, request.start_seconds, request.duration_seconds)
    except VideoPreparationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
