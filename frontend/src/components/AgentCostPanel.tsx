import type { CostLedger } from "../api/types";

export function AgentCostPanel({ ledger }: { ledger: CostLedger | null }) {
  const runs = ledger?.agents ?? [];
  if (runs.length === 0) return null;

  const totalIn = ledger?.tokens_in ?? runs.reduce((sum, r) => sum + (r.tokens_in ?? 0), 0);
  const totalOut = ledger?.tokens_out ?? runs.reduce((sum, r) => sum + (r.tokens_out ?? 0), 0);
  const mock = runs.some((r) => (r.provider ?? "").startsWith("mock"));

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Agent Activity</h3>
        <p className="text-xs text-zinc-500">
          {totalIn.toLocaleString()} tokens in · {totalOut.toLocaleString()} out
        </p>
      </div>
      {mock && (
        <p className="mt-2 rounded-md bg-amber-950 px-3 py-2 text-xs text-amber-300">
          Running with the offline mock provider — findings are a deterministic harness
          output, not real LLM analysis.
        </p>
      )}
      <ul className="mt-3 space-y-2">
        {runs.map((run, index) => (
          <li key={index} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="font-medium capitalize">{run.agent}</span>
            <span className="text-xs text-zinc-500">{run.model}</span>
            <span className="text-xs text-zinc-400">
              {run.findings ?? 0} findings
              {(run.dismissed ?? 0) > 0 ? ` · ${run.dismissed} dismissed` : ""}
            </span>
            <span className="ml-auto text-xs text-zinc-500">
              {run.tokens_in ?? 0}in / {run.tokens_out ?? 0}out
            </span>
            {run.error && (
              <span className="w-full text-xs text-red-400">error: {run.error}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
