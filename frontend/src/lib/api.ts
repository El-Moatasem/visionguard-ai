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
