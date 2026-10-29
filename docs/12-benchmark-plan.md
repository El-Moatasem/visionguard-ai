# Benchmark plan — reproducible safety-review evaluation

**Do not commit videos unless redistribution rights clearly allow it.** Video paths below are placeholders.

Proposed 16 short annotated clips:
- 6 clips with manually verified zone-entry events under a stable camera viewpoint.
- 6 clips without rule violations (including forklift present but not moving).
- 4 challenging clips (partial/full occlusion, crossing pedestrians, camera motion, low light).

Each record in `benchmarks/manifest.example.json` should include a rights/provenance identifier, camera viewpoint description, whether ground truth has been reviewed, timestamp ranges, occlusion flags and the safety zone coordinates when applicable. Keep separate training/development and holdout evaluation clips.

**Metrics**: event-level precision and recall, false positive rate, timestamp error, identity switches, loss/reacquisition statistics, and the percentage requiring human review. Never invent numbers. Empty test results should be labeled not evaluated, not passed.

## Current feature acceptance
- Upload an authorized test clip.
- Verify its container and playback through the browser.
- Confirm the SHA-256 and original filename in the metadata.
- Confirm clips cannot be accidentally committed to Git.

Actual object tracking and safety event metrics are *future feature milestones*, not implemented in this branch.
