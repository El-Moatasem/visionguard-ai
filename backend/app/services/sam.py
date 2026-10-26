"""Hosted SAM 3.1 video tracking validation via the official Meta parser.

This is an original, minimal adapter based on publicly documented Meta APIs.
A successful local unit test does not prove remote model access.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import aclosing
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI

from backend.app.config import META_BASE_URL, SAM_MODEL, model_key

ALLOWED_EXTENSIONS = {".mp4": "video/mp4", ".mov": "video/quicktime"}
MAX_BYTES = 25 * 1024 * 1024  # Day 1 cost/speed guard, not an advertised API limit


def validate_video(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Video not found: {path}")
    mime = ALLOWED_EXTENSIONS.get(path.suffix.lower())
    if not mime:
        raise ValueError("Day 1 accepts .mp4 or .mov; use a short H.264 MP4 for reliability.")
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise ValueError(f"Video size must be between 1 byte and {MAX_BYTES} bytes")
    return mime


def validate_concept(concept: str) -> str:
    normalized = concept.strip()
    if not normalized or len(normalized) > 80 or "\n" in normalized:
        raise ValueError("Use a short noun phrase (1–80 characters) such as 'person' or 'forklift'.")
    return normalized


def response_input(concept: str, file_id: str) -> list[dict[str, Any]]:
    phrase = validate_concept(concept)
    if not file_id.startswith("file-"):
        raise ValueError("Expected a valid uploaded file ID, beginning with 'file-'.")
    return [{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": phrase},
        {"type": "input_video", "file_id": file_id},
    ]}]


async def normalized_events(stream: AsyncIterable[Any]) -> AsyncIterator[dict[str, Any]]:
    """Adapt SDK streaming events to the official parser's expected event shape.

    The Responses API may close output-text lanes via content_part.done;
    the parser needs a matching output_text.done to finalize those lanes.
    """
    finished: set[tuple[Any, Any, Any]] = set()
    async for event in stream:
        obj = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        lane = (obj.get("item_id"), obj.get("output_index"), obj.get("content_index"))
        if obj.get("type") == "response.output_text.done":
            if lane not in finished:
                finished.add(lane)
                yield obj
            continue
        yield obj
        part = obj.get("part")
        if (obj.get("type") == "response.content_part.done"
                and lane not in finished
                and isinstance(part, dict)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)):
            finished.add(lane)
            yield {"type": "response.output_text.done", "item_id": lane[0],
                   "output_index": lane[1], "content_index": lane[2],
                   "text": part["text"]}


async def upload_video(client: AsyncOpenAI, path: Path) -> str:
    mime = validate_video(path)
    uploaded = await client.files.create(
        file=(path.name, path.read_bytes(), mime), purpose="user_data"
    )
    if not isinstance(uploaded.id, str) or not uploaded.id.startswith("file-"):
        raise RuntimeError("Meta did not return a valid file ID")
    return uploaded.id


async def segment_video(client: AsyncOpenAI, file_id: str, concept: str) -> Any:
    # Imported here so health checks/unit tests run without the optional SAM parser.
    from meta_sam_parser import parse_responses_stream, video_segmentation_format

    stream = await client.responses.create(
        model=SAM_MODEL, stream=True, input=response_input(concept, file_id)
    )
    async with stream, aclosing(normalized_events(stream)) as events:
        parsed = parse_responses_stream(events, video_segmentation_format())
        async with parsed:
            async for snapshot in parsed:
                if snapshot.revision == 1 or snapshot.revision % 30 == 0:
                    print(f"  {concept}: parsed revision={snapshot.revision}, records={len(snapshot.records)}")
            return await parsed.final_result()


def summarize(result: Any, concept: str) -> dict[str, Any]:
    """Return a JSON-safe overview; parser records remain the source of truth."""
    from meta_sam_parser import decode_mask_to_raster

    if result.outcome.status != "completed":
        raise RuntimeError(f"SAM result not completed: {result.outcome.status}")
    errors = [d for d in result.diagnostics if d.severity == "error"]
    if errors:
        raise RuntimeError("SAM parser errors: " + "; ".join(d.message for d in errors))

    boxes = []
    masks = []
    frames_by_object: dict[str, set[int]] = defaultdict(set)
    for record in result.records:
        frame = record.frame.frame_index if record.frame is not None else None
        if frame is not None:
            frames_by_object[str(record.object_id)].add(frame)
        if record.kind == "box":
            boxes.append({"object_id": str(record.object_id), "frame": frame,
                          "left": record.left, "top": record.top,
                          "right": record.right, "bottom": record.bottom})
        if record.kind == "mask":
            masks.append({"object_id": str(record.object_id), "frame": frame,
                          "width": record.mask.width, "height": record.mask.height,
                          "encoding": record.mask.encoding,
                          "foreground_pixels": sum(decode_mask_to_raster(record.mask))})
    return {
        "concept": concept, "media": result.media, "outcome": result.outcome.status,
        "box_count": len(boxes), "mask_count": len(masks),
        "boxes": boxes, "masks": masks,
        "tracks": [{"object_id": obj, "first_frame": min(frames),
                    "last_frame": max(frames), "visible_frames": len(frames)}
                   for obj, frames in sorted(frames_by_object.items())],
        "diagnostics": [{"severity": d.severity, "message": d.message}
                        for d in result.diagnostics],
    }


def save_outputs(result: Any, concept: str, root: Path) -> Path:
    """Write one summary and inspectable vector mask per record."""
    from meta_sam_parser import decode_mask_to_svg_path

    slug = re.sub(r"[^a-z0-9]+", "-", concept.lower()).strip("-")[:60] or "object"
    output = root / slug
    output.mkdir(parents=True, exist_ok=True)
    summary = summarize(result, concept)
    for index, record in enumerate(r for r in result.records if r.kind == "mask"):
        path_data = decode_mask_to_svg_path(record.mask)
        (output / f"mask-{index:04d}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {record.mask.width} {record.mask.height}">\n'
            f'<path d="{path_data}" fill="black"/>\n</svg>\n', encoding="utf-8"
        )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return output


async def run_video(path: Path, concepts: list[str], output: Path, file_id: str | None = None) -> list[dict[str, Any]]:
    if file_id is None:
        validate_video(path)
    if not concepts:
        raise ValueError("At least one --concept is required")
    concepts = [validate_concept(c) for c in concepts]
    from openai import AsyncOpenAI

    async with AsyncOpenAI(base_url=META_BASE_URL, api_key=model_key(), timeout=240.0) as client:
        if file_id is None:
            print(f"Uploading video: {path.name}")
            file_id = await upload_video(client, path)
            print(f"Meta Files API ID (reuse with --file-id): {file_id}")
        reports = []
        for concept in concepts:
            print(f"Requesting SAM 3.1 tracking for concept: {concept!r}")
            result = await segment_video(client, file_id, concept)
            location = save_outputs(result, concept, output)
            report = summarize(result, concept)
            reports.append(report)
            print(f"  outcome={report['outcome']} boxes={report['box_count']} masks={report['mask_count']}")
            print(f"  output: {location / 'summary.json'}")
        return reports
