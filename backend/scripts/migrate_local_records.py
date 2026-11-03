"""Explicit, idempotent JSON-file-to-Postgres metadata import (no media bytes)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from backend.app.services import db_store
from backend.app.services.video_store import storage_dir

VIDEO_ID = re.compile(r"^[0-9a-f]{32}$")
JOB_ID = re.compile(r"^[0-9a-f-]{36}$")


def records() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    base = storage_dir()
    videos = []
    for path in base.glob("*.json") if base.exists() else []:
        if VIDEO_ID.fullmatch(path.stem):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("id") != path.stem:
                raise ValueError(f"Video metadata ID mismatch: {path}")
            videos.append(row)
    jobs, results = [], []
    folder = base.parent / "tracking"
    for path in folder.glob("*.json") if folder.exists() else []:
        name = path.name
        if name.endswith(".result.json"):
            job_id = name[:-len(".result.json")]
            if JOB_ID.fullmatch(job_id):
                row = json.loads(path.read_text(encoding="utf-8"))
                if row.get("job_id") not in (None, job_id):
                    raise ValueError(f"Tracking result ID mismatch: {path}")
                row["job_id"] = job_id
                results.append(row)
        elif JOB_ID.fullmatch(path.stem):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("id") != path.stem:
                raise ValueError(f"Tracking job ID mismatch: {path}")
            jobs.append(row)
    snapshots = []
    folder = base.parent / "evidence"
    for path in folder.glob("*.json") if folder.exists() else []:
        if VIDEO_ID.fullmatch(path.stem):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("id") != path.stem:
                raise ValueError(f"Evidence report ID mismatch: {path}")
            snapshots.append(row)
    return videos, jobs, results, snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Import existing local JSON metadata into a configured database")
    parser.add_argument("--apply", action="store_true", help="Write the collected records to the database")
    args = parser.parse_args()
    videos, jobs, results, snapshots = records()
    print(f"Local records: {len(videos)} videos, {len(jobs)} jobs, {len(results)} results, {len(snapshots)} evidence reports")
    if not args.apply:
        print("Dry run only. Add --apply to migrate, after you have initialized the database.")
        return
    if not db_store.enabled():
        raise SystemExit("Set VISIONGUARD_USE_DATABASE=1 and DATABASE_URL before importing")
    # Upserts are safe to rerun after an interruption; original files are untouched.
    for record in videos:
        db_store.put_video(record)
    for record in jobs:
        db_store.put_job(record)
    for record in results:
        db_store.put_result(record)
    for record in snapshots:
        db_store.put_evidence(record)
    print("Metadata import complete. Local video bytes and raw SAM files were NOT uploaded.")


if __name__ == "__main__":
    main()
