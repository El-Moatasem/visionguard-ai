"""VisionGuard local hackathon API (no production authentication yet)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.videos import router as videos_router
from backend.app.config import MUSE_MODEL, SAM_MODEL, api_configured

app = FastAPI(
    title="VisionGuard AI",
    description="Meta-powered visual safety intelligence — video ingestion MVP",
    version="0.2.0",
)

# Local frontend uses a Next.js same-origin rewrite; keep CORS restricted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(videos_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "video-ingestion"}


@app.get("/api/v1/meta/status")
def meta_status() -> dict[str, object]:
    """Local configuration check ONLY (not proof remote Meta calls succeed)."""
    return {
        "key_present": api_configured(),
        "models": {"muse": MUSE_MODEL, "sam": SAM_MODEL},
        "authenticated": None,
        "note": "Use the CLI ping and SAM video commands to validate actual API access.",
    }
