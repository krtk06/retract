import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAnalyzeRepo, useRecentAnalyses, useRepos } from "../api/hooks";
import { StatusPill } from "../components/StatusPill";
import type { AnalysisSummary } from "../api/types";
function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function Row({ analysis, onReanalyze, busy, active }: AnalysisRowProps) {
  const navigate = useNavigate();
  return (
    <li className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3">
      <button
        onClick={() => navigate(`/analyses/${analysis.id}`)}
        className="min-w-0 flex-1 text-left hover:opacity-80"
        title="Open analysis"
      >
        <p className="truncate text-sm font-medium">
          {analysis.repo_owner}/{analysis.repo_name}
        </p>
        <p className="text-xs text-zinc-500">
          {analysis.commit_sha ? analysis.commit_sha.slice(0, 7) : "not cloned"} ·{" "}
          {analysis.finding_count} findings
          {analysis.loc != null && ` · ${analysis.loc.toLocaleString()} loc`} ·{" "}
          {timeAgo(analysis.created_at)}
        </p>
      </button>
      <div className="ml-4 flex items-center gap-3">
        {analysis.overall != null && (
          <span
            className="text-lg font-semibold tabular-nums"
            title="Overall repository health score"
          >
            {analysis.overall}
          </span>
        )}
        <button
          onClick={() => navigate(`/analyses/${analysis.id}`)}
          className="hover:opacity-80"
          title="View analysis"
        >
          <StatusPill status={analysis.status} />
        </button>
        <button
          onClick={() => onReanalyze(analysis.repository_id)}
          disabled={busy || active}
          className="rounded-md border border-zinc-700 px-3 py-1 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          title={active ? "An analysis is already running" : "Re-analyze latest commit"}
        >
          Re-analyze
        </button>
      </div>
    </li>
  );
}

interface AnalysisRowProps {
  analysis: AnalysisSummary;
  onReanalyze: (repoId: number) => void;
  busy: boolean;
  active: boolean;
}

export function DashboardPage() {
  const recent = useRecentAnalyses(true);
  const repos = useRepos(true);
  const analyzeRepo = useAnalyzeRepo();

  async function reanalyze(repoId: number) {
    try {
      await analyzeRepo.mutateAsync(repoId);
    } catch (err) {
      // 409 while one is still running is normal busy-state, not an app failure.
      if (!(err instanceof ApiError && err.status === 409)) {
        throw err;
      }
    }
  }

  const activeRepoIds = useMemo(() => {
    const active = new Set<number>();
    for (const row of recent.data ?? []) {
      if (row.status === "pending" || row.status === "running") {
        active.add(row.repository_id);
      }
    }
    return active;
  }, [recent.data]);

  return (
    <div className="space-y-10">
      <section>
        <div className="mb-4 flex items-baseline justify-between">
          <h1 className="text-lg font-semibold">Recent analyses</h1>
          <span className="text-xs text-zinc-500">newest first</span>
        </div>
        {recent.isLoading && <p className="text-sm text-zinc-400">Loading…</p>}
        {recent.data?.length === 0 && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-8 text-center">
            <p className="text-sm text-zinc-400">No analyses yet.</p>
            <p className="mt-1 text-sm text-zinc-500">
              Add a repository on the{" "}
              <Link to="/repos" className="text-emerald-400 hover:underline">
                repositories page
              </Link>{" "}
              to get a health score.
            </p>
          </div>
        )}
        {recent.data && recent.data.length > 0 && (
          <ul className="space-y-2">
            {recent.data.map((analysis) => (
              <Row
                key={analysis.id}
                analysis={analysis}
                onReanalyze={reanalyze}
                busy={analyzeRepo.isPending}
                active={activeRepoIds.has(analysis.repository_id)}
              />
            ))}
          </ul>
        )}
        {recent.isError && (
          <p className="rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
            Could not load your analyses. Is the API running?
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Your repositories</h2>
        {repos.data?.length === 0 && (
          <p className="text-sm text-zinc-500">
            No repositories yet —{" "}
            <Link to="/repos" className="text-emerald-400 hover:underline">
              add one
            </Link>
            .
          </p>
        )}
        {repos.data && repos.data.length > 0 && (
          <p className="text-sm text-zinc-500">
            {repos.data.length} repositor{repos.data.length === 1 ? "y" : "ies"} · manage them on
            the{" "}
            <Link to="/repos" className="text-emerald-400 hover:underline">
              repositories page
            </Link>
          </p>
        )}
      </section>
    </div>
  );
}
