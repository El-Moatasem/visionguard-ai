# Day 2 — FastAPI + Next.js foundation (planned, not implemented)

## Goal
Build a usable local video upload and playback prototype on top of Day 1 verified API access.

## Implementation tasks
- Scaffold `frontend/` using Next.js, TypeScript, Tailwind and an accessible video player.
- Add a FastAPI upload route with strict size/container checks, local opt-in storage, generated safe filenames, MIME sniffing, request body limits, and cleanup strategy.
- Separate upload and analysis jobs; do not run long Meta calls synchronously in user-facing HTTP handlers.
- Expose typed API responses: clip ID, upload status, analysis status, sanitized error details.
- Restrict CORS to local frontend origin, do not log auth tokens or raw video paths.
- Provide clear notice that video is transmitted to Meta when user explicitly initiates analysis.

## Acceptance tests
- [ ] Valid MP4 uploads and plays locally.
- [ ] Invalid/oversized uploads fail safely with 4xx responses.
- [ ] Upload path traversal attempts are rejected.
- [ ] User sees analysis-in-progress/failed states.
- [ ] Original video never goes into public Git history.

## Prioritize
Functional input/output and error handling over branding and user accounts. No database required.
