"use client";

import Link from "next/link";
import {useCallback, useEffect, useState} from "react";
import {cancelAllTrackingJobs, cancelTrackingJob, fetchActiveTrackingJobs, type TrackingJob} from "@/lib/api";

const RUNNING_STATES = new Set(["queued", "running", "cancelling"]);

/** All process-local active SAM jobs, including those for videos not currently selected. */
export default function ActiveTrackingJobs({videoNames}: {videoNames: Record<string,string>}) {
  const [jobs, setJobs] = useState<TrackingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setJobs((await fetchActiveTrackingJobs()).filter(job => RUNNING_STATES.has(job.status)));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not fetch active jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {void refresh();}, 2500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function cancelOne(jobId: string) {
    setBusy(jobId);
    try {
      await cancelTrackingJob(jobId);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cancellation request failed");
    } finally {setBusy(null);}
  }

  async function cancelAll() {
    if (!jobs.length) return;
    if (!window.confirm(`Request cancellation of all ${jobs.length} active SAM job(s)? Already-started Meta inference may still be billed.`)) return;
    setBusy("all");
    try {
      await cancelAllTrackingJobs();
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cancel-all request failed");
    } finally {setBusy(null);}
  }

  return <section className="vg-side-panel" aria-label="Active tracking jobs">
    <span className="vg-side-title">02 / BACKGROUND ACTIVITY</span>
    <h2>Active SAM jobs ({jobs.length})</h2>
    <p>Jobs running for all uploaded videos in this backend process, not only the selected video.</p>
    {loading && <p className="helper">Checking background jobs…</p>}
    {!loading && jobs.length === 0 && <p className="helper">No active SAM analyses.</p>}
    <div className="vg-side-list">
      {jobs.map(job => <div key={job.id} style={{padding: "10px 0", borderBottom:"1px solid #36515b"}}>
        <div style={{display:"flex",justifyContent:"space-between",gap:8,alignItems:"start"}}>
          <div style={{minWidth:0}}>
            <Link href={`/studio?video=${encodeURIComponent(job.video_id)}`} className="small-link">
              {videoNames[job.video_id] || `Video ${job.video_id.slice(0,8)}`}
            </Link>
            <p className="helper" style={{margin:"4px 0"}}>{job.status.toUpperCase()} · {job.phase ?? "Processing"} · {job.concepts.join(", ")}</p>
          </div>
          {job.status !== "cancelling" && <button type="button" className="button button-alert"
            style={{padding:"7px 10px",fontSize:11}} disabled={busy !== null}
            onClick={() => void cancelOne(job.id)}>
            {busy === job.id ? "Stopping…" : "Cancel"}
          </button>}
        </div>
      </div>)}
    </div>
    {jobs.some(job => job.status !== "cancelling") && <button type="button" className="button button-alert"
      disabled={busy !== null} onClick={() => void cancelAll()}>
      {busy === "all" ? "Requesting cancellation…" : "Cancel all running jobs"}
    </button>}
    {error && <p className="error" role="alert">{error}</p>}
    <p className="helper">Cancelling closes local processing when possible, but cannot guarantee cancellation or refunds for Meta requests already accepted. Jobs disappear after cleanup completes.</p>
  </section>;
}
