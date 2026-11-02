"""Create the initial Neon/PostgreSQL tables explicitly; do not run on app startup."""
from __future__ import annotations

from backend.app.services import db_store


def main() -> None:
    if not db_store.enabled():
        raise SystemExit("Set VISIONGUARD_USE_DATABASE=1 and DATABASE_URL before initializing")
    db_store.initialize()
    if not db_store.check():
        raise SystemExit("Database connectivity test failed")
    print("VisionGuard database tables initialized and connection verified.")


if __name__ == "__main__":
    main()
