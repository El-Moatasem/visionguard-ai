# Days 3–4 — Visual object tracking + overlays (planned)

## Goal
Convert real SAM 3.1 outputs into frontend-friendly temporal track objects and replayable overlays.

## Implementation
- Normalize `person` and `forklift` results separately, creating composite IDs such as `person:0`, `forklift:0` (ID scoped to clip + concept + run).
- Store per-frame bounding boxes/masks and source dimensions. Preserve object IDs, frame index, and optional timestamps; do not assume FPS from frame index without source metadata.
- Encode masks as overlay-friendly geometry or thumbnails; serve synchronized metadata alongside video.
- Add simple overlay canvas scaled correctly to rendered video resolution, letterboxing and aspect ratio.
- Handle objects entering/leaving view, missed frames, camera changes, and partial occlusion without claiming 100% track continuity.
- Record clip SHA-256, Meta model ID, rule version and per-concept prompt for auditability.

## Acceptance tests
- [ ] Boxes line up with the source video at 100% and scaled widths.
- [ ] Tracking remains stable in at least one known-positive video.
- [ ] Object IDs are distinct across categories and runs.
- [ ] Missing data gracefully hides overlays instead of inventing tracks.
- [ ] Unit tests prove pixel-to-display coordinate transforms.
