# Temporal reliability and localized review

## Why this exists

SAM may return sparse observations. Absence of a box in an intervening frame cannot prove that a tracked actor left a region, that an identity survived a full occlusion, or that a hazard remained present. This implementation **never interpolates boxes, treats a gap as evidence, or calculates physical distance**.

## Policy schema

- `min_duration_seconds` (default 0.5): minimum span of the source frames on which the condition is **directly observed**. At constant source FPS, `required_frames = ceil(duration * fps)`.
- `max_observation_gap_frames` (default 2): how many missing indices can connect observed samples into a **review-only candidate**. This **does not** make missing frames observed.
- The tracking normalizer likewise retains provisional fragments over gaps of up to 2 missing frames by default; every missing interval remains in the `gaps` metadata, with identity unverified.
- Both tolerances are heuristics pending testing against actual returned frame indices. They do not establish SAM's sampling semantics.

## Outcomes and evidence

- `events[]`: the same actor or actor pair matched the rule across consecutive source frames **with unchanged fragment IDs**; this is a *potential rule-defined hazard*, not a verified real-world danger.
- `review_items[]`: short-gap spans or identity fragment changes, plus relevant near-zone missing-observation intervals, require human inspection.
- Gaps away from the monitored zone are not promoted into unrelated reviews.
- A result can include **both** observed events and review items. Inspect `has_unresolved_review_items`; do not infer the entire video was unambiguous from the headline `outcome`.
- The person's bounding-box bottom-center is an approximate floor-contact point. The forklift box center is an image-space proxy. Neither is true 3D location.
- For duration, `fps` is required. Without `ffprobe`, validated SAM media metadata is used **if present**. Without trustworthy dimensions/FPS, evaluation fails closed.
- Browser video seeking uses approximate `frame / fps`, not guaranteed frame-exact timestamps.

## Real-video validation

1. Save SAM output from an authorized short clip using the Meta smoke command.
2. Run `python -m backend.scripts.inspect_sam_frames outputs/day1/person/summary.json` and repeat for forklift.
3. Measure step-index distribution and visually check segmentation/tracks against the clip. Missing observations may be caused by model sampling, occlusion, or failed detection. **Do not infer a cause from step size alone.**
4. Evaluate a 0.5 second zone condition at the source FPS; inspect `events[]` and `review_items[]` separately.
5. Repeat with `max_observation_gap_frames=0` and a small bounded value. Record false negatives, false positives, review burden and identity switches in the benchmark report before adjusting defaults.

This feature is for research/demonstration and is not a certified safety monitor or emergency-alert system.
