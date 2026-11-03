"""Single-process, local-demo tracking jobs built on existing SAM CLI adapter.

No durable worker, authentication, hosted video storage, or real-time monitoring.
Concurrent paid SAM requests are intentionally blocked by a process-local gate.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
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
from backend.app.services.sceneops_concepts import normalize_concept
from backend.app.services import db_store

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_ACTIVE: set[str] = set()
# Job cancellation is explicitly process-local. Do not deploy without authentication.
_CANCEL_REQUESTED: set[str] = set()
_WORKERS: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Task[Any]]] = {}


def _cancel_requested(job_id: str) -> bool:
    with _LOCK:
        return job_id in _CANCEL_REQUESTED


def _ensure_not_cancelled(job_id: str) -> None:
    if _cancel_requested(job_id):
        raise asyncio.CancelledError()


def _finalize_cancel(job_id: str) -> None:
    record = _read_record(job_id)
    # A cancellation never creates a completed evidence/tracking result.
    _paths(job_id)[1].unlink(missing_ok=True)
    record.update(status="cancelled", phase="cancelled", cancel_requested=True,
                  message="Local tracking job cancelled. Remote requests already sent to Meta may still be billed.",
                  cancelled_at=datetime.now(timezone.utc).isoformat())
    _write(_paths(job_id)[0], record)



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


def _preview_path(job_id: str) -> Path:
    status, _ = _paths(job_id)
    return status.with_name(f"{job_id}.preview.json")


def _write(path: Path, data: dict[str, Any]) -> None:
    if db_store.enabled():
        if path.name.endswith(".result.json"):
            db_store.put_result(data)
        elif path.name.endswith(".json") and not path.name.endswith(".preview.json"):
            db_store.put_job(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _read_record(job_id: str) -> dict[str, Any]:
    path, _ = _paths(job_id)
    if db_store.enabled():
        record = db_store.get_job(job_id)
        if record is None:
            raise TrackingError("Tracking job not found", 404)
        return record
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
    if record["status"] in {"queued", "running", "cancelling"} and not active:
        if record.get("cancel_requested"):
            record["status"] = "cancelled"
            record["phase"] = "cancelled"
            record["message"] = "Cancellation requested; worker is no longer running."
        else:
            record["status"] = "interrupted"
            record["message"] = "Local process was interrupted; start a new job."
        _write(_paths(job_id)[0], record)
    return record


def active_jobs() -> list[dict[str, Any]]:
    """Jobs active in this one FastAPI process, across ALL uploaded videos."""
    with _LOCK:
        ids = sorted(_ACTIVE)
    jobs = []
    for job_id in ids:
        try:
            jobs.append(_read_record(job_id))
        except TrackingError:
            continue
    return sorted(jobs, key=lambda item: item.get("created_at", ""), reverse=True)


def cancel_job(job_id: str) -> dict[str, Any]:
    """Request cooperative cancellation; do not report success until worker exits.

    Closing the local coroutine/stream doesn't guarantee Meta has stopped a
    request or refunded it. The active slot remains occupied until cleanup.
    """
    record = get_job(job_id)
    if record["status"] in {"completed", "failed", "cancelled", "interrupted"}:
        return record
    if record["status"] not in {"queued", "running", "cancelling"}:
        raise TrackingError("Job is not cancellable", 409)
    with _LOCK:
        if job_id not in _ACTIVE:
            raise TrackingError("Job is no longer active", 409)
        _CANCEL_REQUESTED.add(job_id)
        worker = _WORKERS.get(job_id)
        # Save cancelling status while holding the lock so completion cannot
        # win a race after cancellation has already been accepted.
        record = _read_record(job_id)
        if record["status"] not in {"completed", "failed", "cancelled"}:
            record.update(status="cancelling", phase="cancelling", cancel_requested=True,
                          message="Cancellation requested; stopping local work. Meta may still bill in-flight inference.")
            _write(_paths(job_id)[0], record)
    if worker is not None:
        loop, task = worker
        try:
            loop.call_soon_threadsafe(task.cancel)
        except RuntimeError:
            pass  # Loop exited; get_job() will reconcile final status.
    return record


def cancel_all_jobs() -> list[dict[str, Any]]:
    """Request cancellation for ALL active jobs in this backend process."""
    with _LOCK:
        ids = sorted(_ACTIVE)
    results = []
    for job_id in ids:
        try:
            results.append(cancel_job(job_id))
        except TrackingError as exc:
            if exc.status_code != 404:
                raise
    return results


def list_jobs(video_id: str) -> list[dict[str, Any]]:
    # Validates that the video exists and belongs to the local store.
    try:
        get_video_file(video_id)
    except VideoUploadError as exc:
        raise TrackingError(exc.message, exc.status_code) from exc
    if db_store.enabled():
        return [get_job(item["id"]) for item in db_store.list_jobs(video_id, 10)]
    root = tracking_dir()
    if not root.is_dir():
        return []
    jobs = []
    for path in root.glob("*.json"):
        if path.name.endswith((".result.json", ".preview.json")):
            continue
        try:
            record = get_job(path.stem)
            if record.get("video_id") == video_id:
                jobs.append(record)
        except (TrackingError, OSError, ValueError):
            continue
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)[:10]


def _ffprobe_executable() -> str | None:
    """Locate ffprobe even if FastAPI starts without a macOS package-manager PATH.

    FFPROBE_BIN is an optional explicit override. A resolved program is still
    required; missing or unreadable media must never bypass paid-job preflight.
    """
    explicit = os.getenv("FFPROBE_BIN", "").strip()
    candidates = ([explicit] if explicit else []) + [
        "/opt/local/bin/ffprobe",       # MacPorts
        "/opt/homebrew/bin/ffprobe",    # Homebrew on Apple Silicon
        "/usr/local/bin/ffprobe",      # Homebrew on Intel
    ]
    discovered = shutil.which("ffprobe")
    if discovered:
        candidates.append(discovered)
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def probe_video(path: Path) -> dict[str, Any]:
    """Optional ffprobe. Times are approximate; never a frame-perfect guarantee."""
    executable = _ffprobe_executable()
    if executable is None:
        return {"available": False, "warning": "ffprobe is not installed; video duration and FPS unavailable"}
    try:
        proc = subprocess.run(
            [executable, "-v", "error", "-select_streams", "v:0",
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


def sam_max_active_jobs() -> int:
    # Process-local limit only; not a distributed lock or durable queue.
    raw = os.getenv("SAM_MAX_ACTIVE_JOBS", "1").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise TrackingError("SAM_MAX_ACTIVE_JOBS must be 1 or 2", 503) from exc
    if value not in (1, 2):
        raise TrackingError("SAM_MAX_ACTIVE_JOBS must be 1 or 2", 503)
    return value


def create_job(video_id: str, requested_concepts: list[str] | None = None) -> dict[str, Any]:
    try:
        video_path, video = get_video_file(video_id)
    except VideoUploadError as exc:
        raise TrackingError(exc.message, exc.status_code) from exc
    if not api_configured():
        raise TrackingError("MODEL_API_KEY not configured on the backend", 503)
    if not video["sam_compatible_container"]:
        raise TrackingError("SAM 3.1 accepts MP4/MOV, not WebM. Convert this clip locally first.", 415)
    # Fail before creating a paid job when the SAM adapter would reject it.
    from backend.app.services.sam import MAX_BYTES as SAM_MAX_BYTES, MAX_VIDEO_SECONDS, MAX_VIDEO_FRAMES
    if video_path.stat().st_size > SAM_MAX_BYTES:
        raise TrackingError(
            f"Video is too large for SAM analysis ({SAM_MAX_BYTES // (1024 * 1024)} MiB). "
            "Compress it for analysis; the upload/storage limit is separate.", 413)
    probe = probe_video(video_path)
    # Without verified FPS/dimensions, boxes cannot be aligned with playback or
    # assessed using seconds-based rules. Avoid spending credits for unusable output.
    if not probe.get("available") or not all(
        isinstance(probe.get(key), (int, float))
        and not isinstance(probe.get(key), bool)
        and math.isfinite(probe[key]) and probe[key] > 0
        for key in ("width", "height", "fps")
    ):
        raise TrackingError(
            "Video preflight could not read positive FPS and dimensions. "
            f"FFprobe diagnostic: {probe.get('warning', 'missing required metadata')}. "
            "Set FFPROBE_BIN to an installed ffprobe executable, restart FastAPI, "
            "and verify that the video has a readable frame rate and dimensions.", 503)
    short_side, long_side = sorted((probe["width"], probe["height"]))
    if long_side > 1920 or short_side > 1080 or probe["fps"] > 30:
        raise TrackingError("Use a clip at or below 1080p/30fps for this demo. "
                            "Prepare the uploaded clip first (e.g. --height 480 --fps 12).", 413)
    if probe.get("codec") not in {"h264", "hevc", "mpeg4"}:
        raise TrackingError("Unsupported video codec for SAM 3.1; use H.264, H.265, or MPEG-4.", 415)
    duration = probe.get("duration_seconds")
    if (not isinstance(duration, (float, int)) or isinstance(duration, bool)
            or not math.isfinite(duration) or duration <= 0):
        raise TrackingError("Video duration could not be verified; prepare a readable MP4 before paid SAM inference.", 422)
    if duration > MAX_VIDEO_SECONDS + 0.05:
        raise TrackingError(
            f"This app allows at most {MAX_VIDEO_SECONDS:g} seconds per SAM job. "
            "Prepare a shorter segment or configure SAM_MAX_DURATION_SECONDS.", 413)
    if duration * probe["fps"] > MAX_VIDEO_FRAMES + 1:
        raise TrackingError(
            f"This clip exceeds Meta SAM 3.1's {MAX_VIDEO_FRAMES:,}-frame ceiling. "
            "Prepare a shorter or lower-FPS clip.", 413)
    # Use one concept for the first short live test, then enable both for the demo.
    # An explicit environment override is useful for controlled debugging.
    # Otherwise, the prepared demo's concepts select the model prompts.
    override = os.getenv("SAM_DEMO_CONCEPTS", "").strip()
    requested = requested_concepts if requested_concepts is not None else (override.split(",") if override else video.get("suggested_concepts") or ["person", "forklift"])
    try:
        concepts = [normalize_concept(str(name)) for name in requested]
    except ValueError as exc:
        raise TrackingError("Unsupported concept in SAM_DEMO_CONCEPTS or demo metadata", 422) from exc
    if not 1 <= len(concepts) <= 3 or len(set(concepts)) != len(concepts):
        raise TrackingError("Select 1–3 unique supported SAM concepts", 422)
    job_id = str(uuid.uuid4())
    max_active = sam_max_active_jobs()
    with _LOCK:
        if len(_ACTIVE) >= max_active:
            raise TrackingError(
                f"Maximum concurrent SAM jobs reached ({max_active}). Retry when a slot is free.", 409
            )
        # Revalidate under the same gate used by local video deletion.
        try:
            get_video_file(video_id)
        except VideoUploadError as exc:
            raise TrackingError(exc.message, exc.status_code) from exc
        _ACTIVE.add(job_id)
    record = {"id": job_id, "video_id": video_id, "status": "queued",
              "created_at": datetime.now(timezone.utc).isoformat(), "model": SAM_MODEL,
              "concepts": concepts, "scenario_id": video.get("scenario_id"), "media_probe": probe,
              "phase": "queued", "concepts_completed": [],
              "preview_url": f"/api/v1/tracking-jobs/{job_id}/preview",
              "message": "Waiting for SAM 3.1 processing; this request uses Meta credits.",
              "result_url": f"/api/v1/tracking-jobs/{job_id}/result"}
    try:
        _write(_paths(job_id)[0], record)
    except Exception:
        with _LOCK:
            _ACTIVE.discard(job_id)
        raise
    return record


def process_job(job_id: str) -> None:
    """Worker-thread entry point: never block the ASGI event loop with SAM."""
    asyncio.run(_process_job_async(job_id))


def _safe_preview_boxes(concept: str, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip remote data down to valid box observations (no masks, no interpolation)."""
    valid = {}
    for entry in raw:
        try:
            frame = entry["frame"]
            vals = {key: float(entry[key]) for key in ("left", "top", "right", "bottom")}
            object_id = str(entry["object_id"])
            if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
                continue
            if not object_id or len(object_id) > 80 or not all(math.isfinite(v) for v in vals.values()):
                continue
            if vals["right"] <= vals["left"] or vals["bottom"] <= vals["top"]:
                continue
            track_id = f"{concept}:{object_id}"
            valid[(track_id, frame)] = {"track_id": track_id, "fragment_id": f"{track_id}#preview",
                                        "concept": concept, "frame": frame, "box": vals}
        except (KeyError, ValueError, TypeError):
            continue
    return list(valid.values())


def get_preview(job_id: str) -> dict[str, Any]:
    get_job(job_id)  # Verify job exists and handle interrupted states.
    path = _preview_path(job_id)
    if not path.is_file():
        raise TrackingError("Tracking preview is not available yet", 404)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TrackingError("Tracking preview unavailable", 500) from exc


async def _process_job_async(job_id: str) -> None:
    """Run the billable request off the ASGI loop and publish partial observations."""
    completed: dict[str, dict[str, Any]] = {}
    streamed: dict[str, list[dict[str, Any]]] = {}
    with _LOCK:
        current = asyncio.current_task()
        assert current is not None
        _WORKERS[job_id] = (asyncio.get_running_loop(), current)
    try:
        _ensure_not_cancelled(job_id)
        record = _read_record(job_id)
        video_path, _ = get_video_file(record["video_id"])
        _ensure_not_cancelled(job_id)
        record["status"] = "running"
        record["phase"] = "uploading"
        record["current_concept"] = None
        record["message"] = "Sending authorized clip to Meta SAM 3.1."
        _write(_paths(job_id)[0], record)
        _ensure_not_cancelled(job_id)

        def on_progress(event: dict[str, Any]) -> None:
            _ensure_not_cancelled(job_id)
            phase = str(event["phase"])
            concept = event.get("concept")
            if concept in record["concepts"]:
                record["current_concept"] = concept
            if phase == "upload_completed":
                record["upload_seconds"] = float(event.get("upload_seconds", 0))
            if phase == "concept_completed":
                record["last_concept_inference_seconds"] = float(event.get("inference_seconds", 0))
            if phase == "streaming" and concept in record["concepts"]:
                streamed[concept] = _safe_preview_boxes(concept, event.get("boxes", []))
            if phase == "concept_completed" and concept in record["concepts"]:
                completed[concept] = event["summary"]
                streamed[concept] = _safe_preview_boxes(concept, event["summary"].get("boxes", []))
            if phase in {"streaming", "concept_completed"}:
                boxes = [item for part in record["concepts"] for item in streamed.get(part, [])]
                if boxes:
                    preview = {"job_id": job_id, "schema_version": 1,
                               "partial": True, "status": "preview", "time_alignment": "approximate",
                               "media_probe": record["media_probe"], "media_metadata": {},
                               "boxes": boxes, "box_count": len(boxes),
                               "track_count": len({item["track_id"] for item in boxes}),
                               "gap_count": 0, "gaps": [], "tracks": [],
                               "concepts_completed": list(completed),
                               "note": "Streaming observations are provisional and cannot be used for final safety conclusions."}
                    _write(_preview_path(job_id), preview)
            record["phase"] = phase
            record["message"] = str(event.get("message", "SAM analysis in progress"))
            record["concepts_completed"] = list(completed)
            if "revision" in event:
                record["revision"] = event["revision"]
            _write(_paths(job_id)[0], record)
            _ensure_not_cancelled(job_id)

        summaries = await run_video(video_path, record["concepts"],
                                    tracking_dir() / job_id / "raw",
                                    progress_callback=on_progress)
        _ensure_not_cancelled(job_id)
        record["phase"] = "building_report"
        record["current_concept"] = None
        record["message"] = "Preparing final tracked observations and uncertainty gaps."
        _write(_paths(job_id)[0], record)
        report = await asyncio.to_thread(build_tracking_report, summaries, record["media_probe"])
        report["job_id"] = job_id
        report["video_id"] = record["video_id"]
        # Commit both result and completed status atomically relative to
        # cancel requests. Once completed, a job cannot be cancelled.
        with _LOCK:
            if job_id in _CANCEL_REQUESTED:
                raise asyncio.CancelledError()
            _write(_paths(job_id)[1], report)
            record["status"] = "completed"
            record["phase"] = "completed"
            record["message"] = "SAM analysis completed; review tracks and occlusion gaps. No danger classification yet."
            record["completed_at"] = datetime.now(timezone.utc).isoformat()
            record["track_count"] = report["track_count"]
            record["gap_count"] = report["gap_count"]
            _write(_paths(job_id)[0], record)
    except asyncio.CancelledError:
        _finalize_cancel(job_id)
    except Exception as exc:
        if _cancel_requested(job_id):
            _finalize_cancel(job_id)
            return
        logger.exception("SAM job %s failed", job_id)
        try:
            record = _read_record(job_id)
            record["status"] = "failed"
            record["phase"] = "failed"
            record["failure_type"] = type(exc).__name__  # No raw exception text or credentials.
            record["message"] = (f"Tracking failed ({type(exc).__name__}); check backend logs. "
                                 "Partial observations may be available, but no final result was generated.")
            _write(_paths(job_id)[0], record)
        except Exception:
            logger.exception("Could not persist failed job state")
    finally:
        with _LOCK:
            _WORKERS.pop(job_id, None)
            _CANCEL_REQUESTED.discard(job_id)
            _ACTIVE.discard(job_id)


def get_result(job_id: str) -> dict[str, Any]:
    record = get_job(job_id)
    if record["status"] != "completed":
        raise TrackingError("Tracking result is not ready", 409)
    _, result = _paths(job_id)
    if db_store.enabled():
        report = db_store.get_result(job_id)
        if report is None:
            raise TrackingError("Tracking result is missing", 500)
        return report
    if not result.is_file():
        raise TrackingError("Tracking result is missing", 500)
    return json.loads(result.read_text(encoding="utf-8"))
