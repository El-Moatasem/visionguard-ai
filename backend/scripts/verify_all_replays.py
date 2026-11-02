"""Offline acceptance test for every installed synthetic VisionGuard replay.

Run: python -m backend.scripts.verify_all_replays
No Meta API key or actual videos needed. Every scenario uses the exact rule
and JSON fixture used by the frontend /replay page.
"""
from __future__ import annotations

from backend.app.services.replay_fixtures import SCENARIOS, get_scenario
from backend.app.services.safety_engine import evaluate_tracking
from backend.app.services.safety_rules import RuleSpec

EXPECTED = {
    "warehouse-copresence": "match",
    "occlusion-review": "review",
    "clear-aisle": "no_match",
    "parking-car-dwell": "match",
    "retail-cart-aisle": "match",
    "construction-zone-entry": "match",
}


def main() -> int:
    failures=[]
    for key in SCENARIOS:
        data=get_scenario(key)
        assert data['provenance']=='synthetic_fixture'
        rule=RuleSpec.model_validate(data['default_rule'])
        result=evaluate_tracking(data['tracking_report'],rule)
        expected=EXPECTED[key]
        valid=(result['event_count']>0 if expected=='match' else
               result['review_count']>0 if expected=='review' else
               result['event_count']==0 and result['review_count']==0)
        icon='PASS' if valid else 'FAIL'
        print(f'{icon:4} {key:28s} {result["event_count"]:2d} event(s), {result["review_count"]:2d} review(s), outcome {result["outcome"]}')
        if not valid:
            failures.append(key)
    if set(SCENARIOS)!=set(EXPECTED):
        print('FAIL: replay manifest differs from expected six demos')
        return 1
    if failures:
        print('FAILED SCENARIOS:',', '.join(failures))
        return 1
    print('All six deterministic synthetic scenarios passed (NOT a real SAM accuracy test).')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
