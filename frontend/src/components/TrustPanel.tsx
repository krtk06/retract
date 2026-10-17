import { useTrustSummary } from "../api/hooks";

export function TrustPanel({ analysisId }: { analysisId: number }) {
  const summary = useTrustSummary(analysisId, true);

  if (summary.isLoading) {
    return <p className="text-sm text-muted">Loading trust summary…</p>;
  }
  if (!summary.data) return null;
  const data = summary.data;
  const coverage = data.verification_coverage;
  const decisionAgents = data.acceptance_rates.filter((r) => r.shown > 0);

  return (
    <section className="px-panel p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold text-ink">Trust Summary</h3>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="px-badge border border-line-strong bg-surface-2 text-muted tabular-nums">
            {data.totals.findings} findings
          </span>
          <span className="px-badge border border-ok/30 bg-ok-soft text-ok tabular-nums">
            {data.totals.verified} verified
          </span>
          <span className="px-badge border border-hypo/30 bg-hypo-soft text-hypo tabular-nums">
            {data.totals.hypotheses} hypotheses
          </span>
          {data.totals.dismissed > 0 && (
            <span className="px-badge border border-line bg-surface-2 text-faint tabular-nums">
              {data.totals.dismissed} dismissed
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <div className="border border-line bg-surface-2 p-4">
          <p className="px-eyebrow">Verification coverage</p>
          <p className="mt-1.5 text-3xl font-extrabold tabular-nums tracking-tight text-ink">
            {coverage == null ? "—" : `${Math.round(coverage * 100)}%`}
          </p>
          <div className="mt-3 h-2 overflow-hidden bg-line ring-1 ring-line">
            <div
              className="h-full"
              style={{
                width: `${(coverage ?? 0) * 100}%`,
                background: "linear-gradient(90deg, color-mix(in oklab, var(--ok) 55%, transparent), var(--ok))",
                transition: "width 800ms cubic-bezier(0.32, 0.72, 0, 1)",
              }}
            />
          </div>
          <p className="mt-2 text-xs text-faint">share of open findings corroborated by a deterministic check</p>
        </div>
        <div className="border border-line bg-surface-2 p-4">
          <p className="px-eyebrow">Average confidence</p>
          <p className="mt-1.5 text-3xl font-extrabold tabular-nums tracking-tight text-ink">
            {data.avg_confidence == null ? "—" : data.avg_confidence.toFixed(2)}
          </p>
          <p className="mt-2 text-xs text-faint">
            calibrated across history, corroboration, and model signals
          </p>
        </div>
      </div>

      <h4 className="mt-6 text-[11px] font-semibold uppercase tracking-[0.18em] text-faint">
        Per-agent findings
      </h4>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-faint">
              <th className="pb-2 font-medium">Agent</th>
              <th className="pb-2 font-medium">Findings</th>
              <th className="pb-2 font-medium">V / H / D</th>
              <th className="pb-2 text-right font-medium">Avg confidence</th>
            </tr>
          </thead>
          <tbody>
            {data.agents.map((agent) => (
              <tr key={agent.agent} className="border-t border-line">
                <td className="py-2 font-semibold capitalize text-ink">{agent.agent}</td>
                <td className="py-2 text-muted tabular-nums">{agent.findings}</td>
                <td className="py-2 text-muted tabular-nums">
                  {agent.verified} / {agent.hypotheses} / {agent.dismissed}
                </td>
                <td className="py-2 text-right text-ink tabular-nums">
                  {agent.avg_confidence == null ? "—" : agent.avg_confidence.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {decisionAgents.length > 0 && (
        <>
          <h4 className="mt-6 text-[11px] font-semibold uppercase tracking-[0.18em] text-faint">
            Human acceptance by category
          </h4>
          <ul className="mt-3 space-y-2">
            {decisionAgents.map((row) => (
              <li key={`${row.agent}-${row.category}`} className="flex items-center gap-3 text-sm">
                <span className="w-28 truncate text-muted">
                  {row.agent}/{row.category}
                </span>
                <div className="h-2 flex-1 overflow-hidden bg-line ring-1 ring-line">
                  <div
                    className="h-full"
                    style={{
                      width: `${(row.acceptance_rate ?? 0) * 100}%`,
                      background: "linear-gradient(90deg, color-mix(in oklab, var(--info) 55%, transparent), var(--info))",
                      transition: "width 800ms cubic-bezier(0.32, 0.72, 0, 1)",
                    }}
                  />
                </div>
                <span className="w-24 text-right text-xs text-faint tabular-nums">
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
