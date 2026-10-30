# Milestone 4 — Safety Rule Engine

**Branch:** `feature/safety-rule-engine`

## Shipped scope

- Restricted `RuleSpec` and normalized region model with Pydantic field validation.
- Optional, billable Muse Spark 1.3 structured JSON proposal. Explicit reviewer approval.
- Deterministic backend event evaluator for person-zone occupancy and person/forklift-zone co-presence.
- Contiguous-frame dwell threshold; observed track-fragment identity boundaries respected.
- Uncertainty reporting from SAM tracking gaps; no position interpolation.
- FastAPI evaluation and Muse interpretation routes.
- Responsive SafetyRulePanel with manual controls, region presets/coordinates, Muse proposal, event list, approximate seek-to-event and warning text.
- Offline unit/API tests and a synthetic reproducible fixture; no live Meta credits consumed during test suite.

## Acceptance checks

1. Existing video/tracking tests still pass.
2. `python -m pytest backend/tests -q` passes all local tests.
3. `python -m backend.scripts.evaluate_fixture` prints `"passed": true`.
4. `cd frontend && npm run typecheck && npm run build` passes (requires installed Node dependencies).
5. For a real clip, complete a SAM tracking job with a valid Meta key and click Evaluate; verify rule matches against reviewed visual evidence. Live integration remains pending until actually performed.
6. Invalid zone/threshold fails with HTTP 422; no inference without video dimensions; missing observations do not fabricate events.

## Out of scope / following milestone

Persistence of incidents, reviewer decisions, exportable reports and benchmark scorecards belong to `feature/evidence-dashboard` and later validation. Real-time camera streaming and autonomous safety alerts are not implemented. Browser seek times remain approximate until measured against decoded frames. Current API should stay local/private.
