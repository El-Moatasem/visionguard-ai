"""Hosted SAM 3.1 video tracking validation via the official Meta parser.

This is an original, minimal adapter based on publicly documented Meta APIs.
A successful local unit test does not prove remote model access.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import aclosing
from pathlib import Path
from typing import Any, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from openai import AsyncOpenAI

from backend.app.config import META_BASE_URL, SAM_MODEL, model_key
from backend.app.services.sceneops_concepts import concept_prompt, normalize_concept

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
    phrase = validate_concept(concept_prompt(concept))
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


async def segment_video(client: AsyncOpenAI, file_id: str, concept: str,
                        on_snapshot: Callable[[Any], None] | None = None) -> Any:
    # Imported here so health checks/unit tests run without the optional SAM parser.
    from meta_sam_parser import parse_responses_stream, video_segmentation_format

    mask_encoding = os.getenv("SAM_MASK_ENCODING", "one_bit").strip().lower()
    if mask_encoding not in {"one_bit", "default"}:
        raise ValueError("SAM_MASK_ENCODING must be one_bit or default")
    options = {"metadata": {"mask_encoding": "one_bit"}} if mask_encoding == "one_bit" else {}
    stream = await client.responses.create(
        model=SAM_MODEL, stream=True, input=response_input(concept, file_id),
        **options,
    )
    async with stream, aclosing(normalized_events(stream)) as events:
        parsed = parse_responses_stream(events, video_segmentation_format())
        async with parsed:
            async for snapshot in parsed:
                if on_snapshot is not None:
                    # Progress reporting must never abort an otherwise healthy paid request.
                    try:
                        on_snapshot(snapshot)
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception("Non-fatal SAM preview update failure")
                if snapshot.revision == 1 or snapshot.revision % 30 == 0:
                    print(f"  {concept}: parsed revision={snapshot.revision}, records={len(snapshot.records)}", flush=True)
            return await parsed.final_result()


def summarize(result: Any, concept: str, count_mask_pixels: bool = False) -> dict[str, Any]:
    """Summarize boxes and lightweight mask metadata without raster expansion.

    A full-resolution mask raster is unnecessary for tracking, zone checks, and
    evidence. Explicit pixel counting is reserved for offline debugging only.
    """
    if count_mask_pixels:
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
            entry = {"object_id": str(record.object_id), "frame": frame,
                     "width": record.mask.width, "height": record.mask.height,
                     "encoding": record.mask.encoding}
            if count_mask_pixels:
                entry["foreground_pixels"] = sum(decode_mask_to_raster(record.mask))
            masks.append(entry)
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


def save_outputs(result: Any, concept: str, root: Path,
                 summary: dict[str, Any] | None = None,
                 write_masks: bool = False) -> Path:
    """Save the summary once; export costly SVG masks only when requested.

    The app uses bounding boxes, not SVG masks. Keep export opt-in so a high-
    resolution source cannot stall HTTP polling via expensive polygon decoding.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", concept.lower()).strip("-")[:60] or "object"
    output = root / slug
    output.mkdir(parents=True, exist_ok=True)
    if summary is None:
        summary = summarize(result, concept)
    if write_masks:
        from meta_sam_parser import decode_mask_to_svg_path

        for index, record in enumerate(r for r in result.records if r.kind == "mask"):
            path_data = decode_mask_to_svg_path(record.mask)
            (output / f"mask-{index:04d}.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {record.mask.width} {record.mask.height}">\n'
                f'<path d="{path_data}" fill="black"/>\n</svg>\n', encoding="utf-8"
            )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return output


async def run_video(path: Path, concepts: list[str], output: Path,
                    file_id: str | None = None, *,
                    write_masks: bool = False,
                    concurrent: bool | None = None,
                    progress_callback: Callable[[dict[str, Any]], None] | None = None) -> list[dict[str, Any]]:
    """Run hosted SAM once per concept; preserve completed per-concept artifacts.

    Concurrency is opt-in (SAM_CONCURRENT_CONCEPTS=1): it can improve latency
    but can also increase rate-limit pressure and memory consumption.
    Never automatically retry a paid inference after a streamed failure.
    """
    if file_id is None:
        validate_video(path)
    if not concepts:
        raise ValueError("At least one --concept is required")
    concepts = [normalize_concept(c) for c in concepts]
    if len(set(concepts)) != len(concepts):
        raise ValueError("Repeat concepts are not supported")
    if concurrent is None:
        concurrent = os.getenv("SAM_CONCURRENT_CONCEPTS", "0") == "1"
    from openai import AsyncOpenAI

    def progress(event: dict[str, Any]) -> None:
        if progress_callback is not None:
            progress_callback(event)

    async with AsyncOpenAI(base_url=META_BASE_URL, api_key=model_key(), timeout=240.0) as client:
        if file_id is None:
            progress({"phase": "uploading", "message": "Uploading clip to Meta SAM 3.1"})
            print(f"Uploading video: {path.name}", flush=True)
            started = time.perf_counter()
            file_id = await upload_video(client, path)
            print(f"Meta Files API ID (reuse with --file-id): {file_id}; upload_seconds={time.perf_counter()-started:.2f}", flush=True)

        async def one(concept: str) -> dict[str, Any]:
            started = time.perf_counter()
            progress({"phase": "segmenting", "concept": concept,
                      "message": f"Tracking {concept} with Meta SAM 3.1"})
            print(f"Requesting SAM 3.1 tracking for concept: {concept!r}", flush=True)
            last_preview = 0.0

            def on_snapshot(snapshot: Any) -> None:
                nonlocal last_preview
                now = time.monotonic()
                if snapshot.revision != 1 and now - last_preview < 2.0:
                    return
                last_preview = now
                # Snapshot records may include large masks. Only box fields are exported.
                boxes = []
                for record in snapshot.records:
                    if record.kind != "box" or record.frame is None:
                        continue
                    boxes.append({"object_id": str(record.object_id),
                                  "frame": record.frame.frame_index,
                                  "left": record.left, "top": record.top,
                                  "right": record.right, "bottom": record.bottom})
                progress({"phase": "streaming", "concept": concept,
                          "revision": snapshot.revision, "boxes": boxes,
                          "message": f"Receiving {concept} observations (revision {snapshot.revision})"})

            if progress_callback is None:
                result = await segment_video(client, file_id, concept)
            else:
                result = await segment_video(client, file_id, concept, on_snapshot=on_snapshot)
            infer_elapsed = time.perf_counter() - started
            progress({"phase": "summarizing", "concept": concept,
                      "message": f"Preparing {concept} tracking results"})
            post_started = time.perf_counter()
            # Both parsing and mask/summary saving stay off the ASGI event loop
            # because the entire background job runs in Starlette's threadpool.
            summary = await asyncio.to_thread(summarize, result, concept)
            location = await asyncio.to_thread(save_outputs, result, concept, output,
                                               summary, write_masks)
            print(f"  {concept}: outcome={summary['outcome']} boxes={summary['box_count']} "
                  f"masks={summary['mask_count']} inference_seconds={infer_elapsed:.2f} "
                  f"postprocess_seconds={time.perf_counter()-post_started:.2f}", flush=True)
            print(f"  output: {location / 'summary.json'}", flush=True)
            progress({"phase": "concept_completed", "concept": concept,
                      "summary": summary,
                      "message": f"{concept.capitalize()} tracking complete; {summary['box_count']} boxes"})
            return summary

        if concurrent and len(concepts) > 1:
            return list(await asyncio.gather(*(one(c) for c in concepts)))
        reports = []
        for concept in concepts:
            reports.append(await one(concept))
        return reports
