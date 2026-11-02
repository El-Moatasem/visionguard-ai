"""VisionGuard local hackathon API (no production authentication yet)."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.videos import router as videos_router
from backend.app.api.video_preparation import router as video_preparation_router
from backend.app.api.tracking import router as tracking_router
from backend.app.api.safety import router as safety_router
from backend.app.api.evidence import router as evidence_router
from backend.app.api.replay import router as replay_router
from backend.app.api.demo_catalog import router as demo_router
from backend.app.api.demo_catalog import router as demo_router
from backend.app.config import MUSE_MODEL, SAM_MODEL, api_configured

app = FastAPI(
    title="VisionGuard AI",
    description="Meta-powered visual safety intelligence — zone-based rule evaluation MVP",
    version="0.5.0",
)

# Local frontend uses a Next.js same-origin rewrite; keep CORS restricted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
# Deploy an isolated public replay only with VISIONGUARD_REPLAY_ONLY=1.
# Never expose unauthenticated upload, paid inference, or local review endpoints.
REPLAY_ONLY = os.getenv("VISIONGUARD_REPLAY_ONLY", "0") == "1"
if not REPLAY_ONLY:
    app.include_router(videos_router)
    app.include_router(video_preparation_router)
    app.include_router(tracking_router)
    app.include_router(safety_router)
    app.include_router(evidence_router)
app.include_router(replay_router)
app.include_router(demo_router)
app.include_router(demo_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "safety-rule-engine"}


@app.get("/api/v1/meta/status")
def meta_status() -> dict[str, object]:
    """Local configuration check ONLY (not proof remote Meta calls succeed)."""
    if REPLAY_ONLY:
        return {"key_present": False, "models": {}, "authenticated": None, "note": "Public replay mode; model access disabled."}
    return {
        "key_present": api_configured(),
        "models": {"muse": MUSE_MODEL, "sam": SAM_MODEL},
        "authenticated": None,
        "note": "Use the CLI ping and SAM video commands to validate actual API access.",
    }
