import type {
  Analysis,
  AnalysisHistoryItem,
  AnalysisSummary,
  ApprovalQueue,
  ApprovalResult,
  CalibrationStat,
  CompareResult,
  Finding,
  GraphNeighborhood,
  GraphSummary,
  RemediationPlan,
  Repository,
  SnippetResponse,
  SymbolRef,
  TrustSummary,
  User,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<User>("/api/auth/me"),
  devLogin: (login: string) =>
    request<{ ok: boolean }>(`/api/auth/dev/login?login=${encodeURIComponent(login)}`),
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  listRepos: () => request<Repository[]>("/api/repos"),
  listAnalyses: () => request<AnalysisSummary[]>("/api/analyses"),
  createRepo: (url: string) =>
    request<Repository>("/api/repos", { method: "POST", body: JSON.stringify({ url }) }),
  analyzeRepo: (repoId: number) =>
    request<Analysis>(`/api/repos/${repoId}/analyze`, { method: "POST" }),
  getAnalysis: (id: number) => request<Analysis>(`/api/analyses/${id}`),
  getFindings: (id: number) => request<Finding[]>(`/api/analyses/${id}/findings`),
  graphSummary: (id: number) => request<GraphSummary>(`/api/analyses/${id}/graph/summary`),
  graphSymbols: (id: number, q: string) =>
    request<SymbolRef[]>(
      `/api/analyses/${id}/graph/symbols?limit=300${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    ),
  graphNeighborhood: (id: number, symbol: string) =>
    request<GraphNeighborhood>(
      `/api/analyses/${id}/graph/neighborhood?symbol=${encodeURIComponent(symbol)}`,
    ),
  history: (id: number) => request<AnalysisHistoryItem[]>(`/api/analyses/${id}/history`),
  trustSummary: (id: number) => request<TrustSummary>(`/api/analyses/${id}/trust-summary`),
  remediation: (id: number) => request<RemediationPlan>(`/api/analyses/${id}/remediation`),
  compare: (left: number, right: number) =>
    request<CompareResult>(`/api/analyses/compare?left=${left}&right=${right}`),
  snippet: (id: number, path: string, lineStart: number) =>
    request<SnippetResponse>(
      `/api/analyses/${id}/snippet?path=${encodeURIComponent(path)}&line_start=${lineStart}&context=6`,
    ),
  approvalQueue: (id: number) => request<ApprovalQueue>(`/api/analyses/${id}/approvals/queue`),
  decide: (id: number, findingId: number, decision: "approve" | "dismiss", note?: string) =>
    request<ApprovalResult>(`/api/analyses/${id}/approvals`, {
      method: "POST",
      body: JSON.stringify({ finding_id: findingId, decision, note }),
    }),
  calibrationStats: () => request<CalibrationStat[]>("/api/calibration/stats"),
};
