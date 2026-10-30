"""Deterministic normalization of SAM track observations; no identity guessing.

SAM object IDs are only scoped to one concept request. Contiguous observations
form a track fragment; any missing frame breaks verified continuity. This is
quality metadata, not a hazard classification or a physical-distance estimate.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


class TrackingReportError(ValueError):
    pass


def _valid_box(box: dict[str, Any]) -> dict[str, float] | None:
    keys = ("left", "top", "right", "bottom")
    try:
        values = {k: float(box[k]) for k in keys}
    except (TypeError, ValueError, KeyError):
        return None
    if not all(math.isfinite(v) for v in values.values()):
        return None
    if values["right"] <= values["left"] or values["bottom"] <= values["top"]:
        return None
    return values


def build_tracking_report(summaries: list[dict[str, Any]], media_probe: dict[str, Any] | None = None,
                          max_missing_frames_for_fragment: int = 2) -> dict[str, Any]:
    """Build compact overlay observations and conservative track fragments.

    Report can be constructed from saved, mocked SAM summaries without calling
    remote models. Frame index is authoritative; seconds are *approximate* when
    derived from container FPS. Never interpolate boxes across missing frames.
    """
    if not isinstance(max_missing_frames_for_fragment, int) or not 0 <= max_missing_frames_for_fragment <= 30:
        raise TrackingReportError("max_missing_frames_for_fragment must be between 0 and 30")
    if not summaries:
        raise TrackingReportError("No completed SAM summaries available")
    probe = media_probe or {}
    fps = probe.get("fps")
    fps = float(fps) if isinstance(fps, (int, float)) and fps > 0 else None
    observations: dict[tuple[str, int], dict[str, Any]] = {}
    grouped: dict[str, set[int]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    for summary in summaries:
        if summary.get("outcome") != "completed":
            raise TrackingReportError("SAM analysis is incomplete")
        concept = str(summary.get("concept", "")).strip().lower()
        if concept not in {"person", "forklift"}:
            raise TrackingReportError("Only person and forklift concepts are supported by this milestone")
        counts[concept] += 1
        if counts[concept] > 1:
            raise TrackingReportError("Duplicate concept summary")
        for raw in summary.get("boxes", []):
            frame = raw.get("frame")
            if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
                continue
            coords = _valid_box(raw)
            if coords is None:
                continue
            source_id = str(raw.get("object_id", ""))
            if not source_id or len(source_id) > 80:
                continue
            track_id = f"{concept}:{source_id}"
            key = (track_id, frame)
            # Consecutive repeats are deduplicated; last valid box wins.
            observations[key] = {"track_id": track_id, "concept": concept, "frame": frame, "box": coords}
            grouped[track_id].add(frame)

    tracks: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    fragments: dict[tuple[str, int], int] = {}
    for track_id, frames in sorted(grouped.items()):
        ordered = sorted(frames)
        parts = []
        track_has_gap = False
        start = previous = ordered[0]
        part_no = 0
        for frame in ordered[1:]:
            if frame > previous + 1:
                track_has_gap = True
                missing = frame - previous - 1
                gaps.append({"track_id": track_id, "after_frame": previous, "before_frame": frame,
                             "missing_frames": missing,
                             "reason": "observation_gap",
                             "identity_continuity": "unverified"})
                if missing > max_missing_frames_for_fragment:
                    parts.append({"fragment_id": f"{track_id}#{part_no}", "start_frame": start, "end_frame": previous})
                    for idx in ordered:
                        if start <= idx <= previous:
                            fragments[(track_id, idx)] = part_no
                    part_no += 1
                    start = frame
            previous = frame
        parts.append({"fragment_id": f"{track_id}#{part_no}", "start_frame": start, "end_frame": previous})
        for idx in ordered:
            if start <= idx <= previous:
                fragments[(track_id, idx)] = part_no
        tracks.append({"track_id": track_id, "concept": track_id.split(":", 1)[0],
                       "observed_frames": len(ordered), "first_frame": ordered[0],
                       "last_frame": ordered[-1], "fragment_count": len(parts),
                       "has_uncertain_identity_continuity": track_has_gap,
                       "fragments": parts})

    boxes = sorted(observations.values(), key=lambda obj: (obj["frame"], obj["track_id"]))
    for box in boxes:
        box["fragment_id"] = f"{box['track_id']}#{fragments[(box['track_id'], box['frame'])]}"
    # Best-effort validated SAM media metadata fallback when ffprobe is unavailable.
    # Never invent dimensions or frame rate. Some API versions omit these fields.
    media_metadata: dict[str, float] = {}
    for summary in summaries:
        media = summary.get("media") or {}
        if not isinstance(media, dict):
            continue
        for candidate in (media, media.get("video"), media.get("metadata")):
            if not isinstance(candidate, dict):
                continue
            for field, aliases in {"width": ("width", "video_width"),
                                   "height": ("height", "video_height"),
                                   "fps": ("fps", "frame_rate")}.items():
                if field in media_metadata:
                    continue
                for alias in aliases:
                    value = candidate.get(alias)
                    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
                        media_metadata[field] = float(value)
                        break
    return {
        "schema_version": 1, "media_metadata": media_metadata,
        "models": ["sam-3.1"],
        "concepts_requested": list(counts),
        "media_probe": probe,
        "frame_time_note": "frame/fps is only an approximation for constant-frame-rate source video; verify synchronization before using timestamps as evidence",
        "time_alignment": "approximate" if fps else "unavailable",
        "box_count": len(boxes),
        "track_count": len(tracks),
        "gap_count": len(gaps),
        "tracks": tracks,
        "gaps": gaps,
        "fragment_gap_tolerance_frames": max_missing_frames_for_fragment,
        "boxes": boxes,
        "hazard_detection_implemented": False,
        "identity_policy": "Do not interpolate missing frames, auto-reidentify across gaps, or treat SAM IDs as continuous after full occlusion.",
    }
