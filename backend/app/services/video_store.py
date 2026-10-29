"""Local demo-only video store. No external database or public sharing.

Uploads are streamed to a temporary file, bounded by size, then atomically
committed. No original client filename is used as a filesystem path.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.app.config import ROOT

DEFAULT_MAX_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
ID_RE = re.compile(r"^[0-9a-f]{32}$")


class VideoUploadError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def storage_dir() -> Path:
    raw = os.environ.get("VIDEO_STORAGE_DIR", "").strip()
    return Path(raw).expanduser().resolve() if raw else ROOT / "var" / "uploads"


def max_upload_bytes() -> int:
    value = int(os.environ.get("VIDEO_MAX_BYTES", str(DEFAULT_MAX_BYTES)))
    if value <= 0:
        raise RuntimeError("VIDEO_MAX_BYTES must be positive")
    return value


def sniff_video(header: bytes) -> tuple[str, str] | None:
    """Check file container signature, not merely user-supplied MIME/extension.

    This is not codec verification: transcoding, full ffprobe checks and malware
    scanning are deployment hardening work, not provided by this local prototype.
    """
    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand in {b"qt  "}:
            return (".mov", "video/quicktime")
        return (".mp4", "video/mp4")
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return (".webm", "video/webm")
    return None


def video_paths(video_id: str) -> tuple[Path, Path]:
    if not ID_RE.fullmatch(video_id):
        raise VideoUploadError("Invalid video ID", 404)
    base = storage_dir()
    return base / f"{video_id}.json", base


def read_video(video_id: str) -> dict[str, Any]:
    info, _ = video_paths(video_id)
    if not info.is_file():
        raise VideoUploadError("Video not found", 404)
    return json.loads(info.read_text(encoding="utf-8"))


def list_videos(limit: int = 30) -> list[dict[str, Any]]:
    root = storage_dir()
    if not root.is_dir():
        return []
    videos = []
    # Reject arbitrary JSON filenames; only files whose names are generated IDs.
    for path in root.glob("*.json"):
        if not ID_RE.fullmatch(path.stem):
            continue
        try:
            videos.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return sorted(videos, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]


async def save_video(file: UploadFile) -> dict[str, Any]:
    root = storage_dir()
    root.mkdir(parents=True, exist_ok=True)
    video_id = uuid.uuid4().hex
    pending = root / f".{video_id}.part"
    limit = max_upload_bytes()
    digest = hashlib.sha256()
    total = 0
    header = b""

    try:
        with pending.open("xb") as target:
            while chunk := await file.read(CHUNK_SIZE):
                total += len(chunk)
                if total > limit:
                    raise VideoUploadError(
                        f"Video exceeds {limit // (1024 * 1024)} MiB limit", 413
                    )
                if len(header) < 32:
                    header = (header + chunk)[:32]
                digest.update(chunk)
                target.write(chunk)
        detected = sniff_video(header)
        if not detected:
            raise VideoUploadError("Not a recognized MP4, MOV, or WebM container", 415)
        ext, media_type = detected
        if total == 0:
            raise VideoUploadError("Empty video upload", 400)
        destination = root / f"{video_id}{ext}"
        pending.replace(destination)
        original_name = Path((file.filename or "recording").replace("\\", "/")).name[:120]
        record = {
            "id": video_id,
            "name": original_name or "recording",
            "media_type": media_type,
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "stored",
            "sam_compatible_container": ext in {".mp4", ".mov"},
            "note": "Container format alone does not guarantee SAM-compatible codec; verify before model calls.",
            "file_url": f"/api/v1/videos/{video_id}/file",
        }
        info = root / f"{video_id}.json"
        info.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record
    except Exception:
        pending.unlink(missing_ok=True)
        # If recording metadata write fails, do not retain an orphaned upload.
        for candidate in root.glob(f"{video_id}.*"):
            candidate.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def get_video_file(video_id: str) -> tuple[Path, dict[str, Any]]:
    record = read_video(video_id)
    ext = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}.get(record.get("media_type"))
    if ext is None:
        raise VideoUploadError("Unsupported stored video", 500)
    path = storage_dir() / f"{video_id}{ext}"
    if not path.is_file():
        raise VideoUploadError("Video data missing", 404)
    return path, record
