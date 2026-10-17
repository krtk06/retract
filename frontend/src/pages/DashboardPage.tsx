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

function scoreTone(score: number): string {
  if (score >= 80) return "text-ok";
  if (score >= 60) return "text-info";
  if (score >= 50) return "text-warn";
  return "text-danger";
}

function Row({ analysis, onReanalyze, busy, active }: AnalysisRowProps) {
  const navigate = useNavigate();
  return (
    <li className="px-card px-card-hover flex items-center gap-4 px-4 py-3.5">
      <button
        onClick={() => navigate(`/analyses/${analysis.id}`)}
        className="min-w-0 flex-1 text-left"
        title="Open analysis"
      >
        <p className="truncate text-sm font-semibold text-ink">
          {analysis.repo_owner}/{analysis.repo_name}
        </p>
        <p className="mt-0.5 truncate text-xs text-faint">
          {analysis.commit_sha ? analysis.commit_sha.slice(0, 7) : "not cloned"} ·{" "}
          {analysis.finding_count} findings
          {analysis.loc != null && ` · ${analysis.loc.toLocaleString()} loc`} ·{" "}
          {timeAgo(analysis.created_at)}
        </p>
      </button>
      <div className="flex shrink-0 items-center gap-3">
        {analysis.overall != null && (
          <span
            className={`text-2xl font-extrabold tabular-nums tracking-tight ${scoreTone(analysis.overall)}`}
            title="Overall repository health score"
          >
            {analysis.overall}
          </span>
        )}
        <button
          onClick={() => navigate(`/analyses/${analysis.id}`)}
          className="transition-transform duration-300 ease-step hover:-translate-y-0.5"
          title="View analysis"
        >
          <StatusPill status={analysis.status} />
        </button>
        <button
          onClick={() => onReanalyze(analysis.repository_id)}
          disabled={busy || active}
          className="px-btn px-btn--ghost px-3.5 py-1.5 text-xs"
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
    <div className="space-y-12">
      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="px-eyebrow">Activity</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">Recent analyses</h1>
          </div>
          <span className="text-xs text-faint">newest first</span>
        </div>

        {recent.isLoading && <p className="text-sm text-muted">Loading…</p>}

        {recent.data?.length === 0 && (
          <div className="px-panel flex flex-col items-center gap-2 px-6 py-14 text-center">
            <span
              aria-hidden="true"
              className="mb-1 h-10 w-10"
              style={{
                background: "radial-gradient(circle at 35% 30%, var(--accent-strong), var(--accent))",
                boxShadow: "0 0 28px var(--accent-glow)",
              }}
            />
            <p className="text-sm font-semibold text-ink">No analyses yet</p>
            <p className="max-w-sm text-sm text-muted text-pretty">
              Add a repository on the{" "}
              <Link to="/repos" className="px-link">
                repositories page
              </Link>{" "}
              to get a health score.
            </p>
          </div>
        )}

        {recent.data && recent.data.length > 0 && (
          <ul className="space-y-2.5">
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
          <p className="border border-danger/25 bg-danger-soft px-4 py-2.5 text-sm text-danger">
            Could not load your analyses. Is the API running?
          </p>
        )}
      </section>

      <section>
        <div className="mb-4">
          <p className="px-eyebrow">Inventory</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">Your repositories</h2>
        </div>
        {repos.data?.length === 0 && (
          <p className="text-sm text-faint">
            No repositories yet —{" "}
            <Link to="/repos" className="px-link">
              add one
            </Link>
            .
          </p>
        )}
        {repos.data && repos.data.length > 0 && (
          <div className="px-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <p className="text-sm text-muted">
              <span className="text-lg font-bold text-ink tabular-nums">{repos.data.length}</span>{" "}
              repositor{repos.data.length === 1 ? "y" : "ies"} tracked
            </p>
            <Link to="/repos" className="px-btn px-btn--ghost px-3.5 py-1.5 text-xs">
              Manage repositories →
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
