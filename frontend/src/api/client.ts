import type {
  Analysis,
  ApprovalQueue,
  ApprovalResult,
  CalibrationStat,
  Finding,
  GraphNeighborhood,
  GraphSummary,
  Repository,
  SearchResponse,
  SymbolRef,
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
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  listRepos: () => request<Repository[]>("/api/repos"),
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
  search: (id: number, q: string) =>
    request<SearchResponse>(`/api/analyses/${id}/search?q=${encodeURIComponent(q)}`),
  approvalQueue: (id: number) => request<ApprovalQueue>(`/api/analyses/${id}/approvals/queue`),
  decide: (id: number, findingId: number, decision: "approve" | "dismiss", note?: string) =>
    request<ApprovalResult>(`/api/analyses/${id}/approvals`, {
      method: "POST",
      body: JSON.stringify({ finding_id: findingId, decision, note }),
    }),
  calibrationStats: () => request<CalibrationStat[]>("/api/calibration/stats"),
};
