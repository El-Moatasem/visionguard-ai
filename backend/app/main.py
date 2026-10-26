"""Day 1 health and configuration checks only. No video uploads yet."""
from fastapi import FastAPI

from backend.app.config import MUSE_MODEL, SAM_MODEL, api_configured

app = FastAPI(
    title="VisionGuard AI",
    description="Meta-powered visual safety intelligence — Day 1 model validation",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: does not contact any external service."""
    return {"status": "ok", "stage": "day-1"}


@app.get("/api/v1/meta/status")
def meta_status() -> dict[str, object]:
    """Local configuration check ONLY (not proof an API call succeeds)."""
    return {
        "key_present": api_configured(),
        "models": {"muse": MUSE_MODEL, "sam": SAM_MODEL},
        "authenticated": None,
        "note": "Use the CLI ping and SAM video commands to validate actual API access.",
    }
