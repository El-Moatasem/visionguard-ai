"""Read-only, explicitly synthetic replay fixtures. These are not SAM outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.config import ROOT

SCENARIOS = {
    "warehouse-copresence": "warehouse-copresence.json",
    "occlusion-review": "occlusion-review.json",
    "clear-aisle": "clear-aisle.json",
    "parking-car-dwell": "parking-car-dwell.json",
    "retail-cart-aisle": "retail-cart-aisle.json",
    "construction-zone-entry": "construction-zone-entry.json",
}


class ReplayError(ValueError):
    pass


def get_scenario(scenario_id: str) -> dict[str, Any]:
    filename = SCENARIOS.get(scenario_id)
    if not filename:
        raise ReplayError("Unknown replay scenario")
    path = ROOT / "benchmarks" / "replay" / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("provenance") != "synthetic_fixture" or data.get("id") != scenario_id:
        raise ReplayError("Invalid synthetic replay fixture provenance")
    return data


def list_scenarios() -> list[dict[str, Any]]:
    return [{k: get_scenario(s)[k] for k in ("id", "title", "description", "provenance")}
            for s in SCENARIOS]
