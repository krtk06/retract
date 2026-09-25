import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useCompare, useHistory } from "../api/hooks";
import type { AnalysisHistoryItem } from "../api/types";

const PILLAR_LABELS: Record<string, string> = {
  "code-quality": "Code Quality",
  security: "Security",
  testing: "Testing",
  documentation: "Documentation",
  dependencies: "Dependencies",
  architecture: "Architecture",
};

function Delta({ value }: { value: number }) {
  if (value === 0) return <span className="text-zinc-500">—</span>;
  const up = value > 0;
  return (
    <span className={`font-medium ${up ? "text-emerald-400" : "text-red-400"}`}>
      {up ? "+" : ""}
      {value}
    </span>
  );
}

function statusBadge(item: AnalysisHistoryItem) {
  if (item.status !== "done") {
    return (
      <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300">
        {item.status}
      </span>
    );
  }
  return (
    <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] text-emerald-300">done</span>
  );
}

export function HistoryCompare({ analysisId }: { analysisId: number }) {
  const navigate = useNavigate();
  const history = useHistory(analysisId, true);
  const [left, setLeft] = useState<number | null>(null);
  const [right, setRight] = useState<number | null>(null);
  const comparison = useCompare(left, right);

  if (history.isLoading) {
    return <p className="text-sm text-zinc-400">Loading analysis history…</p>;
  }
  const items = history.data ?? [];
  if (items.length <= 1) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <h3 className="font-semibold">History</h3>
        <p className="mt-2 text-sm text-zinc-500">
          This is the first analysis for this repository. Re-run it after changes to compare
          scores over time.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <h3 className="font-semibold">Analysis History</h3>
      <p className="mt-1 text-xs text-zinc-500">
        Select two runs to compare scores side-by-side.
      </p>
      <ul className="mt-3 space-y-1.5">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex flex-wrap items-center gap-2 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm"
          >
            <button
              onClick={() => navigate(`/analyses/${item.id}`)}
              className="font-mono text-sky-400 hover:underline"
            >
              #{item.id}
            </button>
            {statusBadge(item)}
            <span className="text-zinc-500">
              {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
            </span>
            <span className="font-mono text-xs text-zinc-600">
              {item.commit_sha ? item.commit_sha.slice(0, 8) : "—"}
            </span>
            <span className="text-xs text-zinc-500">{item.finding_count} findings</span>
            {item.overall != null && (
              <span className="text-sm font-medium text-zinc-200">{item.overall}/100</span>
            )}
            <span className="ml-auto flex gap-1">
              <button
                onClick={() => setLeft(item.id)}
                className={`rounded px-2 py-0.5 text-xs ${
                  left === item.id
                    ? "bg-sky-700 text-white"
                    : "border border-zinc-700 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                A
              </button>
              <button
                onClick={() => setRight(item.id)}
                className={`rounded px-2 py-0.5 text-xs ${
                  right === item.id
                    ? "bg-violet-700 text-white"
                    : "border border-zinc-700 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                B
              </button>
            </span>
          </li>
        ))}
      </ul>

      {left != null && right != null && (
        <div className="mt-5 rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <h4 className="text-sm font-semibold">
            Comparison:{" "}
            <span className="font-mono text-sky-400">#{left}</span> →{" "}
            <span className="font-mono text-violet-400">#{right}</span>
          </h4>
          {comparison.isLoading && (
            <p className="mt-2 text-xs text-zinc-500">Loading comparison…</p>
          )}
          {comparison.data && (
            <>
              <p className="mt-2 text-sm">
                Overall{" "}
                <span className="text-zinc-400">
                  {comparison.data.left.overall ?? "—"} → {comparison.data.right.overall ?? "—"}
                </span>{" "}
                <Delta value={comparison.data.overall_delta ?? 0} />
              </p>
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500">
                    <th className="pb-1 font-medium">Pillar</th>
                    <th className="pb-1 font-medium">A</th>
                    <th className="pb-1 font-medium">B</th>
                    <th className="pb-1 text-right font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.data.pillars.map((pillar) => (
                    <tr key={pillar.pillar} className="border-t border-zinc-800/70">
                      <td className="py-1 text-zinc-300">
                        {PILLAR_LABELS[pillar.pillar] ?? pillar.pillar}
                      </td>
                      <td className="py-1 text-zinc-400">{pillar.left_score}</td>
                      <td className="py-1 text-zinc-400">{pillar.right_score}</td>
                      <td className="py-1 text-right">
                        <Delta value={pillar.delta} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {comparison.isError && (
            <p className="mt-2 text-xs text-red-400">
              Could not compare these analyses.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
