# SAM-ready clip preparation

## What it fixes

The local video library accepts uploads up to 100 MiB, but the app's *SAM adapter* deliberately limits billable inference clips to **25 MiB**, **30 seconds**, **1080p**, and **30 FPS**. The backend also requires FFprobe to extract usable frame rate and dimensions. Raising the inference guard is not equivalent to proving Meta supports larger inputs.

The Studio now has a **Prepare for SAM** section. A user selects an uploaded source, a start time and a duration (up to 30 seconds), then creates an H.264 MP4 derivative. The original stays in the library. The derivative is stored under a different video ID and is automatically selected so its playback and SAM observations correspond to the **same file**. No billable Meta call happens during preparation.

## API and integrity

`POST /api/v1/videos/{video_id}/prepare-for-sam`

```json
{"start_seconds": 0, "duration_seconds": 20}
```

This returns a normal `VideoItem` with added fields:

- `analysis_source_video_id` — parent uploaded video ID
- `analysis_source_sha256` — hash of the untouched source
- `analysis_start_seconds` — source offset of the derivative
- `analysis_duration_seconds` — actual output duration

The transcode tries 480p/12FPS, 360p/10FPS, then 240p/8FPS if needed to fit the existing 25 MiB guard; all outputs are validated with FFprobe. It removes audio, which is not used for SAM tracking. A damaged file or a time window beyond the source's duration produces a 4xx response and does **not** start SAM.

## Running locally

Install FFmpeg and FFprobe, or set `FFMPEG_BIN=/opt/local/bin/ffmpeg` and `FFPROBE_BIN=/opt/local/bin/ffprobe` in the root `.env`. Restart FastAPI. Open a video in `/studio`, choose **Prepare MP4**, wait for the new clip to appear, and then press **Analyze with SAM**. Running inference remains a separate explicit paid action.

## Important limitations

- Up to **100 MiB original upload** is supported; the 25 MiB inference guard still exists.
- This is **segment analysis**, not automatically processing every second of an arbitrary video. A 37-second recording needs two separate segments if the whole recording must be covered.
- This is a local prototype without public authentication, upload malware scanning, resource quotas, or durable queues. Do not publicly expose this endpoint without hardening.
- The first supported tracking concepts depend on the user or demo selection. Do not imply automatic universal object recognition.
- No hidden or automatic trimming: the selected start and duration are explicit, and source lineage is retained.
