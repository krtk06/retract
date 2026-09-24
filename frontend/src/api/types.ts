export interface User {
  id: number;
  login: string;
  github_id: number | null;
}

export interface Repository {
  id: number;
  owner: string;
  name: string;
  url: string;
  default_branch: string;
  created_at: string;
  latest_analysis_id: number | null;
  latest_analysis_status: string | null;
}

export type AnalysisStatus = "pending" | "running" | "done" | "failed";

export interface Analysis {
  id: number;
  repository_id: number;
  commit_sha: string | null;
  status: AnalysisStatus;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  created_at: string;
  finding_count: number;
}

export interface Finding {
  id: number;
  analysis_id: number;
  agent: string;
  category: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  file_path: string | null;
  line_start: number | null;
  line_end: number | null;
  evidence_json: Record<string, unknown> | null;
  verifier: string;
  confidence: number;
  status: "verified" | "hypothesis" | "dismissed";
  created_at: string;
}

export interface AnalysisEvent {
  type: string;
  payload: Record<string, unknown>;
  ts: number;
}
