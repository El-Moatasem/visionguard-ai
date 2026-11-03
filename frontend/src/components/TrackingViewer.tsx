"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import SafetyRulePanel from "@/components/SafetyRulePanel";
import EvidenceDashboard from "@/components/EvidenceDashboard";
import {
  fetchTrackingJob, fetchTrackingJobs, fetchTrackingResult, fetchTrackingPreview, playbackUrl,
  startTracking, cancelTrackingJob, type TrackingJob, type TrackingReport, type TrackingBox, type VideoItem, type SafetyZone, type RuleSpec, type SafetyEvaluation,
} from "@/lib/api";

const PALETTE: Record<string, string> = {
  person: "#45d9b7", forklift: "#f5bb77", car: "#7bacf6",
  shopping_cart: "#bd97ff", cardboard_box: "#f1c46b", excavator: "#ed9c68",
};
const MODES = [
  {name: "Warehouse: people + forklifts", concepts: ["person","forklift"]},
  {name: "Parking: cars", concepts: ["car"]},
  {name: "Retail: carts + boxes", concepts: ["shopping_cart","cardboard_box"]},
  {name: "Construction: worker zone entry (person only)", concepts: ["person"]},
  {name: "Construction: people + excavators (extended)", concepts: ["person","excavator"]},
];

export default function TrackingViewer({ video, initialRule }: { video: VideoItem; initialRule?: RuleSpec }) {
  const element = useRef<HTMLVideoElement>(null);
  const [seconds, setSeconds] = useState(0);
  const [safetyZone, setSafetyZone] = useState<SafetyZone>(initialRule?.zone ?? {name: "Operating aisle", x_min:.2,y_min:.2,x_max:.8,y_max:.8});
  const [drawing, setDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{x: number; y: number} | null>(null);
  const [drawCurrent, setDrawCurrent] = useState<{x: number; y: number} | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [job, setJob] = useState<TrackingJob | null>(null);
  const [report, setReport] = useState<TrackingReport | null>(null);
  const [preview, setPreview] = useState<TrackingReport | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [approvedRule, setApprovedRule] = useState<RuleSpec | null>(null);
  const [evaluation, setEvaluation] = useState<SafetyEvaluation | null>(null);
  const [conceptSelection, setConceptSelection] = useState<string[]>(video.suggested_concepts?.length ? video.suggested_concepts : ["person", "forklift"]);
  const seekTo = (time: number) => { if (element.current) { element.current.currentTime = time; setSeconds(time); } };

  useEffect(() => {
    let current = true;
    setSeconds(0);
    setReport(null);
    setPreview(null);
    setJob(null);
    setError("");
    setDrawing(false); setDrawStart(null); setDrawCurrent(null); setApprovedRule(null); setEvaluation(null);
    void fetchTrackingJobs(video.id).then((jobs) => {
      if (current) setJob(jobs[0] ?? null);
    }).catch((err: unknown) => {
      if (current) setError(err instanceof Error ? err.message : "Could not read tracking jobs");
    });
    return () => { current = false; };
  }, [video.id]);

  useEffect(() => {
    if (!job || !["queued", "running", "cancelling"].includes(job.status)) return;
    let current = true;
    const tick = () => { void fetchTrackingJob(job.id).then((fresh) => {
      if (current) { setJob(fresh); setError(""); }
    }).catch((err: unknown) => {
      if (current) setError(err instanceof Error ? err.message : "Could not poll tracking job");
    }); };
    const timer = window.setInterval(tick, 2500);
    tick();
    return () => { current = false; window.clearInterval(timer); };
  }, [job?.id, job?.status]);

  // Poll a separate lightweight, read-only snapshot for progressive overlays.
  // A preview is never treated as a complete safety/evidence report.
  useEffect(() => {
    if (!job || !["queued", "running", "cancelling"].includes(job.status)) return;
    let current = true;
    const tick = () => {
      void fetchTrackingPreview(job.id).then(data => {
        if (current && data) setPreview(data);
      }).catch(() => { /* Status polling reports connectivity failures. */ });
    };
    tick();
    const timer = window.setInterval(tick, 2500);
    return () => { current = false; window.clearInterval(timer); };
  }, [job?.id, job?.status]);

  // Keep partial observations from a terminal job, but never poll it repeatedly.
  useEffect(() => {
    if (!job || !["failed", "interrupted", "cancelled"].includes(job.status)) return;
    let current = true;
    void fetchTrackingPreview(job.id).then(data => { if(current && data) setPreview(data); })
      .catch(() => {/* no partial observations is expected */});
    return () => { current = false; };
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

  // Use actual decoded video-frame timing when the browser supports it. The
  // onTimeUpdate handler below remains a fallback for older browsers.
  useEffect(() => {
    const player = element.current;
    if (!player || !player.requestVideoFrameCallback) return;
    let cancelled = false;
    let requestId = 0;
    const onFrame = (_now: number, metadata: VideoFrameCallbackMetadata) => {
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

  async function analyze() {
    setSubmitting(true);
    setError("");
    setReport(null); setPreview(null); setApprovedRule(null); setEvaluation(null);
    try { setJob(await startTracking(video.id, conceptSelection)); }
    catch (err) { setError(err instanceof Error ? err.message : "Tracking request failed"); }
    finally { setSubmitting(false); }
  }

  async function cancelCurrent() {
    if (!job || !["queued", "running"].includes(job.status)) return;
    setCancelling(true); setError("");
    try { setJob(await cancelTrackingJob(job.id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not cancel analysis"); }
    finally { setCancelling(false); }
  }

  function svgPoint(event: ReactPointerEvent<SVGSVGElement>) {
    const svg = event.currentTarget;
    const matrix = svg.getScreenCTM();
    if (!matrix || !dimensions.width || !dimensions.height) return null;
    const p = svg.createSVGPoint(); p.x = event.clientX; p.y = event.clientY;
    const actual = p.matrixTransform(matrix.inverse());
    return {x: Math.min(1, Math.max(0, actual.x / dimensions.width)),
            y: Math.min(1, Math.max(0, actual.y / dimensions.height))};
  }
  function onDrawStart(event: ReactPointerEvent<SVGSVGElement>) {
    if (!drawing) return;
    const p = svgPoint(event); if (!p) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrawStart(p); setDrawCurrent(p);
  }
  function onDrawMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (drawing && drawStart) setDrawCurrent(svgPoint(event));
  }
  function onDrawEnd(event: ReactPointerEvent<SVGSVGElement>) {
    if (!drawing || !drawStart) return;
    const p = svgPoint(event);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (p) {
      const zone = {name: "Drawn safety zone", x_min: Math.min(drawStart.x,p.x),
        y_min: Math.min(drawStart.y,p.y), x_max: Math.max(drawStart.x,p.x), y_max: Math.max(drawStart.y,p.y)};
      if (zone.x_max-zone.x_min >= .02 && zone.y_max-zone.y_min >= .02) {
        setSafetyZone(zone); setDrawing(false); setApprovedRule(null); setEvaluation(null);
      }
    }
    setDrawStart(null);setDrawCurrent(null);
  }

  // Pre-index observations to avoid scanning every box on every video frame.
  // Missing frames intentionally have no overlay; do not invent/interpolate.
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
  const fps = displayReport?.media_probe.fps ?? displayReport?.media_metadata?.fps;
  const frame = fps ? Math.round(seconds * fps) : null;
  const overlays = frame === null ? [] : boxesByFrame.get(frame) ?? [];
  const showOverlay = Boolean(dimensions.width && dimensions.height);
  const activeEvent = evaluation?.events.find(event => frame !== null && frame >= event.start_frame && frame <= event.end_frame);
  const activeReview = evaluation?.review_items.find(item => frame !== null && frame >= item.start_frame && frame <= item.end_frame);
  const flaggedTracks = new Set(activeEvent?.actor_tracks ?? activeReview?.actor_tracks ?? []);
  const timelineMax = displayReport?.media_probe.duration_seconds ?? (fps ? Math.max(1, (displayReport?.boxes.at(-1)?.frame ?? 30) / fps) : 0);
  const timelineEntries = [...(evaluation?.events ?? []).map(x => ({type: "event" as const, start: x.start_seconds_approx, end: x.end_seconds_approx, id: x.event_id})),
    ...(evaluation?.review_items ?? []).map((x, i) => ({type: "review" as const, start: x.start_seconds_approx, end: x.end_seconds_approx, id: x.event_id ?? `review-${i}`}))];
  const samMaxBytes = 100 * 1024 * 1024;
  const tooLargeForSam = video.size_bytes > samMaxBytes;
  const busy = submitting || cancelling || ["queued", "running", "cancelling"].includes(job?.status ?? "");

  return <div className="tracking-viewer">
    <div className="tracking-player">
      <video key={video.id} ref={element} src={playbackUrl(video)} controls playsInline loop={busy} preload="metadata"
        className="player" onTimeUpdate={(e) => setSeconds(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDimensions({ width: e.currentTarget.videoWidth, height: e.currentTarget.videoHeight })}/>
      {showOverlay && <svg className={`tracking-overlay ${drawing ? "tracking-draw-mode" : ""}`} viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        onPointerDown={onDrawStart} onPointerMove={onDrawMove} onPointerUp={onDrawEnd}
        onPointerCancel={() => {setDrawStart(null);setDrawCurrent(null);}}
        preserveAspectRatio="xMidYMid meet" aria-label="Approximate SAM tracking boxes">
        {<rect x={safetyZone.x_min*dimensions.width} y={safetyZone.y_min*dimensions.height}
          width={(safetyZone.x_max-safetyZone.x_min)*dimensions.width}
          height={(safetyZone.y_max-safetyZone.y_min)*dimensions.height}
          fill="#e8b85a" fillOpacity="0.07" stroke="#e8b85a" strokeDasharray="12 8" strokeWidth={3} />}
        {drawStart && drawCurrent && <rect x={Math.min(drawStart.x,drawCurrent.x)*dimensions.width}
          y={Math.min(drawStart.y,drawCurrent.y)*dimensions.height}
          width={Math.abs(drawStart.x-drawCurrent.x)*dimensions.width}
          height={Math.abs(drawStart.y-drawCurrent.y)*dimensions.height}
          fill="#45d9b7" fillOpacity="0.16" stroke="#45d9b7" strokeWidth={4} />}
        {overlays.map((item) => <g key={`${item.track_id}:${item.frame}`}>
          <rect x={item.box.left} y={item.box.top} width={item.box.right - item.box.left}
            height={item.box.bottom - item.box.top} fill="none"
            stroke={flaggedTracks.has(item.track_id) ? (activeEvent ? "#f16a64" : "#9dbaff") : (PALETTE[item.concept] ?? "white")}
            strokeWidth={Math.max(flaggedTracks.has(item.track_id) ? 4 : 2, dimensions.width / 450)} />
          <text x={item.box.left} y={Math.max(14, item.box.top - 7)} fill={PALETTE[item.concept] ?? "white"}
            fontSize={Math.max(12, dimensions.width / 70)} fontWeight="bold">{item.fragment_id}</text>
        </g>)}
      </svg>}
    </div>
    <div className="vg-pre-sam-zone-toolbar" aria-label="Monitoring zone setup">
      <div className="vg-pre-sam-zone-copy">
        <strong>Monitoring zone</strong>
        <p className="helper">Draw a zone before or after SAM. The zone screens tracked observations; it does not crop video or reduce billable model requests.</p>
        <p className="helper" aria-live="polite">Zone: {(safetyZone.x_min * 100).toFixed(0)}%–{(safetyZone.x_max * 100).toFixed(0)}% across, {(safetyZone.y_min * 100).toFixed(0)}%–{(safetyZone.y_max * 100).toFixed(0)}% down.</p>
      </div>
      <div className="vg-pre-sam-zone-buttons">
        <button className="button button-secondary" type="button" aria-pressed={drawing}
          disabled={!dimensions.width || !dimensions.height}
          onClick={() => {setDrawing(value => !value); setDrawStart(null); setDrawCurrent(null);}}>
          {drawing ? "Cancel zone drawing" : "Draw monitoring zone"}
        </button>
        <button className="button button-quiet" type="button"
          onClick={() => {setSafetyZone({name: "Operating aisle", x_min:.2,y_min:.2,x_max:.8,y_max:.8}); setDrawing(false);setDrawStart(null);setDrawCurrent(null);setApprovedRule(null);setEvaluation(null);}}>
          Reset zone
        </button>
      </div>
      {drawing && <p className="safety-warning" role="status">Drag over the video to mark your monitoring area. Dragging temporarily disables video playback controls; select Cancel zone drawing to return to normal playback.</p>}
    </div>
      {timelineMax > 0 && evaluation && <div className="sceneops-timeline" aria-label="Approximate reviewed-event timeline">
        {timelineEntries.map(item => {
          if (item.start === null) return null;
          const left = Math.max(0, Math.min(100, item.start / timelineMax * 100));
          const end = item.end ?? item.start;
          const width = Math.max(0.8, Math.min(100 - left, (end-item.start)/timelineMax*100));
          return <button key={item.id} type="button" className={item.type === "review" ? "review" : ""}
            title={`${item.type === "review" ? "Uncertain observation" : "Potential rule match"}: ${item.start}s (approximate)`}
            aria-label={`Seek to ${item.type === "review" ? "review item" : "potential match"} at ${item.start} seconds`}
            style={{left:`${left}%`,width:`${width}%`}} onClick={() => seekTo(item.start!)} />;
        })}
        <div className="sceneops-timeline-playhead" style={{left:`${Math.max(0,Math.min(100,seconds/timelineMax*100))}%`}} />
      </div>}
    <div className="tracking-tools">
      <div className="tracking-tools-header"><div><span className="eyebrow">03 / VISUAL TRACKING</span><h3>Meta SAM 3.1 analysis</h3></div>
      <span className={`tracking-state ${job?.status === "completed" ? "is-ok" : ""}`}>{job?.status ?? "Not analyzed"}</span></div>
      <p className="helper">SAM 3.1 tracks selected concepts on an authorized uploaded clip. Each concept is a separate billable request; live-camera alerting and certified danger detection are NOT provided.</p>
      <div className="sceneops-concepts"><label className="safety-label" htmlFor="sceneops-concepts">Tracking concepts</label>
        <select id="sceneops-concepts" className="safety-input" disabled={busy} value={MODES.findIndex(m=>m.concepts.join()===conceptSelection.join()) >= 0 ? conceptSelection.join() : "custom"}
          onChange={e=>setConceptSelection(e.target.value.split(","))}>
          {MODES.map(m=><option key={m.name} value={m.concepts.join()}>{m.name}</option>)}
          {!MODES.some(m=>m.concepts.join()===conceptSelection.join()) && <option value="custom" disabled>Custom: {conceptSelection.join(", ")}</option>}
        </select>
      </div>
      {job?.status === "completed" && job.concepts.join() !== conceptSelection.join() && <p className="helper">The saved tracking result uses {job.concepts.join(", ")}. Changing the concept selection requires a new billable analysis.</p>}
      <button type="button" className="button button-primary" disabled={busy || !video.sam_compatible_container || tooLargeForSam}
        onClick={() => void analyze()}>{busy ? "Analyzing…" : job?.status === "completed" ? "Run fresh analysis (billable)" : "Analyze with SAM (billable)"}</button>
      {["queued", "running"].includes(job?.status ?? "") && <button type="button" className="button button-alert"
        disabled={cancelling} onClick={() => void cancelCurrent()}>
        {cancelling ? "Requesting cancellation…" : "Cancel this analysis"}
      </button>}
      {job?.status === "cancelling" && <p className="helper" role="status">Stopping this job locally. Charges may still apply to Meta requests already started.</p>}
      {job?.status === "cancelled" && <p className="helper" role="status">Analysis cancelled; no final tracking result was published.</p>}
      {!video.sam_compatible_container && <p className="error">WebM is not supported by SAM. Convert to H.264 MP4 first.</p>}
      {tooLargeForSam && <p className="error">This video exceeds this app’s 100 MiB SAM analysis limit. Prepare a smaller clip before inference.</p>}
      {job && <p className="helper" role="status">{job.message}</p>}
      {preview && !report && <p className="helper" role="status">
        Live progress preview: {preview.box_count} observed boxes so far.
        {job?.status === "failed" ? " Partial observations survived the failed job." :
          " Play or seek the video to see boxes; final safety evaluation is unavailable until completion."}
      </p>}
      {job?.failure_type && <p className="error" role="alert">Failure type: {job.failure_type}. See FastAPI traceback for the underlying cause.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {report && <>
        <div className="tracking-metrics"><div><strong>{report.track_count}</strong><small>Tracks</small></div><div><strong>{report.box_count}</strong><small>Observed boxes</small></div><div><strong>{report.gap_count}</strong><small>Occlusion / missing-frame gaps</small></div></div>
        <p className="helper">Frame timing is approximate and not frame-accurate evidence. Short gaps can retain provisional fragment association, but identity is unverified and missing positions are never interpolated. Rule-based screening is below.</p>
        <div className="tracking-track-list">
        {report.tracks.slice(0, 15).map((track) => <div className="tracking-track" key={track.track_id}>
          <strong>{track.track_id}</strong><span>{track.observed_frames} observed frames · {track.fragment_count} fragment(s)</span>
          {track.has_uncertain_identity_continuity && <span className="tracking-warning">Identity continuity unverified</span>}
        </div>)}
        {report.tracks.length === 0 && <p className="helper">No boxes matched the requested concepts. This can be a valid SAM result.</p>}
        </div>
        {job?.status === "completed" && <SafetyRulePanel key={`${job.id}:${safetyZone.x_min}:${safetyZone.y_min}:${safetyZone.x_max}:${safetyZone.y_max}`} jobId={job.id} zone={safetyZone} onZoneChange={z => {setSafetyZone(z);setApprovedRule(null);}}
          drawing={drawing} onDrawingChange={setDrawing}
          initialRule={initialRule} availableConcepts={job.concepts} availablePersonTracks={report.tracks.filter(t => t.concept === "person").map(t => t.track_id)}
          onEvaluated={(result,rule) => {setEvaluation(result);setApprovedRule(rule);}}
          onSeek={seekTo} />}
        {job?.status === "completed" && <EvidenceDashboard key={`evidence-${job.id}`} jobId={job.id} rule={approvedRule}
          onSeek={seekTo} /> }
      </>}
    </div>
  </div>;
}
