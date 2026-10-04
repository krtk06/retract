import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError, request } from "./client";
import type { Score } from "./types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 401) return false;
      return failureCount < 2;
    },
    staleTime: 60_000,
  });
}

export function useRepos(enabled: boolean) {
  return useQuery({ queryKey: ["repos"], queryFn: api.listRepos, enabled });
}

export function useCreateRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createRepo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["repos"] }),
  });
}

export function useAnalyzeRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.analyzeRepo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["repos"] }),
  });
}

export function useScore(id: number, enabled = true) {
  return useQuery({
    queryKey: ["score", id],
    queryFn: () => request<Score>(`/api/analyses/${id}/score`),
    // Only once the analysis is finished. Fetching mid-run asks the backend to score
    // an incomplete analysis, which counts only the findings reported so far — none,
    // early on — and yields an overall of 100 with every pillar unmeasured. That value
    // was cached under this key and, with nothing invalidating it on completion, kept
    // being displayed beside a finished analysis that had actually scored 88.
    enabled: enabled && id > 0,
    retry: false,
  });
}

export function useAnalysis(id: number) {
  return useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api.getAnalysis(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 2000 : false;
    },
  });
}

export function useFindings(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ["findings", id],
    queryFn: () => api.getFindings(id),
    enabled,
  });
}

export function useGraphSummary(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ["graph-summary", id],
    queryFn: () => api.graphSummary(id),
    enabled,
  });
}

export function useGraphSymbols(id: number, q: string, enabled: boolean) {
  return useQuery({
    queryKey: ["graph-symbols", id, q],
    queryFn: () => api.graphSymbols(id, q),
    enabled,
  });
}

export function useNeighborhood(id: number, symbol: string | null) {
  return useQuery({
    queryKey: ["neighborhood", id, symbol],
    queryFn: () => api.graphNeighborhood(id, symbol as string),
    enabled: symbol !== null,
  });
}


export function useApprovalQueue(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ["approvals", id],
    queryFn: () => api.approvalQueue(id),
    enabled,
  });
}

export function useDecide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      analysisId,
      findingId,
      decision,
      note,
    }: {
      analysisId: number;
      findingId: number;
      decision: "approve" | "dismiss";
      note?: string;
    }) => api.decide(analysisId, findingId, decision, note),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ["approvals", variables.analysisId] });
      queryClient.invalidateQueries({ queryKey: ["analysis", variables.analysisId] });
      queryClient.invalidateQueries({ queryKey: ["findings", variables.analysisId] });
      queryClient.invalidateQueries({ queryKey: ["calibration"] });
    },
  });
}

export function useCalibrationStats(enabled: boolean) {
  return useQuery({
    queryKey: ["calibration"],
    queryFn: api.calibrationStats,
    enabled,
  });
}

export function useHistory(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ["history", id],
    queryFn: () => api.history(id),
    enabled,
  });
}

export function useTrustSummary(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ["trust-summary", id],
    queryFn: () => api.trustSummary(id),
    enabled,
  });
}

export function useCompare(left: number | null, right: number | null) {
  return useQuery({
    queryKey: ["compare", left, right],
    queryFn: () => api.compare(left as number, right as number),
    enabled: left != null && right != null && left !== right,
  });
}

export function useSnippet(id: number, path: string | null, lineStart: number | null) {
  return useQuery({
    queryKey: ["snippet", id, path, lineStart],
    queryFn: () => api.snippet(id, path as string, lineStart as number),
    enabled: path != null && lineStart != null,
  });
}
