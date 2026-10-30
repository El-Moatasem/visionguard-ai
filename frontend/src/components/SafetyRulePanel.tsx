"use client";

import { useState } from "react";
import {
  evaluateSafetyRule, interpretSafetyRule, type RuleDraft, type RuleSpec,
  type RuleType, type SafetyEvaluation, type SafetyZone,
} from "@/lib/api";

const DEFAULT_ZONE: SafetyZone = { name: "Operating aisle", x_min: 0.2, y_min: 0.2, x_max: 0.8, y_max: 0.8 };
const PRESETS: Record<string, SafetyZone> = {
  center: DEFAULT_ZONE,
  left: { name: "Left operating area", x_min: 0, y_min: 0, x_max: 0.5, y_max: 1 },
  right: { name: "Right operating area", x_min: 0.5, y_min: 0, x_max: 1, y_max: 1 },
  full: { name: "Whole frame", x_min: 0, y_min: 0, x_max: 1, y_max: 1 },
};

export default function SafetyRulePanel({jobId, onZoneChange, onSeek}: {
  jobId: string;
  onZoneChange: (zone: SafetyZone) => void;
  onSeek: (timeSeconds: number) => void;
}) {
  const [ruleType, setRuleType] = useState<RuleType>("person_and_forklift_in_zone");
  const [ruleName, setRuleName] = useState("Worker and forklift in operating area");
  const [threshold, setThreshold] = useState(3);
  const [zone, setZone] = useState<SafetyZone>(DEFAULT_ZONE);
  const [prompt, setPrompt] = useState("Flag a potential hazard when a pedestrian and forklift are in the same operating area for three consecutive frames.");
  const [draft, setDraft] = useState<RuleDraft | null>(null);
  const [evaluation, setEvaluation] = useState<SafetyEvaluation | null>(null);
  const [busy, setBusy] = useState<"muse" | "evaluate" | null>(null);
  const [error, setError] = useState("");

  function changeZone(next: SafetyZone) {setZone(next); onZoneChange(next); setEvaluation(null);}
  function changeBound(field: "x_min" | "y_min" | "x_max" | "y_max", value: string) {
    // Preserve range checks at the API boundary too; don't silently clamp invalid zones.
    const parsed = Number(value);
    changeZone({...zone, [field]: Number.isFinite(parsed) ? parsed : 0});
  }
  async function interpret() {
    setBusy("muse"); setError(""); setDraft(null);
    try {setDraft(await interpretSafetyRule(prompt));}
    catch (err) {setError(err instanceof Error ? err.message : "Muse interpretation failed");}
    finally {setBusy(null);}
  }
  function acceptDraft() {
    if (!draft) return;
    setRuleName(draft.name);setRuleType(draft.rule_type);setThreshold(draft.min_consecutive_frames);
    setDraft(null);setEvaluation(null);
  }
  async function evaluate() {
    setBusy("evaluate"); setError(""); setEvaluation(null);
    const rule: RuleSpec = {name: ruleName, rule_type: ruleType, min_consecutive_frames: threshold, zone};
    try { setEvaluation(await evaluateSafetyRule(jobId, rule)); }
    catch (err) {setError(err instanceof Error ? err.message : "Rule evaluation failed");}
    finally {setBusy(null);}
  }
  const valid = ruleName.trim().length > 0 && threshold >= 1 && threshold <= 60 &&
    Object.entries(zone).every(([key, value]) => key === "name" || (typeof value === "number" && value >= 0 && value <= 1)) &&
    zone.x_min < zone.x_max && zone.y_min < zone.y_max;

  return <section className="safety-panel" aria-label="Hazard rule evaluation">
    <div className="tracking-tools-header"><div><span className="eyebrow">04 / SAFETY INTELLIGENCE</span><h3>Evaluate visual safety rules</h3></div><span className="pill">Human-reviewed</span></div>
    <p className="helper">Configure a visible area and test rule matches from the completed SAM tracking job. This is not a collision predictor or real-time safety system.</p>
    <label className="safety-label" htmlFor="rule-prompt">Describe a rule (optional Muse Spark API call)</label>
    <textarea id="rule-prompt" className="safety-input" value={prompt} maxLength={500} rows={3} onChange={e => setPrompt(e.target.value)} />
    <button className="button button-secondary" type="button" disabled={busy !== null || prompt.trim().length < 8}
      onClick={() => void interpret()}>{busy === "muse" ? "Asking Muse…" : "Interpret with Muse (billable)"}</button>
    {draft && <div className="rule-draft" role="status">
      <strong>Muse suggestion — review before applying</strong>
      <p>{draft.name} · {draft.rule_type.replaceAll("_", " ")} · {draft.min_consecutive_frames} frames</p>
      <p className="helper">{draft.rationale}</p>
      <button className="button button-secondary" type="button" onClick={acceptDraft}>Approve and apply draft</button>
    </div>}
    <div className="safety-fields">
      <label className="safety-label">Rule name<input className="safety-input" value={ruleName} maxLength={80} onChange={e => {setRuleName(e.target.value);setEvaluation(null);}} /></label>
      <label className="safety-label">Rule type<select className="safety-input" value={ruleType} onChange={e => {setRuleType(e.target.value as RuleType);setEvaluation(null);}}>
        <option value="person_and_forklift_in_zone">Person + forklift simultaneously in zone</option>
        <option value="person_in_zone">Person enters reviewer-defined zone</option>
      </select></label>
      <label className="safety-label">Minimum consecutive frames<input className="safety-input" type="number" min={1} max={60} step={1} value={threshold} onChange={e => {setThreshold(Number(e.target.value));setEvaluation(null);}} /></label>
      <label className="safety-label">Zone preset<select className="safety-input" defaultValue="center" onChange={e => changeZone(PRESETS[e.target.value])}>
        <option value="center">Center (20–80%)</option><option value="left">Left half</option>
        <option value="right">Right half</option><option value="full">Whole frame</option>
      </select></label>
    </div>
    <p className="helper">Zone coordinates are normalized to the video dimensions (0–1). The dashed rectangle is an approximate review overlay.</p>
    <div className="safety-coordinates">
      {(["x_min","y_min","x_max","y_max"] as const).map((field) => <label className="safety-label" key={field}>{field}
        <input className="safety-input" type="number" min={0} max={1} step={0.05} value={zone[field]}
          onChange={e => changeBound(field, e.target.value)}/></label>)}
    </div>
    <button className="button button-primary" type="button" disabled={busy !== null || !valid}
      onClick={() => void evaluate()}>{busy === "evaluate" ? "Evaluating…" : "Evaluate tracked frames (offline, no credits)"}</button>
    {!valid && <p className="error">Set a valid zone (min less than max) and threshold 1–60.</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {evaluation && <div className="safety-results" role="status">
      <div className="safety-outcome"><strong>{evaluation.outcome.replaceAll("_", " ")}</strong>
        <span>{evaluation.event_count} rule match(es) · {evaluation.uncertainty_count} tracking gap(s)</span></div>
      <p className="helper">{evaluation.disclaimer}</p>
      {evaluation.events.map(event => <button type="button" key={event.event_id} className="safety-event"
        disabled={event.start_seconds_approx === null} onClick={() => {if(event.start_seconds_approx !== null)onSeek(event.start_seconds_approx);}}>
        <strong>Review frames {event.start_frame}–{event.end_frame}</strong>
        <small>{event.reason}</small>
        <small>{event.actor_fragments.join(" + ")} · {event.start_seconds_approx ?? "unknown"}s approximate</small>
      </button>)}
      {evaluation.uncertainty_count > 0 && <p className="safety-warning">Tracking gaps require manual review. No positions or identities are inferred across them.</p>}
      {evaluation.event_count === 0 && <p className="helper">No qualifying observed rule matches. This does NOT prove the scene was safe.</p>}
    </div>}
  </section>;
}
