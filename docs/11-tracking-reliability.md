# Tracking reliability is a first-class design requirement

The `feature/video-ingestion` branch does **not** claim to solve tracking. It lays the groundwork for systematic evaluation.

## Next-stage occlusion design
- Normalize SAM tracking data per `(video_id, concept, object_id)`; IDs from independent prompts cannot be assumed globally unique.
- For a given track, record observed frames and gaps without extrapolating into unverifiable positions.
- State machine: `OBSERVED` → `LOST_SHORT` → (`REACQUIRED` if evidence supports it, otherwise `UNRESOLVED`/new track).
- Evaluate associations with explicit bounds on time gap, motion and overlap; uncertain identities must not be silently stitched together.
- Distinguish detected objects, uncertain occupancy, and a confirmed deterministic *rule trigger*. Do not label uncertain events as accidents.

## Evaluate before creating safety alerts
- Full and partial occlusion; two workers crossing; worker leaving frame and returning; fast forklift movements; poor lighting; camera movement; absent objects.
- Track how often identity switches occur; how many annotated events are missed; event precision and recall; false alerts per clip; latency and ambiguous-event rate.
- A camera-zone rule requires the configured polygon in **image coordinates** and a coherent camera viewpoint; it is not a metric-distance or collision-risk measurement.

## Sample benchmark manifest
See `benchmarks/manifest.example.json` for annotation schema. Fill labels using inspected licensed/synthetic clips, not guesses.
