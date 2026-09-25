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

export interface ScorePillar {
  score: number;
  findings: number;
  verified: number;
  hypotheses: number;
  dismissed?: number;
  weighted_penalty?: number;
}

export interface Score {
  version: number;
  overall: number;
  loc: number | null;
  kloc: number;
  pillars: Record<string, ScorePillar>;
  previous_overall?: number | null;
  delta?: number | null;
}

export interface AnalysisHistoryItem {
  id: number;
  repository_id: number;
  commit_sha: string | null;
  status: AnalysisStatus;
  created_at: string;
  finished_at: string | null;
  loc: number | null;
  published: boolean;
  finding_count: number;
  overall: number | null;
}

export interface AgentTrust {
  agent: string;
  findings: number;
  verified: number;
  hypotheses: number;
  dismissed: number;
  avg_confidence: number | null;
}

export interface TrustSummary {
  analysis_id: number;
  totals: {
    findings: number;
    verified: number;
    hypotheses: number;
    dismissed: number;
  };
  verification_coverage: number | null;
  avg_confidence: number | null;
  agents: AgentTrust[];
  acceptance_rates: CalibrationStat[];
}

export interface CompareResult {
  left: { id: number; commit_sha: string | null; created_at: string | null; overall: number | null; loc: number | null };
  right: { id: number; commit_sha: string | null; created_at: string | null; overall: number | null; loc: number | null };
  overall_delta: number | null;
  pillars: {
    pillar: string;
    left_score: number;
    right_score: number;
    delta: number;
    left_findings: number;
    right_findings: number;
  }[];
}

export interface AgentCostRun {
  agent: string;
  provider?: string;
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  findings?: number;
  dropped?: number;
  repaired?: number;
  dismissed?: number;
  error?: string | null;
}

export interface CostLedger {
  agents?: AgentCostRun[];
  tokens_in?: number;
  tokens_out?: number;
}

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
  loc: number | null;
  score_json: Score | null;
  cost_json: CostLedger | null;
  published: boolean;
  pending_approvals: number;
  repository: Repository | null;
}

export interface ApprovalQueue {
  analysis_id: number;
  published: boolean;
  pending_count: number;
  approved_count: number;
  dismissed_count: number;
  pending: Finding[];
}

export interface ApprovalResult {
  finding_id: number;
  decision: string;
  finding_status: string;
  confidence: number;
  note: string | null;
  pending_count: number;
  published: boolean;
}

export interface SnippetResponse {
  path: string;
  line_start: number;
  from_line: number;
  to_line: number;
  lines: string[];
}

export interface CalibrationStat {
  agent: string;
  category: string;
  shown: number;
  accepted: number;
  dismissed: number;
  acceptance_rate: number | null;
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

export interface SymbolRef {
  id: number;
  name: string;
  kind: string;
  file_path: string;
  line_start: number;
}

export interface GraphSummary {
  symbols: Record<string, number>;
  edges: Record<string, number>;
  top_importing_modules: { module: string; imports: number }[];
}

export interface GraphNode {
  id: number;
  name: string;
  kind: string;
  file_path: string;
  line_start: number;
  line_end: number;
}

export interface GraphLink {
  source: string;
  target: string;
  kind: string;
}

export interface GraphNeighborhood {
  root: GraphNode | null;
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface SearchResult {
  chunk_id: number | null;
  symbol_name: string;
  kind: string;
  file_path: string;
  line_start: number;
  line_end: number;
  score: number | null;
  snippet: string;
}

export interface SearchResponse {
  mode: "graph" | "semantic";
  query: string;
  results: SearchResult[];
}
