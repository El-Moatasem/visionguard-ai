"use client";

import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import CameraCapture from "@/components/CameraCapture";
import TrackingViewer from "@/components/TrackingViewer";
import { fetchVideos, uploadVideo, type VideoItem } from "@/lib/api";

const MAX_BYTES = 25 * 1024 * 1024;

export default function Home() {
  const picker = useRef<HTMLInputElement>(null);
  const phonePicker = useRef<HTMLInputElement>(null);
  const [chosen, setChosen] = useState<File | null>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [selected, setSelected] = useState<VideoItem | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      const items = await fetchVideos();
      setVideos(items);
      setSelected((current) => items.find((v) => v.id === current?.id) ?? items[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Video list unavailable");
    }
  }, []);

  useEffect(() => { void reload(); }, [reload]);

  function chooseFile(file: File | undefined) {
    if (!file) return;
    setError("");setMessage("");
    if (file.size > MAX_BYTES) {
      setError("Choose a video under 25 MiB. Trim or compress it first.");
      setChosen(null);return;
    }
    setChosen(file);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
    event.target.value = "";
  }

  async function submit() {
    if (!chosen || busy) return;
    setBusy(true);setError("");setMessage("");
    try {
      const created = await uploadVideo(chosen);
      setChosen(null);
      await reload();
      setSelected(created);
      setMessage(`Uploaded ${created.name}. Select it for optional SAM tracking. Danger detection is a later milestone.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally { setBusy(false); }
  }

  return <main className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">◉</span><strong>VISIONGUARD <span>AI</span></strong></div><span className="top-status"><span className="status-dot" /> Hackathon MVP · Object tracking</span></header>
    <div className="container">
      <section className="hero"><div className="eyebrow">VISUAL SAFETY INTELLIGENCE • FOUNDATION</div><h1>Capture the scene.<br /><span>Understand what happened.</span></h1><p>Upload or record authorized workplace footage. Capture and upload short authorized clips, then optionally analyze people and forklifts with hosted SAM 3.1. Hazard detection follows in a later milestone.</p></section>
      <div className="workspace">
        <div className="column">
          <section className="panel"><div className="section-heading"><div><span className="eyebrow">01 / INGEST</span><h2>Upload a video</h2></div><span className="pill">MP4 · MOV · WebM</span></div>
            <div className="dropzone" onClick={() => picker.current?.click()} role="button" tabIndex={0} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); picker.current?.click(); } }}>
              <div className="upload-icon">↑</div><strong>{chosen ? chosen.name : "Select a short video"}</strong><span>{chosen ? `${(chosen.size / 1024 / 1024).toFixed(1)} MiB ready` : "Max 25 MiB · MP4, MOV or WebM"}</span>
            </div>
            <input ref={picker} type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" hidden onChange={onFileChange} aria-label="Select a video" />
            <input ref={phonePicker} type="file" accept="video/*" capture="environment" hidden onChange={onFileChange} aria-label="Record video with phone" />
            <div className="button-row"><button className="button button-primary" type="button" disabled={!chosen || busy} onClick={submit}>{busy ? "Uploading…" : "Upload video"}</button>
            <button className="button button-secondary" type="button" onClick={() => phonePicker.current?.click()}>Capture with phone</button></div>
          </section>
          <CameraCapture onCaptured={chooseFile} />
        </div>
        <section className="panel library-panel"><div className="section-heading"><div><span className="eyebrow">02 / REVIEW</span><h2>Video workspace</h2></div><button className="small-link" type="button" onClick={() => void reload()}>Refresh</button></div>
          <div className="player-wrap">{selected ? <TrackingViewer key={selected.id} video={selected} /> : <div className="empty-player"><span>▶</span><p>No videos uploaded yet</p></div>}</div>
          {selected && <div className="video-detail"><strong>{selected.name}</strong><span>{(selected.size_bytes / 1024 / 1024).toFixed(1)} MiB · {selected.media_type}</span><span className={selected.sam_compatible_container ? "tag tag-green" : "tag tag-amber"}>{selected.sam_compatible_container ? "MP4/MOV container" : "WebM • convert before SAM"}</span></div>}
          <div className="library-heading"><span>RECENT UPLOADS</span><span>{videos.length} item(s)</span></div>
          <div className="video-list">{videos.length ? videos.map(v => <button type="button" key={v.id} className={`video-row ${selected?.id === v.id ? "is-selected" : ""}`} onClick={() => setSelected(v)}><span className="video-thumb">▶</span><span className="video-info"><strong>{v.name}</strong><small>{new Date(v.created_at).toLocaleString()} · {(v.size_bytes / 1024 / 1024).toFixed(1)} MiB</small></span></button>) : <p className="helper">Uploaded videos will appear here.</p>}</div>
        </section>
      </div>
      {(message || error) && <div className={error ? "toast toast-error" : "toast"} role={error ? "alert" : "status"}>{error || message}</div>}
      <footer><span>VISIONGUARD AI · Research prototype</span><span>Not a certified safety monitor · Never upload confidential or unconsented footage</span></footer>
    </div>
  </main>;
}
