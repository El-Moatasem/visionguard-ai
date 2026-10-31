# Milestone 5 — Evidence dashboard and read-only synthetic replay

## Delivered in the Feature 5 package

- Local filesystem evidence snapshots of completed tracking jobs + applied rule.
- Event and uncertainty timelines with video seek and human confirm/reject/unresolved actions.
- Append-only API review decisions (not an independently tamper-resistant log).
- JSON evidence export and printable HTML with escaped user content.
- Three reproducible, synthetic tracking fixtures and real deterministic offline rule evaluation.
- Browser SVG replay scene with frame slider, playback, selectable rule and temporary review decisions.
- Replay-only FastAPI/Next.js deployment flags that disable local upload, paid Meta calls, and review writes.
- Automated backend endpoint tests and synthetic replay checks.

## Acceptance / readiness gates

- [x] Offline tests for event report, reviews, export, XSS escaping, replay endpoints.
- [x] Synthetic fixture includes normal hazard, occlusion uncertainty and negative control.
- [x] Playback and evidence UI code packaged (live browser QA still required).
- [ ] Frontend complete typecheck and Next.js production build in GitHub Actions.
- [ ] Live SAM 3.1 frame output checked, including `inspect_sam_frames.py` stride inspection.
- [ ] Muse Spark real rule drafting confirmed using authorized account.
- [ ] Real licensed source clips selected and annotated with actual event ground truth.
- [ ] Actual-video end-to-end smoke test and reviewer workflow recorded.
- [ ] Hosted replay-only demo verified on a public HTTPS URL, if submission needs it.
- [ ] Final <3-minute video and hackathon provenance disclosure verified with organizers.

This branch **does not implement** emergency-exit obstruction / box detection, low-latency real-time
video inference, new object categories, or calibrated collision prediction.
