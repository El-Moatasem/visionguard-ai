"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { playbackUrl, type DemoScenario, type VideoItem } from "@/lib/api";

export default function DemoLibrary({scenarios, videos, selectedId, onSelectVideo, onImport}: {
  scenarios: DemoScenario[];
  videos: VideoItem[];
  selectedId: string | null;
  onSelectVideo: (item: VideoItem) => void;
  onImport: (scenarioId: string) => void;
}) {
  const [term, setTerm] = useState("");
  const [filter, setFilter] = useState("all");
  const available = useMemo(() => new Map<string, VideoItem | undefined>(scenarios.map(s => [s.id, videos.find(v => v.scenario_id === s.id)] as const)), [scenarios, videos]);
  const q = term.trim().toLowerCase();
  const entries = scenarios.filter(s => (filter === "all" || s.industry === filter) &&
    (!q || `${s.title} ${s.industry} ${s.description}`.toLowerCase().includes(q)));
  const uploads = videos.filter(v => v.library_source !== "demo" && (!q || v.name.toLowerCase().includes(q)));
  return <section className="sceneops-library" aria-label="Prepared demos and uploaded videos">
    <div className="section-heading"><div><span className="eyebrow">01 / SCENE LIBRARY</span><h2>Choose a scene</h2></div><span className="pill">SceneOps Engine</span></div>
    <p className="helper">Prepared scenarios and your uploads share one library. Choosing a scene never runs a billable model call.</p>
    <div className="sceneops-filters">
      <input className="safety-input" aria-label="Search demo library" placeholder="Search videos and scenarios" value={term} onChange={e => setTerm(e.target.value)}/>
      <select className="safety-input" aria-label="Filter industry" value={filter} onChange={e => setFilter(e.target.value)}>
        {["all", "Warehouse", "Parking", "Retail", "Construction"].map(x=><option value={x} key={x}>{x === "all" ? "All industries" : x}</option>)}
      </select>
    </div>
    <div className="sceneops-demo-grid">
      {entries.map(s => {
        const video=available.get(s.id);
        return <article className={`sceneops-demo ${video && video.id === selectedId ? "is-selected" : ""}`} key={s.id}>
          <div className="sceneops-demo-media">
            {video ? <video muted playsInline preload="metadata" src={`${playbackUrl(video)}#t=0.1`} aria-label={`${s.title} preview`} /> : <div className="sceneops-demo-placeholder" aria-hidden="true">{s.industry === "Parking" ? "P" : s.industry === "Retail" ? "R" : s.industry === "Construction" ? "C" : "W"}</div>}
          </div>
          <div className="sceneops-demo-copy"><strong>{s.title}</strong><span>{s.description}</span>
            <small>{video ? "Prepared footage installed" : s.replay_id ? "Synthetic replay available · footage optional" : "Awaiting authorized footage"}</small>
            <div className="sceneops-demo-actions">
              {video && <button className="button button-primary" onClick={() => onSelectVideo(video)} type="button">{selectedId === video.id ? "Selected" : "Open video"}</button>}
              <button className="button button-secondary" onClick={() => onImport(s.id)} type="button">{video ? "Replace with new upload" : "Add video"}</button>
              {s.replay_id && <Link className="button button-quiet evidence-link" href="/replay">Synthetic replay</Link>}
            </div>
          </div>
        </article>;
      })}
    </div>
    <h3 className="sceneops-heading">My uploads <span>{uploads.length}</span></h3>
    <div className="video-list">
      {uploads.map(v=><button className={`video-row ${v.id === selectedId ? "is-selected" : ""}`} key={v.id} type="button" onClick={() => onSelectVideo(v)}>
        <span className="video-thumb">▶</span><span className="video-info"><strong>{v.name}</strong><small>{(v.size_bytes/1048576).toFixed(2)} MiB · {new Date(v.created_at).toLocaleString()}</small></span>
      </button>)}
      {uploads.length === 0 && <p className="helper">New uploads automatically appear here; no SAM credits spent until Analyze is clicked.</p>}
    </div>
  </section>;
}
