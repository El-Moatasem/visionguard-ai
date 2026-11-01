"""Safely preflight and (opt-in) test multiple authorized SAM video clips.

Default is dry-run; no model calls or API credits are consumed.
Examples:
  python -m backend.scripts.batch_test_videos --directory samples
  python -m backend.scripts.batch_test_videos --directory samples --live --max-videos 3
  python -m backend.scripts.batch_test_videos --directory samples --live --force

Each live clip produces distinct, cached per-concept summary.json files. Skipping
completed clips protects against unintentional repeated billable requests.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.sam import MAX_BYTES, run_video
from backend.app.services.tracking_jobs import probe_video


def output_for(path: Path, root: Path) -> Path:
    slug = re.sub(r"[^a-z0-9-]+", "-", path.stem.lower()).strip("-")[:50] or "clip"
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    return root / f"{slug}-{digest}"


def missing_concepts(out: Path, concepts: list[str]) -> list[str]:
    missing = []
    for concept in concepts:
        slug = re.sub(r"[^a-z0-9]+", "-", concept.lower()).strip("-")[:60] or "object"
        report = out / slug / "summary.json"
        try:
            if json.loads(report.read_text(encoding="utf-8")).get("outcome") == "completed":
                continue
        except (OSError, ValueError):
            pass
        missing.append(concept)
    return missing


def cached(out: Path, concepts: list[str]) -> bool:
    return not missing_concepts(out, concepts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multiple-video SAM smoke testing (dry-run by default)")
    parser.add_argument("--directory", type=Path, default=Path("samples"))
    parser.add_argument("--output", type=Path, default=Path("outputs/batch"))
    parser.add_argument("--concept", action="append", default=None,
                        help="One noun phrase; repeat to request additional classes. Defaults: person, forklift")
    parser.add_argument("--max-videos", type=int, default=10)
    parser.add_argument("--live", action="store_true", help="Make billable hosted Meta calls")
    parser.add_argument("--force", action="store_true", help="Re-run already completed clips (billable)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.max_videos <= 100:
        raise SystemExit("--max-videos must be between 1 and 100")
    concepts = args.concept or ["person", "forklift"]
    if not args.directory.is_dir():
        raise SystemExit(f"Video directory not found: {args.directory}")
    clips = sorted((f for f in args.directory.iterdir()
                    if f.is_file() and f.suffix.lower() in {".mp4", ".mov"}))[:args.max_videos]
    if not clips:
        print("No MP4/MOV videos found; nothing to analyze.")
        return 0
    if args.live:
        from backend.app.config import api_configured
        if not api_configured():
            raise SystemExit("MODEL_API_KEY is not configured; no requests made")
    results: list[dict[str, object]] = []
    args.output.mkdir(parents=True, exist_ok=True)
    for idx, clip in enumerate(clips, start=1):
        size = clip.stat().st_size
        probe = probe_video(clip)
        too_long = isinstance(probe.get("duration_seconds"), (float, int)) and probe["duration_seconds"] > 30
        eligible = 0 < size <= MAX_BYTES and not too_long
        target = output_for(clip, args.output)
        needed = missing_concepts(target, concepts)
        existing = not needed
        item: dict[str, object] = {
            "video": clip.name, "bytes": size, "fps": probe.get("fps"),
            "duration_seconds": probe.get("duration_seconds"), "concepts": concepts,
            "cached_complete": existing, "output": str(target),
            "status": "eligible" if eligible else "skip_incompatible_size_or_duration",
        }
        print(f"[{idx}/{len(clips)}] {clip.name}: {size/(1024*1024):.1f} MiB, "
              f"fps={probe.get('fps', 'unknown')}, "
              f"duration={probe.get('duration_seconds', 'unknown')}, "
              f"status={item['status']}", flush=True)
        if args.live and eligible:
            if existing and not args.force:
                item["status"] = "cached_skipped_no_new_credits"
            else:
                try:
                    # Avoid re-billing for a concept with a saved completed summary.
                    # Unless --force was requested, only missing concepts are sent.
                    to_run = concepts if args.force else needed
                    reports = asyncio.run(run_video(clip, to_run, target))
                    item["status"] = "completed"
                    item["box_count"] = sum(int(r.get("box_count", 0)) for r in reports)
                    item["mask_count"] = sum(int(r.get("mask_count", 0)) for r in reports)
                except Exception as exc:
                    item["status"] = "failed"
                    item["error_type"] = type(exc).__name__
                    # Do not place potentially private external error text in the report.
                    print(f"  Failed: {type(exc).__name__} (inspect local terminal)", flush=True)
        results.append(item)

    manifest = args.output / "manifest.json"
    manifest.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                                    "live_calls_requested": args.live,
                                    "results": results}, indent=2) + "\n", encoding="utf-8")
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8") as output:
        fields = ["video", "bytes", "fps", "duration_seconds", "status", "cached_complete",
                  "box_count", "mask_count", "error_type", "output"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {manifest} and {args.output / 'manifest.csv'}", flush=True)
    return 1 if any(r.get("status") == "failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
