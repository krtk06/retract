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

export function useScore(id: number) {
  return useQuery({
    queryKey: ["score", id],
    queryFn: () => request<Score>(`/api/analyses/${id}/score`),
    enabled: id > 0,
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
