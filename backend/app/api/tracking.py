"""Local research/demo only. Triggers billable hosted Meta SAM 3.1 calls."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.tracking_jobs import (
    TrackingError,
    create_job,
    get_job,
    get_preview,
    get_result,
    list_jobs,
    process_job,
)

router = APIRouter(prefix="/api/v1", tags=["object tracking"])

class TrackingStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concepts: list[str] = Field(min_length=1, max_length=3)



def _bad(exc: TrackingError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/videos/{video_id}/tracking-jobs", status_code=202)
async def start_tracking(video_id: str, background_tasks: BackgroundTasks, request: TrackingStartRequest | None = None):
    try:
        job = create_job(video_id, request.concepts if request is not None else None)
    except TrackingError as exc:
        raise _bad(exc) from exc
    background_tasks.add_task(process_job, job["id"])
    return job


@router.get("/videos/{video_id}/tracking-jobs")
def video_tracking_jobs(video_id: str):
    try:
        return {"items": list_jobs(video_id)}
    except TrackingError as exc:
        raise _bad(exc) from exc


@router.get("/tracking-jobs/{job_id}")
def tracking_status(job_id: str):
    try:
        return get_job(job_id)
    except TrackingError as exc:
        raise _bad(exc) from exc


@router.get("/tracking-jobs/{job_id}/preview")
def tracking_preview(job_id: str):
    try:
        return get_preview(job_id)
    except TrackingError as exc:
        raise _bad(exc) from exc


@router.get("/tracking-jobs/{job_id}/result")
def tracking_result(job_id: str):
    try:
        return get_result(job_id)
    except TrackingError as exc:
        raise _bad(exc) from exc
