"""Create an explicitly selected, SAM-ready derivative without touching the original video.

The derivative becomes its own video-library item; it is both played in the
browser and sent to SAM so image-space boxes are not applied to the wrong clip.
This is local-only and never invokes a paid Meta request.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import UploadFile

from backend.app.services.tracking_jobs import probe_video
from backend.app.services.video_store import (
    VideoUploadError, get_video_file, save_video, storage_dir,
)
from backend.app.services.sam import MAX_BYTES as SAM_MAX_BYTES


class VideoPreparationError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _ffmpeg_executable() -> str:
    explicit = os.getenv("FFMPEG_BIN", "").strip()
    candidates = ([explicit] if explicit else []) + [
        "/opt/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
    ]
    discovered = shutil.which("ffmpeg")
    if discovered:
        candidates.append(discovered)
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise VideoPreparationError("FFmpeg executable not found. Set FFMPEG_BIN to its absolute path.", 503)


def _encode(src: Path, dst: Path, start: float, duration: float) -> None:
    exe = _ffmpeg_executable()
    # More aggressive fallbacks are only attempted if the first output is too large.
    # Re-encoding and resetting timestamps allows box frame indices to correspond
    # to the exact prepared clip displayed by the browser.
    attempts = [(480, 12, 27), (360, 10, 32), (240, 8, 38)]
    for height, fps, crf in attempts:
        cmd = [
            exe, "-hide_banner", "-nostdin", "-y", "-v", "error",
            "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{duration:.3f}",
            "-map", "0:v:0", "-an",
            "-vf", f"fps={fps},scale=854:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-fps_mode", "cfr",
            str(dst),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        except subprocess.TimeoutExpired as exc:
            raise VideoPreparationError("Video preparation timed out. Choose a shorter segment.", 504) from exc
        except OSError as exc:
            raise VideoPreparationError("FFmpeg could not start. Check FFMPEG_BIN and file access.", 503) from exc
        if proc.returncode:
            raise VideoPreparationError("Cannot decode or transcode this video. Check the original file and codec.")
        if dst.exists() and 0 < dst.stat().st_size <= SAM_MAX_BYTES:
            return
        dst.unlink(missing_ok=True)
    raise VideoPreparationError("Prepared clip remains larger than 25 MiB. Select a shorter segment.", 413)


async def prepare_for_sam(video_id: str, start_seconds: float, duration_seconds: float) -> dict:
    if not all(math.isfinite(x) for x in (start_seconds, duration_seconds)):
        raise VideoPreparationError("Start time and duration must be finite numbers.")
    if start_seconds < 0 or start_seconds > 3600 or not 0 < duration_seconds <= 30:
        raise VideoPreparationError("Choose a start between 0 and 3600 seconds and a segment up to 30 seconds.")

    try:
        source, original = get_video_file(video_id)
    except VideoUploadError as exc:
        raise VideoPreparationError(exc.message, exc.status_code) from exc

    source_probe = await asyncio.to_thread(probe_video, source)
    if not source_probe.get("available"):
        raise VideoPreparationError("FFprobe could not read the source video. Verify FFPROBE_BIN.")
    available = source_probe.get("duration_seconds")
    if not isinstance(available, (int, float)) or not math.isfinite(available) or available <= 0:
        raise VideoPreparationError("Source duration is unavailable; choose a video with readable duration.")
    if start_seconds >= available or start_seconds + duration_seconds > available + 0.025:
        raise VideoPreparationError(f"Selected segment exceeds source duration ({available:.1f}s).")

    # Temporary output is never treated as a stored upload until it passes
    # probing, size validation, and normal video-store signature validation.
    with tempfile.TemporaryDirectory(prefix="vg-sam-prepare-") as temp:
        output = Path(temp) / "prepared.mp4"
        await asyncio.to_thread(_encode, source, output, start_seconds, duration_seconds)
        probe = await asyncio.to_thread(probe_video, output)
        if not probe.get("available") or not all(
            isinstance(probe.get(x), (int, float)) and math.isfinite(probe[x]) and probe[x] > 0
            for x in ("width", "height", "fps")
        ):
            raise VideoPreparationError("Prepared video has invalid FPS or dimensions.")
        if probe.get("codec") != "h264" or probe["fps"] > 30 or max(probe["width"], probe["height"]) > 1920:
            raise VideoPreparationError("Prepared video did not meet codec, resolution, or FPS requirements.")
        if not isinstance(probe.get("duration_seconds"), (int, float)) or probe["duration_seconds"] > 30.05:
            raise VideoPreparationError("Prepared clip exceeds the 30-second analysis limit.")
        if not output.is_file() or not 0 < output.stat().st_size <= SAM_MAX_BYTES:
            raise VideoPreparationError("Prepared clip exceeds the 25 MiB inference limit.", 413)

        # Reuse the existing upload validator rather than writing directly to
        # the library. A distinct ID ensures playback and SAM use identical bytes.
        filename = f"{Path(original['name']).stem[:70]}_sam_{start_seconds:g}s.mp4"
        with output.open("rb") as f:
            upload = UploadFile(file=f, filename=filename)
            saved = await save_video(upload)

    # Preserve lineage for the original without changing the API's core fields.
    saved.update({
        "library_source": original.get("library_source", "upload"),
        "scenario_id": original.get("scenario_id"),
        "suggested_concepts": original.get("suggested_concepts", []),
        "analysis_source_video_id": original["id"],
        "analysis_source_sha256": original["sha256"],
        "analysis_start_seconds": start_seconds,
        "analysis_duration_seconds": probe["duration_seconds"],
        "note": "Prepared locally with FFmpeg. Display this exact clip when evaluating SAM detections.",
    })
    info = storage_dir() / f"{saved['id']}.json"
    info.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return saved
