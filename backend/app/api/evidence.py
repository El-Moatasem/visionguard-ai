"""Local evidence and audit API. DO NOT publicly deploy without authentication."""
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from backend.app.services.evidence_store import (
    CreateEvidence, EvidenceError, ReviewInput, add_review, create_evidence,
    get_evidence, list_evidence, printable_html,
)
from backend.app.services.safety_engine import SafetyEvaluationError
from backend.app.services.tracking_jobs import TrackingError
from backend.app.services.video_store import VideoUploadError

router = APIRouter(prefix="/api/v1/evidence-reports", tags=["evidence and local review"])


def translate_error(error: Exception) -> HTTPException:
    if isinstance(error, EvidenceError):
        return HTTPException(error.status, str(error))
    if isinstance(error, TrackingError):
        return HTTPException(error.status_code, str(error))
    if isinstance(error, VideoUploadError):
        return HTTPException(error.status_code, str(error))
    if isinstance(error, SafetyEvaluationError):
        return HTTPException(422, str(error))
    return HTTPException(500, "Evidence report operation failed")


@router.post("", status_code=201)
def create(request: CreateEvidence):
    try:
        return create_evidence(request)
    except (EvidenceError, TrackingError, SafetyEvaluationError, VideoUploadError) as exc:
        raise translate_error(exc) from exc


@router.get("")
def index(tracking_job_id: str | None = Query(default=None)):
    try:
        return {"items": list_evidence(tracking_job_id)}
    except EvidenceError as exc:
        raise translate_error(exc) from exc


@router.get("/{report_id}")
def detail(report_id: str):
    try:
        return get_evidence(report_id)
    except EvidenceError as exc:
        raise translate_error(exc) from exc


@router.post("/{report_id}/reviews", status_code=201)
def review(report_id: str, request: ReviewInput):
    try:
        return add_review(report_id, request)
    except EvidenceError as exc:
        raise translate_error(exc) from exc


@router.get("/{report_id}/export.json")
def export_json(report_id: str):
    try:
        snapshot = get_evidence(report_id)
        data = json.dumps(snapshot, sort_keys=True, indent=2, allow_nan=False) + "\n"
        return Response(data, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="visionguard-evidence-{report_id}.json"',
                                 "Cache-Control": "no-store"})
    except EvidenceError as exc:
        raise translate_error(exc) from exc


@router.get("/{report_id}/export.html", response_class=HTMLResponse)
def export_html(report_id: str):
    try:
        snapshot = get_evidence(report_id)
        return HTMLResponse(printable_html(snapshot), headers={
            "Content-Disposition": f'attachment; filename="visionguard-evidence-{report_id}.html"',
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "Cache-Control": "no-store",
        })
    except EvidenceError as exc:
        raise translate_error(exc) from exc
