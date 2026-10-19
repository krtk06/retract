import { useMemo } from "react";
import { m } from "motion/react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAnalyzeRepo, useRecentAnalyses, useRepos } from "../api/hooks";
import { CountUp } from "../components/CountUp";
import { EmptyState } from "../components/EmptyState";
import { Icon } from "../components/Icon";
import { Reveal } from "../components/Reveal";
import { Sparkline } from "../components/Sparkline";
import { StatusPill } from "../components/StatusPill";
import { EASE, stagger } from "../lib/motion";
import { scoreTone, TONE_VERDICT_WORD } from "../lib/palette";
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

function Row({ analysis, onReanalyze, busy, active, index }: AnalysisRowProps & { index: number }) {
  const navigate = useNavigate();
  return (
    <m.li
      className="card card--hover lift flex items-center gap-4 p-3.5"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.36, ease: EASE, delay: stagger(index, 0.05, 0.3) }}
    >
      <button
        onClick={() => navigate(`/analyses/${analysis.id}`)}
        className="min-w-0 flex-1 text-left"
        title="Open analysis"
      >
        <p className="truncate text-[13px] font-medium text-ink">
          {analysis.repo_owner}/{analysis.repo_name}
        </p>
        <p className="mt-1 truncate font-mono text-[11px] text-faint">
          {analysis.commit_sha ? analysis.commit_sha.slice(0, 7) : "not cloned"} ·{" "}
          {analysis.finding_count} findings
          {analysis.loc != null && ` · ${analysis.loc.toLocaleString()} loc`} ·{" "}
          {timeAgo(analysis.created_at)}
        </p>
      </button>
      <div className="flex shrink-0 items-center gap-3">
        {analysis.overall != null && (
          <span className="inset px-3 py-1 text-center" title="Overall repository health score">
            <span className="figure block text-2xl text-ink">
              <CountUp value={analysis.overall} duration={0.7} delay={0.2 + stagger(index, 0.05, 0.3)} />
            </span>
            <span className="label block whitespace-nowrap">
              {TONE_VERDICT_WORD[scoreTone(analysis.overall)]}
            </span>
          </span>
        )}
        <button onClick={() => navigate(`/analyses/${analysis.id}`)} title="View analysis">
          <StatusPill status={analysis.status} />
        </button>
        <button
          onClick={() => onReanalyze(analysis.repository_id)}
          disabled={busy || active}
          className="btn btn--ghost press"
          title={active ? "An analysis is already running" : "Re-analyze latest commit"}
        >
          Re-analyze
        </button>
      </div>
    </m.li>
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

  // Chronological, so the line reads left-to-right as time moves forward.
  const trend = useMemo(
    () =>
      (recent.data ?? [])
        .map((row) => row.overall)
        .filter((value): value is number => value != null)
        .reverse(),
    [recent.data],
  );

  return (
    <div className="space-y-10">
      <Reveal>
        <section>
          <div className="mb-4 flex items-end justify-between gap-4">
            <h1 className="text-xl font-semibold tracking-tight text-ink">Recent analyses</h1>
            {trend.length >= 2 && (
              <span className="flex items-center gap-3 text-[11px] text-faint">
                score trend
                {/* The values are the text equivalent; the line beside them is
                    decoration and stays aria-hidden. */}
                <span className="font-mono text-muted tabular-nums">
                  {trend[0]} → {trend[trend.length - 1]}
                </span>
                {trend[0] !== trend[trend.length - 1] && (
                  <Sparkline values={trend} width={96} height={28} />
                )}
              </span>
            )}
          </div>

          {recent.isLoading && <p className="text-[13px] text-muted">Loading…</p>}

          {recent.data?.length === 0 && (
            <EmptyState
              title="No analyses yet"
              detail="Point Retract at a GitHub repository and it will score it."
              action={{ label: "Add a repository", to: "/repos" }}
            />
          )}

          {recent.data && recent.data.length > 0 && (
            <ul className="space-y-2.5">
              {recent.data.map((analysis, index) => (
                <Row
                  key={analysis.id}
                  analysis={analysis}
                  onReanalyze={reanalyze}
                  busy={analyzeRepo.isPending}
                  active={activeRepoIds.has(analysis.repository_id)}
                  index={index}
                />
              ))}
            </ul>
          )}

          {recent.isError && (
            <EmptyState
              title="Could not load your analyses"
              detail="Is the API running?"
              icon="alert"
            />
          )}
        </section>
      </Reveal>

      <Reveal delay={0.06}>
        <section>
          <div className="mb-4">
            <h2 className="text-xl font-semibold tracking-tight text-ink">Your repositories</h2>
          </div>
          {repos.data?.length === 0 && (
            <p className="text-[13px] text-faint">
              No repositories yet —{" "}
              <Link to="/repos" className="link">
                add one
              </Link>
              .
            </p>
          )}
          {repos.data && repos.data.length > 0 && (
            <div className="panel flex flex-wrap items-center justify-between gap-3 p-4">
              <p className="text-[13px] text-muted">
                <span className="figure text-2xl text-ink">
                  <CountUp value={repos.data.length} duration={0.6} />
                </span>{" "}
                repositor{repos.data.length === 1 ? "y" : "ies"} tracked
              </p>
              <Link to="/repos" className="btn btn--ghost group press">
                Manage repositories
                <Icon
                  name="arrow-right"
                  size={14}
                  className="transition-transform duration-200 group-hover:translate-x-0.5"
                />
              </Link>
            </div>
          )}
        </section>
      </Reveal>
    </div>
  );
}
