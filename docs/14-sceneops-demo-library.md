# SceneOps demo library implementation

The local app remains branded **VisionGuard AI**. The new SceneOps layer generalizes a bounded set of approved object concepts and two deterministic rule types. The catalog is visible in the app even before installing footage.

## Suggested demo verification order

1. Warehouse: select the already validated 5-second 480p clip. Inspect completed SAM result and person/forklift boxes.
2. Parking: open the **parking-car-dwell** synthetic replay (no credits), evaluate `object_in_zone` and inspect start/end frame references. Separately import an authorized parking clip and run real SAM for `car`. **Live car tracking remains unverified.**
3. Retail: run **retail-cart-aisle** synthetic replay, evaluate `shopping_cart` occupancy, then separately import footage with carts. Run a distinct `cardboard_box` rule to evaluate boxes. **Do not claim true aisle obstruction based on 2D occupancy.**
4. Construction: use the **construction-zone-entry** synthetic replay. Note it requires an outside observation followed by inside observations; gaps imply review.
5. Clear aisle and occlusion: exercise existing synthetic fixtures, confirm no invented detections or continuity.
6. Test evidence snapshots and reviewer decisions after a real, completed SAM job, retaining hashes, frame references and local timestamps.

## Local commands

```bash
python -m pytest backend/tests -q
python -m backend.scripts.seed_demo_library --all
# Start backend without --reload during billable work
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# In a separate terminal:
cd frontend && yarn install --frozen-lockfile && yarn dev --webpack
```

**Data provenance:** `benchmarks/replay/*.json` are generated numeric coordinate fixtures, not actual SAM output, videos or proof of model accuracy. A real demo video requires rights-cleared source footage; `samples/`, `var/` and `outputs/` are excluded from Git. There are no downloadable real video assets in this package.

## API

`GET /api/v1/demo/scenarios` is read-only. `POST /api/v1/videos?scenario_id=retail-clearance` tags a video uploaded via multipart form-data with its scenario, preserving it alongside normal uploads. `POST /api/v1/videos/{video_id}/tracking-jobs` accepts optional `{"concepts":["shopping_cart","cardboard_box"]}` and **can incur charges**. Poll job status and optional provisional `/preview` as before. Use deterministic `POST /api/v1/tracking-jobs/{job_id}/evaluate` with `rule_type=object_in_zone`, `concept=shopping_cart`, zone coordinates and a minimum observed duration to evaluate the saved result without new model calls.

**Limits:** single-process local worker, <=25 MiB for model inference, <=30 seconds, <=1080p/30fps, installed FFprobe, no public authentication. No real-time camera alerting, operator recognition, calibrated physical distances, three-minute violation monitoring, or tested real multi-industry tracking claims.
