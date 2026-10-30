"""Deterministic, conservative evaluation of SAM observations against configured zones.

No geometry across missing frames; no physical distance calculation or collision prediction.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.app.services.safety_rules import RuleSpec


class SafetyEvaluationError(ValueError):
    pass


def _inside(box: dict[str, float], width: float, height: float, rule: RuleSpec) -> bool:
    # Bounding-box center only. Touching the zone boundary is defined as inside.
    x = ((box["left"] + box["right"]) / 2) / width
    y = ((box["top"] + box["bottom"]) / 2) / height
    z = rule.zone
    return z.x_min <= x <= z.x_max and z.y_min <= y <= z.y_max


def evaluate_tracking(report: dict[str, Any], rule: RuleSpec) -> dict[str, Any]:
    """Compute observed events with auditable track fragment IDs and frame ranges.

    A qualifying event must appear in >= N *consecutive observed source frame indices*
    for one stable within-fragment actor (or person/forklift fragment pair).
    """
    probe = report.get("media_probe") or {}
    width, height = probe.get("width"), probe.get("height")
    if not isinstance(width, (int, float)) or isinstance(width, bool) or width <= 0 or not isinstance(height, (int, float)) or isinstance(height, bool) or height <= 0:
        raise SafetyEvaluationError("Video dimensions unavailable. Install ffprobe and re-run SAM analysis to evaluate spatial rules.")
    fps = probe.get("fps")
    fps = float(fps) if isinstance(fps, (int, float)) and fps > 0 else None
    # Reject unexpectedly inconsistent report data instead of guessing coordinates.
    if report.get("schema_version") != 1:
        raise SafetyEvaluationError("Unsupported tracking report schema")
    by_frame: dict[int, dict[str, dict[str, str]]] = defaultdict(lambda: {"person": {}, "forklift": {}})
    for obs in report.get("boxes", []):
        concept = obs.get("concept")
        frame = obs.get("frame")
        fragment_id = obs.get("fragment_id")
        box = obs.get("box")
        if concept not in {"person", "forklift"} or not isinstance(frame, int) or frame < 0 or not isinstance(fragment_id, str) or not isinstance(box, dict):
            continue
        if _inside(box, float(width), float(height), rule):
            by_frame[frame][concept][fragment_id] = fragment_id

    appearances: dict[str, list[int]] = defaultdict(list)
    for frame, people in sorted(by_frame.items()):
        persons = sorted(people["person"])
        forklifts = sorted(people["forklift"])
        if rule.rule_type == "person_in_zone":
            for person in persons:
                appearances[person].append(frame)
        else:
            for person in persons:
                for forklift in forklifts:
                    appearances[f"{person}|{forklift}"].append(frame)

    events: list[dict[str, Any]] = []
    for actor_key, frames in sorted(appearances.items()):
        start = prev = frames[0]
        for frame in frames[1:] + [None]:
            if frame is not None and frame == prev + 1:
                prev = frame
                continue
            if prev - start + 1 >= rule.min_consecutive_frames:
                actors = actor_key.split("|")
                events.append({
                    "event_id": f"{rule.rule_type}:{actor_key}:{start}-{prev}",
                    "status": "potential_hazard",
                    "start_frame": start,
                    "end_frame": prev,
                    "observed_frames": prev - start + 1,
                    "start_seconds_approx": round(start / fps, 3) if fps else None,
                    "end_seconds_approx": round(prev / fps, 3) if fps else None,
                    "actor_fragments": actors,
                    "reason": ("Observed person in reviewer-configured zone" if rule.rule_type == "person_in_zone" else "Observed person and forklift simultaneously in reviewer-configured zone"),
                })
            if frame is not None:
                start = frame
                prev = frame
    events.sort(key=lambda x: (x["start_frame"], x["event_id"]))
    # Gaps are unresolved evidence, not assumed hazards or negative observations.
    uncertainties = [
        {"track_id": g.get("track_id"), "after_frame": g.get("after_frame"),
         "before_frame": g.get("before_frame"), "missing_frames": g.get("missing_frames"),
         "reason": "Missing observations; identity and zone occupancy cannot be inferred"}
        for g in report.get("gaps", [])
    ]
    outcome = "potential_hazard" if events else "needs_review" if uncertainties else "no_rule_match_observed"
    return {
        "schema_version": 1, "rule": rule.model_dump(), "outcome": outcome,
        "event_count": len(events), "events": events,
        "uncertainty_count": len(uncertainties), "uncertainties": uncertainties,
        "frames_with_zone_observations": len(by_frame),
        "time_alignment": "approximate" if fps else "unavailable",
        "method": "Deterministic bounding-box center in normalized reviewer-defined zone; consecutive source frame indices and stable track fragments",
        "disclaimer": "A potential hazard is a rule match, not a certified danger judgment; no match does not establish a safe scene. Review footage and ambiguous tracks manually.",
    }
