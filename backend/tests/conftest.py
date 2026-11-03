"""Keep offline backend tests isolated from the developer's PostgreSQL database.

Most tests build temporary filesystem fixtures. If a developer has database mode
turned on in their .env, those tests must not read/write the shared database.
Tests intentionally exercising the database may explicitly enable their own
isolated SQLite URL *inside* their fixture after this one runs.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_database_from_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default every backend test to filesystem mode without a live DB URL."""
    monkeypatch.setenv("VISIONGUARD_USE_DATABASE", "0")
    monkeypatch.delenv("DATABASE_URL", raising=False)
