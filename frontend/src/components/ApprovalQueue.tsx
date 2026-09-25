import { useState } from "react";

import { useApprovalQueue, useCalibrationStats, useDecide } from "../api/hooks";
import type { Finding } from "../api/types";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-700 text-white",
  high: "bg-red-900 text-red-200",
  medium: "bg-amber-900 text-amber-200",
  low: "bg-sky-900 text-blue-200",
  info: "bg-zinc-700 text-zinc-300",
};

function gateBadge(finding: Finding) {
  const sev = finding.severity;
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${SEVERITY_STYLES[sev]}`}>
      {sev}
    </span>
  );
}

function QueueItem({
  analysisId,
  finding,
  acceptanceRate,
}: {
  analysisId: number;
  finding: Finding;
  acceptanceRate: number | null;
}) {
  const decide = useDecide();
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(false);
  const calibration = (finding.evidence_json?.calibration ?? {}) as Record<string, unknown>;

  return (
    <li className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        {gateBadge(finding)}
        <p className="text-sm font-medium">{finding.title}</p>
        <span className="ml-auto text-xs text-zinc-500">
          {finding.agent} · {finding.verifier} · conf {finding.confidence.toFixed(2)}
          {finding.confidence < 0.5 && (
            <span className="ml-1 rounded bg-red-950 px-1 text-red-300" title="low confidence">
              low
            </span>
          )}
        </span>
      </div>
      <p className="mt-1 text-sm text-zinc-400">{finding.description}</p>
      {finding.file_path && (
        <p className="mt-1 font-mono text-xs text-zinc-500">
          {finding.file_path}
          {finding.line_start ? `:${finding.line_start}` : ""}
        </p>
      )}
      <p className="mt-1 text-xs text-zinc-500">
        history for {finding.agent}/{finding.category}:{" "}
        {acceptanceRate == null ? "no data yet" : `${Math.round(acceptanceRate * 100)}% accepted`}
        {calibration.corroborated === true && " · corroborated by another source"}
      </p>

      {open ? (
        <div className="mt-3 space-y-2">
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note explaining the decision"
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm outline-none placeholder:text-zinc-600 focus:border-zinc-500"
          />
          <div className="flex gap-2">
            <button
              onClick={() =>
                decide.mutate({ analysisId, findingId: finding.id, decision: "approve", note })
              }
              disabled={decide.isPending}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() =>
                decide.mutate({ analysisId, findingId: finding.id, decision: "dismiss", note })
              }
              disabled={decide.isPending}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-800 disabled:opacity-50"
            >
              Dismiss
            </button>
            <button
              onClick={() => setOpen(false)}
              className="px-2 py-1.5 text-sm text-zinc-500 hover:text-zinc-300"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="mt-3 rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-800"
        >
          Review
        </button>
      )}
    </li>
  );
}

export function ApprovalQueue({ analysisId }: { analysisId: number }) {
  const queue = useApprovalQueue(analysisId, true);
  const stats = useCalibrationStats(true);

  const rateFor = (agent: string, category: string): number | null => {
    const match = stats.data?.find((s) => s.agent === agent && s.category === category);
    return match?.acceptance_rate ?? null;
  };

  if (queue.isLoading) {
    return <p className="text-sm text-zinc-400">Loading approval queue…</p>;
  }
  if (!queue.data) return null;

  const { pending, published, pending_count } = queue.data;

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Human Approval Queue</h3>
        {published ? (
          <span className="rounded-full bg-emerald-950 px-2.5 py-0.5 text-xs text-emerald-300">
            published
          </span>
        ) : (
          <span className="rounded-full bg-amber-950 px-2.5 py-0.5 text-xs text-amber-300">
            {pending_count} awaiting review
          </span>
        )}
      </div>
      {published && (
        <p className="mt-2 text-xs text-zinc-500">
          All high-severity hypotheses have been reviewed. This analysis is published.
        </p>
      )}
      {!published && (
        <p className="mt-2 text-xs text-zinc-500">
          High-severity LLM hypotheses require an explicit decision before the analysis is
          published. Approving promotes a finding to verified; dismissing removes its weight.
        </p>
      )}
      <ul className="mt-3 space-y-2">
        {pending.map((finding) => (
          <QueueItem
            key={finding.id}
            analysisId={analysisId}
            finding={finding}
            acceptanceRate={rateFor(finding.agent, finding.category)}
          />
        ))}
      </ul>
      {pending.length === 0 && !published && (
        <p className="mt-3 text-sm text-zinc-500">No pending items.</p>
      )}
    </section>
  );
}
