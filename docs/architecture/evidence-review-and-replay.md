# Feature 5 architecture — evidence, human review, synthetic replay

## Overview

```text
Authorized local MP4/MOV -> Meta SAM 3.1 job (live, billable, unverified until run)
  -> Tracking report (actual observations + gaps; approximate frame timing)
  -> Human-approved visual rule -> Deterministic safety evaluator
  -> Immutable evidence snapshot -> Human reviews (append-only audit history)
  -> JSON / printable HTML evidence exports

Separate public-safe path:
  Synthetic numerical fixtures -> Same deterministic safety evaluator
  -> Read-only /replay browser -> ephemeral local decisions and JSON export
```

## Local evidence API

`POST /api/v1/evidence-reports` accepts `{ "tracking_job_id": uuid, "rule": RuleSpec }`.
It reads a completed local SAM tracking job, checks the matching stored video, evaluates the rule,
records a snapshot, and retains the original evaluation even after subsequent human review.
Each snapshot stores a video SHA256 (from the upload metadata), normalized tracking-result SHA256,
model identifier, approximate time-alignment marker, source tracking job ID, reviewer-approved rule,
event and uncertainty lists, and up to 120 selected observed bounding boxes per event.
No video file is included with an export. Selected observations are not a full original model response.

`GET /api/v1/evidence-reports?tracking_job_id=<uuid>` lists local reports.
`GET /api/v1/evidence-reports/{id}` loads the stored snapshot and appended reviews.
`POST /api/v1/evidence-reports/{id}/reviews` validates membership of the event/review item and appends
`confirmed|rejected|unresolved`, reviewer label, note, and UTC timestamp.
`GET /api/v1/evidence-reports/{id}/export.json` exports the full structured snapshot.
`GET /api/v1/evidence-reports/{id}/export.html` downloads a printable, escaped HTML summary.

This is local, unauthenticated, process/filesystem-based research code. There is **no production
identity, authorization, multi-worker concurrency control, or tamper-resistant audit store**. The
review history is logically append-only under normal API use, but not an immutable security log.
Do not present it as audited compliance evidence or expose it on a public host.

## Public synthetic replay

`GET /api/v1/replay/scenarios` lists generated synthetic data scenes.
`GET /api/v1/replay/scenarios/{id}` fetches the fixture and its original rule.
`POST /api/v1/replay/scenarios/{id}/evaluate` executes the **real deterministic evaluator** against
those fixtures and a reviewer-supplied RuleSpec; no SAM or Muse calls, uploads, credentials or persisted
review writes. The browser draws synthetic boxes at simulated frame times; **it does not show video**.
The three included fixtures: warehouse co-presence, occluded person, and clear aisle (negative control).
No real SAM output, licensed footage or real-world benchmark accuracy is included.

The browser's replay review decisions exist only in session memory until exported as local JSON.
To deploy only this safe subset, use `VISIONGUARD_REPLAY_ONLY=1` for the FastAPI server and
`NEXT_PUBLIC_REPLAY_ONLY=1` at Next.js build time. Verify no upload/paid model/local review routes
are registered. Deploy with a managed host and normal public-service hardening (limits, HTTPS, etc.).

## Known limitations / test gates

- SAM live inference and actual sampling cadence remain unverified without an authorized API run.
- Frame-to-playback alignment is approximate (assumes CFR). Outputs are not frame-perfect evidence.
- High volumes/production require a durable queue, storage, authentication and rate limits.
- Local source video never leaves the workstation except via the user's explicit billable SAM invocation.
- Synthetic replay exercises application logic, **not detector accuracy**.
- Only people and forklifts, with two supported rule types, are implemented; boxes/pallet obstruction,
  real-time live inference, calibrated speed and distance are **not supported**.
