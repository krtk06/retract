import { useState } from "react";
import { AnimatePresence, m } from "motion/react";

import { useApprovalQueue, useCalibrationStats, useDecide } from "../api/hooks";
import { EASE } from "../lib/motion";
import { SEVERITY_COLOR_VAR } from "../lib/palette";
import { EmptyState } from "./EmptyState";
import type { Finding } from "../api/types";

function gateBadge(finding: Finding) {
  const sev = finding.severity;
  const severityColor = `var(${SEVERITY_COLOR_VAR[sev]})`;
  return (
    <span className="chip chip--flat" style={{ borderColor: severityColor, color: severityColor }}>
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
    <m.li
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4, transition: { duration: 0.18, ease: EASE } }}
      transition={{ duration: 0.32, ease: EASE }}
      className="inset px-4 py-3.5"
    >
      <div className="flex flex-wrap items-center gap-2">
        {gateBadge(finding)}
        <p className="text-[13px] font-medium text-ink text-pretty">{finding.title}</p>
        <span className="ml-auto text-[11px] text-faint tabular-nums">
          {finding.agent} · {finding.verifier} · conf {finding.confidence.toFixed(2)}
          {finding.confidence < 0.5 && (
            <span
              className="ml-1 rounded-[4px] border border-danger/40 bg-danger-soft px-1 text-danger"
              title="low confidence"
            >
              low
            </span>
          )}
        </span>
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-muted text-pretty">
        {finding.description}
      </p>
      {finding.file_path && (
        <p className="mt-1.5 inline-block rounded-[2px] bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted">
          {finding.file_path}
          {finding.line_start ? `:${finding.line_start}` : ""}
        </p>
      )}
      <p className="mt-1.5 text-[12px] text-faint">
        history for {finding.agent}/{finding.category}:{" "}
        {acceptanceRate == null ? "no data yet" : `${Math.round(acceptanceRate * 100)}% accepted`}
        {calibration.corroborated === true && " · corroborated by another source"}
      </p>

      {open ? (
        <m.div
          className="mt-3 space-y-2 overflow-hidden"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          transition={{ duration: 0.26, ease: EASE }}
        >
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note explaining the decision"
            className="input"
          />
          <div className="flex gap-2">
            <button
              onClick={() =>
                decide.mutate({ analysisId, findingId: finding.id, decision: "approve", note })
              }
              disabled={decide.isPending}
              className="btn btn--primary sheen press"
            >
              Approve
            </button>
            <button
              onClick={() =>
                decide.mutate({ analysisId, findingId: finding.id, decision: "dismiss", note })
              }
              disabled={decide.isPending}
              className="btn btn--ghost"
            >
              Dismiss
            </button>
            <button onClick={() => setOpen(false)} className="btn btn--quiet">
              Cancel
            </button>
          </div>
        </m.div>
      ) : (
        <button onClick={() => setOpen(true)} className="btn btn--ghost mt-3 press">
          Review
        </button>
      )}
    </m.li>
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
    return <p className="text-[13px] text-muted">Loading approval queue…</p>;
  }
  if (!queue.data) return null;

  const { pending, published, pending_count } = queue.data;

  return (
    <section className="panel p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-ink">Human Approval Queue</h3>
        {published ? (
          <span className="chip border-ok/40 bg-ok-soft text-ok">
            <span aria-hidden="true" className="h-1.5 w-1.5 bg-ok" />
            published
          </span>
        ) : (
          <span className="chip border-warn/40 bg-warn-soft text-warn">
            <span aria-hidden="true" className="anim-pulse block h-1.5 w-1.5 bg-warn" />
            {pending_count} awaiting review
          </span>
        )}
      </div>
      {published && (
        <p className="mt-2 text-[12px] text-faint">
          All high-severity hypotheses have been reviewed. This analysis is published.
        </p>
      )}
      {!published && (
        <p className="mt-2 text-[12px] leading-relaxed text-faint text-pretty">
          High-severity LLM hypotheses require an explicit decision before the analysis is
          published. Approving promotes a finding to verified; dismissing removes its weight.
        </p>
      )}
      <ul className="mt-4 space-y-2.5">
        <AnimatePresence initial={false}>
          {pending.map((finding) => (
            <QueueItem
              key={finding.id}
              analysisId={analysisId}
              finding={finding}
              acceptanceRate={rateFor(finding.agent, finding.category)}
            />
          ))}
        </AnimatePresence>
      </ul>
      {pending.length === 0 && !published && (
        <EmptyState
          title="Nothing awaiting review"
          detail="High-severity agent claims land here for a human decision."
        />
      )}
    </section>
  );
}
