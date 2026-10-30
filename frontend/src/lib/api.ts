export type VideoItem = {
  id: string;
  name: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  status: "stored";
  sam_compatible_container: boolean;
  note: string;
  file_url: string;
};

const API = "/api/backend";

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch { /* return the HTTP status if the body isn't JSON */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function uploadVideo(file: File): Promise<VideoItem> {
  const form = new FormData();
  form.append("file", file, file.name);
  return readResponse<VideoItem>(await fetch(`${API}/videos`, { method: "POST", body: form }));
}
export async function fetchVideos(): Promise<VideoItem[]> {
  const data = await readResponse<{ items: VideoItem[] }>(
    await fetch(`${API}/videos`, { cache: "no-store" })
  );
  return data.items;
}
export function playbackUrl(item: VideoItem): string {
  return `${API}/videos/${encodeURIComponent(item.id)}/file`;
}


export type TrackingJob = {
  id: string;
  video_id: string;
  status: "queued" | "running" | "completed" | "failed" | "interrupted";
  model: string;
  concepts: string[];
  created_at: string;
  message: string;
  result_url: string;
  track_count?: number;
  gap_count?: number;
};
export type TrackingBox = {
  track_id: string;
  fragment_id: string;
  concept: string;
  frame: number;
  box: { left: number; top: number; right: number; bottom: number };
};
export type TrackingTrack = {
  track_id: string;
  concept: string;
  observed_frames: number;
  fragment_count: number;
  has_uncertain_identity_continuity: boolean;
  fragments: { fragment_id: string; start_frame: number; end_frame: number }[];
};
export type TrackingReport = {
  schema_version: number;
  box_count: number;
  track_count: number;
  gap_count: number;
  time_alignment: "approximate" | "unavailable";
  media_probe: { fps?: number | null; width?: number; height?: number; duration_seconds?: number };
  tracks: TrackingTrack[];
  boxes: TrackingBox[];
  gaps: { track_id: string; after_frame: number; before_frame: number; missing_frames: number; identity_continuity: string }[];
};
export async function startTracking(videoId: string): Promise<TrackingJob> {
  return readResponse<TrackingJob>(await fetch(`${API}/videos/${encodeURIComponent(videoId)}/tracking-jobs`, {method: "POST"}));
}
export async function fetchTrackingJobs(videoId: string): Promise<TrackingJob[]> {
  const data = await readResponse<{items: TrackingJob[]}>(await fetch(`${API}/videos/${encodeURIComponent(videoId)}/tracking-jobs`, {cache: "no-store"}));
  return data.items;
}
export async function fetchTrackingJob(jobId: string): Promise<TrackingJob> {
  return readResponse<TrackingJob>(await fetch(`${API}/tracking-jobs/${encodeURIComponent(jobId)}`, {cache: "no-store"}));
}
export async function fetchTrackingResult(jobId: string): Promise<TrackingReport> {
  return readResponse<TrackingReport>(await fetch(`${API}/tracking-jobs/${encodeURIComponent(jobId)}/result`, {cache: "no-store"}));
}
