# Stage: Video ingestion & mobile-friendly playback

**Branch**: `feature/video-ingestion` → `develop` → `main` (after QA)

## Implemented in this feature
- Next.js/React mobile-responsive frontend with file selection, native mobile camera file capture, and optional live preview + 15-second MediaRecorder recording.
- FastAPI multipart ingestion with streamed 1 MiB chunks and a 25 MiB default limit.
- Server-side MP4/MOV/WebM container signature check, SHA-256, UUID-based filenames, JSON metadata and local private-by-convention storage.
- Browser video playback (`FileResponse`, including byte ranges) and recent-uploads listing.
- Next.js same-origin `/api/backend/*` rewrite to FastAPI; no Meta credentials in the browser.
- Seven new offline ingestion tests. Existing eight Day 1 tests continue to pass.

## Acceptance commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest backend/tests -q
uvicorn backend.app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

Open http://localhost:3000, upload a **licensed** short MP4, select it from the list, and play it. Test the browser Range response via backend API.

```bash
curl http://127.0.0.1:8000/health
curl -F 'file=@samples/warehouse.mp4' http://127.0.0.1:8000/api/v1/videos
```

## Scope limits and risks
- No hazard analysis, track overlays, incident classification, benchmark score, persistent database, authentication, or public access control is implemented here.
- A correct MP4/WebM container signature does **not** prove full file/codec validity. File magic alone is not a malware scan.
- WebM clips are stored/playable but require conversion to a compatible MP4 before using the existing SAM CLI.
- Mobile `getUserMedia` requires HTTPS or localhost. The `capture` file input is the pragmatic fallback.
- Public deployment is **not safe** until authentication, upload quotas, abuse protection, privacy notices, lifecycle deletion, and object storage are added.
- Original Day 1 Meta smoke scripts are kept; they are not invoked by the upload UI.
- React dependency install and build must be executed locally; this ZIP's backend tests do not certify the frontend runtime.

## Next stage
`feature/object-tracking`: implement ffprobe/FFmpeg normalization, upload-to-SAM job queue, `track_id` namespacing per concept, coordinate normalization, overlay rendering, and explicit occlusion uncertainty states. See `docs/11-tracking-reliability.md`.
