
"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import SafetyRulePanel from "@/components/SafetyRulePanel";
import EvidenceDashboard from "@/components/EvidenceDashboard";

import {
  fetchTrackingJob,
  fetchTrackingJobs,
  fetchTrackingResult,
  fetchTrackingPreview,
  playbackUrl,
  startTracking,
  type TrackingJob,
  type TrackingReport,
  type TrackingBox,
  type VideoItem,
  type SafetyZone,
  type RuleSpec,
} from "@/lib/api";

const PALETTE: Record<string, string> = {
  person: "#45d9b7",
  forklift: "#f5bb77",
};

const POLL_INTERVAL_MS = 2500;
const SAM_MAX_BYTES = 25 * 1024 * 1024;

type Point = { x: number; y: number };

export default function TrackingViewer({ video }: { video: VideoItem }) {
  const element = useRef<HTMLVideoElement>(null);

  const [seconds, setSeconds] = useState(0);
  const [safetyZone, setSafetyZone] = useState<SafetyZone>({
    name: "Operating aisle",
    x_min: 0.2,
    y_min: 0.2,
    x_max: 0.8,
    y_max: 0.8,
  });

  const [drawing, setDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<Point | null>(null);
  const [drawCurrent, setDrawCurrent] = useState<Point | null>(null);

  const [dimensions, setDimensions] = useState({
    width: 0,
    height: 0,
  });

  const [job, setJob] = useState<TrackingJob | null>(null);
  const [report, setReport] = useState<TrackingReport | null>(null);
  const [preview, setPreview] = useState<TrackingReport | null>(null);

  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [approvedRule, setApprovedRule] = useState<RuleSpec | null>(null);

  const isActive =
    job?.status === "queued" || job?.status === "running";

  // 1. Load the most recent tracking job for the selected video.
  useEffect(() => {
    let current = true;

    setSeconds(0);
    setReport(null);
    setPreview(null);
    setJob(null);
    setError("");
    setDimensions({ width: 0, height: 0 });
    setDrawing(false);
    setDrawStart(null);
    setDrawCurrent(null);
    setApprovedRule(null);

    void fetchTrackingJobs(video.id)
      .then((jobs) => {
        if (current) {
          setJob(jobs[0] ?? null);
        }
      })
      .catch((err: unknown) => {
        if (current) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not read tracking jobs"
          );
        }
      });

    return () => {
      current = false;
    };
  }, [video.id]);

  // 2. Poll job status ONLY while queued or running.
  // Stop polling when completed, failed, or interrupted.
  useEffect(() => {
    if (!job || !isActive) return;

    let current = true;

    const tick = () => {
      void fetchTrackingJob(job.id)
        .then((fresh) => {
          if (!current) return;
          setJob(fresh);
          setError("");
        })
        .catch((err: unknown) => {
          if (!current) return;
          setError(
            err instanceof Error
              ? err.message
              : "Could not poll tracking job"
          );
        });
    };

    tick();

    const timer = window.setInterval(
      tick,
      POLL_INTERVAL_MS
    );

    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status, isActive]);

  // 3. Fetch progressive tracking snapshots ONLY while active.
  // A missing preview (404) is normal before the first observation.
  // Never repeatedly poll an interrupted or failed job.
  useEffect(() => {
    if (!job || !isActive) return;

    let current = true;

    const tick = () => {
      void fetchTrackingPreview(job.id)
        .then((data) => {
          if (current && data) {
            setPreview(data);
          }
        })
        .catch(() => {
          // Status polling handles connection failures.
          // Preview availability must not fail the job.
        });
    };

    tick();

    const timer = window.setInterval(
      tick,
      POLL_INTERVAL_MS
    );

    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status, isActive]);

  // 4. Recover available partial observations from a failed
  // or interrupted job ONCE after reopening the video.
  useEffect(() => {
    if (
      !job ||
      !["failed", "interrupted"].includes(job.status)
    ) {
      return;
    }

    let current = true;

    void fetchTrackingPreview(job.id)
      .then((data) => {
        if (current && data) {
          setPreview(data);
        }
      })
      .catch(() => {
        // A failed job may have no saved preview.
        // Do not retry or spam 404 requests.
      });

    return () => {
      current = false;
    };
  }, [job?.id, job?.status]);

  // 5. Load the final validated result only after completion.
  useEffect(() => {
    if (!job || job.status !== "completed") return;

    let current = true;

    void fetchTrackingResult(job.id)
      .then((data) => {
        if (current) {
          setReport(data);
          setError("");
        }
      })
      .catch((err: unknown) => {
        if (current) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not fetch tracking result"
          );
        }
      });

    return () => {
      current = false;
    };
  }, [job?.id, job?.status]);

  // 6. Synchronize overlays with decoded video-frame timing.
  useEffect(() => {
    const player = element.current;

    if (!player || !player.requestVideoFrameCallback) return;

    let cancelled = false;
    let requestId = 0;

    const onFrame = (
      _now: number,
      metadata: VideoFrameCallbackMetadata
    ) => {
      if (cancelled) return;

      setSeconds(metadata.mediaTime);
      requestId = player.requestVideoFrameCallback(onFrame);
    };

    requestId = player.requestVideoFrameCallback(onFrame);

    return () => {
      cancelled = true;
      player.cancelVideoFrameCallback?.(requestId);
    };
  }, [video.id]);

  // 7. Start a new explicit, billable SAM analysis.
  async function analyze() {
    if (submitting || isActive) return;

    setSubmitting(true);
    setError("");
    setReport(null);
    setPreview(null);
    setApprovedRule(null);

    try {
      const created = await startTracking(video.id);
      setJob(created);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Tracking request failed"
      );
    } finally {
      setSubmitting(false);
    }
  }

  function svgPoint(
    event: ReactPointerEvent<SVGSVGElement>
  ): Point | null {
    const svg = event.currentTarget;
    const matrix = svg.getScreenCTM();

    if (!matrix || !dimensions.width || !dimensions.height) {
      return null;
    }

    const p = svg.createSVGPoint();
    p.x = event.clientX;
    p.y = event.clientY;

    const actual = p.matrixTransform(matrix.inverse());

    return {
      x: Math.min(
        1,
        Math.max(0, actual.x / dimensions.width)
      ),
      y: Math.min(
        1,
        Math.max(0, actual.y / dimensions.height)
      ),
    };
  }

  function onDrawStart(
    event: ReactPointerEvent<SVGSVGElement>
  ) {
    if (!drawing) return;

    const p = svgPoint(event);
    if (!p) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    setDrawStart(p);
    setDrawCurrent(p);
  }

  function onDrawMove(
    event: ReactPointerEvent<SVGSVGElement>
  ) {
    if (drawing && drawStart) {
      setDrawCurrent(svgPoint(event));
    }
  }

  function onDrawEnd(
    event: ReactPointerEvent<SVGSVGElement>
  ) {
    if (!drawing || !drawStart) return;

    const p = svgPoint(event);

    if (
      event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.releasePointerCapture(
        event.pointerId
      );
    }

    if (p) {
      const zone: SafetyZone = {
        name: "Drawn safety zone",
        x_min: Math.min(drawStart.x, p.x),
        y_min: Math.min(drawStart.y, p.y),
        x_max: Math.max(drawStart.x, p.x),
        y_max: Math.max(drawStart.y, p.y),
      };

      if (
        zone.x_max - zone.x_min >= 0.02 &&
        zone.y_max - zone.y_min >= 0.02
      ) {
        setSafetyZone(zone);
        setDrawing(false);
        setApprovedRule(null);
      }
    }

    setDrawStart(null);
    setDrawCurrent(null);
  }

  // 8. Index boxes by frame for efficient video playback.
  // Never interpolate missing observations.
  const displayReport = report ?? preview;

  const boxesByFrame = useMemo(() => {
    const index = new Map<number, TrackingBox[]>();

    for (const box of displayReport?.boxes ?? []) {
      const items = index.get(box.frame) ?? [];
      items.push(box);
      index.set(box.frame, items);
    }

    return index;
  }, [displayReport]);

  const fps =
    displayReport?.media_probe.fps ??
    displayReport?.media_metadata?.fps;

  const frame = fps ? Math.round(seconds * fps) : null;

  const overlays =
    frame === null ? [] : boxesByFrame.get(frame) ?? [];

  const showOverlay = Boolean(
    displayReport &&
      frame !== null &&
      dimensions.width &&
      dimensions.height
  );

  const tooLargeForSam = video.size_bytes > SAM_MAX_BYTES;

  const busy = submitting || isActive;

  return (
    <div className="tracking-viewer">
      <div className="tracking-player">
        <video
          key={video.id}
          ref={element}
          src={playbackUrl(video)}
          controls
          playsInline
          loop={busy}
          preload="metadata"
          className="player"
          onTimeUpdate={(e) =>
            setSeconds(e.currentTarget.currentTime)
          }
          onLoadedMetadata={(e) =>
            setDimensions({
              width: e.currentTarget.videoWidth,
              height: e.currentTarget.videoHeight,
            })
          }
        />

        {showOverlay && (
          <svg
            className={`tracking-overlay ${
              drawing ? "tracking-draw-mode" : ""
            }`}
            viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
            preserveAspectRatio="xMidYMid meet"
            aria-label="Approximate SAM tracking boxes"
            onPointerDown={onDrawStart}
            onPointerMove={onDrawMove}
            onPointerUp={onDrawEnd}
            onPointerCancel={() => {
              setDrawStart(null);
              setDrawCurrent(null);
            }}
          >
            {report && (
              <rect
                x={safetyZone.x_min * dimensions.width}
                y={safetyZone.y_min * dimensions.height}
                width={
                  (safetyZone.x_max - safetyZone.x_min) *
                  dimensions.width
                }
                height={
                  (safetyZone.y_max - safetyZone.y_min) *
                  dimensions.height
                }
                fill="#e8b85a"
                fillOpacity="0.07"
                stroke="#e8b85a"
                strokeDasharray="12 8"
                strokeWidth={3}
              />
            )}

            {drawStart && drawCurrent && (
              <rect
                x={
                  Math.min(drawStart.x, drawCurrent.x) *
                  dimensions.width
                }
                y={
                  Math.min(drawStart.y, drawCurrent.y) *
                  dimensions.height
                }
                width={
                  Math.abs(drawStart.x - drawCurrent.x) *
                  dimensions.width
                }
                height={
                  Math.abs(drawStart.y - drawCurrent.y) *
                  dimensions.height
                }
                fill="#45d9b7"
                fillOpacity="0.16"
                stroke="#45d9b7"
                strokeWidth={4}
              />
            )}

            {overlays.map((item) => (
              <g
                key={`${item.track_id}:${item.frame}`}
              >
                <rect
                  x={item.box.left}
                  y={item.box.top}
                  width={
                    item.box.right - item.box.left
                  }
                  height={
                    item.box.bottom - item.box.top
                  }
                  fill="none"
                  stroke={
                    PALETTE[item.concept] ?? "white"
                  }
                  strokeWidth={Math.max(
                    2,
                    dimensions.width / 450
                  )}
                />

                <text
                  x={item.box.left}
                  y={Math.max(14, item.box.top - 7)}
                  fill={
                    PALETTE[item.concept] ?? "white"
                  }
                  fontSize={Math.max(
                    12,
                    dimensions.width / 70
                  )}
                  fontWeight="bold"
                >
                  {item.fragment_id}
                </text>
              </g>
            ))}
          </svg>
        )}
      </div>

      <div className="tracking-tools">
        <div className="tracking-tools-header">
          <div>
            <span className="eyebrow">
              03 / VISUAL TRACKING
            </span>
            <h3>Meta SAM 3.1 analysis</h3>
          </div>

          <span
            className={`tracking-state ${
              job?.status === "completed"
                ? "is-ok"
                : ""
            }`}
          >
            {job?.status ?? "Not analyzed"}
          </span>
        </div>

        <p className="helper">
          Analyze this clip for <strong>people</strong> and{" "}
          <strong>forklifts</strong>. This sends authorized footage
          to Meta and consumes API credits. Not real-time
          monitoring or certified danger detection.
        </p>

        <button
          type="button"
          className="button button-primary"
          disabled={
            busy ||
            !video.sam_compatible_container ||
            tooLargeForSam
          }
          onClick={() => void analyze()}
        >
          {busy
            ? "Analyzing…"
            : job?.status === "completed"
              ? "Run fresh analysis (billable)"
              : "Analyze with SAM (billable)"}
        </button>

        {!video.sam_compatible_container && (
          <p className="error">
            WebM is not supported by SAM. Convert to
            H.264 MP4 first.
          </p>
        )}

        {tooLargeForSam && (
          <p className="error">
            This video exceeds the 25 MiB SAM analysis
            limit. Uploads may be up to 100 MiB, but clips
            must be compressed before inference.
          </p>
        )}

        {job && (
          <p className="helper" role="status">
            {job.message}
          </p>
        )}

        {preview && !report && (
          <p className="helper" role="status">
            Live progress preview: {preview.box_count}{" "}
            observed boxes so far.
            {job?.status === "failed" ||
            job?.status === "interrupted"
              ? " Partial observations were preserved. Final safety evaluation is unavailable."
              : " Play or seek the video to see boxes. Final safety evaluation is unavailable until completion."}
          </p>
        )}

        {job?.failure_type && (
          <p className="error" role="alert">
            Failure type: {job.failure_type}. See FastAPI
            traceback for the underlying cause.
          </p>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {report && (
          <>
            <div className="tracking-metrics">
              <div>
                <strong>{report.track_count}</strong>
                <small>Tracks</small>
              </div>
              <div>
                <strong>{report.box_count}</strong>
                <small>Observed boxes</small>
              </div>
              <div>
                <strong>{report.gap_count}</strong>
                <small>Occlusion / missing-frame gaps</small>
              </div>
            </div>

            <p className="helper">
              Frame timing is approximate and not frame-accurate
              evidence. Short gaps can retain provisional fragment
              association, but identity is unverified and missing
              positions are never interpolated. Rule-based
              screening is below.
            </p>

            <div className="tracking-track-list">
              {report.tracks.slice(0, 15).map((track) => (
                <div
                  className="tracking-track"
                  key={track.track_id}
                >
                  <strong>{track.track_id}</strong>
                  <span>
                    {track.observed_frames} observed frames ·{" "}
                    {track.fragment_count} fragment(s)
                  </span>

                  {track.has_uncertain_identity_continuity && (
                    <span className="tracking-warning">
                      Identity continuity unverified
                    </span>
                  )}
                </div>
              ))}

              {report.tracks.length === 0 && (
                <p className="helper">
                  No boxes matched the requested concepts.
                  This can be a valid SAM result.
                </p>
              )}
            </div>

            {job?.status === "completed" && (
              <SafetyRulePanel
                key={job.id}
                jobId={job.id}
                zone={safetyZone}
                onZoneChange={(z) => {
                  setSafetyZone(z);
                  setApprovedRule(null);
                }}
                drawing={drawing}
                onDrawingChange={setDrawing}
                onEvaluated={(_, rule) =>
                  setApprovedRule(rule)
                }
                onSeek={(time) => {
                  if (element.current) {
                    element.current.currentTime = time;
                    setSeconds(time);
                  }
                }}
              />
            )}

            {job?.status === "completed" && (
              <EvidenceDashboard
                key={`evidence-${job.id}`}
                jobId={job.id}
                rule={approvedRule}
                onSeek={(time) => {
                  if (element.current) {
                    element.current.currentTime = time;
                    setSeconds(time);
                  }
                }}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
