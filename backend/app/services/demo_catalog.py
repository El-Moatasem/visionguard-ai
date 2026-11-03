"""Curated demo metadata. No footage is bundled or passed off as model output."""
from __future__ import annotations

from typing import Any

SCENARIOS: dict[str, dict[str, Any]] = {
    "warehouse-safety": {
        "id": "warehouse-safety", "title": "Warehouse: shared operating zone", "industry": "Warehouse",
        "description": "Workers and forklifts observed in the same reviewer-defined operating zone.",
        "concepts": ["person", "forklift"], "rule_type": "person_and_forklift_in_zone",
        "rule_concept": None, "duration": 0.5,
        "zone": [0.36, 0.46, 0.68, 0.92], "provenance": "real_video_required",
        "expected": "Review any qualifying observed co-presence; forklift operator may also be detected as person.",
    },
    "pedestrian-forklift": {
        "id": "pedestrian-forklift", "title": "Pedestrian approaching forklift", "industry": "Warehouse",
        "description": "Inspect pedestrian/equipment co-presence and seek to observed events.",
        "concepts": ["person", "forklift"], "rule_type": "person_and_forklift_in_zone",
        "rule_concept": None, "duration": 0.5,
        "zone": [0.1, 0.25, 0.9, 0.95], "provenance": "real_video_required",
        "expected": "Event depends on actual frames and reviewer zone; do not infer collision distance.",
    },
    "parking-loading-zone": {
        "id": "parking-loading-zone", "title": "Parking: vehicle in loading zone", "industry": "Parking",
        "description": "Track cars and flag continuous observed occupancy inside a reviewer-marked loading area.",
        "concepts": ["car"], "rule_type": "object_in_zone",
        "rule_concept": "car", "duration": 2.0,
        "zone": [0.15, 0.25, 0.85, 0.85], "provenance": "synthetic_replay_available", "replay_id": "parking-car-dwell",
        "expected": "Demonstrate a SHORT-CLIP dwell threshold; 3-minute parking enforcement is outside the 30-second upload analysis limit.",
    },
    "retail-clearance": {
        "id": "retail-clearance", "title": "Retail: shopping cart in aisle", "industry": "Retail",
        "description": "Inspect shopping carts occupying a designated clearance zone.",
        "concepts": ["person", "shopping_cart", "cardboard_box"], "rule_type": "object_in_zone",
        "rule_concept": "shopping_cart", "duration": 1.0,
        "zone": [0.28, 0.2, 0.72, 0.95], "provenance": "synthetic_replay_available", "replay_id": "retail-cart-aisle",
        "expected": "Occupancy is not proof of obstruction; try a separate cardboard_box rule for boxes.",
    },
    "construction-person-zone": {
        "id": "construction-person-zone", "title": "Construction: worker enters operating zone", "industry": "Construction",
        "description": "Identify observed person zone-entry transitions near construction machinery.",
        "concepts": ["person", "excavator"], "rule_type": "object_zone_entry",
        "rule_concept": "person", "duration": 0.5,
        "zone": [0.3, 0.3, 0.85, 0.9], "provenance": "synthetic_replay_available", "replay_id": "construction-zone-entry",
        "expected": "Only outside-to-inside transitions with observed frames qualify; not certified danger.",
    },
    "clear-aisle": {
        "id": "clear-aisle", "title": "Clear aisle: negative control", "industry": "Warehouse",
        "description": "No person/forklift co-presence in the monitored area.",
        "concepts": ["person", "forklift"], "rule_type": "person_and_forklift_in_zone",
        "rule_concept": None, "duration": 0.5,
        "zone": [0.2, 0.2, 0.8, 0.8], "provenance": "synthetic_replay_available",
        "replay_id": "clear-aisle", "expected": "No invented positive rule matches; synthetic replay available without footage.",
    },
    "occlusion-review": {
        "id": "occlusion-review", "title": "Occlusion: human review", "industry": "Warehouse",
        "description": "Missing observations and uncertainty are surfaced, not interpolated.",
        "concepts": ["person", "forklift"], "rule_type": "person_and_forklift_in_zone",
        "rule_concept": None, "duration": 0.5,
        "zone": [0.2, 0.2, 0.8, 0.8], "provenance": "synthetic_replay_available",
        "replay_id": "occlusion-review", "expected": "Explicitly synthetic replay, not live SAM footage.",
    },
}


def get_scenario(scenario_id: str) -> dict[str, Any] | None:
    return SCENARIOS.get(scenario_id)


def list_scenarios() -> list[dict[str, Any]]:
    return list(SCENARIOS.values())
