# Synthetic replay (read-only demonstration)

Open `/replay` to select a hand-authored numerical scenario and evaluate the **same**
`evaluate_tracking` function used for genuine SAM results. The SVG scene draws generated tracks and
an operating zone. It is **not video footage**, **not a camera stream**, and **not actual model output**.

Supported scenes:

1. Worker and forklift in the same configured area — an observed co-presence event.
2. Worker briefly unobserved, forklift still visible — two observed sequences plus localized review.
3. Worker stays outside the monitored area — negative example with no matching observed event.

Adjust the supported rule type or minimum duration to see the evaluator respond. Seek to events and
select human-review statuses. These replay-only decisions are browser-memory values until manually
exported to JSON; there is no server persistence in replay mode.

Running `VISIONGUARD_REPLAY_ONLY=1` registers only replay endpoints and status/health routes.
Set `NEXT_PUBLIC_REPLAY_ONLY=1` when building the public frontend to direct the homepage to the
replay experience. Public deployment must not use the local default upload and evidence routes.

To create a **real** judge replay later, gather a licensed clip, complete a successful live SAM call,
inspect and archive actual model results, and seek organizer approval for sharing that footage and data.
Do not silently replace fixture labels or imply real inference from synthetic samples.
