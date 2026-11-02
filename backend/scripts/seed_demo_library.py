"""Import authorized short demo videos into the same video store as user uploads.

    python -m backend.scripts.seed_demo_library --scenario parking-loading-zone --source samples/demo/prepared/parking-loading-zone.mp4
    python -m backend.scripts.seed_demo_library --all
No remote calls; never ship or copy third-party footage into Git.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from fastapi import UploadFile
from backend.app.services.demo_catalog import SCENARIOS
from backend.app.services.tracking_jobs import probe_video
from backend.app.services.video_store import save_video, list_videos, video_paths


def register(path: Path, scenario_id: str) -> dict:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown demo scenario: {scenario_id}")
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".mov"}:
        raise ValueError(f"An existing MP4/MOV is required: {path}")
    media = probe_video(path)
    if not media.get("available") or not all(media.get(k) for k in ("width", "height", "fps")):
        raise ValueError("FFprobe must verify the video before importing it")
    width,height = sorted((media["width"], media["height"]))
    if (height > 1920 or width > 1080 or media["fps"] > 30 or
        (media.get("duration_seconds") or 0) > 30 or path.stat().st_size > 25 * 1024 * 1024 or
        media.get("codec") not in {"h264", "hevc", "mpeg4"}):
        raise ValueError("Prepare a <=1080p/30fps, <=30-second, <=25MiB H.264-compatible clip first")
    with path.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    for existing in list_videos(limit=10000):
        if existing.get("scenario_id") == scenario_id and existing.get("sha256") == sha:
            return existing  # idempotent
    with path.open("rb") as f:
        video = asyncio.run(save_video(UploadFile(filename=path.name, file=f), scenario=SCENARIOS[scenario_id]))
    return video


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Install authorized real clips into SceneOps demo library")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all",action="store_true",help="Import prepared clips with filenames <scenario_id>.mp4")
    group.add_argument("--scenario",choices=list(SCENARIOS))
    parser.add_argument("--source",type=Path,help="Existing permitted short MP4/MOV")
    parser.add_argument("--directory",type=Path,default=Path("samples/demo/prepared"))
    a=parser.parse_args(argv)
    if not a.all and a.source is None:
        parser.error("--source is required with --scenario")
    imported=0
    targets=[(name,a.directory/f"{name}.mp4") for name in SCENARIOS] if a.all else [(a.scenario,a.source)]
    for key,src in targets:
        if a.all and not src.exists():
            print(f"SKIP {key}: no file at {src}")
            continue
        video=register(src,key)
        print(f"OK {key} -> {video['id']} ({video['name']})")
        imported+=1
    print(f"Imported/present: {imported} demo video(s). No model credits spent.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
