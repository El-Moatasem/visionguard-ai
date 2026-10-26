"""Command-line Meta API smoke tests. Run from the repository root.

python -m backend.scripts.meta_smoke status
python -m backend.scripts.meta_smoke muse
python -m backend.scripts.meta_smoke sam --video samples/my-video.mp4 --concept person
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from backend.app.config import META_BASE_URL, MUSE_MODEL, SAM_MODEL, api_configured
from backend.app.services.muse import ping_muse
from backend.app.services.sam import run_video


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 1 hosted Meta AI validation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Local key presence check (no network)")
    sub.add_parser("muse", help="LIVE Muse Spark connectivity check (uses credits)")
    sam = sub.add_parser("sam", help="LIVE SAM 3.1 video tracking (uses credits)")
    sam.add_argument("--video", type=Path, help="Path to short MP4 or MOV")
    sam.add_argument("--file-id", help="Previously uploaded Meta file-... ID")
    sam.add_argument("--concept", action="append", required=True,
                     help="One noun phrase, repeat to test more object classes")
    sam.add_argument("--output", type=Path, default=Path("outputs/day1"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(json.dumps({"key_present": api_configured(), "base_url": META_BASE_URL,
                              "models": [MUSE_MODEL, SAM_MODEL],
                              "api_call_made": False}, indent=2))
        elif args.command == "muse":
            print(f"LIVE response from {MUSE_MODEL}: {ping_muse()}")
        elif args.command == "sam":
            if bool(args.video) == bool(args.file_id):
                parser.error("For SAM, provide exactly one of --video or --file-id")
            asyncio.run(run_video(args.video or Path("."), args.concept,
                                  args.output, args.file_id))
        return 0
    except (RuntimeError, ValueError, OSError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # SDK-specific HTTP errors should be visible for diagnosis
        print(f"Remote request failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
