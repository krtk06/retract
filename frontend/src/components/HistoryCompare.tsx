import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useCompare, useHistory } from "../api/hooks";
import type { AnalysisHistoryItem } from "../api/types";
import { PILLAR_LABELS, type Pillar } from "../lib/palette";

function Delta({ value }: { value: number }) {
  if (value === 0) return <span className="text-faint">—</span>;
  const up = value > 0;
  return (
    <span className={`px-badge px-badge--flat font-ui tabular-nums ${up ? "text-ok" : "text-danger"}`}>
      {up ? "+" : ""}
      {value}
    </span>
  );
}

function statusBadge(item: AnalysisHistoryItem) {
  if (item.status !== "done") {
    return (
      <span className="px-badge px-badge--flat font-ui bg-surface-2 text-muted">
        {item.status}
      </span>
    );
  }
  return (
    <span className="px-badge px-badge--flat font-ui bg-ok-soft text-ok">
      done
    </span>
  );
}

export function HistoryCompare({ analysisId }: { analysisId: number }) {
  const navigate = useNavigate();
  const history = useHistory(analysisId, true);
  const [left, setLeft] = useState<number | null>(null);
  const [right, setRight] = useState<number | null>(null);
  const comparison = useCompare(left, right);

  if (history.isLoading) {
    return <p className="text-sm text-muted">Loading analysis history…</p>;
  }
  const items = history.data ?? [];
  if (items.length <= 1) {
    return (
      <section className="px-panel p-5 sm:p-6">
        <h3 className="font-semibold text-ink">History</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted text-pretty">
          This is the first analysis for this repository. Re-run it after changes to compare
          scores over time.
        </p>
      </section>
    );
  }

  return (
    <section className="px-panel p-5 sm:p-6">
      <h3 className="font-semibold text-ink">Analysis History</h3>
      <p className="mt-1 text-xs text-faint">Select two runs to compare scores side-by-side.</p>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex flex-wrap items-center gap-2.5 border border-line bg-surface-2 px-3.5 py-2.5 text-sm"
          >
            <button
              onClick={() => navigate(`/analyses/${item.id}`)}
              className="font-mono text-accent transition-colors duration-300 hover:underline"
            >
              #{item.id}
            </button>
            {statusBadge(item)}
            <span className="text-faint">
              {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
            </span>
            <span className="font-mono text-xs text-faint/80">
              {item.commit_sha ? item.commit_sha.slice(0, 8) : "—"}
            </span>
            <span className="text-xs text-faint tabular-nums">{item.finding_count} findings</span>
            {item.overall != null && (
              <span className="text-sm font-bold text-ink tabular-nums">{item.overall}/100</span>
            )}
            <span className="ml-auto flex gap-1.5">
              <button
                onClick={() => setLeft(item.id)}
                className={`px-btn px-2.5 py-1 text-xs ${
                  left === item.id ? "bg-info text-ink" : "px-btn--ghost"
                }`}
              >
                A
              </button>
              <button
                onClick={() => setRight(item.id)}
                className={`px-btn px-2.5 py-1 text-xs ${
                  right === item.id ? "bg-hypo text-ink" : "px-btn--ghost"
                }`}
              >
                B
              </button>
            </span>
          </li>
        ))}
      </ul>

      {left != null && right != null && (
        <div className="anim-step-in px-well mt-5 p-4">
          <h4 className="text-sm font-semibold text-ink">
            Comparison:{" "}
            <span className="font-mono text-info">#{left}</span> →{" "}
            <span className="font-mono text-hypo">#{right}</span>
          </h4>
          {comparison.isLoading && (
            <p className="mt-2 text-xs text-faint">Loading comparison…</p>
          )}
          {comparison.data && (
            <>
              <p className="mt-2 text-sm text-muted">
                Overall{" "}
                <span className="text-ink">
                  {comparison.data.left.overall ?? "—"} → {comparison.data.right.overall ?? "—"}
                </span>{" "}
                <Delta value={comparison.data.overall_delta ?? 0} />
              </p>
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-faint">
                    <th className="pb-1.5 font-medium">Pillar</th>
                    <th className="pb-1.5 font-medium">A</th>
                    <th className="pb-1.5 font-medium">B</th>
                    <th className="pb-1.5 text-right font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.data.pillars.map((pillar) => (
                    <tr key={pillar.pillar} className="border-t-2 border-line">
                      <td className="py-1.5 text-ink">
                        {PILLAR_LABELS[pillar.pillar as Pillar] ?? pillar.pillar}
                      </td>
                      <td className="py-1.5 text-muted tabular-nums">{pillar.left_score}</td>
                      <td className="py-1.5 text-muted tabular-nums">{pillar.right_score}</td>
                      <td className="py-1.5 text-right">
                        <Delta value={pillar.delta} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {comparison.isError && (
            <p className="mt-2 text-xs text-danger">Could not compare these analyses.</p>
          )}
        </div>
      )}
    </section>
  );
}
