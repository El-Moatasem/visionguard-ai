"""Evidence snapshots and local human-review audit trail.

Research/demo only: filesystem storage, no authentication or concurrency across
workers. Never expose these endpoints publicly without access controls.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.safety_engine import evaluate_tracking
from backend.app.services.safety_rules import RuleSpec
from backend.app.services.tracking_jobs import get_job, get_result
from backend.app.services.video_store import read_video, storage_dir
from backend.app.services import db_store

_LOCK = threading.RLock()
_ID = re.compile(r"^[0-9a-f]{32}$")


class EvidenceError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEvidence(StrictInput):
    tracking_job_id: str = Field(min_length=1, max_length=80)
    rule: RuleSpec


class ReviewInput(StrictInput):
    item_id: str = Field(min_length=1, max_length=300)
    decision: Literal["confirmed", "rejected", "unresolved"]
    reviewer: str = Field(default="Local reviewer", min_length=1, max_length=64)
    note: str = Field(default="", max_length=600)


def root() -> Path:
    return storage_dir().parent / "evidence"


def _path(report_id: str) -> Path:
    if not _ID.fullmatch(report_id):
        raise EvidenceError("Invalid evidence report ID", 404)
    return root() / f"{report_id}.json"


def _save(path: Path, record: dict[str, Any]) -> None:
    if db_store.enabled():
        db_store.put_evidence(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def get_evidence(report_id: str) -> dict[str, Any]:
    with _LOCK:
        path = _path(report_id)
        if db_store.enabled():
            record = db_store.get_evidence(report_id)
            if record is None:
                raise EvidenceError("Evidence report not found", 404)
            return record
        if not path.is_file():
            raise EvidenceError("Evidence report not found", 404)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise EvidenceError("Evidence report is unreadable", 500) from None


def _record_items(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for kind, source in (("observed_event", evaluation["events"]), ("needs_review", evaluation["review_items"])):
        for item in source:
            identity = str(item.get("event_id") or f"gap:{item.get('track_id', 'unknown')}:{item['start_frame']}-{item['end_frame']}")
            # Explicitly deduplicate IDs without losing separate review candidates.
            index = seen.get(identity, 0)
            seen[identity] = index + 1
            item_id = identity if index == 0 else f"{identity}:{index}"
            items.append({"item_id": item_id, "kind": kind, "observation": item})
    return items


def create_evidence(request: CreateEvidence) -> dict[str, Any]:
    job = get_job(request.tracking_job_id)
    if job.get("status") != "completed":
        raise EvidenceError("Tracking job has not completed", 409)
    report = get_result(request.tracking_job_id)
    evaluation = evaluate_tracking(report, request.rule)
    video = read_video(job["video_id"])
    items = _record_items(evaluation)
    # Bound per-event evidence payload, preserve source hashes and exact referenced frames.
    observations = []
    for item in items:
        ev = item["observation"]
        actors = set(ev.get("actor_tracks") or ([ev["track_id"]] if ev.get("track_id") else []))
        frames = [box for box in report.get("boxes", [])
                  if box.get("track_id") in actors and ev["start_frame"] <= box.get("frame", -1) <= ev["end_frame"]]
        frames = sorted(frames, key=lambda x: (x["frame"], x["track_id"]))
        if len(frames) > 120:
            frames = frames[:60] + frames[-60:]
        observations.append({"item_id": item["item_id"], "sampled_boxes": frames,
                             "sampling_note": "Selected observations only; not an exhaustive record if the interval is long"})
    source_fingerprint = hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
    snapshot_id = uuid.uuid4().hex
    result = {
        "schema_version": 1, "id": snapshot_id, "created_at": datetime.now(timezone.utc).isoformat(),
        "origin": "live_tracking_job", "source": {
            "tracking_job_id": job["id"], "video_id": job["video_id"],
            "video_name": video["name"], "video_sha256": video["sha256"],
            "tracking_sha256": source_fingerprint, "model": job["model"],
            "time_alignment": report.get("time_alignment", "unavailable"),
            "model_output_independently_validated": False,
            "note": "Source was a locally stored job; generated report is not independent verification of model accuracy."
        },
        "rule": request.rule.model_dump(), "evaluation": evaluation, "items": items,
        "observations": observations, "reviews": [],
        "disclaimer": "Research-only evidence. Approximate times and model observations are not safety certification."
    }
    with _LOCK:
        _save(_path(snapshot_id), result)
    return result


def add_review(report_id: str, request: ReviewInput) -> dict[str, Any]:
    with _LOCK:
        snapshot = get_evidence(report_id)
        ids = {item["item_id"] for item in snapshot["items"]}
        if request.item_id not in ids:
            raise EvidenceError("Item does not belong to this evidence report", 422)
        entry = {"id": uuid.uuid4().hex, "item_id": request.item_id,
                 "decision": request.decision, "reviewer": request.reviewer,
                 "note": request.note, "recorded_at": datetime.now(timezone.utc).isoformat()}
        snapshot["reviews"].append(entry)
        _save(_path(report_id), snapshot)
    return entry


def list_evidence(tracking_job_id: str | None = None) -> list[dict[str, Any]]:
    if tracking_job_id is not None:
        try:
            uuid.UUID(tracking_job_id)
        except (TypeError, ValueError):
            raise EvidenceError("Invalid tracking job ID", 422) from None
    if db_store.enabled():
        rows = db_store.list_evidence(tracking_job_id, 30)
        return [{"id": row["id"], "created_at": row["created_at"],
                 "source": row["source"], "rule_name": row["rule"]["name"],
                 "event_count": row["evaluation"]["event_count"],
                 "review_count": row["evaluation"]["review_count"]} for row in rows]
    path = root()
    if not path.exists():
        return []
    found = []
    for f in list(path.glob("*.json"))[:250]:
        if not _ID.fullmatch(f.stem):
            continue
        try:
            snapshot = json.loads(f.read_text(encoding="utf-8"))
            if tracking_job_id is not None and snapshot["source"]["tracking_job_id"] != tracking_job_id:
                continue
            found.append({"id": snapshot["id"], "created_at": snapshot["created_at"],
                          "source": snapshot["source"], "rule_name": snapshot["rule"]["name"],
                          "event_count": snapshot["evaluation"]["event_count"],
                          "review_count": snapshot["evaluation"]["review_count"]})
        except (KeyError, ValueError, OSError, TypeError):
            continue
    return sorted(found, key=lambda x: x["created_at"], reverse=True)[:30]


def printable_html(snapshot: dict[str, Any]) -> str:
    e = html.escape
    source = snapshot["source"]
    decisions: dict[str, dict[str, Any]] = {}
    for review in snapshot["reviews"]:
        decisions[review["item_id"]] = review
    rows = []
    for item in snapshot["items"]:
        ev = item["observation"]
        reviewed = decisions.get(item["item_id"])
        status = reviewed["decision"] if reviewed else "pending"
        rows.append("<tr>" + "".join(f"<td>{e(str(value))}</td>" for value in (
            item["kind"], f"{ev['start_frame']}–{ev['end_frame']}",
            ev.get("reason", ""), status,
            reviewed["note"] if reviewed else "")) + "</tr>")
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>VisionGuard evidence report</title><style>body{font:14px Arial,sans-serif;max-width:1000px;margin:35px auto;padding:15px;color:#172634}table{width:100%;border-collapse:collapse}td,th{border:1px solid #cbd4da;padding:10px;text-align:left;vertical-align:top}small{color:#596675}@media print{body{margin:0}}</style></head><body>""" + (
        f"<h1>VisionGuard AI — Evidence Report</h1><p><b>Created:</b> {e(snapshot['created_at'])}</p>"
        f"<p><b>Video:</b> {e(source['video_name'])}<br><b>SHA256:</b> {e(source['video_sha256'])}</p>"
        f"<p><b>Rule:</b> {e(snapshot['rule']['name'])} — {e(snapshot['rule']['rule_type'])}</p>"
        f"<p><b>Observed matches:</b> {len(snapshot['evaluation']['events'])} &nbsp; <b>Review items:</b> {len(snapshot['evaluation']['review_items'])}</p>"
        f"<p><small>{e(snapshot['disclaimer'])} Frame times are approximate, not frame-perfect evidence.</small></p>"
        "<table><thead><tr><th>Type</th><th>Frames</th><th>Evidence summary</th><th>Decision</th><th>Reviewer note</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table><p><small>Model observations are not an independent measurement or certified safety assessment.</small></p></body></html>"
    )
