export interface User {
  id: number;
  login: string;
  github_id: number | null;
  email?: string | null;
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
  // null when no LOC was measured; the score then comes from raw weighted
  // finding-points rather than density.
  kloc: number | null;
  basis?: "density" | "count" | null;
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

export interface AnalysisSummary {
  id: number;
  repository_id: number;
  repo_owner: string;
  repo_name: string;
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

export type Effort = "low" | "medium" | "high";

export interface RemediationBrief {
  action: string;
  effort: Effort;
  source: "catalog" | "llm:eve";
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
  // Derived server-side, so the table can show the fix inline without a second
  // request. Absent on older payloads, hence the guard at the call site.
  remediation?: RemediationBrief;
}

export interface RemediationTarget {
  finding_id: number;
  title: string;
  severity: Finding["severity"];
  status: Finding["status"];
  file_path: string | null;
  line_start: number | null;
}

export interface RemediationItem {
  key: string;
  pillar: string;
  action: string;
  severity: Finding["severity"];
  effort: Effort;
  source: "catalog" | "llm:eve";
  steps: string[];
  verify: string;
  references: string[];
  findings: RemediationTarget[];
  finding_count: number;
  // What this item is worth in its own pillar, against today's score. Not a share
  // of `recoverable_points`: the overall is capped at worst_pillar + 15, so
  // clearing a non-worst pillar barely moves the headline.
  pillar_points: number;
  // Additive and exact: the scoring curve's own input.
  weighted_penalty_removed: number;
  payoff: number;
}

export interface RemediationPlan {
  analysis_id: number;
  loc: number | null;
  current_overall: number | null;
  // null when nothing was found, so "everything fixed" has nothing to mean.
  projected_overall: number | null;
  recoverable_points: number | null;
  work_items: RemediationItem[];
  findings_considered: number;
  unverified_items: number;
  truncated_findings: number;
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


