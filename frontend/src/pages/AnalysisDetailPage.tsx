import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { useAnalysis, useFindings } from "../api/hooks";
import type { AnalysisEvent } from "../api/types";
import { StatusPill } from "../components/StatusPill";

const EVENT_NAMES = ["status", "step", "done", "failed"];

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString();
}

export function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const analysisId = Number(id);
  const analysis = useAnalysis(analysisId);
  const isActive =
    analysis.data?.status === "pending" || analysis.data?.status === "running";
  const findings = useFindings(analysisId, analysis.data?.status === "done");
  const [events, setEvents] = useState<AnalysisEvent[]>([]);

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

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Analysis #{data.id}</h2>
          <StatusPill status={data.status} />
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
      </section>

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
              <span className="text-zinc-300">{event.type}</span>
              <span>
                {(event.payload.message as string) ??
                  (event.payload.status as string) ??
                  (event.payload.error as string) ??
                  ""}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {data.status === "done" && (
        <section>
          <h3 className="mb-3 font-semibold">Findings</h3>
          {findings.isLoading && <p className="text-sm text-zinc-400">Loading findings…</p>}
          <ul className="space-y-2">
            {findings.data?.map((finding) => (
              <li
                key={finding.id}
                className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{finding.title}</p>
                  <span className="text-xs text-zinc-500">
                    {finding.agent} · {finding.verifier} · confidence{" "}
                    {finding.confidence.toFixed(2)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-zinc-400">{finding.description}</p>
                {finding.evidence_json?.languages != null && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(
                      finding.evidence_json.languages as Record<string, number>,
                    ).map(([language, count]) => (
                      <span
                        key={language}
                        className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300"
                      >
                        {language} {count}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
