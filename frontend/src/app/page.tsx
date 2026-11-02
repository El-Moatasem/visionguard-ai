"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchReplayScenarios,
  fetchVideos,
  deleteVideo, deleteAllVideos,
  playbackUrl,
  uploadVideo,
  type ReplaySummary,
  type VideoItem,
} from "@/lib/api";
import "./visionguard-gallery.css";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
const REPLAY_ONLY = process.env.NEXT_PUBLIC_REPLAY_ONLY === "1";

type Filter = "all" | "uploaded" | "replay" | "planned";
type PreviewTheme = "warehouse" | "occlusion" | "clear" | "parking" | "retail" | "operator";
const fixtureThemes: Record<string, PreviewTheme> = {
  "warehouse-copresence": "warehouse",
  "occlusion-review": "occlusion",
  "clear-aisle": "clear",
  "parking-car-dwell": "parking",
  "retail-cart-aisle": "retail",
  "construction-zone-entry": "operator",
};
const planned = [
  { id: "parking-lot", title: "Parking lot", description: "Vehicle classification and parking-rule extensions are planned.", theme: "parking" as PreviewTheme },
  { id: "shopping-cart", title: "Shopping cart", description: "Cart detection and retail rule types are not implemented yet.", theme: "retail" as PreviewTheme },
  { id: "operator-protocol", title: "Operator exclusion", description: "Real driver/pedestrian validation requires explicit operator identification and a tested clip.", theme: "operator" as PreviewTheme },
];

function Brand() {
  return <Link href="/" className="vg-brand" aria-label="VisionGuard AI home">
    <span className="vg-brand-symbol" aria-hidden="true">◈</span>
    <span>VISIONGUARD <b>AI</b><small>SCENE INTELLIGENCE</small></span>
  </Link>;
}

function SceneVisual({ theme }: { theme: PreviewTheme }) {
  // Original stylized illustration. Not a video thumbnail or SAM model output.
  return <div className={`vg-scene vg-scene-${theme}`} aria-hidden="true">
    <div className="vg-scene-horizon" />
    <div className="vg-scene-rack vg-rack-left" />
    <div className="vg-scene-rack vg-rack-right" />
    {(theme === "warehouse" || theme === "operator" || theme === "occlusion") && <div className="vg-scene-forklift"><i /><i /></div>}
    {(theme === "warehouse" || theme === "retail" || theme === "operator") && <div className="vg-scene-person" />}
    {theme === "retail" && <div className="vg-scene-cart" />}
    {theme === "parking" && <><div className="vg-scene-car vg-car-one" /><div className="vg-scene-car vg-car-two" /></>}
    <span className="vg-preview-notice">ILLUSTRATION</span>
  </div>;
}

const STOCK_PHOTOS: Record<PreviewTheme, { url: string; alt: string }> = {
  warehouse: {
    url: "https://images.unsplash.com/photo-1700952633135-fd1d2a74a557?auto=format&fit=crop&w=1000&q=78",
    alt: "Real stock photograph of a person standing near a forklift in a warehouse",
  },
  occlusion: {
    url: "https://images.unsplash.com/photo-1714627798569-b3e36d409c4b?auto=format&fit=crop&w=1000&q=78",
    alt: "Real stock photograph of a forklift in a warehouse; not a validated occlusion",
  },
  clear: {
    url: "https://images.unsplash.com/photo-1694885169342-909981fb408a?auto=format&fit=crop&w=1000&q=78",
    alt: "Real stock photograph of an empty warehouse",
  },
  parking: {
    url: "https://images.unsplash.com/photo-1772440222970-c1a9d5d38a19?auto=format&fit=crop&w=1000&q=78",
    alt: "Real stock aerial photograph of vehicles in a parking lot",
  },
  retail: {
    url: "https://images.unsplash.com/photo-1739300293398-468ba82fd418?auto=format&fit=crop&w=1000&q=78",
    alt: "Real stock photograph of a shopping cart and shopper in a grocery aisle",
  },
  operator: {
    url: "https://images.unsplash.com/photo-1774031059266-7e2a54c690ac?auto=format&fit=crop&w=1000&q=78",
    alt: "Real stock photograph of a construction worker near heavy equipment",
  },
};

function StockDemoPhoto({ theme }: { theme: PreviewTheme }) {
  // Stock photographs illustrate a domain, NOT the synthetic scenario's frames.
  const [failed, setFailed] = useState(false);
  const photo = STOCK_PHOTOS[theme];
  if (failed) return <SceneVisual theme={theme} />;
  return <div className="vg-demo-stock-photo">
    {/* External photograph; do not label this as a SAM detection or frame from replay. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={photo.url} alt={photo.alt} loading="lazy" onError={() => setFailed(true)} />
    <span className="vg-photo-credit">STOCK PHOTO · NOT SAM OUTPUT</span>
  </div>;
}

function UploadVisual({ item }: { item: VideoItem }) {
  return <div className="vg-upload-visual">
    <video
      src={`${playbackUrl(item)}#t=0.1`}
      preload="metadata"
      muted
      playsInline
      aria-hidden="true"
      tabIndex={-1}
    />
    <span className="vg-video-play" aria-hidden="true">▶</span>
  </div>;
}

function VideoCard({ item }: { item: VideoItem }) {
  return <Link className="vg-video-card" href={`/studio?video=${encodeURIComponent(item.id)}`}>
    <div className="vg-video-card-art"><UploadVisual item={item}/><span className="vg-content-chip vg-chip-upload">YOUR UPLOAD</span></div>
    <div className="vg-card-body">
      <strong title={item.name}>{item.name}</strong>
      <p>{(item.size_bytes / 1024 / 1024).toFixed(1)} MiB · {item.sam_compatible_container ? "MP4/MOV" : "Conversion needed for SAM"}</p>
      <span className="vg-card-link">Open in Analysis Studio <span aria-hidden="true">↗</span></span>
    </div>
  </Link>;
}

function ReplayCard({ item }: { item: ReplaySummary }) {
  const theme = fixtureThemes[item.id] || "warehouse";
  return <Link className="vg-video-card" href={`/replay?scenario=${encodeURIComponent(item.id)}`}>
    <div className="vg-video-card-art"><StockDemoPhoto theme={theme}/><span className="vg-content-chip vg-chip-replay">SYNTHETIC REPLAY</span></div>
    <div className="vg-card-body"><strong>{item.title}</strong><p>{item.description}</p>
      <span className="vg-card-link">Run deterministic replay <span aria-hidden="true">↗</span></span></div>
  </Link>;
}

export default function GalleryPage() {
  const router = useRouter();
  const picker = useRef<HTMLInputElement>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [scenarios, setScenarios] = useState<ReplaySummary[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [videoError, setVideoError] = useState("");
  const [replayError, setReplayError] = useState("");

  useEffect(() => {
    let active = true;
    async function initialize() {
      const [videoResult, replayResult] = await Promise.allSettled([
        REPLAY_ONLY ? Promise.resolve([] as VideoItem[]) : fetchVideos(),
        fetchReplayScenarios(),
      ]);
      if (!active) return;
      if (videoResult.status === "fulfilled") setVideos(videoResult.value);
      else setVideoError(videoResult.reason instanceof Error ? videoResult.reason.message : "Video library unavailable");
      if (replayResult.status === "fulfilled") setScenarios(replayResult.value);
      else setReplayError(replayResult.reason instanceof Error ? replayResult.reason.message : "Replay demos unavailable");
      setLoading(false);
    }
    void initialize();
    return () => { active = false; };
  }, []);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    setError("");
    if (!file) return;
    if (file.size === 0 || file.size > MAX_UPLOAD_BYTES) {
      setError("Select a nonempty video smaller than 100 MiB. SAM analysis has a separate 25 MiB limit.");
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  }

  async function handleUpload() {
    if (!selectedFile || uploading || REPLAY_ONLY) return;
    setUploading(true);
    setError("");
    try {
      const created = await uploadVideo(selectedFile);
      router.push(`/studio?video=${encodeURIComponent(created.id)}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Video upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function removeVideo(item: VideoItem) {
    if (deleting || !window.confirm(`Permanently delete "${item.name}"? Any prepared clips, SAM jobs, and evidence derived from it will also be deleted.`)) return;
    setDeleting(true); setDeleteError("");
    try { await deleteVideo(item.id); setVideos(await fetchVideos()); }
    catch (cause) {setDeleteError(cause instanceof Error ? cause.message : "Delete failed");}
    finally {setDeleting(false);}
  }
  async function clearLibrary() {
    if (deleting || !videos.length) return;
    const typed = window.prompt(`Delete ALL stored uploaded videos (including older videos not shown here), prepared clips, tracking jobs and evidence permanently?\nType DELETE ALL VIDEOS to confirm:`);
    if (typed !== "DELETE ALL VIDEOS") return;
    setDeleting(true); setDeleteError("");
    try { await deleteAllVideos(); setVideos(await fetchVideos()); }
    catch (cause) {setDeleteError(cause instanceof Error ? cause.message : "Clear library failed");}
    finally {setDeleting(false);}
  }

  const search = query.trim().toLocaleLowerCase();
  const shownVideos = useMemo(() => videos.filter(item => item.name.toLocaleLowerCase().includes(search)), [videos, search]);
  const shownScenarios = useMemo(() => scenarios.filter(item => (item.title + " " + item.description).toLocaleLowerCase().includes(search)), [scenarios, search]);
  const shownPlanned = planned.filter(item => (item.title + " " + item.description).toLocaleLowerCase().includes(search));
  const hasContent =
    ((filter === "all" || filter === "uploaded") && shownVideos.length > 0) ||
    ((filter === "all" || filter === "replay") && shownScenarios.length > 0) ||
    ((filter === "all" || filter === "planned") && shownPlanned.length > 0);

  return <main className="vg-gallery-page">
    <header className="vg-gallery-topbar">
      <Brand />
      <nav className="vg-top-links" aria-label="Main navigation">
        <Link className="vg-top-link vg-top-link-active" href="/" aria-current="page">Gallery</Link>
        {!REPLAY_ONLY && <Link className="vg-top-link" href="/studio">Analysis Studio</Link>}
        <Link className="vg-top-link" href="/replay">Synthetic Replay</Link>
      </nav>
      <span className="vg-top-environment"><i /> {REPLAY_ONLY ? "REPLAY ONLY" : "LOCAL RESEARCH MVP"}</span>
    </header>

    <div className="vg-gallery-container">
      <section className="vg-hero-grid" aria-labelledby="vg-main-title">
        <div className="vg-hero-copy">
          <div className="vg-eyebrow"><span className="vg-eyebrow-rule"/> VIDEO INTELLIGENCE, MADE EXPLAINABLE</div>
          <h1 id="vg-main-title">Explore the scene.<br/><em>See the evidence.</em></h1>
          <p>Choose a scenario, bring a new video, or capture a short clip. Turn real SAM observations into zone-based, human-reviewable evidence.</p>
          {REPLAY_ONLY ? <div className="vg-hero-actions"><Link className="vg-cta-main" href="/replay">Explore synthetic replay <span aria-hidden="true">↗</span></Link></div> :
            <div className="vg-hero-actions">
              <button type="button" className="vg-cta-main" onClick={() => picker.current?.click()}><span aria-hidden="true">↑</span> Upload a video</button>
              <Link className="vg-cta-outline" href="/studio?capture=1">◉ Record a clip</Link>
            </div>}
          <div className="vg-hero-foot"><span><i /> {REPLAY_ONLY ? "Synthetic test fixtures" : "Real clips + synthetic tests"}</span><span>•</span><span>Inspectable, not automatic safety certification</span></div>
        </div>
        <div className="vg-hero-art" role="img" aria-label="Stylized illustration of a monitored warehouse scene, not actual model inference">
          <SceneVisual theme="warehouse" />
          <div className="vg-hero-outline vg-hero-outline-person"><span>PERSON</span></div>
          <div className="vg-hero-outline vg-hero-outline-forklift"><span>FORKLIFT</span></div>
          <div className="vg-hero-art-top">SCENE 001 <span>ILLUSTRATION ONLY</span></div>
          <div className="vg-hero-art-bottom"><span>VISIONGUARD · FRAME INSPECTION</span><span>◌ 00:08</span></div>
        </div>
      </section>

      {!REPLAY_ONLY && <section className="vg-quick-upload" aria-label="Quick upload">
        <input ref={picker} type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" onChange={chooseFile} hidden aria-label="Select a video"/>
        <div className="vg-quick-upload-copy"><span className="vg-upload-glyph" aria-hidden="true">↥</span><div><strong>{selectedFile ? selectedFile.name : "Have your own footage?"}</strong><small>{selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(1)} MiB selected · upload to open Studio` : "MP4 · MOV · WebM, up to 100 MiB for storage"}</small></div></div>
        <div className="vg-quick-upload-buttons"><button type="button" className="vg-small-quiet" disabled={uploading} onClick={() => picker.current?.click()}>{selectedFile ? "Change file" : "Browse files"}</button>{selectedFile && <button type="button" className="vg-small-primary" disabled={uploading} onClick={() => void handleUpload()}>{uploading ? "Uploading…" : "Upload & open studio ↗"}</button>}</div>
        {error && <div className="vg-inline-error" role="alert">{error}</div>}
      </section>}

      <section className="vg-library" aria-labelledby="vg-library-title">
        <div className="vg-library-heading"><div><span className="vg-eyebrow">THE SCENE LIBRARY</span><h2 id="vg-library-title">Choose where to begin.</h2><p>Real uploads go to the Analysis Studio. Synthetic fixtures evaluate the existing rule engine offline.</p></div>
        <div className="vg-library-search"><span aria-hidden="true">⌕</span><input value={query} onChange={event=>setQuery(event.target.value)} type="search" placeholder="Search scenarios or videos" aria-label="Search scenarios or videos" /></div></div>
        <div className="vg-library-filters" role="group" aria-label="Filter scenes">
          {([ ["all","All scenes"], ["uploaded","My uploads"], ["replay","Synthetic replay"], ["planned","Future concepts"] ] as const).map(([value,label])=><button key={value} className={filter===value ? "vg-filter vg-filter-on" : "vg-filter"} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}</button>)}
        </div>
        {loading ? <div className="vg-empty-state" role="status">Loading scene library…</div> : <>
          {videoError && <p className="vg-library-alert" role="alert">Upload library unavailable: {videoError}. Replay scenarios can still be opened.</p>}
          {replayError && <p className="vg-library-alert" role="alert">Replay catalog unavailable: {replayError}. Check the backend connection.</p>}
          {!REPLAY_ONLY && videos.length > 0 && <div className="vg-library-delete-bar">
            <span>Manage uploaded videos ({videos.length} shown)</span>
            <button className="vg-card-delete-all" type="button" disabled={deleting} onClick={()=>void clearLibrary()}>
              {deleting ? "Deleting…" : "Delete all uploaded videos"}
            </button>
          </div>}
          {deleteError && <div role="alert" className="vg-library-alert">{deleteError}</div>}
          {(filter === "all" || filter === "uploaded") && shownVideos.length > 0 && <div className="vg-library-section"><div className="vg-section-line"><h3>Your uploaded videos</h3><span>{shownVideos.length} {shownVideos.length===1?"clip":"clips"}</span></div><div className="vg-card-grid">{shownVideos.map(item=><div className="vg-deletable-card" key={item.id}>
            <VideoCard item={item}/>
            <button type="button" className="vg-card-delete" disabled={deleting} onClick={()=>void removeVideo(item)}
              aria-label={`Delete ${item.name} and related analyses`}>{deleting ? "Working…" : "Delete video"}</button>
          </div>)}</div></div>}
          {(filter === "all" || filter === "replay") && shownScenarios.length > 0 && <div className="vg-library-section"><div className="vg-section-line"><h3>Interactive synthetic demos</h3><span>No model credits · Not actual video</span></div><div className="vg-card-grid">{shownScenarios.map(item=><ReplayCard item={item} key={item.id}/>)}</div></div>}
          {(filter === "all" || filter === "planned") && shownPlanned.length > 0 && <div className="vg-library-section"><div className="vg-section-line"><h3>Future SceneOps concepts</h3><span>Not available for analysis</span></div><div className="vg-card-grid">{shownPlanned.map(item=><article className="vg-video-card vg-video-card-planned" key={item.id}><div className="vg-video-card-art"><SceneVisual theme={item.theme}/><span className="vg-content-chip vg-chip-planned">PLANNED</span></div><div className="vg-card-body"><strong>{item.title}</strong><p>{item.description}</p><span className="vg-card-future">Additional model concepts and rules required</span></div></article>)}</div></div>}
          {!hasContent && <div className="vg-empty-state"><strong>No matching scenes</strong><p>{filter === "uploaded" ? "Your uploaded videos appear here automatically after a successful upload." : "Try a different search or filter."}</p></div>}
        </>}
      </section>
      <footer className="vg-gallery-footer"><span>VISIONGUARD AI · Meta Hackathon Research MVP</span><span>Only authorized footage · Analysis is not a certified safety verdict</span></footer>
    </div>
  </main>;
}
