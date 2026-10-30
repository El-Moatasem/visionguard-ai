# Milestone 3 - Object tracking (feature/object-tracking)

## Goal

Connect stored authorized clips to hosted Meta SAM 3.1, normalize returned `person` and `forklift` object boxes across video frames, make identity uncertainty visible and provide a mobile-friendly visual review. This is **not** a hazard detector.

## Implemented

- Explicit user-triggered billable tracking job API, asynchronous local background runner, job polling and saved structured reports.
- MP4/MOV / allowed codec and duration gates; WebM rejection; 25 MiB existing upload guard; one paid job at a time in this prototype.
- Reuse of Day 1 SAM integration to parse box/mask records; existing SVG mask artifacts kept private.
- Separate namespaces for `person` and `forklift` object IDs; frame-order normalization and box validation.
- Fragment splitting on any missing-frame gap; no automatic cross-occlusion reidentification.
- React viewer with tracking status, approximate per-frame box overlays, fragment listing and gap count.
- Offline unit, endpoint and mocked job tests; CI continues to run pytest and frontend build.

## Acceptance gates

- Automated tests pass: `python -m pytest backend/tests -q`.
- Frontend typecheck/build must pass on developer machine/CI.
- With a funded Meta API key and a 5-15 s authorized H.264 clip, user starts tracking, sees `completed`, views named tracks, checks boxes line up, and verifies no false continuity across gaps.
- Empty SAM results show zero tracks rather than invented boxes.
- WebM and unsupported formats fail **before** a billable model request.

## Deferred to later milestones

- Verified browser frame-accurate overlay synchronization, mask visualization, cross-request association, calibration, confidence reporting where provided.
- Muse Spark interpretation, deterministic zone hazard engine, incident severity and explanations.
- Persistent task queue/database, authentication, remote deployment, video retention policy and benchmark scorecards.

## Testing posture

Automated offline tests run now on every commit. The planned full manual benchmark may follow all five feature branches, but a basic **billable smoke test** before adding rules is recommended to surface API integration or video codec issues earlier. No live Meta request was executed during package generation.
