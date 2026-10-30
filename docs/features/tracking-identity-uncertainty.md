# Feature - Tracking identity and occlusion uncertainty

SAM object ordinals are useful within a result but not proof of physical identity after full occlusion, entry/exit, or reappearance. This branch deliberately avoids visually persuasive but unsupported interpolation.

- **Observed:** Valid bounding box returned on frame N. Record `concept:object_id` and coordinates.
- **Observed sequence:** Consecutive frames N, N+1 form one continuous observed fragment.
- **Gap:** If next observation occurs at M > N+1, emit `{after_frame:N, before_frame:M, missing_frames:M-N-1, identity_continuity:'unverified'}`.
- **Post-gap fragment:** Assign new local fragment suffix `#1`, `#2` even if model ordinal is unchanged.
- **Disappeared entirely:** No further observations; do not invent trajectory.
- **No match:** Zero tracks is an allowed outcome, not a model failure.

This does **not** detect whether a gap is caused by occlusion versus SAM omission. UI labels 'occlusion / missing-frame gap' rather than confidently classifying the cause.

Future benchmark scenarios: two people crossing, worker fully blocked by forklift, forklift exiting and re-entering, object near edge of field, camera motion, dark clip, non-event video. Human annotated ground truth is needed before any measured recovery score can be claimed.
