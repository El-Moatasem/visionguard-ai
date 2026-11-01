"""Create small demo clips without introducing playback/coordinate mismatches.

The app and Meta SAM should analyze and display the SAME preprocessed clip.
Requires FFmpeg and FFprobe. Never silently fall back to unprocessed source.

  python -m backend.scripts.prepare_demo_clips --input samples/warehouse.mp4 \\
      --output samples/warehouse_fast.mp4 --seconds 5 --height 480 --fps 12
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def prepare(src: Path, dst: Path, seconds: float = 5.0,
            height: int = 480, fps: int = 12) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required to prepare videos; install them first")
    if not src.is_file() or src.resolve() == dst.resolve():
        raise ValueError("Input must exist, and output must differ from input")
    if not 1 <= seconds <= 30 or not 144 <= height <= 1080 or not 1 <= fps <= 30:
        raise ValueError("Bounds: 1–30 seconds, 144–1080 pixels high, 1–30 FPS")
    dst.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error",
               "-i", str(src), "-t", str(seconds),
               "-vf", f"scale=-2:{height},fps={fps}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(dst)]
    subprocess.run(command, capture_output=True, text=True, timeout=180, check=True)
    from backend.app.services.sam import MAX_BYTES, validate_video
    validate_video(dst)
    if dst.stat().st_size > MAX_BYTES:
        raise ValueError("Compressed video exceeds the 25 MiB SAM guard")
    print(f"Prepared {dst}: {dst.stat().st_size/(1024*1024):.2f} MiB")
    return dst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare clip to upload AND analyze in VisionGuard")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args(argv)
    prepare(args.input, args.output, args.seconds, args.height, args.fps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
