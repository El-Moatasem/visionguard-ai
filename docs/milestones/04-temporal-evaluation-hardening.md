# Feature 4 reliability patch: temporal evaluation hardening

**Suggested branch:** `fix/temporal-evaluation` (start from updated `develop`).

Scope:
- Preserve observed events even if later observations in the same actor track are sparse.
- Represent short-gap matches as review candidates rather than assumed continuous hazards.
- Localize uncertainty to observations near the configured zone and keep review items visible alongside events.
- Use seconds for duration thresholds, with FPS-derived required observation spans.
- Use bottom-center of person boxes for approximate floor-zone entry.
- Add safe `unsupported` Muse suggestions; keep reviewer approval and no inferred zone geometry.
- Add normalized video SVG drag-zone editor and reject empty coordinate fields.
- Use validated SAM media metadata for dimensions/FPS only when ffprobe is unavailable and metadata is actually present.
- Add offline SAM frame-stride inspection, new tests and revised synthetic fixture.

Acceptance:
1. `python -m pytest backend/tests -q` green (local offline tests).
2. `python -m backend.scripts.evaluate_fixture` prints `passed: true`.
3. `cd frontend && npm install && npm run typecheck && npm run build` green (run in GitHub Actions or developer machine).
4. An authorized real SAM response demonstrates expected index stride and zone overlays; this is **not yet validated** in this patch.

Compatibility: The API policy field `min_consecutive_frames` is **removed** and replaced by `min_duration_seconds` plus `max_observation_gap_frames`. Responses now include `review_items`, `review_count`, and `has_unresolved_review_items`. The project frontend is updated accordingly; external clients must migrate.
