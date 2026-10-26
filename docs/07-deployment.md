# Deployment decision: local → Render → Neon (if needed)

## Day 1: no deployment required
It saves money and complexity to run the Meta API integration locally. A hosted website is not proof SAM works. Run the CLI live tests first.

## Render: recommended after the dashboard works
Set up a Python web service connected to `visionguard-ai` with root directory at repository root:
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Health endpoint: `/health`
- Environment: `MODEL_API_KEY` only if and when the deployed app actually needs it. Do not expose it in frontend code.

**Important**: On Day 1, the hosted API only exposes health/config endpoints; it does not accept uploads or run model analysis. A Render deployment therefore provides no major demo benefit yet. Never expose publicly callable paid model routes without authentication and quotas.

**Render free tier caveats:** services can spin down after inactivity; cold starts may be ~minute; local video or SQLite database files can be lost on restart, spin-down or redeploy. For dependable live judging, consider a paid demo service, warmed demo route, or a recorded backup. Do not promise background workers on free web instances.

## Neon PostgreSQL: defer until actual persistence is required
Use Neon when storing clip metadata, analysis runs, normalized tracks, rules, and review decisions beyond local development. Add SQLAlchemy/SQLModel, Alembic migration, and `DATABASE_URL` via environment variables only when needed. No Neon dependency or hard-coded connection string is included on Day 1.

**Video content belongs in object storage, not relational DB:** choose cloud object storage with signed URLs, retention and deletion mechanisms if deploying a real upload workflow. Short demo clips may be bundled only if rights allow.

## Security and privacy
- Do not enable unrestricted public uploads that automatically spend Meta credits.
- Validate MIME/container/size; scan for malicious content if exposed to public traffic.
- Apply auth, per-user quotas, timeouts, sane request limits, data deletion, secure secrets, and privacy policy before production.
- Never claim automated safety compliance or real-world deployment readiness.

References:
- https://render.com/docs/free
- https://render.com/docs/deploys
- https://neon.tech/docs/introduction/plans
