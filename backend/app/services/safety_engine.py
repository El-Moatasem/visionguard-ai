"""Deterministic, evidence-first screening of video tracking observations.

Only actually observed boxes can match a zone. Short gaps may form *provisional*
review episodes, never verified continuous occupancy; no interpolation/re-ID.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from backend.app.services.safety_rules import RuleSpec


class SafetyEvaluationError(ValueError):
    pass


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (ValueError, TypeError):
        return None
    return n if math.isfinite(n) and n > 0 else None


def _dimensions(report: dict[str, Any]) -> tuple[float, float]:
    """Use ffprobe dimensions, falling back to validated SAM media metadata."""
    sources = [report.get("media_probe") or {}, report.get("media_metadata") or {}]
    for source in sources:
        if not isinstance(source, dict):
            continue
        w, h = _positive_number(source.get("width")), _positive_number(source.get("height"))
        if w is not None and h is not None:
            return w, h
    raise SafetyEvaluationError("Video dimensions unavailable from ffprobe or SAM media metadata; cannot evaluate zone geometry")


def _point(box: dict[str, Any], concept: str, width: float, height: float) -> tuple[float, float] | None:
    try:
        left, top, right, bottom = (float(box[k]) for k in ("left", "top", "right", "bottom"))
    except (ValueError, TypeError, KeyError):
        return None
    if not all(math.isfinite(v) for v in (left, top, right, bottom)) or left >= right or top >= bottom:
        return None
    # Person's estimated floor-contact point; forklift center is only an image-space proxy.
    return (left + right) / (2 * width), (bottom if concept == "person" else (top + bottom) / 2) / height


def _near_zone(point: tuple[float, float], rule: RuleSpec, margin: float = 0.06) -> bool:
    x, y = point
    z = rule.zone
    return z.x_min - margin <= x <= z.x_max + margin and z.y_min - margin <= y <= z.y_max + margin


def _inside(point: tuple[float, float], rule: RuleSpec) -> bool:
    x, y = point
    z = rule.zone
    return z.x_min <= x <= z.x_max and z.y_min <= y <= z.y_max


def evaluate_tracking(report: dict[str, Any], rule: RuleSpec) -> dict[str, Any]:
    """Evaluate observed rule matches; keep uncertain temporal associations separate.

    A fully observed event requires continuous matched source frames covering the
    requested duration. Sparse runs may become review candidates when adjacent
    sampled observations use the same source track IDs and the gap is small.
    """
    if report.get("schema_version") != 1:
        raise SafetyEvaluationError("Unsupported tracking report schema")
    width, height = _dimensions(report)
    probe = report.get("media_probe") or {}
    metadata = report.get("media_metadata") or {}
    fps = _positive_number(probe.get("fps")) or _positive_number(metadata.get("fps"))
    if fps is None:
        raise SafetyEvaluationError("FPS unavailable; cannot evaluate a seconds-based duration rule")

    # A deduplicated observation is keyed by source track and exact sampled frame.
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    boundaries: dict[tuple[str, int], bool] = {}
    for raw in report.get("boxes", []):
        if not isinstance(raw, dict):
            continue
        concept, frame = raw.get("concept"), raw.get("frame")
        source = raw.get("track_id")
        fragment = raw.get("fragment_id")
        if (concept not in ("person", "forklift") or not isinstance(frame, int)
                or isinstance(frame, bool) or frame < 0 or not isinstance(source, str)
                or not source.startswith(f"{concept}:") or not isinstance(fragment, str)
                or not fragment.startswith(f"{source}#")):
            continue
        p = _point(raw.get("box") or {}, concept, width, height)
        if p is None:
            continue
        key = (source, frame)
        # If a report contradicts itself, exclude that observation rather than picking one.
        if key in seen and (seen[key]["point"] != p or seen[key]["fragment"] != fragment):
            boundaries[key] = True
        else:
            seen[key] = {"point": p, "fragment": fragment, "concept": concept, "track_id": source, "frame": frame}
    for key in boundaries:
        seen.pop(key, None)

    by_frame: dict[int, dict[str, set[str]]] = defaultdict(lambda: {"person": set(), "forklift": set()})
    all_observations: dict[tuple[str, int], dict[str, Any]] = seen
    for obs in seen.values():
        if _inside(obs["point"], rule):
            by_frame[obs["frame"]][obs["concept"]].add(obs["track_id"])

    matches: dict[str, list[int]] = defaultdict(list)
    for frame in sorted(by_frame):
        people, forklifts = by_frame[frame]["person"], by_frame[frame]["forklift"]
        if rule.rule_type == "person_in_zone":
            for person in sorted(people):
                matches[person].append(frame)
        else:
            for person in sorted(people):
                for forklift in sorted(forklifts):
                    matches[f"{person}|{forklift}"].append(frame)

    required_frames = max(1, math.ceil(rule.min_duration_seconds * fps - 1e-9))
    events: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    # For each actor/pair, separate runs by gap tolerance, and mark fragment breaks.
    for key, frames in sorted(matches.items()):
        actors = key.split("|")
        chunks: list[list[int]] = [[frames[0]]]
        for frame in frames[1:]:
            previous = chunks[-1][-1]
            if frame - previous - 1 > rule.max_observation_gap_frames:
                chunks.append([frame])
            else:
                chunks[-1].append(frame)
        for chunk in chunks:
            # Verified episodes are extracted from strictly consecutive *matching*
            # frames with unchanged fragments, even inside a longer sparse run.
            contiguous: list[list[int]] = [[chunk[0]]]
            for frame in chunk[1:]:
                prev = contiguous[-1][-1]
                unchanged = all(all_observations[(actor, frame)]["fragment"] ==
                                all_observations[(actor, prev)]["fragment"] for actor in actors)
                if frame == prev + 1 and unchanged:
                    contiguous[-1].append(frame)
                else:
                    contiguous.append([frame])
            for observed_run in contiguous:
                if len(observed_run) < required_frames:
                    continue
                first, last = observed_run[0], observed_run[-1]
                events.append({
                    "event_id": f"{rule.rule_type}:{key}:{first}-{last}",
                    "status": "potential_hazard", "start_frame": first, "end_frame": last,
                    "observed_frames": len(observed_run),
                    "observed_span_seconds_approx": round(len(observed_run) / fps, 3),
                    "observed_coverage_ratio": 1.0,
                    "contains_missing_observations": False,
                    "identity_continuity": "observed_in_contiguous_frames",
                    "start_seconds_approx": round(first / fps, 3),
                    "end_seconds_approx": round(last / fps, 3),
                    "actor_tracks": actors,
                    "actor_fragments": sorted({all_observations[(actor, first)]["fragment"] for actor in actors}),
                    "reason": ("Person foot-point observed in reviewer-defined zone" if rule.rule_type == "person_in_zone"
                               else "Person foot-point and forklift center observed in the same zone and frames"),
                })
            start, end = chunk[0], chunk[-1]
            has_gap = len(chunk) != end - start + 1
            has_fragment_change = len(contiguous) > 1 and not has_gap
            # Sparse observations might support an episode, but never a
            # verified continuous hazard. We emit a distinct review candidate.
            if (has_gap or has_fragment_change) and end - start + 1 >= required_frames and len(chunk) >= 2:
                fragments = sorted({all_observations[(actor, f)]["fragment"] for actor in actors for f in chunk})
                review_items.append({
                    "event_id": f"review:{rule.rule_type}:{key}:{start}-{end}",
                    "status": "needs_review", "start_frame": start, "end_frame": end,
                    "observed_frames": len(chunk),
                    "observed_span_seconds_approx": round((end - start + 1) / fps, 3),
                    "observed_coverage_ratio": round(len(chunk) / (end - start + 1), 4),
                    "contains_missing_observations": has_gap,
                    "identity_continuity": "unverified",
                    "start_seconds_approx": round(start / fps, 3),
                    "end_seconds_approx": round(end / fps, 3),
                    "actor_tracks": actors,
                    "actor_fragments": fragments,
                    "reason": "Observed samples could match the rule, but missing observations or fragment changes prevent verified continuity",
                })

    # Localize gaps to actors whose observations near the gap are in/near the zone.
    # A distant disappearing forklift is not relevant to a restricted-zone alert.
    uncertainties: list[dict[str, Any]] = []
    for g in report.get("gaps", []):
        if not isinstance(g, dict):
            continue
        source = g.get("track_id")
        before, after = g.get("after_frame"), g.get("before_frame")
        if not isinstance(source, str) or not isinstance(before, int) or not isinstance(after, int) or after <= before:
            continue
        endpoints = [all_observations.get((source, frame)) for frame in (before, after)]
        if not any(obs is not None and _near_zone(obs["point"], rule) for obs in endpoints):
            continue
        item = {"track_id": source, "after_frame": before, "before_frame": after,
                "start_frame": before, "end_frame": after,
                "missing_frames": after - before - 1,
                "start_seconds_approx": round(before / fps, 3),
                "end_seconds_approx": round(after / fps, 3),
                "status": "needs_review", "reason": "Missing observations near monitored zone; identity and occupancy unverified"}
        uncertainties.append(item)
    # Return uncertainties alongside events, not hidden behind a single outcome.
    review_items.extend(uncertainties)
    events.sort(key=lambda e: (e["start_frame"], e["event_id"]))
    review_items.sort(key=lambda e: (e["start_frame"], e.get("event_id", e.get("track_id", ""))))
    outcome = "potential_hazard" if events else "needs_review" if review_items else "no_rule_match_observed"
    return {
        "schema_version": 2, "rule": rule.model_dump(), "outcome": outcome,
        "event_count": len(events), "events": events,
        "review_count": len(review_items), "review_items": review_items,
        "uncertainty_count": len(uncertainties), "uncertainties": uncertainties,
        "has_unresolved_review_items": bool(review_items),
        "frames_with_zone_observations": len(by_frame),
        "required_observed_frame_span": required_frames,
        "time_alignment": "approximate",
        "method": "Observed person foot-point / forklift box center; seconds-based threshold; short gaps are review-only and NEVER interpolated",
        "disclaimer": "Research screening only. A match is not certified danger; short gaps do not prove occupancy, motion, distance or identity continuity. No match does not establish safety.",
    }
