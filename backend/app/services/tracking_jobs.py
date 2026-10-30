"""Single-process, local-demo tracking jobs built on existing SAM CLI adapter.

No durable worker, authentication, hosted video storage, or real-time monitoring.
Concurrent paid SAM requests are intentionally blocked by a process-local gate.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from backend.app.config import SAM_MODEL, api_configured
from backend.app.services.sam import run_video
from backend.app.services.tracking_report import build_tracking_report
from backend.app.services.video_store import VideoUploadError, get_video_file, storage_dir

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_ACTIVE: set[str] = set()


class TrackingError(Exception):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.status_code = code


def tracking_dir() -> Path:
    return storage_dir().parent / "tracking"


def _paths(job_id: str) -> tuple[Path, Path]:
    try:
        uuid.UUID(job_id)
    except (ValueError, AttributeError) as exc:
        raise TrackingError("Invalid tracking job ID", 404) from exc
    root = tracking_dir()
    return root / f"{job_id}.json", root / f"{job_id}.result.json"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _read_record(job_id: str) -> dict[str, Any]:
    path, _ = _paths(job_id)
    if not path.is_file():
        raise TrackingError("Tracking job not found", 404)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TrackingError("Tracking metadata unavailable", 500) from exc


def get_job(job_id: str) -> dict[str, Any]:
    record = _read_record(job_id)
    with _LOCK:
        active = job_id in _ACTIVE
    # On process restart, old queued/running tasks cannot resume automatically.
    if record["status"] in {"queued", "running"} and not active:
        record["status"] = "interrupted"
        record["message"] = "Local process was interrupted; start a new job."
        _write(_paths(job_id)[0], record)
    return record


def list_jobs(video_id: str) -> list[dict[str, Any]]:
    # Validates that the video exists and belongs to the local store.
    try:
        get_video_file(video_id)
    except VideoUploadError as exc:
        raise TrackingError(exc.message, exc.status_code) from exc
    root = tracking_dir()
    if not root.is_dir():
        return []
    jobs = []
    for path in root.glob("*.json"):
        if path.name.endswith(".result.json"):
            continue
        try:
            record = get_job(path.stem)
            if record.get("video_id") == video_id:
                jobs.append(record)
        except (TrackingError, OSError, ValueError):
            continue
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)[:10]


def probe_video(path: Path) -> dict[str, Any]:
    """Optional ffprobe. Times are approximate; never a frame-perfect guarantee."""
    if not shutil.which("ffprobe"):
        return {"available": False, "warning": "ffprobe is not installed; video duration and FPS unavailable"}
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,codec_name,duration:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=15, check=True,
        )
        data = json.loads(proc.stdout)
        stream = next(iter(data.get("streams", [])), {})
        if not stream:
            return {"available": False, "warning": "No readable video stream found"}
        raw_fps = stream.get("avg_frame_rate", "0/0")
        rate = Fraction(raw_fps)
        fps = round(float(rate), 6) if rate > 0 else None
        d = stream.get("duration") or data.get("format", {}).get("duration")
        duration = float(d) if d is not None else None
        return {"available": True, "width": stream.get("width"), "height": stream.get("height"),
                "fps": fps, "duration_seconds": duration, "codec": stream.get("codec_name"),
                "warning": "Frame-to-time mapping assumes CFR; VFR and browser decoding may differ"}
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, ZeroDivisionError) as exc:
        logger.warning("ffprobe failure: %s", type(exc).__name__)
        return {"available": False, "warning": "Could not inspect input video"}


def create_job(video_id: str) -> dict[str, Any]:
    try:
        video_path, video = get_video_file(video_id)
    except VideoUploadError as exc:
        raise TrackingError(exc.message, exc.status_code) from exc
    if not api_configured():
        raise TrackingError("MODEL_API_KEY not configured on the backend", 503)
    if not video["sam_compatible_container"]:
        raise TrackingError("SAM 3.1 accepts MP4/MOV, not WebM. Convert this clip locally first.", 415)
    probe = probe_video(video_path)
    if probe.get("available") and probe.get("codec") not in {"h264", "hevc", "mpeg4"}:
        raise TrackingError("Unsupported video codec for SAM 3.1; use H.264, H.265, or MPEG-4.", 415)
    if probe.get("duration_seconds") is not None and probe["duration_seconds"] > 30:
        raise TrackingError("Use a clip up to 30 seconds for this demo to bound API usage.", 413)
    job_id = str(uuid.uuid4())
    with _LOCK:
        if _ACTIVE:
            raise TrackingError("Another SAM job is active. Retry when it finishes.", 409)
        _ACTIVE.add(job_id)
    record = {"id": job_id, "video_id": video_id, "status": "queued",
              "created_at": datetime.now(timezone.utc).isoformat(), "model": SAM_MODEL,
              "concepts": ["person", "forklift"], "media_probe": probe,
              "message": "Waiting for SAM 3.1 processing; this request uses Meta credits.",
              "result_url": f"/api/v1/tracking-jobs/{job_id}/result"}
    try:
        _write(_paths(job_id)[0], record)
    except Exception:
        with _LOCK:
            _ACTIVE.discard(job_id)
        raise
    return record


async def process_job(job_id: str) -> None:
    """Run after FastAPI response. Not a robust distributed job queue."""
    try:
        record = _read_record(job_id)
        video_path, _ = get_video_file(record["video_id"])
        record["status"] = "running"
        record["message"] = "Sending authorized clip to Meta SAM 3.1."
        _write(_paths(job_id)[0], record)
        summaries = await run_video(video_path, record["concepts"], tracking_dir() / job_id / "raw")
        report = build_tracking_report(summaries, record["media_probe"])
        report["job_id"] = job_id
        report["video_id"] = record["video_id"]
        _write(_paths(job_id)[1], report)
        record["status"] = "completed"
        record["message"] = "SAM analysis completed; review tracks and occlusion gaps. No danger classification yet."
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        record["track_count"] = report["track_count"]
        record["gap_count"] = report["gap_count"]
        _write(_paths(job_id)[0], record)
    except Exception:
        logger.exception("SAM job %s failed", job_id)
        try:
            record = _read_record(job_id)
            record["status"] = "failed"
            # Do not return raw remote exception details or request data to the browser.
            record["message"] = "Tracking failed. Check server logs and Meta account access; no result was generated."
            _write(_paths(job_id)[0], record)
        except Exception:
            logger.exception("Could not persist failed job state")
    finally:
        with _LOCK:
            _ACTIVE.discard(job_id)


def get_result(job_id: str) -> dict[str, Any]:
    record = get_job(job_id)
    if record["status"] != "completed":
        raise TrackingError("Tracking result is not ready", 409)
    _, result = _paths(job_id)
    if not result.is_file():
        raise TrackingError("Tracking result is missing", 500)
    return json.loads(result.read_text(encoding="utf-8"))
