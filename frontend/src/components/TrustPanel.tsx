import { m } from "motion/react";

import { useTrustSummary } from "../api/hooks";
import { CountUp } from "./CountUp";
import { Meter } from "./Meter";
import { EASE, stagger } from "../lib/motion";

export function TrustPanel({ analysisId }: { analysisId: number }) {
  const summary = useTrustSummary(analysisId, true);

  if (summary.isLoading) {
    return <p className="text-[13px] text-muted">Loading trust summary…</p>;
  }
  if (!summary.data) return null;
  const data = summary.data;
  const coverage = data.verification_coverage;
  const decisionAgents = data.acceptance_rates.filter((r) => r.shown > 0);

  return (
    <section className="panel p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-ink">Trust summary</h3>
        <div className="flex flex-wrap gap-2 text-[11px]">
          <span className="chip chip--flat border-line-strong bg-surface-2 text-muted tabular-nums">
            {data.totals.findings} findings
          </span>
          <span className="chip chip--flat border-ok/40 bg-ok-soft text-ok tabular-nums">
            {data.totals.verified} verified
          </span>
          <span className="chip chip--flat border-hypo/40 bg-hypo-soft text-hypo tabular-nums">
            {data.totals.hypotheses} hypotheses
          </span>
          {data.totals.dismissed > 0 && (
            <span className="chip chip--flat border-line bg-surface-2 text-faint tabular-nums">
              {data.totals.dismissed} dismissed
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <div className="rounded-[2px] border border-line bg-surface-2 p-4">
          <p className="label">Verification coverage</p>
          <p className="figure mt-1.5 text-3xl text-ink">
            {coverage == null ? (
              "—"
            ) : (
              <>
                <CountUp value={Math.round(coverage * 100)} duration={0.8} />%
              </>
            )}
          </p>
          <div className="mt-3">
            <Meter
              value={coverage == null ? null : coverage * 100}
              label="Verification coverage"
              color="var(--ok)"
            />
          </div>
          <p className="mt-2 text-[12px] text-faint">
            share of open findings corroborated by a deterministic check
          </p>
        </div>
        <div className="rounded-[2px] border border-line bg-surface-2 p-4">
          <p className="label">Average confidence</p>
          <p className="figure mt-1.5 text-3xl text-ink">
            {data.avg_confidence == null ? (
              "—"
            ) : (
              <CountUp value={data.avg_confidence} decimals={2} duration={0.8} delay={0.1} />
            )}
          </p>
          <p className="mt-2 text-[12px] text-faint">
            calibrated across history, corroboration, and model signals
          </p>
        </div>
      </div>

      <h4 className="mt-6 text-[12px] font-semibold text-ink">Per-agent findings</h4>
      <div className="scroll mt-2 overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] text-faint">
              <th className="pb-2 font-medium">Agent</th>
              <th className="pb-2 font-medium">Findings</th>
              <th className="pb-2 font-medium">V / H / D</th>
              <th className="pb-2 text-right font-medium">Avg confidence</th>
            </tr>
          </thead>
          <tbody>
            {data.agents.map((agent, index) => (
              <m.tr
                key={agent.agent}
                className="border-t border-line"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.32, ease: EASE, delay: stagger(index, 0.04, 0.24) }}
              >
                <td className="py-2 font-medium capitalize text-ink">{agent.agent}</td>
                <td className="py-2 text-muted tabular-nums">{agent.findings}</td>
                <td className="py-2 text-muted tabular-nums">
                  {agent.verified} / {agent.hypotheses} / {agent.dismissed}
                </td>
                <td className="py-2 text-right text-ink tabular-nums">
                  {agent.avg_confidence == null ? "—" : agent.avg_confidence.toFixed(2)}
                </td>
              </m.tr>
            ))}
          </tbody>
        </table>
      </div>

      {decisionAgents.length > 0 && (
        <>
          <h4 className="mt-6 text-[12px] font-semibold text-ink">Human acceptance by category</h4>
          <ul className="mt-3 space-y-2.5">
            {decisionAgents.map((row) => (
              <li key={`${row.agent}-${row.category}`} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] sm:flex-nowrap">
                <span className="w-full truncate text-muted sm:w-56 sm:shrink-0">
                  {row.agent}/{row.category}
                </span>
                <Meter
                  value={row.acceptance_rate == null ? null : row.acceptance_rate * 100}
                  label={`Human acceptance, ${row.category}`}
                  color="var(--info)"
                />
                <span className="w-24 text-right text-[11px] text-faint tabular-nums">
                  {row.accepted}/{row.shown} accepted
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
