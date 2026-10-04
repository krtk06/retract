import { useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { useAnalysis, useFindings, useScore } from "../api/hooks";
import type { AnalysisEvent } from "../api/types";
import { ApprovalQueue } from "../components/ApprovalQueue";
import { ExploreTab } from "../components/ExploreTab";
import { FindingsTable } from "../components/FindingsTable";
import { HistoryCompare } from "../components/HistoryCompare";
import { ScoreHero } from "../components/ScoreHero";
import { StatusPill } from "../components/StatusPill";
import { TrustPanel } from "../components/TrustPanel";

// The eve client is ~450 kB of the bundle, so the agent surface loads only when
// the tab is opened.
const AgentChat = lazy(() =>
  import("../components/AgentChat").then((module) => ({ default: module.AgentChat })),
);

const EVENT_NAMES = ["status", "step", "tool", "agent", "done", "failed"];

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
  const [tab, setTab] = useState<"overview" | "explore" | "agent">("overview");

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
    return <p className="text-sm text-zinc-400">Loading analysis…</p>;
  }
  if (analysis.isError || !analysis.data) {
    return <p className="text-sm text-red-300">Analysis not found.</p>;
  }

  const data = analysis.data;
  const repo = data.repository;
  const title = repo ? `${repo.owner}/${repo.name}` : `Analysis #${data.id}`;

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">{title}</h1>
          <div className="flex items-center gap-2">
            {data.status === "done" && !data.published && data.pending_approvals > 0 && (
              <span className="rounded-full bg-amber-950 px-2.5 py-0.5 text-xs text-amber-300">
                {data.pending_approvals} pending review
              </span>
            )}
            <StatusPill status={data.status} />
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-4">
          <div>
            <dt className="text-zinc-500">Commit</dt>
            <dd className="font-mono">{data.commit_sha?.slice(0, 8) ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Started</dt>
            <dd>{data.started_at ? new Date(data.started_at).toLocaleString() : "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Finished</dt>
            <dd>{data.finished_at ? new Date(data.finished_at).toLocaleString() : "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Findings</dt>
            <dd>{data.finding_count}</dd>
          </div>
        </dl>
        {data.error && (
          <p className="mt-4 rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
            {data.error}
          </p>
        )}
        {data.status === "done" && (
          <div className="mt-4 flex gap-1 border-b border-zinc-800">
            {(["overview", "explore", "agent"] as const).map((name) => (
              <button
                key={name}
                onClick={() => setTab(name)}
                className={`-mb-px border-b-2 px-3 py-1.5 text-sm capitalize ${
                  tab === name
                    ? "border-emerald-500 text-zinc-100"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        )}
      </section>

      {tab === "overview" && (
        <>
          {/* /score recomputes and persists a missing score, so an analysis whose
              finalize step never cached one still shows its health score. */}
          {data.status === "done" && <ScoreHero score={score.data ?? data.score_json} />}

          {data.status === "done" && <ApprovalQueue analysisId={analysisId} />}

          <section>
            <h3 className="mb-3 font-semibold">Progress</h3>
            {events.length === 0 && isActive && (
              <p className="text-sm text-zinc-500">Waiting for events…</p>
            )}
            {events.length === 0 && !isActive && (
              <p className="text-sm text-zinc-500">No events recorded.</p>
            )}
            <ul className="space-y-1 font-mono text-xs text-zinc-400">
              {events.map((event, index) => (
                <li key={index} className="flex gap-3">
                  <span className="text-zinc-600">{formatTime(event.ts)}</span>
                  <span className="w-24 shrink-0 text-zinc-300">
                    {event.type === "tool"
                      ? `tool:${event.payload.tool}`
                      : event.type === "agent"
                        ? `agent:${event.payload.agent}`
                        : event.type}
                  </span>
                  <span>
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
        </>
      )}

      {tab === "explore" && data.status === "done" && <ExploreTab analysisId={analysisId} />}

      {tab === "agent" && data.status === "done" && (
        <Suspense
          fallback={<p className="text-sm text-zinc-500">Loading the agent…</p>}
        >
          <AgentChat analysisId={analysisId} />
        </Suspense>
      )}
    </div>
  );
}
