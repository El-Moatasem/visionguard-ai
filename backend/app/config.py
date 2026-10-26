"""Day 1 configuration. Secrets are read at execution time, not at import time."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
META_BASE_URL = "https://api.meta.ai/v1"
MUSE_MODEL = "muse-spark-1.3"
SAM_MODEL = "sam-3.1"


def model_key() -> str:
    key = os.getenv("MODEL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MODEL_API_KEY is missing. Configure your local .env or shell environment.")
    return key


def api_configured() -> bool:
    return bool(os.getenv("MODEL_API_KEY", "").strip())
