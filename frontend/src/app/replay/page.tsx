"use client";

import Link from "next/link";
import {useCallback, useEffect, useState} from "react";
import {
  evaluateReplay, fetchReplayScenario, fetchReplayScenarios,
  type ReplayScenario, type ReplaySummary, type RuleSpec, type SafetyEvaluation,
} from "@/lib/api";

function prettyKind(kind: string) {return kind.replaceAll("_", " ");}

export default function ReplayPage() {
  const [options, setOptions] = useState<ReplaySummary[]>([]);
  const [scenario, setScenario] = useState<ReplayScenario | null>(null);
  const [rule, setRule] = useState<RuleSpec | null>(null);
  const [result, setResult] = useState<SafetyEvaluation | null>(null);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [decisions, setDecisions] = useState<Record<string,"confirmed" | "rejected" | "unresolved">>({});

  const load = useCallback(async (id: string) => {
    setBusy(true);setError("");setPlaying(false);setFrame(0);setResult(null);setDecisions({});
    try { const data = await fetchReplayScenario(id);setScenario(data);setRule(data.default_rule); }
    catch (e) {setError(e instanceof Error ? e.message : "Replay scenario unavailable");}
    finally {setBusy(false);}
  }, []);
  useEffect(() => {void fetchReplayScenarios().then(items=>{
    setOptions(items);if(items.length) void load(items[0].id);
  }).catch(e=>setError(e instanceof Error ? e.message : "Replay API unavailable"));},[load]);
  useEffect(() => {
    if (!scenario || !playing) return;
    const maxFrame = Math.ceil((scenario.tracking_report.media_probe.duration_seconds ?? 3)* (scenario.tracking_report.media_probe.fps ?? 10))-1;
    const interval = window.setInterval(()=>setFrame(current=>current>=maxFrame?0:current+1), 100);
    return ()=>window.clearInterval(interval);
  },[scenario,playing]);
  async function run() {
    if(!rule||!scenario) return;
    setBusy(true);setError("");
    try {setResult(await evaluateReplay(scenario.id,rule));setDecisions({});}
    catch(e){setError(e instanceof Error ? e.message : "Rule evaluation failed");}
    finally{setBusy(false);}
  }
  const boxes = scenario?.tracking_report.boxes.filter(b => b.frame === frame) ?? [];
  const fps = scenario?.tracking_report.media_probe.fps ?? 10;
  const maxFrame = Math.max(0,Math.ceil((scenario?.tracking_report.media_probe.duration_seconds ?? 3)*fps)-1);
  const zone = rule?.zone;
  const decisionsByItem = [...(result?.events ?? []),...(result?.review_items ?? [])];
  function saveSession() {
    if(!scenario||!result||!rule) return;
    const blob = new Blob([JSON.stringify({provenance:"synthetic_fixture", live_inference:false,
      source_scenario:scenario.id,rule,evaluation:result,session_decisions:decisions,
      generated_at:new Date().toISOString(), disclaimer:"Local demo decisions only. Synthetic, hand-authored observations. No actual video or SAM inference."},null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`visionguard-synthetic-replay-${scenario.id}.json`;a.click();URL.revokeObjectURL(url);
  }
  return <main className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">◉</span><strong>VISIONGUARD <span>AI</span></strong></div>
      <Link className="small-link" href="/">Back to video workspace</Link></header>
    <div className="container replay-container">
      <section className="hero"><span className="eyebrow">05 / REPLAY & EVIDENCE</span><h1>Understand events.<br/><span>Inspect uncertainty.</span></h1>
        <p>Interact with the actual deterministic safety-rule evaluator using handcrafted numerical observations. This demo is reproducible, offline, and does not call Meta.</p>
        <div className="replay-warning" role="note"><strong>SYNTHETIC REPLAY — NOT REAL VIDEO.</strong> The moving rectangles are a visualization of generated test data; they are not SAM 3.1 detections or a live camera feed. No accuracy claim is made.</div>
      </section>
      <div className="workspace">
        <section className="panel">
          <div className="section-heading"><div><span className="eyebrow">SCENARIO</span><h2>Reproducible test scenes</h2></div><span className="pill">No API key</span></div>
          <label className="safety-label">Choose a scene
            <select className="safety-input" value={scenario?.id ?? ""} disabled={busy} onChange={e=>void load(e.target.value)}>
              {!scenario&&<option value="">Loading…</option>}{options.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
          </label>
          {scenario&& <p className="helper">{scenario.description}</p>}
          <div className="replay-stage">
            <svg role="img" aria-label="Synthetic numbered-frame object observations and a review zone, not a video" viewBox="0 0 640 360" preserveAspectRatio="xMidYMid meet">
              <rect width="640" height="360" fill="#0b1921"/>
              {Array.from({length:9},(_,i)=><line key={i} x1={0} x2={640} y1={i*45} y2={i*45} stroke="#344951" strokeWidth="1" opacity=".45"/>)}
              {zone&&<rect x={zone.x_min*640} y={zone.y_min*360} width={(zone.x_max-zone.x_min)*640} height={(zone.y_max-zone.y_min)*360} fill="#cfa661" fillOpacity=".07" stroke="#eac378" strokeDasharray="8 5" strokeWidth="3"/>}
              <text x="18" y="30" fontSize="16" fill="#a2bbc7">SYNTHETIC FRAME {frame} · {(frame/fps).toFixed(1)}s</text>
              {boxes.map(b=><g key={`${b.track_id}:${frame}`}>
                <rect x={b.box.left} y={b.box.top} width={b.box.right-b.box.left} height={b.box.bottom-b.box.top}
                  fill="none" stroke={b.concept==="person"?"#45d9b7":b.concept==="car"?"#7bacf6":b.concept==="shopping_cart"?"#bd97ff":"#f3b67a"} strokeWidth="3"/>
                <text x={b.box.left} y={Math.max(52,b.box.top-8)} fill={b.concept==="person"?"#45d9b7":"#f3b67a"} fontSize="15">{b.concept} — {b.track_id.split(":")[1]}</text>
              </g>)}
            </svg>
          </div>
          <div className="replay-transport"><button type="button" className="button button-secondary" onClick={()=>setPlaying(!playing)}>{playing?"Pause":"Play synthetic timeline"}</button>
            <input type="range" aria-label="Synthetic frame" min={0} max={maxFrame} value={frame} onChange={e=>{setPlaying(false);setFrame(Number(e.target.value));}}/>
            <span>{frame}/{maxFrame}</span></div>
          {rule&& <div className="safety-fields">
            <label className="safety-label">Rule type
              <select className="safety-input" value={rule.rule_type} onChange={e=>{setRule({...rule,rule_type:e.target.value as RuleSpec["rule_type"],concept:(e.target.value.startsWith("object_")) ? (rule.concept ?? "person") : null});setResult(null);}}>
                <option value="person_and_forklift_in_zone">Person + forklift in zone</option>
                <option value="person_in_zone">Person in zone</option>
                <option value="object_in_zone">Object dwell in zone</option>
                <option value="object_zone_entry">Object entry transition</option>
              </select></label>
            {(rule.rule_type === "object_in_zone" || rule.rule_type === "object_zone_entry") &&
              <label className="safety-label">Tracked object concept
                <select className="safety-input" value={rule.concept ?? "car"} onChange={e=>{setRule({...rule,concept:e.target.value});setResult(null);}}>
                  {["person","forklift","car","shopping_cart","cardboard_box","excavator"].map(x=><option key={x} value={x}>{x.replaceAll("_"," ")}</option>)}
                </select>
              </label>}
            <label className="safety-label">Minimum duration (seconds)
              <input className="safety-input" type="number" min={0.1} max={30} step={0.1} value={rule.min_duration_seconds}
                onChange={e=>{setRule({...rule,min_duration_seconds:Number(e.target.value)});setResult(null);}} /></label>
          </div>}
          <button type="button" className="button button-primary" disabled={busy||!rule||rule.min_duration_seconds<=0} onClick={()=>void run()}>{busy?"Evaluating…":"Evaluate this rule (offline)"}</button>
          {error && <p role="alert" className="error">{error}</p>}
          <p className="helper">Rule evaluation is the same Python function used in the local video workspace. The synthetic input is controlled test data, not independent model validation.</p>
        </section>
        <section className="panel"><div className="section-heading"><div><span className="eyebrow">EVIDENCE</span><h2>Inspectable event timeline</h2></div><span className="pill">Human-reviewed</span></div>
          {!result&&<p className="helper">Choose a synthetic scenario and evaluate a rule to inspect observed matches and uncertain intervals.</p>}
          {result&&<div className="replay-results">
            <div className="evidence-metrics"><div><strong>{result.event_count}</strong><small>Observed matches</small></div><div><strong>{result.review_count}</strong><small>Review items</small></div><div><strong>{Object.keys(decisions).length}</strong><small>Decisions this session</small></div></div>
            <p className="helper">Outcome: <strong>{prettyKind(result.outcome)}</strong>. {result.disclaimer}</p>
            {decisionsByItem.map((item,i)=>{
              const trackId = "track_id" in item ? item.track_id ?? "unknown" : "unknown";
              const key=item.event_id??`gap:${trackId}:${item.start_frame}-${item.end_frame}`;
              return <article className="evidence-item" key={`${key}:${i}`}>
                <div className="evidence-item-head"><strong>{item.status==="potential_hazard"?"Observed potential hazard":"Needs review"}</strong><span className="pill">{decisions[key]??"Pending"}</span></div>
                <button type="button" className="small-link" onClick={()=>{setPlaying(false);setFrame(item.start_frame);}}>Seek: frames {item.start_frame}–{item.end_frame}</button>
                <p>{item.reason}</p>
                <div className="evidence-decisions">
                  {(["confirmed","rejected","unresolved"] as const).map(d=><button type="button" key={d} onClick={()=>setDecisions(prev=>({...prev,[key]:d}))}>{d}</button>)}
                </div>
              </article>;
            })}
            {decisionsByItem.length===0&&<p className="helper">No observed matching event or localized review item. That does not establish safety.</p>}
            <button type="button" className="button button-secondary" onClick={saveSession}>Export synthetic evaluation JSON</button>
            <p className="helper">Review choices on this page exist only in browser memory until exported. They are not saved on the server.</p>
          </div>}
        </section>
      </div>
      <footer><span>VISIONGUARD AI · Synthetic replay only</span><span>No copyrighted footage, real model output, or live inference included</span></footer>
    </div>
  </main>;
}
