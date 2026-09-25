import { useTrustSummary } from "../api/hooks";

export function TrustPanel({ analysisId }: { analysisId: number }) {
  const summary = useTrustSummary(analysisId, true);

  if (summary.isLoading) {
    return <p className="text-sm text-zinc-400">Loading trust summary…</p>;
  }
  if (!summary.data) return null;
  const data = summary.data;
  const coverage = data.verification_coverage;
  const decisionAgents = data.acceptance_rates.filter((r) => r.shown > 0);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">Trust Summary</h3>
        <div className="flex gap-2 text-xs">
          <span className="rounded-full bg-zinc-800 px-2.5 py-1">
            {data.totals.findings} findings
          </span>
          <span className="rounded-full bg-emerald-950 px-2.5 py-1 text-emerald-300">
            {data.totals.verified} verified
          </span>
          <span className="rounded-full bg-purple-950 px-2.5 py-1 text-purple-300">
            {data.totals.hypotheses} hypotheses
          </span>
          {data.totals.dismissed > 0 && (
            <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-zinc-400">
              {data.totals.dismissed} dismissed
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Verification coverage</p>
          <p className="mt-1 text-2xl font-semibold">
            {coverage == null ? "—" : `${Math.round(coverage * 100)}%`}
          </p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-700"
              style={{ width: `${(coverage ?? 0) * 100}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-zinc-500">
            share of open findings corroborated by a deterministic check
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Average confidence</p>
          <p className="mt-1 text-2xl font-semibold">
            {data.avg_confidence == null ? "—" : data.avg_confidence.toFixed(2)}
          </p>
          <p className="mt-2 text-xs text-zinc-500">
            calibrated across history, corroboration, and model signals
          </p>
        </div>
      </div>

      <h4 className="mt-5 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Per-agent findings
      </h4>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-zinc-500">
              <th className="pb-2 font-medium">Agent</th>
              <th className="pb-2 font-medium">Findings</th>
              <th className="pb-2 font-medium">V / H / D</th>
              <th className="pb-2 text-right font-medium">Avg confidence</th>
            </tr>
          </thead>
          <tbody>
            {data.agents.map((agent) => (
              <tr key={agent.agent} className="border-t border-zinc-800/70">
                <td className="py-1.5 font-medium capitalize">{agent.agent}</td>
                <td className="py-1.5 text-zinc-400">{agent.findings}</td>
                <td className="py-1.5 text-zinc-400">
                  {agent.verified} / {agent.hypotheses} / {agent.dismissed}
                </td>
                <td className="py-1.5 text-right text-zinc-300">
                  {agent.avg_confidence == null ? "—" : agent.avg_confidence.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {decisionAgents.length > 0 && (
        <>
          <h4 className="mt-5 text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Human acceptance by category
          </h4>
          <ul className="mt-2 space-y-1.5">
            {decisionAgents.map((row) => (
              <li key={`${row.agent}-${row.category}`} className="flex items-center gap-3 text-sm">
                <span className="w-28 truncate text-zinc-300">
                  {row.agent}/{row.category}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full rounded-full bg-sky-500"
                    style={{ width: `${(row.acceptance_rate ?? 0) * 100}%` }}
                  />
                </div>
                <span className="w-24 text-right text-xs text-zinc-500">
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
