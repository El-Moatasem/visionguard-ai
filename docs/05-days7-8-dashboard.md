# Days 7–8 — Evidence dashboard (planned)

## Goal
Deliver a judge-friendly, evidence-backed human review interface.

## Features
- Clip player with timestamp seek and masks/boxes overlays.
- Reviewer-defined zones, explicit rule configuration and validation states.
- Event timeline with thumbnails, tracked object IDs and `candidate`/`reviewed` statuses.
- Explainable report: what was observed, why the deterministic rule fired, what remains uncertain, source clip hash, model/rule version.
- JSON export and optional PDF only after the main product works.
- Honest empty results and model-error states.

## Optional Neon database entities
`clips`, `analysis_runs`, `object_tracks`, `rules`, `candidate_events`, `reviews`.

Do not store raw video in Neon. Consider object storage or demo-only local files with a retention policy. Avoid user login and complex multi-tenancy until the core demo is stable.

## Acceptance tests
- [ ] A judge can find any flagged event and replay evidence in 2 clicks.
- [ ] No fabricated status/bbox/timestamps in production mode.
- [ ] UI handles a 0-event clip cleanly.
- [ ] Incident reports distinguish automated candidate detection from human judgment.
