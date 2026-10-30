# Feature - Video overlay and analysis job UI

The mobile-first Next.js viewer provides a player with `person` (teal) and `forklift` (amber) source-pixel boxes. The **Analyze with SAM** button creates a paid job only on explicit click, then polls the job endpoint. Stored videos are untouched by analysis until consented to by the operator.

Coordinates are from the SAM summary boxes, preserved as original image pixels. SVG uses a viewBox with the decoded player's intrinsic width and height and `preserveAspectRatio='xMidYMid meet'` to follow contain-mode scaling. Frame selection currently uses `round(currentTime * ffprobe_fps)`; this can be wrong with VFR video and is shown as **approximate** in the UI. When FPS is not available, box overlays do not show; the track summary remains available.

For judged demonstration footage use short CFR H.264 MP4 clips and manually confirm alignment. Before production, adopt frame-accurate Meta SAM video utilities or a validated frame/timestamp mapping and an authenticated storage/processing service.
