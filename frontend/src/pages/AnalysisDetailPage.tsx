import { useQueryClient } from "@tanstack/react-query";
import { m } from "motion/react";
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAnalysis, useFindings, useScore } from "../api/hooks";
import type { Analysis, AnalysisEvent } from "../api/types";
import { EASE } from "../lib/motion";
import { ApprovalQueue } from "../components/ApprovalQueue";
import { Loading } from "../components/EmptyState";
import { ExploreTab } from "../components/ExploreTab";
import { FindingsTable } from "../components/FindingsTable";
import { HistoryCompare } from "../components/HistoryCompare";
import { Icon } from "../components/Icon";
import { ScoreHero } from "../components/ScoreHero";
import { StatusPill } from "../components/StatusPill";
import { TrustPanel } from "../components/TrustPanel";

// The eve client is ~450 kB of the bundle, so the agent surface loads only when
// the tab is opened.
const AgentChat = lazy(() =>
  import("../components/AgentChat").then((module) => ({ default: module.AgentChat })),
);

// The eve client is ~450 kB of the bundle, and the fix plan is the other panel
// that needs it only on demand.
const RemediationPlanPanel = lazy(() =>
  import("../components/RemediationPlan").then((module) => ({
    default: module.RemediationPlanPanel,
  })),
);
const RemediationSummaryCard = lazy(() =>
  import("../components/RemediationPlan").then((module) => ({
    default: module.RemediationSummaryCard,
  })),
);

const EVENT_NAMES = ["status", "step", "tool", "agent", "done", "failed"];

const TABS = ["overview", "explore", "fixes", "agent"] as const;
type TabName = (typeof TABS)[number];

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function toolEventText(payload: Record<string, unknown>): string {
  if (payload.status === "ok") {
    return `${payload.findings} findings (${payload.seconds}s)`;
  }
  if (payload.status === "skipped") {
    return `skipped: ${String(payload.error ?? "").slice(0, 120)}`;
  }
  return `error: ${String(payload.error ?? "").slice(0, 120)} (${payload.seconds}s)`;
}

function agentEventText(payload: Record<string, unknown>): string {
  if (payload.status === "ok") {
    const dismissed = Number(payload.dismissed ?? 0);
    const tokens = `${payload.tokens_in ?? 0}in/${payload.tokens_out ?? 0}out`;
    return `${payload.findings} findings${dismissed ? `, ${dismissed} dismissed` : ""} · ${tokens} tokens · ${payload.seconds}s`;
  }
  if (payload.status === "skipped") {
    return `skipped: ${String(payload.error ?? "").slice(0, 140)}`;
  }
  return `error: ${String(payload.error ?? "").slice(0, 140)}`;
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="inset px-3 py-2">
      <dt className="label">{label}</dt>
      <dd className="mt-1 truncate text-[13px] text-ink">{children}</dd>
    </div>
  );
}

function AnalysisHeader({
  data,
  title,
  tab,
  onSelectTab,
}: {
  data: Analysis;
  title: string;
  tab: TabName;
  onSelectTab: (tab: TabName) => void;
}) {
  return (
    <section className="panel p-6">
      <Link to="/" className="btn btn--quiet mb-3">
        <Icon name="arrow-left" size={15} />
        Back
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-ink text-balance">{title}</h1>
        <div className="flex items-center gap-2">
          {data.status === "done" && !data.published && data.pending_approvals > 0 && (
            <span className="chip border-warn/40 bg-warn-soft text-warn">
              {data.pending_approvals} pending review
            </span>
          )}
          <StatusPill status={data.status} />
          {/* The report's remedy: the primary action of a finished analysis is
              the fix plan, and it lives in this rail. */}
          {data.status === "done" && (
            <button
              type="button"
              onClick={() => onSelectTab("fixes")}
              className="btn btn--primary sheen press"
            >
              View fix plan
            </button>
          )}
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <Stat label="Commit">
          <span className="font-mono text-[12px]">{data.commit_sha?.slice(0, 8) ?? "—"}</span>
        </Stat>
        <Stat label="Started">
          {data.started_at ? new Date(data.started_at).toLocaleString() : "—"}
        </Stat>
        <Stat label="Finished">
          {data.finished_at ? new Date(data.finished_at).toLocaleString() : "—"}
        </Stat>
        <Stat label="Findings">
          <span className="tabular-nums">{data.finding_count}</span>
        </Stat>
      </dl>

      {data.error && (
        <p className="mt-4 rounded-[2px] border border-danger/40 bg-danger-soft px-4 py-2.5 text-[13px] text-danger">
          {data.error}
        </p>
      )}

      {data.status === "done" && (
        <div role="tablist" aria-label="Analysis views" className="tabs mt-5">
          {TABS.map((value) => (
            <button
              key={value}
              role="tab"
              aria-selected={tab === value}
              onClick={() => onSelectTab(value)}
              className="tab tab--motion capitalize"
            >
              {value}
              {tab === value && (
                <m.span
                  layoutId="analysis-tab-underline"
                  className="absolute inset-x-2 -bottom-px h-0.5 bg-ink"
                  transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
                />
              )}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function eventTone(type: string): string {
  if (type === "failed") return "bg-danger";
  if (type === "done") return "bg-ok";
  if (type === "agent") return "bg-hypo";
  if (type === "tool") return "bg-info";
  return "bg-faint";
}

function ProgressFeed({ events, isActive }: { events: AnalysisEvent[]; isActive: boolean }) {
  return (
    <section className="panel p-6">
      <div className="mb-3 flex items-center gap-2.5">
        <h3 className="text-[15px] font-semibold text-ink">Progress</h3>
        {isActive && (
          <span className="flex items-center gap-1.5 text-[11px] text-accent">
            <span aria-hidden="true" className="anim-pulse h-1.5 w-1.5 bg-accent" />
            live
          </span>
        )}
      </div>
      {events.length === 0 && isActive && <p className="text-[13px] text-faint">Waiting for events…</p>}
      {events.length === 0 && !isActive && <p className="text-[13px] text-faint">No events recorded.</p>}
      <ul className="scroll max-h-96 space-y-1 overflow-y-auto font-mono text-[11px]">
        {events.map((event, index) => (
          <li
            key={index}
            className="inset anim-in flex items-start gap-3 px-2.5 py-1.5"
            style={{ animationDuration: "0.4s" }}
          >
            <span
              aria-hidden="true"
              className={`mt-1 h-2 w-2 shrink-0 ${eventTone(event.type)}`}
            />
            <span className="shrink-0 text-faint">{formatTime(event.ts)}</span>
            <span className="w-24 shrink-0 text-ink/80">
              {event.type === "tool"
                ? `tool:${event.payload.tool}`
                : event.type === "agent"
                  ? `agent:${event.payload.agent}`
                  : event.type}
            </span>
            <span className="min-w-0 break-words text-muted">
              {event.type === "tool"
                ? toolEventText(event.payload)
                : event.type === "agent"
                  ? agentEventText(event.payload)
                  : ((event.payload.message as string) ??
                    (event.payload.status as string) ??
                    (event.payload.error as string) ??
                    "")}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const analysisId = Number(id);
  const analysis = useAnalysis(analysisId);
  const isActive =
    analysis.data?.status === "pending" || analysis.data?.status === "running";
  const findings = useFindings(analysisId, analysis.data?.status === "done");
  const isDone = analysis.data?.status === "done";
  const score = useScore(analysisId, isDone);
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [tab, setTab] = useState<TabName>("overview");
  // Handed to the agent panel when the fix plan's "deep fix plan" button is used,
  // so the same eve session is reused rather than a second one opened.
  const [agentPrompt, setAgentPrompt] = useState<string | null>(null);

  const openAgentWith = (prompt: string) => {
    setAgentPrompt(prompt);
    setTab("agent");
  };

  // The score is finalised in the same commit that flips the status to done, so the
  // transition is the signal to read it. Without this the page can keep showing
  // whatever was fetched before completion — which, mid-run, is a 100 scored against
  // an empty finding set.
  const queryClient = useQueryClient();
  const wasDone = useRef(false);
  useEffect(() => {
    if (isDone && !wasDone.current) {
      queryClient.invalidateQueries({ queryKey: ["score", analysisId] });
    }
    wasDone.current = isDone;
  }, [isDone, analysisId, queryClient]);

  useEffect(() => {
    setEvents([]);
    const source = new EventSource(`/api/analyses/${analysisId}/events`);
    const handler = (message: MessageEvent) => {
      const event = JSON.parse(message.data) as AnalysisEvent;
      if (event.type === "ping") return;
      setEvents((prev) => [...prev, event]);
      if (event.type === "done" || event.type === "failed") {
        source.close();
      }
    };
    for (const name of EVENT_NAMES) {
      source.addEventListener(name, handler);
    }
    return () => source.close();
  }, [analysisId]);

  if (analysis.isLoading) {
    return <Loading label="Loading analysis…" />;
  }
  if (analysis.isError || !analysis.data) {
    return <p className="text-[13px] text-danger">Analysis not found.</p>;
  }

  const data = analysis.data;
  const repo = data.repository;
  const title = repo ? `${repo.owner}/${repo.name}` : `Analysis #${data.id}`;

  return (
    <div className="space-y-6">
      <AnalysisHeader data={data} title={title} tab={tab} onSelectTab={setTab} />

      {/* A view switch is a page turn: the new panel settles in, once. The
          key remounts on switch, which is exactly how the panels mounted
          before — the wrapper adds the arrival, nothing else. */}
      <m.div
        key={tab}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: EASE }}
      >
        {tab === "overview" && (
          <div className="space-y-6">
            {/* /score recomputes and persists a missing score, so an analysis whose
                finalize step never cached one still shows its health score. */}
            {data.status === "done" && <ScoreHero score={score.data ?? data.score_json} />}

            {data.status === "done" && <ApprovalQueue analysisId={analysisId} />}

            <ProgressFeed events={events} isActive={isActive} />

            {data.status === "done" && (
              <FindingsTable
                findings={findings.data ?? []}
                repository={repo}
                commitSha={data.commit_sha}
                analysisId={analysisId}
              />
            )}

            {data.status === "done" && <TrustPanel analysisId={analysisId} />}

            {data.status === "done" && <HistoryCompare analysisId={analysisId} />}

            {/* Last on the overview, because it is the answer to the question the
                rest of the page raises: what do I actually do about all this? */}
            {data.status === "done" && (
              <Suspense fallback={null}>
                <RemediationSummaryCard analysisId={analysisId} onOpen={() => setTab("fixes")} />
              </Suspense>
            )}
          </div>
        )}

        {tab === "explore" && data.status === "done" && <ExploreTab analysisId={analysisId} />}

        {tab === "fixes" && data.status === "done" && (
          <Suspense fallback={<Loading label="Building the fix plan…" />}>
            <RemediationPlanPanel
              analysisId={analysisId}
              repository={repo}
              commitSha={data.commit_sha}
              onOpenAgent={() =>
                openAgentWith(
                  "Produce a deep fix plan for this analysis. The dashboard already shows the " +
                    "deterministic remediation catalog; read the findings it did not cover well, " +
                    "and record a repo-specific remediation for each with record_remediation. " +
                    "Cite file:line for every one, and do not invent steps the evidence does not " +
                    "support.",
                )
              }
            />
          </Suspense>
        )}

        {tab === "agent" && data.status === "done" && (
          <Suspense fallback={<Loading label="Loading the agent…" />}>
            <AgentChat analysisId={analysisId} initialPrompt={agentPrompt} />
          </Suspense>
        )}
      </m.div>
    </div>
  );
}
