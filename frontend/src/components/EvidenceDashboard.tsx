"use client";

import {useCallback, useEffect, useState} from "react";
import {
  createEvidenceReport, evidenceExportUrl, fetchEvidenceReport, listEvidenceReports, reviewEvidence,
  type EvidenceReport, type EvidenceSummary, type RuleSpec,
} from "@/lib/api";

export default function EvidenceDashboard({jobId, rule, onSeek}: {
  jobId: string; rule: RuleSpec | null; onSeek: (time: number) => void;
}) {
  const [report, setReport] = useState<EvidenceReport | null>(null);
  const [previous, setPrevious] = useState<EvidenceSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const refresh = useCallback(async () => {
    setPrevious(await listEvidenceReports(jobId));
  }, [jobId]);
  useEffect(() => { void refresh().catch(() => setError("Could not list previous evidence reports")); }, [refresh]);

  async function saveReport() {
    if (!rule) return;
    setBusy(true); setError("");
    try {setReport(await createEvidenceReport(jobId, rule));await refresh();}
    catch (err) {setError(err instanceof Error ? err.message : "Could not save evidence");}
    finally {setBusy(false);}
  }
  async function loadReport(id: string) {
    setBusy(true);setError("");
    try {setReport(await fetchEvidenceReport(id));}
    catch (err) {setError(err instanceof Error ? err.message : "Could not load evidence");}
    finally {setBusy(false);}
  }
  async function decide(itemId: string, decision: "confirmed" | "rejected" | "unresolved") {
    if (!report) return;
    setBusy(true);setError("");
    try {await reviewEvidence(report.id, itemId, decision, note);setReport(await fetchEvidenceReport(report.id));setNote("");}
    catch (err) {setError(err instanceof Error ? err.message : "Could not save reviewer decision");}
    finally {setBusy(false);}
  }
  const latest = new Map(report?.reviews.map(r => [r.item_id,r]) ?? []);
  return <section className="evidence-dashboard" aria-label="Evidence and human review">
    <div className="tracking-tools-header"><div><span className="eyebrow">05 / EVIDENCE</span><h3>Evidence and human review</h3></div><span className="pill">Local prototype</span></div>
    <p className="helper">Save an immutable snapshot of the current rule and tracked observations. Reviewer decisions are stored separately as an append-only audit history. This is not certified safety evidence.</p>
    <button type="button" className="button button-primary" disabled={!rule || busy} onClick={() => void saveReport()}>
      {busy ? "Working…" : "Save evidence snapshot"}
    </button>
    {previous.length > 0 && <label className="safety-label">Previous local snapshots
      <select className="safety-input" value={report?.id ?? ""} onChange={e => void loadReport(e.target.value)}>
        <option value="" disabled>Select a report</option>
        {previous.map(s => <option key={s.id} value={s.id}>{new Date(s.created_at).toLocaleString()} · {s.rule_name} · {s.event_count} event(s)</option>)}
      </select>
    </label>}
    {error && <p className="error" role="alert">{error}</p>}
    {report && <div className="evidence-report">
      <div className="evidence-metrics">
        <div><strong>{report.evaluation.event_count}</strong><small>Observed matches</small></div>
        <div><strong>{report.evaluation.review_count}</strong><small>Review items</small></div>
        <div><strong>{report.reviews.length}</strong><small>Review actions</small></div>
      </div>
      <p className="helper"><strong>Source:</strong> {report.source.video_name} · SAM {report.source.model} · SHA256 {report.source.video_sha256.slice(0,14)}… · timestamps approximate</p>
      <div className="button-row">
        <a className="button button-secondary evidence-link" href={evidenceExportUrl(report.id, "json")}>Export JSON</a>
        <a className="button button-secondary evidence-link" href={evidenceExportUrl(report.id, "html")}>Export printable HTML</a>
      </div>
      <label className="safety-label">Reviewer note (optional)
        <textarea value={note} onChange={e => setNote(e.target.value)} maxLength={600} rows={2} className="safety-input" placeholder="Ground your decision in observed evidence" />
      </label>
      <div className="evidence-items">{report.items.map(item => {
        const obs = item.observation;
        const decision = latest.get(item.item_id);
        return <article className="evidence-item" key={item.item_id}>
          <div className="evidence-item-head"><strong>{item.kind === "observed_event" ? "Observed rule match" : "Needs review"}</strong><span className="pill">{decision?.decision ?? "Pending"}</span></div>
          <button type="button" className="small-link" onClick={() => onSeek(obs.start_seconds_approx ?? 0)}>Seek to frame {obs.start_frame}–{obs.end_frame}</button>
          <p>{obs.reason}</p>
          <p className="helper">{obs.start_seconds_approx ?? "?"}–{obs.end_seconds_approx ?? "?"}s approximate · {report.observations.find(o=>o.item_id===item.item_id)?.sampled_boxes.length ?? 0} recorded observation samples</p>
          <div className="evidence-decisions">
            <button type="button" disabled={busy} onClick={() => void decide(item.item_id,"confirmed")}>Confirm</button>
            <button type="button" disabled={busy} onClick={() => void decide(item.item_id,"rejected")}>Reject</button>
            <button type="button" disabled={busy} onClick={() => void decide(item.item_id,"unresolved")}>Unresolved</button>
          </div>
        </article>;
      })}</div>
      {report.items.length===0 && <p className="helper">No qualifying items in this evidence report. Absence of a rule match does not prove safety.</p>}
      <p className="helper">Reviewer decisions are not model-verdicts and do not overwrite the original detection snapshot. Current local API has no authentication.</p>
    </div>}
  </section>;
}
