# Tracking job cancellation — local MVP

## Tracking concepts versus automatic detection

SAM 3.1 is invoked with selected concepts. The UI retains presets for warehouse, parking, retail, and construction. A video/demo preset may suggest concepts, but that is **not universal automatic detection**. Multiple concepts may make separate billable calls. Bounding boxes alone cannot prove a hazard.

## Cancellation endpoints

- `GET /api/v1/tracking-jobs/active` lists jobs active in the current backend process, across all uploaded videos.
- `POST /api/v1/tracking-jobs/{job_id}/cancel` requests cancellation for one active job.
- `POST /api/v1/tracking-jobs/cancel-all` requests cancellation for all active jobs in the current backend process.

States: `queued → running → completed` or `queued/running → cancelling → cancelled`. The **cancelling** state is not terminal: the active slot stays occupied until worker cleanup completes to avoid overlapping billable inference.

The cancellation request attempts to interrupt the local coroutine and close the Meta stream, but a request already sent to Meta may still run or be billed. No refund or remote cancellation is guaranteed. Partial progress data may remain marked provisional; cancelled jobs do not publish a completed tracking report.

This design intentionally uses process-local tracking. It does not cancel work on other replicas or processes. The application has no authentication or tenant isolation. **Do not deploy these endpoints publicly** until per-user authorization and job ownership are implemented. For multi-user deployments, Cancel All must only affect jobs belonging to the authenticated user, not everyone.

## Tests

```bash
python -m pytest backend/tests/test_tracking_cancellation.py -v
python -m pytest backend/tests -q
cd frontend && yarn typecheck && yarn build
```
