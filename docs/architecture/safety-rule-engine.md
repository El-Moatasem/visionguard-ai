# Safety rule engine — architecture (milestone 4)

## Purpose

Translate a reviewer's natural-language safety request into a **constrained, reviewable draft** using Meta Muse Spark 1.3, then evaluate an **approved** geometric policy against a completed SAM 3.1 tracking report using deterministic Python. Muse does not inspect the source video in this milestone and does not declare a hazard. No continuous live-camera processing is claimed.

## System components

```text
Phone capture / MP4 upload -> local video store
  -> POST /videos/{id}/tracking-jobs -> hosted SAM 3.1
  -> tracking_report.py (person/forklift boxes, track fragments, observation gaps)
  -> TrackingViewer / SafetyRulePanel
     + user-defined normalized rectangular zone (fixed coordinates)
     + manual rule OR Muse Spark proposed parameters (explicit human approval)
  -> POST /tracking-jobs/{job_id}/evaluate -> safety_engine.py
  -> events + uncertainty notes -> interactive event review
```

## Inputs and output contracts

- `RuleSpec`: `name`, `rule_type`, `zone` (`x_min`, `y_min`, `x_max`, `y_max` between 0 and 1), and `min_duration_seconds` (0–30s) and bounded `max_observation_gap_frames` (0–30).
- Supported types:
  - `person_in_zone`: observed person **bounding-box center** inside region for N consecutive frames.
  - `person_and_forklift_in_zone`: **same person fragment and same forklift fragment** observed together inside region for N consecutive frames.
- All regions come from the human-reviewed UI. Muse only proposes name/type/threshold/rationale, never coordinates, code, actions, or arbitrary predicates.
- `evaluate_tracking` returns `potential_hazard`, `needs_review`, or `no_rule_match_observed`, event frame ranges, fragment IDs, approximate seconds if FPS is available, and missing-observation uncertainty.
- Output does not certify safety, measure real distances, predict collisions, infer missing frames, classify machine movement, or identify workers across complete occlusions.

## Fail-closed invariants

1. Unknown rule types, extra fields, invalid bounds, or invalid thresholds produce validation errors (HTTP 422).
2. Source frame indices must be consecutive. Two different person IDs/fragments cannot be combined to satisfy a threshold.
3. SAM IDs from different requests are concept-scoped; fragment boundaries cannot be joined implicitly.
4. Gaps are reported as unresolved; never fill missing object boxes.
5. Bounding-box centers are normalized using trusted video width/height from `ffprobe`. If dimensions are unavailable, spatial evaluation is rejected.
6. Muse structured output is validated with Pydantic. Unsupported outputs fail closed and cannot be evaluated automatically.
7. Evaluation makes **no Model API call**. Only the explicit “Interpret with Muse” button incurs token use; SAM analysis is a separate explicitly billable action.

## Trade-offs / future fixes

- Source timestamps are approximate (`frame / nominal fps`); variable frame rate and browser presentation may differ. Build a frame-accurate alignment layer before treating timestamps as admissible incident evidence.
- A center-in-zone rule is simple and testable, but will miss partially overlapping objects; future geometry rules can use masks if benchmarked.
- The local API remains unauthenticated, with process-local tracking jobs and private local files. Do not expose it to the public without authorization, rate limits, retention policy, persistent worker storage and appropriate consent.
- This evaluates only **two spatial patterns**. Collision probability, forklift motion, PPE, fire/smoke and camera-stream alerting are future modules requiring separate validation.

## Meta API reference

- Chat completions: https://dev.meta.ai/docs/cookbook/quickstart-chat-completions
- JSON schema constrained output: https://dev.meta.ai/docs/cookbook/structured-output
