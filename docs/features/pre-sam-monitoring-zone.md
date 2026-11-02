# Pre-SAM monitoring zone (VisionGuard AI)

## Workflow

1. Upload video or prepare a SAM-compatible derivative first. An FFmpeg derivative gets its own video ID; drawing a zone on the original does not automatically copy it to a different video.
2. Pause the video, then click **Draw monitoring zone** beneath the player. Drag over the video image, not letterbox bars. The yellow rectangle is the reviewer-selected, normalized monitoring area.
3. Select the tracking preset. The person-only construction preset uses one billable SAM concept and defaults to the person zone-entry rule on a successful result.
4. Click **Analyze with SAM (billable)**. SAM receives the whole selected video, not a cropped region. The zone is retained in the current browser session and is evaluated only after the model has completed successfully.
5. In **Safety Intelligence**, select the intended rule and evaluate the saved tracking result (no extra SAM call). You can edit or redraw the zone after analysis without paying for new tracking.
6. Export evidence from completed analysis. If a remote stream fails, a provisional preview is not valid final evidence.

## Caveats

- **Drawing before SAM does not reduce SAM cost, upload size, video length, or processing time**. The zone affects the deterministic rule engine only.
- Zone coordinates live in the page's React state and are **not persisted automatically across page reloads**, and they are not sent to Meta.
- For `object_zone_entry`, a worker must be observed outside the zone and subsequently inside it. Someone already inside at the first observed frame is not an observed entry.
- When a zone changes, prior evaluations are invalidated. If you have saved evidence for an earlier zone, that historical snapshot remains a distinct evidence record.
- This release does **not** install or enable any database. Existing video/job/evidence persistence remains whatever your checkout uses.
- The constructed source ZIP is built from the current committed Git HEAD plus patched frontend files (default). Uncommitted database changes are excluded. To include every currently modified source, pass `--snapshot working` explicitly and review the diff first.
