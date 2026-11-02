"""Local demo endpoints: video ingestion, listing, metadata and browser playback."""
from typing import Annotated
from pydantic import BaseModel

from fastapi import APIRouter, File, HTTPException, UploadFile
from backend.app.services.demo_catalog import get_scenario
from fastapi.responses import FileResponse

from backend.app.services.video_store import (
    VideoUploadError,
    get_video_file,
    list_videos,
    read_video,
    save_video,
)

from backend.app.services.library_deletion import delete_library

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", status_code=201)
async def upload_video(file: Annotated[UploadFile, File(description="Short MP4, MOV or WebM clip")], scenario_id: str | None = None):
    try:
        scenario = get_scenario(scenario_id) if scenario_id is not None else None
        if scenario_id is not None and scenario is None:
            raise HTTPException(422, "Unknown demo scenario")
        return await save_video(file, scenario=scenario)
    except VideoUploadError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("")
def videos():
    return {"items": list_videos()}


@router.get("/{video_id}")
def video_details(video_id: str):
    try:
        return read_video(video_id)
    except VideoUploadError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/{video_id}/file")
def stream_video(video_id: str):
    try:
        path, record = get_video_file(video_id)
        return FileResponse(
            path,
            media_type=record["media_type"],
            content_disposition_type="inline",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )
    except VideoUploadError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


class DeleteAllRequest(BaseModel):
    confirm: str


@router.post("/delete-all")
def delete_all_videos(payload: DeleteAllRequest):
    try:
        return delete_library(confirm_all=payload.confirm)
    except VideoUploadError as error:
        raise HTTPException(error.status_code, error.message) from error


@router.delete("/{video_id}")
def delete_single_video(video_id: str):
    try:
        return delete_library(video_id)
    except VideoUploadError as error:
        raise HTTPException(error.status_code, error.message) from error
