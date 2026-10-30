"use client";

import { useEffect, useRef, useState } from "react";
import {
  fetchTrackingJob, fetchTrackingJobs, fetchTrackingResult, playbackUrl,
  startTracking, type TrackingJob, type TrackingReport, type VideoItem,
} from "@/lib/api";

const PALETTE: Record<string, string> = { person: "#45d9b7", forklift: "#f5bb77" };

export default function TrackingViewer({ video }: { video: VideoItem }) {
  const element = useRef<HTMLVideoElement>(null);
  const [seconds, setSeconds] = useState(0);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [job, setJob] = useState<TrackingJob | null>(null);
  const [report, setReport] = useState<TrackingReport | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let current = true;
    setSeconds(0);
    setReport(null);
    setJob(null);
    setError("");
    void fetchTrackingJobs(video.id).then((jobs) => {
      if (current) setJob(jobs[0] ?? null);
    }).catch((err: unknown) => {
      if (current) setError(err instanceof Error ? err.message : "Could not read tracking jobs");
    });
    return () => { current = false; };
  }, [video.id]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let current = true;
    const tick = () => { void fetchTrackingJob(job.id).then((fresh) => {
      if (current) setJob(fresh);
    }).catch((err: unknown) => {
      if (current) setError(err instanceof Error ? err.message : "Could not poll tracking job");
    }); };
    const timer = window.setInterval(tick, 2500);
    tick();
    return () => { current = false; window.clearInterval(timer); };
  }, [job?.id, job?.status]);

  useEffect(() => {
    if (job?.status !== "completed") return;
    let current = true;
    void fetchTrackingResult(job.id).then((data) => {
      if (current) setReport(data);
    }).catch((err: unknown) => {
      if (current) setError(err instanceof Error ? err.message : "Could not fetch tracking result");
    });
    return () => { current = false; };
  }, [job?.id, job?.status]);

  async function analyze() {
    setSubmitting(true);
    setError("");
    setReport(null);
    try { setJob(await startTracking(video.id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Tracking request failed"); }
    finally { setSubmitting(false); }
  }

  const fps = report?.media_probe.fps;
  const frame = fps ? Math.round(seconds * fps) : null;
  const overlays = frame === null ? [] : (report?.boxes ?? []).filter((box) => box.frame === frame);
  const showOverlay = Boolean(report && frame !== null && dimensions.width && dimensions.height);
  const busy = submitting || job?.status === "running" || job?.status === "queued";

  return <div className="tracking-viewer">
    <div className="tracking-player">
      <video key={video.id} ref={element} src={playbackUrl(video)} controls playsInline preload="metadata"
        className="player" onTimeUpdate={(e) => setSeconds(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDimensions({ width: e.currentTarget.videoWidth, height: e.currentTarget.videoHeight })}/>
      {showOverlay && <svg className="tracking-overlay" viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        preserveAspectRatio="xMidYMid meet" aria-label="Approximate SAM tracking boxes">
        {overlays.map((item) => <g key={`${item.track_id}:${item.frame}`}>
          <rect x={item.box.left} y={item.box.top} width={item.box.right - item.box.left}
            height={item.box.bottom - item.box.top} fill="none" stroke={PALETTE[item.concept] ?? "white"}
            strokeWidth={Math.max(2, dimensions.width / 450)} />
          <text x={item.box.left} y={Math.max(14, item.box.top - 7)} fill={PALETTE[item.concept] ?? "white"}
            fontSize={Math.max(12, dimensions.width / 70)} fontWeight="bold">{item.fragment_id}</text>
        </g>)}
      </svg>}
    </div>
    <div className="tracking-tools">
      <div className="tracking-tools-header"><div><span className="eyebrow">03 / VISUAL TRACKING</span><h3>Meta SAM 3.1 analysis</h3></div>
      <span className={`tracking-state ${job?.status === "completed" ? "is-ok" : ""}`}>{job?.status ?? "Not analyzed"}</span></div>
      <p className="helper">Analyze this clip for <strong>people</strong> and <strong>forklifts</strong>. This sends authorized footage to Meta and consumes API credits. Not real-time monitoring or danger detection.</p>
      <button type="button" className="button button-primary" disabled={busy || !video.sam_compatible_container}
        onClick={() => void analyze()}>{busy ? "Analyzing…" : job?.status === "completed" ? "Run fresh analysis (billable)" : "Analyze with SAM (billable)"}</button>
      {!video.sam_compatible_container && <p className="error">WebM is not supported by SAM. Convert to H.264 MP4 first.</p>}
      {job && <p className="helper" role="status">{job.message}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {report && <>
        <div className="tracking-metrics"><div><strong>{report.track_count}</strong><small>Tracks</small></div><div><strong>{report.box_count}</strong><small>Observed boxes</small></div><div><strong>{report.gap_count}</strong><small>Occlusion / missing-frame gaps</small></div></div>
        <p className="helper">Frame-overlay timing is {report.time_alignment}; it assumes constant FPS and is NOT frame-accurate evidence. SAM IDs are not trusted across missing-frame gaps. This branch does not classify danger.</p>
        <div className="tracking-track-list">
        {report.tracks.slice(0, 15).map((track) => <div className="tracking-track" key={track.track_id}>
          <strong>{track.track_id}</strong><span>{track.observed_frames} observed frames · {track.fragment_count} fragment(s)</span>
          {track.has_uncertain_identity_continuity && <span className="tracking-warning">Identity continuity unverified</span>}
        </div>)}
        {report.tracks.length === 0 && <p className="helper">No boxes matched the requested concepts. This can be a valid SAM result.</p>}
        </div>
      </>}
    </div>
  </div>;
}
