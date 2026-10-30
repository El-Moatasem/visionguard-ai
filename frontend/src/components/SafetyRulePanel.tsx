"use client";

import { useState } from "react";
import {
  evaluateSafetyRule, interpretSafetyRule, type RuleDraft, type RuleSpec,
  type RuleType, type SafetyEvaluation, type SafetyZone,
} from "@/lib/api";

const PRESETS: Record<string, SafetyZone> = {
  center: { name: "Operating aisle", x_min: 0.2, y_min: 0.2, x_max: 0.8, y_max: 0.8 },
  left: { name: "Left operating area", x_min: 0, y_min: 0, x_max: 0.5, y_max: 1 },
  right: { name: "Right operating area", x_min: 0.5, y_min: 0, x_max: 1, y_max: 1 },
  full: { name: "Whole frame", x_min: 0, y_min: 0, x_max: 1, y_max: 1 },
};

export default function SafetyRulePanel({ jobId, onZoneChange, zone, drawing, onDrawingChange, onSeek }: {
  jobId: string;
  zone: SafetyZone;
  drawing: boolean;
  onZoneChange: (zone: SafetyZone) => void;
  onDrawingChange: (value: boolean) => void;
  onSeek: (seconds: number) => void;
}) {
  const [ruleType, setRuleType] = useState<RuleType>("person_and_forklift_in_zone");
  const [ruleName, setRuleName] = useState("Worker and forklift in operating area");
  const [duration, setDuration] = useState(0.5);
  const [gapTolerance, setGapTolerance] = useState(2);
  const [boundInputs, setBoundInputs] = useState<Record<string, string> | null>(null);
  const [prompt, setPrompt] = useState("Flag a pedestrian and forklift observed in the same operating area for half a second.");
  const [draft, setDraft] = useState<RuleDraft | null>(null);
  const [evaluation, setEvaluation] = useState<SafetyEvaluation | null>(null);
  const [busy, setBusy] = useState<"muse" | "evaluate" | null>(null);
  const [error, setError] = useState("");

  function applyZone(next: SafetyZone) {
    onZoneChange(next);
    setBoundInputs(null);
    setEvaluation(null);
  }
  function changeBound(field: "x_min" | "y_min" | "x_max" | "y_max", value: string) {
    setBoundInputs(previous => ({...(previous ?? Object.fromEntries(
      (["x_min", "y_min", "x_max", "y_max"] as const).map(k => [k, String(zone[k])])
    )), [field]: value}));
    // Empty and nonnumeric values remain visible as invalid inputs instead of becoming zero.
    if (value.trim() === "") return;
    const next = Number(value);
    if (Number.isFinite(next)) {
      onZoneChange({...zone, [field]: next});
      setEvaluation(null);
    }
  }
  async function interpret() {
    setBusy("muse"); setError(""); setDraft(null);
    try { setDraft(await interpretSafetyRule(prompt)); }
    catch (err) { setError(err instanceof Error ? err.message : "Muse interpretation failed"); }
    finally { setBusy(null); }
  }
  function acceptDraft() {
    if (!draft || draft.rule_type === "unsupported") return;
    setRuleName(draft.name);
    setRuleType(draft.rule_type);
    setDuration(draft.min_duration_seconds);
    setDraft(null);
    setEvaluation(null);
  }
  async function evaluate() {
    setBusy("evaluate"); setError(""); setEvaluation(null);
    const rule: RuleSpec = {
      name: ruleName, rule_type: ruleType, min_duration_seconds: duration,
      max_observation_gap_frames: gapTolerance, zone,
    };
    try { setEvaluation(await evaluateSafetyRule(jobId, rule)); }
    catch (err) { setError(err instanceof Error ? err.message : "Rule evaluation failed"); }
    finally { setBusy(null); }
  }
  const normalizedInputValid = !boundInputs || Object.values(boundInputs).every(v => v.trim() !== "" && Number.isFinite(Number(v)));
  const valid = normalizedInputValid && ruleName.trim().length > 0 &&
    Number.isFinite(duration) && duration > 0 && duration <= 30 &&
    Number.isInteger(gapTolerance) && gapTolerance >= 0 && gapTolerance <= 30 &&
    Object.entries(zone).every(([key, value]) => key === "name" || (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1)) &&
    zone.x_min < zone.x_max && zone.y_min < zone.y_max;

  return <section className="safety-panel" aria-label="Hazard rule evaluation">
    <div className="tracking-tools-header"><div><span className="eyebrow">04 / SAFETY INTELLIGENCE</span><h3>Evaluate observable safety rules</h3></div><span className="pill">Human-reviewed</span></div>
    <p className="helper">Configure a floor zone and duration. The engine reports observed matches and separate review items; it cannot predict collisions or infer missing observations.</p>
    <label className="safety-label" htmlFor="rule-prompt">Describe a rule (optional, billable Muse Spark call)</label>
    <textarea id="rule-prompt" className="safety-input" value={prompt} maxLength={500} rows={3} onChange={e => setPrompt(e.target.value)} />
    <button className="button button-secondary" type="button" disabled={busy !== null || prompt.trim().length < 8} onClick={() => void interpret()}>
      {busy === "muse" ? "Asking Muse…" : "Interpret with Muse (billable)"}
    </button>
    {draft && <div className="rule-draft" role="status">
      <strong>{draft.rule_type === "unsupported" ? "Muse cannot implement this request" : "Muse suggestion — approval required"}</strong>
      <p>{draft.name} · {draft.rule_type.replaceAll("_", " ")}{draft.rule_type !== "unsupported" && ` · ${draft.min_duration_seconds}s`}</p>
      <p className="helper">{draft.rationale}</p>
      {draft.rule_type !== "unsupported" && <button className="button button-secondary" type="button" onClick={acceptDraft}>Approve and apply rule draft</button>}
    </div>}
    <div className="safety-fields">
      <label className="safety-label">Rule name<input className="safety-input" value={ruleName} maxLength={80} onChange={e => {setRuleName(e.target.value);setEvaluation(null);}} /></label>
      <label className="safety-label">Rule type<select className="safety-input" value={ruleType} onChange={e => {setRuleType(e.target.value as RuleType);setEvaluation(null);}}>
        <option value="person_and_forklift_in_zone">Person + forklift simultaneously in zone</option>
        <option value="person_in_zone">Person foot-point in zone</option>
      </select></label>
      <label className="safety-label">Minimum observed duration (seconds)<input className="safety-input" type="number" min={0.01} max={30} step={0.1} value={duration} onChange={e => {setDuration(Number(e.target.value));setEvaluation(null);}} /></label>
      <label className="safety-label">Max missing frames for review association<input className="safety-input" type="number" min={0} max={30} step={1} value={gapTolerance} onChange={e => {setGapTolerance(Number(e.target.value));setEvaluation(null);}} /></label>
      <label className="safety-label">Zone preset<select className="safety-input" defaultValue="center" onChange={e => applyZone(PRESETS[e.target.value])}>
        <option value="center">Center (20–80%)</option><option value="left">Left half</option>
        <option value="right">Right half</option><option value="full">Whole frame</option>
      </select></label>
    </div>
    <button className="button button-secondary" type="button" onClick={() => onDrawingChange(!drawing)}>
      {drawing ? "Cancel drawing" : "Draw zone on video"}
    </button>
    {drawing && <p className="safety-warning" role="status">Drag a rectangle over the video image, not the black bars. At least 2% width and height are required.</p>}
    <p className="helper">Zone coordinates are normalized (0–1). For people, the bottom-center of the box approximates the floor-contact point; forklift center is an image-space proxy. Timing is approximate.</p>
    <div className="safety-coordinates">
      {(["x_min", "y_min", "x_max", "y_max"] as const).map(field => <label className="safety-label" key={field}>{field}
        <input className="safety-input" type="number" min={0} max={1} step={0.05} value={boundInputs?.[field] ?? String(zone[field])}
          onBlur={() => setBoundInputs(null)} onChange={e => changeBound(field, e.target.value)}/></label>)}
    </div>
    <button className="button button-primary" type="button" disabled={busy !== null || !valid || drawing} onClick={() => void evaluate()}>
      {busy === "evaluate" ? "Evaluating…" : "Evaluate tracked observations (offline, no credits)"}
    </button>
    {!valid && <p className="error">Enter a valid zone, duration (0–30s), and integer gap tolerance (0–30 frames).</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {evaluation && <div className="safety-results" role="status">
      <div className="safety-outcome"><strong>{evaluation.outcome.replaceAll("_", " ")}</strong>
        <span>{evaluation.event_count} observed match(es) · {evaluation.review_count} review item(s)</span></div>
      <p className="helper">{evaluation.disclaimer}</p>
      {evaluation.events.map(event => <button type="button" key={event.event_id} className="safety-event"
        disabled={event.start_seconds_approx === null} onClick={() => {if(event.start_seconds_approx !== null) onSeek(event.start_seconds_approx);}}>
        <strong>Observed match: frames {event.start_frame}–{event.end_frame}</strong>
        <small>{event.reason}</small>
        <small>{event.actor_fragments.join(" + ")} · {event.start_seconds_approx ?? "unknown"}s approximate</small>
      </button>)}
      {evaluation.review_items.map((item, i) => <button type="button" key={item.event_id ?? `gap-${item.track_id ?? i}-${i}`}
        className="safety-event safety-review" disabled={item.start_seconds_approx === null}
        onClick={() => {if(item.start_seconds_approx !== null) onSeek(item.start_seconds_approx);}}>
        <strong>Needs review: frames {item.start_frame}–{item.end_frame}</strong>
        <small>{item.reason}</small>
        {item.observed_coverage_ratio !== undefined && <small>Observed coverage: {Math.round(item.observed_coverage_ratio*100)}% — missing samples are NOT assumed safe or unsafe</small>}
      </button>)}
      {evaluation.event_count === 0 && evaluation.review_count === 0 && <p className="helper">No qualifying observed rule matches or localized review items. This does not prove safety.</p>}
    </div>}
  </section>;
}
