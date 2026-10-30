"""Inspect raw saved SAM summary.json frame strides, without API calls.

python -m backend.scripts.inspect_sam_frames outputs/day1/person/summary.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def inspect(path: Path) -> dict:
    summary = json.loads(path.read_text(encoding="utf-8"))
    frames: dict[str, set[int]] = defaultdict(set)
    for box in summary.get("boxes", []):
        if isinstance(box, dict) and isinstance(box.get("frame"), int) and box["frame"] >= 0:
            frames[str(box.get("object_id", "unknown"))].add(box["frame"])
    tracks = []
    for key, samples in sorted(frames.items()):
        ordered = sorted(samples)
        deltas = Counter(y-x for x, y in zip(ordered, ordered[1:]))
        tracks.append({"object_id": key, "observations": len(ordered),
                       "min_frame": ordered[0], "max_frame": ordered[-1],
                       "frame_step_counts": dict(sorted(deltas.items())),
                       "any_missing_frame_indices": any(k > 1 for k in deltas)})
    return {"concept": summary.get("concept"), "tracks": tracks, "track_count": len(tracks),
            "warning": "Frame skips may mean sampling stride, occlusion or missed observations; do not treat them as proof of disappearance."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path, help="Path to saved Meta SAM summary.json")
    args = parser.parse_args()
    print(json.dumps(inspect(args.summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
