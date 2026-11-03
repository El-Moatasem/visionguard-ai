export type VideoItem = {
  id: string;
  name: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  status: "stored";
  library_source?: "upload" | "demo";
  scenario_id?: string | null;
  suggested_concepts?: string[];
  analysis_source_video_id?: string;
  analysis_source_sha256?: string;
  analysis_start_seconds?: number;
  analysis_duration_seconds?: number;
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

export async function uploadVideo(file: File, scenarioId?: string | null): Promise<VideoItem> {
  const form = new FormData();
  form.append("file", file, file.name);
  return readResponse<VideoItem>(await fetch(`${API}/videos${scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : ""}`, { method: "POST", body: form }));
}
export async function prepareVideoForSam(videoId: string, startSeconds: number, durationSeconds: number): Promise<VideoItem> {
  return readResponse<VideoItem>(await fetch(`${API}/videos/${encodeURIComponent(videoId)}/prepare-for-sam`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({start_seconds: startSeconds, duration_seconds: durationSeconds}),
  }));
}

export type DeleteVideosResult = {
  deleted_videos: number;
  deleted_jobs: number;
  deleted_evidence: number;
  message: string;
};
export async function deleteVideo(videoId: string): Promise<DeleteVideosResult> {
  return readResponse<DeleteVideosResult>(await fetch(`${API}/videos/${encodeURIComponent(videoId)}`, {method: "DELETE"}));
}
export async function deleteAllVideos(): Promise<DeleteVideosResult> {
  return readResponse<DeleteVideosResult>(await fetch(`${API}/videos/delete-all`, {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({confirm: "DELETE ALL VIDEOS"}),
  }));
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


export type DemoScenario = {
  id: string;
  title: string;
  industry: string;
  description: string;
  concepts: string[];
  rule_type: RuleType;
  rule_concept: string | null;
  duration: number;
  zone: [number, number, number, number];
  provenance: "real_video_required" | "synthetic_replay_available";
  replay_id?: string;
  expected: string;
};
export async function fetchDemoScenarios(): Promise<DemoScenario[]> {
  const data = await readResponse<{items: DemoScenario[]}>(await fetch(`${API}/demo/scenarios`, {cache: "no-store"}));
  return data.items;
}
export const APPROVED_CONCEPTS = ["person", "forklift", "car", "shopping_cart", "cardboard_box", "excavator"] as const;

export type TrackingJob = {
  id: string;
  video_id: string;
  status: "queued" | "running" | "cancelling" | "cancelled" | "completed" | "failed" | "interrupted";
  cancel_requested?: boolean;
  cancelled_at?: string;
  model: string;
  concepts: string[];
  phase?: string;
  revision?: number;
  failure_type?: string;
  concepts_completed?: string[];
  current_concept?: string | null;
  upload_seconds?: number;
  last_concept_inference_seconds?: number;
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
  partial?: boolean;
  concepts_completed?: string[];
  box_count: number;
  track_count: number;
  gap_count: number;
  time_alignment: "approximate" | "unavailable";
  media_probe: { fps?: number | null; width?: number; height?: number; duration_seconds?: number };
  media_metadata?: { fps?: number | null; width?: number; height?: number };
  tracks: TrackingTrack[];
  boxes: TrackingBox[];
  gaps: { track_id: string; after_frame: number; before_frame: number; missing_frames: number; identity_continuity: string }[];
};
export async function fetchTrackingPreview(jobId: string): Promise<TrackingReport | null> {
  const response = await fetch(`${API}/tracking-jobs/${encodeURIComponent(jobId)}/preview`, { cache: "no-store" });
  if (response.status === 404) return null; // No streamed boxes yet, not an error.
  return readResponse<TrackingReport>(response);
}

export async function startTracking(videoId: string, concepts?: string[]): Promise<TrackingJob> {
  return readResponse<TrackingJob>(await fetch(`${API}/videos/${encodeURIComponent(videoId)}/tracking-jobs`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({concepts: concepts ?? ["person", "forklift"]})
  }));
}
export async function fetchActiveTrackingJobs(): Promise<TrackingJob[]> {
  const result = await readResponse<{items: TrackingJob[]}>(
    await fetch(`${API}/tracking-jobs/active`, {cache: "no-store"}));
  return result.items;
}
export async function cancelTrackingJob(jobId: string): Promise<TrackingJob> {
  return readResponse<TrackingJob>(await fetch(`${API}/tracking-jobs/${encodeURIComponent(jobId)}/cancel`, {method: "POST"}));
}
export async function cancelAllTrackingJobs(): Promise<{items: TrackingJob[]; count: number}> {
  return readResponse<{items: TrackingJob[]; count: number}>(
    await fetch(`${API}/tracking-jobs/cancel-all`, {method: "POST"}));
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

export type RuleType = "person_in_zone" | "person_and_forklift_in_zone" | "object_in_zone" | "object_zone_entry";
export type SafetyZone = {name: string; x_min: number; y_min: number; x_max: number; y_max: number};
export type RuleSpec = {name: string; rule_type: RuleType; min_duration_seconds: number; max_observation_gap_frames: number; zone: SafetyZone; excluded_operator_track_ids?: string[]; concept?: string | null};
export type RuleDraft = {name: string; rule_type: RuleType | "unsupported"; min_duration_seconds: number; rationale: string};
export type SafetyEvent = {
  event_id: string; status: "potential_hazard" | "needs_review"; start_frame: number; end_frame: number;
  observed_frames: number; start_seconds_approx: number | null; end_seconds_approx: number | null;
  observed_span_seconds_approx: number; observed_coverage_ratio: number;
  contains_missing_observations: boolean; identity_continuity: string;
  actor_fragments: string[]; actor_tracks: string[]; reason: string;
};
export type SafetyReviewItem = Partial<SafetyEvent> & {
  status: "needs_review"; start_frame: number; end_frame: number;
  start_seconds_approx: number | null; end_seconds_approx: number | null;
  reason: string; track_id?: string;
};
export type SafetyEvaluation = {
  operator_candidate_count?: number;
  operator_candidate_track_ids?: string[];
  operator_excluded_count?: number;
  operator_excluded_track_ids?: string[];
  tracking_job_id: string; rule: RuleSpec;
  outcome: "potential_hazard" | "needs_review" | "no_rule_match_observed";
  event_count: number; events: SafetyEvent[]; review_count: number;
  review_items: SafetyReviewItem[]; uncertainty_count: number;
  has_unresolved_review_items: boolean;
  uncertainties: SafetyReviewItem[];
  time_alignment: "approximate" | "unavailable"; method: string; disclaimer: string;
};
export async function interpretSafetyRule(description: string): Promise<RuleDraft> {
  const result = await readResponse<{draft: RuleDraft}>(await fetch(`${API}/rules/interpret`, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({description}),
  }));
  return result.draft;
}
export async function evaluateSafetyRule(jobId: string, rule: RuleSpec): Promise<SafetyEvaluation> {
  return readResponse<SafetyEvaluation>(await fetch(`${API}/tracking-jobs/${encodeURIComponent(jobId)}/evaluate`, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({rule}),
  }));
}

// Feature 5: persistent local evidence reports (not authenticated for public deployment).
export type EvidenceReview = {id: string; item_id: string; decision: "confirmed" | "rejected" | "unresolved"; reviewer: string; note: string; recorded_at: string};
export type EvidenceItem = {item_id: string; kind: "observed_event" | "needs_review"; observation: SafetyEvent | SafetyReviewItem};
export type EvidenceReport = {
  id: string; created_at: string; origin: "live_tracking_job";
  source: {video_name: string; video_sha256: string; tracking_job_id: string; tracking_sha256: string; model: string; time_alignment: string};
  rule: RuleSpec; evaluation: SafetyEvaluation; items: EvidenceItem[]; reviews: EvidenceReview[];
  observations: {item_id: string; sampled_boxes: TrackingBox[]; sampling_note: string}[];
  disclaimer: string;
};
export type EvidenceSummary = {id: string; created_at: string; rule_name: string; event_count: number; review_count: number};
export async function createEvidenceReport(trackingJobId: string, rule: RuleSpec): Promise<EvidenceReport> {
  return readResponse<EvidenceReport>(await fetch(`${API}/evidence-reports`, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tracking_job_id: trackingJobId, rule}),
  }));
}
export async function fetchEvidenceReport(id: string): Promise<EvidenceReport> {
  return readResponse<EvidenceReport>(await fetch(`${API}/evidence-reports/${encodeURIComponent(id)}`, {cache: "no-store"}));
}
export async function listEvidenceReports(jobId: string): Promise<EvidenceSummary[]> {
  const result = await readResponse<{items: EvidenceSummary[]}>(await fetch(`${API}/evidence-reports?tracking_job_id=${encodeURIComponent(jobId)}`, {cache: "no-store"}));
  return result.items;
}
export async function reviewEvidence(reportId: string, itemId: string, decision: EvidenceReview["decision"], note: string): Promise<EvidenceReview> {
  return readResponse<EvidenceReview>(await fetch(`${API}/evidence-reports/${encodeURIComponent(reportId)}/reviews`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({item_id: itemId, decision, note, reviewer: "Demo reviewer"}),
  }));
}
export function evidenceExportUrl(id: string, format: "json" | "html"): string {
  return `${API}/evidence-reports/${encodeURIComponent(id)}/export.${format}`;
}

// Read-only synthetic replay: not video footage, not actual SAM output.
export type ReplaySummary = {id: string; title: string; description: string; provenance: "synthetic_fixture"};
export type ReplayScenario = ReplaySummary & {
  live_inference: false; default_rule: RuleSpec; tracking_report: TrackingReport;
  video_asset_included: false; visualization: string; rights: string;
};
export async function fetchReplayScenarios(): Promise<ReplaySummary[]> {
  const result = await readResponse<{items: ReplaySummary[]}>(await fetch(`${API}/replay/scenarios`));
  return result.items;
}
export async function fetchReplayScenario(id: string): Promise<ReplayScenario> {
  return readResponse<ReplayScenario>(await fetch(`${API}/replay/scenarios/${encodeURIComponent(id)}`));
}
export async function evaluateReplay(id: string, rule: RuleSpec): Promise<SafetyEvaluation> {
  return readResponse<SafetyEvaluation>(await fetch(`${API}/replay/scenarios/${encodeURIComponent(id)}/evaluate`, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({rule}),
  }));
}
