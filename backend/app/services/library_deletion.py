"""Local-only destructive video library maintenance.

No public authentication is implemented. Explicitly opt in with
VISIONGUARD_ALLOW_LIBRARY_DELETE=1 only in a trusted local environment.
Delete a source video and all prepared derivatives to avoid broken provenance.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from backend.app.services import tracking_jobs
from backend.app.services.evidence_store import root as evidence_dir
from backend.app.services.video_store import VideoUploadError, read_video, storage_dir

ID_RE = re.compile(r"^[0-9a-f]{32}$")
JOB_RE = re.compile(r"^[0-9a-f-]{36}$")


def _enabled() -> None:
    if os.getenv("VISIONGUARD_REPLAY_ONLY", "0") == "1" or os.getenv("VISIONGUARD_ALLOW_LIBRARY_DELETE") != "1":
        raise VideoUploadError(
            "Library deletion is disabled. Enable VISIONGUARD_ALLOW_LIBRARY_DELETE=1 only for local use.", 403
        )


def _records() -> dict[str, dict[str, Any]]:
    base = storage_dir()
    records = {}
    for path in base.glob("*.json") if base.is_dir() else []:
        if not ID_RE.fullmatch(path.stem):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VideoUploadError("Video library contains unreadable metadata; deletion aborted", 409) from exc
        if not isinstance(record, dict) or record.get("id") != path.stem:
            raise VideoUploadError("Video metadata ID mismatch; deletion aborted", 409)
        records[path.stem] = record
    return records


def _select(ids: set[str], records: dict[str, dict[str, Any]]) -> set[str]:
    """Follow prepared-clip lineage without ever using client filenames as paths."""
    selected = set(ids)
    while True:
        children = {vid for vid, record in records.items()
                    if record.get("analysis_source_video_id") in selected}
        expanded = selected | children
        if expanded == selected:
            return selected
        selected = expanded


def _job_records(video_ids: set[str]) -> dict[str, dict[str, Any]]:
    root = tracking_jobs.tracking_dir()
    results = {}
    for path in root.glob("*.json") if root.is_dir() else []:
        if not JOB_RE.fullmatch(path.stem):
            continue  # Ignores .result.json and .preview.json
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VideoUploadError("Unreadable tracking metadata; deletion aborted", 409) from exc
        if not isinstance(record, dict) or record.get("id") != path.stem:
            raise VideoUploadError("Tracking metadata ID mismatch; deletion aborted", 409)
        if record.get("video_id") in video_ids:
            results[path.stem] = record
    return results


def _evidence_files(video_ids: set[str], job_ids: set[str]) -> list[Path]:
    root = evidence_dir()
    found = []
    for path in root.glob("*.json") if root.is_dir() else []:
        if not ID_RE.fullmatch(path.stem):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VideoUploadError("Unreadable evidence metadata; deletion aborted", 409) from exc
        if not isinstance(record, dict):
            raise VideoUploadError("Malformed evidence metadata; deletion aborted", 409)
        source = record.get("source") or {}
        if source.get("video_id") in video_ids or source.get("tracking_job_id") in job_ids:
            found.append(path)
    return found


def delete_library(video_id: str | None = None, *, confirm_all: str | None = None) -> dict[str, Any]:
    _enabled()
    if video_id is None and confirm_all != "DELETE ALL VIDEOS":
        raise VideoUploadError("Type DELETE ALL VIDEOS to confirm removal of every uploaded video", 422)
    if video_id is not None:
        # Use normal validation to avoid accepting arbitrary paths/IDs.
        read_video(video_id)
    # Serializes deletion against create_job's _ACTIVE registration, including
    # the final existence check added by this patch.
    with tracking_jobs._LOCK:
        records = _records()
        if video_id is not None and video_id not in records:
            raise VideoUploadError("Video not found", 404)
        selected = _select(set(records) if video_id is None else {video_id}, records)
        if not selected:
            return {"deleted_videos": 0, "deleted_jobs": 0, "deleted_evidence": 0,
                    "message": "Library already empty"}
        active = [job for job in tracking_jobs._ACTIVE if
                  tracking_jobs._read_record(job).get("video_id") in selected]
        if active:
            raise VideoUploadError(
                "A SAM tracking job is active for a video being deleted. Cancel it and wait for cleanup, then retry.", 409
            )
        jobs = _job_records(selected)
        # Inactive stale queued/running job files from a previous process may be
        # removed; only jobs registered in _ACTIVE can still be writing here.
        evidence = _evidence_files(selected, set(jobs))
        # Remove evidence and dependent job artifacts first, then video bytes and metadata.
        # Each path uses an ID-generated basename; no client filename is trusted.
        for path in evidence:
            path.unlink(missing_ok=True)
        root = tracking_jobs.tracking_dir()
        for job_id in jobs:
            for suffix in (".json", ".result.json", ".preview.json"):
                (root / f"{job_id}{suffix}").unlink(missing_ok=True)
            raw_dir = root / job_id
            if raw_dir.is_dir() and not raw_dir.is_symlink():
                shutil.rmtree(raw_dir)
        folder = storage_dir()
        for vid in selected:
            for suffix in (".mp4", ".mov", ".webm", ".json"):
                (folder / f"{vid}{suffix}").unlink(missing_ok=True)
        return {"deleted_videos": len(selected), "deleted_jobs": len(jobs),
                "deleted_evidence": len(evidence),
                "message": "Deleted local uploaded media, prepared derivatives, tracking jobs and evidence"}
