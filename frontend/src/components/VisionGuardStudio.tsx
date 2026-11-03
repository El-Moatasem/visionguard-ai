"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import CameraCapture from "@/components/CameraCapture";
import TrackingViewer from "@/components/TrackingViewer";
import ActiveTrackingJobs from "@/components/ActiveTrackingJobs";
import { fetchVideos, uploadVideo, prepareVideoForSam, deleteVideo, deleteAllVideos, type VideoItem } from "@/lib/api";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

type Props = { requestedVideoId?: string; openCamera?: boolean };

export default function VisionGuardStudio({ requestedVideoId, openCamera = false }: Props) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [selected, setSelected] = useState<VideoItem | null>(null);
  const [chosen, setChosen] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [prepareStart, setPrepareStart] = useState(0);
  const maxSamSeconds = Math.min(600, Math.max(1, Number(process.env.NEXT_PUBLIC_SAM_MAX_DURATION_SECONDS || "120") || 120));
  const [prepareDuration, setPrepareDuration] = useState(20);
  const [preparing, setPreparing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [prepareError, setPrepareError] = useState("");

  const reload = useCallback(async (videoId?: string) => {
    setLoading(true);
    setError("");
    try {
      const items = await fetchVideos();
      setVideos(items);
      setSelected(previous => items.find(v => v.id === (videoId || previous?.id)) ?? items[0] ?? null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load uploaded videos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void reload(requestedVideoId); }, [reload, requestedVideoId]);

  function chooseFile(file?: File) {
    setUploadError("");
    if (!file) return;
    if (file.size === 0 || file.size > MAX_UPLOAD_BYTES) {
      setChosen(null);
      setUploadError("Select a nonempty MP4, MOV, or WebM file under 100 MiB. Tracking requires MP4/MOV under 25 MiB.");
      return;
    }
    setChosen(file);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
    event.target.value = "";
  }

  async function submit() {
    if (!chosen || uploading) return;
    setUploadError("");
    setUploading(true);
    try {
      const created = await uploadVideo(chosen);
      setChosen(null);
      setSelected(created);
      await reload(created.id);
      router.replace(`/studio?video=${encodeURIComponent(created.id)}`, { scroll: false });
    } catch (cause) {
      setUploadError(cause instanceof Error ? cause.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function prepareSelectedVideo() {
    if (!selected || preparing) return;
    setPrepareError("");
    setPreparing(true);
    try {
      const derivative = await prepareVideoForSam(selected.id, prepareStart, prepareDuration);
      setSelected(derivative);
      await reload(derivative.id);
      router.replace(`/studio?video=${encodeURIComponent(derivative.id)}`, {scroll: false});
    } catch (cause) {
      setPrepareError(cause instanceof Error ? cause.message : "Could not prepare a SAM-ready clip");
    } finally {
      setPreparing(false);
    }
  }

  async function refreshAfterDeletion() {
    const items = await fetchVideos();
    setVideos(items);
    const next = items.find(item => item.id === selected?.id) ?? items[0] ?? null;
    setSelected(next);
    router.replace(next ? `/studio?video=${encodeURIComponent(next.id)}` : "/studio", {scroll:false});
  }
  async function removeOne(item: VideoItem) {
    if (deleting || !window.confirm(`Delete "${item.name}" and associated prepared clips, tracking jobs and evidence permanently?`)) return;
    setDeleting(true); setDeleteError("");
    try {await deleteVideo(item.id); await refreshAfterDeletion();}
    catch (cause) {setDeleteError(cause instanceof Error ? cause.message : "Deletion failed");}
    finally {setDeleting(false);}
  }
  async function removeEverything() {
    if (deleting || !videos.length) return;
    const typed = window.prompt(`Permanently delete ALL stored uploaded videos, including any not shown in the recent library, and their analyses?\nType DELETE ALL VIDEOS:`);
    if (typed !== "DELETE ALL VIDEOS") return;
    setDeleting(true); setDeleteError("");
    try {await deleteAllVideos(); await refreshAfterDeletion();}
    catch (cause) {setDeleteError(cause instanceof Error ? cause.message : "Clear library failed");}
    finally {setDeleting(false);}
  }

  return <main className="vg-gallery-page">
    <header className="vg-gallery-topbar">
      <Link href="/" className="vg-brand"><span className="vg-brand-symbol" aria-hidden="true">◈</span><span>VISIONGUARD <b>AI</b><small>SCENE INTELLIGENCE</small></span></Link>
      <nav className="vg-top-links" aria-label="Main navigation">
        <Link className="vg-top-link" href="/">Gallery</Link>
        <Link className="vg-top-link vg-top-link-active" href="/studio" aria-current="page">Analysis Studio</Link>
        <Link className="vg-top-link" href="/replay">Synthetic Replay</Link>
      </nav>
      <span className="vg-top-environment"><i /> LOCAL VIDEO WORKSPACE</span>
    </header>
    <div className="vg-gallery-container">
      <section className="vg-studio-heading">
        <div><div className="vg-eyebrow">REAL FOOTAGE · REVIEWER-CONTROLLED RULES</div><h1>Analysis Studio</h1><p>Inspect footage, track people and forklifts with SAM, draw zones, and review evidence.</p></div>
        <Link className="vg-cta-outline" href="/">← Back to Gallery</Link>
      </section>
      <div className="vg-studio-grid">
        <section className="vg-studio-player" aria-label="Selected video analysis">
          <div className="vg-studio-player-header"><strong>{selected?.name || "No video selected"}</strong><span>{selected ? (selected.sam_compatible_container ? "MP4/MOV · Check preflight for tracking" : "WebM · Convert before tracking") : "SELECT A VIDEO"}</span></div>
          {selected ? <TrackingViewer key={selected.id} video={selected} /> :
            <div className="vg-studio-empty">{loading ? "Loading your video library…" : <div><strong>Start by uploading a video</strong><p>Choose a clip on the right to open the full Analysis Studio.</p></div>}</div>}
        </section>
        <aside className="vg-studio-side" aria-label="Video controls">
          <section className="vg-side-panel"><span className="vg-side-title">01 / ADD A VIDEO</span><h2>Upload or capture</h2>
            <p>Uploads are stored first; SAM inference only starts when you explicitly choose it in the analysis panel.</p>
            <input type="file" ref={fileInput} hidden accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" aria-label="Choose local video" onChange={onFileChange}/>
            <div className="vg-quick-upload-buttons"><button type="button" className="vg-small-quiet" disabled={uploading} onClick={()=>fileInput.current?.click()}>Choose video</button><button type="button" className="vg-small-primary" disabled={!chosen || uploading} onClick={()=>void submit()}>{uploading ? "Uploading…" : "Upload & select"}</button></div>
            {chosen && <p className="vg-side-file">Selected: {chosen.name} ({(chosen.size / 1048576).toFixed(1)} MiB)</p>}
            {uploadError && <p role="alert" className="error">{uploadError}</p>}
            <details open={openCamera}><summary>Camera recording (15-second clips)</summary><CameraCapture onCaptured={chooseFile} /><p>After recording, select Upload & select. Browser WebM recordings need conversion before SAM inference.</p></details>
          </section>
          <ActiveTrackingJobs videoNames={Object.fromEntries(videos.map(item => [item.id, item.name]))} />
          <section className="vg-side-panel" aria-label="Prepare video for SAM">
            <span className="vg-side-title">02 / PREPARE FOR SAM</span>
            <h2>Make an analysis-ready clip</h2>
            <p>For oversized, long, or WebM videos, choose a segment and prepare a compressed MP4 locally. The original stays unchanged. Preparing uses FFmpeg, not Meta credits.</p>
            {selected?.analysis_source_video_id && <p className="vg-side-file">Prepared from your original video, starting at {selected.analysis_start_seconds ?? 0}s. This exact clip is used for SAM playback.</p>}
            <div className="vg-quick-upload-buttons">
              <label className="safety-label">Start (seconds)
                <input className="safety-input" type="number" min={0} max={3600} step={0.5} value={prepareStart}
                  onChange={e=>setPrepareStart(Number(e.target.value))} disabled={preparing}/>
              </label>
              <label className="safety-label">Duration (max {maxSamSeconds}s)
                <input className="safety-input" type="number" min={0.5} max={maxSamSeconds} step={0.5} value={prepareDuration}
                  onChange={e=>setPrepareDuration(Number(e.target.value))} disabled={preparing}/>
              </label>
            </div>
            <div className="vg-quick-upload-buttons">
              <button type="button" className="vg-small-primary" disabled={!selected || preparing || prepareDuration<=0 || prepareDuration>maxSamSeconds || prepareStart<0}
                onClick={()=>void prepareSelectedVideo()}>{preparing ? "Preparing clip…" : "Prepare MP4 (no Meta charge)"}</button>
            </div>
            {prepareError && <p className="error" role="alert">{prepareError}</p>}
            <p>The prepared video appears in Recent Uploads and is selected automatically. Press Analyze with SAM separately to start paid tracking.</p>
          </section>
          <section className="vg-side-panel"><span className="vg-side-title">04 / YOUR VIDEO LIBRARY</span><h2>Recent uploads ({videos.length})</h2>
            {error && <p role="alert" className="error">{error} <button type="button" className="vg-small-quiet" onClick={()=>void reload(requestedVideoId)}>Retry</button></p>}
            <div className="vg-side-list">
              {videos.map(video=><div className="vg-studio-video-row" key={video.id}>
                <button type="button" className="vg-video-select" aria-current={selected?.id === video.id} title={video.name}
                  onClick={()=>{setSelected(video);router.replace(`/studio?video=${encodeURIComponent(video.id)}`, {scroll:false});}}>
                  {selected?.id === video.id ? "● " : "▷ "}{video.name}
                </button>
                <button type="button" className="vg-studio-delete" disabled={deleting} onClick={()=>void removeOne(video)}
                  aria-label={`Delete ${video.name}`}>Delete</button>
              </div>)}
              {!loading && !videos.length && !error && <p>No uploaded videos yet. Your first upload will appear here.</p>}
            </div>
            <div className="vg-quick-upload-buttons"><button type="button" className="vg-small-quiet" disabled={loading || deleting} onClick={()=>void reload(requestedVideoId)}>Refresh library</button><Link className="vg-small-quiet" href="/replay">Synthetic demos ↗</Link></div>
            {videos.length > 0 && <button type="button" className="vg-card-delete-all" disabled={deleting} onClick={()=>void removeEverything()}>
              {deleting ? "Deleting…" : "Delete all uploaded videos"}</button>}
            {deleteError && <p role="alert" className="error">{deleteError}</p>}
          </section>
          <section className="vg-side-panel"><span className="vg-side-title">05 / ANALYSIS NOTES</span><h2>How the studio works</h2>
            <p>Use the SAM tracking section below your video to start billable inference. Supported concepts are <strong>person</strong> and <strong>forklift</strong>. Then draw a zone, run a supported rule, and inspect evidence.</p>
            <p>Stored uploads can be up to 100 MiB. SAM preflight currently requires an MP4/MOV of at most 100 MiB, {maxSamSeconds} seconds, 15,000 frames, and 1080p/30 FPS, with FFprobe available on the backend.</p>
            <p>Tracking runs after a clip is captured or uploaded. It is not continuous live-camera analysis or safety certification.</p>
          </section>
        </aside>
      </div>
      <footer className="vg-gallery-footer"><span>VISIONGUARD AI · Research prototype</span><span>Keep unauthorized footage and API credentials off public deployments.</span></footer>
    </div>
  </main>;
}
