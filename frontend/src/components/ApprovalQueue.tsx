import { useState } from "react";

import { useApprovalQueue, useCalibrationStats, useDecide } from "../api/hooks";
import type { Finding } from "../api/types";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-danger/45 bg-danger-soft text-danger",
  high: "border-danger/25 bg-danger-soft text-danger",
  medium: "border-warn/30 bg-warn-soft text-warn",
  low: "border-info/25 bg-info-soft text-info",
  info: "border-line-strong bg-surface-2 text-muted",
};

function gateBadge(finding: Finding) {
  const sev = finding.severity;
  return (
    <span
      className={`border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${SEVERITY_STYLES[sev]}`}
    >
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
    <li className="px-card px-4 py-3.5">
      <div className="flex flex-wrap items-center gap-2">
        {gateBadge(finding)}
        <p className="text-sm font-semibold text-ink text-pretty">{finding.title}</p>
        <span className="ml-auto text-xs text-faint tabular-nums">
          {finding.agent} · {finding.verifier} · conf {finding.confidence.toFixed(2)}
          {finding.confidence < 0.5 && (
            <span
              className="ml-1 rounded border border-danger/30 bg-danger-soft px-1 text-danger"
              title="low confidence"
            >
              low
            </span>
          )}
        </span>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-muted text-pretty">{finding.description}</p>
      {finding.file_path && (
        <p className="mt-1.5 inline-block bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-faint">
          {finding.file_path}
          {finding.line_start ? `:${finding.line_start}` : ""}
        </p>
      )}
      <p className="mt-1.5 text-xs text-faint">
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
            className="px-input px-3 py-2 text-sm"
          />
          <div className="flex gap-2">
            <button
              onClick={() =>
                decide.mutate({ analysisId, findingId: finding.id, decision: "approve", note })
              }
              disabled={decide.isPending}
              className="px-btn px-btn--primary px-3.5 py-1.5 text-sm"
            >
              Approve
            </button>
            <button
              onClick={() =>
                decide.mutate({ analysisId, findingId: finding.id, decision: "dismiss", note })
              }
              disabled={decide.isPending}
              className="px-btn px-btn--ghost px-3.5 py-1.5 text-sm"
            >
              Dismiss
            </button>
            <button
              onClick={() => setOpen(false)}
              className="px-btn--quiet px-2.5 py-1.5 text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="px-btn px-btn--ghost mt-3 px-3.5 py-1.5 text-sm"
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
    return <p className="text-sm text-muted">Loading approval queue…</p>;
  }
  if (!queue.data) return null;

  const { pending, published, pending_count } = queue.data;

  return (
    <section className="px-panel p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold text-ink">Human Approval Queue</h3>
        {published ? (
          <span className="px-badge border border-ok/30 bg-ok-soft text-ok">
            <span aria-hidden="true" className="h-1.5 w-1.5 bg-ok" />
            published
          </span>
        ) : (
          <span className="px-badge border border-warn/30 bg-warn-soft text-warn">
            <span aria-hidden="true" className="anim-blink h-1.5 w-1.5 bg-warn" />
            {pending_count} awaiting review
          </span>
        )}
      </div>
      {published && (
        <p className="mt-2 text-xs text-faint">
          All high-severity hypotheses have been reviewed. This analysis is published.
        </p>
      )}
      {!published && (
        <p className="mt-2 text-xs leading-relaxed text-faint text-pretty">
          High-severity LLM hypotheses require an explicit decision before the analysis is
          published. Approving promotes a finding to verified; dismissing removes its weight.
        </p>
      )}
      <ul className="mt-4 space-y-2.5">
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
        <p className="mt-3 text-sm text-faint">No pending items.</p>
      )}
    </section>
  );
}
