import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAnalyzeRepo, useRecentAnalyses, useRepos } from "../api/hooks";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { scoreTone, type Tone } from "../lib/palette";
import type { AnalysisSummary } from "../api/types";

const TONE_CLASS: Record<Tone, string> = {
  ok: "text-ok",
  info: "text-info",
  warn: "text-warn",
  danger: "text-danger",
};

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
    <li className="px-card-hover flex items-center gap-4 p-3">
      <button
        onClick={() => navigate(`/analyses/${analysis.id}`)}
        className="min-w-0 flex-1 text-left"
        title="Open analysis"
      >
        <p className="truncate font-ui text-[11px] text-ink">
          {analysis.repo_owner}/{analysis.repo_name}
        </p>
        <p className="mt-0.5 truncate font-mono text-[10px] text-faint">
          {analysis.commit_sha ? analysis.commit_sha.slice(0, 7) : "not cloned"} ·{" "}
          {analysis.finding_count} findings
          {analysis.loc != null && ` · ${analysis.loc.toLocaleString()} loc`} ·{" "}
          {timeAgo(analysis.created_at)}
        </p>
      </button>
      <div className="flex shrink-0 items-center gap-3">
        {analysis.overall != null && (
          <span className="px-well px-3 py-1" title="Overall repository health score">
            <span
              className={`font-ui text-[28px] tabular-nums ${TONE_CLASS[scoreTone(analysis.overall)]}`}
            >
              {analysis.overall}
            </span>
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
          className="px-btn px-btn--ghost"
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
          <EmptyState
            title="No analyses yet"
            detail="Point Retract at a GitHub repository and it will score it."
            action={{ label: "Add a repository", to: "/repos" }}
          />
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
          <EmptyState
            title="Could not load your analyses"
            detail="Is the API running?"
            icon="cross"
          />
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
          <div className="px-panel flex flex-wrap items-center justify-between gap-3 p-5">
            <p className="text-sm text-muted">
              <span className="font-ui text-[28px] text-ink tabular-nums">{repos.data.length}</span>{" "}
              repositor{repos.data.length === 1 ? "y" : "ies"} tracked
            </p>
            <Link to="/repos" className="px-btn px-btn--ghost">
              Manage repositories →
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
