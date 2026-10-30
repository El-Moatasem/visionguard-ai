"""Run offline synthetic rule benchmark. python -m backend.scripts.evaluate_fixture"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from backend.app.services.safety_engine import evaluate_tracking
from backend.app.services.safety_rules import RuleSpec


def run(fixture_path: Path) -> dict:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    outcome = evaluate_tracking(fixture["report"], RuleSpec.model_validate(fixture["rule"]))
    expected = fixture["expected"]
    passed = (outcome["event_count"] == expected["event_count"]
              and bool(outcome["events"])
              and outcome["events"][0]["start_frame"] == expected["start_frame"]
              and outcome["events"][0]["end_frame"] == expected["end_frame"])
    return {"fixture": str(fixture_path), "passed": passed, "outcome": outcome["outcome"],
            "event_count": outcome["event_count"], "expected": expected}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate synthetic VisionGuard observations offline")
    parser.add_argument("--fixture", type=Path, default=Path("benchmarks/fixtures/safety-rule-synthetic.json"))
    args = parser.parse_args()
    result = run(args.fixture)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
