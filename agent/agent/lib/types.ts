/** Shared response shapes from the AI Engineering Intelligence API. */

export type RepoOut = {
  id: number;
  owner: string;
  name: string;
  url: string;
  default_branch: string;
  latest_analysis_id: number | null;
  latest_analysis_status: string | null;
};

export type AnalysisOut = {
  id: number;
  repository_id: number;
  commit_sha: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  created_at: string;
  finding_count: number;
  loc: number | null;
  score_json: Record<string, unknown> | null;
  published: boolean;
  pending_approvals: number;
  repository: RepoOut | null;
};

export type SymbolOut = {
  id: number;
  name: string;
  kind: string;
  file_path: string;
  line_start: number;
  line_end?: number;
  signature?: string | null;
};

export type FindingOut = {
  id: number;
  analysis_id: number;
  agent: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  file_path: string | null;
  line_start: number | null;
  line_end: number | null;
  evidence_json: Record<string, unknown> | null;
  verifier: string;
  confidence: number;
  status: string;
  created_at: string;
};

export type ScoreOut = {
  version: number;
  overall: number;
  loc: number | null;
  kloc: number;
  pillars: Record<string, Record<string, unknown>>;
  previous_overall: number | null;
  delta: number | null;
};

export type GraphSummaryOut = {
  analysis_id: number;
  symbols: Record<string, number>;
  edges: Record<string, number>;
  top_modules?: { module: string; symbols: number }[];
};

export type CallerOut = { symbol: SymbolOut; callsite_line: number | null };
export type NeighborhoodOut = {
  root: SymbolOut | null;
  nodes: SymbolOut[];
  edges: { from: number; to: number; kind: string }[];
};
export type TrustSummaryOut = Record<string, unknown>;
export type SnippetOut = Record<string, unknown>;
export type QueueOut = {
  analysis_id: number;
  published: boolean;
  pending_count: number;
  approved_count: number;
  dismissed_count: number;
  pending: FindingOut[];
};
export type AgentFindingsOut = {
  analysis_id: number;
  agent: string;
  inserted: number;
  dropped: number;
  dismissed: number;
  promoted: number;
  checked: number;
  overall: number | null;
  published: boolean;
  reasons: string[];
};
export type ApprovalOut = {
  finding_id: number;
  decision: string;
  finding_status: string;
  confidence: number;
  note: string | null;
  pending_count: number;
  published: boolean;
};
export type RemediationSubmitOut = {
  analysis_id: number;
  agent: string;
  recorded: number;
  rejected: number;
  reasons: string[];
};
