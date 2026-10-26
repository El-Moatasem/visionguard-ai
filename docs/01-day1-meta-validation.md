# Day 1 — Meta AI account and video-tracking validation

**Objective:** determine if hosted Muse Spark 1.3 and SAM 3.1 actually work in this account, rather than building around an assumption.

## What is implemented in the starter
- `/health` and `/api/v1/meta/status` endpoints (the latter checks only local key presence).
- `python -m backend.scripts.meta_smoke muse` live Muse connection test.
- `python -m backend.scripts.meta_smoke sam --video ... --concept person --concept forklift` file upload, two hosted SAM requests, official parser result summary, decoded SVG masks.
- Unit tests covering offline behavior and protocol handling.

## Tasks to run
1. Set up Python 3.11+, virtual environment, `pip install -r requirements.txt`.
2. Claim event Model API credits if available, set `MODEL_API_KEY` locally, check the account's billing settings. A notification is not a hard cap.
3. `python -m pytest backend/tests -q` → all pass.
4. `python -m backend.scripts.meta_smoke status` → key present true (not a remote check).
5. `python -m backend.scripts.meta_smoke muse` → authenticated completion, record time/error if failing.
6. Use a licensed short MP4 with person and forklift; run SAM CLI (first test with an easily tracked single object if difficult).
7. Inspect actual `summary.json`, track IDs, first/last/visible frames, masks, absent matches, and whether content agrees with the video.
8. Record observations in `docs/01-day1-results-template.md` without adding credentials or sensitive video.

## Passing criteria
- [ ] Muse API key and quota work with an actual call.
- [ ] SAM API accepts video upload and segmentation stream.
- [ ] At least one object class has real boxes and masks and stable object IDs across frames.
- [ ] Any zero detections, parser failures, or performance bottlenecks are documented.
- [ ] No sensitive clips/keys are committed.

## Caveats
- This generator environment did **not** have your key and did not execute the live API tests; you must perform them yourself.
- SAM concept phrases are nouns (`person`, `forklift`), not elaborate prompts; each concept is a separate API call.
- IDs from separate prompt requests need a namespace before combining.
- Videos with heavy occlusions or tiny objects may require choosing a different clip or prompting specific objects with box/point prompts (later).

## Official references
- https://dev.meta.ai/docs/cookbook/sam-api-basics
- https://dev.meta.ai/docs/sam/overview
- https://dev.meta.ai/docs/cookbook/quickstart-chat-completions
