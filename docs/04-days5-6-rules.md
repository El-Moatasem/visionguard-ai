# Days 5–6 — Natural-language monitoring rules (planned)

## Goal
Turn a reviewer prompt into a tightly scoped structured rule and evaluate it *deterministically* over real tracked objects.

## Proposed example
Input: "Flag when a pedestrian enters the marked forklift operating zone while a forklift is moving."

Allowed schema (illustrative, not yet implemented):
```json
{
  "rule_type": "zone_overlap_while_object_active",
  "subject_class": "person",
  "context_class": "forklift",
  "zone_id": "forklift-lane-1",
  "min_consecutive_frames": 3
}
```

## Key constraints
- Reviewer draws the zone in UI; Muse may not invent an unknown zone or silently modify it.
- Validate LLM output with a strict Pydantic schema/enum and require explicit approval before activating it.
- Rules are computed by Python on actual frames/tracks; do not use the LLM as the event detector.
- Define simple movement from observed tracking displacement over time with smoothing and confidence thresholds. Image displacement is not calibrated physical speed.
- Emit statuses `candidate_event`, `no_event`, `insufficient_evidence`; uncertainty/occlusion is not proof of safety.
- Include prompt injection protections and avoid sending private raw footage by default.

## Acceptance tests
- [ ] Positive, negative, and ambiguous synthetic track tests.
- [ ] Muse outputs parse or return a clear validation error.
- [ ] Unknown rule types and invalid parameters rejected.
- [ ] Re-running same tracks + rule yields identical event records.
