# VisionGuard Mobile-First Web MVP

Next.js 16 + React 19, mobile-responsive upload and playback, `getUserMedia`
preview + `MediaRecorder` short captures, plus camera-input fallback. This branch
**does not** implement hazard detection, tracking overlays or a native iOS app.

## Local development

```bash
# Terminal A, from repository root:
uvicorn backend.app.main:app --reload --port 8000

# Terminal B:
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend rewrites `/api/backend/*` to
`http://127.0.0.1:8000/api/v1/*`, via `BACKEND_URL` in `frontend/.env.local`.
This avoids browser cross-origin issues and works through a hosted HTTPS
frontend as long as the proxy can reach the backend.

Phone capture (the HTML `capture="environment"` input) is the first fallback.
The live preview/record mode requires HTTPS or localhost and compatible APIs.
WebM clips can be stored/play back, but **not automatically sent to SAM**;
transcode them to H.264 MP4 in a later processing stage.

### Verify TypeScript and build

```bash
npm run typecheck
npm run build
```
